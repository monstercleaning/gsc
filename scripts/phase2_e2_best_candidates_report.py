#!/usr/bin/env python3
"""Deterministic stdlib Phase-2 E2 best-candidates reporting tool."""

from __future__ import annotations

import argparse
import glob
import gzip
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import sys
import tarfile
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gsc.measurement_model import (  # noqa: E402
    D_A_flat,
    FlatLambdaCDMHistory,
    GSCTransitionHistory,
    H0_to_SI,
)
from gsc.structure.growth_factor import growth_observables_from_solution, solve_growth_ln_a  # noqa: E402
from gsc.structure.power_spectrum_linear import sigma8_0_from_As  # noqa: E402
from gsc.structure.rsd_fsigma8_data import (  # noqa: E402
    chi2_diag,
    load_fsigma8_csv,
    profile_scale_chi2_diag,
)


SCHEMA_ID = "phase2_e2_best_candidates_report_v1"
BEST_CANDIDATES_SNIPPET_MARKER = "phase2_e2_best_candidates_snippet_v2"
SF_RSD_SNIPPET_MARKER = "phase2_sf_rsd_summary_snippet_v1"
DEFAULT_RSD_DATA_PATH = ROOT / "data" / "structure" / "fsigma8_gold2017_plus_zhao2018.csv"
RSD_CHI2_FIELD_PRIORITY: Tuple[str, ...] = ("rsd_chi2", "rsd_chi2_profiled", "rsd_chi2_min")
SF_RSD_DISCLAIMER = (
    "RSD fσ8 overlay is a linear-GR diagnostic assuming a standard CDM+baryon baseline; "
    "full freeze-frame perturbation theory is deferred."
)
AP_DA_TRAPZ_N = 4000
VOLATILE_FALLBACK_KEYS = {
    "created_utc",
    "updated_utc",
    "timestamp",
    "scan_started_utc",
    "scan_finished_utc",
}


@dataclass(frozen=True)
class ParsedRecord:
    source: str
    line: int
    status: str
    chi2_total: Optional[float]
    chi2_cmb: Optional[float]
    chi2_cmb_priors: Optional[float]
    params_hash: str
    params_hash_source: str
    plan_point_id: str
    model: str
    plausible_ok: bool
    plausible_present: bool
    parts_present: bool
    drift_summary: Dict[str, Any]
    drift_summary_short: str
    raw: Dict[str, Any]


@dataclass(frozen=True)
class InputFileStats:
    path: str
    bytes: int
    n_records: int
    n_invalid_lines: int


class RankingUnavailableError(ValueError):
    """Raised when requested ranking cannot be computed from available fields."""


def _finite_float(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except Exception:
        return None
    if not math.isfinite(out):
        return None
    return float(out)


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _decode_jsonl_bytes(source: str, data: bytes) -> str:
    raw = bytes(data)
    if str(source).lower().endswith(".gz"):
        try:
            raw = gzip.decompress(raw)
        except OSError as exc:
            raise ValueError(f"Invalid gzip JSONL payload: {source}") from exc
    return raw.decode("utf-8")


def _safe_member_path(name: str) -> bool:
    posix = PurePosixPath(str(name))
    if posix.is_absolute():
        return False
    return ".." not in posix.parts


def _is_bundle_file(path: Path) -> bool:
    lower = path.name.lower()
    return lower.endswith(".zip") or lower.endswith(".tar") or lower.endswith(".tgz") or lower.endswith(".tar.gz")


def _canonical_params(params: Mapping[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key in sorted(str(k) for k in params.keys()):
        value = params.get(key)
        if isinstance(value, (str, bool)):
            out[str(key)] = value
            continue
        if isinstance(value, int):
            out[str(key)] = int(value)
            continue
        f = _finite_float(value)
        if f is not None:
            out[str(key)] = float(f)
    return out


def _fallback_params_hash(record: Mapping[str, Any], *, line_text: str) -> Tuple[str, str]:
    params = record.get("params")
    if isinstance(params, Mapping):
        canonical = _canonical_params(params)
        if canonical:
            return _sha256_text(_canonical_json(canonical)), "params_fallback"

    payload = {
        str(k): record[k]
        for k in sorted(record.keys(), key=lambda x: str(x))
        if str(k) not in VOLATILE_FALLBACK_KEYS
    }
    if payload:
        try:
            return _sha256_text(_canonical_json(payload)), "record_fallback"
        except Exception:
            pass
    return _sha256_text(line_text.strip()), "line_fallback"


def _extract_params_hash(record: Mapping[str, Any], *, line_text: str) -> Tuple[str, str]:
    raw = record.get("params_hash")
    if isinstance(raw, str) and raw.strip():
        return raw.strip(), "params_hash"
    return _fallback_params_hash(record, line_text=line_text)


def _normalize_status(record: Mapping[str, Any]) -> str:
    raw = record.get("status")
    if raw is None:
        return "unknown"
    text = str(raw).strip().lower()
    return text if text else "unknown"


def _extract_chi2_parts(record: Mapping[str, Any]) -> Dict[str, float]:
    parts_raw = _as_mapping(record.get("chi2_parts"))
    parts: Dict[str, float] = {}
    for key in sorted(parts_raw.keys(), key=lambda x: str(x)):
        value = parts_raw[key]
        if isinstance(value, Mapping):
            comp = _finite_float(value.get("chi2"))
        else:
            comp = _finite_float(value)
        if comp is None:
            continue
        parts[str(key)] = float(comp)
    return parts


def _extract_chi2_total(record: Mapping[str, Any], *, parts: Mapping[str, float]) -> Optional[float]:
    for key in ("chi2_total", "chi2", "chi2_tot"):
        value = _finite_float(record.get(key))
        if value is not None:
            return value
    if parts:
        total = sum(float(v) for v in parts.values())
        if math.isfinite(total):
            return float(total)
    return None


def _extract_chi2_cmb(record: Mapping[str, Any], *, parts: Mapping[str, float]) -> Optional[float]:
    direct = _finite_float(record.get("chi2_cmb"))
    if direct is not None:
        return direct
    if "cmb_priors" in parts:
        return float(parts["cmb_priors"])
    if "cmb" in parts:
        return float(parts["cmb"])
    nested = _finite_float(_as_mapping(record.get("cmb_priors")).get("chi2"))
    if nested is not None:
        return nested
    nested = _finite_float(_as_mapping(record.get("cmb")).get("chi2"))
    if nested is not None:
        return nested
    return None


def _extract_chi2_cmb_priors(record: Mapping[str, Any], *, parts: Mapping[str, float]) -> Optional[float]:
    if "cmb_priors" in parts:
        return float(parts["cmb_priors"])
    nested = _finite_float(_as_mapping(record.get("cmb_priors")).get("chi2"))
    if nested is not None:
        return nested
    return None


def _extract_model(record: Mapping[str, Any]) -> str:
    for key in ("deformation_family", "deformation", "model", "family"):
        raw = record.get(key)
        if raw is None:
            continue
        text = str(raw).strip()
        if text:
            return text
    return "unknown"


def _extract_plan_point_id(record: Mapping[str, Any]) -> str:
    raw = record.get("plan_point_id")
    if raw is None:
        return ""
    text = str(raw).strip()
    return text


def _extract_plausibility(record: Mapping[str, Any]) -> Tuple[bool, bool]:
    if "microphysics_plausible_ok" not in record:
        return True, False
    raw = record.get("microphysics_plausible_ok")
    if isinstance(raw, bool):
        return bool(raw), True
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        f = _finite_float(raw)
        if f is None:
            return True, True
        return bool(f != 0.0), True
    text = str(raw).strip().lower()
    if text in {"1", "true", "t", "yes", "y", "ok"}:
        return True, True
    if text in {"0", "false", "f", "no", "n"}:
        return False, True
    return True, True


def _extract_drift_summary(record: Mapping[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    direct_keys = ("drift_precheck_ok", "drift_sign_z2_5", "drift_sign_z3", "drift_metric")
    for key in direct_keys:
        if key not in record:
            continue
        value = record.get(key)
        if isinstance(value, (bool, str)):
            out[key] = value
        else:
            fv = _finite_float(value)
            out[key] = fv if fv is not None else str(value)
        if len(out) >= 3:
            return out

    drift_obj = _as_mapping(record.get("drift"))
    nested_keys = ("all_positive", "min_z_dot", "min_zdot_si")
    for key in nested_keys:
        if key not in drift_obj:
            continue
        value = drift_obj.get(key)
        name = f"drift.{key}"
        if isinstance(value, (bool, str)):
            out[name] = value
        else:
            fv = _finite_float(value)
            out[name] = fv if fv is not None else str(value)
        if len(out) >= 3:
            return out
    return out


def _fmt_float(value: Any) -> str:
    fv = _finite_float(value)
    if fv is None:
        return "NA"
    abs_fv = abs(float(fv))
    if abs_fv >= 1e6 or (0.0 < abs_fv < 1e-4):
        return f"{float(fv):.6e}"
    return f"{float(fv):.6f}"


def _fmt_bool(value: Any) -> str:
    if value is None:
        return "NA"
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return "true"
    if text in {"false", "0", "no", "n"}:
        return "false"
    return "NA"


def _coerce_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        fv = _finite_float(value)
        if fv is None:
            return None
        return bool(fv != 0.0)
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y", "ok"}:
        return True
    if text in {"0", "false", "f", "no", "n"}:
        return False
    return None


def _extract_precomputed_rsd_chi2(
    raw: Mapping[str, Any], *, field_override: Optional[str]
) -> Tuple[Optional[float], Optional[str]]:
    if field_override is not None:
        key = str(field_override).strip()
        if not key:
            return None, None
        value = _finite_float(raw.get(key))
        if value is None:
            return None, None
        return float(value), key
    for key in RSD_CHI2_FIELD_PRIORITY:
        value = _finite_float(raw.get(key))
        if value is None:
            continue
        return float(value), key
    return None, None


def _drift_summary_short(drift_summary: Mapping[str, Any]) -> str:
    if not drift_summary:
        return "missing"
    parts: List[str] = []
    for key in sorted(drift_summary.keys(), key=lambda k: str(k)):
        value = drift_summary[key]
        if isinstance(value, bool):
            token = _fmt_bool(value)
        else:
            fv = _finite_float(value)
            token = _fmt_float(fv) if fv is not None else str(value)
        parts.append(f"{key}={token}")
    return ";".join(parts[:3])


def _is_eligible(record: ParsedRecord, *, status_filter: str, plausibility: str) -> bool:
    if record.chi2_total is None:
        return False
    if status_filter == "ok_only" and record.status != "ok":
        return False
    if status_filter == "any_eligible" and record.status == "error":
        return False
    if plausibility == "plausible_only" and not bool(record.plausible_ok):
        return False
    return True


def _sort_key(record: ParsedRecord) -> Tuple[Any, ...]:
    return (
        float(record.chi2_total) if record.chi2_total is not None else float("inf"),
        str(record.params_hash),
        str(record.source),
        int(record.line),
    )


def _pick_param_float(sources: Sequence[Mapping[str, Any]], *names: str) -> Optional[float]:
    targets = {str(name).strip().lower() for name in names if str(name).strip()}
    if not targets:
        return None
    for source in sources:
        for key in source.keys():
            key_text = str(key).strip().lower()
            if key_text not in targets:
                continue
            out = _finite_float(source.get(key))
            if out is not None:
                return float(out)
    return None


def _candidate_background_params(record: ParsedRecord) -> Dict[str, Optional[float]]:
    raw = _as_mapping(record.raw)
    params = _as_mapping(raw.get("params"))
    bestfit = _as_mapping(raw.get("bestfit_params"))
    sources: List[Mapping[str, Any]] = [raw, params, bestfit]

    h0 = _pick_param_float(sources, "H0", "h0", "h0_km_s_mpc", "hubble0")
    little_h = _pick_param_float(sources, "h", "little_h")
    if h0 is None and little_h is not None:
        h0 = float(100.0 * little_h)

    omega_m0 = _pick_param_float(sources, "omega_m", "omega_m0", "omegam", "om0", "Omega_m")
    omega_lambda0 = _pick_param_float(
        sources,
        "omega_lambda",
        "omega_l",
        "omega_l0",
        "omega_de",
        "Omega_Lambda",
        "Omega_lambda",
        "ol0",
    )
    p = _pick_param_float(sources, "p", "transition_p", "p_transition")
    z_transition = _pick_param_float(sources, "z_transition", "transition_z", "z_t", "zt")
    omega_b0 = _pick_param_float(sources, "omega_b", "omega_b0", "omegab", "Omega_b", "Omega_b0")
    As = _pick_param_float(sources, "As", "A_s", "as", "a_s")
    ns = _pick_param_float(sources, "ns", "n_s")
    return {
        "H0_km_s_Mpc": h0,
        "h": little_h if little_h is not None else (h0 / 100.0 if h0 is not None else None),
        "Omega_m0": omega_m0,
        "Omega_lambda0": omega_lambda0,
        "p": p,
        "z_transition": z_transition,
        "Omega_b0": omega_b0,
        "As": As,
        "ns": ns,
    }


def _build_candidate_history(record: ParsedRecord) -> Tuple[Any, float, float, Dict[str, Optional[float]], str]:
    params = _candidate_background_params(record)
    h0_km = params.get("H0_km_s_Mpc")
    omega_m0 = params.get("Omega_m0")
    if h0_km is None or omega_m0 is None:
        raise ValueError("missing_params:H0_or_Omega_m")

    h0_km_val = float(h0_km)
    omega_m0_val = float(omega_m0)
    if not (h0_km_val > 0.0 and omega_m0_val > 0.0):
        raise ValueError("invalid_params:H0_or_Omega_m_non_positive")

    omega_lambda0 = params.get("Omega_lambda0")
    if omega_lambda0 is None:
        omega_lambda0_val = float(1.0 - omega_m0_val)
    else:
        omega_lambda0_val = float(omega_lambda0)
    if not math.isfinite(omega_lambda0_val):
        raise ValueError("invalid_params:Omega_lambda_not_finite")
    if omega_lambda0_val < 0.0:
        raise ValueError("invalid_params:Omega_lambda_negative")

    h0_si = float(H0_to_SI(h0_km_val))
    p = params.get("p")
    z_transition = params.get("z_transition")
    if p is not None and z_transition is not None:
        history = GSCTransitionHistory(
            H0=h0_si,
            Omega_m=omega_m0_val,
            Omega_Lambda=omega_lambda0_val,
            p=float(p),
            z_transition=float(z_transition),
        )
        return history, h0_si, omega_m0_val, params, "gsc_transition"

    history = FlatLambdaCDMHistory(
        H0=h0_si,
        Omega_m=omega_m0_val,
        Omega_Lambda=omega_lambda0_val,
    )
    return history, h0_si, omega_m0_val, params, "lcdm"


def _compute_ap_factor(
    *,
    z: float,
    omega_m_ref: float,
    ap_mode: str,
    history: Any,
    h0_si: float,
    model_da_cache: Dict[float, float],
    ref_hd_cache: Dict[Tuple[float, float], Tuple[float, float]],
) -> float:
    if ap_mode == "off":
        return 1.0

    z_key = float(z)
    om_key = float(omega_m_ref)
    if z_key not in model_da_cache:
        h_model = float(history.H(z_key))
        da_model = float(D_A_flat(z=z_key, H_of_z=history.H, n=AP_DA_TRAPZ_N))
        if not (math.isfinite(h_model) and h_model > 0.0 and math.isfinite(da_model) and da_model > 0.0):
            raise ValueError("invalid model H(z) or D_A(z) in AP correction")
        model_da_cache[z_key] = da_model

    ref_key = (z_key, om_key)
    if ref_key not in ref_hd_cache:
        ref_history = FlatLambdaCDMHistory(
            H0=float(h0_si),
            Omega_m=float(om_key),
            Omega_Lambda=float(max(0.0, 1.0 - om_key)),
        )
        h_ref = float(ref_history.H(z_key))
        da_ref = float(D_A_flat(z=z_key, H_of_z=ref_history.H, n=AP_DA_TRAPZ_N))
        if not (math.isfinite(h_ref) and h_ref > 0.0 and math.isfinite(da_ref) and da_ref > 0.0):
            raise ValueError("invalid reference H(z) or D_A(z) in AP correction")
        ref_hd_cache[ref_key] = (h_ref, da_ref)

    h_model = float(history.H(z_key))
    da_model = float(model_da_cache[z_key])
    h_ref, da_ref = ref_hd_cache[ref_key]
    return float((h_ref * da_ref) / (h_model * da_model))


def _compute_candidate_rsd_overlay(
    *,
    record: ParsedRecord,
    rsd_rows: Sequence[Mapping[str, Any]],
    rsd_mode: str,
    ap_mode: str,
    rsd_chi2_field: Optional[str],
) -> Dict[str, Any]:
    if record.chi2_total is None:
        return {
            "sf_status": "missing_chi2_total",
            "chi2_rsd": None,
            "sigma8_0_best": None,
            "chi2_total_plus_rsd": None,
            "n_rsd_points": int(len(rsd_rows)),
        }
    raw = record.raw if isinstance(record.raw, Mapping) else {}
    pre_ok = _coerce_bool(raw.get("rsd_overlay_ok"))
    pre_chi2, pre_field = _extract_precomputed_rsd_chi2(raw, field_override=rsd_chi2_field)
    pre_joint = _finite_float(raw.get("chi2_joint_total"))
    pre_weight = _finite_float(raw.get("rsd_chi2_weight"))
    if pre_weight is None:
        pre_weight = 1.0
    if pre_joint is not None and pre_ok is not False:
        pre_sigma8 = _finite_float(raw.get("rsd_sigma8_0_best"))
        pre_n = int(_finite_float(raw.get("rsd_n")) or 0)
        chi2_total = _finite_float(record.chi2_total)
        if pre_chi2 is None and chi2_total is not None and abs(float(pre_weight)) > 0.0:
            pre_chi2 = float((float(pre_joint) - float(chi2_total)) / float(pre_weight))
        return {
            "sf_status": "ok",
            "chi2_rsd": None if pre_chi2 is None else float(pre_chi2),
            "sigma8_0_best": pre_sigma8,
            "chi2_total_plus_rsd": float(pre_joint),
            "n_rsd_points": int(max(pre_n, 0)),
            "sf_history": "precomputed",
            "rsd_chi2_field_used": str(pre_field or "chi2_joint_total"),
            "rsd_chi2_weight_used": float(pre_weight),
        }
    if pre_chi2 is not None and pre_ok is not False:
        pre_sigma8 = _finite_float(raw.get("rsd_sigma8_0_best"))
        pre_n = int(_finite_float(raw.get("rsd_n")) or 0)
        return {
            "sf_status": "ok",
            "chi2_rsd": float(pre_chi2),
            "sigma8_0_best": pre_sigma8,
            "chi2_total_plus_rsd": float(float(record.chi2_total) + float(pre_chi2)),
            "n_rsd_points": int(max(pre_n, 0)),
            "sf_history": "precomputed",
            "rsd_chi2_field_used": str(pre_field or "unknown"),
            "rsd_chi2_weight_used": 1.0,
        }
    
    try:
        history, h0_si, omega_m0, params, history_kind = _build_candidate_history(record)
    except ValueError as exc:
        return {
            "sf_status": "missing_params",
            "sf_error": str(exc),
            "chi2_rsd": None,
            "sigma8_0_best": None,
            "chi2_total_plus_rsd": None,
            "n_rsd_points": int(len(rsd_rows)),
        }

    z_targets = sorted({float(row.get("z")) for row in rsd_rows})
    if not z_targets:
        return {
            "sf_status": "missing_rsd_rows",
            "chi2_rsd": None,
            "sigma8_0_best": None,
            "chi2_total_plus_rsd": None,
            "n_rsd_points": 0,
            "rsd_chi2_field_used": None,
        }
    z_start = max(100.0, max(z_targets) + 5.0)

    def E_of_z(z: float) -> float:
        hz = float(history.H(float(z)))
        if not (math.isfinite(hz) and hz > 0.0):
            raise ValueError("non-positive or non-finite H(z)")
        return float(hz / h0_si)

    try:
        solution = solve_growth_ln_a(
            E_of_z,
            float(omega_m0),
            z_start=float(z_start),
            z_targets=z_targets,
            n_steps=4000,
            eps_dlnH=1.0e-5,
        )
        obs = growth_observables_from_solution(solution, z_targets)
    except Exception as exc:
        return {
            "sf_status": "error",
            "sf_error": f"growth_solver_failed:{exc}",
            "chi2_rsd": None,
            "sigma8_0_best": None,
            "chi2_total_plus_rsd": None,
            "n_rsd_points": int(len(rsd_rows)),
        }

    obs_by_z: Dict[float, Dict[str, float]] = {}
    for i, z in enumerate(obs.get("z", [])):
        obs_by_z[float(z)] = {
            "D": float(obs["D"][i]),
            "f": float(obs["f"][i]),
            "g": float(obs["g"][i]),
        }

    model_da_cache: Dict[float, float] = {}
    ref_hd_cache: Dict[Tuple[float, float], Tuple[float, float]] = {}
    data_y: List[float] = []
    sigmas: List[float] = []
    model_t: List[float] = []
    try:
        for row in rsd_rows:
            z = float(row.get("z"))
            obs_row = obs_by_z.get(float(z))
            if obs_row is None:
                raise ValueError("missing growth grid point")
            y = float(row.get("fsigma8"))
            sigma = float(row.get("sigma"))
            om_ref = float(row.get("omega_m_ref"))
            ap_factor = _compute_ap_factor(
                z=float(z),
                omega_m_ref=float(om_ref),
                ap_mode=ap_mode,
                history=history,
                h0_si=float(h0_si),
                model_da_cache=model_da_cache,
                ref_hd_cache=ref_hd_cache,
            )
            t_val = float(obs_row["g"] * ap_factor)
            if not (math.isfinite(y) and math.isfinite(sigma) and sigma > 0.0 and math.isfinite(t_val)):
                raise ValueError("non-finite row payload")
            data_y.append(float(y))
            sigmas.append(float(sigma))
            model_t.append(float(t_val))
    except Exception as exc:
        return {
            "sf_status": "error",
            "sf_error": f"rsd_row_processing_failed:{exc}",
            "chi2_rsd": None,
            "sigma8_0_best": None,
            "chi2_total_plus_rsd": None,
            "n_rsd_points": int(len(rsd_rows)),
        }

    if rsd_mode == "derived_As":
        As = params.get("As")
        ns = params.get("ns")
        if As is None or ns is None:
            return {
                "sf_status": "missing_params",
                "sf_error": "missing_params:As_or_ns",
                "chi2_rsd": None,
                "sigma8_0_best": None,
                "chi2_total_plus_rsd": None,
                "n_rsd_points": int(len(rsd_rows)),
                "sf_history": str(history_kind),
            }
        omega_b0 = params.get("Omega_b0")
        if omega_b0 is None:
            omega_b0 = 0.049
        h_raw = params.get("h")
        if h_raw is None:
            return {
                "sf_status": "missing_params",
                "sf_error": "missing_params:h",
                "chi2_rsd": None,
                "sigma8_0_best": None,
                "chi2_total_plus_rsd": None,
                "n_rsd_points": int(len(rsd_rows)),
                "sf_history": str(history_kind),
            }
        try:
            sigma8_0 = sigma8_0_from_As(
                As=float(As),
                ns=float(ns),
                omega_m0=float(omega_m0),
                h=float(h_raw),
                transfer="bbks",
                omega_b0=float(omega_b0),
                Tcmb_K=2.7255,
                E_of_z=E_of_z,
                z_start=float(z_start),
                n_steps=4000,
                eps_dlnH=1.0e-5,
            )
            preds = [float(sigma8_0 * t) for t in model_t]
            residuals = [float(y - p) for y, p in zip(data_y, preds)]
            chi2 = chi2_diag(residuals, sigmas)
        except Exception as exc:
            return {
                "sf_status": "error",
                "sf_error": f"derived_As_failed:{exc}",
                "chi2_rsd": None,
                "sigma8_0_best": None,
                "chi2_total_plus_rsd": None,
                "n_rsd_points": int(len(rsd_rows)),
                "sf_history": str(history_kind),
            }
        sigma8_best = float(sigma8_0)
        chi2_rsd = float(chi2)
    else:
        try:
            prof = profile_scale_chi2_diag(data_y, model_t, sigmas)
            scale = prof.get("scale_bestfit")
            chi2_min = prof.get("chi2_min")
            if scale is None or chi2_min is None:
                raise ValueError("sigma8 profiling denominator <= 0")
        except Exception as exc:
            return {
                "sf_status": "error",
                "sf_error": f"nuisance_sigma8_failed:{exc}",
                "chi2_rsd": None,
                "sigma8_0_best": None,
                "chi2_total_plus_rsd": None,
                "n_rsd_points": int(len(rsd_rows)),
                "sf_history": str(history_kind),
            }
        sigma8_best = float(scale)
        chi2_rsd = float(chi2_min)

    return {
        "sf_status": "ok",
        "chi2_rsd": float(chi2_rsd),
        "sigma8_0_best": float(sigma8_best),
        "chi2_total_plus_rsd": float(float(record.chi2_total) + float(chi2_rsd)),
        "n_rsd_points": int(len(rsd_rows)),
        "sf_history": str(history_kind),
        "rsd_chi2_field_used": "computed",
        "rsd_chi2_weight_used": 1.0,
    }


def _tex_escape(value: str) -> str:
    text = str(value)
    text = text.replace("\\", "\\textbackslash{}")
    text = text.replace("&", "\\&")
    text = text.replace("%", "\\%")
    text = text.replace("_", "\\_")
    text = text.replace("$", "\\$")
    text = text.replace("#", "\\#")
    text = text.replace("{", "\\{")
    text = text.replace("}", "\\}")
    return text


def _resolve_inputs(tokens: Sequence[str]) -> List[Path]:
    resolved: List[Path] = []
    seen: Set[Path] = set()
    for raw in tokens:
        token = str(raw).strip()
        if not token:
            continue
        expanded_any = False
        if any(ch in token for ch in "*?["):
            matches = sorted(glob.glob(token))
            for match in matches:
                path = Path(match).expanduser().resolve()
                if path in seen:
                    continue
                seen.add(path)
                resolved.append(path)
                expanded_any = True
            if not expanded_any:
                raise FileNotFoundError(f"Input glob matched no paths: {token}")
            continue

        path = Path(token).expanduser().resolve()
        if path in seen:
            continue
        seen.add(path)
        resolved.append(path)
    return resolved


def _iter_bundle_jsonl_payloads(bundle_path: Path) -> List[Tuple[str, bytes]]:
    lower = bundle_path.name.lower()
    if lower.endswith(".zip"):
        payloads: List[Tuple[str, bytes]] = []
        with zipfile.ZipFile(bundle_path, "r") as zf:
            names = sorted(
                name
                for name in zf.namelist()
                if not name.endswith("/")
                and (name.lower().endswith(".jsonl") or name.lower().endswith(".jsonl.gz"))
            )
            for name in names:
                if not _safe_member_path(name):
                    raise ValueError(f"Unsafe bundle member path: {name}")
                payloads.append((name, zf.read(name)))
        return payloads

    if lower.endswith(".tar") or lower.endswith(".tgz") or lower.endswith(".tar.gz"):
        payloads = []
        with tarfile.open(bundle_path, "r:*") as tf:
            members = sorted((m for m in tf.getmembers() if m.isfile()), key=lambda m: str(m.name))
            for member in members:
                name = str(member.name)
                if not (name.lower().endswith(".jsonl") or name.lower().endswith(".jsonl.gz")):
                    continue
                if not _safe_member_path(name):
                    raise ValueError(f"Unsafe bundle member path: {name}")
                fh = tf.extractfile(member)
                if fh is None:
                    continue
                payloads.append((name, fh.read()))
        return payloads

    raise ValueError(f"Unsupported bundle path/type: {bundle_path}")


def _parse_jsonl_text(source: str, text: str, *, bytes_len: int) -> Tuple[List[ParsedRecord], InputFileStats]:
    records: List[ParsedRecord] = []
    n_invalid = 0
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except Exception:
            n_invalid += 1
            continue
        if not isinstance(payload, Mapping):
            n_invalid += 1
            continue
        obj = {str(k): payload[k] for k in payload.keys()}
        parts = _extract_chi2_parts(obj)
        params_hash, params_hash_source = _extract_params_hash(obj, line_text=stripped)
        status = _normalize_status(obj)
        plausible_ok, plausible_present = _extract_plausibility(obj)
        drift_summary = _extract_drift_summary(obj)
        records.append(
            ParsedRecord(
                source=str(source),
                line=int(line_no),
                status=str(status),
                chi2_total=_extract_chi2_total(obj, parts=parts),
                chi2_cmb=_extract_chi2_cmb(obj, parts=parts),
                chi2_cmb_priors=_extract_chi2_cmb_priors(obj, parts=parts),
                params_hash=str(params_hash),
                params_hash_source=str(params_hash_source),
                plan_point_id=_extract_plan_point_id(obj),
                model=_extract_model(obj),
                plausible_ok=bool(plausible_ok),
                plausible_present=bool(plausible_present),
                parts_present=bool(parts),
                drift_summary={str(k): drift_summary[k] for k in sorted(drift_summary.keys())},
                drift_summary_short=_drift_summary_short(drift_summary),
                raw=obj,
            )
        )
    stats = InputFileStats(
        path=str(source),
        bytes=int(bytes_len),
        n_records=int(len(records)),
        n_invalid_lines=int(n_invalid),
    )
    return records, stats


def _load_records_from_path(path: Path) -> Tuple[List[ParsedRecord], List[InputFileStats]]:
    if not path.exists():
        raise FileNotFoundError(f"Input path not found: {path}")

    if path.is_dir():
        files = sorted(
            p.resolve()
            for p in list(path.glob("*.jsonl")) + list(path.glob("*.jsonl.gz"))
            if p.is_file()
        )
        if not files:
            raise FileNotFoundError(f"No *.jsonl/.jsonl.gz files found in directory: {path}")
        all_records: List[ParsedRecord] = []
        all_stats: List[InputFileStats] = []
        for file_path in files:
            data = file_path.read_bytes()
            parsed, stats = _parse_jsonl_text(
                str(file_path), _decode_jsonl_bytes(str(file_path), data), bytes_len=len(data)
            )
            all_records.extend(parsed)
            all_stats.append(stats)
        return all_records, all_stats

    if path.is_file():
        if _is_bundle_file(path):
            payloads = _iter_bundle_jsonl_payloads(path)
            if not payloads:
                raise FileNotFoundError(f"No *.jsonl/.jsonl.gz payloads found in bundle: {path}")
            all_records = []
            all_stats = []
            for member_name, data in payloads:
                source = f"{path}!{member_name}"
                parsed, stats = _parse_jsonl_text(
                    source, _decode_jsonl_bytes(member_name, data), bytes_len=len(data)
                )
                all_records.extend(parsed)
                all_stats.append(stats)
            return all_records, all_stats
        data = path.read_bytes()
        parsed, stats = _parse_jsonl_text(
            str(path), _decode_jsonl_bytes(str(path), data), bytes_len=len(data)
        )
        return parsed, [stats]

    raise FileNotFoundError(f"Unsupported input path type: {path}")


def _record_summary(record: ParsedRecord, *, rank: Optional[int] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "chi2_total": record.chi2_total,
        "chi2_cmb": record.chi2_cmb,
        "chi2_cmb_priors": record.chi2_cmb_priors,
        "drift_summary": {str(k): record.drift_summary[k] for k in sorted(record.drift_summary.keys())},
        "drift_summary_short": str(record.drift_summary_short),
        "microphysics_plausible_ok": bool(record.plausible_ok),
        "model": str(record.model),
        "params_hash": str(record.params_hash),
        "params_hash_short": str(record.params_hash)[:8],
        "params_hash_source": str(record.params_hash_source),
        "parts_present": bool(record.parts_present),
        "plan_point_id": str(record.plan_point_id),
        "source": str(record.source),
        "status": str(record.status),
    }
    if rank is not None:
        out["rank"] = int(rank)
    return out


def _build_payload(
    *,
    records: Sequence[ParsedRecord],
    input_paths_raw: Sequence[str],
    input_stats: Sequence[InputFileStats],
    status_filter: str,
    plausibility: str,
    top_n: int,
    rank_by: str,
    rsd_chi2_field: Optional[str],
    sf_rsd: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    status_counts: Dict[str, int] = {}
    n_missing_chi2 = 0
    n_non_plausible = 0

    for record in records:
        status = str(record.status)
        status_counts[status] = int(status_counts.get(status, 0) + 1)
        if record.chi2_total is None:
            n_missing_chi2 += 1
        if not bool(record.plausible_ok):
            n_non_plausible += 1

    eligible_base = [rec for rec in records if rec.chi2_total is not None and (status_filter != "ok_only" or rec.status == "ok")]
    eligible: List[ParsedRecord] = []
    for rec in eligible_base:
        if status_filter == "any_eligible" and rec.status == "error":
            continue
        if not _is_eligible(rec, status_filter=status_filter, plausibility=plausibility):
            continue
        eligible.append(rec)

    eligible_sorted = sorted(eligible, key=_sort_key)
    best_overall = eligible_sorted[0] if eligible_sorted else None

    plausible_pool = [rec for rec in eligible_base if rec.status != "error" and bool(rec.plausible_ok)]
    plausible_pool_sorted = sorted(plausible_pool, key=_sort_key)
    best_plausible = plausible_pool_sorted[0] if plausible_pool_sorted else None

    total_bytes = sum(int(row.bytes) for row in input_stats)
    n_invalid_lines = sum(int(row.n_invalid_lines) for row in input_stats)
    n_records_parsed = len(records)

    candidate_rows: List[Dict[str, Any]] = []
    for idx, rec in enumerate(eligible_sorted):
        row = _record_summary(rec)
        row["_sort_idx"] = int(idx)
        candidate_rows.append(row)

    sf_enabled = bool(sf_rsd is not None or rank_by in {"rsd", "joint"})
    sf_overlay_payload: Optional[Dict[str, Any]] = None
    rsd_rows_cfg = list((sf_rsd or {}).get("rows") or [])
    rsd_mode_cfg = str((sf_rsd or {}).get("mode") or "nuisance_sigma8")
    ap_mode_cfg = str((sf_rsd or {}).get("ap_correction") or "off")
    rsd_data_path_cfg = str((sf_rsd or {}).get("data_path") or "")

    if sf_enabled:
        for row, rec in zip(candidate_rows, eligible_sorted):
            overlay = _compute_candidate_rsd_overlay(
                record=rec,
                rsd_rows=rsd_rows_cfg,
                rsd_mode=rsd_mode_cfg,
                ap_mode=ap_mode_cfg,
                rsd_chi2_field=rsd_chi2_field,
            )
            row.update(
                {
                    "chi2_rsd": overlay.get("chi2_rsd"),
                    "sigma8_0_best": overlay.get("sigma8_0_best"),
                    "chi2_total_plus_rsd": overlay.get("chi2_total_plus_rsd"),
                    "joint_score": overlay.get("chi2_total_plus_rsd"),
                    "chi2_joint_total": overlay.get("chi2_total_plus_rsd"),
                    "n_rsd_points": int(overlay.get("n_rsd_points", 0)),
                    "sf_status": str(overlay.get("sf_status", "unknown")),
                    "sf_history": str(overlay.get("sf_history", "unknown")),
                    "rsd_chi2_field_used": overlay.get("rsd_chi2_field_used"),
                    "rsd_chi2_weight_used": overlay.get("rsd_chi2_weight_used"),
                }
            )
            if overlay.get("sf_error"):
                row["sf_error"] = str(overlay.get("sf_error"))

    def _metric_for_rank(item: Mapping[str, Any]) -> Optional[float]:
        if rank_by == "cmb":
            return _finite_float(item.get("chi2_total"))
        if rank_by == "rsd":
            return _finite_float(item.get("chi2_rsd"))
        return _finite_float(item.get("joint_score"))

    def _rankable(item: Mapping[str, Any]) -> bool:
        metric = _metric_for_rank(item)
        if metric is None:
            return False
        if rank_by in {"rsd", "joint"} and str(item.get("sf_status", "unknown")) != "ok":
            return False
        return True

    rankable_rows = [row for row in candidate_rows if _rankable(row)]
    if rank_by in {"rsd", "joint"} and not rankable_rows:
        if rank_by == "joint":
            raise RankingUnavailableError(
                "MISSING_RSD_CHI2_FIELD_FOR_JOINT_OBJECTIVE: missing required RSD fields for joint ranking"
            )
        raise RankingUnavailableError("MISSING_RSD_CHI2_FIELD: missing required RSD fields for rsd ranking")

    def _rank_sort_key(item: Mapping[str, Any]) -> Tuple[Any, ...]:
        metric = _metric_for_rank(item)
        return (
            float(metric) if metric is not None else float("inf"),
            str(item.get("params_hash", "")),
            int(item.get("_sort_idx", 0)),
        )

    ranked_rows_sorted = sorted(rankable_rows if rank_by in {"rsd", "joint"} else candidate_rows, key=_rank_sort_key)
    top_rows = ranked_rows_sorted[: max(1, int(top_n))]
    top_candidates: List[Dict[str, Any]] = []
    for rank, row in enumerate(top_rows, start=1):
        out = dict(row)
        out["rank"] = int(rank)
        top_candidates.append(out)

    best_cmb_row = candidate_rows[0] if candidate_rows else None
    joint_rows = [
        row
        for row in candidate_rows
        if _finite_float(row.get("joint_score")) is not None and str(row.get("sf_status", "unknown")) == "ok"
    ]
    best_joint_row = (
        sorted(
            joint_rows,
            key=lambda item: (
                float(_finite_float(item.get("joint_score")) or float("inf")),
                str(item.get("params_hash", "")),
                int(item.get("_sort_idx", 0)),
            ),
        )[0]
        if joint_rows
        else None
    )
    rsd_rows_rank = [
        row
        for row in candidate_rows
        if _finite_float(row.get("chi2_rsd")) is not None and str(row.get("sf_status", "unknown")) == "ok"
    ]
    best_rsd_row = sorted(
        rsd_rows_rank,
        key=lambda item: (
            float(_finite_float(item.get("chi2_rsd")) or float("inf")),
            str(item.get("params_hash", "")),
            int(item.get("_sort_idx", 0)),
        ),
    )[0] if rsd_rows_rank else None

    def _public_row(item: Optional[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
        if item is None:
            return None
        out: Dict[str, Any] = {}
        for key in sorted(item.keys(), key=lambda x: str(x)):
            text_key = str(key)
            if text_key.startswith("_"):
                continue
            out[text_key] = item[key]
        return out

    if sf_enabled:
        data_sha_values = sorted(
            {
                str(rec.raw.get("rsd_dataset_sha256", "")).strip().lower()
                for rec in eligible_sorted
                if str(rec.raw.get("rsd_dataset_sha256", "")).strip()
            }
        )
        data_id_values = sorted(
            {
                str(rec.raw.get("rsd_dataset_id", "")).strip()
                for rec in eligible_sorted
                if str(rec.raw.get("rsd_dataset_id", "")).strip()
            }
        )
        ap_values = sorted(
            {
                str(rec.raw.get("rsd_ap_correction", "")).strip()
                for rec in eligible_sorted
                if str(rec.raw.get("rsd_ap_correction", "")).strip()
            }
        )
        mode_values = sorted(
            {
                str(rec.raw.get("rsd_mode", "")).strip()
                for rec in eligible_sorted
                if str(rec.raw.get("rsd_mode", "")).strip()
            }
        )
        field_values = sorted(
            {
                str(row.get("rsd_chi2_field_used", "")).strip()
                for row in candidate_rows
                if str(row.get("rsd_chi2_field_used", "")).strip()
            }
        )
        weight_values = sorted(
            {
                float(_finite_float(row.get("rsd_chi2_weight_used")) or 0.0)
                for row in candidate_rows
                if _finite_float(row.get("rsd_chi2_weight_used")) is not None
            }
        )
        sf_overlay_payload = {
            "enabled": True,
            "data_path": rsd_data_path_cfg,
            "rsd_dataset_id": data_id_values[0] if len(data_id_values) == 1 else ("mixed" if data_id_values else ""),
            "rsd_dataset_sha256": data_sha_values[0] if len(data_sha_values) == 1 else ("mixed" if data_sha_values else ""),
            "n_points": int(len(rsd_rows_cfg)),
            "rsd_mode": rsd_mode_cfg if sf_rsd is not None else (mode_values[0] if len(mode_values) == 1 else ""),
            "ap_correction_mode": ap_mode_cfg if sf_rsd is not None else (ap_values[0] if len(ap_values) == 1 else ""),
            "rsd_chi2_field_used": field_values[0] if len(field_values) == 1 else ("mixed" if field_values else ""),
            "rsd_chi2_weight_used": weight_values[0] if len(weight_values) == 1 else ("mixed" if weight_values else None),
            "best_by_cmb": _public_row(best_cmb_row),
            "best_by_joint": _public_row(best_joint_row),
            "best_by_rsd": _public_row(best_rsd_row),
            "disclaimer": SF_RSD_DISCLAIMER,
        }

    payload: Dict[str, Any] = {
        "schema": SCHEMA_ID,
        "filters": {
            "plausibility": str(plausibility),
            "rank_by": str(rank_by),
            "rsd_chi2_field": str(rsd_chi2_field or ""),
            "status_filter": str(status_filter),
            "top_n": int(top_n),
        },
        "header": {
            "n_files_expanded": int(len(input_stats)),
            "n_inputs": int(len(input_paths_raw)),
            "n_invalid_lines": int(n_invalid_lines),
            "n_missing_chi2": int(n_missing_chi2),
            "n_missing_rsd_chi2": int(
                sum(1 for row in candidate_rows if _finite_float(row.get("chi2_rsd")) is None)
            ),
            "n_records_parsed": int(n_records_parsed),
            "total_bytes": int(total_bytes),
        },
        "status_counts": {str(k): int(status_counts[k]) for k in sorted(status_counts.keys())},
        "best_overall_eligible": _record_summary(best_overall) if best_overall is not None else None,
        "best_by_cmb": _public_row(best_cmb_row),
        "best_by_joint": _public_row(best_joint_row),
        "joint_chi2_total_best": (
            _finite_float(best_joint_row.get("joint_score")) if best_joint_row is not None else None
        ),
        "rsd_chi2_field_used": (
            None
            if sf_overlay_payload is None
            else sf_overlay_payload.get("rsd_chi2_field_used")
        ),
        "rsd_chi2_weight_used": (
            None
            if sf_overlay_payload is None
            else sf_overlay_payload.get("rsd_chi2_weight_used")
        ),
        "best_plausible_eligible": _record_summary(best_plausible) if best_plausible is not None else None,
        "top_candidates": [_public_row(row) or {} for row in top_candidates],
        "input_files": [
            {
                "bytes": int(row.bytes),
                "n_invalid_lines": int(row.n_invalid_lines),
                "n_records": int(row.n_records),
                "path": str(row.path),
            }
            for row in sorted(input_stats, key=lambda item: str(item.path))
        ],
        "notes": {
            "n_non_plausible_records": int(n_non_plausible),
            "plausibility_missing_defaults_to_true": True,
        },
    }
    if sf_overlay_payload is not None:
        payload["sf_rsd_overlay"] = sf_overlay_payload
    return payload


def _render_text(payload: Mapping[str, Any]) -> str:
    header = _as_mapping(payload.get("header"))
    filters = _as_mapping(payload.get("filters"))
    status_counts = _as_mapping(payload.get("status_counts"))
    top_rows = payload.get("top_candidates")
    best_overall = _as_mapping(payload.get("best_overall_eligible"))
    best_plausible = _as_mapping(payload.get("best_plausible_eligible"))
    sf_overlay = _as_mapping(payload.get("sf_rsd_overlay"))
    sf_enabled = bool(sf_overlay.get("enabled"))

    lines: List[str] = []
    lines.append("== Header ==")
    lines.append(f"schema={payload.get('schema', 'UNKNOWN')}")
    lines.append(f"n_inputs={int(header.get('n_inputs', 0))}")
    lines.append(f"n_files_expanded={int(header.get('n_files_expanded', 0))}")
    lines.append(f"n_records_parsed={int(header.get('n_records_parsed', 0))}")
    lines.append(f"n_invalid_lines={int(header.get('n_invalid_lines', 0))}")
    lines.append(f"n_missing_chi2={int(header.get('n_missing_chi2', 0))}")
    lines.append(f"status_filter={filters.get('status_filter', '')}")
    lines.append(f"plausibility={filters.get('plausibility', '')}")
    lines.append(f"rank_by={filters.get('rank_by', 'cmb')}")
    lines.append(f"rsd_chi2_field={filters.get('rsd_chi2_field', '')}")
    lines.append(f"top_n={int(filters.get('top_n', 0))}")
    lines.append("")

    lines.append("== StatusCounts ==")
    buckets = sorted(
        ((str(k), int(v)) for k, v in status_counts.items()),
        key=lambda item: (-int(item[1]), str(item[0])),
    )
    for key, count in buckets:
        lines.append(f"status={key} count={count}")
    lines.append("")

    lines.append("== BestOverallEligible ==")
    if best_overall:
        lines.append(f"chi2_total={_fmt_float(best_overall.get('chi2_total'))}")
        lines.append(f"status={best_overall.get('status', 'NA')}")
        lines.append(f"params_hash={best_overall.get('params_hash', 'NA')}")
        lines.append(f"plan_point_id={best_overall.get('plan_point_id', '') or '-'}")
        lines.append(f"microphysics_plausible_ok={_fmt_bool(best_overall.get('microphysics_plausible_ok'))}")
        lines.append(f"drift_summary={best_overall.get('drift_summary_short', 'missing')}")
    else:
        lines.append("best_overall_eligible=NONE")
    lines.append("")

    lines.append("== BestPlausibleEligible ==")
    if best_plausible:
        lines.append(f"chi2_total={_fmt_float(best_plausible.get('chi2_total'))}")
        lines.append(f"status={best_plausible.get('status', 'NA')}")
        lines.append(f"params_hash={best_plausible.get('params_hash', 'NA')}")
        lines.append(f"plan_point_id={best_plausible.get('plan_point_id', '') or '-'}")
        lines.append(f"microphysics_plausible_ok={_fmt_bool(best_plausible.get('microphysics_plausible_ok'))}")
        lines.append(f"drift_summary={best_plausible.get('drift_summary_short', 'missing')}")
    else:
        lines.append("best_plausible_eligible=NONE")
    lines.append("")

    lines.append("== TopCandidates ==")
    if isinstance(top_rows, Sequence):
        for item in top_rows:
            if not isinstance(item, Mapping):
                continue
            line = (
                "rank={rank} chi2_total={chi2} status={status} plausible={plausible} "
                "id={identifier} model={model} drift={drift}".format(
                    rank=int(item.get("rank", 0)),
                    chi2=_fmt_float(item.get("chi2_total")),
                    status=str(item.get("status", "")),
                    plausible=_fmt_bool(item.get("microphysics_plausible_ok")),
                    identifier=str(item.get("plan_point_id", "") or item.get("params_hash_short", "")),
                    model=str(item.get("model", "")),
                    drift=str(item.get("drift_summary_short", "missing")),
                )
            )
            if sf_enabled:
                line += (
                    " chi2_rsd={chi2_rsd} sigma8_0_best={sigma8} chi2_total_plus_rsd={chi2_plus} sf_status={sf_status}"
                ).format(
                    chi2_rsd=_fmt_float(item.get("chi2_rsd")),
                    sigma8=_fmt_float(item.get("sigma8_0_best")),
                    chi2_plus=_fmt_float(item.get("chi2_total_plus_rsd")),
                    sf_status=str(item.get("sf_status", "unknown")),
                )
            lines.append(line)

    if sf_enabled:
        lines.append("")
        lines.append("== RSDOverlay ==")
        lines.append(f"data_path={sf_overlay.get('data_path', '')}")
        lines.append(f"n_points={int(sf_overlay.get('n_points', 0))}")
        lines.append(f"rsd_mode={sf_overlay.get('rsd_mode', '')}")
        lines.append(f"ap_correction={sf_overlay.get('ap_correction_mode', '')}")
        lines.append(f"rsd_dataset_id={sf_overlay.get('rsd_dataset_id', '')}")
        lines.append(f"rsd_dataset_sha256={sf_overlay.get('rsd_dataset_sha256', '')}")
        lines.append(f"rsd_chi2_field_used={sf_overlay.get('rsd_chi2_field_used', '')}")
        best_cmb = _as_mapping(sf_overlay.get("best_by_cmb"))
        best_joint = _as_mapping(sf_overlay.get("best_by_joint"))
        if best_cmb:
            lines.append(
                "best_by_cmb params_hash={hash} chi2_total={chi2} chi2_rsd={chi2_rsd} "
                "joint_score={chi2_plus} sigma8_0_best={sigma8} sf_status={sf_status}".format(
                    hash=str(best_cmb.get("params_hash", "")),
                    chi2=_fmt_float(best_cmb.get("chi2_total")),
                    chi2_rsd=_fmt_float(best_cmb.get("chi2_rsd")),
                    chi2_plus=_fmt_float(best_cmb.get("joint_score", best_cmb.get("chi2_total_plus_rsd"))),
                    sigma8=_fmt_float(best_cmb.get("sigma8_0_best")),
                    sf_status=str(best_cmb.get("sf_status", "unknown")),
                )
            )
        else:
            lines.append("best_by_cmb=NONE")
        if best_joint:
            lines.append(
                "best_by_joint params_hash={hash} chi2_total={chi2} chi2_rsd={chi2_rsd} "
                "joint_score={chi2_plus} sigma8_0_best={sigma8} sf_status={sf_status}".format(
                    hash=str(best_joint.get("params_hash", "")),
                    chi2=_fmt_float(best_joint.get("chi2_total")),
                    chi2_rsd=_fmt_float(best_joint.get("chi2_rsd")),
                    chi2_plus=_fmt_float(best_joint.get("joint_score", best_joint.get("chi2_total_plus_rsd"))),
                    sigma8=_fmt_float(best_joint.get("sigma8_0_best")),
                    sf_status=str(best_joint.get("sf_status", "unknown")),
                )
            )
        else:
            lines.append("best_by_joint=NONE")
            lines.append("joint_ranking_unavailable=missing_rsd_fields")
        lines.append(f"note={sf_overlay.get('disclaimer', SF_RSD_DISCLAIMER)}")
    return "\n".join(lines)


def _render_md(payload: Mapping[str, Any], *, title: str) -> str:
    header = _as_mapping(payload.get("header"))
    filters = _as_mapping(payload.get("filters"))
    best_overall = _as_mapping(payload.get("best_overall_eligible"))
    best_plausible = _as_mapping(payload.get("best_plausible_eligible"))
    top_rows = payload.get("top_candidates")
    sf_overlay = _as_mapping(payload.get("sf_rsd_overlay"))
    sf_enabled = bool(sf_overlay.get("enabled"))

    lines: List[str] = []
    lines.append(f"<!-- {BEST_CANDIDATES_SNIPPET_MARKER} -->")
    lines.append("")
    lines.append(f"# {title}")
    lines.append("")
    lines.append("Deterministic Phase-2 E2 top-candidate summary from compressed-priors diagnostics.")
    lines.append("")
    lines.append("## Header")
    lines.append("")
    lines.append(f"- n_inputs: `{int(header.get('n_inputs', 0))}`")
    lines.append(f"- n_files_expanded: `{int(header.get('n_files_expanded', 0))}`")
    lines.append(f"- n_records_parsed: `{int(header.get('n_records_parsed', 0))}`")
    lines.append(f"- n_invalid_lines: `{int(header.get('n_invalid_lines', 0))}`")
    lines.append(f"- n_missing_chi2: `{int(header.get('n_missing_chi2', 0))}`")
    lines.append(f"- status_filter: `{filters.get('status_filter', '')}`")
    lines.append(f"- plausibility: `{filters.get('plausibility', '')}`")
    lines.append(f"- rank_by: `{filters.get('rank_by', 'cmb')}`")
    lines.append(f"- rsd_chi2_field: `{filters.get('rsd_chi2_field', '')}`")
    lines.append(f"- top_n: `{int(filters.get('top_n', 0))}`")
    lines.append("")

    lines.append("## Best records")
    lines.append("")
    if best_overall:
        lines.append(
            "- best_overall_eligible: "
            f"`chi2_total={_fmt_float(best_overall.get('chi2_total'))}`, "
            f"`status={best_overall.get('status', 'NA')}`, "
            f"`params_hash={best_overall.get('params_hash', 'NA')}`, "
            f"`plan_point_id={best_overall.get('plan_point_id', '') or '-'}`, "
            f"`plausible={_fmt_bool(best_overall.get('microphysics_plausible_ok'))}`, "
            f"`drift={best_overall.get('drift_summary_short', 'missing')}`"
        )
    else:
        lines.append("- best_overall_eligible: `NONE`")

    if best_plausible:
        lines.append(
            "- best_plausible_eligible: "
            f"`chi2_total={_fmt_float(best_plausible.get('chi2_total'))}`, "
            f"`status={best_plausible.get('status', 'NA')}`, "
            f"`params_hash={best_plausible.get('params_hash', 'NA')}`, "
            f"`plan_point_id={best_plausible.get('plan_point_id', '') or '-'}`, "
            f"`plausible={_fmt_bool(best_plausible.get('microphysics_plausible_ok'))}`, "
            f"`drift={best_plausible.get('drift_summary_short', 'missing')}`"
        )
    else:
        lines.append("- best_plausible_eligible: `NONE`")
    lines.append("")

    lines.append("## Top-N table")
    lines.append("")
    if sf_enabled:
        lines.append(
            "| rank | chi2_total | chi2_rsd | chi2_total_plus_rsd | sigma8_0_best | sf_status | status | plausible | id | model | drift |"
        )
        lines.append("|---:|---:|---:|---:|---:|---|---|---:|---|---|---|")
    else:
        lines.append("| rank | chi2_total | status | plausible | id | model | drift |")
        lines.append("|---:|---:|---|---:|---|---|---|")
    if isinstance(top_rows, Sequence):
        for item in top_rows:
            if not isinstance(item, Mapping):
                continue
            if sf_enabled:
                lines.append(
                    "| "
                    + str(int(item.get("rank", 0)))
                    + " | "
                    + _fmt_float(item.get("chi2_total"))
                    + " | "
                    + _fmt_float(item.get("chi2_rsd"))
                    + " | "
                    + _fmt_float(item.get("chi2_total_plus_rsd"))
                    + " | "
                    + _fmt_float(item.get("sigma8_0_best"))
                    + " | "
                    + str(item.get("sf_status", "unknown"))
                    + " | "
                    + str(item.get("status", ""))
                    + " | "
                    + _fmt_bool(item.get("microphysics_plausible_ok"))
                    + " | "
                    + str(item.get("plan_point_id", "") or item.get("params_hash_short", ""))
                    + " | "
                    + str(item.get("model", ""))
                    + " | "
                    + str(item.get("drift_summary_short", "missing"))
                    + " |"
                )
            else:
                lines.append(
                    "| "
                    + str(int(item.get("rank", 0)))
                    + " | "
                    + _fmt_float(item.get("chi2_total"))
                    + " | "
                    + str(item.get("status", ""))
                    + " | "
                    + _fmt_bool(item.get("microphysics_plausible_ok"))
                    + " | "
                    + str(item.get("plan_point_id", "") or item.get("params_hash_short", ""))
                    + " | "
                    + str(item.get("model", ""))
                    + " | "
                    + str(item.get("drift_summary_short", "missing"))
                    + " |"
                )
    if sf_enabled:
        lines.append("")
        lines.append("## Structure formation diagnostics (RSD fσ8)")
        lines.append("")
        lines.append(f"- data_path: `{sf_overlay.get('data_path', '')}`")
        lines.append(f"- n_points: `{int(sf_overlay.get('n_points', 0))}`")
        lines.append(f"- rsd_mode: `{sf_overlay.get('rsd_mode', '')}`")
        lines.append(f"- ap_correction_mode: `{sf_overlay.get('ap_correction_mode', '')}`")
        lines.append(f"- rsd_dataset_id: `{sf_overlay.get('rsd_dataset_id', '')}`")
        lines.append(f"- rsd_dataset_sha256: `{sf_overlay.get('rsd_dataset_sha256', '')}`")
        lines.append(f"- rsd_chi2_field_used: `{sf_overlay.get('rsd_chi2_field_used', '')}`")
        best_cmb = _as_mapping(sf_overlay.get("best_by_cmb"))
        best_joint = _as_mapping(sf_overlay.get("best_by_joint"))
        if best_cmb:
            lines.append(
                "- Best by CMB (eligible): "
                f"`params_hash={best_cmb.get('params_hash', '')}` "
                f"`chi2_total={_fmt_float(best_cmb.get('chi2_total'))}` "
                f"`chi2_rsd={_fmt_float(best_cmb.get('chi2_rsd'))}` "
                f"`joint_score={_fmt_float(best_cmb.get('joint_score', best_cmb.get('chi2_total_plus_rsd')))} `"
                f"`sigma8_0_best={_fmt_float(best_cmb.get('sigma8_0_best'))}` "
                f"`status={best_cmb.get('status', 'unknown')}` "
                f"`plausible={_fmt_bool(best_cmb.get('microphysics_plausible_ok'))}` "
                f"`plan_point_id={best_cmb.get('plan_point_id', '')}`"
            )
        else:
            lines.append("- Best by CMB (eligible): `NONE`")
        if best_joint:
            lines.append(
                "- Best by joint CMB+RSD (eligible): "
                f"`params_hash={best_joint.get('params_hash', '')}` "
                f"`chi2_total={_fmt_float(best_joint.get('chi2_total'))}` "
                f"`chi2_rsd={_fmt_float(best_joint.get('chi2_rsd'))}` "
                f"`joint_score={_fmt_float(best_joint.get('joint_score', best_joint.get('chi2_total_plus_rsd')))} `"
                f"`sigma8_0_best={_fmt_float(best_joint.get('sigma8_0_best'))}` "
                f"`status={best_joint.get('status', 'unknown')}` "
                f"`plausible={_fmt_bool(best_joint.get('microphysics_plausible_ok'))}` "
                f"`plan_point_id={best_joint.get('plan_point_id', '')}`"
            )
        else:
            lines.append("- Best by joint CMB+RSD (eligible): `joint ranking unavailable: missing RSD fields`")
        lines.append(f"- note: {sf_overlay.get('disclaimer', SF_RSD_DISCLAIMER)}")
    lines.append("")
    lines.append("Diagnostic-only summary: this table reports pipeline output under current filters and does not add new physics claims.")
    return "\n".join(lines)


def _render_tex(payload: Mapping[str, Any], *, title: str) -> str:
    top_rows = payload.get("top_candidates")
    sf_overlay = _as_mapping(payload.get("sf_rsd_overlay"))
    sf_enabled = bool(sf_overlay.get("enabled"))
    lines: List[str] = []
    lines.append(f"% {BEST_CANDIDATES_SNIPPET_MARKER}")
    lines.append("% Auto-generated by phase2_e2_best_candidates_report.py")
    lines.append(f"% {title}")
    if sf_enabled:
        lines.append("\\begin{tabular}{rllllllllll}")
    else:
        lines.append("\\begin{tabular}{rllllll}")
    lines.append("\\hline")
    if sf_enabled:
        lines.append(
            "rank & chi2\\_total & chi2\\_rsd & chi2\\_total+rsd & sigma8\\_0 & sf\\_status & status & plausible & id & model & drift \\\\"
        )
    else:
        lines.append("rank & chi2\\_total & status & plausible & id & model & drift \\\\")
    lines.append("\\hline")
    if isinstance(top_rows, Sequence):
        for item in top_rows:
            if not isinstance(item, Mapping):
                continue
            if sf_enabled:
                cells = [
                    str(int(item.get("rank", 0))),
                    _tex_escape(_fmt_float(item.get("chi2_total"))),
                    _tex_escape(_fmt_float(item.get("chi2_rsd"))),
                    _tex_escape(_fmt_float(item.get("chi2_total_plus_rsd"))),
                    _tex_escape(_fmt_float(item.get("sigma8_0_best"))),
                    _tex_escape(str(item.get("sf_status", "unknown"))),
                    _tex_escape(str(item.get("status", ""))),
                    _tex_escape(_fmt_bool(item.get("microphysics_plausible_ok"))),
                    _tex_escape(str(item.get("plan_point_id", "") or item.get("params_hash_short", ""))),
                    _tex_escape(str(item.get("model", ""))),
                    _tex_escape(str(item.get("drift_summary_short", "missing"))),
                ]
            else:
                cells = [
                    str(int(item.get("rank", 0))),
                    _tex_escape(_fmt_float(item.get("chi2_total"))),
                    _tex_escape(str(item.get("status", ""))),
                    _tex_escape(_fmt_bool(item.get("microphysics_plausible_ok"))),
                    _tex_escape(str(item.get("plan_point_id", "") or item.get("params_hash_short", ""))),
                    _tex_escape(str(item.get("model", ""))),
                    _tex_escape(str(item.get("drift_summary_short", "missing"))),
                ]
            lines.append(" & ".join(cells) + " \\\\")
    lines.append("\\hline")
    lines.append("\\end{tabular}")
    if sf_enabled:
        lines.append("")
        lines.append("\\paragraph{Structure formation diagnostics (RSD $f\\sigma_8$)}")
        lines.append(
            "Dataset: \\texttt{"
            + _tex_escape(str(sf_overlay.get("data_path", "")))
            + "} (N="
            + str(int(sf_overlay.get("n_points", 0)))
            + "). "
            + _tex_escape(str(sf_overlay.get("disclaimer", SF_RSD_DISCLAIMER)))
        )
        best_cmb = _as_mapping(sf_overlay.get("best_by_cmb"))
        best_joint = _as_mapping(sf_overlay.get("best_by_joint"))
        if best_cmb:
            lines.append(
                "Best by CMB (eligible): $\\chi^2_\\mathrm{total}="
                + _tex_escape(_fmt_float(best_cmb.get("chi2_total")))
                + "$, $\\chi^2_\\mathrm{RSD}="
                + _tex_escape(_fmt_float(best_cmb.get("chi2_rsd")))
                + "$, $\\chi^2_\\mathrm{joint}="
                + _tex_escape(_fmt_float(best_cmb.get("joint_score", best_cmb.get("chi2_total_plus_rsd"))))
                + "$, $\\sigma_{8,0}="
                + _tex_escape(_fmt_float(best_cmb.get("sigma8_0_best")))
                + "$, \\texttt{"
                + _tex_escape(str(best_cmb.get("params_hash", "")))
                + "}."
            )
        else:
            lines.append("Best by CMB (eligible): unavailable.")
        if best_joint:
            lines.append(
                "Best by joint CMB+RSD (eligible): $\\chi^2_\\mathrm{total}="
                + _tex_escape(_fmt_float(best_joint.get("chi2_total")))
                + "$, $\\chi^2_\\mathrm{RSD}="
                + _tex_escape(_fmt_float(best_joint.get("chi2_rsd")))
                + "$, $\\chi^2_\\mathrm{joint}="
                + _tex_escape(_fmt_float(best_joint.get("joint_score", best_joint.get("chi2_total_plus_rsd"))))
                + "$, $\\sigma_{8,0}="
                + _tex_escape(_fmt_float(best_joint.get("sigma8_0_best")))
                + "$, \\texttt{"
                + _tex_escape(str(best_joint.get("params_hash", "")))
                + "}."
            )
        else:
            lines.append("Best by joint CMB+RSD (eligible): joint ranking unavailable (missing RSD fields).")
    lines.append("")
    lines.append(
        "Compressed-priors pipeline summary only; candidate ranking is conditional on the selected filters and scanned families."
    )
    return "\n".join(lines)


def _render_sf_rsd_summary_md(payload: Mapping[str, Any]) -> str:
    sf_overlay = _as_mapping(payload.get("sf_rsd_overlay"))
    lines: List[str] = [f"<!-- {SF_RSD_SNIPPET_MARKER} -->", "## Structure formation diagnostics (RSD fσ8)", ""]
    if not sf_overlay:
        lines.append("- overlay_status: `unavailable`")
        lines.append("- note: RSD overlay was not enabled for this report run.")
        return "\n".join(lines)

    lines.append(f"- dataset: `{sf_overlay.get('data_path', '')}`")
    lines.append(f"- n_points: `{int(sf_overlay.get('n_points', 0))}`")
    lines.append(f"- rsd_mode: `{sf_overlay.get('rsd_mode', '')}`")
    lines.append(f"- ap_correction_mode: `{sf_overlay.get('ap_correction_mode', '')}`")
    best_cmb = _as_mapping(sf_overlay.get("best_by_cmb"))
    best_joint = _as_mapping(sf_overlay.get("best_by_joint"))
    if best_cmb:
        lines.append(
            "- Best by CMB (eligible): "
            f"`chi2_total={_fmt_float(best_cmb.get('chi2_total'))}` "
            f"`chi2_rsd={_fmt_float(best_cmb.get('chi2_rsd'))}` "
            f"`joint_score={_fmt_float(best_cmb.get('joint_score', best_cmb.get('chi2_total_plus_rsd')))} `"
            f"`sigma8_0_best={_fmt_float(best_cmb.get('sigma8_0_best'))}` "
            f"`params_hash={best_cmb.get('params_hash', '')}`"
        )
    else:
        lines.append("- Best by CMB (eligible): `NONE`")
    if best_joint:
        lines.append(
            "- Best by joint CMB+RSD (eligible): "
            f"`chi2_total={_fmt_float(best_joint.get('chi2_total'))}` "
            f"`chi2_rsd={_fmt_float(best_joint.get('chi2_rsd'))}` "
            f"`joint_score={_fmt_float(best_joint.get('joint_score', best_joint.get('chi2_total_plus_rsd')))} `"
            f"`sigma8_0_best={_fmt_float(best_joint.get('sigma8_0_best'))}` "
            f"`params_hash={best_joint.get('params_hash', '')}`"
        )
    else:
        lines.append("- Best by joint CMB+RSD (eligible): `joint ranking unavailable: missing RSD fields`")
    lines.append("")
    lines.append(str(sf_overlay.get("disclaimer", SF_RSD_DISCLAIMER)))
    return "\n".join(lines)


def _render_sf_rsd_summary_tex(payload: Mapping[str, Any]) -> str:
    sf_overlay = _as_mapping(payload.get("sf_rsd_overlay"))
    lines: List[str] = [f"% {SF_RSD_SNIPPET_MARKER}", "\\paragraph{Structure formation diagnostics (RSD $f\\sigma_8$)}"]
    if not sf_overlay:
        lines.append("RSD overlay unavailable for this report run.")
        return "\n".join(lines)

    lines.append(
        "Dataset: \\texttt{"
        + _tex_escape(str(sf_overlay.get("data_path", "")))
        + "} (N="
        + str(int(sf_overlay.get("n_points", 0)))
        + ")."
    )
    best_cmb = _as_mapping(sf_overlay.get("best_by_cmb"))
    best_joint = _as_mapping(sf_overlay.get("best_by_joint"))
    if best_cmb:
        lines.append(
            "Best by CMB (eligible): $\\chi^2_\\mathrm{total}="
            + _tex_escape(_fmt_float(best_cmb.get("chi2_total")))
            + "$, $\\chi^2_\\mathrm{RSD}="
            + _tex_escape(_fmt_float(best_cmb.get("chi2_rsd")))
            + "$, $\\chi^2_\\mathrm{joint}="
            + _tex_escape(_fmt_float(best_cmb.get("joint_score", best_cmb.get("chi2_total_plus_rsd"))))
            + "$, $\\sigma_{8,0}="
            + _tex_escape(_fmt_float(best_cmb.get("sigma8_0_best")))
            + "$."
        )
    else:
        lines.append("Best by CMB (eligible): unavailable.")
    if best_joint:
        lines.append(
            "Best by joint CMB+RSD (eligible): $\\chi^2_\\mathrm{total}="
            + _tex_escape(_fmt_float(best_joint.get("chi2_total")))
            + "$, $\\chi^2_\\mathrm{RSD}="
            + _tex_escape(_fmt_float(best_joint.get("chi2_rsd")))
            + "$, $\\chi^2_\\mathrm{joint}="
            + _tex_escape(_fmt_float(best_joint.get("joint_score", best_joint.get("chi2_total_plus_rsd"))))
            + "$, $\\sigma_{8,0}="
            + _tex_escape(_fmt_float(best_joint.get("sigma8_0_best")))
            + "$."
        )
    else:
        lines.append("Best by joint CMB+RSD (eligible): joint ranking unavailable (missing RSD fields).")
    lines.append(_tex_escape(str(sf_overlay.get("disclaimer", SF_RSD_DISCLAIMER))))
    return "\n".join(lines)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip("\n") + "\n", encoding="utf-8")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="phase2_e2_best_candidates_report",
        description="Deterministic stdlib top-candidates report for Phase-2 E2 JSONL inputs.",
    )
    ap.add_argument(
        "--input",
        action="append",
        default=[],
        help="Input path (JSONL file, directory with *.jsonl, or bundle archive). Repeatable.",
    )
    ap.add_argument("--status-filter", choices=["ok_only", "any_eligible"], default="ok_only")
    ap.add_argument("--plausibility", choices=["any", "plausible_only"], default="any")
    ap.add_argument("--rank-by", choices=["cmb", "rsd", "joint"], default="cmb")
    ap.add_argument(
        "--rsd-chi2-field",
        type=str,
        default=None,
        help="Optional explicit RSD chi2 field name; auto-detected when omitted.",
    )
    ap.add_argument("--format", choices=["text", "json", "tex", "md"], default="text")
    ap.add_argument("--top-n", type=int, default=10)
    ap.add_argument("--tex-out", type=Path, default=None)
    ap.add_argument("--md-out", type=Path, default=None)
    ap.add_argument("--json-out", type=Path, default=None)
    ap.add_argument("--sf-rsd", action="store_true", help="Enable additive RSD fσ8 overlay for top candidates.")
    ap.add_argument(
        "--rsd-data",
        type=Path,
        default=DEFAULT_RSD_DATA_PATH,
        help="RSD fσ8 CSV (default: built-in 22-point dataset).",
    )
    ap.add_argument("--rsd-ap-correction", choices=["off", "on"], default="off")
    ap.add_argument("--rsd-mode", choices=["nuisance_sigma8", "derived_As"], default="nuisance_sigma8")
    ap.add_argument("--sf-snippet-md-out", type=Path, default=None)
    ap.add_argument("--sf-snippet-tex-out", type=Path, default=None)
    ap.add_argument("--title", type=str, default="Phase-2 E2 Best Candidates")
    args = ap.parse_args(argv)

    if int(args.top_n) <= 0:
        raise ValueError("--top-n must be > 0")
    if not args.input:
        raise ValueError("At least one --input path is required")
    if (args.sf_snippet_md_out is not None or args.sf_snippet_tex_out is not None) and not bool(args.sf_rsd):
        raise ValueError("--sf-snippet-*-out requires --sf-rsd")

    input_paths = _resolve_inputs([str(x) for x in list(args.input)])
    if not input_paths:
        raise FileNotFoundError("No input paths resolved from --input arguments")

    all_records: List[ParsedRecord] = []
    all_stats: List[InputFileStats] = []
    for path in input_paths:
        recs, stats = _load_records_from_path(path)
        all_records.extend(recs)
        all_stats.extend(stats)

    sf_rsd_cfg: Optional[Dict[str, Any]] = None
    if bool(args.sf_rsd):
        rsd_data_path = Path(args.rsd_data).expanduser().resolve()
        try:
            rsd_rows = load_fsigma8_csv(str(rsd_data_path))
        except ValueError as exc:
            raise ValueError(f"failed to load --rsd-data: {exc}") from exc
        sf_rsd_cfg = {
            "rows": rsd_rows,
            "mode": str(args.rsd_mode),
            "ap_correction": str(args.rsd_ap_correction),
            "data_path": str(rsd_data_path),
        }

    payload = _build_payload(
        records=all_records,
        input_paths_raw=[str(x) for x in list(args.input)],
        input_stats=all_stats,
        status_filter=str(args.status_filter),
        plausibility=str(args.plausibility),
        top_n=int(args.top_n),
        rank_by=str(args.rank_by),
        rsd_chi2_field=(str(args.rsd_chi2_field).strip() if args.rsd_chi2_field else None),
        sf_rsd=sf_rsd_cfg,
    )

    md_text = _render_md(payload, title=str(args.title))
    tex_text = _render_tex(payload, title=str(args.title))
    json_text = json.dumps(payload, sort_keys=True)
    text_out = _render_text(payload)
    sf_md_text = _render_sf_rsd_summary_md(payload)
    sf_tex_text = _render_sf_rsd_summary_tex(payload)

    if args.md_out is not None:
        _write_text(args.md_out.expanduser().resolve(), md_text)
    if args.tex_out is not None:
        _write_text(args.tex_out.expanduser().resolve(), tex_text)
    if args.json_out is not None:
        _write_json(args.json_out.expanduser().resolve(), payload)
    if args.sf_snippet_md_out is not None:
        _write_text(args.sf_snippet_md_out.expanduser().resolve(), sf_md_text)
    if args.sf_snippet_tex_out is not None:
        _write_text(args.sf_snippet_tex_out.expanduser().resolve(), sf_tex_text)

    if str(args.format) == "json":
        print(json_text)
    elif str(args.format) == "md":
        print(md_text)
    elif str(args.format) == "tex":
        print(tex_text)
    else:
        print(text_out)
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        return run(argv)
    except RankingUnavailableError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

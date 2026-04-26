"""RSD f*sigma8 overlay helper for E2 records (stdlib-only, deterministic).

This helper centralizes the additive structure-growth diagnostic used by
Phase-2 E2 reporting tools. It is approximation-first and claim-safe:
linear GR growth over an explicit background history, with optional
AP-like correction and analytic nuisance-amplitude profiling.
"""

from __future__ import annotations

from functools import lru_cache
import hashlib
import math
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from gsc.measurement_model import D_A_flat, FlatLambdaCDMHistory, GSCTransitionHistory, H0_to_SI
from gsc.structure.growth_factor import growth_observables_from_solution, solve_growth_ln_a
from gsc.structure.power_spectrum_linear import sigma8_0_from_As
from gsc.structure.rsd_fsigma8_data import chi2_diag, load_fsigma8_csv, profile_scale_chi2_diag


AP_DA_TRAPZ_N = 4000
_ERROR_LIMIT = 120


def _finite_float(value: Any) -> float | None:
    try:
        out = float(value)
    except Exception:
        return None
    if not math.isfinite(out):
        return None
    return float(out)


def _truncate_error(message: str) -> str:
    text = str(message).strip()
    if len(text) <= _ERROR_LIMIT:
        return text
    return text[: _ERROR_LIMIT - 3] + "..."


def _normalize_status(record: Mapping[str, Any]) -> str:
    raw = record.get("status")
    if raw is None:
        return "unknown"
    text = str(raw).strip().lower()
    return text if text else "unknown"


def _status_allowed(status: str, *, status_filter: str) -> bool:
    label = str(status).strip().lower()
    if str(status_filter) == "ok_only":
        return label == "ok"
    if str(status_filter) != "any_eligible":
        return False
    if label == "ok" or label == "ok_legacy":
        return True
    if label.startswith("error") or label.startswith("skipped"):
        return False
    return label not in {"unknown", ""}


def _canonical_transfer_model(name: str | None) -> str:
    raw = str(name).strip().lower() if name is not None else "bbks"
    if raw in {"bbks"}:
        return "bbks"
    if raw in {"eh98", "eh98_nowiggle"}:
        return "eh98_nowiggle"
    raise ValueError("unsupported transfer model; expected one of: bbks, eh98_nowiggle")


def _pick_param_float(sources: Sequence[Mapping[str, Any]], *names: str) -> float | None:
    targets = {str(name).strip().lower() for name in names if str(name).strip()}
    if not targets:
        return None
    for source in sources:
        for key in source.keys():
            if str(key).strip().lower() not in targets:
                continue
            value = _finite_float(source.get(key))
            if value is not None:
                return float(value)
    return None


def _extract_background_params(record: Mapping[str, Any]) -> Dict[str, float | None]:
    raw = dict(record)
    params = raw.get("params")
    params_map = params if isinstance(params, Mapping) else {}
    bestfit = raw.get("bestfit_params")
    bestfit_map = bestfit if isinstance(bestfit, Mapping) else {}
    sources: List[Mapping[str, Any]] = [raw, params_map, bestfit_map]

    h0 = _pick_param_float(sources, "H0", "h0", "h0_km_s_mpc", "hubble0")
    little_h = _pick_param_float(sources, "h", "little_h")
    if h0 is None and little_h is not None:
        h0 = 100.0 * float(little_h)

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
    k_pivot_mpc = _pick_param_float(
        sources,
        "k_pivot_mpc",
        "k_pivot",
        "k0_mpc",
        "k0",
    )
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
        "k_pivot_mpc": k_pivot_mpc,
    }


def _build_history(record: Mapping[str, Any]) -> Tuple[Any, float, float, Dict[str, float | None]]:
    params = _extract_background_params(record)
    h0_km = params.get("H0_km_s_Mpc")
    omega_m0 = params.get("Omega_m0")
    if h0_km is None or omega_m0 is None:
        raise ValueError("missing_cosmo:H0_or_Omega_m")

    h0_km_val = float(h0_km)
    omega_m0_val = float(omega_m0)
    if not (h0_km_val > 0.0 and omega_m0_val > 0.0):
        raise ValueError("invalid_cosmo:H0_or_Omega_m_non_positive")

    omega_lambda0 = params.get("Omega_lambda0")
    omega_lambda0_val = float(1.0 - omega_m0_val) if omega_lambda0 is None else float(omega_lambda0)
    if not (math.isfinite(omega_lambda0_val) and omega_lambda0_val >= 0.0):
        raise ValueError("invalid_cosmo:Omega_lambda")

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
        return history, h0_si, omega_m0_val, params

    history = FlatLambdaCDMHistory(H0=h0_si, Omega_m=omega_m0_val, Omega_Lambda=omega_lambda0_val)
    return history, h0_si, omega_m0_val, params


def _compute_ap_factor(
    *,
    z: float,
    omega_m_ref: float,
    ap_correction: bool,
    history: Any,
    h0_si: float,
    model_da_cache: Dict[float, float],
    ref_hd_cache: Dict[Tuple[float, float], Tuple[float, float]],
) -> float:
    if not bool(ap_correction):
        return 1.0

    z_key = float(z)
    om_key = float(omega_m_ref)
    if z_key not in model_da_cache:
        h_model = float(history.H(z_key))
        da_model = float(D_A_flat(z=z_key, H_of_z=history.H, n=AP_DA_TRAPZ_N))
        if not (math.isfinite(h_model) and h_model > 0.0 and math.isfinite(da_model) and da_model > 0.0):
            raise ValueError("invalid model H(z) or D_A(z)")
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
            raise ValueError("invalid reference H(z) or D_A(z)")
        ref_hd_cache[ref_key] = (h_ref, da_ref)

    h_model = float(history.H(z_key))
    da_model = float(model_da_cache[z_key])
    h_ref, da_ref = ref_hd_cache[ref_key]
    return float((h_ref * da_ref) / (h_model * da_model))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@lru_cache(maxsize=8)
def _load_rsd_dataset_cached(path_text: str) -> Tuple[Tuple[Tuple[float, float, float, float], ...], str]:
    path = Path(path_text).expanduser().resolve()
    rows = load_fsigma8_csv(str(path))
    tuples = tuple(
        (
            float(row.get("z")),
            float(row.get("fsigma8")),
            float(row.get("sigma")),
            float(row.get("omega_m_ref")),
        )
        for row in rows
    )
    return tuples, _sha256_file(path)


def rsd_overlay_for_e2_record(
    record: Mapping[str, Any],
    *,
    rsd_csv_path: str,
    ap_correction: bool,
    status_filter: str,
    rsd_mode: str = "nuisance_sigma8",
    transfer_model: str | None = None,
    primordial_ns: float | None = None,
    primordial_k_pivot_mpc: float | None = None,
) -> Dict[str, Any]:
    """Compute additive RSD overlay metrics for one E2 record.

    Returned fields:
      - rsd_overlay_status
      - chi2_rsd_min
      - rsd_sigma8_0_best
      - rsd_n
      - rsd_data_sha256
      - rsd_ap_correction
      - optional rsd_error
    """
    status = _normalize_status(record)
    out: Dict[str, Any] = {
        "rsd_overlay_status": "ok",
        "chi2_rsd_min": None,
        "rsd_sigma8_0_best": None,
        "rsd_n": 0,
        "rsd_data_sha256": None,
        "rsd_ap_correction": bool(ap_correction),
        "rsd_transfer_model": None,
        "rsd_primordial_ns": None,
        "rsd_primordial_k_pivot_mpc": None,
    }

    if not _status_allowed(status, status_filter=str(status_filter)):
        out["rsd_overlay_status"] = "skipped_ineligible"
        return out

    path = Path(str(rsd_csv_path)).expanduser().resolve()
    try:
        rsd_rows, data_sha256 = _load_rsd_dataset_cached(str(path))
    except Exception as exc:
        out["rsd_overlay_status"] = "skipped_missing_data"
        out["rsd_error"] = _truncate_error(str(exc))
        return out

    out["rsd_data_sha256"] = str(data_sha256)
    out["rsd_n"] = int(len(rsd_rows))
    if not rsd_rows:
        out["rsd_overlay_status"] = "error"
        out["rsd_error"] = "empty_rsd_dataset"
        return out

    try:
        history, h0_si, omega_m0, params = _build_history(record)
    except Exception as exc:
        out["rsd_overlay_status"] = "skipped_missing_cosmo"
        out["rsd_error"] = _truncate_error(str(exc))
        return out

    z_targets = sorted({float(row[0]) for row in rsd_rows})
    z_start = max(100.0, max(z_targets) + 5.0)

    def E_of_z(z: float) -> float:
        hz = float(history.H(float(z)))
        if not (math.isfinite(hz) and hz > 0.0):
            raise ValueError("non-positive_or_non-finite_H")
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
        out["rsd_overlay_status"] = "error"
        out["rsd_error"] = _truncate_error(f"growth_solver_failed:{exc}")
        return out

    obs_by_z: Dict[float, Dict[str, float]] = {}
    for i, z in enumerate(obs.get("z", [])):
        obs_by_z[float(z)] = {"g": float(obs["g"][i])}

    model_da_cache: Dict[float, float] = {}
    ref_hd_cache: Dict[Tuple[float, float], Tuple[float, float]] = {}
    data_y: List[float] = []
    sigmas: List[float] = []
    model_t: List[float] = []
    try:
        for z, y, sigma, omega_m_ref in rsd_rows:
            obs_row = obs_by_z.get(float(z))
            if obs_row is None:
                raise ValueError("missing_growth_grid_point")
            ap_factor = _compute_ap_factor(
                z=float(z),
                omega_m_ref=float(omega_m_ref),
                ap_correction=bool(ap_correction),
                history=history,
                h0_si=float(h0_si),
                model_da_cache=model_da_cache,
                ref_hd_cache=ref_hd_cache,
            )
            t_val = float(obs_row["g"] * ap_factor)
            if not (math.isfinite(y) and math.isfinite(sigma) and sigma > 0.0 and math.isfinite(t_val)):
                raise ValueError("non-finite_row_payload")
            data_y.append(float(y))
            sigmas.append(float(sigma))
            model_t.append(float(t_val))
    except Exception as exc:
        out["rsd_overlay_status"] = "error"
        out["rsd_error"] = _truncate_error(f"row_processing_failed:{exc}")
        return out

    mode = str(rsd_mode).strip().lower()
    if mode == "derived_as":
        try:
            transfer = _canonical_transfer_model(transfer_model)
        except Exception as exc:
            out["rsd_overlay_status"] = "error"
            out["rsd_error"] = _truncate_error(f"derived_As_failed:{exc}")
            return out
        As = params.get("As")
        ns = _finite_float(primordial_ns) if primordial_ns is not None else params.get("ns")
        little_h = params.get("h")
        omega_b0 = params.get("Omega_b0")
        k_pivot = (
            _finite_float(primordial_k_pivot_mpc)
            if primordial_k_pivot_mpc is not None
            else params.get("k_pivot_mpc")
        )
        if k_pivot is None:
            k_pivot = 0.05
        if ns is None:
            ns = 1.0
        if As is None or little_h is None:
            out["rsd_overlay_status"] = "skipped_missing_cosmo"
            out["rsd_error"] = "missing_cosmo:As_h"
            return out
        if omega_b0 is None:
            omega_b0 = 0.049
        out["rsd_transfer_model"] = str(transfer)
        out["rsd_primordial_ns"] = float(ns)
        out["rsd_primordial_k_pivot_mpc"] = float(k_pivot)
        try:
            sigma8_0 = sigma8_0_from_As(
                As=float(As),
                ns=float(ns),
                omega_m0=float(omega_m0),
                h=float(little_h),
                transfer_model=str(transfer),
                omega_b0=float(omega_b0),
                Tcmb_K=2.7255,
                k_pivot_mpc=float(k_pivot),
                E_of_z=E_of_z,
                z_start=float(z_start),
                n_steps=4000,
                eps_dlnH=1.0e-5,
            )
            preds = [float(float(sigma8_0) * t) for t in model_t]
            residuals = [float(y - p) for y, p in zip(data_y, preds)]
            chi2 = chi2_diag(residuals, sigmas)
            out["chi2_rsd_min"] = float(chi2)
            out["rsd_sigma8_0_best"] = float(sigma8_0)
            out["rsd_overlay_status"] = "ok"
            return out
        except Exception as exc:
            out["rsd_overlay_status"] = "error"
            out["rsd_error"] = _truncate_error(f"derived_As_failed:{exc}")
            return out

    try:
        prof = profile_scale_chi2_diag(data_y, model_t, sigmas)
        scale = prof.get("scale_bestfit")
        chi2_min = prof.get("chi2_min")
        if scale is None or chi2_min is None:
            raise ValueError("profiling_denominator_non_positive")
        out["chi2_rsd_min"] = float(chi2_min)
        out["rsd_sigma8_0_best"] = float(scale)
        out["rsd_overlay_status"] = "ok"
        return out
    except Exception as exc:
        out["rsd_overlay_status"] = "error"
        out["rsd_error"] = _truncate_error(f"nuisance_sigma8_failed:{exc}")
        return out


__all__ = ["rsd_overlay_for_e2_record"]

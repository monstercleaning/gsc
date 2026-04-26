#!/usr/bin/env python3
"""Phase-3 low-z joint diagnostics report (BAO + SN + RSD).

Scope:
- deterministic diagnostic chi2 summary
- analytic nuisance profiling (r_d, delta_M, sigma8_0)
- claim-safe: not a full global likelihood fit
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gsc.datasets.bao import (  # noqa: E402
    BAOBlock1D,
    BAOBlock2D,
    BAOBlockND,
    BAODataset,
    D_H,
    D_V_flat,
)
from gsc.datasets.cmb_priors import CMBPriorsDataset  # noqa: E402
from gsc.datasets.sn import SNDataset  # noqa: E402
from gsc.early_time import compute_bridged_distance_priors  # noqa: E402
from gsc.measurement_model import (  # noqa: E402
    D_A_flat,
    D_M_flat,
    FlatLambdaCDMHistory,
    H0_to_SI,
)
from gsc.structure.growth_factor import (  # noqa: E402
    growth_observables_from_solution,
    solve_growth_ln_a,
)
from gsc.structure.power_spectrum_linear import sigma8_0_from_As  # noqa: E402
from gsc.structure.rsd_fsigma8_data import (  # noqa: E402
    chi2_diag,
    load_fsigma8_csv,
    profile_scale_chi2_diag,
)
from gsc.theory.sigmatensor_v1 import (  # noqa: E402
    SigmaTensorV1History,
    SigmaTensorV1Params,
    solve_sigmatensor_v1_background,
)


TOOL_NAME = "phase3_joint_sigmatensor_lowz_report"
SCHEMA_NAME = "phase3_sigmatensor_lowz_joint_report_v1"
FAIL_MARKER = "PHASE3_LOWZ_JOINT_FAILED"
DEFAULT_CREATED_UTC = "2000-01-01T00:00:00Z"
DEFAULT_BAO_DATA = ROOT / "data" / "bao" / "bao_6df_mgs_boss_dr12_cov6_plus_lya_qso.csv"
DEFAULT_SN_DATA = ROOT / "data" / "sn" / "pantheon_plus_shoes" / "pantheon_plus_shoes_mu.csv"
DEFAULT_RSD_DATA = ROOT / "data" / "structure" / "fsigma8_gold2017_plus_zhao2018.csv"
DEFAULT_CMB_PRIORS_DATA = (
    ROOT
    / "data"
    / "cmb"
    / "planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv"
)
DEFAULT_CMB_COV_DATA = (
    ROOT
    / "data"
    / "cmb"
    / "planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov"
)
AP_DA_TRAPZ_N = 4000
_CREATED_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_OMEGA_CDM_NEG_TOL = 1.0e-12


class UsageError(Exception):
    """Usage/IO/configuration error (exit 1)."""


class GateError(Exception):
    """Physics/data/numpy gate error (exit 2)."""


def _finite_float(value: Any, *, name: str) -> float:
    try:
        out = float(value)
    except Exception as exc:
        raise UsageError(f"{name} must be a finite float") from exc
    if not math.isfinite(out):
        raise UsageError(f"{name} must be a finite float")
    return float(out)


def _finite_positive(value: Any, *, name: str) -> float:
    out = _finite_float(value, name=name)
    if out <= 0.0:
        raise UsageError(f"{name} must be > 0")
    return float(out)


def _normalize_created_utc(value: str) -> str:
    text = str(value or "").strip()
    if not _CREATED_UTC_RE.match(text):
        raise UsageError("--created-utc must match YYYY-MM-DDTHH:MM:SSZ")
    try:
        parsed = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise UsageError("--created-utc must match YYYY-MM-DDTHH:MM:SSZ") from exc
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def _json_text(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _fmt_num(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        out = float(value)
    except Exception:
        return "n/a"
    if not math.isfinite(out):
        return "n/a"
    return f"{out:.12g}"


def _canonical_transfer_model(name: str) -> str:
    raw = str(name).strip().lower()
    if raw == "bbks":
        return "bbks"
    if raw in {"eh98", "eh98_nowiggle"}:
        return "eh98_nowiggle"
    raise UsageError("unsupported transfer model; expected one of: bbks, eh98_nowiggle")


def _resolve_omega_cdm_h2(
    *,
    H0_km_s_Mpc: float,
    omega_m0: float,
    omega_b_h2: float,
    omega_cdm_h2_input: Optional[float],
) -> Tuple[float, bool]:
    if omega_cdm_h2_input is not None:
        val = _finite_float(omega_cdm_h2_input, name="--omega-cdm-h2")
        if val < -_OMEGA_CDM_NEG_TOL:
            raise GateError("--omega-cdm-h2 must be >= 0")
        return max(0.0, float(val)), False

    h = float(H0_km_s_Mpc) / 100.0
    omega_m_h2 = float(omega_m0) * h * h
    derived = float(omega_m_h2 - float(omega_b_h2))
    if derived < -_OMEGA_CDM_NEG_TOL:
        raise GateError(
            "derived omega_cdm_h2 is negative; check --Omega-m and --omega-b-h2 consistency"
        )
    return max(0.0, derived), True


def _bao_max_z(dataset: BAODataset) -> float:
    values: List[float] = []
    for block in dataset.blocks:
        if isinstance(block, BAOBlock1D):
            values.append(float(block.z))
        elif isinstance(block, BAOBlock2D):
            values.append(float(block.z))
        elif isinstance(block, BAOBlockND):
            for z in block.zs:
                values.append(float(z))
    return max(values) if values else 0.0


def _needed_bg_zmax(*, z_start: float, eps_dlnH: float) -> float:
    return float(z_start + (1.0 + z_start) * (3.0 * eps_dlnH) + 1.0e-3)


def _resolve_bg_zmax(
    *,
    z_max_bg_arg: Optional[float],
    max_data_z: float,
    z_start: float,
    eps_dlnH: float,
) -> Tuple[Optional[float], float]:
    needed_growth = _needed_bg_zmax(z_start=float(z_start), eps_dlnH=float(eps_dlnH))
    min_needed = max(float(max_data_z) + 1.0e-6, float(needed_growth))
    if z_max_bg_arg is None:
        return None, float(min_needed)
    requested = float(z_max_bg_arg)
    if requested <= 0.0:
        raise UsageError("--z-max-bg must be > 0 when provided")
    return float(requested), float(max(requested, min_needed))


def _ap_factor(
    *,
    z: float,
    omega_m_ref: float,
    ap_correction: bool,
    history: SigmaTensorV1History,
    H0_si: float,
    model_da_cache: Dict[float, float],
    ref_hd_cache: Dict[Tuple[float, float], Tuple[float, float]],
) -> float:
    if not ap_correction:
        return 1.0

    z_key = float(z)
    om_key = float(omega_m_ref)

    if z_key not in model_da_cache:
        h_model = float(history.H(z_key))
        da_model = float(D_A_flat(z=z_key, H_of_z=history.H, n=AP_DA_TRAPZ_N))
        if not (math.isfinite(h_model) and h_model > 0.0 and math.isfinite(da_model) and da_model > 0.0):
            raise GateError("invalid model H(z) or D_A(z) for AP correction")
        model_da_cache[z_key] = float(da_model)

    ref_key = (z_key, om_key)
    if ref_key not in ref_hd_cache:
        ref_history = FlatLambdaCDMHistory(
            H0=float(H0_si),
            Omega_m=float(om_key),
            Omega_Lambda=float(max(0.0, 1.0 - om_key)),
        )
        h_ref = float(ref_history.H(z_key))
        da_ref = float(D_A_flat(z=z_key, H_of_z=ref_history.H, n=AP_DA_TRAPZ_N))
        if not (math.isfinite(h_ref) and h_ref > 0.0 and math.isfinite(da_ref) and da_ref > 0.0):
            raise GateError("invalid reference H(z) or D_A(z) for AP correction")
        ref_hd_cache[ref_key] = (float(h_ref), float(da_ref))

    h_model = float(history.H(z_key))
    da_model = float(model_da_cache[z_key])
    h_ref, da_ref = ref_hd_cache[ref_key]
    return float((h_ref * da_ref) / (h_model * da_model))


def _stable_bao_chi2_at_rd(*, dataset: BAODataset, history: SigmaTensorV1History, rd_m: float, n: int) -> float:
    if not (math.isfinite(float(rd_m)) and float(rd_m) > 0.0):
        raise GateError("invalid rd_m for BAO residual chi2")
    inv_rd = 1.0 / float(rd_m)
    total = 0.0
    for block in dataset.blocks:
        if isinstance(block, BAOBlock1D):
            pred = float(D_V_flat(z=float(block.z), model=history, n=int(n)) * inv_rd)
            res = (pred - float(block.y)) / float(block.sigma)
            total += float(res * res)
            continue
        if isinstance(block, BAOBlock2D):
            dm = float(D_M_flat(z=float(block.z), H_of_z=history.H, n=int(n)) * inv_rd)
            dh = float(D_H(z=float(block.z), model=history) * inv_rd)
            r_dm = dm - float(block.y_dm)
            r_dh = dh - float(block.y_dh)
            a = float(block.sigma_dm * block.sigma_dm)
            c = float(block.sigma_dh * block.sigma_dh)
            b = float(block.rho_dm_dh * block.sigma_dm * block.sigma_dh)
            det = a * c - b * b
            if not (det > 0.0 and math.isfinite(det)):
                raise GateError("invalid BAO 2D covariance (det<=0)")
            inv00 = c / det
            inv01 = -b / det
            inv11 = a / det
            total += float(r_dm * (inv00 * r_dm + inv01 * r_dh) + r_dh * (inv01 * r_dm + inv11 * r_dh))
            continue

        # BAOBlockND path (requires numpy, same as dataset loader semantics)
        try:
            import numpy as np  # type: ignore
        except Exception as exc:
            raise GateError(
                "numpy is required for BAO covariance blocks (VECTOR_over_rd)."
            ) from exc

        d_list: List[float] = []
        for kind, z in zip(block.kinds, block.zs):
            kk = str(kind).strip().upper()
            zz = float(z)
            if kk == "DV":
                d_list.append(float(D_V_flat(z=zz, model=history, n=int(n)) * inv_rd))
            elif kk == "DM":
                d_list.append(float(D_M_flat(z=zz, H_of_z=history.H, n=int(n)) * inv_rd))
            elif kk == "DH":
                d_list.append(float(D_H(z=zz, model=history) * inv_rd))
            else:
                raise GateError(f"unknown BAO kind in VECTOR_over_rd: {kind!r}")
        d_vec = np.asarray(d_list, dtype=float)
        y_vec = np.asarray(block.y, dtype=float)
        cov = block.cov if hasattr(block.cov, "shape") else np.asarray(block.cov, dtype=float)
        L = np.linalg.cholesky(cov)
        r = d_vec - y_vec
        t = np.linalg.solve(L, r)
        x = np.linalg.solve(L.T, t)
        total += float(np.dot(r, x))
    if not math.isfinite(total):
        raise GateError("non-finite BAO residual chi2")
    return float(total)


def _evaluate_rsd(
    *,
    history: SigmaTensorV1History,
    H0_si: float,
    omega_m0: float,
    rows: Sequence[Mapping[str, Any]],
    ap_correction: bool,
    sigma8_mode: str,
    sigma8_fixed: Optional[float],
    As: Optional[float],
    ns: float,
    transfer_model: str,
    omega_b0: float,
    k0_mpc: float,
    kmin: float,
    kmax: float,
    nk: int,
    z_start: float,
    n_steps_growth: int,
    eps_dlnH: float,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    if not rows:
        raise GateError("RSD dataset has no usable points")

    z_targets = sorted({float(row["z"]) for row in rows})
    if max(z_targets) >= float(z_start):
        raise GateError("--z-start must be strictly greater than RSD z values")

    def e_of_z_growth(z: float) -> float:
        zz = float(z)
        if zz < 0.0:
            zz = 0.0
        return float(history.E(zz))

    try:
        solution = solve_growth_ln_a(
            e_of_z_growth,
            float(omega_m0),
            z_start=float(z_start),
            z_targets=z_targets,
            n_steps=int(n_steps_growth),
            eps_dlnH=float(eps_dlnH),
        )
        obs = growth_observables_from_solution(solution, z_targets)
    except ValueError as exc:
        raise GateError(str(exc)) from exc

    obs_by_z: Dict[float, Dict[str, float]] = {}
    for i, z in enumerate(obs["z"]):
        obs_by_z[float(z)] = {
            "D": float(obs["D"][i]),
            "f": float(obs["f"][i]),
            "g": float(obs["g"][i]),
        }

    model_da_cache: Dict[float, float] = {}
    ref_hd_cache: Dict[Tuple[float, float], Tuple[float, float]] = {}
    data_y: List[float] = []
    sigmas: List[float] = []
    template_t: List[float] = []
    template_rows: List[Dict[str, float]] = []
    for row in rows:
        z = float(row["z"])
        y = float(row["fsigma8"])
        sigma = float(row["sigma"])
        om_ref = float(row["omega_m_ref"])
        g = float(obs_by_z[z]["g"])
        ap = _ap_factor(
            z=z,
            omega_m_ref=om_ref,
            ap_correction=bool(ap_correction),
            history=history,
            H0_si=float(H0_si),
            model_da_cache=model_da_cache,
            ref_hd_cache=ref_hd_cache,
        )
        t = float(g * ap)
        data_y.append(float(y))
        sigmas.append(float(sigma))
        template_t.append(float(t))
        template_rows.append({"z": float(z), "g": float(g), "ap_factor": float(ap), "shape_t": float(t)})

    sigma8_info: Dict[str, Any] = {"sigma8_mode": str(sigma8_mode)}
    if sigma8_mode == "nuisance":
        try:
            prof = profile_scale_chi2_diag(data_y, template_t, sigmas)
        except ValueError as exc:
            raise GateError(str(exc)) from exc
        scale = prof.get("scale_bestfit")
        chi2 = prof.get("chi2_min")
        if scale is None or chi2 is None:
            raise GateError("RSD nuisance profiling failed (non-positive denominator)")
        sigma8_used = float(scale)
        ndof = int(len(rows) - 1)
        sigma8_info["sigma8_0_bestfit"] = float(scale)
    elif sigma8_mode == "derived_As":
        if As is None:
            raise UsageError("--sigma8-mode derived_As requires --As")
        try:
            sigma8_used = sigma8_0_from_As(
                As=float(As),
                ns=float(ns),
                omega_m0=float(omega_m0),
                h=float(H0_si * 3.085677581e22 / 1000.0 / 100.0),
                transfer_model=str(transfer_model),
                omega_b0=float(omega_b0),
                k0_mpc=float(k0_mpc),
                kmin=float(kmin),
                kmax=float(kmax),
                nk=int(nk),
                E_of_z=e_of_z_growth,
                z_start=float(z_start),
                n_steps=int(n_steps_growth),
                eps_dlnH=float(eps_dlnH),
            )
        except ValueError as exc:
            raise GateError(str(exc)) from exc
        preds = [float(sigma8_used * t) for t in template_t]
        residuals = [float(y - p) for y, p in zip(data_y, preds)]
        try:
            chi2 = chi2_diag(residuals, sigmas)
        except ValueError as exc:
            raise GateError(str(exc)) from exc
        ndof = int(len(rows))
        sigma8_info["sigma8_0_used"] = float(sigma8_used)
    else:
        if sigma8_fixed is None:
            raise UsageError("--sigma8-mode fixed requires --sigma8-0")
        sigma8_used = float(sigma8_fixed)
        preds = [float(sigma8_used * t) for t in template_t]
        residuals = [float(y - p) for y, p in zip(data_y, preds)]
        try:
            chi2 = chi2_diag(residuals, sigmas)
        except ValueError as exc:
            raise GateError(str(exc)) from exc
        ndof = int(len(rows))
        sigma8_info["sigma8_0_used"] = float(sigma8_used)

    if sigma8_mode == "nuisance":
        preds = [float(sigma8_used * t) for t in template_t]
        residuals = [float(y - p) for y, p in zip(data_y, preds)]
        chi2 = float(chi2)

    residual_dump: List[Dict[str, float]] = []
    for row, y, pred, sigma in zip(template_rows, data_y, preds, sigmas):
        residual = float(y - pred)
        pull = float(residual / sigma)
        residual_dump.append({"z": float(row["z"]), "residual": residual, "pull": pull})

    residual_lines = "".join(
        f"{r['z']:.12e},{r['residual']:.12e},{r['pull']:.12e}\n" for r in residual_dump
    )
    rsd_block = {
        "enabled": True,
        "ap_correction": bool(ap_correction),
        "sigma8_mode": str(sigma8_mode),
        "chi2": float(chi2),
        "ndof": int(ndof),
        "residuals_digest_sha256": _sha256_text(residual_lines),
    }
    rsd_block.update(sigma8_info)
    return rsd_block, sigma8_info


def _evaluate_cmb(
    *,
    history: SigmaTensorV1History,
    cmb_dataset: CMBPriorsDataset,
    cmb_priors_basename: str,
    cmb_priors_sha256: str,
    cmb_cov_basename: str,
    cmb_cov_sha256: str,
    cmb_z_bridge: float,
    omega_b_h2: float,
    omega_c_h2: float,
    N_eff: float,
    Tcmb_K: float,
    cmb_integrator: str,
    cmb_eps_abs: float,
    cmb_eps_rel: float,
    cmb_rs_star_calibration: float,
    cmb_dm_star_calibration: float,
) -> Dict[str, Any]:
    def _finite_or_none(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            out = float(value)
        except Exception:
            return None
        if not math.isfinite(out):
            return None
        return float(out)

    try:
        pred_full = compute_bridged_distance_priors(
            model=history,
            z_bridge=float(cmb_z_bridge),
            omega_b_h2=float(omega_b_h2),
            omega_c_h2=float(omega_c_h2),
            N_eff=float(N_eff),
            Tcmb_K=float(Tcmb_K),
            rs_star_calibration=float(cmb_rs_star_calibration),
            dm_star_calibration=float(cmb_dm_star_calibration),
            integrator=str(cmb_integrator),
            integration_eps_abs=float(cmb_eps_abs),
            integration_eps_rel=float(cmb_eps_rel),
        )
    except ValueError as exc:
        raise GateError(str(exc)) from exc

    predicted: Dict[str, float] = {}
    missing: List[str] = []
    for key in cmb_dataset.keys:
        if key not in pred_full:
            missing.append(str(key))
            continue
        val = float(pred_full[key])
        if not math.isfinite(val):
            raise GateError(f"non-finite CMB predicted value for key: {key}")
        predicted[str(key)] = float(val)
    if missing:
        raise GateError(f"missing CMB predicted values for keys: {missing}")

    try:
        chi2_res = cmb_dataset.chi2_from_values(predicted)
    except RuntimeError as exc:
        raise GateError(str(exc)) from exc
    except ValueError as exc:
        raise GateError(str(exc)) from exc

    meta = {
        "z_star": _finite_or_none(pred_full.get("z_star")),
        "z_drag": _finite_or_none(pred_full.get("z_drag")),
        "r_s_star_Mpc": _finite_or_none(pred_full.get("r_s_star_Mpc")),
        "D_M_star_Mpc": _finite_or_none(pred_full.get("D_M_star_Mpc")),
        "rd_Mpc": _finite_or_none(pred_full.get("rd_Mpc")),
        "bridge_H_ratio": _finite_or_none(pred_full.get("bridge_H_ratio")),
        "integration_method": str(pred_full.get("integration_method", "")),
        "recombination_method": str(pred_full.get("recombination_method", "")),
        "drag_method": str(pred_full.get("drag_method", "")),
        "dataset_method": str(chi2_res.meta.get("method", "")),
    }
    return {
        "enabled": True,
        "priors_basename": str(cmb_priors_basename),
        "priors_sha256": str(cmb_priors_sha256),
        "cov_basename": str(cmb_cov_basename),
        "cov_sha256": str(cmb_cov_sha256),
        "chi2": float(chi2_res.chi2),
        "ndof": int(chi2_res.ndof),
        "omega_b_h2": float(omega_b_h2),
        "omega_c_h2": float(omega_c_h2),
        "z_bridge": float(cmb_z_bridge),
        "predicted": {k: float(predicted[k]) for k in sorted(predicted.keys())},
        "meta": meta,
    }


def _evaluate_sigma_tensor_model(
    *,
    H0_si: float,
    omega_m0: float,
    w0: float,
    lambda_: float,
    Tcmb_K: float,
    N_eff: float,
    omega_r0_override: Optional[float],
    sign_u0: int,
    z_max_bg_effective: float,
    n_steps_bg: int,
    bao_enabled: bool,
    bao_dataset: Optional[BAODataset],
    bao_data_basename: Optional[str],
    bao_data_sha256: Optional[str],
    bao_n: int,
    sn_enabled: bool,
    sn_dataset: Optional[SNDataset],
    sn_data_basename: Optional[str],
    sn_data_sha256: Optional[str],
    sn_n: int,
    cmb_enabled: bool,
    cmb_dataset: Optional[CMBPriorsDataset],
    cmb_priors_basename: Optional[str],
    cmb_priors_sha256: Optional[str],
    cmb_cov_basename: Optional[str],
    cmb_cov_sha256: Optional[str],
    cmb_z_bridge: float,
    omega_b_h2: float,
    omega_c_h2: float,
    cmb_integrator: str,
    cmb_eps_abs: float,
    cmb_eps_rel: float,
    cmb_rs_star_calibration: float,
    cmb_dm_star_calibration: float,
    rsd_enabled: bool,
    rsd_rows: Sequence[Mapping[str, Any]],
    rsd_data_basename: Optional[str],
    rsd_data_sha256: Optional[str],
    ap_correction: bool,
    sigma8_mode: str,
    sigma8_fixed: Optional[float],
    As: Optional[float],
    ns: float,
    transfer_model: str,
    omega_b0: float,
    k0_mpc: float,
    kmin: float,
    kmax: float,
    nk: int,
    z_start: float,
    n_steps_growth: int,
    eps_dlnH: float,
) -> Dict[str, Any]:
    params = SigmaTensorV1Params(
        H0_si=float(H0_si),
        Omega_m0=float(omega_m0),
        w_phi0=float(w0),
        lambda_=float(lambda_),
        Tcmb_K=float(Tcmb_K),
        N_eff=float(N_eff),
        Omega_r0_override=None if omega_r0_override is None else float(omega_r0_override),
        sign_u0=int(sign_u0),
    )
    try:
        bg = solve_sigmatensor_v1_background(
            params,
            z_max=float(z_max_bg_effective),
            n_steps=int(n_steps_bg),
        )
    except ValueError as exc:
        raise GateError(str(exc)) from exc
    hist = SigmaTensorV1History(bg)

    blocks: Dict[str, Any] = {}
    total_chi2 = 0.0
    total_ndof = 0

    if bao_enabled:
        if bao_dataset is None or bao_data_basename is None or bao_data_sha256 is None:
            raise GateError("BAO block enabled but dataset is unavailable")
        try:
            bao_res = bao_dataset.chi2(hist, fit_rd=True, n=int(bao_n))
        except RuntimeError as exc:
            # numpy gate for VECTOR blocks.
            raise GateError(str(exc)) from exc
        except ValueError as exc:
            raise GateError(str(exc)) from exc
        rd_bestfit = float(bao_res.params.get("rd_m", float("nan")))
        chi2_stable = _stable_bao_chi2_at_rd(
            dataset=bao_dataset,
            history=hist,
            rd_m=rd_bestfit,
            n=int(bao_n),
        )
        bao_block = {
            "enabled": True,
            "data_basename": str(bao_data_basename),
            "data_sha256": str(bao_data_sha256),
            "chi2": float(chi2_stable),
            "ndof": int(bao_res.ndof),
            "rd_m_bestfit": float(rd_bestfit),
            "meta": {
                "method": str(bao_res.meta.get("method", "")),
                "n_obs": int(bao_res.meta.get("n_obs", 0)) if bao_res.meta.get("n_obs") is not None else None,
            },
        }
        blocks["bao"] = bao_block
        total_chi2 += float(chi2_stable)
        total_ndof += int(bao_res.ndof)
    else:
        blocks["bao"] = {
            "enabled": False,
            "data_basename": None,
            "data_sha256": None,
            "chi2": 0.0,
            "ndof": 0,
            "rd_m_bestfit": None,
            "meta": {},
        }

    if sn_enabled:
        if sn_dataset is None or sn_data_basename is None or sn_data_sha256 is None:
            raise GateError("SN block enabled but dataset is unavailable")
        try:
            sn_res = sn_dataset.chi2(hist, fit_delta_M=True, n=int(sn_n))
        except RuntimeError as exc:
            raise GateError(str(exc)) from exc
        except ValueError as exc:
            raise GateError(str(exc)) from exc
        sn_block = {
            "enabled": True,
            "data_basename": str(sn_data_basename),
            "data_sha256": str(sn_data_sha256),
            "chi2": float(sn_res.chi2),
            "ndof": int(sn_res.ndof),
            "delta_M_bestfit": float(sn_res.params.get("delta_M", float("nan"))),
            "meta": {
                "method": str(sn_res.meta.get("method", "")),
            },
        }
        blocks["sn"] = sn_block
        total_chi2 += float(sn_res.chi2)
        total_ndof += int(sn_res.ndof)
    else:
        blocks["sn"] = {
            "enabled": False,
            "data_basename": None,
            "data_sha256": None,
            "chi2": 0.0,
            "ndof": 0,
            "delta_M_bestfit": None,
            "meta": {},
        }

    if cmb_enabled:
        if (
            cmb_dataset is None
            or cmb_priors_basename is None
            or cmb_priors_sha256 is None
            or cmb_cov_basename is None
            or cmb_cov_sha256 is None
        ):
            raise GateError("CMB block enabled but dataset/covariance is unavailable")
        cmb_block = _evaluate_cmb(
            history=hist,
            cmb_dataset=cmb_dataset,
            cmb_priors_basename=str(cmb_priors_basename),
            cmb_priors_sha256=str(cmb_priors_sha256),
            cmb_cov_basename=str(cmb_cov_basename),
            cmb_cov_sha256=str(cmb_cov_sha256),
            cmb_z_bridge=float(cmb_z_bridge),
            omega_b_h2=float(omega_b_h2),
            omega_c_h2=float(omega_c_h2),
            N_eff=float(N_eff),
            Tcmb_K=float(Tcmb_K),
            cmb_integrator=str(cmb_integrator),
            cmb_eps_abs=float(cmb_eps_abs),
            cmb_eps_rel=float(cmb_eps_rel),
            cmb_rs_star_calibration=float(cmb_rs_star_calibration),
            cmb_dm_star_calibration=float(cmb_dm_star_calibration),
        )
        blocks["cmb"] = cmb_block
        total_chi2 += float(cmb_block["chi2"])
        total_ndof += int(cmb_block["ndof"])
    else:
        blocks["cmb"] = {
            "enabled": False,
            "priors_basename": None,
            "priors_sha256": None,
            "cov_basename": None,
            "cov_sha256": None,
            "chi2": 0.0,
            "ndof": 0,
            "omega_b_h2": None,
            "omega_c_h2": None,
            "z_bridge": None,
            "predicted": {},
            "meta": {},
        }

    sigma8_info_for_payload: Dict[str, Any] = {"sigma8_mode": str(sigma8_mode)}
    if rsd_enabled:
        rsd_block, sigma8_info = _evaluate_rsd(
            history=hist,
            H0_si=float(H0_si),
            omega_m0=float(omega_m0),
            rows=rsd_rows,
            ap_correction=bool(ap_correction),
            sigma8_mode=str(sigma8_mode),
            sigma8_fixed=(None if sigma8_fixed is None else float(sigma8_fixed)),
            As=(None if As is None else float(As)),
            ns=float(ns),
            transfer_model=str(transfer_model),
            omega_b0=float(omega_b0),
            k0_mpc=float(k0_mpc),
            kmin=float(kmin),
            kmax=float(kmax),
            nk=int(nk),
            z_start=float(z_start),
            n_steps_growth=int(n_steps_growth),
            eps_dlnH=float(eps_dlnH),
        )
        rsd_block["data_basename"] = str(rsd_data_basename)
        rsd_block["data_sha256"] = str(rsd_data_sha256)
        blocks["rsd"] = rsd_block
        sigma8_info_for_payload.update(sigma8_info)
        total_chi2 += float(rsd_block["chi2"])
        total_ndof += int(rsd_block["ndof"])
    else:
        blocks["rsd"] = {
            "enabled": False,
            "data_basename": None,
            "data_sha256": None,
            "ap_correction": bool(ap_correction),
            "sigma8_mode": str(sigma8_mode),
            "chi2": 0.0,
            "ndof": 0,
            "residuals_digest_sha256": None,
        }

    return {
        "derived_today": {
            "Omega_r0": float(bg.meta["Omega_r0"]),
            "Omega_phi0": float(bg.meta["Omega_phi0"]),
            "u0": float(bg.meta["u0"]),
            "Vhat0": float(bg.meta["Vhat0"]),
            "p_action": float(bg.meta["p_action"]),
        },
        "blocks": blocks,
        "total": {
            "chi2": float(total_chi2),
            "ndof": int(total_ndof),
        },
        "sigma8_info": sigma8_info_for_payload,
    }


def _digest_payload_lines(payload: Mapping[str, Any]) -> str:
    lines: List[str] = []
    total = payload.get("total") if isinstance(payload.get("total"), Mapping) else {}
    lines.append(f"model_total_chi2={float(total.get('chi2', 0.0)):.12e}")
    lines.append(f"model_total_ndof={int(total.get('ndof', 0))}")
    blocks = payload.get("blocks") if isinstance(payload.get("blocks"), Mapping) else {}
    for name in ("bao", "sn", "cmb", "rsd"):
        block = blocks.get(name) if isinstance(blocks.get(name), Mapping) else {}
        lines.append(f"{name}_enabled={int(bool(block.get('enabled')))}")
        lines.append(f"{name}_chi2={float(block.get('chi2', 0.0)):.12e}")
        lines.append(f"{name}_ndof={int(block.get('ndof', 0))}")
        if name == "bao":
            val = block.get("rd_m_bestfit")
            if val is not None:
                lines.append(f"{name}_rd_m_bestfit={float(val):.12e}")
        if name == "sn":
            val = block.get("delta_M_bestfit")
            if val is not None:
                lines.append(f"{name}_delta_M_bestfit={float(val):.12e}")
        if name == "cmb":
            for key in ("omega_b_h2", "omega_c_h2", "z_bridge"):
                val = block.get(key)
                if val is not None:
                    lines.append(f"{name}_{key}={float(val):.12e}")
        if name == "rsd":
            for k in ("sigma8_0_bestfit", "sigma8_0_used"):
                val = block.get(k)
                if val is not None:
                    lines.append(f"{name}_{k}={float(val):.12e}")
        ds = block.get("data_sha256")
        if isinstance(ds, str):
            lines.append(f"{name}_data_sha256={ds}")

    baseline = payload.get("lcdm_baseline")
    if isinstance(baseline, Mapping):
        btot = baseline.get("total") if isinstance(baseline.get("total"), Mapping) else {}
        lines.append(f"lcdm_total_chi2={float(btot.get('chi2', 0.0)):.12e}")
        lines.append(f"lcdm_total_ndof={int(btot.get('ndof', 0))}")
    deltas = payload.get("deltas")
    if isinstance(deltas, Mapping):
        for key in (
            "delta_chi2_total",
            "delta_chi2_bao",
            "delta_chi2_sn",
            "delta_chi2_cmb",
            "delta_chi2_rsd",
        ):
            lines.append(f"{key}={float(deltas.get(key, 0.0)):.12e}")
    return "\n".join(lines) + "\n"


def _render_markdown(*, args: argparse.Namespace, payload: Mapping[str, Any]) -> str:
    blocks = payload.get("blocks") if isinstance(payload.get("blocks"), Mapping) else {}
    total = payload.get("total") if isinstance(payload.get("total"), Mapping) else {}
    lines: List[str] = [
        "# Low-z joint diagnostics report",
        "",
        "Claim-safe scope: deterministic diagnostic chi2 report (BAO + SN + RSD).",
        "This output is not a full global cosmology fit.",
        "",
        "## Model",
        f"- H0_km_s_Mpc: `{_fmt_num(payload.get('params', {}).get('H0_km_s_Mpc'))}`",
        f"- Omega_m0: `{_fmt_num(payload.get('params', {}).get('Omega_m0'))}`",
        f"- w0: `{_fmt_num(payload.get('params', {}).get('w_phi0'))}`",
        f"- lambda: `{_fmt_num(payload.get('params', {}).get('lambda'))}`",
        "",
        "## Blocks",
        "",
        "| block | enabled | chi2 | ndof | nuisance(bestfit) |",
        "|---|---:|---:|---:|---|",
    ]
    for name, nuisance_key in (
        ("bao", "rd_m_bestfit"),
        ("sn", "delta_M_bestfit"),
        ("cmb", None),
        ("rsd", "sigma8_0_bestfit"),
    ):
        block = blocks.get(name) if isinstance(blocks.get(name), Mapping) else {}
        nuisance = block.get(nuisance_key) if nuisance_key is not None else None
        if nuisance is None and name == "rsd":
            nuisance = block.get("sigma8_0_used")
        lines.append(
            "| "
            + f"{name} | {int(bool(block.get('enabled')))} | {_fmt_num(block.get('chi2'))} | {_fmt_num(block.get('ndof'))} | "
            + f"{_fmt_num(nuisance)} |"
        )
    lines.extend(
        [
            "",
            f"- total chi2: `{_fmt_num(total.get('chi2'))}`",
            f"- total ndof: `{_fmt_num(total.get('ndof'))}`",
        ]
    )

    deltas = payload.get("deltas")
    if isinstance(deltas, Mapping):
        lines.extend(
            [
                "",
                "## LCDM baseline deltas",
                f"- delta_chi2_total: `{_fmt_num(deltas.get('delta_chi2_total'))}`",
                f"- delta_chi2_bao: `{_fmt_num(deltas.get('delta_chi2_bao'))}`",
                f"- delta_chi2_sn: `{_fmt_num(deltas.get('delta_chi2_sn'))}`",
                f"- delta_chi2_cmb: `{_fmt_num(deltas.get('delta_chi2_cmb'))}`",
                f"- delta_chi2_rsd: `{_fmt_num(deltas.get('delta_chi2_rsd'))}`",
            ]
        )

    cmd: List[str] = [
        "python3 v11.0.0/scripts/phase3_joint_sigmatensor_lowz_report.py",
        f"--H0-km-s-Mpc {float(args.H0_km_s_Mpc):.12g}",
        f"--Omega-m {float(args.Omega_m):.12g}",
        f"--w0 {float(args.w0):.12g}",
        f"--lambda {float(args.lambda_):.12g}",
        f"--sigma8-mode {str(args.sigma8_mode)}",
        "--outdir <outdir>",
        "--format text",
    ]
    if args.sigma8_mode == "fixed":
        cmd.append(f"--sigma8-0 {float(args.sigma8_0):.12g}")
    if args.sigma8_mode == "derived_As":
        cmd.append(f"--As {float(args.As):.12g}")
    if str(args.ap_correction) == "1":
        cmd.append("--ap-correction 1")
    if str(args.cmb) == "1":
        cmd.extend(
            [
                "--cmb 1",
                f"--cmb-z-bridge {float(args.cmb_z_bridge):.12g}",
                f"--omega-b-h2 {float(args.omega_b_h2):.12g}",
            ]
        )
        if args.omega_cdm_h2 is not None:
            cmd.append(f"--omega-cdm-h2 {float(args.omega_cdm_h2):.12g}")
    if str(args.compare_lcdm) == "0":
        cmd.append("--compare-lcdm 0")
    lines.extend(
        [
            "",
            "## Reproduce",
            "```bash",
            " \\\n  ".join(cmd),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def _render_text(payload: Mapping[str, Any]) -> str:
    blocks = payload.get("blocks") if isinstance(payload.get("blocks"), Mapping) else {}
    total = payload.get("total") if isinstance(payload.get("total"), Mapping) else {}
    lines: List[str] = ["block,chi2,ndof,nuisance_bestfit"]
    for name, nuisance_key in (
        ("bao", "rd_m_bestfit"),
        ("sn", "delta_M_bestfit"),
        ("cmb", None),
        ("rsd", "sigma8_0_bestfit"),
    ):
        block = blocks.get(name) if isinstance(blocks.get(name), Mapping) else {}
        nuisance = block.get(nuisance_key) if nuisance_key is not None else None
        if nuisance is None and name == "rsd":
            nuisance = block.get("sigma8_0_used")
        lines.append(
            f"{name},{_fmt_num(block.get('chi2'))},{_fmt_num(block.get('ndof'))},{_fmt_num(nuisance)}"
        )
    lines.append(f"total,{_fmt_num(total.get('chi2'))},{_fmt_num(total.get('ndof'))},n/a")

    deltas = payload.get("deltas")
    if isinstance(deltas, Mapping):
        lines.append(
            "delta_vs_lcdm,"
            f"{_fmt_num(deltas.get('delta_chi2_total'))},n/a,"
            f"bao={_fmt_num(deltas.get('delta_chi2_bao'))};"
            f"sn={_fmt_num(deltas.get('delta_chi2_sn'))};"
            f"cmb={_fmt_num(deltas.get('delta_chi2_cmb'))};"
            f"rsd={_fmt_num(deltas.get('delta_chi2_rsd'))}"
        )
    return "\n".join(lines) + "\n"


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Phase-3 low-z joint diagnostics report (BAO+SN+RSD+optional CMB priors).")
    ap.add_argument("--H0-km-s-Mpc", dest="H0_km_s_Mpc", type=float, required=True)
    ap.add_argument("--Omega-m", dest="Omega_m", type=float, required=True)
    ap.add_argument("--w0", type=float, required=True)
    ap.add_argument("--lambda", dest="lambda_", type=float, required=True)
    ap.add_argument("--Tcmb-K", dest="Tcmb_K", type=float, default=2.7255)
    ap.add_argument("--N-eff", dest="N_eff", type=float, default=3.046)
    ap.add_argument("--Omega-r0-override", dest="Omega_r0_override", type=float, default=None)
    ap.add_argument("--sign-u0", dest="sign_u0", type=int, choices=(-1, +1), default=+1)

    ap.add_argument("--bao", choices=("0", "1"), default="1")
    ap.add_argument("--bao-data", type=Path, default=DEFAULT_BAO_DATA)
    ap.add_argument("--bao-n", type=int, default=10000)
    ap.add_argument("--sn", choices=("0", "1"), default="1")
    ap.add_argument("--sn-data", type=Path, default=DEFAULT_SN_DATA)
    ap.add_argument("--sn-n", type=int, default=2000)
    ap.add_argument("--cmb", choices=("0", "1"), default="0")
    ap.add_argument("--cmb-priors", type=Path, default=DEFAULT_CMB_PRIORS_DATA)
    ap.add_argument("--cmb-cov", type=Path, default=DEFAULT_CMB_COV_DATA)
    ap.add_argument("--cmb-z-bridge", type=float, default=5.0)
    ap.add_argument("--omega-b-h2", dest="omega_b_h2", type=float, default=0.02237)
    ap.add_argument("--omega-cdm-h2", dest="omega_cdm_h2", type=float, default=None)
    ap.add_argument("--cmb-integrator", choices=("trap", "adaptive_simpson"), default="trap")
    ap.add_argument("--cmb-eps-abs", type=float, default=1.0e-10)
    ap.add_argument("--cmb-eps-rel", type=float, default=1.0e-10)
    ap.add_argument("--cmb-rs-star-calibration", type=float, default=1.0)
    ap.add_argument("--cmb-dm-star-calibration", type=float, default=1.0)
    ap.add_argument("--rsd", choices=("0", "1"), default="1")
    ap.add_argument("--rsd-data", type=Path, default=DEFAULT_RSD_DATA)
    ap.add_argument("--ap-correction", choices=("0", "1"), default="0")

    ap.add_argument("--sigma8-mode", choices=("nuisance", "derived_As", "fixed"), default="nuisance")
    ap.add_argument("--sigma8-0", dest="sigma8_0", type=float, default=None)
    ap.add_argument("--As", dest="As", type=float, default=None)
    ap.add_argument("--ns", type=float, default=0.965)
    ap.add_argument("--transfer-model", choices=("bbks", "eh98_nowiggle"), default="bbks")
    ap.add_argument("--Omega-b0", dest="Omega_b0", type=float, default=0.049)
    ap.add_argument("--k0-mpc", dest="k0_mpc", type=float, default=0.05)
    ap.add_argument("--kmin", type=float, default=1.0e-4)
    ap.add_argument("--kmax", type=float, default=1.0e2)
    ap.add_argument("--nk", type=int, default=2048)

    ap.add_argument("--z-start", type=float, default=100.0)
    ap.add_argument("--n-steps-growth", dest="n_steps_growth", type=int, default=4000)
    ap.add_argument("--eps-dlnH", dest="eps_dlnH", type=float, default=1.0e-5)
    ap.add_argument("--n-steps-bg", dest="n_steps_bg", type=int, default=8192)
    ap.add_argument("--z-max-bg", dest="z_max_bg", type=float, default=None)

    ap.add_argument("--compare-lcdm", choices=("0", "1"), default="1")
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--created-utc", default=DEFAULT_CREATED_UTC)
    ap.add_argument("--format", choices=("text", "json"), default="text")
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        created_utc = _normalize_created_utc(str(args.created_utc))
        H0_km = _finite_positive(args.H0_km_s_Mpc, name="--H0-km-s-Mpc")
        H0_si = float(H0_to_SI(H0_km))
        omega_m0 = _finite_positive(args.Omega_m, name="--Omega-m")
        w0 = _finite_float(args.w0, name="--w0")
        lambda_ = _finite_float(args.lambda_, name="--lambda")
        Tcmb_K = _finite_positive(args.Tcmb_K, name="--Tcmb-K")
        N_eff = _finite_float(args.N_eff, name="--N-eff")
        if N_eff < 0.0:
            raise UsageError("--N-eff must be >= 0")
        omega_r0_override = None
        if args.Omega_r0_override is not None:
            omega_r0_override = _finite_float(args.Omega_r0_override, name="--Omega-r0-override")
            if omega_r0_override < 0.0:
                raise UsageError("--Omega-r0-override must be >= 0")

        bao_enabled = str(args.bao) == "1"
        sn_enabled = str(args.sn) == "1"
        cmb_enabled = str(args.cmb) == "1"
        rsd_enabled = str(args.rsd) == "1"
        ap_correction = str(args.ap_correction) == "1"
        compare_lcdm = str(args.compare_lcdm) == "1"

        cmb_z_bridge = _finite_positive(args.cmb_z_bridge, name="--cmb-z-bridge")
        omega_b_h2 = _finite_positive(args.omega_b_h2, name="--omega-b-h2")
        if args.omega_cdm_h2 is None:
            omega_c_h2_input = None
        else:
            omega_c_h2_input = _finite_float(args.omega_cdm_h2, name="--omega-cdm-h2")
        cmb_integrator = str(args.cmb_integrator)
        cmb_eps_abs = _finite_positive(args.cmb_eps_abs, name="--cmb-eps-abs")
        cmb_eps_rel = _finite_positive(args.cmb_eps_rel, name="--cmb-eps-rel")
        cmb_rs_star_calibration = _finite_positive(
            args.cmb_rs_star_calibration, name="--cmb-rs-star-calibration"
        )
        cmb_dm_star_calibration = _finite_positive(
            args.cmb_dm_star_calibration, name="--cmb-dm-star-calibration"
        )

        omega_c_h2_derived = False
        omega_c_h2 = None
        if cmb_enabled:
            omega_c_h2, omega_c_h2_derived = _resolve_omega_cdm_h2(
                H0_km_s_Mpc=float(H0_km),
                omega_m0=float(omega_m0),
                omega_b_h2=float(omega_b_h2),
                omega_cdm_h2_input=(None if omega_c_h2_input is None else float(omega_c_h2_input)),
            )

        sigma8_mode = str(args.sigma8_mode)
        sigma8_fixed = None
        As = None
        if rsd_enabled:
            if sigma8_mode == "fixed":
                if args.sigma8_0 is None:
                    raise UsageError("--sigma8-mode fixed requires --sigma8-0")
                sigma8_fixed = _finite_positive(args.sigma8_0, name="--sigma8-0")
            elif args.sigma8_0 is not None:
                raise UsageError("--sigma8-0 is only valid for --sigma8-mode fixed")

            if sigma8_mode == "derived_As":
                if args.As is None:
                    raise UsageError("--sigma8-mode derived_As requires --As")
                As = _finite_positive(args.As, name="--As")
            elif args.As is not None:
                raise UsageError("--As is only valid for --sigma8-mode derived_As")
        else:
            # RSD-disabled runs ignore sigma8 controls; keep scan usable for BAO/SN/CMB-only diagnostics.
            sigma8_mode = "unused"

        ns = _finite_float(args.ns, name="--ns")
        transfer_model = _canonical_transfer_model(str(args.transfer_model))
        omega_b0 = _finite_float(args.Omega_b0, name="--Omega-b0")
        if omega_b0 < 0.0:
            raise UsageError("--Omega-b0 must be >= 0")
        k0_mpc = _finite_positive(args.k0_mpc, name="--k0-mpc")
        kmin = _finite_positive(args.kmin, name="--kmin")
        kmax = _finite_positive(args.kmax, name="--kmax")
        if kmax <= kmin:
            raise UsageError("--kmax must be > --kmin")
        nk = int(args.nk)
        if nk < 8:
            raise UsageError("--nk must be >= 8")

        z_start = _finite_positive(args.z_start, name="--z-start")
        n_steps_growth = int(args.n_steps_growth)
        if n_steps_growth < 16:
            raise UsageError("--n-steps-growth must be >= 16")
        eps_dlnH = _finite_positive(args.eps_dlnH, name="--eps-dlnH")
        n_steps_bg = int(args.n_steps_bg)
        if n_steps_bg < 32:
            raise UsageError("--n-steps-bg must be >= 32")

        bao_n = int(args.bao_n)
        if bao_n < 100:
            raise UsageError("--bao-n must be >= 100")
        sn_n = int(args.sn_n)
        if sn_n < 100:
            raise UsageError("--sn-n must be >= 100")

        bao_dataset = None
        bao_data_sha256 = None
        bao_data_basename = None
        bao_zmax = 0.0
        if bao_enabled:
            bao_path = Path(args.bao_data).expanduser().resolve()
            try:
                bao_dataset = BAODataset.from_csv(bao_path)
            except Exception as exc:
                raise GateError(f"BAO dataset load failed: {exc}") from exc
            bao_data_sha256 = _sha256_file(bao_path)
            bao_data_basename = bao_path.name
            bao_zmax = _bao_max_z(bao_dataset)

        sn_dataset = None
        sn_data_sha256 = None
        sn_data_basename = None
        sn_zmax = 0.0
        if sn_enabled:
            sn_path = Path(args.sn_data).expanduser().resolve()
            try:
                sn_dataset = SNDataset.from_csv(sn_path)
            except Exception as exc:
                raise GateError(f"SN dataset load failed: {exc}") from exc
            sn_data_sha256 = _sha256_file(sn_path)
            sn_data_basename = sn_path.name
            sn_zmax = max(float(z) for z in sn_dataset.z) if sn_dataset.z else 0.0

        cmb_dataset = None
        cmb_priors_sha256 = None
        cmb_priors_basename = None
        cmb_cov_sha256 = None
        cmb_cov_basename = None
        cmb_zmax = 0.0
        if cmb_enabled:
            cmb_priors_path = Path(args.cmb_priors).expanduser().resolve()
            cmb_cov_path = Path(args.cmb_cov).expanduser().resolve()
            try:
                cmb_dataset = CMBPriorsDataset.from_csv(
                    cmb_priors_path,
                    cov_path=cmb_cov_path,
                    name="planck2018_chw2018",
                )
            except Exception as exc:
                raise GateError(f"CMB priors dataset load failed: {exc}") from exc
            cmb_priors_sha256 = _sha256_file(cmb_priors_path)
            cmb_priors_basename = cmb_priors_path.name
            cmb_cov_sha256 = _sha256_file(cmb_cov_path)
            cmb_cov_basename = cmb_cov_path.name
            cmb_zmax = float(cmb_z_bridge)

        rsd_rows: List[Mapping[str, Any]] = []
        rsd_data_sha256 = None
        rsd_data_basename = None
        rsd_zmax = 0.0
        if rsd_enabled:
            rsd_path = Path(args.rsd_data).expanduser().resolve()
            try:
                rsd_rows = list(load_fsigma8_csv(str(rsd_path)))
            except Exception as exc:
                raise GateError(f"RSD dataset load failed: {exc}") from exc
            if not rsd_rows:
                raise GateError("RSD dataset has no usable rows")
            rsd_data_sha256 = _sha256_file(rsd_path)
            rsd_data_basename = rsd_path.name
            rsd_zmax = max(float(row["z"]) for row in rsd_rows)

        max_data_z = max(float(bao_zmax), float(sn_zmax), float(cmb_zmax), float(rsd_zmax))
        z_max_bg_requested = None if args.z_max_bg is None else _finite_float(args.z_max_bg, name="--z-max-bg")
        z_max_bg_requested, z_max_bg_effective = _resolve_bg_zmax(
            z_max_bg_arg=z_max_bg_requested,
            max_data_z=float(max_data_z),
            z_start=float(z_start),
            eps_dlnH=float(eps_dlnH),
        )

        model_eval = _evaluate_sigma_tensor_model(
            H0_si=float(H0_si),
            omega_m0=float(omega_m0),
            w0=float(w0),
            lambda_=float(lambda_),
            Tcmb_K=float(Tcmb_K),
            N_eff=float(N_eff),
            omega_r0_override=(None if omega_r0_override is None else float(omega_r0_override)),
            sign_u0=int(args.sign_u0),
            z_max_bg_effective=float(z_max_bg_effective),
            n_steps_bg=int(n_steps_bg),
            bao_enabled=bool(bao_enabled),
            bao_dataset=bao_dataset,
            bao_data_basename=bao_data_basename,
            bao_data_sha256=bao_data_sha256,
            bao_n=int(bao_n),
            sn_enabled=bool(sn_enabled),
            sn_dataset=sn_dataset,
            sn_data_basename=sn_data_basename,
            sn_data_sha256=sn_data_sha256,
            sn_n=int(sn_n),
            cmb_enabled=bool(cmb_enabled),
            cmb_dataset=cmb_dataset,
            cmb_priors_basename=cmb_priors_basename,
            cmb_priors_sha256=cmb_priors_sha256,
            cmb_cov_basename=cmb_cov_basename,
            cmb_cov_sha256=cmb_cov_sha256,
            cmb_z_bridge=float(cmb_z_bridge),
            omega_b_h2=float(omega_b_h2),
            omega_c_h2=(0.0 if omega_c_h2 is None else float(omega_c_h2)),
            cmb_integrator=str(cmb_integrator),
            cmb_eps_abs=float(cmb_eps_abs),
            cmb_eps_rel=float(cmb_eps_rel),
            cmb_rs_star_calibration=float(cmb_rs_star_calibration),
            cmb_dm_star_calibration=float(cmb_dm_star_calibration),
            rsd_enabled=bool(rsd_enabled),
            rsd_rows=rsd_rows,
            rsd_data_basename=rsd_data_basename,
            rsd_data_sha256=rsd_data_sha256,
            ap_correction=bool(ap_correction),
            sigma8_mode=str(sigma8_mode),
            sigma8_fixed=(None if sigma8_fixed is None else float(sigma8_fixed)),
            As=(None if As is None else float(As)),
            ns=float(ns),
            transfer_model=str(transfer_model),
            omega_b0=float(omega_b0),
            k0_mpc=float(k0_mpc),
            kmin=float(kmin),
            kmax=float(kmax),
            nk=int(nk),
            z_start=float(z_start),
            n_steps_growth=int(n_steps_growth),
            eps_dlnH=float(eps_dlnH),
        )

        payload: Dict[str, Any] = {
            "schema": SCHEMA_NAME,
            "tool": TOOL_NAME,
            "created_utc": str(created_utc),
            "params": {
                "H0_km_s_Mpc": float(H0_km),
                "H0_si": float(H0_si),
                "Omega_m0": float(omega_m0),
                "w_phi0": float(w0),
                "lambda": float(lambda_),
                "Tcmb_K": float(Tcmb_K),
                "N_eff": float(N_eff),
                "Omega_r0_override": (None if omega_r0_override is None else float(omega_r0_override)),
                "sign_u0": int(args.sign_u0),
                "bao_enabled": bool(bao_enabled),
                "sn_enabled": bool(sn_enabled),
                "cmb_enabled": bool(cmb_enabled),
                "rsd_enabled": bool(rsd_enabled),
                "bao_data_basename": bao_data_basename,
                "sn_data_basename": sn_data_basename,
                "cmb_priors_basename": cmb_priors_basename,
                "cmb_cov_basename": cmb_cov_basename,
                "rsd_data_basename": rsd_data_basename,
                "bao_n": int(bao_n),
                "sn_n": int(sn_n),
                "cmb_z_bridge": float(cmb_z_bridge),
                "omega_b_h2": float(omega_b_h2),
                "omega_c_h2": (None if omega_c_h2 is None else float(omega_c_h2)),
                "omega_c_h2_derived": bool(omega_c_h2_derived),
                "cmb_integrator": str(cmb_integrator),
                "cmb_eps_abs": float(cmb_eps_abs),
                "cmb_eps_rel": float(cmb_eps_rel),
                "cmb_rs_star_calibration": float(cmb_rs_star_calibration),
                "cmb_dm_star_calibration": float(cmb_dm_star_calibration),
                "z_start": float(z_start),
                "n_steps_growth": int(n_steps_growth),
                "eps_dlnH": float(eps_dlnH),
                "n_steps_bg": int(n_steps_bg),
                "z_max_bg_requested": (None if z_max_bg_requested is None else float(z_max_bg_requested)),
                "z_max_bg_effective": float(z_max_bg_effective),
                "ap_correction": bool(ap_correction),
                "sigma8_mode": str(sigma8_mode),
                "transfer_model": str(transfer_model),
                "Omega_b0": float(omega_b0),
                "k0_mpc": float(k0_mpc),
                "kmin": float(kmin),
                "kmax": float(kmax),
                "nk": int(nk),
                "compare_lcdm": bool(compare_lcdm),
            },
            "derived_today": model_eval["derived_today"],
            "background_summary": {
                "z_max_bg_requested": (None if z_max_bg_requested is None else float(z_max_bg_requested)),
                "z_max_bg_effective": float(z_max_bg_effective),
                "n_steps_bg": int(n_steps_bg),
                "max_data_z": float(max_data_z),
            },
            "blocks": model_eval["blocks"],
            "total": model_eval["total"],
        }

        if compare_lcdm:
            baseline_eval = _evaluate_sigma_tensor_model(
                H0_si=float(H0_si),
                omega_m0=float(omega_m0),
                w0=-1.0,
                lambda_=0.0,
                Tcmb_K=float(Tcmb_K),
                N_eff=float(N_eff),
                omega_r0_override=(None if omega_r0_override is None else float(omega_r0_override)),
                sign_u0=int(args.sign_u0),
                z_max_bg_effective=float(z_max_bg_effective),
                n_steps_bg=int(n_steps_bg),
                bao_enabled=bool(bao_enabled),
                bao_dataset=bao_dataset,
                bao_data_basename=bao_data_basename,
                bao_data_sha256=bao_data_sha256,
                bao_n=int(bao_n),
                sn_enabled=bool(sn_enabled),
                sn_dataset=sn_dataset,
                sn_data_basename=sn_data_basename,
                sn_data_sha256=sn_data_sha256,
                sn_n=int(sn_n),
                cmb_enabled=bool(cmb_enabled),
                cmb_dataset=cmb_dataset,
                cmb_priors_basename=cmb_priors_basename,
                cmb_priors_sha256=cmb_priors_sha256,
                cmb_cov_basename=cmb_cov_basename,
                cmb_cov_sha256=cmb_cov_sha256,
                cmb_z_bridge=float(cmb_z_bridge),
                omega_b_h2=float(omega_b_h2),
                omega_c_h2=(0.0 if omega_c_h2 is None else float(omega_c_h2)),
                cmb_integrator=str(cmb_integrator),
                cmb_eps_abs=float(cmb_eps_abs),
                cmb_eps_rel=float(cmb_eps_rel),
                cmb_rs_star_calibration=float(cmb_rs_star_calibration),
                cmb_dm_star_calibration=float(cmb_dm_star_calibration),
                rsd_enabled=bool(rsd_enabled),
                rsd_rows=rsd_rows,
                rsd_data_basename=rsd_data_basename,
                rsd_data_sha256=rsd_data_sha256,
                ap_correction=bool(ap_correction),
                sigma8_mode=str(sigma8_mode),
                sigma8_fixed=(None if sigma8_fixed is None else float(sigma8_fixed)),
                As=(None if As is None else float(As)),
                ns=float(ns),
                transfer_model=str(transfer_model),
                omega_b0=float(omega_b0),
                k0_mpc=float(k0_mpc),
                kmin=float(kmin),
                kmax=float(kmax),
                nk=int(nk),
                z_start=float(z_start),
                n_steps_growth=int(n_steps_growth),
                eps_dlnH=float(eps_dlnH),
            )
            payload["lcdm_baseline"] = {
                "derived_today": baseline_eval["derived_today"],
                "blocks": baseline_eval["blocks"],
                "total": baseline_eval["total"],
            }
            payload["deltas"] = {
                "delta_chi2_total": float(model_eval["total"]["chi2"] - baseline_eval["total"]["chi2"]),
                "delta_chi2_bao": float(model_eval["blocks"]["bao"]["chi2"] - baseline_eval["blocks"]["bao"]["chi2"]),
                "delta_chi2_sn": float(model_eval["blocks"]["sn"]["chi2"] - baseline_eval["blocks"]["sn"]["chi2"]),
                "delta_chi2_cmb": float(model_eval["blocks"]["cmb"]["chi2"] - baseline_eval["blocks"]["cmb"]["chi2"]),
                "delta_chi2_rsd": float(model_eval["blocks"]["rsd"]["chi2"] - baseline_eval["blocks"]["rsd"]["chi2"]),
            }

        payload["digests"] = {
            "stable_rows_digest_sha256": _sha256_text(_digest_payload_lines(payload)),
        }

        outdir = Path(args.outdir).expanduser().resolve()
        outdir.mkdir(parents=True, exist_ok=True)
        json_text = _json_text(payload)
        (outdir / "LOWZ_JOINT_REPORT.json").write_text(json_text, encoding="utf-8")
        (outdir / "LOWZ_JOINT_REPORT.md").write_text(_render_markdown(args=args, payload=payload), encoding="utf-8")

    except UsageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except GateError as exc:
        print(FAIL_MARKER, file=sys.stderr)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if str(args.format) == "json":
        sys.stdout.write(json_text)
    else:
        sys.stdout.write(_render_text(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

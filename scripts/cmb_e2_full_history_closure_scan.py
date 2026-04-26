#!/usr/bin/env python3
"""E2.7 diagnostic: full-range (no-stitch) early-time closure scan.

Goal
----
Quantify whether an opt-in **full-range history** H(z) (defined over 0..z*)
can reduce/remove the strict CHW2018 distance-priors tension without a
bridge/stitch knob.

This script:
- runs a coarse grid over (p, z_transition) (as in E2.4),
- computes a reference *bridged* chi2 (using bridge_z_ref),
- computes a *full-history* chi2 for a small set of z_relax values,
- optionally reports residual diagnostic closure (dm_fit, rs_fit) via a
  deterministic semi-analytic joint fit.

Diagnostic-only. Must not be used as a submission claim.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


V101_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = V101_DIR.parent
sys.path.insert(0, str(V101_DIR))

import numpy as np  # noqa: E402

from gsc.datasets.cmb_priors import CMBPriorsDataset  # noqa: E402
from gsc.early_time import compute_bridged_distance_priors, compute_full_history_distance_priors  # noqa: E402
from gsc.early_time.cmb_distance_priors import _comoving_distance_model_to_z_m  # noqa: E402
from gsc.early_time.cmb_distance_priors import _RS_STAR_CALIB_CHW2018  # noqa: E402
from gsc.histories.full_range import FlatLCDMRadHistory, GSCTransitionFullHistory  # noqa: E402
from gsc.measurement_model import GSCTransitionHistory, H0_to_SI, MPC_SI, delta_v_cm_s  # noqa: E402


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _relpath(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except Exception:
        return str(path)


def _run_git(args: Sequence[str]) -> str:
    try:
        return subprocess.check_output(list(args), stderr=subprocess.STDOUT, text=True).strip()
    except Exception as e:  # pragma: no cover
        return f"<error: {e}>"


def _parse_float_list(csv_s: str) -> List[float]:
    out: List[float] = []
    for tok in str(csv_s).split(","):
        tok = tok.strip()
        if not tok:
            continue
        out.append(float(tok))
    if not out:
        raise ValueError("Empty CSV list")
    return out


def _parse_z_relax_list(csv_s: str) -> List[str]:
    """Parse a CSV list of z_relax values; supports the token 'inf'."""
    out: List[str] = []
    for tok in str(csv_s).split(","):
        t = tok.strip().lower()
        if not t:
            continue
        if t in ("inf", "infty", "infinite"):
            out.append("inf")
        else:
            z = float(t)
            if not (z > 0 and math.isfinite(z)):
                raise ValueError(f"Invalid z_relax value: {tok!r}")
            out.append(f"{z:g}")
    if not out:
        raise ValueError("Empty z_relax list")
    return out


def _effective_cov(ds: CMBPriorsDataset) -> np.ndarray:
    if ds.cov is None:
        raise ValueError("CMB covariance is required for strict CHW2018 distance-priors mode.")
    cov = np.asarray(ds.cov, dtype=float)
    sig_th = np.asarray(ds.sigmas_theory, dtype=float)
    if sig_th.size and float(np.max(sig_th)) > 0.0:
        cov = cov + np.diag(sig_th * sig_th)
    return cov


def _diag_pulls(*, keys: Tuple[str, ...], mean: np.ndarray, cov: np.ndarray, pred: Dict[str, float]) -> Dict[str, float]:
    diag = np.diag(cov)
    pulls: Dict[str, float] = {}
    for i, k in enumerate(keys):
        sigma = float(math.sqrt(float(diag[i])))
        pulls[k] = (float(pred[k]) - float(mean[i])) / sigma
    return pulls


def _apply_dm_rs_to_pred_raw(*, pred_raw: Dict[str, float], dm: float, rs: float) -> Dict[str, float]:
    if not (dm > 0 and math.isfinite(dm)):
        raise ValueError("dm must be finite and > 0")
    if not (rs > 0 and math.isfinite(rs)):
        raise ValueError("rs must be finite and > 0")

    out = dict(pred_raw)
    out["dm_star_calibration"] = float(dm)
    out["dm_star_calibration_applied"] = bool(float(dm) != 1.0)
    out["rs_star_calibration"] = float(rs)
    out["rs_star_calibration_applied"] = bool(float(rs) != 1.0)

    out["R"] = float(dm) * float(pred_raw["R"])
    out["lA"] = (float(dm) / float(rs)) * float(pred_raw["lA"])
    if "theta_star" in out:
        out["theta_star"] = (float(rs) / float(dm)) * float(pred_raw["theta_star"])
    if "D_M_star_Mpc" in out:
        out["D_M_star_Mpc"] = float(dm) * float(pred_raw["D_M_star_Mpc"])
    if "r_s_star_Mpc" in out:
        out["r_s_star_Mpc"] = float(rs) * float(pred_raw["r_s_star_Mpc"])
    return out


def _fit_dm_rs_against_chw2018(
    *,
    ds: CMBPriorsDataset,
    mean: np.ndarray,
    cov: np.ndarray,
    W: np.ndarray,
    pred_raw: Dict[str, float],
    rs_min: float,
    rs_max: float,
    rs_step: float,
    dm_min: float = 1e-6,
) -> Tuple[float, float, float]:
    keys = ds.keys
    for req in ("R", "lA", "omega_b_h2"):
        if req not in keys:
            raise ValueError(f"Dataset is missing required key: {req!r}")
    if not (rs_min > 0 and rs_max > rs_min and rs_step > 0):
        raise ValueError("Require rs_min>0, rs_max>rs_min, rs_step>0")

    iR = keys.index("R")
    ilA = keys.index("lA")
    iob = keys.index("omega_b_h2")

    R0 = float(pred_raw["R"])
    lA0 = float(pred_raw["lA"])
    ob_pred = float(pred_raw["omega_b_h2"])

    c = np.zeros_like(mean)
    c[iob] = ob_pred
    b = mean - c
    Wb = W @ b

    best_rs = float("nan")
    best_dm = float("nan")
    best_chi2 = float("inf")

    n = int(math.floor((float(rs_max) - float(rs_min)) / float(rs_step))) + 1
    for i in range(int(n)):
        rs = float(rs_min) + float(i) * float(rs_step)
        if rs > float(rs_max) + 1e-15:
            break

        A = np.zeros_like(mean)
        A[iR] = R0
        A[ilA] = lA0 / float(rs)

        denom = float(A @ (W @ A))
        if not (denom > 0 and math.isfinite(denom)):
            raise ValueError("Non-positive A^T W A (covariance issue)")
        dm = float((A @ Wb) / denom)
        if not (dm > 0 and math.isfinite(dm)):
            dm = float(dm_min)
        if dm < float(dm_min):
            dm = float(dm_min)

        y = float(dm) * A + c
        r = y - mean
        chi2 = float(r.T @ W @ r)
        if chi2 < best_chi2:
            best_chi2 = float(chi2)
            best_rs = float(rs)
            best_dm = float(dm)

    return float(best_dm), float(best_rs), float(best_chi2)


def _effective_const_A(
    *,
    D_low_Mpc: float,
    D_total_Mpc: float,
    dm_fit: float,
) -> Optional[float]:
    """Interpretation-only constant-A mapping above z_start (low piece fixed)."""
    if not (D_low_Mpc >= 0 and math.isfinite(D_low_Mpc)):
        return None
    if not (D_total_Mpc > 0 and math.isfinite(D_total_Mpc)):
        return None
    if not (dm_fit > 0 and math.isfinite(dm_fit)):
        return None
    D_target = float(dm_fit) * float(D_total_Mpc)
    D_high = float(D_total_Mpc) - float(D_low_Mpc)
    denom = float(D_target) - float(D_low_Mpc)
    if not (D_high > 0 and denom > 0 and math.isfinite(denom)):
        return None
    A = float(D_high) / float(denom)
    if not (A > 0 and math.isfinite(A)):
        return None
    return float(A)


@dataclass(frozen=True)
class ScanRow:
    model: str
    p: float
    z_transition: float
    bridge_z_ref: float
    z_relax: str
    z_bbn_clamp: str
    bbn_clamp: bool

    chi2_bridged_base: float
    chi2_full_base: float
    chi2_bridged_base_rs_reporting: float
    chi2_full_base_rs_reporting: float
    chi2_bridged_min: float
    chi2_full_min: float
    delta_chi2_bridged: float
    delta_chi2_full: float
    dm_fit_bridged: float
    rs_fit_bridged: float
    dm_fit_full: float
    rs_fit_full: float

    pulls_bridged_base_R: float
    pulls_bridged_base_lA: float
    pulls_full_base_R: float
    pulls_full_base_lA: float

    D_M_star_Mpc_bridged: float
    D_M_star_Mpc_full: float
    r_s_star_Mpc_bridged: float
    r_s_star_Mpc_full: float
    delta_DM_star_frac_full: float

    A_required_const_bridged: Optional[float]
    A_required_const_full: Optional[float]

    dv_base_z2_cm_s_10y: float
    dv_base_z3_cm_s_10y: float
    dv_base_z4_cm_s_10y: float
    dv_base_z5_cm_s_10y: float
    dv_full_z2_cm_s_10y: float
    dv_full_z3_cm_s_10y: float
    dv_full_z4_cm_s_10y: float
    dv_full_z5_cm_s_10y: float
    drift_sign_ok: bool

    def as_csv_dict(self) -> Dict[str, str]:
        def fmt(x: Optional[float], *, p: int = 16) -> str:
            if x is None:
                return ""
            if not math.isfinite(float(x)):
                return ""
            return f"{float(x):.{p}g}"

        return {
            "model": str(self.model),
            "p": fmt(self.p, p=12),
            "z_transition": fmt(self.z_transition, p=12),
            "bridge_z_ref": fmt(self.bridge_z_ref, p=12),
            "z_relax": str(self.z_relax),
            "bbn_clamp": str(bool(self.bbn_clamp)),
            "z_bbn_clamp": str(self.z_bbn_clamp),
            "chi2_bridged_base": fmt(self.chi2_bridged_base),
            "chi2_full_base": fmt(self.chi2_full_base),
            "chi2_bridged_base_rs_reporting": fmt(self.chi2_bridged_base_rs_reporting),
            "chi2_full_base_rs_reporting": fmt(self.chi2_full_base_rs_reporting),
            "chi2_bridged_min": fmt(self.chi2_bridged_min),
            "chi2_full_min": fmt(self.chi2_full_min),
            "delta_chi2_bridged": fmt(self.delta_chi2_bridged),
            "delta_chi2_full": fmt(self.delta_chi2_full),
            "dm_fit_bridged": fmt(self.dm_fit_bridged),
            "rs_fit_bridged": fmt(self.rs_fit_bridged),
            "dm_fit_full": fmt(self.dm_fit_full),
            "rs_fit_full": fmt(self.rs_fit_full),
            "pulls_bridged_base_R": fmt(self.pulls_bridged_base_R),
            "pulls_bridged_base_lA": fmt(self.pulls_bridged_base_lA),
            "pulls_full_base_R": fmt(self.pulls_full_base_R),
            "pulls_full_base_lA": fmt(self.pulls_full_base_lA),
            "D_M_star_Mpc_bridged": fmt(self.D_M_star_Mpc_bridged, p=12),
            "D_M_star_Mpc_full": fmt(self.D_M_star_Mpc_full, p=12),
            "r_s_star_Mpc_bridged": fmt(self.r_s_star_Mpc_bridged, p=12),
            "r_s_star_Mpc_full": fmt(self.r_s_star_Mpc_full, p=12),
            "delta_DM_star_frac_full": fmt(self.delta_DM_star_frac_full),
            "A_required_const_bridged": fmt(self.A_required_const_bridged),
            "A_required_const_full": fmt(self.A_required_const_full),
            "dv_base_z2_cm_s_10y": fmt(self.dv_base_z2_cm_s_10y, p=12),
            "dv_base_z3_cm_s_10y": fmt(self.dv_base_z3_cm_s_10y, p=12),
            "dv_base_z4_cm_s_10y": fmt(self.dv_base_z4_cm_s_10y, p=12),
            "dv_base_z5_cm_s_10y": fmt(self.dv_base_z5_cm_s_10y, p=12),
            "dv_full_z2_cm_s_10y": fmt(self.dv_full_z2_cm_s_10y, p=12),
            "dv_full_z3_cm_s_10y": fmt(self.dv_full_z3_cm_s_10y, p=12),
            "dv_full_z4_cm_s_10y": fmt(self.dv_full_z4_cm_s_10y, p=12),
            "dv_full_z5_cm_s_10y": fmt(self.dv_full_z5_cm_s_10y, p=12),
            "drift_sign_ok": str(bool(self.drift_sign_ok)),
        }


def _plot_chi2_vs_zrelax(
    *,
    rows: Sequence[ScanRow],
    z_relax_values: Sequence[str],
    out_path: Path,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: E402

    # Aggregate full-history chi2_base by z_relax.
    x = []
    y_med = []
    y_p10 = []
    y_p90 = []
    for zr in z_relax_values:
        vals = [float(r.chi2_full_base) for r in rows if str(r.z_relax) == str(zr) and math.isfinite(float(r.chi2_full_base))]
        if not vals:
            continue
        x.append(zr)
        y_med.append(float(np.median(vals)))
        y_p10.append(float(np.quantile(vals, 0.10)))
        y_p90.append(float(np.quantile(vals, 0.90)))

    fig, ax = plt.subplots(figsize=(7.6, 4.8), constrained_layout=True)
    ax.plot(range(len(x)), y_med, marker="o", linewidth=2.5, label="median chi2 (full history; dm=rs=1)")
    ax.fill_between(range(len(x)), y_p10, y_p90, alpha=0.20, label="10–90% band")
    ax.set_yscale("log")
    ax.set_xticks(range(len(x)))
    ax.set_xticklabels(x, rotation=0)
    ax.set_xlabel("z_relax (p(z) relax scale; 'inf' = no relax)")
    ax.set_ylabel("chi2 (strict CHW2018 distance priors)")
    ax.set_title("E2.7 diagnostic: full-history chi2_base (dm=rs=1) vs z_relax (grid summary)")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend(frameon=False)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def _plot_quantiles_vs_zrelax(
    *,
    rows: Sequence[ScanRow],
    z_relax_values: Sequence[str],
    getter,
    ylabel: str,
    title: str,
    out_path: Path,
    yscale: str = "linear",
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: E402

    x = []
    y_med = []
    y_p10 = []
    y_p90 = []
    for zr in z_relax_values:
        vals = [float(getter(r)) for r in rows if str(r.z_relax) == str(zr) and math.isfinite(float(getter(r)))]
        if not vals:
            continue
        x.append(zr)
        y_med.append(float(np.median(vals)))
        y_p10.append(float(np.quantile(vals, 0.10)))
        y_p90.append(float(np.quantile(vals, 0.90)))

    fig, ax = plt.subplots(figsize=(7.6, 4.8), constrained_layout=True)
    ax.plot(range(len(x)), y_med, marker="o", linewidth=2.5, label="median")
    ax.fill_between(range(len(x)), y_p10, y_p90, alpha=0.20, label="10–90% band")
    if yscale != "linear":
        ax.set_yscale(yscale)
    ax.set_xticks(range(len(x)))
    ax.set_xticklabels(x, rotation=0)
    ax.set_xlabel("z_relax (p(z) relax scale; 'inf' = no relax)")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, which="both", alpha=0.25)
    ax.legend(frameon=False)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def run(
    *,
    cmb_csv: Path,
    cmb_cov: Path,
    out_dir: Path,
    bridge_z_ref: float,
    p_grid: Sequence[float],
    ztrans_grid: Sequence[float],
    z_relax_list: Sequence[str],
    z_bbn_clamp: Optional[float],
    n_D_M: int,
    n_r_s: int,
    H0_km_s_Mpc: float,
    Omega_m: float,
    omega_b_h2: float,
    omega_c_h2: float,
    Neff: float,
    Tcmb_K: float,
    baseline_rs: float,
    rs_min: float,
    rs_max: float,
    rs_step: float,
) -> Dict[str, Any]:
    out_dir = out_dir.resolve()
    tables_dir = out_dir / "tables"
    figs_dir = out_dir / "figures"
    _ensure_dir(tables_dir)
    _ensure_dir(figs_dir)

    ds = CMBPriorsDataset.from_csv(cmb_csv, cov_path=cmb_cov)
    keys = ds.keys
    mean = np.asarray(ds.values, dtype=float)
    cov = _effective_cov(ds)
    W = np.linalg.inv(cov)

    if int(n_D_M) < 512:
        raise ValueError("n_D_M too small")
    if int(n_r_s) < 512:
        raise ValueError("n_r_s too small")

    lcdm_rad = FlatLCDMRadHistory(H0=H0_to_SI(float(H0_km_s_Mpc)), Omega_m=float(Omega_m), N_eff=float(Neff), Tcmb_K=float(Tcmb_K))
    pred_raw_lcdm = compute_full_history_distance_priors(
        history_full=lcdm_rad,
        omega_b_h2=float(omega_b_h2),
        omega_c_h2=float(omega_c_h2),
        N_eff=float(Neff),
        Tcmb_K=float(Tcmb_K),
        rs_star_calibration=1.0,
        dm_star_calibration=1.0,
        n_D_M=int(n_D_M),
        n_r_s=int(n_r_s),
    )
    D_M_star_Mpc_lcdm = float(pred_raw_lcdm["D_M_star_Mpc_raw"])

    rows: List[ScanRow] = []
    for p in p_grid:
        for zt in ztrans_grid:
            # Reference bridged predictor.
            hist_bridged = GSCTransitionHistory(
                H0=H0_to_SI(float(H0_km_s_Mpc)),
                Omega_m=float(Omega_m),
                Omega_Lambda=float(1.0 - float(Omega_m)),
                p=float(p),
                z_transition=float(zt),
            )
            pred_raw_bridged = compute_bridged_distance_priors(
                model=hist_bridged,
                z_bridge=float(bridge_z_ref),
                omega_b_h2=float(omega_b_h2),
                omega_c_h2=float(omega_c_h2),
                N_eff=float(Neff),
                Tcmb_K=float(Tcmb_K),
                rs_star_calibration=1.0,
                dm_star_calibration=1.0,
            )

            # Drift sanity (late-time, z~2-5). Supporting diagnostic only in Roadmap v2.8 framing.
            drift_years = 10.0
            dv_base = {
                2.0: float(delta_v_cm_s(z=2.0, years=drift_years, H0=float(hist_bridged.H(0.0)), H_of_z=hist_bridged.H)),
                3.0: float(delta_v_cm_s(z=3.0, years=drift_years, H0=float(hist_bridged.H(0.0)), H_of_z=hist_bridged.H)),
                4.0: float(delta_v_cm_s(z=4.0, years=drift_years, H0=float(hist_bridged.H(0.0)), H_of_z=hist_bridged.H)),
                5.0: float(delta_v_cm_s(z=5.0, years=drift_years, H0=float(hist_bridged.H(0.0)), H_of_z=hist_bridged.H)),
            }

            # No-fudge baseline: dm=1, rs=1. (No calibration/rescaling.)
            pred_base_bridged = _apply_dm_rs_to_pred_raw(pred_raw=pred_raw_bridged, dm=1.0, rs=1.0)
            chi2_base_bridged = float(ds.chi2_from_values(pred_base_bridged).chi2)
            pulls_base_bridged = _diag_pulls(keys=keys, mean=mean, cov=cov, pred=pred_base_bridged)

            # Reporting-only baseline: dm=1, rs=baseline_rs (legacy bridge stopgap for comparisons).
            pred_base_bridged_rs_reporting = _apply_dm_rs_to_pred_raw(pred_raw=pred_raw_bridged, dm=1.0, rs=float(baseline_rs))
            chi2_base_bridged_rs_reporting = float(ds.chi2_from_values(pred_base_bridged_rs_reporting).chi2)

            dm_fit_b, rs_fit_b, chi2_min_b = _fit_dm_rs_against_chw2018(
                ds=ds,
                mean=mean,
                cov=cov,
                W=W,
                pred_raw=pred_raw_bridged,
                rs_min=float(rs_min),
                rs_max=float(rs_max),
                rs_step=float(rs_step),
            )
            delta_chi2_b = float(chi2_base_bridged) - float(chi2_min_b)

            D_low_b = float(pred_raw_bridged.get("D_M_0_to_bridge_Mpc", float("nan")))
            D_high_b = float(pred_raw_bridged.get("D_M_bridge_to_zstar_Mpc", float("nan")))
            A_req_b = None
            if math.isfinite(D_low_b) and math.isfinite(D_high_b) and D_low_b >= 0 and D_high_b > 0:
                A_req_b = _effective_const_A(D_low_Mpc=float(D_low_b), D_total_Mpc=float(D_low_b + D_high_b), dm_fit=float(dm_fit_b))

            # Full history for each z_relax.
            for zr_s in z_relax_list:
                if zr_s == "inf":
                    zr = math.inf
                else:
                    zr = float(zr_s)

                hist_full = GSCTransitionFullHistory(
                    H0=H0_to_SI(float(H0_km_s_Mpc)),
                    Omega_m=float(Omega_m),
                    p_late=float(p),
                    z_transition=float(zt),
                    z_relax=float(zr),
                    N_eff=float(Neff),
                    Tcmb_K=float(Tcmb_K),
                    z_bbn_clamp=float(z_bbn_clamp) if z_bbn_clamp is not None else None,
                )
                pred_raw_full = compute_full_history_distance_priors(
                    history_full=hist_full,
                    omega_b_h2=float(omega_b_h2),
                    omega_c_h2=float(omega_c_h2),
                    N_eff=float(Neff),
                    Tcmb_K=float(Tcmb_K),
                    rs_star_calibration=1.0,
                    dm_star_calibration=1.0,
                    n_D_M=int(n_D_M),
                    n_r_s=int(n_r_s),
                )

                pred_base_full = _apply_dm_rs_to_pred_raw(pred_raw=pred_raw_full, dm=1.0, rs=1.0)
                chi2_base_full = float(ds.chi2_from_values(pred_base_full).chi2)
                pulls_base_full = _diag_pulls(keys=keys, mean=mean, cov=cov, pred=pred_base_full)

                pred_base_full_rs_reporting = _apply_dm_rs_to_pred_raw(pred_raw=pred_raw_full, dm=1.0, rs=float(baseline_rs))
                chi2_base_full_rs_reporting = float(ds.chi2_from_values(pred_base_full_rs_reporting).chi2)
                dm_fit_f, rs_fit_f, chi2_min_f = _fit_dm_rs_against_chw2018(
                    ds=ds,
                    mean=mean,
                    cov=cov,
                    W=W,
                    pred_raw=pred_raw_full,
                    rs_min=float(rs_min),
                    rs_max=float(rs_max),
                    rs_step=float(rs_step),
                )
                delta_chi2_f = float(chi2_base_full) - float(chi2_min_f)

                # Interpretation-only A mapping above z_transition: compute D_low and map dm_fit.
                z_star = float(pred_raw_full.get("z_star", float("nan")))
                D_total_full = float(pred_raw_full.get("D_M_star_Mpc_raw", float("nan")))
                delta_DM_frac_full = float("nan")
                if math.isfinite(D_total_full) and float(D_M_star_Mpc_lcdm) > 0:
                    delta_DM_frac_full = (float(D_total_full) - float(D_M_star_Mpc_lcdm)) / float(D_M_star_Mpc_lcdm)
                A_req_f = None
                if math.isfinite(z_star) and math.isfinite(D_total_full) and float(zt) < float(z_star):
                    D_low_full_m = _comoving_distance_model_to_z_m(z=float(zt), model=hist_full, n=4096)
                    D_low_full = float(D_low_full_m / float(MPC_SI))
                    A_req_f = _effective_const_A(D_low_Mpc=float(D_low_full), D_total_Mpc=float(D_total_full), dm_fit=float(dm_fit_f))

                dv_full = {
                    2.0: float(delta_v_cm_s(z=2.0, years=drift_years, H0=float(hist_full.H(0.0)), H_of_z=hist_full.H)),
                    3.0: float(delta_v_cm_s(z=3.0, years=drift_years, H0=float(hist_full.H(0.0)), H_of_z=hist_full.H)),
                    4.0: float(delta_v_cm_s(z=4.0, years=drift_years, H0=float(hist_full.H(0.0)), H_of_z=hist_full.H)),
                    5.0: float(delta_v_cm_s(z=5.0, years=drift_years, H0=float(hist_full.H(0.0)), H_of_z=hist_full.H)),
                }
                drift_ok = bool(all(float(v) > 0.0 for v in dv_full.values()))

                rows.append(
                    ScanRow(
                        model="gsc_transition",
                        p=float(p),
                        z_transition=float(zt),
                        bridge_z_ref=float(bridge_z_ref),
                        z_relax=str(zr_s),
                        z_bbn_clamp=("none" if z_bbn_clamp is None else f"{float(z_bbn_clamp):g}"),
                        bbn_clamp=bool(z_bbn_clamp is not None),
                        chi2_bridged_base=float(chi2_base_bridged),
                        chi2_full_base=float(chi2_base_full),
                        chi2_bridged_base_rs_reporting=float(chi2_base_bridged_rs_reporting),
                        chi2_full_base_rs_reporting=float(chi2_base_full_rs_reporting),
                        chi2_bridged_min=float(chi2_min_b),
                        chi2_full_min=float(chi2_min_f),
                        delta_chi2_bridged=float(delta_chi2_b),
                        delta_chi2_full=float(delta_chi2_f),
                        dm_fit_bridged=float(dm_fit_b),
                        rs_fit_bridged=float(rs_fit_b),
                        dm_fit_full=float(dm_fit_f),
                        rs_fit_full=float(rs_fit_f),
                        pulls_bridged_base_R=float(pulls_base_bridged.get("R", float("nan"))),
                        pulls_bridged_base_lA=float(pulls_base_bridged.get("lA", float("nan"))),
                        pulls_full_base_R=float(pulls_base_full.get("R", float("nan"))),
                        pulls_full_base_lA=float(pulls_base_full.get("lA", float("nan"))),
                        D_M_star_Mpc_bridged=float(pred_raw_bridged["D_M_star_Mpc_raw"]),
                        D_M_star_Mpc_full=float(pred_raw_full["D_M_star_Mpc_raw"]),
                        r_s_star_Mpc_bridged=float(pred_raw_bridged["r_s_star_Mpc"]),
                        r_s_star_Mpc_full=float(pred_raw_full["r_s_star_Mpc"]),
                        delta_DM_star_frac_full=float(delta_DM_frac_full),
                        A_required_const_bridged=A_req_b,
                        A_required_const_full=A_req_f,
                        dv_base_z2_cm_s_10y=float(dv_base[2.0]),
                        dv_base_z3_cm_s_10y=float(dv_base[3.0]),
                        dv_base_z4_cm_s_10y=float(dv_base[4.0]),
                        dv_base_z5_cm_s_10y=float(dv_base[5.0]),
                        dv_full_z2_cm_s_10y=float(dv_full[2.0]),
                        dv_full_z3_cm_s_10y=float(dv_full[3.0]),
                        dv_full_z4_cm_s_10y=float(dv_full[4.0]),
                        dv_full_z5_cm_s_10y=float(dv_full[5.0]),
                        drift_sign_ok=bool(drift_ok),
                    )
                )

    csv_path = tables_dir / "cmb_full_history_scan.csv"
    fieldnames = list(rows[0].as_csv_dict().keys())
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r.as_csv_dict())

    fig_chi2_base = figs_dir / "chi2_full_base_vs_z_relax.png"
    _plot_chi2_vs_zrelax(rows=rows, z_relax_values=z_relax_list, out_path=fig_chi2_base)

    fig_dm = figs_dir / "dm_fit_full_vs_z_relax.png"
    _plot_quantiles_vs_zrelax(
        rows=rows,
        z_relax_values=z_relax_list,
        getter=lambda r: r.dm_fit_full,
        ylabel="dm_fit_full (diagnostic distance-closure factor)",
        title="E2.7 diagnostic: dm_fit_full vs z_relax (grid summary)",
        out_path=fig_dm,
        yscale="linear",
    )

    fig_rs = figs_dir / "rs_fit_full_vs_z_relax.png"
    _plot_quantiles_vs_zrelax(
        rows=rows,
        z_relax_values=z_relax_list,
        getter=lambda r: r.rs_fit_full,
        ylabel="rs_fit_full (diagnostic sound-horizon factor)",
        title="E2.7 diagnostic: rs_fit_full vs z_relax (grid summary)",
        out_path=fig_rs,
        yscale="linear",
    )

    chi2_base_med: Dict[str, float] = {}
    chi2_min_med: Dict[str, float] = {}
    dm_q: Dict[str, Dict[str, float]] = {}
    drift_ok_frac: Dict[str, float] = {}

    for zr in z_relax_list:
        vals_base = [float(r.chi2_full_base) for r in rows if str(r.z_relax) == str(zr) and math.isfinite(float(r.chi2_full_base))]
        if vals_base:
            chi2_base_med[str(zr)] = float(np.median(vals_base))

        vals_min = [float(r.chi2_full_min) for r in rows if str(r.z_relax) == str(zr) and math.isfinite(float(r.chi2_full_min))]
        if vals_min:
            chi2_min_med[str(zr)] = float(np.median(vals_min))

        vals_dm = [float(r.dm_fit_full) for r in rows if str(r.z_relax) == str(zr) and math.isfinite(float(r.dm_fit_full))]
        if vals_dm:
            dm_q[str(zr)] = {
                "q10": float(np.quantile(vals_dm, 0.10)),
                "q50": float(np.quantile(vals_dm, 0.50)),
                "q90": float(np.quantile(vals_dm, 0.90)),
            }

        vals_ok = [1.0 if r.drift_sign_ok else 0.0 for r in rows if str(r.z_relax) == str(zr)]
        if vals_ok:
            drift_ok_frac[str(zr)] = float(np.mean(vals_ok))

    summary: Dict[str, Any] = {
        "num_points_total": int(len(rows)),
        "num_grid_points": int(len(p_grid) * len(ztrans_grid)),
        "z_relax_list": list(z_relax_list),
        "D_M_star_Mpc_lcdm_rad_full_history": float(D_M_star_Mpc_lcdm),
        "chi2_full_base_median_by_z_relax": chi2_base_med,
        "chi2_full_min_median_by_z_relax": chi2_min_med,
        "dm_fit_full_quantiles_by_z_relax": dm_q,
        "drift_sign_ok_fraction_by_z_relax": drift_ok_frac,
    }

    manifest: Dict[str, Any] = {
        "diagnostic_only": True,
        "kind": "cmb_e2_full_history_closure_scan",
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "git_commit": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"]),
        "git_branch": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "--abbrev-ref", "HEAD"]),
        "git_dirty": bool(_run_git(["git", "-C", str(REPO_ROOT), "status", "--porcelain=v1"]).strip()),
        "inputs": {
            "cmb_csv": _relpath(cmb_csv),
            "cmb_cov": _relpath(cmb_cov),
        },
        "fixed_params": {
            "H0_km_s_Mpc": float(H0_km_s_Mpc),
            "Omega_m": float(Omega_m),
            "omega_b_h2": float(omega_b_h2),
            "omega_c_h2": float(omega_c_h2),
            "Neff": float(Neff),
            "Tcmb_K": float(Tcmb_K),
            "baseline_rs_reporting": float(baseline_rs),
        },
        "grid": {
            "bridge_z_ref": float(bridge_z_ref),
            "p": [float(x) for x in p_grid],
            "z_transition": [float(x) for x in ztrans_grid],
            "z_relax": list(z_relax_list),
            "z_bbn_clamp": (None if z_bbn_clamp is None else float(z_bbn_clamp)),
        },
        "definitions": {
            "no_fudge_baseline": {"dm_star_calibration": 1.0, "rs_star_calibration": 1.0},
            "delta_DM_star_frac_full": "(D_M_star_full_raw - D_M_star_lcdm_rad_raw) / D_M_star_lcdm_rad_raw",
            "p_eff_z_definition": (
                "p_eff(z) = p_late for z<=z_transition; "
                "p_eff(z) = p_late + (1.5 - p_late) * (1 - exp(-(z-z_transition)/z_relax)) for z>z_transition"
            ),
            "H_full_definition": "H(z)^2 = H_gsc_component(z)^2 + H_rad(z)^2 (plus optional BBN clamp at very high z)",
        },
        "drift_check": {
            "years": 10.0,
            "z": [2.0, 3.0, 4.0, 5.0],
            "metric": "delta_v_cm_s",
            "sign_ok_definition": "all(dv_cm_s_10y > 0) on z in [2,3,4,5]",
        },
        "baseline_histories": {
            "lcdm_rad": {
                "H0_si": float(lcdm_rad.H0),
                "Omega_m": float(lcdm_rad.Omega_m),
                "Omega_r": float(lcdm_rad.Omega_r),
            }
        },
        "fit": {
            "rs_grid": {"rs_min": float(rs_min), "rs_max": float(rs_max), "rs_step": float(rs_step)},
            "dm_min": 1e-6,
        },
        "outputs": {
            "outdir": _relpath(out_dir),
            "csv": _relpath(csv_path),
            "fig_chi2_full_base_vs_z_relax": _relpath(fig_chi2_base),
            "fig_dm_fit_full_vs_z_relax": _relpath(fig_dm),
            "fig_rs_fit_full_vs_z_relax": _relpath(fig_rs),
        },
        "summary": summary,
        "notes": [
            "Diagnostic-only: compares bridged E1 distance priors vs a full-range history (no stitch) with p(z) relaxation + BBN safety clamp.",
            "Out of submission scope; does not change canonical late-time outputs.",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return manifest


def main(argv: Optional[Sequence[str]] = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cmb", type=Path, default=V101_DIR / "data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv")
    ap.add_argument(
        "--cmb-cov",
        type=Path,
        default=V101_DIR / "data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov",
    )
    ap.add_argument("--outdir", type=Path, default=Path("v11.0.0/results/diagnostic_cmb_full_history"))

    ap.add_argument("--bridge-z-ref", type=float, default=5.0)
    ap.add_argument("--p-grid", type=str, default="0.55,0.6,0.65,0.7,0.75,0.8,0.9")
    ap.add_argument("--ztrans-grid", type=str, default="0.8,1.2,1.5,1.8,2.2,3.0,4.0")
    ap.add_argument("--z-relax-list", type=str, default="2,5,10,20,inf", help="CSV list; supports 'inf' for no relax.")
    ap.add_argument("--z-bbn-clamp", type=float, default=1.0e7, help="If >0, clamp to LCDM+rad at z>=z_bbn_clamp. Use 0 to disable.")
    ap.add_argument("--n-dm", type=int, default=8192, help="Integration grid size for D_M(z*).")
    ap.add_argument("--n-rs", type=int, default=8192, help="Integration grid size for r_s(z*).")

    ap.add_argument("--H0", type=float, default=67.4)
    ap.add_argument("--Omega-m", dest="Omega_m", type=float, default=0.315)
    ap.add_argument("--omega-b-h2", type=float, default=0.02237)
    ap.add_argument("--omega-c-h2", type=float, default=0.1200)
    ap.add_argument("--Neff", type=float, default=3.046)
    ap.add_argument("--Tcmb-K", type=float, default=2.7255)

    ap.add_argument(
        "--baseline-rs",
        type=float,
        default=float(_RS_STAR_CALIB_CHW2018),
        help="Reporting-only baseline rs_star_calibration used for chi2_*_base_rs_reporting (legacy stopgap).",
    )
    ap.add_argument("--rs-min", type=float, default=0.90)
    ap.add_argument("--rs-max", type=float, default=1.20)
    ap.add_argument("--rs-step", type=float, default=1e-3)

    args = ap.parse_args(argv)

    z_bbn_clamp = float(args.z_bbn_clamp)
    if not math.isfinite(z_bbn_clamp) or z_bbn_clamp <= 0:
        z_bbn_clamp_opt = None
    else:
        z_bbn_clamp_opt = float(z_bbn_clamp)

    run(
        cmb_csv=Path(args.cmb),
        cmb_cov=Path(args.cmb_cov),
        out_dir=Path(args.outdir),
        bridge_z_ref=float(args.bridge_z_ref),
        p_grid=_parse_float_list(str(args.p_grid)),
        ztrans_grid=_parse_float_list(str(args.ztrans_grid)),
        z_relax_list=_parse_z_relax_list(str(args.z_relax_list)),
        z_bbn_clamp=z_bbn_clamp_opt,
        n_D_M=int(args.n_dm),
        n_r_s=int(args.n_rs),
        H0_km_s_Mpc=float(args.H0),
        Omega_m=float(args.Omega_m),
        omega_b_h2=float(args.omega_b_h2),
        omega_c_h2=float(args.omega_c_h2),
        Neff=float(args.Neff),
        Tcmb_K=float(args.Tcmb_K),
        baseline_rs=float(args.baseline_rs),
        rs_min=float(args.rs_min),
        rs_max=float(args.rs_max),
        rs_step=float(args.rs_step),
    )


if __name__ == "__main__":  # pragma: no cover
    main()

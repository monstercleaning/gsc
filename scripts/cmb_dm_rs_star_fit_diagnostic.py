#!/usr/bin/env python3
"""E2.2 diagnostic: joint-fit (D_M(z*), r_s(z*)) closure vs strict CHW2018 priors.

Purpose
-------
Quantify "what would it take" to reconcile a *non-degenerate* E1-style bridge
prediction with strict CHW2018 distance priors by allowing two purely
diagnostic, multiplicative calibration knobs:

- `dm_star_calibration`: multiplies D_M(z*)
- `rs_star_calibration`: multiplies r_s(z*)

Then:
- R ∝ D_M(z*)  (controls R directly)
- lA = pi * D_M(z*) / r_s(z*)  (controls lA via the ratio)

This is diagnostic-only tooling. It must not be used as a physics claim.
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
from typing import Any, Dict, List, Tuple
import zipfile


V101_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = V101_DIR.parent
sys.path.insert(0, str(V101_DIR))

import numpy as np  # noqa: E402

from gsc.datasets.cmb_priors import CMBPriorsDataset  # noqa: E402
from gsc.early_time import compute_bridged_distance_priors, compute_lcdm_distance_priors  # noqa: E402
from gsc.early_time.cmb_distance_priors import _RS_STAR_CALIB_CHW2018  # noqa: E402
from gsc.measurement_model import (  # noqa: E402
    GSCTransitionHistory,
    H0_to_SI,
    PowerLawHistory,
)


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _relpath(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except Exception:
        return str(path)


def _run_git(cmd: List[str]) -> str:
    try:
        return subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True).strip()
    except Exception as e:
        return f"<error: {e}>"


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


def _make_plot(*, x: List[float], y: List[float], out_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: E402

    fig, ax = plt.subplots(figsize=(7.5, 4.5), constrained_layout=True)
    ax.plot(x, y, marker="o", linewidth=2.0)
    ax.set_xlabel("rs_star_calibration")
    ax.set_ylabel("chi2_min(dm | rs)  (CHW2018 cov)")
    ax.set_title("E2.2 diagnostic: chi2 vs rs_star_calibration (dm optimized analytically)")
    ax.grid(True, alpha=0.3)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def _zip_dir(*, dir_path: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    root_name = dir_path.name
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(dir_path.rglob("*")):
            if p.is_dir():
                continue
            if p.name in {".DS_Store"} or p.name.startswith("._") or "__MACOSX" in str(p):
                continue
            arc = str(Path(root_name) / p.relative_to(dir_path))
            zf.write(p, arcname=arc)


@dataclass(frozen=True)
class JointFitResult:
    dm_star_calibration_fit: float
    rs_star_calibration_fit: float
    chi2_base: float
    chi2_min: float

    pulls_base: Dict[str, float]
    pulls_fit: Dict[str, float]

    pred_raw: Dict[str, float]
    pred_base: Dict[str, float]
    pred_fit: Dict[str, float]

    bridge_z_used: float
    is_degenerate: bool


def _compute_pred_raw(
    *,
    model: str,
    H0_km_s_Mpc: float,
    Omega_m: float,
    Omega_L: float,
    gsc_p: float,
    gsc_ztrans: float,
    cmb_bridge_z: float,
    omega_b_h2: float,
    omega_c_h2: float,
    Neff: float,
    Tcmb_K: float,
) -> Dict[str, float]:
    if model == "lcdm":
        return compute_lcdm_distance_priors(
            H0_km_s_Mpc=float(H0_km_s_Mpc),
            Omega_m=float(Omega_m),
            omega_b_h2=float(omega_b_h2),
            omega_c_h2=float(omega_c_h2),
            N_eff=float(Neff),
            Tcmb_K=float(Tcmb_K),
            rs_star_calibration=1.0,
            dm_star_calibration=1.0,
        )
    if model == "gsc_transition":
        H0_si = H0_to_SI(float(H0_km_s_Mpc))
        hist = GSCTransitionHistory(
            H0=float(H0_si),
            Omega_m=float(Omega_m),
            Omega_Lambda=float(Omega_L),
            p=float(gsc_p),
            z_transition=float(gsc_ztrans),
        )
        pred = compute_bridged_distance_priors(
            model=hist,
            z_bridge=float(cmb_bridge_z),
            omega_b_h2=float(omega_b_h2),
            omega_c_h2=float(omega_c_h2),
            N_eff=float(Neff),
            Tcmb_K=float(Tcmb_K),
            rs_star_calibration=1.0,
            dm_star_calibration=1.0,
        )
        # Help diagnostics: allow degeneracy checks without threading extra args around.
        pred["z_transition"] = float(gsc_ztrans)
        return pred
    if model == "gsc_powerlaw":
        H0_si = H0_to_SI(float(H0_km_s_Mpc))
        hist = PowerLawHistory(H0=float(H0_si), p=float(gsc_p))
        return compute_bridged_distance_priors(
            model=hist,
            z_bridge=float(cmb_bridge_z),
            omega_b_h2=float(omega_b_h2),
            omega_c_h2=float(omega_c_h2),
            N_eff=float(Neff),
            Tcmb_K=float(Tcmb_K),
            rs_star_calibration=1.0,
            dm_star_calibration=1.0,
        )
    raise ValueError(f"Unknown model: {model}")


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

    # Apply scaling consistent with how the predictor uses the calibrated D_M, r_s.
    out["R"] = float(dm) * float(pred_raw["R"])
    out["lA"] = (float(dm) / float(rs)) * float(pred_raw["lA"])
    if "theta_star" in out:
        out["theta_star"] = (float(rs) / float(dm)) * float(pred_raw["theta_star"])
    if "D_M_star_Mpc" in out:
        out["D_M_star_Mpc"] = float(dm) * float(pred_raw["D_M_star_Mpc"])
    if "r_s_star_Mpc" in out:
        out["r_s_star_Mpc"] = float(rs) * float(pred_raw["r_s_star_Mpc"])
    return out


def joint_fit_dm_rs_star_calibration(
    *,
    ds: CMBPriorsDataset,
    pred_raw: Dict[str, float],
    rs_min: float,
    rs_max: float,
    rs_step: float,
    dm_min: float = 1e-6,
) -> Tuple[JointFitResult, List[Dict[str, float]]]:
    """Deterministic rs-grid + analytic dm optimum (quadratic) joint fit.

    Returns:
    - best-fit result
    - grid rows: [{"rs_star_calibration":..., "dm_star_calibration_opt":..., "chi2":...}, ...]
    """
    keys = ds.keys
    for req in ("R", "lA", "omega_b_h2"):
        if req not in keys:
            raise ValueError(f"Dataset is missing required key: {req!r}")
    if not (rs_min > 0 and rs_max > rs_min and rs_step > 0):
        raise ValueError("Require rs_min>0, rs_max>rs_min, rs_step>0")
    if not (dm_min > 0):
        raise ValueError("dm_min must be > 0")

    mean = np.asarray(ds.values, dtype=float)
    cov = _effective_cov(ds)
    W = np.linalg.inv(cov)

    iR = keys.index("R")
    ilA = keys.index("lA")
    iob = keys.index("omega_b_h2")

    R0 = float(pred_raw["R"])
    lA0 = float(pred_raw["lA"])
    ob_pred = float(pred_raw["omega_b_h2"])

    # b = mu - c, where c has omega_b prediction and zeros elsewhere.
    c = np.zeros_like(mean)
    c[iob] = ob_pred
    b = mean - c

    n = int(math.floor((float(rs_max) - float(rs_min)) / float(rs_step))) + 1
    if n < 2:
        raise ValueError("rs grid too small")

    grid_rows: List[Dict[str, float]] = []

    best_rs = float("nan")
    best_dm = float("nan")
    best_chi2 = float("inf")

    Wb = W @ b
    for i in range(int(n)):
        rs = float(rs_min) + float(i) * float(rs_step)
        if rs > float(rs_max) + 1e-15:
            break
        A = np.zeros_like(mean)
        A[iR] = R0
        A[ilA] = lA0 / float(rs)
        # A[iob] stays 0 (omega_b_h2 is independent of dm, rs).

        denom = float(A @ (W @ A))
        if not (denom > 0 and math.isfinite(denom)):
            raise ValueError("Non-positive A^T W A (covariance issue)")
        dm = float((A @ Wb) / denom)
        clamped = False
        if not (dm > 0 and math.isfinite(dm)):
            dm = float(dm_min)
            clamped = True
        if dm < float(dm_min):
            dm = float(dm_min)
            clamped = True

        y = float(dm) * A + c
        r = y - mean
        chi2 = float(r.T @ W @ r)
        if clamped:
            # Still record, but such points are not expected in normal runs.
            pass

        grid_rows.append(
            {
                "rs_star_calibration": float(rs),
                "dm_star_calibration_opt": float(dm),
                "chi2": float(chi2),
            }
        )
        if chi2 < best_chi2:
            best_chi2 = float(chi2)
            best_rs = float(rs)
            best_dm = float(dm)

    pred_fit = _apply_dm_rs_to_pred_raw(pred_raw=pred_raw, dm=float(best_dm), rs=float(best_rs))
    chi2_min = float(ds.chi2_from_values(pred_fit).chi2)

    # For "base" pulls/chi2 we record the raw (dm=1, rs=1) mapping; the caller can
    # choose a different baseline if desired.
    pred_base = _apply_dm_rs_to_pred_raw(pred_raw=pred_raw, dm=1.0, rs=1.0)
    chi2_base = float(ds.chi2_from_values(pred_base).chi2)

    pulls_base = _diag_pulls(keys=keys, mean=mean, cov=cov, pred=pred_base)
    pulls_fit = _diag_pulls(keys=keys, mean=mean, cov=cov, pred=pred_fit)

    bridge_z_used = float(pred_raw.get("bridge_z", float("nan")))
    is_degenerate = False
    # The degeneracy definition is model-specific; only used for gsc_transition.
    zt = pred_raw.get("z_transition")
    if zt is not None and math.isfinite(float(zt)) and math.isfinite(float(bridge_z_used)):
        if float(bridge_z_used) <= float(zt):
            is_degenerate = True

    return (
        JointFitResult(
            dm_star_calibration_fit=float(best_dm),
            rs_star_calibration_fit=float(best_rs),
            chi2_base=float(chi2_base),
            chi2_min=float(chi2_min),
            pulls_base=pulls_base,
            pulls_fit=pulls_fit,
            pred_raw=dict(pred_raw),
            pred_base=pred_base,
            pred_fit=pred_fit,
            bridge_z_used=float(bridge_z_used),
            is_degenerate=bool(is_degenerate),
        ),
        grid_rows,
    )


def _manifest_obj(
    *,
    cmb_csv: Path,
    cmb_cov: Path,
    model_cfg: Dict[str, Any],
    baseline_cfg: Dict[str, Any],
    fit_cfg: Dict[str, Any],
    result: JointFitResult,
    out_dir: Path,
    grid_csv: Path,
    plot_path: Path,
) -> Dict[str, Any]:
    return {
        "diagnostic_only": True,
        "kind": "cmb_e2_dm_rs_star_joint_fit_diagnostic",
        "cmb_e2_dm_rs_fit_applied": True,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"]),
        "git_branch": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "--abbrev-ref", "HEAD"]),
        "git_dirty": bool(_run_git(["git", "-C", str(REPO_ROOT), "status", "--porcelain=v1"])),
        "inputs": {
            "cmb_csv": _relpath(cmb_csv),
            "cmb_cov": _relpath(cmb_cov),
            "chw2018_csv_name": cmb_csv.name,
            "chw2018_cov_name": cmb_cov.name,
        },
        "model_config": model_cfg,
        "baseline_config": baseline_cfg,
        "fit_config": fit_cfg,
        "results": {
            "bridge_z_used": float(result.bridge_z_used),
            "is_degenerate": bool(result.is_degenerate),
            "chi2_base": float(result.chi2_base),
            "chi2_min": float(result.chi2_min),
            "dm_star_calibration_fit": float(result.dm_star_calibration_fit),
            "rs_star_calibration_fit": float(result.rs_star_calibration_fit),
            "pulls_base_diag": dict(result.pulls_base),
            "pulls_fit_diag": dict(result.pulls_fit),
        },
        "outputs": {
            "out_dir": _relpath(out_dir),
            "grid_csv": _relpath(grid_csv),
            "plot": _relpath(plot_path),
        },
        "notes": [
            "Diagnostic-only artifact: fits (dm_star_calibration, rs_star_calibration) against strict CHW2018 distance priors.",
            "By construction: R -> dm*R0, lA -> (dm/rs)*lA0, omega_b_h2 fixed.",
            "This is a 'what would it take' closure diagnostic, not a physics claim.",
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=("lcdm", "gsc_transition", "gsc_powerlaw"), default="gsc_transition")
    ap.add_argument(
        "--cmb",
        type=Path,
        default=V101_DIR / "data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv",
    )
    ap.add_argument(
        "--cmb-cov",
        type=Path,
        default=V101_DIR / "data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov",
    )
    ap.add_argument("--cmb-bridge-z", type=float, default=5.0)

    ap.add_argument("--H0", type=float, default=67.4)
    ap.add_argument("--Omega-m", dest="Omega_m", type=float, default=0.315)
    ap.add_argument("--Omega-L", dest="Omega_L", type=float, default=0.685)

    ap.add_argument("--gsc-p", type=float, default=0.6)
    ap.add_argument("--gsc-ztrans", type=float, default=1.8)

    ap.add_argument("--omega-b-h2", type=float, default=0.02237)
    ap.add_argument("--omega-c-h2", type=float, default=0.1200)
    ap.add_argument("--Neff", type=float, default=3.046)
    ap.add_argument("--Tcmb-K", type=float, default=2.7255)

    # Baseline for reporting (not for the fit algorithm).
    ap.add_argument(
        "--baseline-rs",
        type=float,
        default=float(_RS_STAR_CALIB_CHW2018),
        help="Baseline rs_star_calibration used for chi2_base reporting (default: CHW2018 stopgap).",
    )
    ap.add_argument("--baseline-dm", type=float, default=1.0)

    # Fit grid config.
    ap.add_argument("--rs-min", type=float, default=0.90)
    ap.add_argument("--rs-max", type=float, default=1.20)
    ap.add_argument("--rs-step", type=float, default=5e-4)

    ap.add_argument("--out-dir", type=Path, default=Path("v11.0.0/results/diagnostic_cmb_e2_dm_rs_star_fit"))
    ap.add_argument(
        "--paper-assets-dir",
        type=Path,
        default=Path("v11.0.0/paper_assets_cmb_e2_dm_rs_fit_diagnostic"),
    )
    ap.add_argument(
        "--zip-out",
        type=Path,
        default=Path("v11.0.0/paper_assets_cmb_e2_dm_rs_fit_diagnostic_r0.zip"),
    )
    args = ap.parse_args()

    ds = CMBPriorsDataset.from_csv(args.cmb, cov_path=args.cmb_cov, name="cmb_chw2018")

    pred_raw = _compute_pred_raw(
        model=str(args.model),
        H0_km_s_Mpc=float(args.H0),
        Omega_m=float(args.Omega_m),
        Omega_L=float(args.Omega_L),
        gsc_p=float(args.gsc_p),
        gsc_ztrans=float(args.gsc_ztrans),
        cmb_bridge_z=float(args.cmb_bridge_z),
        omega_b_h2=float(args.omega_b_h2),
        omega_c_h2=float(args.omega_c_h2),
        Neff=float(args.Neff),
        Tcmb_K=float(args.Tcmb_K),
    )

    # Compute a report baseline (does not affect the fit).
    if str(args.model) == "lcdm":
        pred_baseline = compute_lcdm_distance_priors(
            H0_km_s_Mpc=float(args.H0),
            Omega_m=float(args.Omega_m),
            omega_b_h2=float(args.omega_b_h2),
            omega_c_h2=float(args.omega_c_h2),
            N_eff=float(args.Neff),
            Tcmb_K=float(args.Tcmb_K),
            rs_star_calibration=float(args.baseline_rs),
            dm_star_calibration=float(args.baseline_dm),
        )
    else:
        H0_si = H0_to_SI(float(args.H0))
        if str(args.model) == "gsc_transition":
            hist = GSCTransitionHistory(
                H0=float(H0_si),
                Omega_m=float(args.Omega_m),
                Omega_Lambda=float(args.Omega_L),
                p=float(args.gsc_p),
                z_transition=float(args.gsc_ztrans),
            )
        else:
            hist = PowerLawHistory(H0=float(H0_si), p=float(args.gsc_p))
        pred_baseline = compute_bridged_distance_priors(
            model=hist,
            z_bridge=float(args.cmb_bridge_z),
            omega_b_h2=float(args.omega_b_h2),
            omega_c_h2=float(args.omega_c_h2),
            N_eff=float(args.Neff),
            Tcmb_K=float(args.Tcmb_K),
            rs_star_calibration=float(args.baseline_rs),
            dm_star_calibration=float(args.baseline_dm),
        )

    chi2_report_base = float(ds.chi2_from_values(pred_baseline).chi2)

    best, grid_rows = joint_fit_dm_rs_star_calibration(
        ds=ds,
        pred_raw=pred_raw,
        rs_min=float(args.rs_min),
        rs_max=float(args.rs_max),
        rs_step=float(args.rs_step),
    )

    # Recompute chi2_min relative to the reporting baseline? No: chi2_min is absolute for the fitted pred.
    chi2_min = float(ds.chi2_from_values(best.pred_fit).chi2)

    cov = _effective_cov(ds)
    mean = np.asarray(ds.values, dtype=float)
    pulls_report_base = _diag_pulls(keys=ds.keys, mean=mean, cov=cov, pred=pred_baseline)
    pulls_fit = _diag_pulls(keys=ds.keys, mean=mean, cov=cov, pred=best.pred_fit)

    out_dir = args.out_dir
    tables_dir = out_dir / "tables"
    figs_dir = out_dir / "figures"
    _ensure_dir(tables_dir)
    _ensure_dir(figs_dir)

    summary_path = out_dir / "cmb_e2_dm_rs_fit_summary.txt"
    grid_csv_path = tables_dir / "cmb_e2_dm_rs_fit_grid.csv"
    plot_path = figs_dir / "chi2_vs_rs_star_calibration.png"

    # Write grid CSV.
    with grid_csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(grid_rows[0].keys()))
        w.writeheader()
        for r in grid_rows:
            w.writerow(r)

    # Plot.
    xs = [float(r["rs_star_calibration"]) for r in grid_rows]
    ys = [float(r["chi2"]) for r in grid_rows]
    _make_plot(x=xs, y=ys, out_path=plot_path)

    # Summary.
    dm_pct = 100.0 * (float(best.dm_star_calibration_fit) - 1.0)
    rs_pct_vs_1 = 100.0 * (float(best.rs_star_calibration_fit) - 1.0)
    rs_pct_vs_base = 100.0 * (float(best.rs_star_calibration_fit) / float(args.baseline_rs) - 1.0)
    eff_H_boost_pct = 100.0 * (1.0 / float(best.dm_star_calibration_fit) - 1.0)

    lines: List[str] = []
    lines.append("E2.2 diagnostic: joint-fit (dm_star_calibration, rs_star_calibration) vs strict CHW2018 priors")
    lines.append("")
    lines.append("inputs:")
    lines.append(f"  cmb_csv={_relpath(args.cmb)}")
    lines.append(f"  cmb_cov={_relpath(args.cmb_cov)}")
    lines.append(f"  model={args.model}")
    if args.model != "lcdm":
        lines.append(f"  cmb_bridge_z_requested={float(args.cmb_bridge_z):g}")
        lines.append(f"  cmb_bridge_z_used={float(pred_baseline.get('bridge_z', float('nan'))):g}")
    lines.append("")
    lines.append("report baseline (for context; not part of the fit algorithm):")
    lines.append(f"  dm_star_calibration={float(args.baseline_dm):.16g}")
    lines.append(f"  rs_star_calibration={float(args.baseline_rs):.16g}")
    lines.append(f"  chi2_base={chi2_report_base:.12g}")
    for k in ds.keys:
        lines.append(f"  pull_base[{k}]={pulls_report_base.get(k, float('nan')):.6g}")
    lines.append("")
    lines.append("joint fit (deterministic rs-grid + analytic dm optimum):")
    lines.append(f"  rs_grid=[{float(args.rs_min):g}, {float(args.rs_max):g}] step={float(args.rs_step):g}")
    lines.append(f"  dm_star_calibration_fit={best.dm_star_calibration_fit:.16g}  ({dm_pct:+.3f}%)")
    lines.append(
        f"  rs_star_calibration_fit={best.rs_star_calibration_fit:.16g}  "
        f"({rs_pct_vs_1:+.3f}% vs 1.0, {rs_pct_vs_base:+.3f}% vs baseline)"
    )
    lines.append(f"  chi2_min={chi2_min:.12g}")
    for k in ds.keys:
        lines.append(f"  pull_fit[{k}]={pulls_fit.get(k, float('nan')):.6g}")
    lines.append("")
    lines.append("intuition:")
    lines.append(
        "  dm_star_calibration rescales D_M(z*) directly. "
        f"dm={best.dm_star_calibration_fit:.6g} corresponds to ~{eff_H_boost_pct:+.2f}% effective H-boost "
        "over the (bridge_z, z*) distance integral (very rough intuition)."
    )

    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[e2.2] wrote: {summary_path}")
    print(f"[e2.2] wrote: {grid_csv_path}")
    print(f"[e2.2] wrote: {plot_path}")

    # Paper-assets directory (ignored by git) + zip artifact.
    paper_dir = args.paper_assets_dir
    (paper_dir / "tables").mkdir(parents=True, exist_ok=True)
    (paper_dir / "figures").mkdir(parents=True, exist_ok=True)

    # Copy.
    (paper_dir / "tables" / "cmb_e2_dm_rs_fit_grid.csv").write_bytes(grid_csv_path.read_bytes())
    (paper_dir / "tables" / "cmb_e2_dm_rs_fit_summary.txt").write_bytes(summary_path.read_bytes())
    (paper_dir / "figures" / plot_path.name).write_bytes(plot_path.read_bytes())

    model_cfg = {
        "model": str(args.model),
        "H0_km_s_Mpc": float(args.H0),
        "Omega_m": float(args.Omega_m),
        "Omega_L": float(args.Omega_L),
        "gsc_p": float(args.gsc_p),
        "gsc_ztrans": float(args.gsc_ztrans),
        "cmb_bridge_z_requested": float(args.cmb_bridge_z),
        "bridge_z_used": float(pred_baseline.get("bridge_z", float("nan"))),
        "is_degenerate": bool(best.is_degenerate),
    }
    baseline_cfg = {
        "dm_star_calibration": float(args.baseline_dm),
        "rs_star_calibration": float(args.baseline_rs),
        "chi2_base": float(chi2_report_base),
    }
    fit_cfg = {
        "rs_grid": {"min": float(args.rs_min), "max": float(args.rs_max), "step": float(args.rs_step)},
        "dm_analytic_optimum": True,
        "dm_clamp_min": 1e-6,
    }

    manifest = _manifest_obj(
        cmb_csv=args.cmb,
        cmb_cov=args.cmb_cov,
        model_cfg=model_cfg,
        baseline_cfg=baseline_cfg,
        fit_cfg=fit_cfg,
        result=JointFitResult(
            dm_star_calibration_fit=float(best.dm_star_calibration_fit),
            rs_star_calibration_fit=float(best.rs_star_calibration_fit),
            chi2_base=float(chi2_report_base),
            chi2_min=float(chi2_min),
            pulls_base=dict(pulls_report_base),
            pulls_fit=dict(pulls_fit),
            pred_raw=dict(best.pred_raw),
            pred_base=dict(pred_baseline),
            pred_fit=dict(best.pred_fit),
            bridge_z_used=float(model_cfg["bridge_z_used"]),
            is_degenerate=bool(best.is_degenerate),
        ),
        out_dir=out_dir,
        grid_csv=grid_csv_path,
        plot_path=plot_path,
    )
    manifest_path = paper_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    zip_out = args.zip_out
    _zip_dir(dir_path=paper_dir, zip_path=zip_out)

    print(f"[e2.2] wrote: {manifest_path}")
    print(f"[e2.2] wrote: {zip_out}")


if __name__ == "__main__":
    main()

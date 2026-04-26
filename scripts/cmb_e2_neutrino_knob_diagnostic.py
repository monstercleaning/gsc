#!/usr/bin/env python3
"""E2.6 diagnostic: neutrino-sector knob (Delta N_eff) vs CMB distance-closure needs.

Purpose
-------
This module is *diagnostic-only* and explicitly out of submission scope.

It explores how varying an early-time radiation parameter (implemented as
Delta N_eff, i.e. N_eff = N_eff_base + Delta N_eff) changes:

- baseline CHW2018 distance-priors tension (chi2_base)
- the required diagnostic closure knobs (dm_star_calibration, rs_star_calibration)
  when jointly fitted against strict CHW2018 distance priors
- the implied effective constant-H boost mapping A (E2.3 interpretation), via:
    D_M(0->z_b) + D_M(z_b->z*)/A = dm_fit * D_M_raw(z*)

This is a "what would it take" tool. It must not be used as a physics claim.
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
        # Fallback: keep it portable by returning the basename.
        return str(path.name)


def _run_git(args: Sequence[str]) -> str:
    try:
        return subprocess.check_output(list(args), stderr=subprocess.STDOUT, text=True).strip()
    except Exception as e:  # pragma: no cover
        return f"<error: {e}>"


def _parse_csv_floats(arg: str) -> List[float]:
    out: List[float] = []
    for tok in str(arg).split(","):
        tok = tok.strip()
        if not tok:
            continue
        out.append(float(tok))
    if not out:
        raise ValueError("Empty CSV list")
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
        # Use the direct LCDM predictor for priors; this does not include the
        # D_M split metadata, which is optional for this diagnostic.
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
    raise ValueError(f"Unknown model: {model!r}")


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


@dataclass(frozen=True)
class FitRow:
    bridge_z_used: float
    delta_Neff: float
    Neff: float
    is_degenerate: bool

    chi2_base: float
    chi2_min: float
    dm_fit: float
    rs_fit: float

    A_required_const: Optional[float]

    R_base: float
    lA_base: float
    R_fit: float
    lA_fit: float

    pulls_base_R: float
    pulls_base_lA: float
    pulls_fit_R: float
    pulls_fit_lA: float

    D_M_0_to_bridge_Mpc: Optional[float]
    D_M_bridge_to_zstar_Mpc: Optional[float]


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

    pred_fit = _apply_dm_rs_to_pred_raw(pred_raw=pred_raw, dm=float(best_dm), rs=float(best_rs))
    chi2_min = float(ds.chi2_from_values(pred_fit).chi2)
    return float(best_dm), float(best_rs), float(chi2_min)


def _effective_const_A_from_dm(
    *,
    D_M_0_to_bridge_Mpc: float,
    D_M_bridge_to_zstar_Mpc: float,
    dm_star_calibration: float,
) -> Optional[float]:
    if not (D_M_0_to_bridge_Mpc >= 0 and math.isfinite(D_M_0_to_bridge_Mpc)):
        return None
    if not (D_M_bridge_to_zstar_Mpc > 0 and math.isfinite(D_M_bridge_to_zstar_Mpc)):
        return None
    if not (dm_star_calibration > 0 and math.isfinite(dm_star_calibration)):
        return None

    D_total = float(D_M_0_to_bridge_Mpc) + float(D_M_bridge_to_zstar_Mpc)
    D_target = float(dm_star_calibration) * float(D_total)
    denom = float(D_target) - float(D_M_0_to_bridge_Mpc)
    if not (denom > 0 and math.isfinite(denom)):
        return None
    A = float(D_M_bridge_to_zstar_Mpc) / float(denom)
    if not (A > 0 and math.isfinite(A)):
        return None
    return float(A)


def _plot_scan(*, rows: List[FitRow], out_png: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: E402

    # Group by bridge_z.
    by_bz: Dict[float, List[FitRow]] = {}
    for r in rows:
        by_bz.setdefault(float(r.bridge_z_used), []).append(r)
    for bz in by_bz:
        by_bz[bz] = sorted(by_bz[bz], key=lambda x: float(x.delta_Neff))

    fig, axes = plt.subplots(3, 1, figsize=(7.6, 8.8), constrained_layout=True, sharex=True)

    for bz, rr in sorted(by_bz.items()):
        xs = [float(r.delta_Neff) for r in rr]
        dm = [float(r.dm_fit) for r in rr]
        rs = [float(r.rs_fit) for r in rr]
        A = [float(r.A_required_const) for r in rr if r.A_required_const is not None]
        xs_A = [float(r.delta_Neff) for r in rr if r.A_required_const is not None]
        axes[0].plot(xs, dm, marker="o", linewidth=2.0, label=f"bridge_z={bz:g}")
        axes[1].plot(xs, rs, marker="o", linewidth=2.0, label=f"bridge_z={bz:g}")
        axes[2].plot(xs_A, A, marker="o", linewidth=2.0, label=f"bridge_z={bz:g}")

    axes[0].set_ylabel("dm_fit")
    axes[1].set_ylabel("rs_fit")
    axes[2].set_ylabel("A_required_const")
    axes[2].set_xlabel("Delta N_eff (relative to baseline)")

    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(frameon=False)

    axes[0].set_title("E2.6 diagnostic: Delta N_eff vs required closure knobs (dm, rs) and effective A mapping")
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=160)
    plt.close(fig)


def run(
    *,
    model: str,
    cmb_csv: Path,
    cmb_cov: Path,
    out_dir: Path,
    bridge_zs: Sequence[float],
    delta_neff_grid: Sequence[float],
    H0_km_s_Mpc: float,
    Omega_m: float,
    Omega_L: float,
    gsc_p: float,
    gsc_ztrans: float,
    omega_b_h2: float,
    omega_c_h2: float,
    Neff_base: float,
    Tcmb_K: float,
    baseline_rs: float,
    baseline_dm: float,
    rs_min: float,
    rs_max: float,
    rs_step: float,
) -> Dict[str, Any]:
    out_dir = out_dir.resolve()
    tables_dir = out_dir / "tables"
    figs_dir = out_dir / "figures"
    _ensure_dir(tables_dir)
    _ensure_dir(figs_dir)

    ds = CMBPriorsDataset.from_csv(cmb_csv, cov_path=cmb_cov, name="cmb_chw2018")
    cov = _effective_cov(ds)
    W = np.linalg.inv(cov)
    mean = np.asarray(ds.values, dtype=float)

    keys = ds.keys
    for req in ("R", "lA", "omega_b_h2"):
        if req not in keys:
            raise ValueError(f"Dataset is missing required key: {req!r}")
    iR = keys.index("R")
    ilA = keys.index("lA")

    rows: List[FitRow] = []
    for bz in bridge_zs:
        for dN in delta_neff_grid:
            Neff = float(Neff_base) + float(dN)
            if Neff < 0 or not math.isfinite(Neff):
                continue

            pred_raw = _compute_pred_raw(
                model=str(model),
                H0_km_s_Mpc=float(H0_km_s_Mpc),
                Omega_m=float(Omega_m),
                Omega_L=float(Omega_L),
                gsc_p=float(gsc_p),
                gsc_ztrans=float(gsc_ztrans),
                cmb_bridge_z=float(bz),
                omega_b_h2=float(omega_b_h2),
                omega_c_h2=float(omega_c_h2),
                Neff=float(Neff),
                Tcmb_K=float(Tcmb_K),
            )

            bridge_z_used = float(pred_raw.get("bridge_z", float(bz)))
            is_degenerate = False
            zt = pred_raw.get("z_transition")
            if zt is not None and math.isfinite(float(zt)) and math.isfinite(float(bridge_z_used)):
                if float(bridge_z_used) <= float(zt):
                    is_degenerate = True

            pred_base = _apply_dm_rs_to_pred_raw(pred_raw=pred_raw, dm=float(baseline_dm), rs=float(baseline_rs))
            chi2_base = float(ds.chi2_from_values(pred_base).chi2)

            dm_fit, rs_fit, chi2_min = _fit_dm_rs_against_chw2018(
                ds=ds,
                mean=mean,
                cov=cov,
                W=W,
                pred_raw=pred_raw,
                rs_min=float(rs_min),
                rs_max=float(rs_max),
                rs_step=float(rs_step),
            )
            pred_fit = _apply_dm_rs_to_pred_raw(pred_raw=pred_raw, dm=float(dm_fit), rs=float(rs_fit))

            pulls_base = _diag_pulls(keys=keys, mean=mean, cov=cov, pred=pred_base)
            pulls_fit = _diag_pulls(keys=keys, mean=mean, cov=cov, pred=pred_fit)

            D_low = pred_raw.get("D_M_0_to_bridge_Mpc")
            D_high = pred_raw.get("D_M_bridge_to_zstar_Mpc")
            A_req = None
            if D_low is not None and D_high is not None:
                A_req = _effective_const_A_from_dm(
                    D_M_0_to_bridge_Mpc=float(D_low),
                    D_M_bridge_to_zstar_Mpc=float(D_high),
                    dm_star_calibration=float(dm_fit),
                )

            rows.append(
                FitRow(
                    bridge_z_used=float(bridge_z_used),
                    delta_Neff=float(dN),
                    Neff=float(Neff),
                    is_degenerate=bool(is_degenerate),
                    chi2_base=float(chi2_base),
                    chi2_min=float(chi2_min),
                    dm_fit=float(dm_fit),
                    rs_fit=float(rs_fit),
                    A_required_const=A_req,
                    R_base=float(pred_base["R"]),
                    lA_base=float(pred_base["lA"]),
                    R_fit=float(pred_fit["R"]),
                    lA_fit=float(pred_fit["lA"]),
                    pulls_base_R=float(pulls_base["R"]),
                    pulls_base_lA=float(pulls_base["lA"]),
                    pulls_fit_R=float(pulls_fit["R"]),
                    pulls_fit_lA=float(pulls_fit["lA"]),
                    D_M_0_to_bridge_Mpc=float(D_low) if D_low is not None else None,
                    D_M_bridge_to_zstar_Mpc=float(D_high) if D_high is not None else None,
                )
            )

    csv_path = tables_dir / "cmb_e2_neutrino_knob_scan.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "model",
            "gsc_p",
            "gsc_ztrans",
            "bridge_z_used",
            "delta_Neff",
            "Neff",
            "is_degenerate",
            "chi2_base",
            "chi2_min",
            "dm_fit",
            "rs_fit",
            "A_required_const",
            "R_base",
            "lA_base",
            "R_fit",
            "lA_fit",
            "pulls_base_R",
            "pulls_base_lA",
            "pulls_fit_R",
            "pulls_fit_lA",
            "D_M_0_to_bridge_Mpc",
            "D_M_bridge_to_zstar_Mpc",
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(
                {
                    "model": str(model),
                    "gsc_p": f"{float(gsc_p):.16g}",
                    "gsc_ztrans": f"{float(gsc_ztrans):.16g}",
                    "bridge_z_used": f"{float(r.bridge_z_used):.16g}",
                    "delta_Neff": f"{float(r.delta_Neff):.16g}",
                    "Neff": f"{float(r.Neff):.16g}",
                    "is_degenerate": str(bool(r.is_degenerate)),
                    "chi2_base": f"{float(r.chi2_base):.16g}",
                    "chi2_min": f"{float(r.chi2_min):.16g}",
                    "dm_fit": f"{float(r.dm_fit):.16g}",
                    "rs_fit": f"{float(r.rs_fit):.16g}",
                    "A_required_const": "" if r.A_required_const is None else f"{float(r.A_required_const):.16g}",
                    "R_base": f"{float(r.R_base):.16g}",
                    "lA_base": f"{float(r.lA_base):.16g}",
                    "R_fit": f"{float(r.R_fit):.16g}",
                    "lA_fit": f"{float(r.lA_fit):.16g}",
                    "pulls_base_R": f"{float(r.pulls_base_R):.16g}",
                    "pulls_base_lA": f"{float(r.pulls_base_lA):.16g}",
                    "pulls_fit_R": f"{float(r.pulls_fit_R):.16g}",
                    "pulls_fit_lA": f"{float(r.pulls_fit_lA):.16g}",
                    "D_M_0_to_bridge_Mpc": "" if r.D_M_0_to_bridge_Mpc is None else f"{float(r.D_M_0_to_bridge_Mpc):.16g}",
                    "D_M_bridge_to_zstar_Mpc": "" if r.D_M_bridge_to_zstar_Mpc is None else f"{float(r.D_M_bridge_to_zstar_Mpc):.16g}",
                }
            )

    fig_path = figs_dir / "neutrino_knob_dm_rs_A_vs_delta_neff.png"
    _plot_scan(rows=rows, out_png=fig_path)

    # Summary stats (skip degenerate points).
    nd = [r for r in rows if not r.is_degenerate]
    A_vals = [float(r.A_required_const) for r in nd if r.A_required_const is not None and math.isfinite(float(r.A_required_const))]
    dm_vals = [float(r.dm_fit) for r in nd]

    manifest: Dict[str, Any] = {
        "diagnostic_only": True,
        "kind": "cmb_e2_neutrino_knob_diagnostic",
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"]),
        "git_branch": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "--abbrev-ref", "HEAD"]),
        "git_dirty": bool(_run_git(["git", "-C", str(REPO_ROOT), "status", "--porcelain=v1"]).strip()),
        "inputs": {
            "cmb_csv": _relpath(Path(cmb_csv)),
            "cmb_cov": _relpath(Path(cmb_cov)),
            "chw2018_csv_name": Path(cmb_csv).name,
            "chw2018_cov_name": Path(cmb_cov).name,
        },
        "config": {
            "model": str(model),
            "late_time": {
                "H0_km_s_Mpc": float(H0_km_s_Mpc),
                "Omega_m": float(Omega_m),
                "Omega_L": float(Omega_L),
                "gsc_p": float(gsc_p),
                "gsc_ztrans": float(gsc_ztrans),
            },
            "early_time": {
                "omega_b_h2": float(omega_b_h2),
                "omega_c_h2": float(omega_c_h2),
                "Tcmb_K": float(Tcmb_K),
                "Neff_base": float(Neff_base),
                "delta_neff_grid": [float(x) for x in delta_neff_grid],
            },
            "bridge_zs": [float(x) for x in bridge_zs],
            "baseline_reporting": {"dm": float(baseline_dm), "rs": float(baseline_rs)},
            "fit_grid": {"rs_min": float(rs_min), "rs_max": float(rs_max), "rs_step": float(rs_step)},
        },
        "summary": {
            "num_rows": int(len(rows)),
            "num_rows_non_degenerate": int(len(nd)),
            "dm_fit_range_nondeg": (
                [float(min(dm_vals)), float(max(dm_vals))] if dm_vals else None
            ),
            "A_required_const_range_nondeg": (
                [float(min(A_vals)), float(max(A_vals))] if A_vals else None
            ),
        },
        "outputs": {
            "out_dir": _relpath(out_dir),
            "csv": _relpath(csv_path),
            "figure": _relpath(fig_path),
        },
        "notes": [
            "Diagnostic-only: explores a neutrino-sector knob implemented as Delta N_eff (radiation density).",
            "Per point, jointly fits (dm_star_calibration, rs_star_calibration) vs strict CHW2018 distance priors.",
            "The effective constant-A mapping is an interpretation of dm_fit (not a physical claim).",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return manifest


def main(argv: Optional[Sequence[str]] = None) -> None:
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

    ap.add_argument("--outdir", type=Path, default=Path("v11.0.0/results/diagnostic_cmb_e2_neutrino_knob"))

    ap.add_argument("--bridge-zs", type=str, default="5,10", help="CSV list of bridge_z_used values.")
    ap.add_argument(
        "--delta-neff-grid",
        type=str,
        default="-1.0,-0.5,0.0,0.5,1.0",
        help="CSV list of Delta N_eff values (added to Neff_base).",
    )

    ap.add_argument("--H0", type=float, default=67.4)
    ap.add_argument("--Omega-m", dest="Omega_m", type=float, default=0.315)
    ap.add_argument("--Omega-L", dest="Omega_L", type=float, default=0.685)
    ap.add_argument("--gsc-p", type=float, default=0.6)
    ap.add_argument("--gsc-ztrans", type=float, default=1.8)

    ap.add_argument("--omega-b-h2", type=float, default=0.02237)
    ap.add_argument("--omega-c-h2", type=float, default=0.1200)
    ap.add_argument("--Neff-base", type=float, default=3.046)
    ap.add_argument("--Tcmb-K", type=float, default=2.7255)

    ap.add_argument(
        "--baseline-rs",
        type=float,
        default=float(_RS_STAR_CALIB_CHW2018),
        help="Baseline rs_star_calibration for chi2_base reporting (default: CHW2018 stopgap).",
    )
    ap.add_argument("--baseline-dm", type=float, default=1.0)

    ap.add_argument("--rs-min", type=float, default=0.90)
    ap.add_argument("--rs-max", type=float, default=1.20)
    ap.add_argument("--rs-step", type=float, default=5e-4)

    args = ap.parse_args(argv)

    run(
        model=str(args.model),
        cmb_csv=Path(args.cmb),
        cmb_cov=Path(args.cmb_cov),
        out_dir=Path(args.outdir),
        bridge_zs=_parse_csv_floats(str(args.bridge_zs)),
        delta_neff_grid=_parse_csv_floats(str(args.delta_neff_grid)),
        H0_km_s_Mpc=float(args.H0),
        Omega_m=float(args.Omega_m),
        Omega_L=float(args.Omega_L),
        gsc_p=float(args.gsc_p),
        gsc_ztrans=float(args.gsc_ztrans),
        omega_b_h2=float(args.omega_b_h2),
        omega_c_h2=float(args.omega_c_h2),
        Neff_base=float(args.Neff_base),
        Tcmb_K=float(args.Tcmb_K),
        baseline_rs=float(args.baseline_rs),
        baseline_dm=float(args.baseline_dm),
        rs_min=float(args.rs_min),
        rs_max=float(args.rs_max),
        rs_step=float(args.rs_step),
    )


if __name__ == "__main__":  # pragma: no cover
    main()


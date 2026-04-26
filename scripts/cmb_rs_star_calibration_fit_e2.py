#!/usr/bin/env python3
"""E2.0 diagnostic: 1D r_s(z*) calibration fit against CHW2018 distance priors.

Goal
----
Quantify how much *early-time correction* (in the simplest form: a multiplicative
rescaling of r_s(z*)) is required to reconcile a non-degenerate bridge prediction
with strict CHW2018 compressed CMB distance priors.

This script is diagnostic-only:
- It does NOT modify the canonical late-time or submission pipeline.
- It fits an *additional* multiplicative factor `rs_star_calibration_fit` that
  affects only l_A via r_s(z*) scaling:

    r_s(z*) -> k * r_s(z*)   ==>   l_A -> l_A / k

R and omega_b_h2 are left unchanged by construction.
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Dict, Optional, Tuple


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


def _effective_cov(ds: CMBPriorsDataset) -> np.ndarray:
    if ds.cov is None:
        raise ValueError("CMB covariance is required for rs* calibration fit (strict CHW2018 mode).")
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


@dataclass(frozen=True)
class RsStarFitResult:
    rs_star_calibration_base: float
    rs_star_calibration_fit: float
    rs_star_calibration_total: float

    chi2_base: float
    chi2_min: float

    k_bounds_initial: Tuple[float, float]
    k_bounds_final: Tuple[float, float]
    was_clamped: bool

    pulls_base: Dict[str, float]
    pulls_fit: Dict[str, float]

    pred_base: Dict[str, float]
    pred_fit: Dict[str, float]


def fit_rs_star_calibration_multiplier(
    *,
    ds: CMBPriorsDataset,
    pred_base: Dict[str, float],
    rs_star_calibration_base: float,
    k_min: float = 0.8,
    k_max: float = 1.3,
    expand_factor: float = 1.25,
    max_expands: int = 8,
) -> RsStarFitResult:
    """Fit k such that lA -> lA/k minimizes chi2 under the dataset covariance.

    The minimization is analytic because only one element (lA) is rescaled.
    Bounds are applied in k-space with optional auto-expansion if the optimum
    sits outside the initial interval.
    """
    if not (k_min > 0 and k_max > k_min):
        raise ValueError("Require 0 < k_min < k_max")
    if not (expand_factor > 1.0):
        raise ValueError("expand_factor must be > 1")
    if max_expands < 0:
        raise ValueError("max_expands must be >= 0")

    keys = ds.keys
    if "lA" not in keys:
        raise ValueError("CMB priors vector must contain 'lA' for rs* calibration fit.")
    if any(k not in pred_base for k in keys):
        missing = [k for k in keys if k not in pred_base]
        raise ValueError(f"Missing predicted values for keys: {missing}")

    mean = np.asarray(ds.values, dtype=float)
    cov = _effective_cov(ds)
    W = np.linalg.inv(cov)

    i_lA = keys.index("lA")
    y0 = np.asarray([float(pred_base[k]) for k in keys], dtype=float)

    # y(q) is the same as y0 except lA -> q*lA0, where q = 1/k.
    lA0 = float(y0[i_lA])
    if not (math.isfinite(lA0) and lA0 != 0.0):
        raise ValueError("Non-finite or zero lA in prediction; cannot fit rs* calibration.")

    y_other = y0.copy()
    y_other[i_lA] = 0.0
    r_other = y_other - mean

    Wii = float(W[i_lA, i_lA])
    if not (Wii > 0.0 and math.isfinite(Wii)):
        raise ValueError("Invalid covariance inverse (W_ii <= 0) for lA element.")

    # Quadratic chi2(q) = a q^2 + b q + c, where only the lA component depends on q.
    a = (lA0 * lA0) * Wii
    b = 2.0 * lA0 * float(W[i_lA, :] @ r_other)
    # c not needed for optimum; computed via chi2 evaluation below.

    q_star = -b / (2.0 * a)
    k_star = 1.0 / q_star if (math.isfinite(q_star) and q_star != 0.0) else float("nan")

    # Bounds + optional auto-expansion.
    k_lo = float(k_min)
    k_hi = float(k_max)
    for _ in range(int(max_expands)):
        if not (math.isfinite(k_star) and k_star > 0.0):
            break
        if k_star < k_lo:
            k_lo /= float(expand_factor)
            continue
        if k_star > k_hi:
            k_hi *= float(expand_factor)
            continue
        break

    # Clamp if needed (also clamps pathological q_star <= 0 cases).
    was_clamped = False
    if not (math.isfinite(k_star) and k_star > 0.0):
        # Fall back to the initial interval center if the analytic optimum is non-physical.
        k_fit = 0.5 * (float(k_lo) + float(k_hi))
        was_clamped = True
    else:
        if k_star < k_lo:
            was_clamped = True
        if k_star > k_hi:
            was_clamped = True
        k_fit = float(min(max(k_star, k_lo), k_hi))

    pred_fit = dict(pred_base)
    pred_fit["rs_star_calibration_base"] = float(rs_star_calibration_base)
    pred_fit["rs_star_calibration_fit"] = float(k_fit)
    pred_fit["rs_star_calibration_total"] = float(rs_star_calibration_base) * float(k_fit)

    # Apply r_s(z*) scaling consistently to bridge-level diagnostic fields (not just lA).
    pred_fit["lA"] = float(pred_base["lA"]) / float(k_fit)
    if "theta_star" in pred_fit:
        pred_fit["theta_star"] = float(pred_base["theta_star"]) * float(k_fit)
    if "r_s_star_Mpc" in pred_fit:
        pred_fit["r_s_star_Mpc"] = float(pred_base["r_s_star_Mpc"]) * float(k_fit)

    chi2_base = float(ds.chi2_from_values(pred_base).chi2)
    chi2_fit = float(ds.chi2_from_values(pred_fit).chi2)

    pulls_base = _diag_pulls(keys=keys, mean=mean, cov=cov, pred=pred_base)
    pulls_fit = _diag_pulls(keys=keys, mean=mean, cov=cov, pred=pred_fit)

    return RsStarFitResult(
        rs_star_calibration_base=float(rs_star_calibration_base),
        rs_star_calibration_fit=float(k_fit),
        rs_star_calibration_total=float(rs_star_calibration_base) * float(k_fit),
        chi2_base=float(chi2_base),
        chi2_min=float(chi2_fit),
        k_bounds_initial=(float(k_min), float(k_max)),
        k_bounds_final=(float(k_lo), float(k_hi)),
        was_clamped=bool(was_clamped),
        pulls_base=pulls_base,
        pulls_fit=pulls_fit,
        pred_base=dict(pred_base),
        pred_fit=dict(pred_fit),
    )


def _write_csv_row(path: Path, *, row: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if write_header:
            w.writeheader()
        w.writerow(row)


def _relpath(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except Exception:
        return str(path)


def _compute_pred(
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
    rs_star_calibration_base: float,
) -> Dict[str, float]:
    if model == "lcdm":
        return compute_lcdm_distance_priors(
            H0_km_s_Mpc=float(H0_km_s_Mpc),
            Omega_m=float(Omega_m),
            omega_b_h2=float(omega_b_h2),
            omega_c_h2=float(omega_c_h2),
            N_eff=float(Neff),
            Tcmb_K=float(Tcmb_K),
            rs_star_calibration=float(rs_star_calibration_base),
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
        return compute_bridged_distance_priors(
            model=hist,
            z_bridge=float(cmb_bridge_z),
            omega_b_h2=float(omega_b_h2),
            omega_c_h2=float(omega_c_h2),
            N_eff=float(Neff),
            Tcmb_K=float(Tcmb_K),
            rs_star_calibration=float(rs_star_calibration_base),
        )
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
            rs_star_calibration=float(rs_star_calibration_base),
        )
    raise ValueError(f"Unknown model: {model}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=("lcdm", "gsc_transition", "gsc_powerlaw"), required=True)

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
    ap.add_argument(
        "--cmb-bridge-z",
        type=float,
        default=5.0,
        help="Bridge stitch redshift (diagnostic knob; used for non-LCDM models).",
    )

    ap.add_argument("--H0", type=float, default=67.4)
    ap.add_argument("--Omega-m", dest="Omega_m", type=float, default=0.315)
    ap.add_argument("--Omega-L", dest="Omega_L", type=float, default=0.685)

    ap.add_argument("--gsc-p", type=float, default=0.6)
    ap.add_argument("--gsc-ztrans", type=float, default=1.8)

    ap.add_argument("--omega-b-h2", type=float, default=0.02237)
    ap.add_argument("--omega-c-h2", type=float, default=0.1200)
    ap.add_argument("--Neff", type=float, default=3.046)
    ap.add_argument("--Tcmb-K", type=float, default=2.7255)

    ap.add_argument("--fit-k-min", type=float, default=0.8)
    ap.add_argument("--fit-k-max", type=float, default=1.3)
    ap.add_argument("--fit-expand-factor", type=float, default=1.25)
    ap.add_argument("--fit-max-expands", type=int, default=8)

    ap.add_argument("--raw", action="store_true", help="Disable the CHW2018 stopgap r_s(z*) calibration.")
    ap.add_argument("--out-csv", type=Path, default=None, help="Optional: append a one-line CSV record.")

    args = ap.parse_args()

    ds = CMBPriorsDataset.from_csv(args.cmb, cov_path=args.cmb_cov, name="cmb_chw2018")

    rs_star_base = 1.0 if bool(args.raw) else float(_RS_STAR_CALIB_CHW2018)
    pred_base = _compute_pred(
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
        rs_star_calibration_base=float(rs_star_base),
    )

    res = fit_rs_star_calibration_multiplier(
        ds=ds,
        pred_base=pred_base,
        rs_star_calibration_base=float(rs_star_base),
        k_min=float(args.fit_k_min),
        k_max=float(args.fit_k_max),
        expand_factor=float(args.fit_expand_factor),
        max_expands=int(args.fit_max_expands),
    )

    bridge_z_used = float(pred_base.get("bridge_z", float("nan")))
    is_degenerate = False
    if str(args.model) == "gsc_transition" and math.isfinite(bridge_z_used):
        if bridge_z_used <= float(args.gsc_ztrans):
            is_degenerate = True

    print("[e2.0] CHW2018 rs*(z*) calibration fit (diagnostic-only)")
    print(f"  model={args.model}")
    print(f"  cmb_csv={_relpath(args.cmb)}")
    print(f"  cmb_cov={_relpath(args.cmb_cov)}")
    if args.model != "lcdm":
        print(f"  cmb_bridge_z_requested={float(args.cmb_bridge_z):g}")
        print(f"  cmb_bridge_z_used={bridge_z_used:g}")
        if args.model == "gsc_transition":
            print(f"  is_degenerate={bool(is_degenerate)}  (degenerate iff bridge_z_used <= z_transition)")
    print("  params:")
    print(f"    H0={float(args.H0):.16g}")
    if args.model != "gsc_powerlaw":
        print(f"    Omega_m={float(args.Omega_m):.16g}")
        print(f"    Omega_L={float(args.Omega_L):.16g}")
    if args.model != "lcdm":
        print(f"    gsc_p={float(args.gsc_p):.16g}")
        if args.model == "gsc_transition":
            print(f"    gsc_ztrans={float(args.gsc_ztrans):.16g}")
    print(f"    omega_b_h2={float(args.omega_b_h2):.16g}")
    print(f"    omega_c_h2={float(args.omega_c_h2):.16g}")
    print(f"    Neff={float(args.Neff):.16g}")
    print(f"    Tcmb_K={float(args.Tcmb_K):.16g}")

    print("  baseline:")
    print(f"    rs_star_calibration_base={res.rs_star_calibration_base:.16g}  (raw={bool(args.raw)})")
    print(f"    chi2_cmb={res.chi2_base:.12g}")
    for k in ds.keys:
        print(f"    pull_base[{k}]={res.pulls_base.get(k, float('nan')):.6g}")

    print("  fit:")
    print(
        f"    rs_star_calibration_fit={res.rs_star_calibration_fit:.16g}  "
        f"(bounds_initial={res.k_bounds_initial[0]:g}..{res.k_bounds_initial[1]:g}, "
        f"bounds_final={res.k_bounds_final[0]:g}..{res.k_bounds_final[1]:g}, clamped={bool(res.was_clamped)})"
    )
    print(f"    rs_star_calibration_total={res.rs_star_calibration_total:.16g}")
    print(f"    chi2_cmb_min={res.chi2_min:.12g}")
    for k in ds.keys:
        print(f"    pull_fit[{k}]={res.pulls_fit.get(k, float('nan')):.6g}")

    if args.out_csv is not None:
        row: Dict[str, object] = {
            "model": str(args.model),
            "H0": float(args.H0),
            "Omega_m": float(args.Omega_m),
            "Omega_L": float(args.Omega_L),
            "gsc_p": float(args.gsc_p),
            "gsc_ztrans": float(args.gsc_ztrans),
            "cmb_bridge_z_requested": float(args.cmb_bridge_z),
            "cmb_bridge_z_used": float(bridge_z_used),
            "is_degenerate": bool(is_degenerate),
            "chi2_base": float(res.chi2_base),
            "chi2_min": float(res.chi2_min),
            "rs_star_calibration_base": float(res.rs_star_calibration_base),
            "rs_star_calibration_fit": float(res.rs_star_calibration_fit),
            "rs_star_calibration_total": float(res.rs_star_calibration_total),
            "fit_k_min_initial": float(res.k_bounds_initial[0]),
            "fit_k_max_initial": float(res.k_bounds_initial[1]),
            "fit_k_min_final": float(res.k_bounds_final[0]),
            "fit_k_max_final": float(res.k_bounds_final[1]),
            "fit_was_clamped": bool(res.was_clamped),
        }
        for k in ds.keys:
            row[f"pull_base_{k}"] = float(res.pulls_base.get(k, float("nan")))
        for k in ds.keys:
            row[f"pull_fit_{k}"] = float(res.pulls_fit.get(k, float("nan")))

        _write_csv_row(Path(args.out_csv), row=row)
        print(f"  wrote_csv={Path(args.out_csv)}")


if __name__ == "__main__":
    main()

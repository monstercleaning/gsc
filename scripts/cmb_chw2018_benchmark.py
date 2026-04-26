#!/usr/bin/env python3
"""One-command CHW2018 distance-priors benchmark (E1.1/E1.2).

Prints:
- z_star, r_s(z*), D_M(z*)
- (R, lA, omega_b_h2) prediction, pulls (diag), and chi2 (full cov)

This is intended for reviewer/QA checks and regression sanity.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import sys


# Allow running from repo root: add v11.0.0/ to import path.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.datasets.cmb_priors import CMBPriorsDataset  # noqa: E402
from gsc.early_time import compute_lcdm_distance_priors  # noqa: E402
from gsc.early_time.cmb_distance_priors import _RS_STAR_CALIB_CHW2018  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--raw",
        action="store_true",
        help="Disable the CHW2018 r_s(z*) stopgap calibration (prints the raw bridge-level predictor).",
    )
    args = ap.parse_args()

    try:
        import numpy as np  # type: ignore
    except Exception as e:
        raise SystemExit("numpy is required for this benchmark script") from e

    chw_csv = ROOT / "data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv"
    chw_cov = ROOT / "data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov"
    ds = CMBPriorsDataset.from_csv(chw_csv, cov_path=chw_cov, name="cmb_chw2018")

    # Planck-like benchmark (kept in sync with docs).
    H0 = 67.4
    Omega_m = 0.315
    omega_b_h2 = 0.02237
    omega_c_h2 = 0.1200
    Neff = 3.046
    Tcmb_K = 2.7255

    rs_star_calib = 1.0 if args.raw else float(_RS_STAR_CALIB_CHW2018)
    pred = compute_lcdm_distance_priors(
        H0_km_s_Mpc=H0,
        Omega_m=Omega_m,
        omega_b_h2=omega_b_h2,
        omega_c_h2=omega_c_h2,
        N_eff=Neff,
        Tcmb_K=Tcmb_K,
        rs_star_calibration=rs_star_calib,
    )

    r = ds.chi2_from_values(pred)

    keys = list(ds.keys)
    mean = np.asarray(ds.values, dtype=float)
    cov = np.asarray(ds.cov, dtype=float)
    pred_v = np.asarray([float(pred[k]) for k in keys], dtype=float)
    res = pred_v - mean
    sig = np.sqrt(np.diag(cov))
    pulls = res / sig

    print("CHW2018 CMB distance priors benchmark")
    print(f"  csv={chw_csv}")
    print(f"  cov={chw_cov}")
    print("params:")
    print(f"  H0_km_s_Mpc={H0}")
    print(f"  Omega_m={Omega_m}")
    print(f"  omega_b_h2={omega_b_h2}")
    print(f"  omega_c_h2={omega_c_h2}")
    print(f"  Neff={Neff}")
    print(f"  Tcmb_K={Tcmb_K}")
    print("predictor:")
    print(f"  rs_star_calibration={rs_star_calib:.16g}  (raw={bool(args.raw)})")
    print("pred:")
    for k in ("z_star", "r_s_star_Mpc", "D_M_star_Mpc", "theta_star", "lA", "R", "rd_Mpc"):
        if k in pred:
            print(f"  {k}={pred[k]:.16g}")
    print("priors:")
    for k, mu, p, pull in zip(keys, mean.tolist(), pred_v.tolist(), pulls.tolist()):
        print(f"  {k}: mean={mu:.16g}  pred={p:.16g}  pull(diag)={pull:.6g}")
    print(f"chi2_cmb={float(r.chi2):.12g}  ndof={int(r.ndof)}  method={r.meta.get('method')}")
    if not (math.isfinite(float(r.chi2)) and float(r.chi2) >= 0.0):
        raise SystemExit("chi2_cmb is non-finite or negative")


if __name__ == "__main__":
    main()


#!/usr/bin/env python3
"""E1.3 diagnostic: coarse scan over (p, z_transition) for selected bridge_z values.

This is intentionally a *diagnostic* tool:
- Computes CHW2018 compressed CMB chi2 (vector+cov) for gsc_transition via the E1.3 bridge.
- Checks the late-time "positive drift" guardrail: z_dot(z) > 0 on a small z-grid up to z=5.

It does NOT try to solve early-time physics; it quantifies sensitivity and potential tension.
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
import sys
from typing import Any, Dict, List, Tuple


V101_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V101_DIR))

import numpy as np  # noqa: E402

from gsc.datasets.cmb_priors import CMBPriorsDataset  # noqa: E402
from gsc.early_time import compute_bridged_distance_priors  # noqa: E402
from gsc.early_time import cmb_distance_priors as cmb_dp  # noqa: E402
from gsc.early_time.cmb_distance_priors import _RS_STAR_CALIB_CHW2018  # noqa: E402
from gsc.measurement_model import (  # noqa: E402
    GSCTransitionHistory,
    H0_to_SI,
    MPC_SI,
    z_dot_sandage_loeb,
)


def _parse_float_list(s: str) -> Tuple[float, ...]:
    out: List[float] = []
    for part in (s or "").split(","):
        part = part.strip()
        if not part:
            continue
        out.append(float(part))
    if not out:
        raise ValueError("empty float list")
    return tuple(out)


def _diag_pulls(*, keys: Tuple[str, ...], mean: np.ndarray, cov: np.ndarray, pred: Dict[str, float]) -> Dict[str, float]:
    diag = np.diag(cov)
    pulls: Dict[str, float] = {}
    for i, k in enumerate(keys):
        sigma = float(math.sqrt(float(diag[i])))
        pulls[k] = (float(pred[k]) - float(mean[i])) / sigma
    return pulls


def _drift_guardrail_positive(model, *, z_grid: Tuple[float, ...]) -> tuple[bool, float]:
    """Return (ok, min_z_dot) for z_dot(z) on z_grid."""
    H0 = float(model.H(0.0))

    def H_of_z(z: float) -> float:
        return float(model.H(z))

    z_dots = [float(z_dot_sandage_loeb(z=float(z), H0=H0, H_of_z=H_of_z)) for z in z_grid]
    ok = all((zd > 0.0 and math.isfinite(zd)) for zd in z_dots)
    return ok, float(min(z_dots)) if z_dots else float("nan")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True, help="Output CSV path.")

    ap.add_argument("--cmb", type=Path, required=True)
    ap.add_argument("--cmb-cov", type=Path, required=True)
    ap.add_argument("--bridge-z", type=str, default="2,5,10")

    ap.add_argument("--H0", type=float, default=67.4)
    ap.add_argument("--Omega-m", dest="Omega_m", type=float, default=0.315)
    ap.add_argument("--Omega-L", dest="Omega_L", type=float, default=0.685)

    ap.add_argument("--p-grid", type=str, default="0.55,0.6,0.65,0.7,0.8,0.9")
    ap.add_argument("--ztrans-grid", type=str, default="1.2,1.5,1.8,2.2,3.0")

    ap.add_argument("--omega-b-h2", type=float, default=0.02237)
    ap.add_argument("--omega-c-h2", type=float, default=0.1200)
    ap.add_argument("--Neff", type=float, default=3.046)
    ap.add_argument("--Tcmb-K", type=float, default=2.7255)

    args = ap.parse_args()

    out_path = args.out.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    bridge_zs = _parse_float_list(args.bridge_z)
    p_grid = _parse_float_list(args.p_grid)
    zt_grid = _parse_float_list(args.ztrans_grid)

    cmb_ds = CMBPriorsDataset.from_csv(args.cmb, cov_path=args.cmb_cov, name="cmb")
    cmb_keys = cmb_ds.keys
    cmb_mean = np.asarray(cmb_ds.values, dtype=float)
    cmb_cov = np.asarray(cmb_ds.cov, dtype=float) if cmb_ds.cov is not None else None
    if cmb_cov is None:
        raise SystemExit("CMB covariance missing (strict CHW2018 requires cov).")

    rs_star_calib = float(_RS_STAR_CALIB_CHW2018)
    rs_applied = bool(rs_star_calib != 1.0)

    # Drift sign guardrail grid (late-time scope).
    z_guard_grid = (0.5, 1.0, 2.0, 3.0, 4.0, 5.0)

    rows: List[Dict[str, Any]] = []
    best: tuple[float, Dict[str, Any]] | None = None

    H0_si = H0_to_SI(float(args.H0))
    for z_bridge in bridge_zs:
        for p in p_grid:
            for zt in zt_grid:
                model = GSCTransitionHistory(
                    H0=H0_si,
                    Omega_m=float(args.Omega_m),
                    Omega_Lambda=float(args.Omega_L),
                    p=float(p),
                    z_transition=float(zt),
                )
                drift_ok, min_z_dot = _drift_guardrail_positive(model, z_grid=z_guard_grid)
                pred = compute_bridged_distance_priors(
                    model=model,
                    z_bridge=float(z_bridge),
                    omega_b_h2=float(args.omega_b_h2),
                    omega_c_h2=float(args.omega_c_h2),
                    N_eff=float(args.Neff),
                    Tcmb_K=float(args.Tcmb_K),
                    rs_star_calibration=rs_star_calib,
                )
                r_cmb = cmb_ds.chi2_from_values(pred)
                pulls = _diag_pulls(keys=cmb_keys, mean=cmb_mean, cov=cmb_cov, pred=pred)

                bridge_z_used = float(pred.get("bridge_z", float("nan")))
                is_degenerate = bool(math.isfinite(bridge_z_used) and bridge_z_used <= float(zt))
                degenerate_reason = ""
                if is_degenerate:
                    degenerate_reason = (
                        "bridge_z_used <= z_transition: CMB D_M(z*) integral never enters the powerlaw segment; "
                        "CMB prediction is LCDM-only w.r.t gsc_transition(p,z_transition)."
                    )

                DM_0_to_bridge_Mpc = float(pred.get("D_M_0_to_bridge_Mpc", float("nan")))
                DM_bridge_to_zstar_Mpc = float(pred.get("D_M_bridge_to_zstar_Mpc", float("nan")))
                DM_total_Mpc = float(pred.get("D_M_star_Mpc", float("nan")))

                frac_DM_non_lcdm = float("nan")
                if math.isfinite(DM_total_Mpc) and DM_total_Mpc > 0.0:
                    if not is_degenerate and math.isfinite(DM_0_to_bridge_Mpc):
                        try:
                            D_M_0_to_ztrans_Mpc = float(
                                cmb_dp._comoving_distance_model_to_z_m(z=float(zt), model=model, n=4096)
                                / float(MPC_SI)
                            )
                        except Exception:
                            D_M_0_to_ztrans_Mpc = float("nan")
                        if math.isfinite(D_M_0_to_ztrans_Mpc):
                            DM_non_lcdm = max(0.0, DM_0_to_bridge_Mpc - D_M_0_to_ztrans_Mpc)
                        else:
                            DM_non_lcdm = 0.0
                    else:
                        DM_non_lcdm = 0.0
                    frac_DM_non_lcdm = float(DM_non_lcdm / DM_total_Mpc)

                row = {
                    "bridge_z": float(z_bridge),
                    "bridge_z_used": float(bridge_z_used),
                    "gsc_p": float(p),
                    "gsc_ztrans": float(zt),
                    "is_degenerate": bool(is_degenerate),
                    "degenerate_reason": str(degenerate_reason),
                    "chi2_cmb": float(r_cmb.chi2),
                    "ndof_cmb": int(r_cmb.ndof),
                    "pull_R": float(pulls.get("R", float("nan"))),
                    "pull_lA": float(pulls.get("lA", float("nan"))),
                    "pull_omega_b_h2": float(pulls.get("omega_b_h2", float("nan"))),
                    "R_pred": float(pred.get("R", float("nan"))),
                    "lA_pred": float(pred.get("lA", float("nan"))),
                    "omega_b_h2_pred": float(pred.get("omega_b_h2", float("nan"))),
                    "DM_0_to_bridge_Mpc": float(DM_0_to_bridge_Mpc),
                    "DM_bridge_to_zstar_Mpc": float(DM_bridge_to_zstar_Mpc),
                    "DM_total_Mpc": float(DM_total_Mpc),
                    "frac_DM_non_lcdm": float(frac_DM_non_lcdm),
                    "z_star": float(pred.get("z_star", float("nan"))),
                    "r_s_star_Mpc": float(pred.get("r_s_star_Mpc", float("nan"))),
                    "D_M_star_Mpc": float(pred.get("D_M_star_Mpc", float("nan"))),
                    "rs_star_calibration": rs_star_calib,
                    "rs_star_calibration_applied": bool(rs_applied),
                    "drift_guardrail_positive": bool(drift_ok),
                    "min_z_dot_SI": float(min_z_dot),
                }
                rows.append(row)

                if drift_ok and (not is_degenerate) and math.isfinite(float(r_cmb.chi2)):
                    if best is None or float(r_cmb.chi2) < best[0]:
                        best = (float(r_cmb.chi2), row)

    # Write CSV.
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)

    if best is not None:
        chi, row = best
        print(
            f"[e1.3 pzt] best (drift-positive) chi2_cmb={chi:.6g} at bridge_z={row['bridge_z']} p={row['gsc_p']} zt={row['gsc_ztrans']}"
        )
    print(f"[e1.3 pzt] wrote: {out_path}")


if __name__ == "__main__":
    main()

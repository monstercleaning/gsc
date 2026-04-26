#!/usr/bin/env python3
"""
Diagnostic helper: comoving-distance budget to recombination.

Purpose:
- Provide a quantitative breakdown of D_M(z*) contributions by redshift interval.
- Compare a bridged non-LCDM late-time history (E1-style) against an early-time LCDM+rad baseline.
- Localize where ΔD_M(z*) accumulates (e.g. why E1.3 becomes catastrophic for bridge_z >= 5).

Outputs (diagnostic-only; not part of canonical paper assets):
- v11.0.0/results/diagnostic_cmb_distance_budget/*.csv
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


def _repo_root() -> Path:
    # .../v11.0.0/scripts/ -> repo root
    return Path(__file__).resolve().parents[2]


def _require_numpy():
    try:
        import numpy as np  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("numpy is required for this diagnostic script.") from e
    return np


def _np_trapezoid(np, y, x) -> float:
    trap = getattr(np, "trapezoid", None)
    if callable(trap):
        return float(trap(y, x))
    trapz = getattr(np, "trapz", None)
    if callable(trapz):
        return float(trapz(y, x))
    y_arr = np.asarray(y, dtype=float)
    x_arr = np.asarray(x, dtype=float)
    if y_arr.shape != x_arr.shape:
        raise ValueError("trapezoid fallback requires x and y with matching shape")
    if int(y_arr.size) < 2:
        return 0.0
    return float(0.5 * np.sum((y_arr[1:] + y_arr[:-1]) * (x_arr[1:] - x_arr[:-1])))


def _mpc_from_m(x_m: float) -> float:
    # Local import to avoid circularity in help/argparse mode.
    from gsc.measurement_model import MPC_SI

    return float(x_m) / float(MPC_SI)


def _H0_to_SI(H0_km_s_Mpc: float) -> float:
    from gsc.measurement_model import H0_to_SI

    return float(H0_to_SI(float(H0_km_s_Mpc)))


def _z_star_default(*, omega_b_h2: float, omega_c_h2: float) -> float:
    from gsc.early_time.cmb_distance_priors import z_star_hu_sugiyama

    omega_m_h2 = float(omega_b_h2) + float(omega_c_h2)
    return float(z_star_hu_sugiyama(omega_b_h2=float(omega_b_h2), omega_m_h2=float(omega_m_h2)))


def _omega_r_h2(*, Tcmb_K: float, N_eff: float) -> float:
    from gsc.early_time.rd import omega_r_h2

    return float(omega_r_h2(Tcmb_K=float(Tcmb_K), N_eff=float(N_eff)))


def _early_time_Ez(
    z,
    *,
    Omega_m: float,
    Omega_r: float,
    Omega_lambda: float,
):
    return (Omega_r * (1.0 + z) ** 4 + Omega_m * (1.0 + z) ** 3 + Omega_lambda) ** 0.5


def _comoving_distance_interval_m(
    *,
    z0: float,
    z1: float,
    H_of_z: Callable[[float], float],
    n: int,
) -> float:
    if not (0.0 <= z0 <= z1 and math.isfinite(z0) and math.isfinite(z1)):
        raise ValueError("Require finite 0 <= z0 <= z1")
    if z0 == z1:
        return 0.0
    if n < 256:
        raise ValueError("n too small for diagnostic integration")

    from gsc.measurement_model import C_SI

    np = _require_numpy()
    zz = np.linspace(float(z0), float(z1), int(n), dtype=float)
    Hz = np.asarray([float(H_of_z(float(z))) for z in zz], dtype=float)
    if not (np.isfinite(Hz).all() and float(Hz.min()) > 0.0):
        raise ValueError("H(z) must be finite and strictly positive on the interval")
    integral = _np_trapezoid(np, 1.0 / Hz, zz)
    return float(C_SI) * integral


def _comoving_distance_interval_early_m(
    *,
    z0: float,
    z1: float,
    H0_si: float,
    Omega_m: float,
    Omega_r: float,
    Omega_lambda: float,
    n: int,
) -> float:
    if z0 == z1:
        return 0.0
    np = _require_numpy()
    from gsc.measurement_model import C_SI

    zz = np.linspace(float(z0), float(z1), int(n), dtype=float)
    Ez = _early_time_Ez(zz, Omega_m=float(Omega_m), Omega_r=float(Omega_r), Omega_lambda=float(Omega_lambda))
    Hz = float(H0_si) * Ez
    integral = _np_trapezoid(np, 1.0 / Hz, zz)
    return float(C_SI) * integral


@dataclass(frozen=True)
class BudgetRow:
    interval: str
    z0: float
    z1: float
    D_baseline_Mpc: float
    D_model_Mpc: float
    delta_Mpc: float
    delta_pct: float
    frac_baseline: float
    frac_model: float


def _make_late_time_model(args) -> object:
    from gsc.measurement_model import FlatLambdaCDMHistory, GSCTransitionHistory, H0_to_SI, PowerLawHistory

    H0_si = float(H0_to_SI(float(args.H0)))
    model = str(args.model).strip().lower()
    if model == "lcdm":
        return FlatLambdaCDMHistory(H0=H0_si, Omega_m=float(args.Omega_m), Omega_Lambda=float(args.Omega_L))
    if model == "gsc_powerlaw":
        return PowerLawHistory(H0=H0_si, p=float(args.p))
    if model == "gsc_transition":
        return GSCTransitionHistory(
            H0=H0_si,
            Omega_m=float(args.Omega_m),
            Omega_Lambda=float(args.Omega_L),
            p=float(args.p),
            z_transition=float(args.z_transition),
        )
    raise ValueError(f"Unsupported model: {args.model!r}")


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="cmb_distance_budget_diagnostic",
        description="Break down D_M(z*) by redshift interval and compare LCDM+rad baseline vs bridged late-time model (E1-style).",
    )
    ap.add_argument("--model", choices=["lcdm", "gsc_powerlaw", "gsc_transition"], required=True)

    ap.add_argument("--H0", type=float, default=67.4, help="H0 in km/s/Mpc (default: 67.4)")
    ap.add_argument("--Omega-m", dest="Omega_m", type=float, default=0.315, help="Omega_m (late-time) (default: 0.315)")
    ap.add_argument("--Omega-L", dest="Omega_L", type=float, default=0.685, help="Omega_Lambda (late-time) (default: 0.685)")
    ap.add_argument("--p", type=float, default=0.6, help="GSC p parameter (default: 0.6)")
    ap.add_argument("--z-transition", type=float, default=1.8, help="GSC transition redshift (default: 1.8)")

    ap.add_argument("--bridge-z", type=float, default=5.0, help="E1-style bridge stitch redshift (default: 5)")

    ap.add_argument("--omega-b-h2", type=float, default=0.02237, help="omega_b h^2 (default: 0.02237)")
    ap.add_argument("--omega-c-h2", type=float, default=0.1200, help="omega_c h^2 (default: 0.1200)")
    ap.add_argument("--N-eff", type=float, default=3.046, help="N_eff (default: 3.046)")
    ap.add_argument("--Tcmb-K", type=float, default=2.7255, help="Tcmb (K) (default: 2.7255)")
    ap.add_argument("--z-star", type=float, default=None, help="Override z* (default: Hu-Sugiyama fit)")

    ap.add_argument("--n", type=int, default=8192, help="Integration grid per interval (default: 8192)")
    ap.add_argument(
        "--out-dir",
        default="v11.0.0/results/diagnostic_cmb_distance_budget",
        help="Output directory (default: v11.0.0/results/diagnostic_cmb_distance_budget)",
    )
    args = ap.parse_args()

    # Make sure imports work when running from repo root.
    import sys

    v101 = _repo_root() / "v11.0.0"
    sys.path.insert(0, str(v101))

    if not (args.H0 > 0 and math.isfinite(args.H0)):
        raise SystemExit("ERROR: H0 must be positive and finite")

    # Early-time baseline densities derived from (omega_x h^2, H0).
    h = float(args.H0) / 100.0
    omega_m_h2 = float(args.omega_b_h2) + float(args.omega_c_h2)
    Omega_m_early = float(omega_m_h2) / (h * h)
    Omega_r = float(_omega_r_h2(Tcmb_K=float(args.Tcmb_K), N_eff=float(args.N_eff))) / (h * h)
    Omega_lambda_early = 1.0 - float(Omega_m_early) - float(Omega_r)
    if Omega_lambda_early <= 0.0:
        raise SystemExit("ERROR: derived Omega_lambda_early <= 0 (check inputs)")

    H0_si = float(_H0_to_SI(float(args.H0)))
    z_star = float(args.z_star) if args.z_star is not None else float(_z_star_default(omega_b_h2=float(args.omega_b_h2), omega_c_h2=float(args.omega_c_h2)))
    if not (z_star > 0 and math.isfinite(z_star)):
        raise SystemExit("ERROR: non-physical z_star")

    # Bridge clamp.
    z_b = float(min(float(args.bridge_z), float(z_star)))
    if not (z_b >= 0.0 and math.isfinite(z_b)):
        raise SystemExit("ERROR: bridge_z must be finite and >= 0")

    model = _make_late_time_model(args)

    # Fixed budget intervals (requested).
    intervals = [
        (0.0, 2.0),
        (2.0, 5.0),
        (5.0, 20.0),
        (20.0, z_star),
    ]

    # Baseline: early-time LCDM+rad on the full [0, z_star] (no stitch).
    baseline_contrib_m = []
    for (a, b) in intervals:
        a_use = float(max(0.0, a))
        b_use = float(min(float(b), float(z_star)))
        baseline_contrib_m.append(
            _comoving_distance_interval_early_m(
                z0=a_use,
                z1=b_use,
                H0_si=H0_si,
                Omega_m=Omega_m_early,
                Omega_r=Omega_r,
                Omega_lambda=Omega_lambda_early,
                n=int(args.n),
            )
        )
    baseline_total_m = float(sum(baseline_contrib_m))

    # Model (E1-style): model.H(z) for z <= z_b, then early-time LCDM+rad for z > z_b.
    def H_model(z: float) -> float:
        return float(model.H(float(z)))

    model_contrib_m = []
    for (a, b) in intervals:
        a_use = float(max(0.0, a))
        b_use = float(min(float(b), float(z_star)))
        if b_use <= z_b:
            d_m = _comoving_distance_interval_m(z0=a_use, z1=b_use, H_of_z=H_model, n=int(args.n))
        elif a_use >= z_b:
            d_m = _comoving_distance_interval_early_m(
                z0=a_use,
                z1=b_use,
                H0_si=H0_si,
                Omega_m=Omega_m_early,
                Omega_r=Omega_r,
                Omega_lambda=Omega_lambda_early,
                n=int(args.n),
            )
        else:
            d_m = _comoving_distance_interval_m(z0=a_use, z1=z_b, H_of_z=H_model, n=int(args.n)) + _comoving_distance_interval_early_m(
                z0=z_b,
                z1=b_use,
                H0_si=H0_si,
                Omega_m=Omega_m_early,
                Omega_r=Omega_r,
                Omega_lambda=Omega_lambda_early,
                n=int(args.n),
            )
        model_contrib_m.append(float(d_m))
    model_total_m = float(sum(model_contrib_m))

    rows: list[BudgetRow] = []
    for (a, b), db_m, dm_m in zip(intervals, baseline_contrib_m, model_contrib_m):
        label = f"[{a:g},{min(b, z_star):g}]"
        db = _mpc_from_m(db_m)
        dm = _mpc_from_m(dm_m)
        delta = float(dm - db)
        delta_pct = (100.0 * delta / db) if db != 0.0 else float("nan")
        rows.append(
            BudgetRow(
                interval=label,
                z0=float(a),
                z1=float(min(b, z_star)),
                D_baseline_Mpc=float(db),
                D_model_Mpc=float(dm),
                delta_Mpc=float(delta),
                delta_pct=float(delta_pct),
                frac_baseline=float(db_m / baseline_total_m) if baseline_total_m > 0 else float("nan"),
                frac_model=float(dm_m / model_total_m) if model_total_m > 0 else float("nan"),
            )
        )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / f"distance_budget_{args.model}_bridgez_{z_b:g}.csv"

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "interval",
                "z0",
                "z1",
                "D_baseline_Mpc",
                "D_model_Mpc",
                "delta_Mpc",
                "delta_pct",
                "frac_baseline",
                "frac_model",
            ]
        )
        for r in rows:
            w.writerow(
                [
                    r.interval,
                    f"{r.z0:.10g}",
                    f"{r.z1:.10g}",
                    f"{r.D_baseline_Mpc:.10g}",
                    f"{r.D_model_Mpc:.10g}",
                    f"{r.delta_Mpc:.10g}",
                    f"{r.delta_pct:.10g}",
                    f"{r.frac_baseline:.10g}",
                    f"{r.frac_model:.10g}",
                ]
            )

    # stdout summary (human scan friendly)
    print("[budget] model:", args.model)
    print("[budget] z_star:", f"{z_star:.6g}")
    print("[budget] bridge_z_used:", f"{z_b:.6g}")
    print("[budget] early Omegas:", f"Omega_m={Omega_m_early:.6g} Omega_r={Omega_r:.6g} Omega_L={Omega_lambda_early:.6g}")
    print("[budget] totals (Mpc): baseline=", f"{_mpc_from_m(baseline_total_m):.6g}", " model=", f"{_mpc_from_m(model_total_m):.6g}", " delta=", f"{_mpc_from_m(model_total_m - baseline_total_m):.6g}")
    print("[budget] wrote:", out_csv)
    for r in rows:
        print(
            "  ",
            r.interval,
            " baseline=",
            f"{r.D_baseline_Mpc:.6g}",
            " model=",
            f"{r.D_model_Mpc:.6g}",
            " d=",
            f"{r.delta_Mpc:.6g}",
            f" ({r.delta_pct:.3g}%)",
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

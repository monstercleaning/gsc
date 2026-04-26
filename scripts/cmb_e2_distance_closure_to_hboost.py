#!/usr/bin/env python3
"""E2.3 diagnostic: map distance-closure (dm_star_calibration) to an effective H(z) boost.

Context
-------
E2.2 introduced a purely diagnostic closure knob `dm_star_calibration` that rescales
the bridged comoving distance to recombination D_M(z*):

  D_M_target(z*) = dm_star_calibration * D_M_raw(z*)

This script provides an *interpretation mapping* for that knob: an "effective"
constant multiplicative boost A applied to H(z) above a chosen redshift z_boost_start.

Definition (effective mapping; not physics)
------------------------------------------
Let the bridge construction define a split of D_M(z*) as:

  D_M_raw(z*) = D_M(0 -> z_boost_start) + D_M(z_boost_start -> z*)

Define A such that applying H -> A H on [z_boost_start, z*] (so that
D_M(z_boost_start -> z*) -> D_M(z_boost_start -> z*) / A) reproduces the
diagnostic target distance:

  D_M(0 -> z_boost_start) + D_M(z_boost_start -> z*) / A = D_M_target(z*)

Solving:

  A = D_M(z_boost_start -> z*) / (D_M_target(z*) - D_M(0 -> z_boost_start))

This is an effective "what would it take" mapping only. It is not a physical
early-time closure model and must not be used as a claim.
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
from typing import Any, Dict, List, Sequence


V101_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = V101_DIR.parent
sys.path.insert(0, str(V101_DIR))
sys.path.insert(0, str(V101_DIR / "scripts"))

import numpy as np  # noqa: E402

from gsc.early_time import compute_bridged_distance_priors  # noqa: E402
from gsc.early_time.cmb_distance_priors import _comoving_distance_to_z_m  # noqa: E402
from gsc.measurement_model import (  # noqa: E402
    FlatLambdaCDMHistory,
    GSCTransitionHistory,
    H0_to_SI,
    MPC_SI,
    PowerLawHistory,
)


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


def _comoving_distance_early_Mpc(
    *,
    z: float,
    H0_si: float,
    Omega_m: float,
    Omega_r: float,
    Omega_lambda: float,
) -> float:
    """Early-time comoving distance helper used by the bridge (LCDM + radiation).

    Implementation detail: we reuse the bridge module's internal integrator to keep
    this diagnostic consistent with the bridge construction.
    """
    if z == 0.0:
        return 0.0
    D_m = float(
        _comoving_distance_to_z_m(
            z=float(z),
            H0_si=float(H0_si),
            omega_m=float(Omega_m),
            omega_r=float(Omega_r),
            omega_lambda=float(Omega_lambda),
        )
    )
    return float(D_m / float(MPC_SI))


def effective_H_boost_factor(
    *,
    D_M_0_to_zstart_Mpc: float,
    D_M_zstart_to_zstar_Mpc: float,
    dm_star_calibration: float,
) -> float:
    """Return the effective constant H boost factor A implied by dm_star_calibration.

    Raises if the mapping is impossible (e.g. dm_star_calibration too small to be
    achieved by boosting H only above zstart).
    """
    if not (D_M_0_to_zstart_Mpc >= 0 and math.isfinite(D_M_0_to_zstart_Mpc)):
        raise ValueError("D_M_0_to_zstart_Mpc must be finite and >= 0")
    if not (D_M_zstart_to_zstar_Mpc > 0 and math.isfinite(D_M_zstart_to_zstar_Mpc)):
        raise ValueError("D_M_zstart_to_zstar_Mpc must be finite and > 0")
    if not (dm_star_calibration > 0 and math.isfinite(dm_star_calibration)):
        raise ValueError("dm_star_calibration must be finite and > 0")

    D_M_total = float(D_M_0_to_zstart_Mpc) + float(D_M_zstart_to_zstar_Mpc)
    D_M_target = float(dm_star_calibration) * float(D_M_total)
    denom = float(D_M_target) - float(D_M_0_to_zstart_Mpc)
    if not (denom > 0 and math.isfinite(denom)):
        raise ValueError(
            "effective mapping is impossible: require D_M_target > D_M(0->zstart); "
            f"got D_M_target={D_M_target:.6g} and D_M_0_to_zstart={D_M_0_to_zstart_Mpc:.6g}"
        )
    A = float(D_M_zstart_to_zstar_Mpc) / float(denom)
    if not (A > 0 and math.isfinite(A)):
        raise ValueError("Computed A is non-physical")
    return float(A)


@dataclass(frozen=True)
class HBoostRow:
    z_boost_start: float
    A: float
    deltaH_over_H: float
    D_M_0_to_zstart_Mpc: float
    D_M_zstart_to_zstar_Mpc: float
    D_M_total_Mpc: float
    D_M_target_Mpc: float


def compute_effective_hboost_solution(
    *,
    model: str,
    H0_km_s_Mpc: float,
    Omega_m: float,
    Omega_L: float,
    gsc_p: float,
    gsc_ztrans: float,
    cmb_bridge_z: float,
    dm_star_calibration: float,
    omega_b_h2: float,
    omega_c_h2: float,
    Neff: float,
    Tcmb_K: float,
    z_boost_starts: Sequence[float],
) -> Dict[str, Any]:
    if model == "lcdm":
        H0_si = H0_to_SI(float(H0_km_s_Mpc))
        hist = FlatLambdaCDMHistory(H0=float(H0_si), Omega_m=float(Omega_m), Omega_Lambda=float(Omega_L))
    elif model == "gsc_powerlaw":
        H0_si = H0_to_SI(float(H0_km_s_Mpc))
        hist = PowerLawHistory(H0=float(H0_si), p=float(gsc_p))
    elif model == "gsc_transition":
        H0_si = H0_to_SI(float(H0_km_s_Mpc))
        hist = GSCTransitionHistory(
            H0=float(H0_si),
            Omega_m=float(Omega_m),
            Omega_Lambda=float(Omega_L),
            p=float(gsc_p),
            z_transition=float(gsc_ztrans),
        )
    else:
        raise ValueError(f"Unknown model: {model!r}")

    pred_raw = compute_bridged_distance_priors(
        model=hist,
        z_bridge=float(cmb_bridge_z),
        omega_b_h2=float(omega_b_h2),
        omega_c_h2=float(omega_c_h2),
        N_eff=float(Neff),
        Tcmb_K=float(Tcmb_K),
        rs_star_calibration=1.0,
        dm_star_calibration=1.0,
    )

    z_bridge_used = float(pred_raw["bridge_z"])
    z_star = float(pred_raw["z_star"])

    D0_bridge = float(pred_raw["D_M_0_to_bridge_Mpc"])
    D_bridge_star = float(pred_raw["D_M_bridge_to_zstar_Mpc"])
    D_total = float(pred_raw.get("D_M_star_Mpc_raw", D0_bridge + D_bridge_star))
    D_total = float(D0_bridge + D_bridge_star) if not math.isfinite(D_total) else float(D_total)

    Omega_m_early = float(pred_raw["Omega_m_early"])
    Omega_r = float(pred_raw["Omega_r"])
    Omega_lambda_early = 1.0 - float(Omega_m_early) - float(Omega_r)
    if not math.isfinite(Omega_lambda_early):
        raise ValueError("Derived Omega_lambda_early is non-finite")

    H0_si = float(hist.H(0.0))

    # Precompute early distances needed for z-boost sweeps (z >= z_bridge).
    D_early_bridge = _comoving_distance_early_Mpc(
        z=float(z_bridge_used),
        H0_si=float(H0_si),
        Omega_m=float(Omega_m_early),
        Omega_r=float(Omega_r),
        Omega_lambda=float(Omega_lambda_early),
    )
    D_early_star = _comoving_distance_early_Mpc(
        z=float(z_star),
        H0_si=float(H0_si),
        Omega_m=float(Omega_m_early),
        Omega_r=float(Omega_r),
        Omega_lambda=float(Omega_lambda_early),
    )

    rows: List[HBoostRow] = []
    for z_start in z_boost_starts:
        z_start = float(z_start)
        if not (z_start >= z_bridge_used and z_start < z_star and math.isfinite(z_start)):
            continue

        if abs(z_start - z_bridge_used) < 1e-12:
            D_0_to_zstart = float(D0_bridge)
            D_zstart_to_star = float(D_bridge_star)
        else:
            D_early_zstart = _comoving_distance_early_Mpc(
                z=float(z_start),
                H0_si=float(H0_si),
                Omega_m=float(Omega_m_early),
                Omega_r=float(Omega_r),
                Omega_lambda=float(Omega_lambda_early),
            )
            D_0_to_zstart = float(D0_bridge) + (float(D_early_zstart) - float(D_early_bridge))
            D_zstart_to_star = float(D_early_star) - float(D_early_zstart)

        D_total_use = float(D_0_to_zstart + D_zstart_to_star)
        D_target = float(dm_star_calibration) * float(D_total_use)
        try:
            A = effective_H_boost_factor(
                D_M_0_to_zstart_Mpc=float(D_0_to_zstart),
                D_M_zstart_to_zstar_Mpc=float(D_zstart_to_star),
                dm_star_calibration=float(dm_star_calibration),
            )
        except ValueError:
            # If z_boost_start is too close to z* (or dm too small), there may be
            # insufficient remaining distance to "repair" by boosting H only above
            # z_boost_start. Record NaNs for those rows instead of hard-failing.
            A = float("nan")
        rows.append(
            HBoostRow(
                z_boost_start=float(z_start),
                A=float(A),
                deltaH_over_H=float(A - 1.0) if math.isfinite(float(A)) else float("nan"),
                D_M_0_to_zstart_Mpc=float(D_0_to_zstart),
                D_M_zstart_to_zstar_Mpc=float(D_zstart_to_star),
                D_M_total_Mpc=float(D_total_use),
                D_M_target_Mpc=float(D_target),
            )
        )

    if not rows:
        raise ValueError("No valid z_boost_starts (require z_boost_start >= bridge_z and < z_star)")

    rows_sorted = sorted(rows, key=lambda r: float(r.z_boost_start))
    row_bridge = min(rows_sorted, key=lambda r: abs(float(r.z_boost_start) - float(z_bridge_used)))

    return {
        "pred_raw": dict(pred_raw),
        "z_bridge_used": float(z_bridge_used),
        "z_star": float(z_star),
        "Omega_m_early": float(Omega_m_early),
        "Omega_r": float(Omega_r),
        "Omega_lambda_early": float(Omega_lambda_early),
        "dm_star_calibration": float(dm_star_calibration),
        "solution_at_bridge_z": {
            "z_boost_start": float(row_bridge.z_boost_start),
            "A": float(row_bridge.A),
            "deltaH_over_H": float(row_bridge.deltaH_over_H),
        },
        "rows": [r.__dict__ for r in rows_sorted],
    }


def _plot_hboost_vs_zstart(*, rows: List[HBoostRow], out_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: E402

    xs = [float(r.z_boost_start) for r in rows if math.isfinite(float(r.deltaH_over_H))]
    ys = [100.0 * float(r.deltaH_over_H) for r in rows if math.isfinite(float(r.deltaH_over_H))]

    fig, ax = plt.subplots(figsize=(7.5, 4.5), constrained_layout=True)
    ax.plot(xs, ys, marker="o", linewidth=2.0)
    ax.set_xlabel("z_boost_start")
    ax.set_ylabel("effective H boost  (A-1) [%]")
    ax.set_title("E2.3 diagnostic: effective constant H(z) boost vs z_boost_start")
    ax.grid(True, alpha=0.3)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=("lcdm", "gsc_transition", "gsc_powerlaw"), default="gsc_transition")
    ap.add_argument("--cmb-bridge-z", type=float, default=5.0)
    ap.add_argument("--dm-star-calib", type=float, default=1.0, help="Diagnostic D_M(z*) multiplier (E2.2 dm_fit).")
    ap.add_argument(
        "--z-boost-starts",
        type=str,
        default="bridge,10,20,50,100",
        help="CSV list of z_boost_start values; use 'bridge' to denote the used bridge_z.",
    )
    ap.add_argument("--outdir", type=Path, default=Path("v11.0.0/results/diagnostic_cmb_e2_hboost"))

    # Late-time model defaults (Planck-like baseline used in bridge diagnostics).
    ap.add_argument("--H0", type=float, default=67.4)
    ap.add_argument("--Omega-m", dest="Omega_m", type=float, default=0.315)
    ap.add_argument("--Omega-L", dest="Omega_L", type=float, default=0.685)
    ap.add_argument("--gsc-p", type=float, default=0.6)
    ap.add_argument("--gsc-ztrans", type=float, default=1.8)

    # Early-time physical densities (Planck-like).
    ap.add_argument("--omega-b-h2", type=float, default=0.02237)
    ap.add_argument("--omega-c-h2", type=float, default=0.1200)
    ap.add_argument("--Neff", type=float, default=3.046)
    ap.add_argument("--Tcmb-K", type=float, default=2.7255)

    args = ap.parse_args()

    out_dir = args.outdir
    tables_dir = out_dir / "tables"
    figs_dir = out_dir / "figures"
    _ensure_dir(tables_dir)
    _ensure_dir(figs_dir)

    # Parse z_boost_starts.
    zstarts: List[float] = []
    for tok in str(args.z_boost_starts).split(","):
        tok = tok.strip()
        if not tok:
            continue
        if tok == "bridge":
            zstarts.append(float(args.cmb_bridge_z))
        else:
            zstarts.append(float(tok))
    if not zstarts:
        zstarts = [float(args.cmb_bridge_z)]

    r = compute_effective_hboost_solution(
        model=str(args.model),
        H0_km_s_Mpc=float(args.H0),
        Omega_m=float(args.Omega_m),
        Omega_L=float(args.Omega_L),
        gsc_p=float(args.gsc_p),
        gsc_ztrans=float(args.gsc_ztrans),
        cmb_bridge_z=float(args.cmb_bridge_z),
        dm_star_calibration=float(args.dm_star_calib),
        omega_b_h2=float(args.omega_b_h2),
        omega_c_h2=float(args.omega_c_h2),
        Neff=float(args.Neff),
        Tcmb_K=float(args.Tcmb_K),
        z_boost_starts=zstarts,
    )

    rows = [HBoostRow(**row) for row in r["rows"]]

    # One-line summary (bridge_z only).
    sol = dict(r["solution_at_bridge_z"])
    D_total = float(rows[0].D_M_total_Mpc) if rows else float("nan")

    summary_csv = tables_dir / "hboost_solution.csv"
    with summary_csv.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "model",
            "gsc_p",
            "gsc_ztrans",
            "bridge_z_used",
            "z_star",
            "dm_star_calibration",
            "A",
            "deltaH_over_H",
            "D_M_total_Mpc",
            "D_M_target_Mpc",
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerow(
            {
                "model": str(args.model),
                "gsc_p": f"{float(args.gsc_p):.12g}",
                "gsc_ztrans": f"{float(args.gsc_ztrans):.12g}",
                "bridge_z_used": f"{float(r['z_bridge_used']):.12g}",
                "z_star": f"{float(r['z_star']):.12g}",
                "dm_star_calibration": f"{float(args.dm_star_calib):.16g}",
                "A": f"{float(sol['A']):.16g}",
                "deltaH_over_H": f"{float(sol['deltaH_over_H']):.16g}",
                "D_M_total_Mpc": f"{float(D_total):.12g}",
                "D_M_target_Mpc": f"{float(args.dm_star_calib) * float(D_total):.12g}",
            }
        )

    sweep_csv = tables_dir / "hboost_vs_zboost_start.csv"
    with sweep_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].__dict__.keys()))
        w.writeheader()
        for rr in rows:
            w.writerow({k: f"{float(v):.16g}" for k, v in rr.__dict__.items()})

    plot_path = figs_dir / "hboost_vs_zboost_start.png"
    _plot_hboost_vs_zstart(rows=rows, out_path=plot_path)

    def _row_for_json(rr: HBoostRow) -> Dict[str, Any]:
        # JSON does not support NaN/Infinity; encode impossible mappings as nulls.
        d: Dict[str, Any] = dict(rr.__dict__)
        for k in ("A", "deltaH_over_H"):
            v = float(d[k])
            if not math.isfinite(v):
                d[k] = None
        return d

    manifest = {
        "diagnostic_only": True,
        "kind": "cmb_e2_distance_closure_to_hboost",
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"]),
        "git_branch": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "--abbrev-ref", "HEAD"]),
        "git_dirty": bool(_run_git(["git", "-C", str(REPO_ROOT), "status", "--porcelain=v1"])),
        "model_config": {
            "model": str(args.model),
            "H0_km_s_Mpc": float(args.H0),
            "Omega_m": float(args.Omega_m),
            "Omega_L": float(args.Omega_L),
            "gsc_p": float(args.gsc_p),
            "gsc_ztrans": float(args.gsc_ztrans),
            "cmb_bridge_z": float(args.cmb_bridge_z),
        },
        "early_config": {
            "omega_b_h2": float(args.omega_b_h2),
            "omega_c_h2": float(args.omega_c_h2),
            "Neff": float(args.Neff),
            "Tcmb_K": float(args.Tcmb_K),
        },
        "closure_mapping": {
            "dm_star_calibration": float(args.dm_star_calib),
            "definition": "Solve A such that D_M(0->z_start) + D_M(z_start->z*)/A = dm * D_M_raw(z*).",
            "z_boost_starts": [float(x) for x in zstarts],
            "solution_at_bridge_z": dict(sol),
            "rows": [_row_for_json(rr) for rr in rows],
        },
        "outputs": {
            "outdir": _relpath(out_dir),
            "summary_csv": _relpath(summary_csv),
            "sweep_csv": _relpath(sweep_csv),
            "plot": _relpath(plot_path),
        },
        "notes": [
            "Diagnostic-only: effective mapping from dm_star_calibration to an H(z) boost above z_boost_start.",
            "This is not a physical early-time closure model and must not be used as a claim.",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("OK: wrote E2.3 effective-hboost diagnostic")
    print(f"  outdir={_relpath(out_dir)}")
    print(f"  dm_star_calibration={float(args.dm_star_calib):.16g}")
    print(f"  bridge_z_used={float(r['z_bridge_used']):.6g}  z_star={float(r['z_star']):.6g}")
    print(f"  A(bridge_z)={float(sol['A']):.6g}  deltaH/H={100.0*float(sol['deltaH_over_H']):.3g}%")


if __name__ == "__main__":
    main()

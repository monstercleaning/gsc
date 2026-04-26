#!/usr/bin/env python3
"""E2.9 diagnostic: z* / r_s(z*) definition audit (Hu–Sugiyama vs Peebles-style recombination).

Scope / guardrails
------------------
- Diagnostic-only; not used by the canonical late-time pipeline.
- Goal is *not* to remove `_RS_STAR_CALIB_CHW2018` here, but to quantify whether
  the ~0.29% stopgap is driven by:
    (A) numerical quadrature error (already audited separately), or
    (B) definition/approximation mismatch (e.g. z* model).

This script compares:
1) z* from the existing Hu–Sugiyama fitting formula, and
2) z* from a minimal Peebles-style 3-level atom recombination ODE (hydrogen-only, approximate).

Then it computes r_s(z*) for each method using the *same* sound-horizon integral
implementation as the bridge predictors (to isolate the effect of z*).
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
from typing import Any, Dict, Optional, Sequence, Tuple


V101_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = V101_DIR.parent
sys.path.insert(0, str(V101_DIR))

from gsc.early_time import z_star_hu_sugiyama  # noqa: E402
from gsc.early_time.cmb_distance_priors import _RS_STAR_CALIB_CHW2018, _sound_horizon_from_z_m  # noqa: E402
from gsc.early_time.rd import omega_gamma_h2_from_Tcmb, omega_r_h2  # noqa: E402
from gsc.measurement_model import H0_to_SI, MPC_SI  # noqa: E402
from gsc.diagnostics.recombination import z_star_peebles_approx  # noqa: E402


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


@dataclass(frozen=True)
class AuditRow:
    H0: float
    Omega_m: float
    omega_b_h2: float
    omega_c_h2: float
    Neff: float
    Tcmb_K: float
    Yp: float

    zstar_hu_sugiyama: float
    zstar_peebles: float

    rs_hu_sugiyama_Mpc: float
    rs_peebles_Mpc: float

    delta_rs_ppm: float
    chw2018_calib_ppm: float

    def as_csv_dict(self) -> Dict[str, str]:
        def f(x: float) -> str:
            return f"{float(x):.16g}"

        return {
            "H0_km_s_Mpc": f(self.H0),
            "Omega_m": f(self.Omega_m),
            "omega_b_h2": f(self.omega_b_h2),
            "omega_c_h2": f(self.omega_c_h2),
            "Neff": f(self.Neff),
            "Tcmb_K": f(self.Tcmb_K),
            "Yp": f(self.Yp),
            "zstar_hu_sugiyama": f(self.zstar_hu_sugiyama),
            "zstar_peebles": f(self.zstar_peebles),
            "rs_hu_sugiyama_Mpc": f(self.rs_hu_sugiyama_Mpc),
            "rs_peebles_Mpc": f(self.rs_peebles_Mpc),
            "delta_rs_ppm": f(self.delta_rs_ppm),
            "chw2018_calib_ppm": f(self.chw2018_calib_ppm),
        }


def run(
    *,
    out_dir: Path,
    H0_km_s_Mpc: float,
    Omega_m: float,
    omega_b_h2: float,
    omega_c_h2: float,
    Neff: float,
    Tcmb_K: float,
    Yp: float,
    n_rs: int,
    z_max: float,
    z_min_ode: float,
    n_grid: int,
    ode_method: str,
) -> Dict[str, Any]:
    out_dir = out_dir.resolve()
    tables_dir = out_dir / "tables"
    figs_dir = out_dir / "figures"
    _ensure_dir(tables_dir)
    _ensure_dir(figs_dir)

    H0_si = float(H0_to_SI(float(H0_km_s_Mpc)))

    # Radiation bookkeeping (standard).
    H0_km_s_Mpc_f = float(H0_km_s_Mpc)
    h = float(H0_km_s_Mpc_f) / 100.0
    og_h2 = float(omega_gamma_h2_from_Tcmb(float(Tcmb_K)))
    or_h2 = float(omega_r_h2(Tcmb_K=float(Tcmb_K), N_eff=float(Neff)))
    Omega_r = float(or_h2) / (h * h)
    Omega_Lambda = 1.0 - float(Omega_m) - float(Omega_r)
    if Omega_Lambda <= 0.0:
        raise ValueError("Derived Omega_Lambda <= 0 (non-flat inputs)")

    omega_m_h2 = float(omega_b_h2) + float(omega_c_h2)
    z_hs = float(z_star_hu_sugiyama(omega_b_h2=float(omega_b_h2), omega_m_h2=float(omega_m_h2)))
    z_p, info_p = z_star_peebles_approx(
        H0_si=float(H0_si),
        Omega_m=float(Omega_m),
        Omega_r=float(Omega_r),
        Omega_Lambda=float(Omega_Lambda),
        omega_b_h2=float(omega_b_h2),
        Tcmb_K=float(Tcmb_K),
        Yp=float(Yp),
        z_max=float(z_max),
        z_min_ode=float(z_min_ode),
        n_grid=int(n_grid),
        method=str(ode_method),
    )

    rs_hs_m = float(
        _sound_horizon_from_z_m(
            z=float(z_hs),
            H0_si=float(H0_si),
            omega_b_h2=float(omega_b_h2),
            omega_gamma_h2=float(og_h2),
            omega_m=float(Omega_m),
            omega_r=float(Omega_r),
            omega_lambda=float(Omega_Lambda),
            n=int(n_rs),
        )
    )
    rs_p_m = float(
        _sound_horizon_from_z_m(
            z=float(z_p),
            H0_si=float(H0_si),
            omega_b_h2=float(omega_b_h2),
            omega_gamma_h2=float(og_h2),
            omega_m=float(Omega_m),
            omega_r=float(Omega_r),
            omega_lambda=float(Omega_Lambda),
            n=int(n_rs),
        )
    )

    rs_hs_Mpc = float(rs_hs_m) / float(MPC_SI)
    rs_p_Mpc = float(rs_p_m) / float(MPC_SI)
    delta_rs_ppm = (float(rs_p_Mpc) / float(rs_hs_Mpc) - 1.0) * 1.0e6
    chw_calib_ppm = (float(_RS_STAR_CALIB_CHW2018) - 1.0) * 1.0e6

    row = AuditRow(
        H0=float(H0_km_s_Mpc),
        Omega_m=float(Omega_m),
        omega_b_h2=float(omega_b_h2),
        omega_c_h2=float(omega_c_h2),
        Neff=float(Neff),
        Tcmb_K=float(Tcmb_K),
        Yp=float(Yp),
        zstar_hu_sugiyama=float(z_hs),
        zstar_peebles=float(z_p),
        rs_hu_sugiyama_Mpc=float(rs_hs_Mpc),
        rs_peebles_Mpc=float(rs_p_Mpc),
        delta_rs_ppm=float(delta_rs_ppm),
        chw2018_calib_ppm=float(chw_calib_ppm),
    )

    # Write table.
    table_path = tables_dir / "zstar_rs_audit.csv"
    with table_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row.as_csv_dict().keys()))
        w.writeheader()
        w.writerow(row.as_csv_dict())

    # Figure.
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.0, 3.2), constrained_layout=True)
    labels = ["Hu-Sugiyama fit", "Peebles ODE"]
    ax1.bar(labels, [float(z_hs), float(z_p)], color=["#4c78a8", "#f58518"])
    ax1.set_ylabel("z*")
    ax1.set_title("Recombination redshift z* (diagnostic)")
    ax1.grid(True, axis="y", alpha=0.25)

    ax2.bar(labels, [float(rs_hs_Mpc), float(rs_p_Mpc)], color=["#4c78a8", "#f58518"])
    ax2.set_ylabel("r_s(z*) [Mpc]")
    ax2.set_title("Sound horizon evaluated at each z* (same integral)")
    ax2.grid(True, axis="y", alpha=0.25)

    fig_path = figs_dir / "rs_vs_method.png"
    fig.savefig(fig_path, dpi=170)
    plt.close(fig)

    summary_path = tables_dir / "summary.txt"
    summary_lines = [
        "E2.9 z* / r_s(z*) definition audit (diagnostic-only)",
        "",
        f"inputs: H0={float(H0_km_s_Mpc):g}  Omega_m={float(Omega_m):g}  omega_b_h2={float(omega_b_h2):g}  omega_c_h2={float(omega_c_h2):g}",
        f"        Neff={float(Neff):g}  Tcmb_K={float(Tcmb_K):g}  Yp={float(Yp):g}",
        "",
        f"zstar_hu_sugiyama={float(z_hs):.6g}",
        f"zstar_peebles={float(z_p):.6g}  (x_e={float(info_p.get('x_e_at_z_star', float('nan'))):.3g}, tau={float(info_p.get('tau_at_z_star', float('nan'))):.3g})",
        "",
        f"rs_hu_sugiyama_Mpc={float(rs_hs_Mpc):.9g}",
        f"rs_peebles_Mpc={float(rs_p_Mpc):.9g}",
        f"delta_rs_ppm (peebles/hs - 1) = {float(delta_rs_ppm):.3f} ppm",
        f"CHW2018 rs* stopgap calibration = {float(chw_calib_ppm):.3f} ppm  (factor {_RS_STAR_CALIB_CHW2018:.10g})",
    ]
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    manifest: Dict[str, Any] = {
        "diagnostic_only": True,
        "kind": "cmb_e2_zstar_recombination_audit",
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "git_commit": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"]),
        "git_branch": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "--abbrev-ref", "HEAD"]),
        "git_dirty": bool(_run_git(["git", "-C", str(REPO_ROOT), "status", "--porcelain=v1"]).strip()),
        "inputs": {
            "params": {
                "H0_km_s_Mpc": float(H0_km_s_Mpc),
                "Omega_m": float(Omega_m),
                "omega_b_h2": float(omega_b_h2),
                "omega_c_h2": float(omega_c_h2),
                "Neff": float(Neff),
                "Tcmb_K": float(Tcmb_K),
                "Yp": float(Yp),
            }
        },
        "methods": {
            "zstar_hu_sugiyama": "Hu–Sugiyama fitting formula (as in bridge predictors).",
            "zstar_peebles": {
                "description": "Minimal Peebles-style hydrogen recombination ODE; z* defined as visibility peak.",
                "ode": {"z_max": float(z_max), "z_min_ode": float(z_min_ode), "n_grid": int(n_grid), "method": str(ode_method)},
            },
            "rs_star": {
                "description": "Sound-horizon integral evaluated at the chosen z* (same integrator for both methods).",
                "n_rs": int(n_rs),
            },
            "chw2018_stopgap": {"_RS_STAR_CALIB_CHW2018": float(_RS_STAR_CALIB_CHW2018)},
        },
        "outputs": {
            "outdir": _relpath(out_dir),
            "table": _relpath(table_path),
            "summary": _relpath(summary_path),
            "figure": _relpath(fig_path),
        },
        "summary": {
            "zstar_hu_sugiyama": float(z_hs),
            "zstar_peebles": float(z_p),
            "rs_hu_sugiyama_Mpc": float(rs_hs_Mpc),
            "rs_peebles_Mpc": float(rs_p_Mpc),
            "delta_rs_ppm": float(delta_rs_ppm),
            "chw2018_calib_ppm": float(chw_calib_ppm),
        },
        "notes": [
            "Diagnostic-only audit of z* definition sensitivity; not a recombination engine.",
            "This does not modify any canonical pipeline outputs or the CHW2018 stopgap calibration.",
        ],
    }

    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return manifest


def main(argv: Optional[Sequence[str]] = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", type=Path, default=Path("v11.0.0/results/diagnostic_zstar_recombination_audit"))

    ap.add_argument("--H0", type=float, default=67.4)
    ap.add_argument("--Omega-m", dest="Omega_m", type=float, default=0.315)
    ap.add_argument("--omega-b-h2", type=float, default=0.02237)
    ap.add_argument("--omega-c-h2", type=float, default=0.1200)
    ap.add_argument("--Neff", type=float, default=3.046)
    ap.add_argument("--Tcmb-K", type=float, default=2.7255)
    ap.add_argument("--Yp", type=float, default=0.245)

    ap.add_argument("--n-rs", type=int, default=8192)
    ap.add_argument("--z-max", type=float, default=3000.0)
    ap.add_argument("--z-min-ode", type=float, default=200.0)
    ap.add_argument("--n-grid", type=int, default=8192)
    ap.add_argument("--ode-method", type=str, default="fixed_rk4_u")

    args = ap.parse_args(argv)

    run(
        out_dir=Path(args.outdir),
        H0_km_s_Mpc=float(args.H0),
        Omega_m=float(args.Omega_m),
        omega_b_h2=float(args.omega_b_h2),
        omega_c_h2=float(args.omega_c_h2),
        Neff=float(args.Neff),
        Tcmb_K=float(args.Tcmb_K),
        Yp=float(args.Yp),
        n_rs=int(args.n_rs),
        z_max=float(args.z_max),
        z_min_ode=float(args.z_min_ode),
        n_grid=int(args.n_grid),
        ode_method=str(args.ode_method),
    )


if __name__ == "__main__":  # pragma: no cover
    main()

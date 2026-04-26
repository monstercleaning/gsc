#!/usr/bin/env python3
"""E2 diagnostic: r_s(z*) numerics audit for the CHW2018 stopgap calibration.

Goal
----
Quantify whether the ~0.29% `_RS_STAR_CALIB_CHW2018` factor is explained by
numerical integration error in the bridge-level `r_s(z*)` integral, or whether
it persists under higher-accuracy quadrature (pointing to a definition / fit-
formula mismatch rather than a discretization artifact).

Scope / guardrails
------------------
- Diagnostic-only; out of submission scope.
- Does not modify canonical late-time outputs or frozen bundles.
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

from gsc.early_time.cmb_distance_priors import (  # noqa: E402
    _RS_STAR_CALIB_CHW2018,
    _e_lcdm_radiation,
    _sound_horizon_from_z_m,
    omega_gamma_h2_from_Tcmb,
    omega_r_h2,
    z_star_hu_sugiyama,
    _comoving_distance_to_z_m,
    compute_lcdm_distance_priors,
)
from gsc.measurement_model import C_SI, H0_to_SI, MPC_SI  # noqa: E402


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


def _parse_int_list(spec: str) -> List[int]:
    s = str(spec).strip()
    if not s:
        return []
    out: List[int] = []
    for tok in s.split(","):
        t = tok.strip()
        if not t:
            continue
        out.append(int(t))
    return out


def _sound_horizon_gauss_legendre_u(
    *,
    z: float,
    H0_si: float,
    omega_b_h2: float,
    omega_gamma_h2: float,
    omega_m: float,
    omega_r: float,
    omega_lambda: float,
    z_max: float,
    n: int,
) -> float:
    """Compute r_s(z) with Gauss-Legendre quadrature in u=ln(1+z).

    This matches the integrand used by `_sound_horizon_from_z_m`:
      r_s = ∫_{z}^{z_max} c_s(z)/H(z) dz
          = ∫_{u(z)}^{u(z_max)} [c_s/H * (1+z)] du,   with dz=(1+z)du.
    """
    if not (z > 0 and z_max > z and math.isfinite(z_max)):
        raise ValueError("Require z_max > z > 0")
    if n < 32:
        raise ValueError("n too small for Gauss-Legendre")

    u0 = math.log1p(float(z))
    u1 = math.log1p(float(z_max))
    x, w = np.polynomial.legendre.leggauss(int(n))
    uu = 0.5 * (u1 - u0) * x + 0.5 * (u1 + u0)
    ww = 0.5 * (u1 - u0) * w

    one_plus_z = np.exp(uu)
    zz = one_plus_z - 1.0

    # R(z) = (3/4) * (omega_b/omega_gamma) / (1+z)
    R = (3.0 / 4.0) * (float(omega_b_h2) / float(omega_gamma_h2)) / one_plus_z
    cs = float(C_SI) / np.sqrt(3.0 * (1.0 + R))
    Ez = _e_lcdm_radiation(zz, omega_m=float(omega_m), omega_r=float(omega_r), omega_lambda=float(omega_lambda))
    Hz = float(H0_si) * Ez
    if not (np.isfinite(Hz).all() and float(Hz.min()) > 0.0):
        raise ValueError("Non-finite/negative H(z) in quadrature nodes")

    integrand = (cs / Hz) * one_plus_z
    rs = float(np.sum(ww * integrand))
    if not (rs > 0 and math.isfinite(rs)):
        raise ValueError("Computed r_s is non-physical")
    return float(rs)


@dataclass(frozen=True)
class Row:
    method: str
    n: int
    z_star: float
    z_max: float
    rs_star_Mpc: float
    rel_err_vs_ref: float
    lA: float
    R: float

    def as_csv_dict(self) -> Dict[str, str]:
        def f(x: float) -> str:
            if not math.isfinite(float(x)):
                return ""
            return f"{float(x):.16g}"

        return {
            "method": str(self.method),
            "n": str(int(self.n)),
            "z_star": f(self.z_star),
            "z_max": f(self.z_max),
            "rs_star_Mpc": f(self.rs_star_Mpc),
            "rel_err_vs_ref": f(self.rel_err_vs_ref),
            "lA": f(self.lA),
            "R": f(self.R),
        }


def run(
    *,
    out_dir: Path,
    H0_km_s_Mpc: float,
    Omega_m: float,
    omega_b_h2: float,
    omega_c_h2: float,
    N_eff: float,
    Tcmb_K: float,
    z_max: float,
    trap_n_list: Sequence[int],
    gl_n_list: Sequence[int],
    gl_n_ref: int,
) -> Dict[str, Any]:
    out_dir = out_dir.resolve()
    tables_dir = out_dir / "tables"
    figs_dir = out_dir / "figures"
    _ensure_dir(tables_dir)
    _ensure_dir(figs_dir)

    if not (H0_km_s_Mpc > 0 and 0.0 < Omega_m < 1.0 and omega_b_h2 > 0 and omega_c_h2 >= 0):
        raise ValueError("Invalid baseline parameters")
    if not (N_eff > 0 and Tcmb_K > 0):
        raise ValueError("Invalid early-time parameters")
    if not (z_max > 1.0e4 and math.isfinite(z_max)):
        raise ValueError("z_max must be large and finite")
    if gl_n_ref < 64:
        raise ValueError("gl_n_ref too small")

    # Derived early parameters (match compute_lcdm_distance_priors).
    h = float(H0_km_s_Mpc) / 100.0
    H0_si = float(H0_to_SI(float(H0_km_s_Mpc)))
    omega_g_h2 = float(omega_gamma_h2_from_Tcmb(float(Tcmb_K)))
    omega_r_h2_val = float(omega_r_h2(Tcmb_K=float(Tcmb_K), N_eff=float(N_eff)))
    Omega_r = float(omega_r_h2_val) / (h * h)
    Omega_lambda = 1.0 - float(Omega_m) - float(Omega_r)
    if Omega_lambda < 0:
        raise ValueError("Derived Omega_lambda < 0; adjust inputs")

    omega_m_h2 = float(omega_b_h2) + float(omega_c_h2)
    z_star = float(z_star_hu_sugiyama(omega_b_h2=float(omega_b_h2), omega_m_h2=float(omega_m_h2)))

    # Baseline D_M (keep fixed for lA comparisons).
    D_M_star_m = float(
        _comoving_distance_to_z_m(
            z=float(z_star),
            H0_si=float(H0_si),
            omega_m=float(Omega_m),
            omega_r=float(Omega_r),
            omega_lambda=float(Omega_lambda),
            n=8192,
        )
    )
    if not (D_M_star_m > 0 and math.isfinite(D_M_star_m)):
        raise ValueError("Non-physical D_M(z*)")

    # Reference r_s using Gauss-Legendre.
    rs_ref_m = _sound_horizon_gauss_legendre_u(
        z=float(z_star),
        H0_si=float(H0_si),
        omega_b_h2=float(omega_b_h2),
        omega_gamma_h2=float(omega_g_h2),
        omega_m=float(Omega_m),
        omega_r=float(Omega_r),
        omega_lambda=float(Omega_lambda),
        z_max=float(z_max),
        n=int(gl_n_ref),
    )

    def lA_from_rs(rs_m: float) -> float:
        theta_star = float(rs_m / D_M_star_m)
        return float(math.pi / theta_star)

    def R_from_dm(dm_m: float) -> float:
        return float(math.sqrt(float(Omega_m)) * float(H0_si) * float(dm_m) / float(C_SI))

    R_val = R_from_dm(D_M_star_m)

    rows: List[Row] = []

    # Trapezoid u-integrator (current implementation).
    for n in trap_n_list:
        rs_m = float(
            _sound_horizon_from_z_m(
                z=float(z_star),
                H0_si=float(H0_si),
                omega_b_h2=float(omega_b_h2),
                omega_gamma_h2=float(omega_g_h2),
                omega_m=float(Omega_m),
                omega_r=float(Omega_r),
                omega_lambda=float(Omega_lambda),
                z_max=float(z_max),
                n=int(n),
            )
        )
        rel = float(rs_m / float(rs_ref_m) - 1.0)
        rows.append(
            Row(
                method="trap_u",
                n=int(n),
                z_star=float(z_star),
                z_max=float(z_max),
                rs_star_Mpc=float(rs_m / float(MPC_SI)),
                rel_err_vs_ref=float(rel),
                lA=float(lA_from_rs(rs_m)),
                R=float(R_val),
            )
        )

    # Gauss-Legendre u-integrator (alternative).
    for n in gl_n_list:
        rs_m = float(
            _sound_horizon_gauss_legendre_u(
                z=float(z_star),
                H0_si=float(H0_si),
                omega_b_h2=float(omega_b_h2),
                omega_gamma_h2=float(omega_g_h2),
                omega_m=float(Omega_m),
                omega_r=float(Omega_r),
                omega_lambda=float(Omega_lambda),
                z_max=float(z_max),
                n=int(n),
            )
        )
        rel = float(rs_m / float(rs_ref_m) - 1.0)
        rows.append(
            Row(
                method="gauss_u",
                n=int(n),
                z_star=float(z_star),
                z_max=float(z_max),
                rs_star_Mpc=float(rs_m / float(MPC_SI)),
                rel_err_vs_ref=float(rel),
                lA=float(lA_from_rs(rs_m)),
                R=float(R_val),
            )
        )

    # Add a convenience row that shows the calibrated r_s at the default trapezoid resolution.
    rs_raw_default_m = float(
        _sound_horizon_from_z_m(
            z=float(z_star),
            H0_si=float(H0_si),
            omega_b_h2=float(omega_b_h2),
            omega_gamma_h2=float(omega_g_h2),
            omega_m=float(Omega_m),
            omega_r=float(Omega_r),
            omega_lambda=float(Omega_lambda),
            z_max=float(z_max),
            n=8192,
        )
    )
    rs_cal_m = float(rs_raw_default_m) * float(_RS_STAR_CALIB_CHW2018)
    rows.append(
        Row(
            method="trap_u_calibrated",
            n=8192,
            z_star=float(z_star),
            z_max=float(z_max),
            rs_star_Mpc=float(rs_cal_m / float(MPC_SI)),
            rel_err_vs_ref=float(rs_cal_m / float(rs_ref_m) - 1.0),
            lA=float(lA_from_rs(rs_cal_m)),
            R=float(R_val),
        )
    )

    # Sort deterministically.
    rows = sorted(rows, key=lambda r: (str(r.method), int(r.n)))

    # Write table.
    csv_path = tables_dir / "rs_star_numerics_compare.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].as_csv_dict().keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r.as_csv_dict())

    # Simple plot: relative error vs n for each integrator.
    fig_path: Optional[Path] = None
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # noqa: E402

        fig, ax = plt.subplots(figsize=(7.8, 4.8), constrained_layout=True)
        for method in ("trap_u", "gauss_u"):
            xs: List[float] = []
            ys: List[float] = []
            for r in rows:
                if r.method != method:
                    continue
                xs.append(float(r.n))
                ys.append(1.0e6 * float(r.rel_err_vs_ref))  # ppm
            if xs:
                ax.plot(xs, ys, marker="o", linewidth=2.0, label=method)
        calib_ppm = 1.0e6 * float(float(_RS_STAR_CALIB_CHW2018) - 1.0)
        ax.axhline(calib_ppm, color="k", alpha=0.25, linestyle="--", linewidth=1.0, label="CHW2018 calib (ppm)")
        ax.axhline(0.0, color="k", alpha=0.15, linewidth=1.0)
        ax.set_xscale("log")
        ax.set_xlabel("integration nodes (n)")
        ax.set_ylabel("relative error vs GL ref (ppm)")
        ax.set_title("r_s(z*) numerics audit (GL ref in u=ln(1+z))")
        ax.grid(True, alpha=0.25, which="both")
        ax.legend(frameon=False)
        fig_path = figs_dir / "rs_star_rel_error.png"
        fig.savefig(fig_path, dpi=160)
        plt.close(fig)
    except Exception:
        fig_path = None

    # Text summary.
    # Use the default trap_u n=8192 value to estimate discretization error.
    trap8192 = [r for r in rows if r.method == "trap_u" and r.n == 8192]
    trap_rel = float(trap8192[0].rel_err_vs_ref) if trap8192 else float("nan")
    calib_rel = float(float(_RS_STAR_CALIB_CHW2018) - 1.0)
    summary_path = tables_dir / "summary.txt"
    summary_lines = [
        "r_s(z*) numerics audit (diagnostic-only)",
        "",
        f"Planck-like inputs: H0={float(H0_km_s_Mpc):g}, Omega_m={float(Omega_m):g}, omega_b_h2={float(omega_b_h2):g}, omega_c_h2={float(omega_c_h2):g}, Neff={float(N_eff):g}, Tcmb={float(Tcmb_K):g}",
        f"z_star (Hu+Sugiyama fit): {float(z_star):.12g}",
        f"z_max (sound horizon upper limit): {float(z_max):.12g}",
        "",
        f"GL reference: n_ref={int(gl_n_ref)}  r_s_ref={float(rs_ref_m/MPC_SI):.16g} Mpc",
        f"trap_u @ n=8192: rel_err_vs_ref = {float(trap_rel):.6g}  ({float(1e6*trap_rel):.3f} ppm)",
        f"CHW2018 stopgap calibration: _RS_STAR_CALIB_CHW2018={float(_RS_STAR_CALIB_CHW2018):.16g}  => +{float(100*calib_rel):.6g}%  ({float(1e6*calib_rel):.1f} ppm)",
        "",
        "Interpretation hint:",
        "- If |trap_u rel_err| << calib_rel, then the ~0.29% offset is not a discretization artifact of the r_s integral.",
        "- If |trap_u rel_err| ~ calib_rel, then integration accuracy is the likely source.",
        "",
    ]
    summary_path.write_text("\n".join(summary_lines), encoding="utf-8")

    manifest: Dict[str, Any] = {
        "diagnostic_only": True,
        "kind": "rs_star_numerics_audit",
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "git_commit": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"]),
        "git_branch": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "--abbrev-ref", "HEAD"]),
        "git_dirty": bool(_run_git(["git", "-C", str(REPO_ROOT), "status", "--porcelain=v1"]).strip()),
        "inputs": {
            "H0_km_s_Mpc": float(H0_km_s_Mpc),
            "Omega_m": float(Omega_m),
            "omega_b_h2": float(omega_b_h2),
            "omega_c_h2": float(omega_c_h2),
            "N_eff": float(N_eff),
            "Tcmb_K": float(Tcmb_K),
        },
        "derived": {
            "h": float(h),
            "omega_gamma_h2": float(omega_g_h2),
            "omega_r_h2": float(omega_r_h2_val),
            "Omega_r": float(Omega_r),
            "Omega_lambda": float(Omega_lambda),
            "z_star": float(z_star),
            "D_M_star_Mpc": float(D_M_star_m / float(MPC_SI)),
        },
        "calibration": {
            "RS_STAR_CALIB_CHW2018": float(_RS_STAR_CALIB_CHW2018),
            "calib_rel": float(float(_RS_STAR_CALIB_CHW2018) - 1.0),
        },
        "numerics": {
            "z_max": float(z_max),
            "trap_n_list": [int(n) for n in trap_n_list],
            "gl_n_list": [int(n) for n in gl_n_list],
            "gl_n_ref": int(gl_n_ref),
        },
        "reference": {"rs_ref_Mpc": float(rs_ref_m / float(MPC_SI))},
        "outputs": {
            "outdir": _relpath(out_dir),
            "table": _relpath(csv_path),
            "figure": (_relpath(fig_path) if fig_path is not None else None),
            "summary": _relpath(summary_path),
        },
        "notes": [
            "Diagnostic-only audit of r_s(z*) numerical integration vs a Gauss-Legendre reference.",
            "Uses the same z_star fit formula for all methods to isolate integration error only.",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return manifest


def main(argv: Optional[Sequence[str]] = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", type=Path, default=Path("v11.0.0/results/diagnostic_rs_star_numerics"))

    ap.add_argument("--H0", type=float, default=67.4)
    ap.add_argument("--Omega-m", dest="Omega_m", type=float, default=0.315)
    ap.add_argument("--omega-b-h2", dest="omega_b_h2", type=float, default=0.02237)
    ap.add_argument("--omega-c-h2", dest="omega_c_h2", type=float, default=0.1200)
    ap.add_argument("--N-eff", dest="N_eff", type=float, default=3.046)
    ap.add_argument("--Tcmb", dest="Tcmb_K", type=float, default=2.7255)

    ap.add_argument("--z-max", dest="z_max", type=float, default=1.0e7)
    ap.add_argument("--trap-n-list", type=str, default="512,1024,2048,4096,8192")
    ap.add_argument("--gl-n-list", type=str, default="64,128,256,512,1024")
    ap.add_argument("--gl-n-ref", type=int, default=2048)

    args = ap.parse_args(argv)
    run(
        out_dir=Path(args.outdir),
        H0_km_s_Mpc=float(args.H0),
        Omega_m=float(args.Omega_m),
        omega_b_h2=float(args.omega_b_h2),
        omega_c_h2=float(args.omega_c_h2),
        N_eff=float(args.N_eff),
        Tcmb_K=float(args.Tcmb_K),
        z_max=float(args.z_max),
        trap_n_list=_parse_int_list(str(args.trap_n_list)),
        gl_n_list=_parse_int_list(str(args.gl_n_list)),
        gl_n_ref=int(args.gl_n_ref),
    )


if __name__ == "__main__":  # pragma: no cover
    main()


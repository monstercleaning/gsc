#!/usr/bin/env python3
"""E3 diagnostic module: GW "standard sirens" (diagnostic-only; out of submission scope).

This script generates simple examples of the GW/EM luminosity-distance ratio
under modified GW propagation, using one of two modes:

1) Phenomenological (Xi0, n) parameterization:
     Xi(z) = Xi0 + (1 - Xi0)/(1+z)^n
     d_L^GW(z) = Xi(z) * d_L^EM(z)

2) Friction / Planck-mass running interface (delta/alpha_M hooks):
     d_L^GW(z) / d_L^EM(z) = exp( ∫_0^z delta(z')/(1+z') dz' )

This is pipeline-unused and intended for roadmap diagnostics only.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable, Dict, Optional, Sequence


V101_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = V101_DIR.parent
sys.path.insert(0, str(V101_DIR))

from gsc.diagnostics.gw_sirens import Xi_of_z, gw_distance_ratio  # noqa: E402
from gsc.measurement_model import (  # noqa: E402
    D_L_flat,
    FlatLambdaCDMHistory,
    H0_to_SI,
    MPC_SI,
)


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _relpath(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except Exception:
        return str(path.name)


def _run_git(args: Sequence[str]) -> str:
    try:
        return subprocess.check_output(list(args), stderr=subprocess.STDOUT, text=True).strip()
    except Exception as e:  # pragma: no cover
        return f"<error: {e}>"


def _plot_ratio_csv(*, csv_path: Path, out_png: Path, title: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: E402

    zs = []
    ratio = []
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            zs.append(float(row["z"]))
            ratio.append(float(row["ratio"]))

    fig, ax = plt.subplots(figsize=(7.2, 4.8), constrained_layout=True)
    ax.axhline(1.0, color="#444444", linestyle=":", linewidth=2.0, label="GR baseline (ratio=1)")
    ax.plot(zs, ratio, label="example modification", linewidth=2.5)
    ax.set_xlabel("z")
    ax.set_ylabel("d_L^GW / d_L^EM")
    ax.set_title(title)
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=160)
    plt.close(fig)


def _lcdm_planck_like_history(*, H0_km_s_Mpc: float, Omega_m: float) -> FlatLambdaCDMHistory:
    H0_si = H0_to_SI(float(H0_km_s_Mpc))
    Omega_L = 1.0 - float(Omega_m)
    return FlatLambdaCDMHistory(H0=float(H0_si), Omega_m=float(Omega_m), Omega_Lambda=float(Omega_L))


def run(
    *,
    out_dir: Path,
    mode: str,
    z_max: float,
    dz: float,
    n_int: int,
    H0_km_s_Mpc: float,
    Omega_m: float,
    # xi0_n mode
    xi0: float,
    xi_n: float,
    # friction mode
    delta0: float,
    alphaM0: float,
) -> Dict[str, Any]:
    out_dir = out_dir.resolve()
    tables_dir = out_dir / "tables"
    figs_dir = out_dir / "figures"
    _ensure_dir(tables_dir)
    _ensure_dir(figs_dir)

    mode = str(mode).strip()
    if mode not in ("xi0_n", "friction"):
        raise ValueError("mode must be one of: xi0_n, friction")
    z_max = float(z_max)
    dz = float(dz)
    n_int = int(n_int)
    if not (z_max > 0 and dz > 0):
        raise ValueError("Require z_max>0 and dz>0")

    hist = _lcdm_planck_like_history(H0_km_s_Mpc=float(H0_km_s_Mpc), Omega_m=float(Omega_m))

    # Select ratio model.
    ratio_label = ""
    ratio_fn: Callable[[float], float]
    model_meta: Dict[str, Any] = {}

    if mode == "xi0_n":
        xi0 = float(xi0)
        xi_n = float(xi_n)
        ratio_label = f"Xi0={xi0:g}, n={xi_n:g}"

        def ratio_fn(z: float) -> float:
            return float(Xi_of_z(float(z), Xi0=float(xi0), n=float(xi_n)))

        model_meta = {
            "mode": "xi0_n",
            "xi0": float(xi0),
            "xi_n": float(xi_n),
            "definition": "Xi(z)=Xi0+(1-Xi0)/(1+z)^n; dL_GW=Xi*dL_EM",
        }
    else:
        delta0 = float(delta0)
        alphaM0 = float(alphaM0)
        if abs(delta0) > 0.0 and abs(alphaM0) > 0.0:
            raise ValueError("Provide at most one of delta0 or alphaM0 for mode=friction")
        if abs(delta0) == 0.0 and abs(alphaM0) == 0.0:
            ratio_label = "GR (delta=0)"
        elif abs(alphaM0) > 0.0:
            ratio_label = f"alphaM0={alphaM0:g} (const)"
        else:
            ratio_label = f"delta0={delta0:g} (const)"

        def delta_const(z: float) -> float:
            return float(delta0)

        def alphaM_const(z: float) -> float:
            return float(alphaM0)

        def ratio_fn(z: float) -> float:
            if abs(alphaM0) > 0.0:
                return float(gw_distance_ratio(float(z), alphaM_of_z=alphaM_const, n=int(n_int)))
            if abs(delta0) > 0.0:
                return float(gw_distance_ratio(float(z), delta_of_z=delta_const, n=int(n_int)))
            return 1.0

        model_meta = {
            "mode": "friction",
            "delta0_const": float(delta0),
            "alphaM0_const": float(alphaM0),
            "definition_delta": "dL_GW/dL_EM = exp(+int_0^z delta(z')/(1+z') dz')",
            "definition_alphaM": "dL_GW/dL_EM = exp(0.5*int_0^z alphaM(z')/(1+z') dz')",
        }

    csv_path = tables_dir / "gw_xi_vs_z.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "z",
            "Xi_z",
            "dL_em_Mpc",
            "dL_gw_Mpc",
            "ratio",
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        z = 0.0
        while z <= z_max + 1e-12:
            ratio = float(ratio_fn(float(z)))
            dL_em_m = float(D_L_flat(z=float(z), H_of_z=hist.H, n=10_000))
            dL_em_Mpc = float(dL_em_m / float(MPC_SI))
            dL_gw_Mpc = float(ratio) * float(dL_em_Mpc)
            w.writerow(
                {
                    "z": f"{float(z):.6g}",
                    "Xi_z": f"{float(ratio):.16g}",
                    "dL_em_Mpc": f"{float(dL_em_Mpc):.16g}",
                    "dL_gw_Mpc": f"{float(dL_gw_Mpc):.16g}",
                    "ratio": f"{float(ratio):.16g}",
                }
            )
            z += dz

    fig_path = figs_dir / "gw_dL_ratio_vs_z.png"
    _plot_ratio_csv(
        csv_path=csv_path,
        out_png=fig_path,
        title=f"E3 diagnostic: dL_GW/dL_EM vs z ({mode}; {ratio_label})",
    )

    manifest: Dict[str, Any] = {
        "diagnostic_only": True,
        "kind": "gw_standard_sirens_diagnostic",
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "git_commit": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"]),
        "git_branch": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "--abbrev-ref", "HEAD"]),
        "git_dirty": bool(_run_git(["git", "-C", str(REPO_ROOT), "status", "--porcelain=v1"]).strip()),
        "em_background": {
            "history": "FlatLambdaCDMHistory (late-time, no radiation; for illustrative dL_em only)",
            "H0_km_s_Mpc": float(H0_km_s_Mpc),
            "Omega_m": float(Omega_m),
        },
        "model": {
            **model_meta,
            "z_grid": {"z_max": float(z_max), "dz": float(dz)},
            "integration": {"n": int(n_int)},
        },
        "outputs": {
            "outdir": _relpath(out_dir),
            "csv": _relpath(csv_path),
            "figure": _relpath(fig_path),
        },
        "notes": [
            "Diagnostic-only: GW standard-sirens modified-propagation examples (not part of submission claims).",
            "The EM background dL_em is illustrative; the key output is the ratio dL_GW/dL_EM.",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return manifest


def main(argv: Optional[Sequence[str]] = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", type=Path, default=Path("v11.0.0/results/diagnostic_gw_standard_sirens"))
    ap.add_argument("--mode", choices=("xi0_n", "friction"), default="xi0_n")
    ap.add_argument("--z-max", type=float, default=5.0)
    ap.add_argument("--dz", type=float, default=0.05)
    ap.add_argument("--n-int", type=int, default=10_000)
    ap.add_argument("--H0", type=float, default=67.4, help="EM background H0 (km/s/Mpc) for illustrative dL_em.")
    ap.add_argument("--Omega-m", dest="Omega_m", type=float, default=0.315, help="EM background Omega_m for illustrative dL_em.")

    # xi0_n mode knobs.
    ap.add_argument("--xi0", type=float, default=0.9, help="High-z asymptote Xi0 in Xi(z) parameterization.")
    ap.add_argument("--xi-n", dest="xi_n", type=float, default=2.0, help="Exponent n in Xi(z)=Xi0+(1-Xi0)/(1+z)^n.")

    # friction mode knobs.
    ap.add_argument("--delta0", type=float, default=0.1, help="Const delta0 for friction mode (set to 0 for GR).")
    ap.add_argument("--alphaM0", type=float, default=0.0, help="Const alphaM0 for friction mode (alternative to delta0).")
    args = ap.parse_args(argv)

    run(
        out_dir=args.outdir,
        mode=str(args.mode),
        z_max=float(args.z_max),
        dz=float(args.dz),
        n_int=int(args.n_int),
        H0_km_s_Mpc=float(args.H0),
        Omega_m=float(args.Omega_m),
        xi0=float(args.xi0),
        xi_n=float(args.xi_n),
        delta0=float(args.delta0),
        alphaM0=float(args.alphaM0),
    )


if __name__ == "__main__":  # pragma: no cover
    main()

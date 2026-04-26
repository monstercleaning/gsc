#!/usr/bin/env python3
"""Distance-duality (Etherington reciprocity) diagnostic: fit epsilon_dd from SN+BAO.

Diagnostic-only / out of submission scope.

We introduce a 1-parameter deviation from distance duality:

  D_L(z) = (1+z) * D_M(z) * (1+z)^{epsilon_dd}

Equivalently for distance modulus:

  mu_th(z; epsilon_dd) = mu_th(z; 0) + 5 * epsilon_dd * log10(1+z)

We profile analytically over:
- SN absolute magnitude nuisance delta_M (additive in mu)
- BAO sound-horizon nuisance r_d (multiplicative in D/rd; profiled in BAODataset)
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

from gsc.datasets.bao import BAODataset  # noqa: E402
from gsc.datasets.sn import SNDataset  # noqa: E402
from gsc.measurement_model import (  # noqa: E402
    FlatLambdaCDMHistory,
    GSCTransitionHistory,
    H0_to_SI,
    MPC_SI,
    PowerLawHistory,
    distance_modulus_flat,
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


def _epsilon_mu_shift(z: float, epsilon_dd: float) -> float:
    """Return additive shift in mu_th due to epsilon_dd."""
    if z < -1.0:
        raise ValueError("Require z >= -1")
    # D_L -> D_L * (1+z)^{epsilon_dd}  =>  mu -> mu + 5*epsilon_dd*log10(1+z).
    return 5.0 * float(epsilon_dd) * math.log10(1.0 + float(z))


@dataclass(frozen=True)
class SNProfileQuadratic:
    """Quadratic SN chi^2(eps) after profiling delta_M.

    With r0(eps) = (mu_obs - mu_th0) - eps*s, and delta_M profiled:
      chi2(eps) = chi2_0 - 2 eps chi2_1 + eps^2 chi2_2
      delta_M(eps) = d0 - eps*d1
    """

    chi2_0: float
    chi2_1: float
    chi2_2: float
    d0: float
    d1: float

    def eval(self, eps: float) -> Tuple[float, float]:
        e = float(eps)
        chi2 = float(self.chi2_0) - 2.0 * e * float(self.chi2_1) + (e * e) * float(self.chi2_2)
        delta_M = float(self.d0) - e * float(self.d1)
        return (float(chi2), float(delta_M))


def _prepare_sn_profile_quadratic(
    *,
    sn: SNDataset,
    model,
    n_mu: int,
) -> SNProfileQuadratic:
    """Precompute SN chi^2(epsilon_dd) as a quadratic after profiling delta_M."""
    if n_mu < 256:
        raise ValueError("n_mu too small")
    zs = sn.z
    if len(zs) == 0:
        raise ValueError("Empty SN dataset")

    mu0 = [distance_modulus_flat(z=float(z), H_of_z=model.H, n=int(n_mu)) for z in zs]
    r00_list = [float(mu_obs) - float(mu_pred) for (mu_obs, mu_pred) in zip(sn.mu, mu0)]
    s_list = [_epsilon_mu_shift(float(z), 1.0) for z in zs]  # s = 5*log10(1+z)
    npts = len(r00_list)

    if sn.cov is not None:
        cov = sn.cov
        if not hasattr(cov, "shape"):
            cov = np.asarray(cov, dtype=float)
        if cov.shape != (npts, npts):
            raise ValueError(f"SN covariance shape mismatch: got {cov.shape}, expected {(npts, npts)}")

        r00 = np.asarray(r00_list, dtype=float)
        s = np.asarray(s_list, dtype=float)
        ones = np.ones(npts, dtype=float)
        L = np.linalg.cholesky(cov)

        def solve_cov(b):
            y = np.linalg.solve(L, b)
            return np.linalg.solve(L.T, y)

        x_r00 = solve_cov(r00)  # C^{-1} r00
        x_s = solve_cov(s)  # C^{-1} s
        u = solve_cov(ones)  # C^{-1} 1
        denom = float(np.dot(ones, u))
        if not (denom > 0 and math.isfinite(denom)):
            raise ValueError("Non-positive 1^T C^{-1} 1 in SN profiling")
        d0 = float(np.dot(ones, x_r00) / denom)
        d1 = float(np.dot(ones, x_s) / denom)

        a = r00 - d0 * ones
        b = s - d1 * ones
        x_a = solve_cov(a)
        x_b = solve_cov(b)
        chi2_0 = float(np.dot(a, x_a))
        chi2_1 = float(np.dot(a, x_b))
        chi2_2 = float(np.dot(b, x_b))
        return SNProfileQuadratic(chi2_0=float(chi2_0), chi2_1=float(chi2_1), chi2_2=float(chi2_2), d0=float(d0), d1=float(d1))

    # Diagonal mode.
    sig = sn.sigma_mu
    if len(sig) != npts:
        raise ValueError("sigma_mu length mismatch")
    w = np.asarray([1.0 / (float(s) * float(s)) for s in sig], dtype=float)
    r00 = np.asarray(r00_list, dtype=float)
    s = np.asarray(s_list, dtype=float)
    denom = float(np.sum(w))
    if not (denom > 0 and math.isfinite(denom)):
        raise ValueError("Invalid SN weights")
    d0 = float(np.sum(w * r00) / denom)
    d1 = float(np.sum(w * s) / denom)
    a = r00 - d0
    b = s - d1
    chi2_0 = float(np.sum(w * a * a))
    chi2_1 = float(np.sum(w * a * b))
    chi2_2 = float(np.sum(w * b * b))
    return SNProfileQuadratic(chi2_0=float(chi2_0), chi2_1=float(chi2_1), chi2_2=float(chi2_2), d0=float(d0), d1=float(d1))


@dataclass(frozen=True)
class ScanRow:
    epsilon_dd: float
    chi2_total: float
    chi2_sn: float
    chi2_bao: float
    delta_M_best: float
    rd_Mpc_best: float

    def as_csv_dict(self) -> Dict[str, str]:
        def f(x: float) -> str:
            if not math.isfinite(float(x)):
                return ""
            return f"{float(x):.16g}"

        return {
            "epsilon_dd": f(self.epsilon_dd),
            "chi2_total": f(self.chi2_total),
            "chi2_sn": f(self.chi2_sn),
            "chi2_bao": f(self.chi2_bao),
            "delta_M_best": f(self.delta_M_best),
            "rd_Mpc_best": f(self.rd_Mpc_best),
        }


def run(
    *,
    out_dir: Path,
    sn_csv: Path,
    sn_cov: Optional[Path],
    bao_csv: Path,
    model_name: str,
    H0_km_s_Mpc: float,
    Omega_m: float,
    p: float,
    z_transition: float,
    eps_min: float,
    eps_max: float,
    eps_step: float,
    n_mu: int = 2000,
    n_bao: int = 10_000,
) -> Dict[str, Any]:
    out_dir = out_dir.resolve()
    tables_dir = out_dir / "tables"
    figs_dir = out_dir / "figures"
    _ensure_dir(tables_dir)
    _ensure_dir(figs_dir)

    if not (eps_step > 0 and eps_max >= eps_min):
        raise ValueError("Require eps_step>0 and eps_max>=eps_min")

    # Load datasets.
    if sn_cov is None:
        sn = SNDataset.from_csv(sn_csv)
    else:
        sn = SNDataset.from_csv_and_cov(sn_csv, sn_cov)
    bao = BAODataset.from_csv(bao_csv)

    # Select history.
    H0 = H0_to_SI(float(H0_km_s_Mpc))
    name = str(model_name).strip().lower()
    if name == "lcdm":
        hist = FlatLambdaCDMHistory(H0=H0, Omega_m=float(Omega_m), Omega_Lambda=float(1.0 - float(Omega_m)))
    elif name in ("gsc_transition", "gsc-transition"):
        hist = GSCTransitionHistory(
            H0=H0,
            Omega_m=float(Omega_m),
            Omega_Lambda=float(1.0 - float(Omega_m)),
            p=float(p),
            z_transition=float(z_transition),
        )
    elif name in ("gsc_powerlaw", "gsc-powerlaw", "powerlaw"):
        hist = PowerLawHistory(H0=H0, p=float(p))
    else:
        raise ValueError(f"Unknown model: {model_name!r}")

    rows: List[ScanRow] = []
    best = (float("inf"), float("nan"), float("nan"))  # chi2, eps, rd_Mpc

    # Precompute dataset-dependent pieces once:
    # - SN chi^2(eps) is quadratic after profiling delta_M analytically.
    # - BAO chi^2 is independent of epsilon_dd (epsilon only deforms D_L, not D_M).
    sn_quad = _prepare_sn_profile_quadratic(sn=sn, model=hist, n_mu=int(n_mu))
    bao_res = bao.chi2(hist, n=int(n_bao))
    chi2_bao = float(bao_res.chi2)
    rd_m = float(bao_res.params.get("rd_m", float("nan")))
    rd_Mpc = float(rd_m / float(MPC_SI)) if (rd_m > 0 and math.isfinite(rd_m)) else float("nan")

    n = int(math.floor((float(eps_max) - float(eps_min)) / float(eps_step))) + 1
    for i in range(int(n)):
        eps = float(eps_min) + float(i) * float(eps_step)
        if eps > float(eps_max) + 1e-15:
            break

        chi2_sn, delta_M = sn_quad.eval(float(eps))
        chi2_tot = float(chi2_sn) + float(chi2_bao)
        rows.append(
            ScanRow(
                epsilon_dd=float(eps),
                chi2_total=float(chi2_tot),
                chi2_sn=float(chi2_sn),
                chi2_bao=float(chi2_bao),
                delta_M_best=float(delta_M),
                rd_Mpc_best=float(rd_Mpc),
            )
        )
        if chi2_tot < best[0]:
            best = (float(chi2_tot), float(eps), float(rd_Mpc))

    if not rows:
        raise ValueError("Empty epsilon grid (no rows)")

    # Write table.
    csv_path = tables_dir / "chi2_vs_epsilon_dd.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].as_csv_dict().keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r.as_csv_dict())

    # Plot.
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: E402

    eps = np.asarray([r.epsilon_dd for r in rows], dtype=float)
    chi2 = np.asarray([r.chi2_total for r in rows], dtype=float)
    chi2_min = float(np.min(chi2))
    fig, ax = plt.subplots(figsize=(7.6, 4.8), constrained_layout=True)
    ax.plot(eps, chi2 - chi2_min, linewidth=2.0)
    ax.axvline(0.0, color="k", alpha=0.25, linewidth=1.0)
    ax.set_xlabel("epsilon_dd")
    ax.set_ylabel("Δchi² (relative to best-fit)")
    ax.set_title("Distance duality diagnostic: SN+BAO vs epsilon_dd (profiled nuisances)")
    ax.grid(True, alpha=0.25)
    fig_path = figs_dir / "chi2_vs_epsilon_dd.png"
    fig.savefig(fig_path, dpi=160)
    plt.close(fig)

    # Δchi² at eps=0 for reporting (nearest grid point).
    idx0 = int(np.argmin(np.abs(eps - 0.0)))
    delta_chi2_eps0 = float(chi2[idx0] - chi2_min)

    manifest: Dict[str, Any] = {
        "diagnostic_only": True,
        "kind": "distance_duality_diagnostic",
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "git_commit": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"]),
        "git_branch": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "--abbrev-ref", "HEAD"]),
        "git_dirty": bool(_run_git(["git", "-C", str(REPO_ROOT), "status", "--porcelain=v1"]).strip()),
        "inputs": {
            "sn_csv": _relpath(sn_csv),
            "sn_cov": (_relpath(sn_cov) if sn_cov is not None else None),
            "bao_csv": _relpath(bao_csv),
        },
        "model": {
            "name": str(name),
            "H0_km_s_Mpc": float(H0_km_s_Mpc),
            "Omega_m": float(Omega_m),
            "p": float(p),
            "z_transition": float(z_transition),
        },
        "definition": {
            "D_L_relation": "D_L(z) = (1+z) * D_M(z) * (1+z)^{epsilon_dd}",
            "mu_shift": "mu_th(z; eps) = mu_th(z; 0) + 5*eps*log10(1+z)",
            "nuisances_profiled": ["SN delta_M (additive)", "BAO r_d (multiplicative)"],
        },
        "grid": {"eps_min": float(eps_min), "eps_max": float(eps_max), "eps_step": float(eps_step), "n": int(len(rows))},
        "numerics": {"n_mu": int(n_mu), "n_bao": int(n_bao)},
        "best_fit": {"epsilon_dd": float(best[1]), "chi2_total": float(best[0]), "rd_Mpc_best": float(best[2])},
        "delta_chi2_eps0": float(delta_chi2_eps0),
        "outputs": {"outdir": _relpath(out_dir), "csv": _relpath(csv_path), "fig": _relpath(fig_path)},
        "notes": [
            "Diagnostic-only: tests Etherington distance duality as a fitted epsilon_dd from SN+BAO consistency.",
            "Not part of submission scope; does not modify canonical late-time outputs or bundles.",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return manifest


def main(argv: Optional[Sequence[str]] = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", type=Path, default=Path("v11.0.0/results/diagnostic_distance_duality"))

    ap.add_argument("--sn", type=Path, default=V101_DIR / "data/sn/pantheon_plus_shoes/pantheon_plus_shoes_hflow_mu.csv")
    ap.add_argument("--sn-cov", type=Path, default=V101_DIR / "data/sn/pantheon_plus_shoes/Pantheon+SH0ES_STAT+SYS.cov")
    ap.add_argument("--sn-no-cov", action="store_true", help="Use diagonal SN errors from CSV (ignore --sn-cov).")
    ap.add_argument("--bao", type=Path, default=V101_DIR / "data/bao/bao_6df_mgs_boss_dr12_cov6_plus_lya_qso.csv")

    ap.add_argument("--model", type=str, default="gsc_transition", choices=["lcdm", "gsc_transition", "gsc_powerlaw"])
    ap.add_argument("--H0", type=float, default=67.4)
    ap.add_argument("--Omega-m", dest="Omega_m", type=float, default=0.315)
    ap.add_argument("--gsc-p", dest="p", type=float, default=0.6)
    ap.add_argument("--gsc-ztrans", dest="z_transition", type=float, default=1.8)

    ap.add_argument("--eps-min", type=float, default=-0.20)
    ap.add_argument("--eps-max", type=float, default=0.20)
    ap.add_argument("--eps-step", type=float, default=0.002)
    ap.add_argument("--n-mu", type=int, default=2000)
    ap.add_argument("--n-bao", type=int, default=10_000)

    args = ap.parse_args(argv)

    sn_cov = None if bool(args.sn_no_cov) else Path(args.sn_cov)
    run(
        out_dir=Path(args.outdir),
        sn_csv=Path(args.sn),
        sn_cov=sn_cov,
        bao_csv=Path(args.bao),
        model_name=str(args.model),
        H0_km_s_Mpc=float(args.H0),
        Omega_m=float(args.Omega_m),
        p=float(args.p),
        z_transition=float(args.z_transition),
        eps_min=float(args.eps_min),
        eps_max=float(args.eps_max),
        eps_step=float(args.eps_step),
        n_mu=int(args.n_mu),
        n_bao=int(args.n_bao),
    )


if __name__ == "__main__":  # pragma: no cover
    main()

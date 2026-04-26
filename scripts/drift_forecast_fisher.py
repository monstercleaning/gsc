#!/usr/bin/env python3
"""Redshift-drift forecast (diagnostic-only): significance vs baseline years with a systematic floor.

This script answers "when will we know?" at a very coarse level:
it compares the predicted Sandage–Loeb velocity drift Δv(z) between two
background histories and computes a simple Fisher-style significance:

  chi2(years) = Σ_i [ (Δv_A(z_i; years) - Δv_B(z_i; years)) / σ_tot ]^2
  significance = sqrt(chi2)

where σ_tot = sqrt(σ_stat^2 + σ_sys^2) is treated as a per-bin uncertainty on Δv.

Notes / scope:
- Diagnostic-only; not part of submission claims.
- This is a "floor-aware" scaling toy, not an exposure-time calculator.
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

from gsc.measurement_model import (  # noqa: E402
    FlatLambdaCDMHistory,
    GSCTransitionHistory,
    H0_to_SI,
    PowerLawHistory,
    delta_v_cm_s,
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


def _parse_grid(spec: str) -> List[float]:
    s = str(spec).strip()
    if not s:
        raise ValueError("empty grid spec")
    if ":" in s:
        parts = [p.strip() for p in s.split(":")]
        if len(parts) != 3:
            raise ValueError("range spec must be 'start:stop:step'")
        start, stop, step = (float(parts[0]), float(parts[1]), float(parts[2]))
        if step <= 0:
            raise ValueError("step must be positive")
        out: List[float] = []
        v = start
        tol = 1e-12 * max(1.0, abs(stop))
        while v <= stop + tol:
            out.append(float(v))
            v += step
        if not out:
            raise ValueError("empty range after parsing")
        return out
    return [float(tok.strip()) for tok in s.split(",") if tok.strip()]


def _build_model(
    *,
    name: str,
    H0_km_s_Mpc: float,
    Omega_m: float,
    p: float,
    z_transition: float,
):
    n = str(name).strip().lower()
    H0_si = H0_to_SI(float(H0_km_s_Mpc))
    if n == "lcdm":
        Om = float(Omega_m)
        return FlatLambdaCDMHistory(H0=H0_si, Omega_m=Om, Omega_Lambda=1.0 - Om)
    if n in ("gsc_transition", "gsc-transition"):
        Om = float(Omega_m)
        return GSCTransitionHistory(
            H0=H0_si,
            Omega_m=Om,
            Omega_Lambda=1.0 - Om,
            p=float(p),
            z_transition=float(z_transition),
        )
    if n in ("gsc_powerlaw", "gsc-powerlaw", "powerlaw"):
        return PowerLawHistory(H0=H0_si, p=float(p))
    raise ValueError(f"unknown model: {name!r}")


def _sigma_total(*, sigma_stat_cm_s: float, sigma_sys_cm_s: float) -> float:
    ss = float(sigma_stat_cm_s)
    sy = float(sigma_sys_cm_s)
    if ss <= 0 or sy < 0:
        raise ValueError("Require sigma_stat>0 and sigma_sys>=0")
    return math.sqrt(ss * ss + sy * sy)


@dataclass(frozen=True)
class Row:
    scenario: str
    years: float
    chi2: float
    significance_sigma: float
    sigma_stat_cm_s: float
    sigma_sys_cm_s: float
    sigma_tot_cm_s: float

    def as_csv_row(self) -> Dict[str, str]:
        def f(x: float) -> str:
            if not math.isfinite(float(x)):
                return ""
            return f"{float(x):.16g}"

        return {
            "scenario": str(self.scenario),
            "years": f(self.years),
            "chi2": f(self.chi2),
            "significance_sigma": f(self.significance_sigma),
            "sigma_stat_cm_s": f(self.sigma_stat_cm_s),
            "sigma_sys_cm_s": f(self.sigma_sys_cm_s),
            "sigma_tot_cm_s": f(self.sigma_tot_cm_s),
        }


def run(
    *,
    out_dir: Path,
    z_targets: Sequence[float],
    years_list: Sequence[float],
    sigma_stat_cm_s: float,
    sigma_sys_cm_s_list: Sequence[float],
    model_a: str,
    model_b: str,
    H0_km_s_Mpc: float,
    Omega_m: float,
    p: float,
    z_transition: float,
) -> Dict[str, Any]:
    out_dir = out_dir.resolve()
    tables_dir = out_dir / "tables"
    figs_dir = out_dir / "figures"
    _ensure_dir(tables_dir)
    _ensure_dir(figs_dir)

    zs = [float(z) for z in z_targets]
    if not zs:
        raise ValueError("Empty z_targets")
    if any(z < 0 for z in zs):
        raise ValueError("Require z>=0 for z_targets")

    years = [float(y) for y in years_list]
    if not years:
        raise ValueError("Empty years_list")
    if any(y <= 0 for y in years):
        raise ValueError("Require years>0")

    sigma_sys_list = [float(x) for x in sigma_sys_cm_s_list]
    if not sigma_sys_list:
        raise ValueError("Empty sigma_sys list")
    if any(s < 0 for s in sigma_sys_list):
        raise ValueError("Require sigma_sys>=0")

    hist_a = _build_model(
        name=str(model_a),
        H0_km_s_Mpc=float(H0_km_s_Mpc),
        Omega_m=float(Omega_m),
        p=float(p),
        z_transition=float(z_transition),
    )
    hist_b = _build_model(
        name=str(model_b),
        H0_km_s_Mpc=float(H0_km_s_Mpc),
        Omega_m=float(Omega_m),
        p=float(p),
        z_transition=float(z_transition),
    )
    H0_si = float(H0_to_SI(float(H0_km_s_Mpc)))

    # Precompute vdot difference per z (cm/s per year) to avoid recomputing dv repeatedly.
    dv_diff_per_year: List[float] = []
    for z in zs:
        dv_a_1y = float(delta_v_cm_s(z=float(z), years=1.0, H0=H0_si, H_of_z=hist_a.H))
        dv_b_1y = float(delta_v_cm_s(z=float(z), years=1.0, H0=H0_si, H_of_z=hist_b.H))
        dv_diff_per_year.append(float(dv_b_1y - dv_a_1y))

    rows: List[Row] = []
    for sigma_sys in sigma_sys_list:
        sigma_tot = _sigma_total(sigma_stat_cm_s=float(sigma_stat_cm_s), sigma_sys_cm_s=float(sigma_sys))
        scenario = f"sigstat={float(sigma_stat_cm_s):g}cm/s sigsys={float(sigma_sys):g}cm/s"
        for y in years:
            chi2 = 0.0
            for dv1 in dv_diff_per_year:
                dv = float(dv1) * float(y)
                chi2 += (dv / sigma_tot) ** 2
            sig = math.sqrt(float(chi2))
            rows.append(
                Row(
                    scenario=str(scenario),
                    years=float(y),
                    chi2=float(chi2),
                    significance_sigma=float(sig),
                    sigma_stat_cm_s=float(sigma_stat_cm_s),
                    sigma_sys_cm_s=float(sigma_sys),
                    sigma_tot_cm_s=float(sigma_tot),
                )
            )

    # Write table.
    table_path = tables_dir / "significance_vs_years.csv"
    with table_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].as_csv_row().keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r.as_csv_row())

    # Plot.
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # noqa: E402

        fig, ax = plt.subplots(figsize=(7.6, 4.8), constrained_layout=True)
        for sigma_sys in sigma_sys_list:
            sigma_tot = _sigma_total(sigma_stat_cm_s=float(sigma_stat_cm_s), sigma_sys_cm_s=float(sigma_sys))
            scenario = f"sys={float(sigma_sys):g} cm/s  (tot={float(sigma_tot):.3g})"
            xs: List[float] = []
            ys_plot: List[float] = []
            for y in years:
                chi2 = 0.0
                for dv1 in dv_diff_per_year:
                    dv = float(dv1) * float(y)
                    chi2 += (dv / sigma_tot) ** 2
                xs.append(float(y))
                ys_plot.append(math.sqrt(float(chi2)))
            ax.plot(xs, ys_plot, linewidth=2.0, label=scenario)
        ax.set_xlabel("baseline years")
        ax.set_ylabel("forecast significance (σ)")
        ax.set_title("Redshift-drift forecast: GSC vs LCDM (diagnostic-only)")
        ax.grid(True, alpha=0.25)
        ax.legend(frameon=False)
        fig_path = figs_dir / "significance_vs_years.png"
        fig.savefig(fig_path, dpi=160)
        plt.close(fig)
    except Exception:  # pragma: no cover
        fig_path = None

    manifest: Dict[str, Any] = {
        "diagnostic_only": True,
        "kind": "drift_forecast_fisher",
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "git_commit": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"]),
        "git_branch": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "--abbrev-ref", "HEAD"]),
        "git_dirty": bool(_run_git(["git", "-C", str(REPO_ROOT), "status", "--porcelain=v1"]).strip()),
        "models": {
            "model_a": str(model_a),
            "model_b": str(model_b),
            "H0_km_s_Mpc": float(H0_km_s_Mpc),
            "Omega_m": float(Omega_m),
            "p": float(p),
            "z_transition": float(z_transition),
        },
        "inputs": {
            "z_targets": [float(z) for z in zs],
            "years_list": [float(y) for y in years],
            "sigma_stat_cm_s": float(sigma_stat_cm_s),
            "sigma_sys_cm_s_list": [float(s) for s in sigma_sys_list],
            "sigma_tot_cm_s_list": [
                float(_sigma_total(sigma_stat_cm_s=float(sigma_stat_cm_s), sigma_sys_cm_s=float(s))) for s in sigma_sys_list
            ],
        },
        "dv_diff_cm_s_per_year": [float(x) for x in dv_diff_per_year],
        "outputs": {
            "outdir": _relpath(out_dir),
            "table": _relpath(table_path),
            "figure": (_relpath(fig_path) if fig_path is not None else None),
        },
        "notes": [
            "Diagnostic-only: simple Fisher-style forecast for redshift drift with a systematic floor.",
            "Not an exposure-time calculator; sigma_stat and sigma_sys are treated as per-bin Δv uncertainties.",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return manifest


def main(argv: Optional[Sequence[str]] = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", type=Path, default=Path("v11.0.0/results/diagnostic_drift_forecast"))

    ap.add_argument("--z-targets", type=str, default="2.0,2.5,3.0,3.5,4.5", help="comma list or start:stop:step")
    ap.add_argument("--years", type=str, default="1:40:1", help="comma list or start:stop:step")

    ap.add_argument("--sigma-stat-cm-s", type=float, default=1.0)
    ap.add_argument(
        "--sigma-sys-cm-s",
        type=float,
        action="append",
        default=None,
        help="systematic floor (cm/s) per bin; repeat to plot multiple scenarios",
    )

    ap.add_argument("--model-a", type=str, default="lcdm", choices=["lcdm", "gsc_transition", "gsc_powerlaw"])
    ap.add_argument("--model-b", type=str, default="gsc_transition", choices=["lcdm", "gsc_transition", "gsc_powerlaw"])

    ap.add_argument("--H0", type=float, default=67.4)
    ap.add_argument("--Omega-m", dest="Omega_m", type=float, default=0.315)
    ap.add_argument("--gsc-p", dest="p", type=float, default=0.6)
    ap.add_argument("--gsc-ztrans", dest="z_transition", type=float, default=1.8)

    args = ap.parse_args(argv)
    sigma_sys_list = args.sigma_sys_cm_s if args.sigma_sys_cm_s is not None else [1.0]
    run(
        out_dir=Path(args.outdir),
        z_targets=_parse_grid(str(args.z_targets)),
        years_list=_parse_grid(str(args.years)),
        sigma_stat_cm_s=float(args.sigma_stat_cm_s),
        sigma_sys_cm_s_list=[float(s) for s in sigma_sys_list],
        model_a=str(args.model_a),
        model_b=str(args.model_b),
        H0_km_s_Mpc=float(args.H0),
        Omega_m=float(args.Omega_m),
        p=float(args.p),
        z_transition=float(args.z_transition),
    )


if __name__ == "__main__":  # pragma: no cover
    main()


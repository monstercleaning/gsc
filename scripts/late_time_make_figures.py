#!/usr/bin/env python3
"""Generate paper-ready late-time figures from best-fit JSONs (v11.0.0)."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Tuple

from _outdir import resolve_outdir

# Allow running from repo root: add v11.0.0/ to import path.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.datasets.bao import BAOBlock1D, BAOBlock2D, BAOBlockND, BAODataset  # noqa: E402
from gsc.datasets.drift import DriftDataset  # noqa: E402
from gsc.datasets.sn import SNDataset  # noqa: E402
from gsc.measurement_model import (  # noqa: E402
    C_SI,
    MPC_SI,
    PC_SI,
    SEC_PER_YR,
    FlatLambdaCDMHistory,
    GSCTransitionHistory,
    H0_to_SI,
    PowerLawHistory,
    z_dot_sandage_loeb,
)


def _require_numpy():
    try:
        import numpy as np  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise SystemExit("numpy is required for late_time_make_figures.py") from e
    return np


def _model_from_bestfit(model_name: str, params: Dict[str, float]):
    H0_si = H0_to_SI(params["H0"])
    if model_name == "lcdm":
        Om = float(params["Omega_m"])
        Ol = 1.0 - Om
        return FlatLambdaCDMHistory(H0=H0_si, Omega_m=Om, Omega_Lambda=Ol)
    if model_name == "gsc_powerlaw":
        return PowerLawHistory(H0=H0_si, p=float(params["p"]))
    if model_name == "gsc_transition":
        Om = float(params["Omega_m"])
        Ol = 1.0 - Om
        return GSCTransitionHistory(
            H0=H0_si,
            Omega_m=Om,
            Omega_Lambda=Ol,
            p=float(params["p"]),
            z_transition=float(params["z_transition"]),
        )
    raise ValueError(f"Unknown model {model_name!r}")


def _build_dm_interpolator(model, *, z_max: float, n_grid: int):
    np = _require_numpy()
    z_grid = np.linspace(0.0, float(z_max), int(n_grid) + 1, dtype=float)
    inv_H = np.empty_like(z_grid)
    for i, z in enumerate(z_grid):
        inv_H[i] = 1.0 / float(model.H(float(z)))
    dz = float(z_grid[1] - z_grid[0])
    cum = np.empty_like(z_grid)
    cum[0] = 0.0
    cum[1:] = np.cumsum(0.5 * (inv_H[:-1] + inv_H[1:]) * dz)
    chi_grid = float(C_SI) * cum

    def dm(zs):
        return np.interp(zs, z_grid, chi_grid)

    return dm


def _load_fit(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _ensure_mpl_config_dir(out_dir: Path) -> None:
    # Prevent matplotlib from trying to write to global locations.
    if "MPLCONFIGDIR" not in os.environ:
        d = out_dir / ".mplconfig"
        d.mkdir(parents=True, exist_ok=True)
        os.environ["MPLCONFIGDIR"] = str(d)
    # Ensure a non-interactive backend for reproducible, headless runs.
    os.environ.setdefault("MPLBACKEND", "Agg")


def _plot_drift(models: List[Tuple[str, Any]], out_path: Path, *, drift: DriftDataset | None = None) -> None:
    np = _require_numpy()
    import matplotlib.pyplot as plt  # type: ignore

    z = np.linspace(0.0, 5.0, 400)
    baseline_years = 1.0
    per_year = True
    if drift is not None and len(drift.z) > 0:
        if drift.baseline_years_by_row is not None:
            baselines = np.asarray(drift.baseline_years_by_row, dtype=float)
            if baselines.size > 0 and np.allclose(baselines, baselines[0], rtol=0.0, atol=1e-12):
                baseline_years = float(baselines[0])
                per_year = False
        else:
            if float(drift.baseline_years) > 0:
                baseline_years = float(drift.baseline_years)
                per_year = False

    for label, m in models:
        H0 = float(m.H(0.0))
        zdot = np.array([z_dot_sandage_loeb(z=float(zz), H0=H0, H_of_z=m.H) for zz in z], dtype=float)
        dv_cm_s = 100.0 * (float(C_SI) * zdot / (1.0 + z)) * (baseline_years * float(SEC_PER_YR))
        plt.plot(z, dv_cm_s, label=label, lw=2)

    if drift is not None and len(drift.z) > 0:
        z_obs = np.asarray(drift.z, dtype=float)
        dv_obs = np.asarray(drift.dv_cm_s, dtype=float)
        sig = np.asarray(drift.sigma_dv_cm_s, dtype=float)
        if drift.baseline_years_by_row is not None:
            baselines = np.asarray(drift.baseline_years_by_row, dtype=float)
        else:
            baselines = np.full_like(z_obs, float(drift.baseline_years), dtype=float)
        if per_year:
            # Convert to per-year units to match the model curves (baseline_years=1).
            dv_plot = dv_obs / baselines
            sig_plot = sig / baselines
            data_label = f"drift data (per-yr; N={len(z_obs)})"
            ylab = "Δv [cm/s] per 1 yr"
        else:
            dv_plot = dv_obs
            sig_plot = sig
            data_label = f"drift data ({baseline_years:g} yr; N={len(z_obs)})"
            ylab = f"Δv [cm/s] over {baseline_years:g} yr"
        plt.errorbar(
            z_obs,
            dv_plot,
            yerr=sig_plot,
            fmt="o",
            ms=5,
            capsize=2,
            color="k",
            label=data_label,
            zorder=5,
        )

    plt.axvspan(2.0, 5.0, color="0.9", label="high-z discriminant (z~2–5)")
    plt.axhline(0.0, color="k", lw=1)
    plt.xlabel("z")
    if drift is None or len(getattr(drift, "z", ())) == 0:
        plt.ylabel("Δv [cm/s] per 1 yr")
    else:
        plt.ylabel(ylab)
    plt.title("Redshift Drift (Sandage–Loeb)")
    plt.legend(frameon=False)
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=200)
    plt.close()


def _plot_sn_residuals(models: List[Tuple[str, Any, float]], sn: SNDataset, out_path: Path, *, n_grid: int) -> None:
    np = _require_numpy()
    import matplotlib.pyplot as plt  # type: ignore

    z = np.asarray(sn.z, dtype=float)
    mu_obs = np.asarray(sn.mu, dtype=float)
    z_max = float(z.max())

    for label, m, delta_M in models:
        dm_fn = _build_dm_interpolator(m, z_max=z_max, n_grid=n_grid)
        dl = (1.0 + z) * dm_fn(z)
        mu_th = 5.0 * np.log10(dl / (10.0 * float(PC_SI)))
        resid = mu_obs - mu_th - float(delta_M)
        plt.scatter(z, resid, s=6, alpha=0.35, label=label)

    plt.axhline(0.0, color="k", lw=1)
    plt.xlabel("z")
    plt.ylabel("μ_obs − μ_model − ΔM")
    plt.title("SN Ia Residuals (Pantheon+SH0ES Hflow)")
    plt.legend(frameon=False, markerscale=2)
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=200)
    plt.close()


def _plot_bao(models: List[Tuple[str, Any, float]], bao: BAODataset, out_path: Path, *, n_grid: int) -> None:
    np = _require_numpy()
    import matplotlib.pyplot as plt  # type: ignore

    # Collect points by kind.
    pts_dv = []
    pts_dm = []
    pts_dh = []
    errs_dv = []
    errs_dm = []
    errs_dh = []
    z_dv = []
    z_dm = []
    z_dh = []

    for b in bao.blocks:
        if isinstance(b, BAOBlock1D):
            z_dv.append(float(b.z))
            pts_dv.append(float(b.y))
            errs_dv.append(float(b.sigma))
        elif isinstance(b, BAOBlock2D):
            z_dm.append(float(b.z))
            z_dh.append(float(b.z))
            pts_dm.append(float(b.y_dm))
            pts_dh.append(float(b.y_dh))
            errs_dm.append(float(b.sigma_dm))
            errs_dh.append(float(b.sigma_dh))
        else:
            # ND vector: plot with diagonal errors only
            cov = np.asarray(b.cov, dtype=float)
            sig = np.sqrt(np.diag(cov))
            for k, z, y, s in zip(b.kinds, b.zs, b.y, sig):
                kk = str(k).strip().upper()
                if kk == "DV":
                    z_dv.append(float(z))
                    pts_dv.append(float(y))
                    errs_dv.append(float(s))
                elif kk == "DM":
                    z_dm.append(float(z))
                    pts_dm.append(float(y))
                    errs_dm.append(float(s))
                elif kk == "DH":
                    z_dh.append(float(z))
                    pts_dh.append(float(y))
                    errs_dh.append(float(s))

    # Plot three panels.
    fig, axes = plt.subplots(3, 1, figsize=(7, 9), sharex=True)

    def plot_panel(ax, z_obs, y_obs, y_err, kind):
        if not z_obs:
            return
        ax.errorbar(z_obs, y_obs, yerr=y_err, fmt="o", ms=4, capsize=2, label=f"data ({kind})")
        z_grid = np.linspace(0.0, max(z_obs) * 1.05, 300)
        for label, m, rd_m in models:
            dm_fn = _build_dm_interpolator(m, z_max=float(z_grid.max()), n_grid=n_grid)
            if kind == "DV":
                dm = dm_fn(z_grid)
                Hz = np.array([float(m.H(float(zz))) for zz in z_grid], dtype=float)
                dh = float(C_SI) / Hz
                dv = (z_grid * dh * dm * dm) ** (1.0 / 3.0)
                y_pred = dv / float(rd_m)
            elif kind == "DM":
                dm = dm_fn(z_grid)
                y_pred = dm / float(rd_m)
            else:  # DH
                Hz = np.array([float(m.H(float(zz))) for zz in z_grid], dtype=float)
                dh = float(C_SI) / Hz
                y_pred = dh / float(rd_m)
            ax.plot(z_grid, y_pred, lw=2, label=label)
        ax.set_ylabel(f"{kind}/r_d")
        ax.legend(frameon=False)

    plot_panel(axes[0], z_dv, pts_dv, errs_dv, "DV")
    plot_panel(axes[1], z_dm, pts_dm, errs_dm, "DM")
    plot_panel(axes[2], z_dh, pts_dh, errs_dh, "DH")
    axes[2].set_xlabel("z")
    fig.suptitle("BAO Ratios (r_d Free, Best-Fit)")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def _count_fit_params(fit: Dict[str, Any]) -> Tuple[int, int]:
    """Return (k, n_obs) for information criteria.

    k counts *all free parameters* in the fit (model params + profiled nuisances).
    n_obs counts the total number of data points across included datasets.

    Important: the fit JSON's `best.ndof` is an "effective" ndof that already
    subtracts analytically-profiled nuisances (SN ΔM, BAO r_d, and optionally
    H0 when drift profiling is enabled), but it does *not* subtract scanned
    model parameters like Ωm, p, z_transition. Therefore we do *not* use
    `best.ndof` to infer n_obs.
    """
    best = fit.get("best", {})
    parts = best.get("parts", {}) if isinstance(best.get("parts"), dict) else {}
    grid = fit.get("grid", {}) if isinstance(fit.get("grid"), dict) else {}
    profile_H0 = bool(fit.get("profile_H0", False))

    # Free model parameters from the scanned grid.
    k = 0
    for name, vals in grid.items():
        try:
            if isinstance(vals, list) and len(vals) > 1:
                k += 1
        except Exception:
            continue
    # H0 is removed from the grid when profiled; still count it as fitted.
    if profile_H0:
        k += 1

    # Nuisances profiled analytically.
    if isinstance(parts.get("sn"), dict) and ("delta_M" in parts.get("sn", {})):
        k += 1
    if isinstance(parts.get("bao"), dict) and ("rd_m" in parts.get("bao", {})):
        k += 1

    # Total number of observations inferred from per-dataset ndof + whether a
    # nuisance was profiled for that dataset.
    n_obs = 0
    if isinstance(parts.get("sn"), dict) and "ndof" in parts["sn"]:
        nd = int(parts["sn"]["ndof"])
        n_obs += nd + (1 if "delta_M" in parts["sn"] else 0)
    if isinstance(parts.get("bao"), dict) and "ndof" in parts["bao"]:
        nd = int(parts["bao"]["ndof"])
        n_obs += nd + (1 if "rd_m" in parts["bao"] else 0)
    if isinstance(parts.get("drift"), dict) and "ndof" in parts["drift"]:
        nd = int(parts["drift"]["ndof"])
        n_obs += nd + (1 if bool(parts["drift"].get("profile_H0", False)) else 0)
    if isinstance(parts.get("cmb"), dict) and "ndof" in parts["cmb"]:
        n_obs += int(parts["cmb"]["ndof"])
    return int(k), int(n_obs)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit-dir", type=Path, default=ROOT / "results" / "late_time_fit")
    ap.add_argument("--models", default="lcdm,gsc_powerlaw,gsc_transition")
    ap.add_argument("--out-dir", "--outdir", dest="out_dir", type=Path, default=None)
    ap.add_argument("--n-grid", type=int, default=6000)

    # Optional overrides; if not set we use dataset paths from the first fit JSON.
    ap.add_argument("--sn", type=Path, default=None)
    ap.add_argument("--sn-cov", type=Path, default=None)
    ap.add_argument("--bao", type=Path, default=None)
    ap.add_argument("--drift", type=Path, default=None)
    ap.add_argument("--drift-baseline-years", type=float, default=None)

    args = ap.parse_args()
    fit_dir = args.fit_dir
    if args.out_dir is not None:
        out_dir = Path(args.out_dir).expanduser().resolve()
    else:
        out_root = resolve_outdir(None, v101_dir=ROOT)
        out_dir = (out_root / "late_time_figures").resolve()
    print(f"[info] OUTDIR={out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    _ensure_mpl_config_dir(out_dir)

    model_names = [m.strip() for m in args.models.split(",") if m.strip()]
    fits: List[Dict[str, Any]] = []
    skipped: List[Tuple[str, str]] = []
    for m in model_names:
        p = fit_dir / f"{m}_bestfit.json"
        if not p.exists():
            skipped.append((m, f"missing fit JSON: {p.name}"))
            continue
        fit = _load_fit(p)
        best = fit.get("best", {})
        params = best.get("params", {})
        parts = best.get("parts", {})
        if isinstance(parts, dict) and "error" in parts:
            skipped.append((m, f"fit error: {parts.get('error')}"))
            continue
        if not isinstance(params, dict) or "H0" not in params:
            skipped.append((m, "missing best.params.H0"))
            continue
        fits.append(fit)

    for m, reason in skipped:
        print(f"[figures] SKIP {m}: {reason}")
    if not fits:
        raise SystemExit(f"No usable fit JSONs found in {fit_dir}")

    # Load datasets (prefer explicit CLI overrides).
    ds0 = fits[0].get("datasets", {})
    sn_path = args.sn or (Path(ds0["sn"]) if ds0.get("sn") else None)
    sn_cov_path = args.sn_cov or (Path(ds0["sn_cov"]) if ds0.get("sn_cov") else None)
    bao_path = args.bao or (Path(ds0["bao"]) if ds0.get("bao") else None)
    drift_path = args.drift or (Path(ds0["drift"]) if ds0.get("drift") else None)

    if sn_path is None or bao_path is None:
        raise SystemExit("Need at least --sn and --bao datasets (or present in fit JSON).")

    if sn_cov_path is not None:
        sn = SNDataset.from_csv_and_cov(sn_path, sn_cov_path, name="sn")
    else:
        sn = SNDataset.from_csv(sn_path, name="sn")

    bao = BAODataset.from_csv(bao_path, name="bao")
    drift_ds = None
    if drift_path is not None:
        drift_ds = DriftDataset.from_csv(drift_path, baseline_years=args.drift_baseline_years, name="drift")

    # Build model objects + labels + nuisance.
    drift_models = []
    sn_models = []
    bao_models = []
    summary_rows = []
    for fit in fits:
        model_name = str(fit["model"])
        best = fit["best"]
        params = best["params"]
        parts = best["parts"]
        m = _model_from_bestfit(model_name, params)
        label = model_name

        # nuisance
        delta_M = float(parts.get("sn", {}).get("delta_M", 0.0))
        rd_m = float(parts.get("bao", {}).get("rd_m", float("nan")))

        drift_models.append((label, m))
        sn_models.append((label, m, delta_M))
        bao_models.append((label, m, rd_m))

        summary_rows.append(
            {
                "model": model_name,
                "chi2": float(best["chi2"]),
                "ndof": int(best["ndof"]),
                "chi2_over_ndof": float(best["chi2"]) / int(best["ndof"]) if int(best["ndof"]) > 0 else float("nan"),
                "H0": float(params.get("H0", float("nan"))),
                "Omega_m": float(params.get("Omega_m", float("nan"))),
                "p": float(params.get("p", float("nan"))),
                "z_transition": float(params.get("z_transition", float("nan"))),
                "delta_M": delta_M,
                "rd_Mpc": float(rd_m) / float(MPC_SI) if math.isfinite(rd_m) else float("nan"),
                "chi2_sn": float(parts.get("sn", {}).get("chi2", float("nan"))),
                "chi2_bao": float(parts.get("bao", {}).get("chi2", float("nan"))),
                "chi2_drift": float(parts.get("drift", {}).get("chi2", float("nan"))),
                "chi2_cmb": float(parts.get("cmb", {}).get("chi2", float("nan"))),
            }
        )

    # Add simple model-comparison stats (AIC/BIC) and deltas vs LCDM.
    for r, fit in zip(summary_rows, fits):
        k, n_obs = _count_fit_params(fit)
        chi2 = float(r["chi2"])
        r["k_params"] = int(k)
        r["n_obs"] = int(n_obs)
        r["AIC"] = float(chi2 + 2.0 * k) if k > 0 else float("nan")
        r["BIC"] = float(chi2 + k * math.log(n_obs)) if (k > 0 and n_obs > 0) else float("nan")

    ref = next((r for r in summary_rows if str(r.get("model", "")) == "lcdm"), None)
    if ref is not None:
        chi2_ref = float(ref["chi2"])
        aic_ref = float(ref.get("AIC", float("nan")))
        bic_ref = float(ref.get("BIC", float("nan")))
        for r in summary_rows:
            r["delta_chi2_vs_lcdm"] = float(r["chi2"]) - chi2_ref
            r["delta_AIC_vs_lcdm"] = float(r.get("AIC", float("nan"))) - aic_ref
            r["delta_BIC_vs_lcdm"] = float(r.get("BIC", float("nan"))) - bic_ref

    # Drift figure
    _plot_drift(drift_models, out_dir / "figure_A_drift_dv_vs_z.png", drift=drift_ds)

    # SN residuals
    _plot_sn_residuals(sn_models, sn, out_dir / "figure_B_sn_residuals.png", n_grid=args.n_grid)

    # BAO ratios figure
    _plot_bao(bao_models, bao, out_dir / "figure_C_bao_ratios.png", n_grid=args.n_grid)

    # Summary table CSV
    summary_path = fit_dir / "bestfit_summary.csv"
    keys = [
        "model",
        "chi2",
        "ndof",
        "chi2_over_ndof",
        "k_params",
        "n_obs",
        "AIC",
        "BIC",
        "delta_chi2_vs_lcdm",
        "delta_AIC_vs_lcdm",
        "delta_BIC_vs_lcdm",
        "H0",
        "Omega_m",
        "p",
        "z_transition",
        "delta_M",
        "rd_Mpc",
        "chi2_sn",
        "chi2_bao",
        "chi2_drift",
        "chi2_cmb",
    ]
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in summary_rows:
            w.writerow({k: r.get(k, "") for k in keys})

    print(f"WROTE {out_dir}")
    print(f"WROTE {summary_path}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""SN two-pass sensitivity diagnostic (v11.0.0, diagnostic-only).

Purpose:
- Quantify whether diagonal-SN prefiltering (`--two-pass-top`) can miss the
  global full-covariance best point on representative grids.
- Keep canonical late-time pipeline defaults unchanged.

Outputs:
- tables/sn_two_pass_sensitivity.csv
- tables/sn_two_pass_points.csv
- figures/chi2_best_vs_two_pass_top.png
- figures/best_rank_position_vs_two_pass_top.png
- manifest.json (strict JSON, repo-relative paths)
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
sys.path.insert(0, str(V101_DIR / "scripts"))

import numpy as np  # noqa: E402

from gsc.datasets.bao import BAOBlock1D, BAOBlock2D, BAOBlockND, BAODataset  # noqa: E402
from gsc.datasets.drift import DriftDataset  # noqa: E402
from gsc.datasets.sn import SNDataset  # noqa: E402
from gsc.fit import iter_param_grid, parse_grid_spec, profile_H0_from_drift  # noqa: E402
from gsc.measurement_model import C_SI, MPC_SI, PC_SI, SEC_PER_YR, z_dot_sandage_loeb  # noqa: E402
import late_time_fit_grid as ltf  # noqa: E402


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


def _parse_csv_floats(s: str) -> List[float]:
    out: List[float] = []
    for t in str(s).split(","):
        tt = t.strip()
        if not tt:
            continue
        out.append(float(tt))
    if not out:
        raise ValueError("empty list")
    return out


def _parse_csv_models(s: str) -> List[str]:
    out: List[str] = []
    for t in str(s).split(","):
        tt = t.strip()
        if not tt:
            continue
        if tt not in {"lcdm", "gsc_transition"}:
            raise ValueError(f"unsupported model in this diagnostic: {tt!r}")
        out.append(tt)
    if not out:
        raise ValueError("empty models list")
    return out


def _finite(x: float) -> bool:
    return math.isfinite(float(x))


@dataclass
class EvalPoint:
    model: str
    params: Dict[str, float]
    chi2_diag_total: float
    chi2_cov_total: float
    chi2_sn_diag: float
    chi2_sn_cov: float
    chi2_bao: float
    chi2_drift: float
    ndof_total: int
    delta_M_diag: float
    delta_M_cov: float
    error: str = ""


@dataclass
class ModelSummaryRow:
    model: str
    two_pass_top: int
    n_points: int
    global_best_cov_chi2: float
    global_best_diag_rank: int
    global_best_cov_rank: int
    best_cov_chi2_within_top: float
    delta_chi2_to_global: float
    global_best_found: bool
    selected_diag_rank: int
    selected_cov_rank: int
    selected_H0: Optional[float]
    selected_Omega_m: Optional[float]
    selected_p: Optional[float]
    selected_z_transition: Optional[float]
    selected_chi2_sn_full: Optional[float]
    selected_chi2_bao: Optional[float]
    selected_chi2_drift: Optional[float]

    def as_csv(self) -> Dict[str, str]:
        def f(v: Optional[float]) -> str:
            if v is None:
                return ""
            if not _finite(float(v)):
                return ""
            return f"{float(v):.16g}"

        return {
            "model": self.model,
            "two_pass_top": str(int(self.two_pass_top)),
            "n_points": str(int(self.n_points)),
            "global_best_cov_chi2": f(self.global_best_cov_chi2),
            "global_best_diag_rank": str(int(self.global_best_diag_rank)),
            "global_best_cov_rank": str(int(self.global_best_cov_rank)),
            "best_cov_chi2_within_top": f(self.best_cov_chi2_within_top),
            "delta_chi2_to_global": f(self.delta_chi2_to_global),
            "global_best_found": "true" if self.global_best_found else "false",
            "selected_diag_rank": str(int(self.selected_diag_rank)),
            "selected_cov_rank": str(int(self.selected_cov_rank)),
            "selected_H0": f(self.selected_H0),
            "selected_Omega_m": f(self.selected_Omega_m),
            "selected_p": f(self.selected_p),
            "selected_z_transition": f(self.selected_z_transition),
            "selected_chi2_sn_full": f(self.selected_chi2_sn_full),
            "selected_chi2_bao": f(self.selected_chi2_bao),
            "selected_chi2_drift": f(self.selected_chi2_drift),
        }


def _zmax_from_datasets(sn: Optional[ltf.PreparedSN], bao_src: Optional[BAODataset]) -> float:
    z_need: List[float] = []
    if sn is not None:
        z_need.extend([float(z) for z in np.asarray(sn.z, dtype=float)])
    if bao_src is not None:
        for b in bao_src.blocks:
            if isinstance(b, (BAOBlock1D, BAOBlock2D)):
                z_need.append(float(b.z))
            elif isinstance(b, BAOBlockND):
                z_need.extend([float(z) for z in b.zs])
    z_max = max(z_need) if z_need else 1.0
    return max(0.5, float(z_max))


def _validate_params(model: str, params: Dict[str, float]) -> Optional[str]:
    if "Omega_m" in params:
        Om = float(params["Omega_m"])
        if not (0.0 <= Om <= 1.0):
            return "Omega_m outside [0,1]"
    if model == "gsc_transition":
        p = float(params["p"])
        if not (0.0 < p < 1.0):
            return "p outside (0,1)"
        if float(params["z_transition"]) < 0.0:
            return "z_transition < 0"
    return None


def _eval_point(
    *,
    model_name: str,
    params: Dict[str, float],
    sn_diag: ltf.PreparedSN,
    sn_cov: ltf.PreparedSN,
    bao_ds: Optional[ltf.PreparedBAO],
    drift_ds: Optional[DriftDataset],
    z_max: float,
    n_grid: int,
    profile_h0: bool,
    h0_ref: float,
    h0_min: float,
    h0_max: float,
) -> EvalPoint:
    err = _validate_params(model_name, params)
    if err is not None:
        return EvalPoint(
            model=model_name,
            params=dict(params),
            chi2_diag_total=1.0e99,
            chi2_cov_total=1.0e99,
            chi2_sn_diag=1.0e99,
            chi2_sn_cov=1.0e99,
            chi2_bao=1.0e99,
            chi2_drift=1.0e99,
            ndof_total=0,
            delta_M_diag=float("nan"),
            delta_M_cov=float("nan"),
            error=err,
        )

    params_use = dict(params)
    params_ref = dict(params)
    params_ref["H0"] = float(h0_ref)

    try:
        model_ref = ltf._model_from_params(model_name, params_ref)
        if model_name.startswith("gsc_"):
            ltf._guardrail_gsc(model_ref, z_max=5.0)
    except Exception as e:
        return EvalPoint(
            model=model_name,
            params=dict(params),
            chi2_diag_total=1.0e99,
            chi2_cov_total=1.0e99,
            chi2_sn_diag=1.0e99,
            chi2_sn_cov=1.0e99,
            chi2_bao=1.0e99,
            chi2_drift=1.0e99,
            ndof_total=0,
            delta_M_diag=float("nan"),
            delta_M_cov=float("nan"),
            error=f"model/guardrail: {e}",
        )

    drift_profiled: Optional[Dict[str, float]] = None
    if profile_h0 and drift_ds is not None:
        try:
            drift_profiled = profile_H0_from_drift(
                drift=drift_ds,
                model_ref=model_ref,
                H0_bounds_km_s_Mpc=(float(h0_min), float(h0_max)),
            )
            params_use["H0"] = float(drift_profiled["H0_km_s_Mpc"])
        except Exception as e:
            return EvalPoint(
                model=model_name,
                params=dict(params),
                chi2_diag_total=1.0e99,
                chi2_cov_total=1.0e99,
                chi2_sn_diag=1.0e99,
                chi2_sn_cov=1.0e99,
                chi2_bao=1.0e99,
                chi2_drift=1.0e99,
                ndof_total=0,
                delta_M_diag=float("nan"),
                delta_M_cov=float("nan"),
                error=f"drift profile failed: {e}",
            )
    else:
        if "H0" not in params_use:
            params_use["H0"] = float(h0_ref)

    try:
        model = ltf._model_from_params(model_name, params_use)
        dm_fn = ltf._build_dm_interpolator(model, z_max=float(z_max), n_grid=int(n_grid))
    except Exception as e:
        return EvalPoint(
            model=model_name,
            params=dict(params_use),
            chi2_diag_total=1.0e99,
            chi2_cov_total=1.0e99,
            chi2_sn_diag=1.0e99,
            chi2_sn_cov=1.0e99,
            chi2_bao=1.0e99,
            chi2_drift=1.0e99,
            ndof_total=0,
            delta_M_diag=float("nan"),
            delta_M_cov=float("nan"),
            error=f"model/interp failed: {e}",
        )

    # SN (diag and full-cov evaluated for the same params/model).
    dm_sn = dm_fn(np.asarray(sn_diag.z, dtype=float))
    dl = (1.0 + np.asarray(sn_diag.z, dtype=float)) * dm_sn
    mu_th = 5.0 * np.log10(dl / (10.0 * float(PC_SI)))

    try:
        chi2_sn_diag, delta_M_diag, ndof_sn = sn_diag.chi2_from_mu_theory(mu_th)
        chi2_sn_cov, delta_M_cov, _ = sn_cov.chi2_from_mu_theory(mu_th)
    except Exception as e:
        return EvalPoint(
            model=model_name,
            params=dict(params_use),
            chi2_diag_total=1.0e99,
            chi2_cov_total=1.0e99,
            chi2_sn_diag=1.0e99,
            chi2_sn_cov=1.0e99,
            chi2_bao=1.0e99,
            chi2_drift=1.0e99,
            ndof_total=0,
            delta_M_diag=float("nan"),
            delta_M_cov=float("nan"),
            error=f"SN chi2 failed: {e}",
        )

    chi2_bao = 0.0
    ndof_bao = 0
    if bao_ds is not None:
        try:
            chi2_bao, _rd_m, ndof_bao = bao_ds.chi2(dm_fn=dm_fn, H_of_z=model.H, rd_m=None)
        except Exception as e:
            return EvalPoint(
                model=model_name,
                params=dict(params_use),
                chi2_diag_total=1.0e99,
                chi2_cov_total=1.0e99,
                chi2_sn_diag=1.0e99,
                chi2_sn_cov=1.0e99,
                chi2_bao=1.0e99,
                chi2_drift=1.0e99,
                ndof_total=0,
                delta_M_diag=float("nan"),
                delta_M_cov=float("nan"),
                error=f"BAO chi2 failed: {e}",
            )

    chi2_drift = 0.0
    ndof_drift = 0
    if drift_ds is not None:
        if drift_profiled is not None:
            chi2_drift = float(drift_profiled["chi2"])
            ndof_drift = int(drift_profiled.get("ndof", max(0, len(drift_ds.z) - 1)))
        else:
            H0 = float(model.H(0.0))
            for i, (z, dv_obs, sig) in enumerate(zip(drift_ds.z, drift_ds.dv_cm_s, drift_ds.sigma_dv_cm_s)):
                years = drift_ds.baseline_years_by_row[i] if drift_ds.baseline_years_by_row is not None else drift_ds.baseline_years
                zdot = z_dot_sandage_loeb(z=float(z), H0=H0, H_of_z=model.H)
                dv_pred = 100.0 * (float(C_SI) * zdot / (1.0 + float(z))) * (float(years) * float(SEC_PER_YR))
                r = (float(dv_obs) - float(dv_pred)) / float(sig)
                chi2_drift += float(r * r)
            ndof_drift = len(drift_ds.z)

    ndof_total = int(ndof_sn + ndof_bao + ndof_drift)
    shared = float(chi2_bao + chi2_drift)
    return EvalPoint(
        model=model_name,
        params=dict(params_use),
        chi2_diag_total=float(chi2_sn_diag + shared),
        chi2_cov_total=float(chi2_sn_cov + shared),
        chi2_sn_diag=float(chi2_sn_diag),
        chi2_sn_cov=float(chi2_sn_cov),
        chi2_bao=float(chi2_bao),
        chi2_drift=float(chi2_drift),
        ndof_total=ndof_total,
        delta_M_diag=float(delta_M_diag),
        delta_M_cov=float(delta_M_cov),
        error="",
    )


def _plot_chi2_vs_top(rows: Sequence[ModelSummaryRow], out_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: E402

    models = sorted(set(r.model for r in rows))
    fig, ax = plt.subplots(figsize=(8.0, 4.8), constrained_layout=True)

    for m in models:
        rr = [r for r in rows if r.model == m]
        rr = sorted(rr, key=lambda x: int(x.two_pass_top))
        xs = [int(r.two_pass_top) for r in rr]
        ys = [float(r.best_cov_chi2_within_top) for r in rr]
        y0 = float(rr[0].global_best_cov_chi2)
        ax.plot(xs, ys, marker="o", linewidth=2.0, label=f"{m} two-pass best")
        ax.axhline(y0, linestyle="--", linewidth=1.2, alpha=0.5)

    ax.set_xlabel("two_pass_top")
    ax.set_ylabel("best full-cov chi2 within top-N")
    ax.set_title("SN two-pass sensitivity (diag prefilter -> fullcov)")
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False, fontsize=8)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=170)
    plt.close(fig)


def _plot_rank_vs_top(rows: Sequence[ModelSummaryRow], out_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: E402

    models = sorted(set(r.model for r in rows))
    fig, ax = plt.subplots(figsize=(8.0, 4.8), constrained_layout=True)

    for m in models:
        rr = [r for r in rows if r.model == m]
        rr = sorted(rr, key=lambda x: int(x.two_pass_top))
        xs = [int(r.two_pass_top) for r in rr]
        ys = [int(r.selected_diag_rank) for r in rr]
        y_global = int(rr[0].global_best_diag_rank)
        ax.plot(xs, ys, marker="o", linewidth=2.0, label=f"{m} selected rank")
        ax.axhline(y_global, linestyle="--", linewidth=1.2, alpha=0.5)

    ax.set_xlabel("two_pass_top")
    ax.set_ylabel("diag rank position")
    ax.set_title("Diag rank of selected full-cov best candidate")
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False, fontsize=8)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=170)
    plt.close(fig)


def run(
    *,
    out_dir: Path,
    models: Sequence[str],
    two_pass_top_list: Sequence[int],
    sn_csv: Path,
    sn_cov: Path,
    bao_csv: Optional[Path],
    drift_csv: Optional[Path],
    drift_baseline_years: Optional[float],
    profile_h0: bool,
    H0_grid: Sequence[float],
    Omega_m_grid: Sequence[float],
    p_grid: Sequence[float],
    ztrans_grid: Sequence[float],
    n_grid: int,
) -> Dict[str, Any]:
    out_dir = out_dir.resolve()
    tables_dir = out_dir / "tables"
    figs_dir = out_dir / "figures"
    _ensure_dir(tables_dir)
    _ensure_dir(figs_dir)

    # Data prep.
    sn_ds = SNDataset.from_csv_and_cov(sn_csv, sn_cov, name="sn")
    sn_diag = ltf.PreparedSN(sn_ds, mode="diag")
    sn_cov_prep = ltf.PreparedSN(sn_ds, mode="cov")

    bao_src: Optional[BAODataset] = None
    bao_ds: Optional[ltf.PreparedBAO] = None
    if bao_csv is not None:
        bao_src = BAODataset.from_csv(bao_csv, name="bao")
        bao_ds = ltf.PreparedBAO(bao_src)

    drift_ds: Optional[DriftDataset] = None
    if drift_csv is not None:
        drift_ds = DriftDataset.from_csv(drift_csv, baseline_years=drift_baseline_years, name="drift")

    z_max = _zmax_from_datasets(sn_diag, bao_src)

    h0_vals = [float(x) for x in H0_grid]
    h0_ref = float(h0_vals[0])
    h0_min = float(min(h0_vals))
    h0_max = float(max(h0_vals))

    top_list = sorted({int(x) for x in two_pass_top_list if int(x) > 0})
    if not top_list:
        raise ValueError("two_pass_top_list must contain positive integers")

    all_points_rows: List[Dict[str, Any]] = []
    summary_rows: List[ModelSummaryRow] = []

    for model_name in models:
        grid: Dict[str, Sequence[float]] = {}
        if not profile_h0:
            grid["H0"] = h0_vals
        if model_name in ("lcdm", "gsc_transition"):
            grid["Omega_m"] = [float(x) for x in Omega_m_grid]
        if model_name == "gsc_transition":
            grid["p"] = [float(x) for x in p_grid]
            grid["z_transition"] = [float(x) for x in ztrans_grid]

        points: List[EvalPoint] = []
        for params in iter_param_grid(grid):
            p = _eval_point(
                model_name=model_name,
                params={k: float(v) for k, v in params.items()},
                sn_diag=sn_diag,
                sn_cov=sn_cov_prep,
                bao_ds=bao_ds,
                drift_ds=drift_ds,
                z_max=z_max,
                n_grid=int(n_grid),
                profile_h0=bool(profile_h0),
                h0_ref=h0_ref,
                h0_min=h0_min,
                h0_max=h0_max,
            )
            points.append(p)

        n_points = len(points)
        if n_points == 0:
            continue

        diag_order = sorted(range(n_points), key=lambda i: float(points[i].chi2_diag_total))
        cov_order = sorted(range(n_points), key=lambda i: float(points[i].chi2_cov_total))
        diag_rank = {idx: int(r + 1) for r, idx in enumerate(diag_order)}
        cov_rank = {idx: int(r + 1) for r, idx in enumerate(cov_order)}

        global_idx = int(cov_order[0])
        global_best = points[global_idx]

        for idx, p in enumerate(points):
            all_points_rows.append(
                {
                    "model": model_name,
                    "idx": int(idx),
                    "diag_rank": int(diag_rank[idx]),
                    "cov_rank": int(cov_rank[idx]),
                    "H0": float(p.params.get("H0", float("nan"))),
                    "Omega_m": float(p.params.get("Omega_m", float("nan"))),
                    "p": float(p.params.get("p", float("nan"))),
                    "z_transition": float(p.params.get("z_transition", float("nan"))),
                    "chi2_diag_total": float(p.chi2_diag_total),
                    "chi2_cov_total": float(p.chi2_cov_total),
                    "chi2_sn_diag": float(p.chi2_sn_diag),
                    "chi2_sn_cov": float(p.chi2_sn_cov),
                    "chi2_bao": float(p.chi2_bao),
                    "chi2_drift": float(p.chi2_drift),
                    "delta_M_diag": float(p.delta_M_diag),
                    "delta_M_cov": float(p.delta_M_cov),
                    "error": str(p.error),
                }
            )

        for top_n in top_list:
            n_sel = min(int(top_n), n_points)
            cand = diag_order[:n_sel]
            sel_idx = min(cand, key=lambda i: float(points[i].chi2_cov_total))
            sel = points[sel_idx]

            summary_rows.append(
                ModelSummaryRow(
                    model=model_name,
                    two_pass_top=int(top_n),
                    n_points=int(n_points),
                    global_best_cov_chi2=float(global_best.chi2_cov_total),
                    global_best_diag_rank=int(diag_rank[global_idx]),
                    global_best_cov_rank=int(cov_rank[global_idx]),
                    best_cov_chi2_within_top=float(sel.chi2_cov_total),
                    delta_chi2_to_global=float(sel.chi2_cov_total - global_best.chi2_cov_total),
                    global_best_found=bool(global_idx in cand),
                    selected_diag_rank=int(diag_rank[sel_idx]),
                    selected_cov_rank=int(cov_rank[sel_idx]),
                    selected_H0=float(sel.params.get("H0")) if "H0" in sel.params else None,
                    selected_Omega_m=float(sel.params.get("Omega_m")) if "Omega_m" in sel.params else None,
                    selected_p=float(sel.params.get("p")) if "p" in sel.params else None,
                    selected_z_transition=float(sel.params.get("z_transition")) if "z_transition" in sel.params else None,
                    selected_chi2_sn_full=float(sel.chi2_sn_cov),
                    selected_chi2_bao=float(sel.chi2_bao),
                    selected_chi2_drift=float(sel.chi2_drift),
                )
            )

    if not summary_rows:
        raise ValueError("No summary rows produced")

    summary_csv = tables_dir / "sn_two_pass_sensitivity.csv"
    with summary_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(summary_rows[0].as_csv().keys()))
        w.writeheader()
        for r in summary_rows:
            w.writerow(r.as_csv())

    points_csv = tables_dir / "sn_two_pass_points.csv"
    point_fields = [
        "model",
        "idx",
        "diag_rank",
        "cov_rank",
        "H0",
        "Omega_m",
        "p",
        "z_transition",
        "chi2_diag_total",
        "chi2_cov_total",
        "chi2_sn_diag",
        "chi2_sn_cov",
        "chi2_bao",
        "chi2_drift",
        "delta_M_diag",
        "delta_M_cov",
        "error",
    ]
    with points_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=point_fields)
        w.writeheader()
        for row in all_points_rows:
            out: Dict[str, str] = {}
            for k in point_fields:
                v = row.get(k)
                if isinstance(v, float):
                    out[k] = "" if not _finite(v) else f"{v:.16g}"
                else:
                    out[k] = str(v)
            w.writerow(out)

    fig1 = figs_dir / "chi2_best_vs_two_pass_top.png"
    fig2 = figs_dir / "best_rank_position_vs_two_pass_top.png"
    _plot_chi2_vs_top(summary_rows, fig1)
    _plot_rank_vs_top(summary_rows, fig2)

    # Human-readable summary.
    txt = tables_dir / "summary.txt"
    lines = [
        "SN two-pass sensitivity diagnostic (v11.0.0)",
        "",
        "Interpretation:",
        "- If delta_chi2_to_global is ~0 for moderate top-N, two-pass prefilter is stable on this grid.",
        "- If global_best_found=false for practical top-N, there is a ranking risk to flag.",
        "",
    ]
    by_model: Dict[str, List[ModelSummaryRow]] = {}
    for r in summary_rows:
        by_model.setdefault(r.model, []).append(r)
    for m in sorted(by_model.keys()):
        lines.append(f"Model: {m}")
        for r in sorted(by_model[m], key=lambda x: int(x.two_pass_top)):
            lines.append(
                f"  top={r.two_pass_top}: chi2_best={r.best_cov_chi2_within_top:.6g}, "
                f"global={r.global_best_cov_chi2:.6g}, delta={r.delta_chi2_to_global:.6g}, "
                f"global_found={r.global_best_found}, global_diag_rank={r.global_best_diag_rank}"
            )
        lines.append("")
    txt.write_text("\n".join(lines), encoding="utf-8")

    manifest: Dict[str, Any] = {
        "diagnostic_only": True,
        "kind": "sn_two_pass_sensitivity",
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"]),
        "git_branch": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "--abbrev-ref", "HEAD"]),
        "git_dirty": bool(_run_git(["git", "-C", str(REPO_ROOT), "status", "--porcelain=v1"]).strip()),
        "inputs": {
            "sn_csv": _relpath(Path(sn_csv)),
            "sn_cov": _relpath(Path(sn_cov)),
            "bao_csv": (_relpath(Path(bao_csv)) if bao_csv is not None else None),
            "drift_csv": (_relpath(Path(drift_csv)) if drift_csv is not None else None),
            "drift_baseline_years": (None if drift_baseline_years is None else float(drift_baseline_years)),
        },
        "grid": {
            "models": list(models),
            "two_pass_top": [int(x) for x in top_list],
            "profile_h0": bool(profile_h0),
            "H0_grid": [float(x) for x in H0_grid],
            "Omega_m_grid": [float(x) for x in Omega_m_grid],
            "p_grid": [float(x) for x in p_grid],
            "ztrans_grid": [float(x) for x in ztrans_grid],
            "n_grid": int(n_grid),
        },
        "outputs": {
            "outdir": _relpath(out_dir),
            "summary_table": _relpath(summary_csv),
            "points_table": _relpath(points_csv),
            "summary_text": _relpath(txt),
            "figure_best": _relpath(fig1),
            "figure_rank": _relpath(fig2),
        },
        "notes": [
            "Diagnostic-only robustness check for diagonal->fullcov two-pass prefiltering.",
            "No canonical late-time defaults are changed.",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return manifest


def main(argv: Optional[Sequence[str]] = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", type=Path, default=Path("v11.0.0/results/diagnostic_sn_two_pass_sensitivity"))

    ap.add_argument("--models", type=str, default="lcdm,gsc_transition")
    ap.add_argument("--two-pass-top", type=str, default="60,200,500")

    ap.add_argument(
        "--sn",
        type=Path,
        default=Path("v11.0.0/data/sn/pantheon_plus_shoes/pantheon_plus_shoes_hflow_mu.csv"),
    )
    ap.add_argument(
        "--sn-cov",
        type=Path,
        default=Path("v11.0.0/data/sn/pantheon_plus_shoes/Pantheon+SH0ES_STAT+SYS.cov"),
    )
    ap.add_argument(
        "--bao",
        type=Path,
        default=Path("v11.0.0/data/bao/bao_6df_mgs_boss_dr12_cov6_plus_lya_qso.csv"),
    )
    ap.add_argument(
        "--drift",
        type=Path,
        default=Path("v11.0.0/data/drift/elt_andes_liske_conservative_20yr_asimov.csv"),
    )
    ap.add_argument("--drift-baseline-years", type=float, default=None)

    ap.add_argument("--profile-H0", action="store_true", default=True)
    ap.add_argument("--no-profile-H0", action="store_false", dest="profile_H0")

    ap.add_argument("--H0-grid", type=str, default="60:80:2")
    ap.add_argument("--Omega-m-grid", type=str, default="0.27,0.295,0.315,0.335,0.36")
    ap.add_argument("--p-grid", type=str, default="0.55,0.6,0.65,0.7,0.8")
    ap.add_argument("--ztrans-grid", type=str, default="1.0,1.5,1.8,2.5,3.5")
    ap.add_argument("--n-grid", type=int, default=4000)

    args = ap.parse_args(argv)

    models = _parse_csv_models(str(args.models))
    tops = [int(x) for x in _parse_csv_floats(str(args.two_pass_top))]

    manifest = run(
        out_dir=Path(args.outdir),
        models=models,
        two_pass_top_list=tops,
        sn_csv=Path(args.sn),
        sn_cov=Path(args.sn_cov),
        bao_csv=Path(args.bao) if args.bao else None,
        drift_csv=Path(args.drift) if args.drift else None,
        drift_baseline_years=(None if args.drift_baseline_years is None else float(args.drift_baseline_years)),
        profile_h0=bool(args.profile_H0),
        H0_grid=[float(x) for x in parse_grid_spec(str(args.H0_grid))],
        Omega_m_grid=[float(x) for x in parse_grid_spec(str(args.Omega_m_grid))],
        p_grid=[float(x) for x in parse_grid_spec(str(args.p_grid))],
        ztrans_grid=[float(x) for x in parse_grid_spec(str(args.ztrans_grid))],
        n_grid=int(args.n_grid),
    )

    print(f"WROTE {Path(args.outdir).resolve() / 'tables' / 'sn_two_pass_sensitivity.csv'}")
    print(f"WROTE {Path(args.outdir).resolve() / 'figures' / 'chi2_best_vs_two_pass_top.png'}")
    print(f"WROTE {Path(args.outdir).resolve() / 'manifest.json'}")
    print(f"kind={manifest.get('kind')}  diagnostic_only={manifest.get('diagnostic_only')}")


if __name__ == "__main__":  # pragma: no cover
    main()

#!/usr/bin/env python3
"""E2.0 diagnostic scan: rs*(z*) calibration fit vs bridge_z (CHW2018 priors).

This script runs a small scan over `bridge_z_used` for a fixed non-degenerate
GSC bridge configuration and records:
- baseline chi2_cmb (strict CHW2018 cov)
- best-fit rs_star_calibration_fit (1D; affects only lA via r_s(z*) scaling)
- chi2_cmb_min after the fit
- diag pulls (base vs fit)

Outputs
-------
Writes (repo-relative, under --out-dir):
- cmb_rs_star_fit_scan.csv
- figures/chi2_base_vs_bridge_z.png
- figures/chi2_min_vs_bridge_z.png
- figures/rs_star_calibration_fit_vs_bridge_z.png

Optionally also writes a paper-assets directory (ignored by git) + a zip artifact
for a GitHub pre-release.
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
from typing import Any, Dict, List, Tuple
import zipfile


V101_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = V101_DIR.parent
sys.path.insert(0, str(V101_DIR))

import numpy as np  # noqa: E402

from gsc.datasets.cmb_priors import CMBPriorsDataset  # noqa: E402
from gsc.early_time.cmb_distance_priors import _RS_STAR_CALIB_CHW2018  # noqa: E402

import cmb_rs_star_calibration_fit_e2 as fit  # noqa: E402


def _parse_bridge_z_list(s: str) -> Tuple[float, ...]:
    out: List[float] = []
    for part in (s or "").split(","):
        part = part.strip()
        if not part:
            continue
        out.append(float(part))
    if not out:
        raise ValueError("empty bridge_z list")
    return tuple(out)


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _relpath(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except Exception:
        return str(path)


def _run_git(cmd: List[str]) -> str:
    try:
        return subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True).strip()
    except Exception as e:
        return f"<error: {e}>"


def _make_plot(*, x: List[float], y: List[float], out_path: Path, title: str, y_label: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: E402

    fig, ax = plt.subplots(figsize=(7.5, 4.5), constrained_layout=True)
    ax.plot(x, y, marker="o", linewidth=2.0)
    ax.set_xlabel("bridge_z_used")
    ax.set_ylabel(y_label)
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def _write_csv(path: Path, *, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _write_manifest(
    *,
    out_path: Path,
    cmb_csv: Path,
    cmb_cov: Path,
    scan_cfg: Dict[str, Any],
    results_csv: Path,
    figures: List[Path],
    tables: List[Path],
) -> None:
    obj: Dict[str, Any] = {
        "diagnostic_only": True,
        "kind": "cmb_rs_star_calibration_fit_e2_scan",
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"]),
        "git_branch": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "--abbrev-ref", "HEAD"]),
        "git_dirty": bool(_run_git(["git", "-C", str(REPO_ROOT), "status", "--porcelain=v1"])),
        "inputs": {
            "cmb_csv": _relpath(cmb_csv),
            "cmb_cov": _relpath(cmb_cov),
            "chw2018_csv_name": cmb_csv.name,
            "chw2018_cov_name": cmb_cov.name,
        },
        "scan_config": scan_cfg,
        "outputs": {
            "results_csv": _relpath(results_csv),
            "tables": [_relpath(p) for p in tables],
            "figures": [_relpath(p) for p in figures],
        },
        "notes": [
            "Diagnostic-only artifact: rs_star_calibration_fit is an extra 1D nuisance multiplier on r_s(z*).",
            "By construction, only lA is altered: lA -> lA / rs_star_calibration_fit (R, omega_b_h2 fixed).",
            "Not used anywhere in the canonical late-time or submission pipeline.",
        ],
    }
    out_path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def _zip_dir(*, dir_path: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    root_name = dir_path.name
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(dir_path.rglob("*")):
            if p.is_dir():
                continue
            if p.name in {".DS_Store"} or p.name.startswith("._"):
                continue
            arc = str(Path(root_name) / p.relative_to(dir_path))
            zf.write(p, arcname=arc)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, default=Path("v11.0.0/results/diagnostic_cmb_rs_star_fit"))
    ap.add_argument("--paper-assets-dir", type=Path, default=Path("v11.0.0/paper_assets_cmb_e2_rs_star_fit_diagnostic"))
    ap.add_argument("--zip-out", type=Path, default=Path("v11.0.0/paper_assets_cmb_e2_rs_star_fit_diagnostic_r0.zip"))

    ap.add_argument(
        "--cmb",
        type=Path,
        default=V101_DIR / "data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv",
    )
    ap.add_argument(
        "--cmb-cov",
        type=Path,
        default=V101_DIR / "data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov",
    )

    ap.add_argument("--bridge-z", type=str, default="2,5,10,20")

    # Fixed "starter" point requested in the sprint notes (still configurable for convenience).
    ap.add_argument("--model", choices=("gsc_transition",), default="gsc_transition")
    ap.add_argument("--H0", type=float, default=67.4)
    ap.add_argument("--Omega-m", dest="Omega_m", type=float, default=0.315)
    ap.add_argument("--Omega-L", dest="Omega_L", type=float, default=0.685)
    ap.add_argument("--gsc-p", type=float, default=0.6)
    ap.add_argument("--gsc-ztrans", type=float, default=1.8)
    ap.add_argument("--omega-b-h2", type=float, default=0.02237)
    ap.add_argument("--omega-c-h2", type=float, default=0.1200)
    ap.add_argument("--Neff", type=float, default=3.046)
    ap.add_argument("--Tcmb-K", type=float, default=2.7255)

    ap.add_argument("--fit-k-min", type=float, default=0.8)
    ap.add_argument("--fit-k-max", type=float, default=1.3)
    ap.add_argument("--fit-expand-factor", type=float, default=1.25)
    ap.add_argument("--fit-max-expands", type=int, default=8)

    args = ap.parse_args()

    out_dir = args.out_dir
    fig_dir = out_dir / "figures"
    _ensure_dir(out_dir)
    _ensure_dir(fig_dir)

    bridge_zs = _parse_bridge_z_list(args.bridge_z)

    ds = CMBPriorsDataset.from_csv(args.cmb, cov_path=args.cmb_cov, name="cmb_chw2018")
    rs_star_base = float(_RS_STAR_CALIB_CHW2018)

    rows: List[Dict[str, Any]] = []
    for zreq in bridge_zs:
        pred_base = fit._compute_pred(
            model=str(args.model),
            H0_km_s_Mpc=float(args.H0),
            Omega_m=float(args.Omega_m),
            Omega_L=float(args.Omega_L),
            gsc_p=float(args.gsc_p),
            gsc_ztrans=float(args.gsc_ztrans),
            cmb_bridge_z=float(zreq),
            omega_b_h2=float(args.omega_b_h2),
            omega_c_h2=float(args.omega_c_h2),
            Neff=float(args.Neff),
            Tcmb_K=float(args.Tcmb_K),
            rs_star_calibration_base=float(rs_star_base),
        )

        r = fit.fit_rs_star_calibration_multiplier(
            ds=ds,
            pred_base=pred_base,
            rs_star_calibration_base=float(rs_star_base),
            k_min=float(args.fit_k_min),
            k_max=float(args.fit_k_max),
            expand_factor=float(args.fit_expand_factor),
            max_expands=int(args.fit_max_expands),
        )

        bridge_z_used = float(pred_base.get("bridge_z", float("nan")))
        is_degenerate = bool(math.isfinite(bridge_z_used) and bridge_z_used <= float(args.gsc_ztrans))

        row: Dict[str, Any] = {
            "model": str(args.model),
            "gsc_p": float(args.gsc_p),
            "gsc_ztrans": float(args.gsc_ztrans),
            "bridge_z_requested": float(zreq),
            "bridge_z_used": float(bridge_z_used),
            "is_degenerate": bool(is_degenerate),
            "chi2_base": float(r.chi2_base),
            "chi2_min": float(r.chi2_min),
            "rs_star_calibration_fit": float(r.rs_star_calibration_fit),
            "rs_star_calibration_base": float(r.rs_star_calibration_base),
            "rs_star_calibration_total": float(r.rs_star_calibration_total),
        }

        for k in ds.keys:
            row[f"pulls_base_{k}"] = float(r.pulls_base.get(k, float("nan")))
        for k in ds.keys:
            row[f"pulls_fit_{k}"] = float(r.pulls_fit.get(k, float("nan")))

        rows.append(row)

    csv_path = out_dir / "cmb_rs_star_fit_scan.csv"
    _write_csv(csv_path, rows=rows)

    # Plots.
    xs = [float(r["bridge_z_used"]) for r in rows]
    y_base = [float(r["chi2_base"]) for r in rows]
    y_min = [float(r["chi2_min"]) for r in rows]
    y_k = [float(r["rs_star_calibration_fit"]) for r in rows]

    fig_base = fig_dir / "chi2_base_vs_bridge_z.png"
    fig_min = fig_dir / "chi2_min_vs_bridge_z.png"
    fig_k = fig_dir / "rs_star_calibration_fit_vs_bridge_z.png"

    _make_plot(x=xs, y=y_base, out_path=fig_base, title="E2.0 diagnostic: baseline chi2 vs bridge_z", y_label="chi2_base (CHW2018 cov)")
    _make_plot(x=xs, y=y_min, out_path=fig_min, title="E2.0 diagnostic: fitted chi2_min vs bridge_z", y_label="chi2_min (CHW2018 cov)")
    _make_plot(x=xs, y=y_k, out_path=fig_k, title="E2.0 diagnostic: rs* fit vs bridge_z", y_label="rs_star_calibration_fit")

    print(f"[e2.0] wrote: {csv_path}")
    print(f"[e2.0] wrote: {fig_base}")
    print(f"[e2.0] wrote: {fig_min}")
    print(f"[e2.0] wrote: {fig_k}")

    # Paper-assets directory (ignored by git).
    paper_dir = args.paper_assets_dir
    (paper_dir / "figures").mkdir(parents=True, exist_ok=True)
    (paper_dir / "tables").mkdir(parents=True, exist_ok=True)

    table_out = paper_dir / "tables" / "cmb_rs_star_fit_scan.csv"
    table_out.write_bytes(csv_path.read_bytes())

    figs_out: List[Path] = []
    for p in (fig_base, fig_min, fig_k):
        dst = paper_dir / "figures" / p.name
        dst.write_bytes(p.read_bytes())
        figs_out.append(dst)

    scan_cfg = {
        "model": str(args.model),
        "gsc_p": float(args.gsc_p),
        "gsc_ztrans": float(args.gsc_ztrans),
        "bridge_z_list": [float(z) for z in bridge_zs],
        "rs_star_calibration_base": float(rs_star_base),
        "fit_parameter": "rs_star_calibration_fit (multiplicative on r_s(z*); implemented as lA -> lA / k)",
        "fit_bounds_initial": {"k_min": float(args.fit_k_min), "k_max": float(args.fit_k_max)},
        "fit_expand": {"factor": float(args.fit_expand_factor), "max_expands": int(args.fit_max_expands)},
        "chw2018_keys": list(ds.keys),
    }

    manifest_path = paper_dir / "manifest.json"
    _write_manifest(
        out_path=manifest_path,
        cmb_csv=args.cmb,
        cmb_cov=args.cmb_cov,
        scan_cfg=scan_cfg,
        results_csv=csv_path,
        figures=figs_out,
        tables=[table_out],
    )

    zip_out = args.zip_out
    _zip_dir(dir_path=paper_dir, zip_path=zip_out)
    print(f"[e2.0] wrote: {manifest_path}")
    print(f"[e2.0] wrote: {zip_out}")


if __name__ == "__main__":
    main()


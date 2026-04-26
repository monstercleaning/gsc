#!/usr/bin/env python3
"""E1.3 diagnostic scan: CMB chi2 sensitivity vs bridge_z (v11.0.0).

This script is intentionally *diagnostic*:
- It evaluates compressed CMB distance-priors (CHW2018 vector+cov) for non-LCDM
  late-time histories using the E1.3 "bridged" mapping.
- It scans over the explicit diagnostic knob `bridge_z` and records chi2/pulls.

Notes:
- The primary target is `gsc_transition`.
- `gsc_powerlaw` is kept only as a "fails hard" CMB curve; we do not spend time
  evaluating SN/BAO/drift for it (those fields are set to NaN / 0 ndof).

Outputs (under --out-dir):
- cmb_bridge_scan.csv
- figures/chi2_cmb_vs_bridge_z.png
- *_bestfit.json stubs (one per model+bridge_z) for manifest/provenance tooling
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, List, Optional, Tuple


V101_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V101_DIR))

import numpy as np  # noqa: E402

from gsc.datasets.bao import BAODataset, BAODatasetFixedRd  # noqa: E402
from gsc.datasets.cmb_priors import CMBPriorsDataset  # noqa: E402
from gsc.datasets.drift import DriftDataset  # noqa: E402
from gsc.datasets.sn import SNDataset  # noqa: E402
from gsc.early_time import compute_bridged_distance_priors, compute_rd_Mpc  # noqa: E402
from gsc.early_time import cmb_distance_priors as cmb_dp  # noqa: E402
from gsc.early_time.cmb_distance_priors import _RS_STAR_CALIB_CHW2018  # noqa: E402
from gsc.likelihood import chi2_total  # noqa: E402
from gsc.measurement_model import (  # noqa: E402
    GSCTransitionHistory,
    H0_to_SI,
    MPC_SI,
    PowerLawHistory,
)


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


def _diag_pulls(*, keys: Tuple[str, ...], mean: np.ndarray, cov: np.ndarray, pred: Dict[str, float]) -> Dict[str, float]:
    diag = np.diag(cov)
    pulls: Dict[str, float] = {}
    for i, k in enumerate(keys):
        sigma = float(math.sqrt(float(diag[i])))
        pulls[k] = (float(pred[k]) - float(mean[i])) / sigma
    return pulls


def _z_to_tag(z: float) -> str:
    """Stable, filesystem-safe tag for float z values (e.g. 0.5 -> 0p5)."""
    s = f"{float(z):g}"
    return s.replace("-", "m").replace(".", "p")


def _write_bestfit_stub(
    *,
    out_path: Path,
    model_id: str,
    base_model: str,
    model_params: Dict[str, Any],
    datasets: Dict[str, str],
    early_time: Dict[str, Any],
    cmb_cfg: Dict[str, Any],
    chi2_breakdown: Dict[str, Any],
    cmb_pred: Dict[str, Any],
) -> None:
    obj = {
        "model": model_id,
        "base_model": base_model,
        "model_params": model_params,
        "datasets": datasets,
        "early_time": early_time,
        "cmb": cmb_cfg,
        "chi2": chi2_breakdown,
        "cmb_pred": cmb_pred,
    }
    out_path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def _make_plot(*, rows: List[Dict[str, Any]], out_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: E402

    # Group by base_model.
    by_model: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        by_model.setdefault(str(r["base_model"]), []).append(r)

    fig, ax = plt.subplots(figsize=(7.5, 4.5), constrained_layout=True)
    for m, rr in sorted(by_model.items()):
        rr_sorted = sorted(rr, key=lambda x: float(x["bridge_z_requested"]))
        x = [float(r["bridge_z_requested"]) for r in rr_sorted]
        y = [float(r["chi2_cmb"]) for r in rr_sorted]
        ax.plot(x, y, marker="o", linewidth=2.0, label=m)

    ax.set_xlabel("bridge_z (requested)")
    ax.set_ylabel("chi2_cmb (CHW2018, cov)")
    ax.set_title("E1.3 Diagnostic: CMB chi2 vs bridge_z")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")

    # If chi2 ranges over orders of magnitude, log scale is more readable.
    yy = [float(r["chi2_cmb"]) for r in rows if math.isfinite(float(r["chi2_cmb"])) and float(r["chi2_cmb"]) > 0.0]
    if yy:
        y_min = min(yy)
        y_max = max(yy)
        if y_max / max(y_min, 1e-9) > 1e3:
            ax.set_yscale("log")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, default=Path("v11.0.0/results/late_time_fit_cmb_e13_diagnostic"))
    ap.add_argument("--sync-paper-assets-dir", type=Path, default=None, help="Optional paper_assets output dir.")

    ap.add_argument("--sn", type=Path, required=True)
    ap.add_argument("--sn-cov", type=Path, required=True)
    ap.add_argument("--bao", type=Path, required=True)
    ap.add_argument("--drift", type=Path, default=None)

    ap.add_argument("--cmb", type=Path, required=True)
    ap.add_argument("--cmb-cov", type=Path, required=True)

    # Default r2 scan grid around the "critical" low bridge region for gsc_transition.
    ap.add_argument("--bridge-z", type=str, default="0.5,1,1.5,2,2.5,3,4,5,7.5,10,20,50,100")
    # Keep gsc_powerlaw only as a cheap "fails hard" curve.
    ap.add_argument("--bridge-z-powerlaw", type=str, default="2,5,10,20,50,100")

    ap.add_argument("--H0", type=float, default=67.4)
    ap.add_argument("--Omega-m", dest="Omega_m", type=float, default=0.315)
    ap.add_argument("--Omega-L", dest="Omega_L", type=float, default=0.685)

    ap.add_argument("--gsc-p", type=float, default=0.6)
    ap.add_argument("--gsc-ztrans", type=float, default=1.8)

    ap.add_argument("--omega-b-h2", type=float, default=0.02237)
    ap.add_argument("--omega-c-h2", type=float, default=0.1200)
    ap.add_argument("--Neff", type=float, default=3.046)
    ap.add_argument("--Tcmb-K", type=float, default=2.7255)
    ap.add_argument("--rd-method", type=str, default="eisenstein_hu_1998")

    args = ap.parse_args()

    out_dir = args.out_dir.resolve()
    fig_dir = out_dir / "figures"
    _ensure_dir(out_dir)
    _ensure_dir(fig_dir)

    bridge_zs_transition = _parse_bridge_z_list(args.bridge_z)
    bridge_zs_powerlaw = _parse_bridge_z_list(args.bridge_z_powerlaw)

    # Load datasets.
    sn_ds = SNDataset.from_csv_and_cov(args.sn, args.sn_cov, name="sn")
    bao_base = BAODataset.from_csv(args.bao, name="bao")
    drift_ds = DriftDataset.from_csv(args.drift, name="drift") if args.drift is not None else None

    cmb_ds = CMBPriorsDataset.from_csv(args.cmb, cov_path=args.cmb_cov, name="cmb")
    cmb_keys = cmb_ds.keys
    cmb_mean = np.asarray(cmb_ds.values, dtype=float)
    cmb_cov = np.asarray(cmb_ds.cov, dtype=float) if cmb_ds.cov is not None else None
    if cmb_cov is None:
        raise SystemExit("CMB covariance missing (strict E1.1/E1.2 requires cov).")

    # Precompute fixed r_d for BAO (E0 closure).
    rd_mpc = compute_rd_Mpc(
        omega_b_h2=float(args.omega_b_h2),
        omega_c_h2=float(args.omega_c_h2),
        N_eff=float(args.Neff),
        Tcmb_K=float(args.Tcmb_K),
        method=str(args.rd_method),
    )
    bao_ds = BAODatasetFixedRd(base=bao_base, rd_m=float(rd_mpc) * float(MPC_SI), name="bao")

    # CHW2018 stopgap calibration is applied only to r_s(z*) in the CHW2018 path.
    rs_star_calib = float(_RS_STAR_CALIB_CHW2018)

    # Models to scan.
    H0_si = H0_to_SI(float(args.H0))
    models: List[Tuple[str, Any, Dict[str, Any]]] = []
    models.append(
        (
            "gsc_powerlaw",
            PowerLawHistory(H0=H0_si, p=float(args.gsc_p)),
            {"H0": float(args.H0), "gsc_p": float(args.gsc_p)},
        )
    )
    models.append(
        (
            "gsc_transition",
            GSCTransitionHistory(
                H0=H0_si,
                Omega_m=float(args.Omega_m),
                Omega_Lambda=float(args.Omega_L),
                p=float(args.gsc_p),
                z_transition=float(args.gsc_ztrans),
            ),
            {
                "H0": float(args.H0),
                "Omega_m": float(args.Omega_m),
                "Omega_L": float(args.Omega_L),
                "gsc_p": float(args.gsc_p),
                "gsc_ztrans": float(args.gsc_ztrans),
            },
        )
    )

    rows: List[Dict[str, Any]] = []
    bestfit_paths: List[Path] = []

    for base_model, model, model_params in models:
        # Evaluate non-CMB datasets once per model (they do not depend on bridge_z).
        #
        # For gsc_powerlaw we deliberately skip SN/BAO/drift to keep this scan cheap;
        # it is included only as a "fails hard" CMB curve.
        if base_model == "gsc_powerlaw":
            r_sn = None
            r_bao = None
            r_drift = None
            bridge_zs = bridge_zs_powerlaw
        else:
            r_sn = sn_ds.chi2(model)
            r_bao = bao_ds.chi2(model)
            r_drift = drift_ds.chi2(model) if drift_ds is not None else None
            bridge_zs = bridge_zs_transition

        # For gsc_transition we can precompute D_M(0->z_transition) once to
        # estimate how much of the CMB D_M(z*) integral enters the non-LCDM
        # (powerlaw) segment for a given bridge_z.
        z_transition = float(args.gsc_ztrans) if base_model == "gsc_transition" else float("nan")
        D_M_0_to_ztrans_Mpc: float = float("nan")
        if base_model == "gsc_transition":
            try:
                D_M_0_to_ztrans_Mpc = float(
                    cmb_dp._comoving_distance_model_to_z_m(z=float(z_transition), model=model, n=4096) / float(MPC_SI)
                )
            except Exception:
                D_M_0_to_ztrans_Mpc = float("nan")

        for zreq in bridge_zs:
            pred = compute_bridged_distance_priors(
                model=model,
                z_bridge=float(zreq),
                omega_b_h2=float(args.omega_b_h2),
                omega_c_h2=float(args.omega_c_h2),
                N_eff=float(args.Neff),
                Tcmb_K=float(args.Tcmb_K),
                rs_star_calibration=rs_star_calib,
            )
            r_cmb = cmb_ds.chi2_from_values(pred)
            pulls = _diag_pulls(keys=cmb_keys, mean=cmb_mean, cov=cmb_cov, pred=pred)

            bridge_z_used = float(pred.get("bridge_z", float("nan")))
            is_degenerate = False
            degenerate_reason = ""
            if base_model == "gsc_transition" and math.isfinite(bridge_z_used):
                # If bridge_z_used <= z_transition, the CMB comoving-distance
                # integral never enters the powerlaw segment, so CMB is blind to
                # the non-LCDM part of gsc_transition. This is a diagnostic knob
                # degeneracy, not a "good fit".
                if bridge_z_used <= float(z_transition):
                    is_degenerate = True
                    degenerate_reason = (
                        "bridge_z_used <= z_transition: CMB D_M(z*) integral never enters the powerlaw segment; "
                        "CMB prediction is LCDM-only w.r.t gsc_transition(p,z_transition)."
                    )
                    print(
                        f"[e1.3][WARN] gsc_transition degeneracy: bridge_z_used={bridge_z_used:g} <= z_transition={z_transition:g}."
                    )

            # Distance split provenance columns.
            DM_0_to_bridge_Mpc = float(pred.get("D_M_0_to_bridge_Mpc", float("nan")))
            DM_bridge_to_zstar_Mpc = float(pred.get("D_M_bridge_to_zstar_Mpc", float("nan")))
            DM_total_Mpc = float(pred.get("D_M_star_Mpc", float("nan")))

            # Fraction of CMB D_M(z*) integral in the non-LCDM (powerlaw) segment.
            frac_DM_non_lcdm = float("nan")
            if base_model == "gsc_transition" and math.isfinite(DM_total_Mpc) and DM_total_Mpc > 0.0:
                if not is_degenerate and math.isfinite(D_M_0_to_ztrans_Mpc) and math.isfinite(DM_0_to_bridge_Mpc):
                    DM_non_lcdm = max(0.0, float(DM_0_to_bridge_Mpc) - float(D_M_0_to_ztrans_Mpc))
                else:
                    DM_non_lcdm = 0.0
                frac_DM_non_lcdm = float(DM_non_lcdm / float(DM_total_Mpc))

            chi2_sn_val = float(r_sn.chi2) if r_sn is not None else float("nan")
            ndof_sn_val = int(r_sn.ndof) if r_sn is not None else 0
            chi2_bao_val = float(r_bao.chi2) if r_bao is not None else float("nan")
            ndof_bao_val = int(r_bao.ndof) if r_bao is not None else 0
            chi2_drift_val = float(r_drift.chi2) if r_drift is not None else float("nan")
            ndof_drift_val = int(r_drift.ndof) if r_drift is not None else 0

            chi2_total_val = float(
                (chi2_sn_val if math.isfinite(chi2_sn_val) else 0.0)
                + (chi2_bao_val if math.isfinite(chi2_bao_val) else 0.0)
                + (chi2_drift_val if math.isfinite(chi2_drift_val) else 0.0)
                + float(r_cmb.chi2)
            )
            ndof_total_val = int(ndof_sn_val + ndof_bao_val + ndof_drift_val + int(r_cmb.ndof))

            row = {
                "base_model": base_model,
                "bridge_z": float(zreq),
                "bridge_z_requested": float(zreq),
                "bridge_z_used": float(bridge_z_used),
                "z_transition": float(z_transition),
                "is_degenerate": bool(is_degenerate),
                "degenerate_reason": str(degenerate_reason),
                "chi2_cmb": float(r_cmb.chi2),
                "ndof_cmb": int(r_cmb.ndof),
                "R_pred": float(pred.get("R", float("nan"))),
                "lA_pred": float(pred.get("lA", float("nan"))),
                "omega_b_h2_pred": float(pred.get("omega_b_h2", float("nan"))),
                "pull_R": float(pulls.get("R", float("nan"))),
                "pull_lA": float(pulls.get("lA", float("nan"))),
                "pull_omega_b_h2": float(pulls.get("omega_b_h2", float("nan"))),
                "DM_0_to_bridge_Mpc": float(DM_0_to_bridge_Mpc),
                "DM_bridge_to_zstar_Mpc": float(DM_bridge_to_zstar_Mpc),
                "DM_total_Mpc": float(DM_total_Mpc),
                "frac_DM_non_lcdm": float(frac_DM_non_lcdm),
                "chi2_sn": chi2_sn_val,
                "chi2_bao": chi2_bao_val,
                "chi2_drift": chi2_drift_val,
                "chi2_total": chi2_total_val,
                "ndof_total": ndof_total_val,
                "rs_star_calibration": float(rs_star_calib),
                "rs_star_calibration_applied": bool(float(rs_star_calib) != 1.0),
                "bridge_H_ratio": float(pred.get("bridge_H_ratio", float("nan"))),
                "z_star": float(pred.get("z_star", float("nan"))),
                "r_s_star_Mpc": float(pred.get("r_s_star_Mpc", float("nan"))),
                "D_M_star_Mpc": float(pred.get("D_M_star_Mpc", float("nan"))),
                "rd_Mpc": float(pred.get("rd_Mpc", float("nan"))),
            }
            rows.append(row)

            # bestfit stub for manifest/provenance tooling
            z_tag = _z_to_tag(float(zreq))
            model_id = f"{base_model}@bridge_z={z_tag}"
            stub_path = out_dir / f"{base_model}_bridge_z_{z_tag}_bestfit.json"
            bestfit_paths.append(stub_path)
            include_full_ds = base_model != "gsc_powerlaw"
            _write_bestfit_stub(
                out_path=stub_path,
                model_id=model_id,
                base_model=base_model,
                model_params=model_params,
                datasets={
                    "sn": str(args.sn) if include_full_ds else "",
                    "sn_cov": str(args.sn_cov) if include_full_ds else "",
                    "bao": str(args.bao) if include_full_ds else "",
                    "drift": str(args.drift) if (include_full_ds and args.drift is not None) else "",
                    "cmb": str(args.cmb),
                    "cmb_cov": str(args.cmb_cov),
                },
                early_time={
                    "rd_mode": "early",
                    "rd_method": str(args.rd_method),
                    "omega_b_h2": float(args.omega_b_h2),
                    "omega_c_h2": float(args.omega_c_h2),
                    "Neff": float(args.Neff),
                    "Tcmb_K": float(args.Tcmb_K),
                    "rd_Mpc": float(rd_mpc),
                },
                cmb_cfg={
                    "path": str(args.cmb),
                    "cov_path": str(args.cmb_cov),
                    "mode": "distance_priors",
                    "bridge_z_requested": float(zreq),
                    "bridge_z_used": float(bridge_z_used),
                    "bridge_z_transition": float(z_transition),
                    "cmb_bridge_degenerate": bool(is_degenerate),
                    "cmb_bridge_degenerate_reason": str(degenerate_reason),
                },
                chi2_breakdown={
                    "chi2_total": chi2_total_val,
                    "ndof_total": ndof_total_val,
                    "chi2_sn": chi2_sn_val,
                    "ndof_sn": ndof_sn_val,
                    "chi2_bao": chi2_bao_val,
                    "ndof_bao": ndof_bao_val,
                    "chi2_drift": chi2_drift_val,
                    "ndof_drift": ndof_drift_val,
                    "chi2_cmb": float(r_cmb.chi2),
                    "ndof_cmb": int(r_cmb.ndof),
                    "pulls_diag": pulls,
                },
                cmb_pred=pred,
            )

    # Write scan CSV.
    csv_path = out_dir / "cmb_bridge_scan.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=list(rows[0].keys()),
        )
        w.writeheader()
        for r in rows:
            w.writerow(r)

    # Plot.
    fig_path = fig_dir / "chi2_cmb_vs_bridge_z.png"
    _make_plot(rows=rows, out_path=fig_path)

    # Optional paper-assets sync: copy figures/tables/manifest after manifest is generated.
    if args.sync_paper_assets_dir is not None:
        paper_dir = args.sync_paper_assets_dir.resolve()
        (paper_dir / "figures").mkdir(parents=True, exist_ok=True)
        (paper_dir / "tables").mkdir(parents=True, exist_ok=True)
        # Do not copy manifest here; the caller should run late_time_make_manifest.py after this scan.
        (paper_dir / "tables" / "cmb_bridge_scan.csv").write_bytes(csv_path.read_bytes())
        (paper_dir / "figures" / "chi2_cmb_vs_bridge_z.png").write_bytes(fig_path.read_bytes())

    # Print quick summary for logs.
    for base_model in sorted({r["base_model"] for r in rows}):
        rr = [r for r in rows if r["base_model"] == base_model]
        if base_model == "gsc_transition":
            rr_non_deg = [r for r in rr if not bool(r.get("is_degenerate"))]
            rr_sel = rr_non_deg if rr_non_deg else rr
        else:
            rr_sel = rr
        best = min(rr_sel, key=lambda x: float(x["chi2_cmb"]))
        print(
            f"[e1.3] {base_model}: min chi2_cmb={best['chi2_cmb']:.6g} at bridge_z={best['bridge_z_requested']}"
        )
    print(f"[e1.3] wrote: {csv_path}")
    print(f"[e1.3] wrote: {fig_path}")


if __name__ == "__main__":
    main()

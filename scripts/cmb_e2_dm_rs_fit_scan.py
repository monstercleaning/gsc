#!/usr/bin/env python3
"""E2.4 diagnostic: coarse scan of (dm_star_calibration, rs_star_calibration) closure fits.

Purpose
-------
For a family of late-time histories (here: `gsc_transition`) and non-degenerate bridge
choices, quantify:

- baseline strict-CHW2018 chi2 (dm=1, rs=1)
- best-fit diagnostic closure knobs (dm_fit, rs_fit) minimizing strict-CHW2018 chi2

This is diagnostic-only tooling. It must not be used as a physics claim.
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
from typing import Any, Dict, Iterable, List, Sequence, Tuple


V101_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = V101_DIR.parent
sys.path.insert(0, str(V101_DIR))
sys.path.insert(0, str(V101_DIR / "scripts"))

import numpy as np  # noqa: E402

from gsc.datasets.cmb_priors import CMBPriorsDataset  # noqa: E402
from gsc.early_time import compute_bridged_distance_priors  # noqa: E402
from gsc.measurement_model import GSCTransitionHistory, H0_to_SI  # noqa: E402


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


def _effective_cov(ds: CMBPriorsDataset) -> np.ndarray:
    if ds.cov is None:
        raise ValueError("CMB covariance is required for strict CHW2018 distance-priors mode.")
    cov = np.asarray(ds.cov, dtype=float)
    sig_th = np.asarray(ds.sigmas_theory, dtype=float)
    if sig_th.size and float(np.max(sig_th)) > 0.0:
        cov = cov + np.diag(sig_th * sig_th)
    return cov


def _parse_float_list(csv_s: str) -> List[float]:
    out: List[float] = []
    for tok in str(csv_s).split(","):
        tok = tok.strip()
        if not tok:
            continue
        out.append(float(tok))
    return out


def _compute_pred_raw_transition(
    *,
    H0_km_s_Mpc: float,
    Omega_m: float,
    Omega_L: float,
    p: float,
    z_transition: float,
    bridge_z: float,
    omega_b_h2: float,
    omega_c_h2: float,
    Neff: float,
    Tcmb_K: float,
) -> Dict[str, float]:
    H0_si = H0_to_SI(float(H0_km_s_Mpc))
    hist = GSCTransitionHistory(
        H0=float(H0_si),
        Omega_m=float(Omega_m),
        Omega_Lambda=float(Omega_L),
        p=float(p),
        z_transition=float(z_transition),
    )
    pred = compute_bridged_distance_priors(
        model=hist,
        z_bridge=float(bridge_z),
        omega_b_h2=float(omega_b_h2),
        omega_c_h2=float(omega_c_h2),
        N_eff=float(Neff),
        Tcmb_K=float(Tcmb_K),
        rs_star_calibration=1.0,
        dm_star_calibration=1.0,
    )
    pred["z_transition"] = float(z_transition)
    return pred


@dataclass(frozen=True)
class FitRow:
    model: str
    p: float
    z_transition: float
    bridge_z_used: float
    is_degenerate: bool
    dm_fit: float
    rs_fit: float
    chi2_min: float
    chi2_base: float
    pulls_R: float
    pulls_lA: float
    pulls_omega_b_h2: float


def _joint_fit_dm_rs(
    *,
    keys: Tuple[str, ...],
    mean: np.ndarray,
    cov: np.ndarray,
    W: np.ndarray,
    Wb: np.ndarray,
    omega_b_h2_pred: float,
    pred_raw: Dict[str, float],
    rs_min: float,
    rs_max: float,
    rs_step: float,
    dm_min: float = 1e-6,
) -> Tuple[FitRow, List[Dict[str, float]]]:
    for req in ("R", "lA", "omega_b_h2"):
        if req not in keys:
            raise ValueError(f"Dataset is missing required key: {req!r}")
    if not (rs_min > 0 and rs_max > rs_min and rs_step > 0):
        raise ValueError("Require rs_min>0, rs_max>rs_min, rs_step>0")

    iR = keys.index("R")
    ilA = keys.index("lA")
    iob = keys.index("omega_b_h2")

    R0 = float(pred_raw["R"])
    lA0 = float(pred_raw["lA"])
    ob0 = float(pred_raw["omega_b_h2"])
    if abs(ob0 - float(omega_b_h2_pred)) > 1e-12:
        # This should not happen for fixed early inputs; keep but do not hard-fail.
        pass

    c = np.zeros_like(mean)
    c[iob] = float(omega_b_h2_pred)

    # Base chi2 at (dm=1, rs=1) using the same linear form.
    A_base = np.zeros_like(mean)
    A_base[iR] = R0
    A_base[ilA] = lA0
    y_base = A_base + c
    r_base = y_base - mean
    chi2_base = float(r_base.T @ W @ r_base)

    n = int(math.floor((float(rs_max) - float(rs_min)) / float(rs_step))) + 1
    if n < 2:
        raise ValueError("rs grid too small")

    best_rs = float("nan")
    best_dm = float("nan")
    best_chi2 = float("inf")

    grid_rows: List[Dict[str, float]] = []

    for i in range(int(n)):
        rs = float(rs_min) + float(i) * float(rs_step)
        if rs > float(rs_max) + 1e-15:
            break

        A = np.zeros_like(mean)
        A[iR] = R0
        A[ilA] = lA0 / float(rs)

        denom = float(A @ (W @ A))
        if not (denom > 0 and math.isfinite(denom)):
            raise ValueError("Non-positive A^T W A (covariance issue)")
        dm = float((A @ Wb) / denom)
        if not (dm > 0 and math.isfinite(dm)):
            dm = float(dm_min)
        if dm < float(dm_min):
            dm = float(dm_min)

        y = float(dm) * A + c
        r = y - mean
        chi2 = float(r.T @ W @ r)

        grid_rows.append({"rs_star_calibration": float(rs), "dm_star_calibration_opt": float(dm), "chi2": float(chi2)})
        if chi2 < best_chi2:
            best_chi2 = float(chi2)
            best_rs = float(rs)
            best_dm = float(dm)

    # Best-fit pulls (diag of cov).
    diag = np.diag(cov)
    sig = np.sqrt(diag)
    y_fit = np.zeros_like(mean)
    y_fit[iR] = float(best_dm) * float(R0)
    y_fit[ilA] = (float(best_dm) / float(best_rs)) * float(lA0)
    y_fit[iob] = float(omega_b_h2_pred)
    pulls = (y_fit - mean) / sig

    row = FitRow(
        model="gsc_transition",
        p=float("nan"),
        z_transition=float("nan"),
        bridge_z_used=float(pred_raw.get("bridge_z", float("nan"))),
        is_degenerate=False,
        dm_fit=float(best_dm),
        rs_fit=float(best_rs),
        chi2_min=float(best_chi2),
        chi2_base=float(chi2_base),
        pulls_R=float(pulls[iR]),
        pulls_lA=float(pulls[ilA]),
        pulls_omega_b_h2=float(pulls[iob]),
    )
    return row, grid_rows


def _plot_dm_scatter(
    *,
    rows: List[FitRow],
    bridge_z: float,
    out_path: Path,
    title: str,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: E402

    xs: List[float] = []
    ys: List[float] = []
    cs: List[float] = []
    for r in rows:
        if bool(r.is_degenerate):
            continue
        if not math.isfinite(float(r.dm_fit)):
            continue
        if abs(float(r.bridge_z_used) - float(bridge_z)) > 1e-9:
            continue
        xs.append(float(r.p))
        ys.append(float(r.z_transition))
        cs.append(float(r.dm_fit))

    fig, ax = plt.subplots(figsize=(7.5, 5.0), constrained_layout=True)
    if xs:
        sc = ax.scatter(xs, ys, c=cs, cmap="viridis", s=46, edgecolors="none")
        cb = fig.colorbar(sc, ax=ax)
        cb.set_label("dm_star_calibration_fit")
    ax.set_xlabel("p")
    ax.set_ylabel("z_transition")
    ax.set_title(title)
    ax.grid(True, alpha=0.25)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def _plot_chi2_base_vs_dm_fit(*, rows: List[FitRow], out_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: E402

    xs: List[float] = []
    ys: List[float] = []
    cs: List[float] = []
    for r in rows:
        if bool(r.is_degenerate):
            continue
        if not (math.isfinite(float(r.dm_fit)) and math.isfinite(float(r.chi2_base))):
            continue
        xs.append(float(r.dm_fit))
        ys.append(float(r.chi2_base))
        cs.append(float(r.bridge_z_used))

    fig, ax = plt.subplots(figsize=(7.5, 4.5), constrained_layout=True)
    if xs:
        sc = ax.scatter(xs, ys, c=cs, cmap="plasma", s=46, edgecolors="none")
        cb = fig.colorbar(sc, ax=ax)
        cb.set_label("bridge_z_used")
    ax.set_xlabel("dm_star_calibration_fit")
    ax.set_ylabel("chi2_base  (dm=1, rs=1)")
    ax.set_title("E2.4 diagnostic: baseline chi2 vs required distance-closure (dm_fit)")
    ax.grid(True, alpha=0.25)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
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

    ap.add_argument("--bridge-zs", type=str, default="5,10")
    ap.add_argument("--p-grid", type=str, default="0.55,0.6,0.65,0.7,0.75,0.8,0.9")
    ap.add_argument("--ztrans-grid", type=str, default="0.8,1.2,1.5,1.8,2.2,3.0,4.0")

    ap.add_argument("--H0", type=float, default=67.4)
    ap.add_argument("--Omega-m", dest="Omega_m", type=float, default=0.315)
    ap.add_argument("--Omega-L", dest="Omega_L", type=float, default=0.685)
    ap.add_argument("--omega-b-h2", type=float, default=0.02237)
    ap.add_argument("--omega-c-h2", type=float, default=0.1200)
    ap.add_argument("--Neff", type=float, default=3.046)
    ap.add_argument("--Tcmb-K", type=float, default=2.7255)

    ap.add_argument("--rs-min", type=float, default=0.90)
    ap.add_argument("--rs-max", type=float, default=1.20)
    ap.add_argument("--rs-step", type=float, default=5e-4)

    ap.add_argument("--outdir", type=Path, default=Path("v11.0.0/results/diagnostic_cmb_e2_dm_rs_fit_scan"))
    args = ap.parse_args()

    ds = CMBPriorsDataset.from_csv(args.cmb, cov_path=args.cmb_cov, name="cmb_chw2018")
    keys = ds.keys
    mean = np.asarray(ds.values, dtype=float)
    cov = _effective_cov(ds)
    W = np.linalg.inv(cov)

    # Precompute Wb for the analytic dm optimum (depends only on omega_b_h2_pred).
    if "omega_b_h2" not in keys:
        raise ValueError("Expected omega_b_h2 in CMB dataset keys")
    iob = keys.index("omega_b_h2")
    c = np.zeros_like(mean)
    c[iob] = float(args.omega_b_h2)
    b = mean - c
    Wb = W @ b

    bridge_zs = _parse_float_list(str(args.bridge_zs))
    ps = _parse_float_list(str(args.p_grid))
    zts = _parse_float_list(str(args.ztrans_grid))

    out_dir = args.outdir
    tables_dir = out_dir / "tables"
    figs_dir = out_dir / "figures"
    _ensure_dir(tables_dir)
    _ensure_dir(figs_dir)

    rows: List[FitRow] = []

    for bridge_z in bridge_zs:
        for zt in zts:
            for p in ps:
                is_deg = bool(float(bridge_z) <= float(zt))
                if is_deg:
                    rows.append(
                        FitRow(
                            model="gsc_transition",
                            p=float(p),
                            z_transition=float(zt),
                            bridge_z_used=float(bridge_z),
                            is_degenerate=True,
                            dm_fit=float("nan"),
                            rs_fit=float("nan"),
                            chi2_min=float("nan"),
                            chi2_base=float("nan"),
                            pulls_R=float("nan"),
                            pulls_lA=float("nan"),
                            pulls_omega_b_h2=float("nan"),
                        )
                    )
                    continue

                pred_raw = _compute_pred_raw_transition(
                    H0_km_s_Mpc=float(args.H0),
                    Omega_m=float(args.Omega_m),
                    Omega_L=float(args.Omega_L),
                    p=float(p),
                    z_transition=float(zt),
                    bridge_z=float(bridge_z),
                    omega_b_h2=float(args.omega_b_h2),
                    omega_c_h2=float(args.omega_c_h2),
                    Neff=float(args.Neff),
                    Tcmb_K=float(args.Tcmb_K),
                )

                fit_row, _grid = _joint_fit_dm_rs(
                    keys=keys,
                    mean=mean,
                    cov=cov,
                    W=W,
                    Wb=Wb,
                    omega_b_h2_pred=float(args.omega_b_h2),
                    pred_raw=pred_raw,
                    rs_min=float(args.rs_min),
                    rs_max=float(args.rs_max),
                    rs_step=float(args.rs_step),
                )

                rows.append(
                    FitRow(
                        model="gsc_transition",
                        p=float(p),
                        z_transition=float(zt),
                        bridge_z_used=float(fit_row.bridge_z_used),
                        is_degenerate=False,
                        dm_fit=float(fit_row.dm_fit),
                        rs_fit=float(fit_row.rs_fit),
                        chi2_min=float(fit_row.chi2_min),
                        chi2_base=float(fit_row.chi2_base),
                        pulls_R=float(fit_row.pulls_R),
                        pulls_lA=float(fit_row.pulls_lA),
                        pulls_omega_b_h2=float(fit_row.pulls_omega_b_h2),
                    )
                )

    # Write CSV.
    csv_path = tables_dir / "cmb_e2_dm_rs_fit_scan.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].__dict__.keys()))
        w.writeheader()
        for r in rows:
            w.writerow({k: f"{v:.16g}" if isinstance(v, float) else str(v) for k, v in r.__dict__.items()})

    # Figures.
    for bridge_z in bridge_zs:
        _plot_dm_scatter(
            rows=rows,
            bridge_z=float(bridge_z),
            out_path=figs_dir / f"dm_fit_vs_p_ztrans_bridgez{float(bridge_z):g}.png",
            title=f"E2.4 diagnostic: dm_fit vs (p, z_transition)   bridge_z={float(bridge_z):g}",
        )

    _plot_chi2_base_vs_dm_fit(rows=rows, out_path=figs_dir / "chi2_base_vs_dm_fit.png")

    # Manifest summary.
    by_bridge: Dict[str, Dict[str, float]] = {}
    for bridge_z in bridge_zs:
        vals = [float(r.dm_fit) for r in rows if (not r.is_degenerate) and math.isfinite(float(r.dm_fit)) and abs(float(r.bridge_z_used) - float(bridge_z)) < 1e-9]
        if vals:
            by_bridge[str(float(bridge_z))] = {
                "dm_fit_min": float(np.min(vals)),
                "dm_fit_max": float(np.max(vals)),
                "dm_fit_median": float(np.median(vals)),
            }

    manifest = {
        "diagnostic_only": True,
        "kind": "cmb_e2_dm_rs_fit_scan",
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"]),
        "git_branch": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "--abbrev-ref", "HEAD"]),
        "git_dirty": bool(_run_git(["git", "-C", str(REPO_ROOT), "status", "--porcelain=v1"])),
        "inputs": {
            "cmb_csv": _relpath(args.cmb),
            "cmb_cov": _relpath(args.cmb_cov),
            "chw2018_csv_name": args.cmb.name,
            "chw2018_cov_name": args.cmb_cov.name,
        },
        "fixed_params": {
            "H0_km_s_Mpc": float(args.H0),
            "Omega_m": float(args.Omega_m),
            "Omega_L": float(args.Omega_L),
            "omega_b_h2": float(args.omega_b_h2),
            "omega_c_h2": float(args.omega_c_h2),
            "Neff": float(args.Neff),
            "Tcmb_K": float(args.Tcmb_K),
        },
        "grid": {
            "bridge_z_used": [float(x) for x in bridge_zs],
            "p": [float(x) for x in ps],
            "z_transition": [float(x) for x in zts],
            "degenerate_condition": "bridge_z_used <= z_transition (skip; non-informative)",
        },
        "fit_grid": {"rs_min": float(args.rs_min), "rs_max": float(args.rs_max), "rs_step": float(args.rs_step)},
        "summary_by_bridge_z": by_bridge,
        "outputs": {
            "outdir": _relpath(out_dir),
            "csv": _relpath(csv_path),
            "figures_dir": _relpath(figs_dir),
        },
        "notes": [
            "Diagnostic-only: joint-fit (dm_star_calibration, rs_star_calibration) against strict CHW2018 distance priors.",
            "This is a 'what would it take' closure diagnostic, not a physics claim.",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("OK: wrote E2.4 dm/rs closure scan")
    print(f"  outdir={_relpath(out_dir)}")
    print(f"  rows={len(rows)}  nondeg={sum(1 for r in rows if not r.is_degenerate)}")
    for k, v in by_bridge.items():
        print(f"  bridge_z={k}: dm_fit median={v.get('dm_fit_median', float('nan')):.6g}  range=[{v.get('dm_fit_min', float('nan')):.6g},{v.get('dm_fit_max', float('nan')):.6g}]")


if __name__ == "__main__":
    main()


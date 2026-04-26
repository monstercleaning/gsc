#!/usr/bin/env python3
"""E2.10 diagnostic: high-z H-boost repair scan (full-history, drift-safe).

Goal
----
Test whether strict CHW2018 distance priors can be closed in *full-history* mode
(no stitch), using only an explicit high-z deformation:

  H(z) -> A(z) * H(z)  for z > z_boost_start

with:
- A(z)=1 for z <= z_boost_start (protect the drift window z~2–5),
- A(z)=1 for z >= z_bbn_clamp (preserve the BBN guardrail via the clamp),
- no additional dm/rs fit knobs (dm=1, rs=_RS_STAR_CALIB_CHW2018 by default).

Diagnostic-only / out of submission scope.
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

from gsc.datasets.cmb_priors import CMBPriorsDataset  # noqa: E402
from gsc.early_time import compute_full_history_distance_priors  # noqa: E402
from gsc.early_time.cmb_distance_priors import _RS_STAR_CALIB_CHW2018, z_star_hu_sugiyama  # noqa: E402
from gsc.histories.full_range import FlatLCDMRadHistory, GSCTransitionFullHistory, HBoostWrapper  # noqa: E402
from gsc.measurement_model import H0_to_SI, delta_v_cm_s  # noqa: E402


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


def _parse_float_list(csv_s: str) -> List[float]:
    out: List[float] = []
    for tok in str(csv_s).split(","):
        t = tok.strip()
        if not t:
            continue
        out.append(float(t))
    if not out:
        raise ValueError("Empty CSV list")
    return out


def _effective_cov(ds: CMBPriorsDataset) -> np.ndarray:
    if ds.cov is None:
        raise ValueError("CMB covariance is required for strict CHW2018 distance-priors mode.")
    cov = np.asarray(ds.cov, dtype=float)
    sig_th = np.asarray(ds.sigmas_theory, dtype=float)
    if sig_th.size and float(np.max(sig_th)) > 0.0:
        cov = cov + np.diag(sig_th * sig_th)
    return cov


def _diag_pulls(*, keys: Tuple[str, ...], mean: np.ndarray, cov: np.ndarray, pred: Dict[str, float]) -> Dict[str, float]:
    diag = np.diag(cov)
    pulls: Dict[str, float] = {}
    for i, k in enumerate(keys):
        sigma = float(math.sqrt(float(diag[i])))
        pulls[k] = (float(pred[k]) - float(mean[i])) / sigma
    return pulls


@dataclass(frozen=True)
class Row:
    z_boost_start: float
    A_const: float

    chi2_full_base: float
    pulls_R: float
    pulls_lA: float
    pulls_omega_b_h2: float

    dv_z2: float
    dv_z3: float
    dv_z4: float
    dv_z5: float
    drift_sign_ok: bool

    bbn_dev_z1e8: float
    bbn_dev_z1e9: float

    D_M_star_Mpc: float
    r_s_star_Mpc: float

    def as_csv_dict(self) -> Dict[str, str]:
        def f(x: float) -> str:
            if not math.isfinite(float(x)):
                return ""
            return f"{float(x):.16g}"

        return {
            "z_boost_start": f(self.z_boost_start),
            "A_const": f(self.A_const),
            "chi2_full_base": f(self.chi2_full_base),
            "pull_R": f(self.pulls_R),
            "pull_lA": f(self.pulls_lA),
            "pull_omega_b_h2": f(self.pulls_omega_b_h2),
            "dv_z2_cm_s_10y": f(self.dv_z2),
            "dv_z3_cm_s_10y": f(self.dv_z3),
            "dv_z4_cm_s_10y": f(self.dv_z4),
            "dv_z5_cm_s_10y": f(self.dv_z5),
            "drift_sign_ok": ("True" if bool(self.drift_sign_ok) else "False"),
            "bbn_dev_z1e8": f(self.bbn_dev_z1e8),
            "bbn_dev_z1e9": f(self.bbn_dev_z1e9),
            "D_M_star_Mpc": f(self.D_M_star_Mpc),
            "r_s_star_Mpc": f(self.r_s_star_Mpc),
        }


def run(
    *,
    cmb_csv: Path,
    cmb_cov: Path,
    out_dir: Path,
    # Late-time checkpoint (fixed by default; diagnostic-only).
    p_late: float,
    z_transition: float,
    # Full-history convergence (guarded) parameters.
    z_relax_start: float,
    relax_scale: float,
    p_target: float,
    z_bbn_clamp: Optional[float],
    # Boost scan parameters.
    z_boost_start_list: Sequence[float],
    A_min: float,
    A_max: float,
    A_step: float,
    transition_width: float,
    # Early/physical parameters.
    H0_km_s_Mpc: float,
    Omega_m: float,
    omega_b_h2: float,
    omega_c_h2: float,
    Neff: float,
    Tcmb_K: float,
    # Numerics.
    n_D_M: int,
    n_r_s: int,
    # CHW2018 stopgap calibration: keep as-is (scoped to distance-priors path).
    rs_star_calibration: float,
) -> Dict[str, Any]:
    out_dir = out_dir.resolve()
    tables_dir = out_dir / "tables"
    figs_dir = out_dir / "figures"
    _ensure_dir(tables_dir)
    _ensure_dir(figs_dir)

    if not (p_late > 0 and math.isfinite(p_late)):
        raise ValueError("p_late must be finite and > 0")
    if not (z_transition >= 0 and math.isfinite(z_transition)):
        raise ValueError("z_transition must be finite and >= 0")
    if not (math.isfinite(z_relax_start) and z_relax_start >= 0):
        raise ValueError("z_relax_start must be finite and >= 0")
    if float(z_relax_start) < float(z_transition):
        raise ValueError("z_relax_start must be >= z_transition")
    if not (relax_scale > 0 and math.isfinite(relax_scale)):
        raise ValueError("relax_scale must be finite and > 0")
    if not (p_target > 0 and math.isfinite(p_target)):
        raise ValueError("p_target must be finite and > 0")
    if z_bbn_clamp is not None and not (z_bbn_clamp > 0 and math.isfinite(float(z_bbn_clamp))):
        raise ValueError("z_bbn_clamp must be finite and > 0, or None")

    if not z_boost_start_list:
        raise ValueError("Empty z_boost_start_list")
    if any((not (math.isfinite(float(z)) and float(z) >= 0)) for z in z_boost_start_list):
        raise ValueError("All z_boost_start values must be finite and >= 0")

    if not (A_min > 0 and A_max >= A_min and A_step > 0 and math.isfinite(A_step)):
        raise ValueError("Require A_min>0, A_max>=A_min, A_step>0")
    if not (transition_width >= 0 and math.isfinite(transition_width)):
        raise ValueError("transition_width must be finite and >= 0")

    if n_D_M < 512 or n_r_s < 512:
        raise ValueError("integration grids too small")
    if not (rs_star_calibration > 0 and math.isfinite(rs_star_calibration)):
        raise ValueError("rs_star_calibration must be finite and > 0")

    # Load strict CHW2018 priors (vector+cov).
    ds = CMBPriorsDataset.from_csv(cmb_csv, cov_path=cmb_cov)
    keys = ds.keys
    mean = np.asarray(ds.values, dtype=float)
    cov = _effective_cov(ds)

    for req in ("R", "lA", "omega_b_h2"):
        if req not in keys:
            raise ValueError(f"Dataset missing required key: {req}")

    # Baseline full history (guarded relax above z_relax_start).
    base = GSCTransitionFullHistory(
        H0=H0_to_SI(float(H0_km_s_Mpc)),
        Omega_m=float(Omega_m),
        p_late=float(p_late),
        z_transition=float(z_transition),
        z_relax=float(relax_scale),
        z_relax_start=float(z_relax_start),
        p_target=float(p_target),
        N_eff=float(Neff),
        Tcmb_K=float(Tcmb_K),
        z_bbn_clamp=(float(z_bbn_clamp) if z_bbn_clamp is not None else None),
    )

    lcdm_rad = FlatLCDMRadHistory(
        H0=float(base.H0),
        Omega_m=float(base.Omega_m),
        N_eff=float(base.N_eff),
        Tcmb_K=float(base.Tcmb_K),
    )

    # z_star is defined by the same fitting formula used inside the distance-priors helper.
    # For this diagnostic, we apply the boost only on (z_boost_start, z_star) so r_s(z*)
    # is not modified by construction (matching the E2.3 mapping logic).
    omega_m_h2 = float(omega_b_h2) + float(omega_c_h2)
    z_star_use = float(z_star_hu_sugiyama(omega_b_h2=float(omega_b_h2), omega_m_h2=float(omega_m_h2)))

    # Drift baseline (10y) is computed per point on the boosted history; by construction it should
    # be identical for z<z_boost_start, but we measure it explicitly.
    drift_years = 10.0

    rows: List[Row] = []
    for z_bs in sorted([float(x) for x in z_boost_start_list]):
        A_vals: List[float] = []
        n = int(math.floor((float(A_max) - float(A_min)) / float(A_step))) + 1
        for i in range(int(n)):
            A = float(A_min) + float(i) * float(A_step)
            if A > float(A_max) + 1e-15:
                break
            A_vals.append(float(A))

        for A in A_vals:
            hist = HBoostWrapper(
                base_history=base,
                z_boost_start=float(z_bs),
                z_boost_end=float(z_star_use),
                z_bbn_clamp=(float(z_bbn_clamp) if z_bbn_clamp is not None else None),
                transition_width=float(transition_width),
                boost_mode="const",
                A_const=float(A),
            )

            pred = compute_full_history_distance_priors(
                history_full=hist,
                omega_b_h2=float(omega_b_h2),
                omega_c_h2=float(omega_c_h2),
                N_eff=float(Neff),
                Tcmb_K=float(Tcmb_K),
                rs_star_calibration=float(rs_star_calibration),
                dm_star_calibration=1.0,
                n_D_M=int(n_D_M),
                n_r_s=int(n_r_s),
            )

            chi2 = float(ds.chi2_from_values(pred).chi2)
            pulls = _diag_pulls(keys=keys, mean=mean, cov=cov, pred=pred)

            dv = {
                2.0: float(delta_v_cm_s(z=2.0, years=drift_years, H0=float(hist.H(0.0)), H_of_z=hist.H)),
                3.0: float(delta_v_cm_s(z=3.0, years=drift_years, H0=float(hist.H(0.0)), H_of_z=hist.H)),
                4.0: float(delta_v_cm_s(z=4.0, years=drift_years, H0=float(hist.H(0.0)), H_of_z=hist.H)),
                5.0: float(delta_v_cm_s(z=5.0, years=drift_years, H0=float(hist.H(0.0)), H_of_z=hist.H)),
            }
            drift_ok = bool(all(float(v) > 0.0 for v in dv.values()))

            # BBN clamp sanity: compare to LCDM+rad at very high z.
            dev_1e8 = float(hist.H(1.0e8) / lcdm_rad.H(1.0e8) - 1.0)
            dev_1e9 = float(hist.H(1.0e9) / lcdm_rad.H(1.0e9) - 1.0)

            rows.append(
                Row(
                    z_boost_start=float(z_bs),
                    A_const=float(A),
                    chi2_full_base=float(chi2),
                    pulls_R=float(pulls.get("R", float("nan"))),
                    pulls_lA=float(pulls.get("lA", float("nan"))),
                    pulls_omega_b_h2=float(pulls.get("omega_b_h2", float("nan"))),
                    dv_z2=float(dv[2.0]),
                    dv_z3=float(dv[3.0]),
                    dv_z4=float(dv[4.0]),
                    dv_z5=float(dv[5.0]),
                    drift_sign_ok=bool(drift_ok),
                    bbn_dev_z1e8=float(dev_1e8),
                    bbn_dev_z1e9=float(dev_1e9),
                    D_M_star_Mpc=float(pred.get("D_M_star_Mpc", float("nan"))),
                    r_s_star_Mpc=float(pred.get("r_s_star_Mpc", float("nan"))),
                )
            )

    if not rows:
        raise ValueError("No rows produced")

    # Write CSV.
    csv_path = tables_dir / "cmb_highz_hboost_scan.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].as_csv_dict().keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r.as_csv_dict())

    # Feasible subset: drift_ok + chi2 below a loose threshold.
    feasible = [r for r in rows if bool(r.drift_sign_ok) and float(r.chi2_full_base) < 100.0]
    feasible_path = tables_dir / "feasible_subset.csv"
    with feasible_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].as_csv_dict().keys()))
        w.writeheader()
        for r in feasible:
            w.writerow(r.as_csv_dict())

    # Figures.
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: E402

    # 1) chi2 vs A (curve per z_boost_start).
    fig, ax = plt.subplots(figsize=(8.2, 4.8), constrained_layout=True)
    for z_bs in sorted(set(float(r.z_boost_start) for r in rows)):
        xs: List[float] = []
        ys: List[float] = []
        for r in rows:
            if float(r.z_boost_start) != float(z_bs):
                continue
            xs.append(float(r.A_const))
            ys.append(float(r.chi2_full_base))
        ax.plot(xs, ys, marker="o", linewidth=2.0, label=f"z_start={z_bs:g}")
    ax.set_yscale("log")
    ax.set_xlabel("A_const (H -> A*H for z>z_boost_start)")
    ax.set_ylabel("chi2_full_base (strict CHW2018, dm=1)")
    ax.set_title("E2.10 high-z H-boost repair scan (diagnostic)")
    ax.grid(True, alpha=0.25, which="both")
    ax.legend(frameon=False, ncol=2)
    fig1_path = figs_dir / "chi2_vs_A_by_zbooststart.png"
    fig.savefig(fig1_path, dpi=170)
    plt.close(fig)

    # 2) drift vs A (z=4), as a sanity check.
    fig, ax = plt.subplots(figsize=(8.2, 4.2), constrained_layout=True)
    for z_bs in sorted(set(float(r.z_boost_start) for r in rows)):
        xs = []
        ys = []
        for r in rows:
            if float(r.z_boost_start) != float(z_bs):
                continue
            xs.append(float(r.A_const))
            ys.append(float(r.dv_z4))
        ax.plot(xs, ys, marker="o", linewidth=2.0, label=f"z_start={z_bs:g}")
    ax.axhline(0.0, color="k", alpha=0.25, linewidth=1.0)
    ax.set_xlabel("A_const")
    ax.set_ylabel("Δv(z=4) [cm/s over 10y]")
    ax.set_title("Drift window sanity (should be unchanged for z<z_boost_start)")
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False, ncol=2)
    fig2_path = figs_dir / "drift_vs_A.png"
    fig.savefig(fig2_path, dpi=170)
    plt.close(fig)

    # Summary text.
    best = sorted(rows, key=lambda r: float(r.chi2_full_base))
    summary_path = tables_dir / "summary.txt"
    b = best[0]
    lines = [
        "E2.10 high-z H-boost repair scan (diagnostic-only)",
        "",
        f"late-time checkpoint: p={float(p_late):g}  z_transition={float(z_transition):g}",
        f"full-history base: z_relax_start={float(z_relax_start):g}  relax_scale={float(relax_scale):g}  p_target={float(p_target):g}",
        f"bbn clamp: {(float(z_bbn_clamp) if z_bbn_clamp is not None else None)}",
        f"z_star (Hu-Sugiyama fit): {float(z_star_use):.6g}",
        "",
        f"boost grid: z_boost_start={list(z_boost_start_list)}  A_const=[{float(A_min):g},{float(A_max):g}] step={float(A_step):g}",
        f"rs_star_calibration (CHW path stopgap): {float(rs_star_calibration):.10g}",
        "boost support: applied only for z in (z_boost_start, z_star) (so r_s(z*) is unchanged by construction)",
        "",
        f"num_points_total={len(rows)}",
        f"num_points_drift_ok={len([r for r in rows if r.drift_sign_ok])}",
        "",
        "best point (min chi2_full_base):",
        f"  z_boost_start={float(b.z_boost_start):g}  A_const={float(b.A_const):.6g}",
        f"  chi2_full_base={float(b.chi2_full_base):.6g}",
        f"  pulls: R={float(b.pulls_R):.6g}  lA={float(b.pulls_lA):.6g}  omega_b_h2={float(b.pulls_omega_b_h2):.6g}",
        f"  drift Δv(z=4,10y)={float(b.dv_z4):.6g} cm/s  drift_sign_ok={bool(b.drift_sign_ok)}",
        f"  BBN clamp dev: z=1e8 -> {float(b.bbn_dev_z1e8):.3g}, z=1e9 -> {float(b.bbn_dev_z1e9):.3g}",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest: Dict[str, Any] = {
        "diagnostic_only": True,
        "kind": "cmb_e2_highz_hboost_repair_scan",
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "git_commit": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"]),
        "git_branch": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "--abbrev-ref", "HEAD"]),
        "git_dirty": bool(_run_git(["git", "-C", str(REPO_ROOT), "status", "--porcelain=v1"]).strip()),
        "inputs": {"cmb_csv": _relpath(cmb_csv), "cmb_cov": _relpath(cmb_cov)},
        "fixed_params": {
            "H0_km_s_Mpc": float(H0_km_s_Mpc),
            "Omega_m": float(Omega_m),
            "omega_b_h2": float(omega_b_h2),
            "omega_c_h2": float(omega_c_h2),
            "Neff": float(Neff),
            "Tcmb_K": float(Tcmb_K),
        },
        "model": {
            "base_history": {
                "name": "gsc_transition_full_history_guarded_relax",
                "p_late": float(p_late),
                "z_transition": float(z_transition),
                "z_relax_start": float(z_relax_start),
                "relax_scale": float(relax_scale),
                "p_target": float(p_target),
                "z_bbn_clamp": (float(z_bbn_clamp) if z_bbn_clamp is not None else None),
            },
            "boost": {
                "mode": "const",
                "z_boost_start_list": [float(x) for x in z_boost_start_list],
                "z_boost_end": float(z_star_use),
                "A_min": float(A_min),
                "A_max": float(A_max),
                "A_step": float(A_step),
                "transition_width": float(transition_width),
            },
            "rs_star_calibration": float(rs_star_calibration),
            "legacy_rs_star_calibration_constant": float(_RS_STAR_CALIB_CHW2018),
            "z_star_method": "hu_sugiyama",
            "z_star": float(z_star_use),
        },
        "numerics": {"n_D_M": int(n_D_M), "n_r_s": int(n_r_s)},
        "outputs": {
            "outdir": _relpath(out_dir),
            "table": _relpath(csv_path),
            "feasible_subset": _relpath(feasible_path),
            "summary": _relpath(summary_path),
            "fig_chi2": _relpath(fig1_path),
            "fig_drift": _relpath(fig2_path),
        },
        "summary": {
            "best": {
                "z_boost_start": float(b.z_boost_start),
                "A_const": float(b.A_const),
                "chi2_full_base": float(b.chi2_full_base),
                "drift_sign_ok": bool(b.drift_sign_ok),
            }
        },
        "notes": [
            "Diagnostic-only: scans a high-z multiplicative H(z) deformation above z_boost_start.",
            "Drift safety is enforced by design: A(z)=1 for z<=z_boost_start (and measured explicitly).",
            "BBN safety is enforced by the base full-history clamp; the wrapper disables A(z) above z_bbn_clamp.",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return manifest


def main(argv: Optional[Sequence[str]] = None) -> None:
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
    ap.add_argument("--outdir", type=Path, default=Path("v11.0.0/results/diagnostic_cmb_highz_hboost_repair"))

    ap.add_argument("--gsc-p", dest="p_late", type=float, default=0.6)
    ap.add_argument("--gsc-ztrans", dest="z_transition", type=float, default=1.8)
    ap.add_argument("--z-relax-start", type=float, default=5.0)
    ap.add_argument("--relax-scale", type=float, default=0.5)
    ap.add_argument("--p-target", type=float, default=1.5)
    ap.add_argument("--z-bbn-clamp", type=float, default=1.0e7, help="If >0, clamp to LCDM+rad at z>=z_bbn_clamp. Use 0 to disable.")

    ap.add_argument("--z-boost-start-list", type=str, default="5,6,7,8,10")
    ap.add_argument("--A-min", dest="A_min", type=float, default=1.00)
    ap.add_argument("--A-max", dest="A_max", type=float, default=2.00)
    ap.add_argument("--A-step", dest="A_step", type=float, default=0.02)
    ap.add_argument("--transition-width", type=float, default=0.0)

    ap.add_argument("--n-dm", type=int, default=8192)
    ap.add_argument("--n-rs", type=int, default=8192)

    ap.add_argument("--H0", type=float, default=67.4)
    ap.add_argument("--Omega-m", dest="Omega_m", type=float, default=0.315)
    ap.add_argument("--omega-b-h2", type=float, default=0.02237)
    ap.add_argument("--omega-c-h2", type=float, default=0.1200)
    ap.add_argument("--Neff", type=float, default=3.046)
    ap.add_argument("--Tcmb-K", type=float, default=2.7255)

    ap.add_argument("--rs-star-calibration", type=float, default=float(_RS_STAR_CALIB_CHW2018))

    args = ap.parse_args(argv)

    z_bbn_clamp = float(args.z_bbn_clamp)
    z_bbn_clamp_opt = None if (not math.isfinite(z_bbn_clamp) or z_bbn_clamp <= 0.0) else float(z_bbn_clamp)

    run(
        cmb_csv=Path(args.cmb),
        cmb_cov=Path(args.cmb_cov),
        out_dir=Path(args.outdir),
        p_late=float(args.p_late),
        z_transition=float(args.z_transition),
        z_relax_start=float(args.z_relax_start),
        relax_scale=float(args.relax_scale),
        p_target=float(args.p_target),
        z_bbn_clamp=z_bbn_clamp_opt,
        z_boost_start_list=_parse_float_list(str(args.z_boost_start_list)),
        A_min=float(args.A_min),
        A_max=float(args.A_max),
        A_step=float(args.A_step),
        transition_width=float(args.transition_width),
        H0_km_s_Mpc=float(args.H0),
        Omega_m=float(args.Omega_m),
        omega_b_h2=float(args.omega_b_h2),
        omega_c_h2=float(args.omega_c_h2),
        Neff=float(args.Neff),
        Tcmb_K=float(args.Tcmb_K),
        n_D_M=int(args.n_dm),
        n_r_s=int(args.n_rs),
        rs_star_calibration=float(args.rs_star_calibration),
    )


if __name__ == "__main__":  # pragma: no cover
    main()

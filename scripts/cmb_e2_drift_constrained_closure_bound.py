#!/usr/bin/env python3
"""E2.10 diagnostic: drift-constrained closure Pareto bound.

Goal
----
Quantify the tradeoff between:
- preserving positive redshift drift in the test window z in [2,5], and
- reducing strict CHW2018 compressed-prior chi2 (R, lA, omega_b_h2)
  without free dm/rs fitting knobs.

Construction
------------
For z in [z_window_min, z_window_max], define a one-parameter deformation:

    H_mod(z; s) = (1-s) * H_base(z) + s * H_cap(z),  s in [0,1)

with H_cap(z) = H0 * (1+z) * (1-epsilon_cap), so s -> 1 approaches
drift -> 0^+ while keeping positive drift by construction in the window.

Outside the drift window:
- z <= z_handoff: keep the baseline late-time GSC transition history
- z >  z_handoff: switch to a standard high-z reference history (flat LCDM+rad)

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
from gsc.early_time.cmb_distance_priors import _RS_STAR_CALIB_CHW2018  # noqa: E402
from gsc.histories.full_range import FlatLCDMRadHistory  # noqa: E402
from gsc.measurement_model import GSCTransitionHistory, H0_to_SI, delta_v_cm_s, z_dot_sandage_loeb  # noqa: E402


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


def _default_s_grid() -> List[float]:
    vals = [i * 0.05 for i in range(0, 20)]  # 0.00..0.95
    vals.extend([0.98, 0.99, 0.995])
    # stable de-dup + strict [0,1)
    out: List[float] = []
    seen: set[int] = set()
    for x in vals:
        xx = float(x)
        if not (0.0 <= xx < 1.0):
            continue
        k = int(round(xx * 1.0e12))
        if k in seen:
            continue
        seen.add(k)
        out.append(xx)
    return sorted(out)


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
class DriftConstrainedHistory:
    """Piecewise history for the drift-constrained closure bound diagnostic."""

    low_history: GSCTransitionHistory
    highz_reference: FlatLCDMRadHistory
    s: float
    z_window_min: float
    z_window_max: float
    z_handoff: float
    epsilon_cap: float

    def H(self, z: float) -> float:
        zz = float(z)
        if zz < -1.0:
            raise ValueError("Require z >= -1")

        # Keep the high-z segment explicit and standard.
        if zz > float(self.z_handoff):
            return float(self.highz_reference.H(zz))

        hb = float(self.low_history.H(zz))
        if float(self.z_window_min) <= zz <= float(self.z_window_max):
            H0 = float(self.low_history.H(0.0))
            hcap = float(H0) * (1.0 + zz) * (1.0 - float(self.epsilon_cap))
            return (1.0 - float(self.s)) * float(hb) + float(self.s) * float(hcap)
        return float(hb)


@dataclass(frozen=True)
class Row:
    s: float
    chi2_cmb: float
    pull_R: float
    pull_lA: float
    pull_omega_b_h2: float
    D_M_star_Mpc: float
    r_s_star_Mpc: float
    dv_z2_cm_s_10y: float
    dv_z3_cm_s_10y: float
    dv_z4_cm_s_10y: float
    dv_z5_cm_s_10y: float
    drift_sign_ok: bool
    drift_sign_ok_dense: bool

    def as_csv(self) -> Dict[str, str]:
        def f(x: float) -> str:
            if not math.isfinite(float(x)):
                return ""
            return f"{float(x):.16g}"

        return {
            "s": f(self.s),
            "chi2_cmb": f(self.chi2_cmb),
            "pull_R": f(self.pull_R),
            "pull_lA": f(self.pull_lA),
            "pull_omega_b_h2": f(self.pull_omega_b_h2),
            "DM_star_Mpc": f(self.D_M_star_Mpc),
            "rs_star_Mpc": f(self.r_s_star_Mpc),
            "dv_z2_cm_s_10y": f(self.dv_z2_cm_s_10y),
            "dv_z3_cm_s_10y": f(self.dv_z3_cm_s_10y),
            "dv_z4_cm_s_10y": f(self.dv_z4_cm_s_10y),
            "dv_z5_cm_s_10y": f(self.dv_z5_cm_s_10y),
            "drift_sign_ok": ("True" if bool(self.drift_sign_ok) else "False"),
            "drift_sign_ok_dense": ("True" if bool(self.drift_sign_ok_dense) else "False"),
        }


def _dense_sign_check(
    *,
    history,
    z_min: float,
    z_max: float,
    n: int,
) -> bool:
    H0 = float(history.H(0.0))
    if not (math.isfinite(H0) and H0 > 0.0):
        return False
    zs = np.linspace(float(z_min), float(z_max), int(n))
    for z in zs:
        dzdt = float(z_dot_sandage_loeb(z=float(z), H0=H0, H_of_z=history.H))
        if (not math.isfinite(dzdt)) or (dzdt <= 0.0):
            return False
    return True


def run(
    *,
    cmb_csv: Path,
    cmb_cov: Path,
    out_dir: Path,
    p_late: float,
    z_transition: float,
    H0_km_s_Mpc: float,
    Omega_m: float,
    omega_b_h2: float,
    omega_c_h2: float,
    Neff: float,
    Tcmb_K: float,
    z_window_min: float,
    z_window_max: float,
    z_handoff: float,
    epsilon_cap: float,
    s_values: Sequence[float],
    n_D_M: int,
    n_r_s: int,
    rs_star_calibration: float,
) -> Dict[str, Any]:
    out_dir = out_dir.resolve()
    tables_dir = out_dir / "tables"
    figs_dir = out_dir / "figures"
    _ensure_dir(tables_dir)
    _ensure_dir(figs_dir)

    if not (p_late > 0.0 and math.isfinite(p_late)):
        raise ValueError("p_late must be finite and > 0")
    if not (z_transition >= 0.0 and math.isfinite(z_transition)):
        raise ValueError("z_transition must be finite and >= 0")
    if not (H0_km_s_Mpc > 0.0 and math.isfinite(H0_km_s_Mpc)):
        raise ValueError("H0 must be finite and > 0")
    if not (0.0 < Omega_m < 1.0 and math.isfinite(Omega_m)):
        raise ValueError("Omega_m must be finite and in (0,1)")
    if not (omega_b_h2 > 0.0 and omega_c_h2 >= 0.0):
        raise ValueError("omega_b_h2 must be >0 and omega_c_h2 >=0")
    if not (z_window_min >= 0.0 and z_window_max > z_window_min):
        raise ValueError("Require 0<=z_window_min<z_window_max")
    if not (z_handoff >= z_window_max):
        raise ValueError("z_handoff must be >= z_window_max")
    if not (0.0 <= epsilon_cap < 1.0):
        raise ValueError("epsilon_cap must be in [0,1)")
    if n_D_M < 512 or n_r_s < 512:
        raise ValueError("integration grids too small")
    if not (rs_star_calibration > 0.0 and math.isfinite(rs_star_calibration)):
        raise ValueError("rs_star_calibration must be finite and > 0")

    s_grid = sorted(float(s) for s in s_values)
    if not s_grid:
        raise ValueError("Empty s grid")
    for s in s_grid:
        if not (0.0 <= s < 1.0 and math.isfinite(s)):
            raise ValueError(f"s must be in [0,1), got {s}")

    ds = CMBPriorsDataset.from_csv(cmb_csv, cov_path=cmb_cov)
    keys = ds.keys
    for req in ("R", "lA", "omega_b_h2"):
        if req not in keys:
            raise ValueError(f"Dataset missing required key: {req}")
    mean = np.asarray(ds.values, dtype=float)
    cov = _effective_cov(ds)

    H0_si = float(H0_to_SI(float(H0_km_s_Mpc)))
    low = GSCTransitionHistory(
        H0=float(H0_si),
        Omega_m=float(Omega_m),
        Omega_Lambda=float(1.0 - float(Omega_m)),
        p=float(p_late),
        z_transition=float(z_transition),
    )
    highz = FlatLCDMRadHistory(
        H0=float(H0_si),
        Omega_m=float(Omega_m),
        N_eff=float(Neff),
        Tcmb_K=float(Tcmb_K),
    )

    rows: List[Row] = []
    for s in s_grid:
        hist = DriftConstrainedHistory(
            low_history=low,
            highz_reference=highz,
            s=float(s),
            z_window_min=float(z_window_min),
            z_window_max=float(z_window_max),
            z_handoff=float(z_handoff),
            epsilon_cap=float(epsilon_cap),
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

        drift_years = 10.0
        dv2 = float(delta_v_cm_s(z=2.0, years=drift_years, H0=float(hist.H(0.0)), H_of_z=hist.H))
        dv3 = float(delta_v_cm_s(z=3.0, years=drift_years, H0=float(hist.H(0.0)), H_of_z=hist.H))
        dv4 = float(delta_v_cm_s(z=4.0, years=drift_years, H0=float(hist.H(0.0)), H_of_z=hist.H))
        dv5 = float(delta_v_cm_s(z=5.0, years=drift_years, H0=float(hist.H(0.0)), H_of_z=hist.H))
        sign_ok = bool(all(v > 0.0 for v in (dv2, dv3, dv4, dv5)))
        sign_ok_dense = _dense_sign_check(history=hist, z_min=float(z_window_min), z_max=float(z_window_max), n=61)

        rows.append(
            Row(
                s=float(s),
                chi2_cmb=float(chi2),
                pull_R=float(pulls.get("R", float("nan"))),
                pull_lA=float(pulls.get("lA", float("nan"))),
                pull_omega_b_h2=float(pulls.get("omega_b_h2", float("nan"))),
                D_M_star_Mpc=float(pred.get("D_M_star_Mpc", float("nan"))),
                r_s_star_Mpc=float(pred.get("r_s_star_Mpc", float("nan"))),
                dv_z2_cm_s_10y=float(dv2),
                dv_z3_cm_s_10y=float(dv3),
                dv_z4_cm_s_10y=float(dv4),
                dv_z5_cm_s_10y=float(dv5),
                drift_sign_ok=bool(sign_ok),
                drift_sign_ok_dense=bool(sign_ok_dense),
            )
        )

    csv_path = tables_dir / "cmb_drift_constrained_bound_scan.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].as_csv().keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r.as_csv())

    # Summary text.
    sorted_by_chi2 = sorted(rows, key=lambda r: float(r.chi2_cmb))
    best = sorted_by_chi2[0]
    drift_ok_rows = [r for r in rows if r.drift_sign_ok and r.drift_sign_ok_dense]
    best_drift_ok = sorted(drift_ok_rows, key=lambda r: float(r.chi2_cmb))[0] if drift_ok_rows else None
    txt = tables_dir / "summary.txt"
    lines = [
        "E2.10 drift-constrained closure bound (diagnostic-only)",
        "",
        "Model:",
        f"  gsc_transition: p={float(p_late):g}  z_transition={float(z_transition):g}",
        f"  H0={float(H0_km_s_Mpc):g}  Omega_m={float(Omega_m):g}",
        f"  high-z reference: flat LCDM + rad (z>{float(z_handoff):g})",
        "",
        "Drift-window deformation:",
        f"  H_mod(z;s)=(1-s)H_base+sH_cap on z in [{float(z_window_min):g},{float(z_window_max):g}]",
        f"  H_cap(z)=H0(1+z)*(1-epsilon_cap), epsilon_cap={float(epsilon_cap):.3g}",
        f"  s-grid points: {len(s_grid)}",
        "",
        f"Best chi2 point: s={float(best.s):.6g}, chi2_cmb={float(best.chi2_cmb):.6g}, dv_z4={float(best.dv_z4_cm_s_10y):.6g} cm/s/10y, drift_ok={best.drift_sign_ok and best.drift_sign_ok_dense}",
    ]
    if best_drift_ok is not None:
        lines.append(
            f"Best drift-ok point: s={float(best_drift_ok.s):.6g}, chi2_cmb={float(best_drift_ok.chi2_cmb):.6g}, dv_z4={float(best_drift_ok.dv_z4_cm_s_10y):.6g} cm/s/10y"
        )
    else:
        lines.append("No drift-ok points on this s-grid.")
    txt.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Figures.
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: E402

    # 1) chi2 vs drift amplitude (Pareto view).
    xs = [float(r.dv_z4_cm_s_10y) for r in rows]
    ys = [float(r.chi2_cmb) for r in rows]
    cs = [float(r.s) for r in rows]

    fig, ax = plt.subplots(figsize=(8.2, 4.8), constrained_layout=True)
    sc = ax.scatter(xs, ys, c=cs, cmap="viridis", s=40)
    ax.set_yscale("log")
    ax.set_xlabel("Δv(z=4) [cm/s over 10y]")
    ax.set_ylabel("chi2_cmb (strict CHW2018)")
    ax.set_title("E2.10 diagnostic: CMB closure vs drift amplitude")
    ax.grid(True, alpha=0.25, which="both")
    cb = fig.colorbar(sc, ax=ax, label="s")
    cb.ax.tick_params(labelsize=8)
    fig1 = figs_dir / "chi2_cmb_vs_dv_z4.png"
    fig.savefig(fig1, dpi=170)
    plt.close(fig)

    # 2) pulls vs drift amplitude.
    by_x = sorted(rows, key=lambda r: float(r.dv_z4_cm_s_10y))
    x2 = [float(r.dv_z4_cm_s_10y) for r in by_x]
    fig, ax = plt.subplots(figsize=(8.2, 4.6), constrained_layout=True)
    ax.plot(x2, [float(r.pull_R) for r in by_x], marker="o", linewidth=1.8, label="pull R")
    ax.plot(x2, [float(r.pull_lA) for r in by_x], marker="o", linewidth=1.8, label="pull lA")
    ax.plot(x2, [float(r.pull_omega_b_h2) for r in by_x], marker="o", linewidth=1.8, label="pull omega_b_h2")
    ax.axhline(0.0, color="k", alpha=0.25, linewidth=1.0)
    ax.set_xlabel("Δv(z=4) [cm/s over 10y]")
    ax.set_ylabel("pull [sigma]")
    ax.set_title("E2.10 diagnostic: CHW2018 pulls vs drift amplitude")
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False)
    fig2 = figs_dir / "pulls_vs_dv_z4.png"
    fig.savefig(fig2, dpi=170)
    plt.close(fig)

    # 3) optional DM_star vs s
    fig, ax = plt.subplots(figsize=(8.2, 4.2), constrained_layout=True)
    ax.plot([float(r.s) for r in rows], [float(r.D_M_star_Mpc) for r in rows], marker="o", linewidth=2.0)
    ax.set_xlabel("s")
    ax.set_ylabel("D_M(z*) [Mpc]")
    ax.set_title("E2.10 diagnostic: D_M(z*) vs drift-window slack s")
    ax.grid(True, alpha=0.25)
    fig3 = figs_dir / "DM_star_vs_s.png"
    fig.savefig(fig3, dpi=170)
    plt.close(fig)

    # Manifest.
    manifest: Dict[str, Any] = {
        "diagnostic_only": True,
        "kind": "cmb_e2_drift_constrained_closure_bound",
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "git_commit": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"]),
        "git_branch": _run_git(["git", "-C", str(REPO_ROOT), "rev-parse", "--abbrev-ref", "HEAD"]),
        "git_dirty": bool(_run_git(["git", "-C", str(REPO_ROOT), "status", "--porcelain=v1"]).strip()),
        "inputs": {"cmb_csv": _relpath(cmb_csv), "cmb_cov": _relpath(cmb_cov)},
        "model": {
            "baseline": {
                "name": "gsc_transition",
                "p_late": float(p_late),
                "z_transition": float(z_transition),
                "H0_km_s_Mpc": float(H0_km_s_Mpc),
                "Omega_m": float(Omega_m),
                "Omega_Lambda_lowz": float(1.0 - float(Omega_m)),
            },
            "highz_reference": {
                "name": "flat_lcdm_rad",
                "handoff_z_gt": float(z_handoff),
                "Neff": float(Neff),
                "Tcmb_K": float(Tcmb_K),
            },
            "drift_window_deformation": {
                "z_window_min": float(z_window_min),
                "z_window_max": float(z_window_max),
                "epsilon_cap": float(epsilon_cap),
                "s_grid": [float(s) for s in s_grid],
                "formula": "H_mod=(1-s)H_base+s*H_cap, H_cap=H0(1+z)(1-epsilon_cap)",
            },
            "distance_priors": {
                "dm_star_calibration": 1.0,
                "rs_star_calibration": float(rs_star_calibration),
                "legacy_rs_star_calibration_constant": float(_RS_STAR_CALIB_CHW2018),
            },
            "early_inputs": {
                "omega_b_h2": float(omega_b_h2),
                "omega_c_h2": float(omega_c_h2),
                "Neff": float(Neff),
                "Tcmb_K": float(Tcmb_K),
            },
        },
        "numerics": {"n_D_M": int(n_D_M), "n_r_s": int(n_r_s)},
        "outputs": {
            "outdir": _relpath(out_dir),
            "table_scan": _relpath(csv_path),
            "summary_text": _relpath(txt),
            "fig_chi2_vs_dv_z4": _relpath(fig1),
            "fig_pulls_vs_dv_z4": _relpath(fig2),
            "fig_DM_star_vs_s": _relpath(fig3),
        },
        "summary": {
            "num_points": int(len(rows)),
            "num_drift_ok_discrete": int(sum(1 for r in rows if r.drift_sign_ok)),
            "num_drift_ok_dense": int(sum(1 for r in rows if r.drift_sign_ok_dense)),
            "best_chi2": {
                "s": float(best.s),
                "chi2_cmb": float(best.chi2_cmb),
                "dv_z4_cm_s_10y": float(best.dv_z4_cm_s_10y),
                "drift_sign_ok": bool(best.drift_sign_ok),
                "drift_sign_ok_dense": bool(best.drift_sign_ok_dense),
            },
            "best_drift_ok": (
                None
                if best_drift_ok is None
                else {
                    "s": float(best_drift_ok.s),
                    "chi2_cmb": float(best_drift_ok.chi2_cmb),
                    "dv_z4_cm_s_10y": float(best_drift_ok.dv_z4_cm_s_10y),
                }
            ),
        },
        "notes": [
            "Diagnostic-only Pareto-style bound between drift amplitude and strict CHW2018 closure.",
            "No dm/rs fitting is performed in this scan.",
            "High-z segment uses flat LCDM+rad reference above z_handoff.",
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
    ap.add_argument("--outdir", type=Path, default=Path("v11.0.0/results/diagnostic_cmb_drift_constrained_bound"))

    ap.add_argument("--gsc-p", dest="p_late", type=float, default=0.6)
    ap.add_argument("--gsc-ztrans", dest="z_transition", type=float, default=1.8)
    ap.add_argument("--H0", type=float, default=67.4)
    ap.add_argument("--Omega-m", dest="Omega_m", type=float, default=0.315)
    ap.add_argument("--omega-b-h2", type=float, default=0.02237)
    ap.add_argument("--omega-c-h2", type=float, default=0.1200)
    ap.add_argument("--Neff", type=float, default=3.046)
    ap.add_argument("--Tcmb-K", type=float, default=2.7255)

    ap.add_argument("--z-window-min", type=float, default=2.0)
    ap.add_argument("--z-window-max", type=float, default=5.0)
    ap.add_argument("--z-handoff", type=float, default=5.0)
    ap.add_argument("--epsilon-cap", type=float, default=1.0e-6)
    ap.add_argument(
        "--s-grid",
        type=str,
        default="",
        help="CSV list of s values in [0,1). If omitted, uses default dense grid.",
    )

    ap.add_argument("--n-dm", type=int, default=8192)
    ap.add_argument("--n-rs", type=int, default=8192)
    ap.add_argument("--rs-star-calibration", type=float, default=float(_RS_STAR_CALIB_CHW2018))

    args = ap.parse_args(argv)
    if str(args.s_grid).strip():
        s_grid = _parse_float_list(str(args.s_grid))
    else:
        s_grid = _default_s_grid()

    run(
        cmb_csv=Path(args.cmb),
        cmb_cov=Path(args.cmb_cov),
        out_dir=Path(args.outdir),
        p_late=float(args.p_late),
        z_transition=float(args.z_transition),
        H0_km_s_Mpc=float(args.H0),
        Omega_m=float(args.Omega_m),
        omega_b_h2=float(args.omega_b_h2),
        omega_c_h2=float(args.omega_c_h2),
        Neff=float(args.Neff),
        Tcmb_K=float(args.Tcmb_K),
        z_window_min=float(args.z_window_min),
        z_window_max=float(args.z_window_max),
        z_handoff=float(args.z_handoff),
        epsilon_cap=float(args.epsilon_cap),
        s_values=s_grid,
        n_D_M=int(args.n_dm),
        n_r_s=int(args.n_rs),
        rs_star_calibration=float(args.rs_star_calibration),
    )


if __name__ == "__main__":  # pragma: no cover
    main()

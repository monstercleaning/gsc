#!/usr/bin/env python3
"""E2.8 diagnostic: drift-protected full-history closure scan (no-stitch).

Motivation
----------
E2.7 showed a key tension:
- fast high-z relaxation can reduce strict CHW2018 chi^2 in the *full-history* (no-stitch) mode,
  but it can also contaminate the primary late-time falsifier: the redshift-drift sign in z~2–5.

E2.8 introduces a minimal "guarded relax" variant:
- keep the exact late-time GSC power-law behavior up to a chosen `z_relax_start` (>=5 by default),
  protecting the drift window,
- allow relaxation (convergence to matter-era slope) only for z > z_relax_start.

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
from gsc.early_time.cmb_distance_priors import _RS_STAR_CALIB_CHW2018, _comoving_distance_model_to_z_m  # noqa: E402
from gsc.histories.full_range import GSCTransitionFullHistory  # noqa: E402
from gsc.measurement_model import GSCTransitionHistory, H0_to_SI, MPC_SI, delta_v_cm_s  # noqa: E402


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


def _apply_dm_rs_to_pred_raw(*, pred_raw: Dict[str, float], dm: float, rs: float) -> Dict[str, float]:
    if not (dm > 0 and math.isfinite(dm)):
        raise ValueError("dm must be finite and > 0")
    if not (rs > 0 and math.isfinite(rs)):
        raise ValueError("rs must be finite and > 0")

    out = dict(pred_raw)
    out["dm_star_calibration"] = float(dm)
    out["dm_star_calibration_applied"] = bool(float(dm) != 1.0)
    out["rs_star_calibration"] = float(rs)
    out["rs_star_calibration_applied"] = bool(float(rs) != 1.0)

    out["R"] = float(dm) * float(pred_raw["R"])
    out["lA"] = (float(dm) / float(rs)) * float(pred_raw["lA"])
    if "theta_star" in out:
        out["theta_star"] = (float(rs) / float(dm)) * float(pred_raw["theta_star"])
    if "D_M_star_Mpc" in out:
        out["D_M_star_Mpc"] = float(dm) * float(pred_raw["D_M_star_Mpc"])
    if "r_s_star_Mpc" in out:
        out["r_s_star_Mpc"] = float(rs) * float(pred_raw["r_s_star_Mpc"])
    return out


def _fit_dm_rs_against_chw2018(
    *,
    ds: CMBPriorsDataset,
    mean: np.ndarray,
    cov: np.ndarray,
    W: np.ndarray,
    pred_raw: Dict[str, float],
    rs_min: float,
    rs_max: float,
    rs_step: float,
    dm_min: float = 1e-6,
) -> Tuple[float, float, float]:
    keys = ds.keys
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

    # b = mu - pred(eps=0, dm=0, rs=...) but we solve for dm only, for each rs.
    mu = mean
    b = np.array([float(mu[iR]) - 0.0, float(mu[ilA]) - 0.0, float(mu[iob]) - float(ob0)], dtype=float)

    best = (float("inf"), float("nan"), float("nan"))  # chi2, dm, rs
    n = int(math.floor((float(rs_max) - float(rs_min)) / float(rs_step))) + 1
    for i in range(int(n)):
        rs = float(rs_min) + float(i) * float(rs_step)
        if rs > float(rs_max) + 1e-15:
            break
        # A = [R0, lA0/rs, 0] so pred = dm*A + [0,0,ob0] in the 3-dim CHW2018 vector.
        A = np.array([float(R0), float(lA0) / float(rs), 0.0], dtype=float)
        num = float(A.T @ W @ b)
        den = float(A.T @ W @ A)
        if not (den > 0 and math.isfinite(den)):
            continue
        dm = float(num / den)
        if dm < float(dm_min):
            dm = float(dm_min)
        pred = _apply_dm_rs_to_pred_raw(pred_raw=pred_raw, dm=float(dm), rs=float(rs))
        chi2 = float(ds.chi2_from_values(pred).chi2)
        if chi2 < best[0]:
            best = (float(chi2), float(dm), float(rs))
    return (float(best[1]), float(best[2]), float(best[0]))


def _effective_const_A(*, D_low_Mpc: float, D_total_Mpc: float, dm_fit: float) -> Optional[float]:
    """Map a DM scaling dm_fit to an equivalent constant H-boost A above the low-z cutoff.

    If H -> A*H on the high-z segment, then D_high -> D_high/A.
    Solve: D_low + D_high/A = dm_fit * D_total, where D_high=D_total-D_low.
    """
    if not (math.isfinite(D_low_Mpc) and math.isfinite(D_total_Mpc) and math.isfinite(dm_fit)):
        return None
    if D_low_Mpc < 0 or D_total_Mpc <= 0 or dm_fit <= 0:
        return None
    D_high = float(D_total_Mpc) - float(D_low_Mpc)
    if not (D_high > 0):
        return None
    denom = float(dm_fit) * float(D_total_Mpc) - float(D_low_Mpc)
    if not (denom > 0):
        return None
    A = float(D_high) / float(denom)
    if not (A > 0 and math.isfinite(A)):
        return None
    return float(A)


@dataclass(frozen=True)
class Row:
    z_relax_start: float
    relax_scale: float

    chi2_full_base: float
    pulls_full_base_R: float
    pulls_full_base_lA: float

    dm_fit_full: float
    rs_fit_full: float
    chi2_full_min: float

    A_required_const: Optional[float]
    deltaG_required: Optional[float]

    dv_base_z2: float
    dv_base_z3: float
    dv_base_z4: float
    dv_base_z5: float

    dv_full_z2: float
    dv_full_z3: float
    dv_full_z4: float
    dv_full_z5: float

    drift_sign_ok: bool

    def as_csv_dict(self) -> Dict[str, str]:
        def f(x: float) -> str:
            if not math.isfinite(float(x)):
                return ""
            return f"{float(x):.16g}"

        def fo(x: Optional[float]) -> str:
            if x is None:
                return ""
            return f(float(x))

        return {
            "z_relax_start": f(self.z_relax_start),
            "relax_scale": f(self.relax_scale),
            "chi2_full_base": f(self.chi2_full_base),
            "pulls_full_base_R": f(self.pulls_full_base_R),
            "pulls_full_base_lA": f(self.pulls_full_base_lA),
            "dm_fit_full": f(self.dm_fit_full),
            "rs_fit_full": f(self.rs_fit_full),
            "chi2_full_min": f(self.chi2_full_min),
            "A_required_const": fo(self.A_required_const),
            "deltaG_required": fo(self.deltaG_required),
            "dv_base_z2_cm_s_10y": f(self.dv_base_z2),
            "dv_base_z3_cm_s_10y": f(self.dv_base_z3),
            "dv_base_z4_cm_s_10y": f(self.dv_base_z4),
            "dv_base_z5_cm_s_10y": f(self.dv_base_z5),
            "dv_full_z2_cm_s_10y": f(self.dv_full_z2),
            "dv_full_z3_cm_s_10y": f(self.dv_full_z3),
            "dv_full_z4_cm_s_10y": f(self.dv_full_z4),
            "dv_full_z5_cm_s_10y": f(self.dv_full_z5),
            "drift_sign_ok": ("True" if bool(self.drift_sign_ok) else "False"),
        }


def run(
    *,
    cmb_csv: Path,
    cmb_cov: Path,
    out_dir: Path,
    p_late: float,
    z_transition: float,
    z_relax_start_list: Sequence[float],
    relax_scale_list: Sequence[float],
    p_target: float,
    z_bbn_clamp: Optional[float],
    n_D_M: int,
    n_r_s: int,
    H0_km_s_Mpc: float,
    Omega_m: float,
    omega_b_h2: float,
    omega_c_h2: float,
    Neff: float,
    Tcmb_K: float,
    rs_min: float,
    rs_max: float,
    rs_step: float,
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
    if not z_relax_start_list:
        raise ValueError("Empty z_relax_start_list")
    if not relax_scale_list:
        raise ValueError("Empty relax_scale_list")
    if any((not (z >= float(z_transition) and math.isfinite(z))) for z in z_relax_start_list):
        raise ValueError("z_relax_start must be finite and >= z_transition")
    if any((not (s > 0 and math.isfinite(s))) for s in relax_scale_list):
        raise ValueError("relax_scale must be finite and > 0")
    if not (p_target > 0 and math.isfinite(p_target)):
        raise ValueError("p_target must be finite and > 0")

    if n_D_M < 512 or n_r_s < 512:
        raise ValueError("integration grids too small")

    # Load strict CHW2018 priors (vector+cov).
    ds = CMBPriorsDataset.from_csv(cmb_csv, cov_path=cmb_cov)
    keys = ds.keys
    mean = np.asarray(ds.values, dtype=float)
    cov = _effective_cov(ds)
    W = np.linalg.inv(cov)

    # Drift baseline (late-time history only).
    hist_base = GSCTransitionHistory(
        H0=H0_to_SI(float(H0_km_s_Mpc)),
        Omega_m=float(Omega_m),
        Omega_Lambda=1.0 - float(Omega_m),
        p=float(p_late),
        z_transition=float(z_transition),
    )
    drift_years = 10.0
    dv_base = {
        2.0: float(delta_v_cm_s(z=2.0, years=drift_years, H0=float(hist_base.H(0.0)), H_of_z=hist_base.H)),
        3.0: float(delta_v_cm_s(z=3.0, years=drift_years, H0=float(hist_base.H(0.0)), H_of_z=hist_base.H)),
        4.0: float(delta_v_cm_s(z=4.0, years=drift_years, H0=float(hist_base.H(0.0)), H_of_z=hist_base.H)),
        5.0: float(delta_v_cm_s(z=5.0, years=drift_years, H0=float(hist_base.H(0.0)), H_of_z=hist_base.H)),
    }

    rows: List[Row] = []
    for zrs in sorted([float(z) for z in z_relax_start_list]):
        for s in sorted([float(x) for x in relax_scale_list]):
            hist_full = GSCTransitionFullHistory(
                H0=H0_to_SI(float(H0_km_s_Mpc)),
                Omega_m=float(Omega_m),
                p_late=float(p_late),
                z_transition=float(z_transition),
                z_relax=float(s),
                z_relax_start=float(zrs),
                p_target=float(p_target),
                N_eff=float(Neff),
                Tcmb_K=float(Tcmb_K),
                z_bbn_clamp=float(z_bbn_clamp) if z_bbn_clamp is not None else None,
            )

            pred_raw_full = compute_full_history_distance_priors(
                history_full=hist_full,
                omega_b_h2=float(omega_b_h2),
                omega_c_h2=float(omega_c_h2),
                N_eff=float(Neff),
                Tcmb_K=float(Tcmb_K),
                rs_star_calibration=1.0,
                dm_star_calibration=1.0,
                n_D_M=int(n_D_M),
                n_r_s=int(n_r_s),
            )

            pred_base_full = _apply_dm_rs_to_pred_raw(pred_raw=pred_raw_full, dm=1.0, rs=1.0)
            chi2_base_full = float(ds.chi2_from_values(pred_base_full).chi2)
            pulls_base_full = _diag_pulls(keys=keys, mean=mean, cov=cov, pred=pred_base_full)

            dm_fit_f, rs_fit_f, chi2_min_f = _fit_dm_rs_against_chw2018(
                ds=ds,
                mean=mean,
                cov=cov,
                W=W,
                pred_raw=pred_raw_full,
                rs_min=float(rs_min),
                rs_max=float(rs_max),
                rs_step=float(rs_step),
            )

            # Interpretation-only mapping: above z_relax_start.
            D_total = float(pred_raw_full.get("D_M_star_Mpc_raw", float("nan")))
            D_low_m = _comoving_distance_model_to_z_m(z=float(zrs), model=hist_full, n=4096)
            D_low = float(D_low_m / float(MPC_SI))
            A_req = _effective_const_A(D_low_Mpc=float(D_low), D_total_Mpc=float(D_total), dm_fit=float(dm_fit_f))
            dG = None if A_req is None else float(A_req) * float(A_req) - 1.0

            dv_full = {
                2.0: float(delta_v_cm_s(z=2.0, years=drift_years, H0=float(hist_full.H(0.0)), H_of_z=hist_full.H)),
                3.0: float(delta_v_cm_s(z=3.0, years=drift_years, H0=float(hist_full.H(0.0)), H_of_z=hist_full.H)),
                4.0: float(delta_v_cm_s(z=4.0, years=drift_years, H0=float(hist_full.H(0.0)), H_of_z=hist_full.H)),
                5.0: float(delta_v_cm_s(z=5.0, years=drift_years, H0=float(hist_full.H(0.0)), H_of_z=hist_full.H)),
            }
            drift_ok = bool(all(float(v) > 0.0 for v in dv_full.values()))

            rows.append(
                Row(
                    z_relax_start=float(zrs),
                    relax_scale=float(s),
                    chi2_full_base=float(chi2_base_full),
                    pulls_full_base_R=float(pulls_base_full.get("R", float("nan"))),
                    pulls_full_base_lA=float(pulls_base_full.get("lA", float("nan"))),
                    dm_fit_full=float(dm_fit_f),
                    rs_fit_full=float(rs_fit_f),
                    chi2_full_min=float(chi2_min_f),
                    A_required_const=(float(A_req) if A_req is not None else None),
                    deltaG_required=(float(dG) if dG is not None else None),
                    dv_base_z2=float(dv_base[2.0]),
                    dv_base_z3=float(dv_base[3.0]),
                    dv_base_z4=float(dv_base[4.0]),
                    dv_base_z5=float(dv_base[5.0]),
                    dv_full_z2=float(dv_full[2.0]),
                    dv_full_z3=float(dv_full[3.0]),
                    dv_full_z4=float(dv_full[4.0]),
                    dv_full_z5=float(dv_full[5.0]),
                    drift_sign_ok=bool(drift_ok),
                )
            )

    if not rows:
        raise ValueError("No rows produced")

    # Write CSV.
    csv_path = tables_dir / "cmb_full_history_guarded_relax_scan.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].as_csv_dict().keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r.as_csv_dict())

    # Also write feasible subset (drift ok + chi2 under a loose threshold), for convenience.
    feasible = [r for r in rows if bool(r.drift_sign_ok) and float(r.chi2_full_base) < 1.0e5]
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

    # 1) chi2 vs z_relax_start (one curve per relax_scale).
    fig, ax = plt.subplots(figsize=(7.8, 4.8), constrained_layout=True)
    for s in sorted(set(float(r.relax_scale) for r in rows)):
        xs: List[float] = []
        ys: List[float] = []
        for r in rows:
            if float(r.relax_scale) != float(s):
                continue
            xs.append(float(r.z_relax_start))
            ys.append(float(r.chi2_full_base))
        ax.plot(xs, ys, marker="o", linewidth=2.0, label=f"scale={s:g}")
    ax.set_yscale("log")
    ax.set_xlabel("z_relax_start (guard)")
    ax.set_ylabel("chi2_full_base (strict CHW2018, no-fudge)")
    ax.set_title("E2.8 guarded full-history: chi2 vs relax start")
    ax.grid(True, alpha=0.25, which="both")
    ax.legend(frameon=False, ncol=2)
    fig1_path = figs_dir / "chi2_full_base_vs_z_relax_start.png"
    fig.savefig(fig1_path, dpi=160)
    plt.close(fig)

    # 2) drift sign map (Δv(z=4) sign).
    zrs_vals = sorted(set(float(r.z_relax_start) for r in rows))
    s_vals = sorted(set(float(r.relax_scale) for r in rows))
    grid = np.full((len(s_vals), len(zrs_vals)), np.nan, dtype=float)
    for r in rows:
        i = s_vals.index(float(r.relax_scale))
        j = zrs_vals.index(float(r.z_relax_start))
        grid[i, j] = 1.0 if float(r.dv_full_z4) > 0 else -1.0
    fig, ax = plt.subplots(figsize=(7.8, 4.2), constrained_layout=True)
    im = ax.imshow(grid, origin="lower", aspect="auto", vmin=-1.0, vmax=1.0, cmap="coolwarm")
    ax.set_xticks(list(range(len(zrs_vals))))
    ax.set_xticklabels([f"{v:g}" for v in zrs_vals])
    ax.set_yticks(list(range(len(s_vals))))
    ax.set_yticklabels([f"{v:g}" for v in s_vals])
    ax.set_xlabel("z_relax_start")
    ax.set_ylabel("relax_scale (x units)")
    ax.set_title("Drift sign map: sign(Δv(z=4) over 10y)")
    fig2_path = figs_dir / "drift_sign_map.png"
    fig.colorbar(im, ax=ax, fraction=0.05, pad=0.02)
    fig.savefig(fig2_path, dpi=160)
    plt.close(fig)

    # 3) dm_fit vs z_relax_start (one curve per relax_scale).
    fig, ax = plt.subplots(figsize=(7.8, 4.8), constrained_layout=True)
    for s in sorted(set(float(r.relax_scale) for r in rows)):
        xs = []
        ys = []
        for r in rows:
            if float(r.relax_scale) != float(s):
                continue
            xs.append(float(r.z_relax_start))
            ys.append(float(r.dm_fit_full))
        ax.plot(xs, ys, marker="o", linewidth=2.0, label=f"scale={s:g}")
    ax.axhline(1.0, color="k", alpha=0.25, linewidth=1.0)
    ax.set_xlabel("z_relax_start (guard)")
    ax.set_ylabel("dm_fit_full (diagnostic closure knob)")
    ax.set_title("E2.8 guarded full-history: required D_M(z*) scaling (diagnostic)")
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False, ncol=2)
    fig3_path = figs_dir / "dm_fit_full_vs_z_relax_start.png"
    fig.savefig(fig3_path, dpi=160)
    plt.close(fig)

    # Summary text.
    # Find best chi2 among drift-ok points.
    best_ok = sorted([r for r in rows if bool(r.drift_sign_ok)], key=lambda r: float(r.chi2_full_base))
    summary_path = tables_dir / "summary.txt"
    lines = [
        "E2.8 guarded full-history closure scan (diagnostic-only)",
        "",
        f"late-time: p={float(p_late):g}, z_transition={float(z_transition):g}",
        f"guard grid: z_relax_start={list(z_relax_start_list)}  relax_scale={list(relax_scale_list)}",
        f"p_target={float(p_target):g}  z_bbn_clamp={(float(z_bbn_clamp) if z_bbn_clamp is not None else None)}",
        "",
        f"num_points_total={len(rows)}",
        f"num_points_drift_ok={len(best_ok)}",
    ]
    if best_ok:
        b = best_ok[0]
        lines += [
            "",
            "best drift-ok point (by chi2_full_base):",
            f"  z_relax_start={float(b.z_relax_start):g}  relax_scale={float(b.relax_scale):g}",
            f"  chi2_full_base={float(b.chi2_full_base):.6g}",
            f"  dv_full_z4_cm_s_10y={float(b.dv_full_z4):.6g}",
            f"  dm_fit_full={float(b.dm_fit_full):.6g}  rs_fit_full={float(b.rs_fit_full):.6g}  chi2_full_min={float(b.chi2_full_min):.6g}",
            f"  A_required_const={(float(b.A_required_const) if b.A_required_const is not None else None)}",
            f"  deltaG_required={(float(b.deltaG_required) if b.deltaG_required is not None else None)}",
        ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest: Dict[str, Any] = {
        "diagnostic_only": True,
        "kind": "cmb_e2_full_history_guarded_relax_scan",
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
            "name": "gsc_transition_full_history_guarded_relax",
            "p_late": float(p_late),
            "z_transition": float(z_transition),
            "z_relax_start_list": [float(x) for x in z_relax_start_list],
            "relax_scale_list": [float(x) for x in relax_scale_list],
            "p_target": float(p_target),
            "z_bbn_clamp": (float(z_bbn_clamp) if z_bbn_clamp is not None else None),
            "legacy_rs_star_reporting_calibration": float(_RS_STAR_CALIB_CHW2018),
        },
        "numerics": {
            "n_D_M": int(n_D_M),
            "n_r_s": int(n_r_s),
            "rs_grid": {"rs_min": float(rs_min), "rs_max": float(rs_max), "rs_step": float(rs_step)},
        },
        "outputs": {
            "outdir": _relpath(out_dir),
            "table": _relpath(csv_path),
            "feasible_subset": _relpath(feasible_path),
            "summary": _relpath(summary_path),
            "fig_chi2": _relpath(fig1_path),
            "fig_drift_sign": _relpath(fig2_path),
            "fig_dm_fit": _relpath(fig3_path),
        },
        "notes": [
            "Diagnostic-only: drift-protected full-history relaxation scan (no-stitch).",
            "Uses strict CHW2018 distance priors (R, lA, omega_b_h2) with published covariance.",
            "The full-history relax is guarded to start only above z_relax_start, to protect the z~2–5 drift window.",
        ],
        "summary": {
            "num_points_total": int(len(rows)),
            "num_points_drift_ok": int(len(best_ok)),
            "best_drift_ok": (
                {
                    "z_relax_start": float(best_ok[0].z_relax_start),
                    "relax_scale": float(best_ok[0].relax_scale),
                    "chi2_full_base": float(best_ok[0].chi2_full_base),
                    "dv_full_z4_cm_s_10y": float(best_ok[0].dv_full_z4),
                }
                if best_ok
                else None
            ),
        },
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
    ap.add_argument("--outdir", type=Path, default=Path("v11.0.0/results/diagnostic_cmb_full_history_guarded_relax"))

    ap.add_argument("--gsc-p", dest="p_late", type=float, default=0.6)
    ap.add_argument("--gsc-ztrans", dest="z_transition", type=float, default=1.8)
    ap.add_argument("--p-target", dest="p_target", type=float, default=1.5)

    ap.add_argument("--z-relax-start-list", type=str, default="5,6,7,8,10")
    ap.add_argument("--relax-scale-list", type=str, default="0.5,1,2,5,10")
    ap.add_argument("--z-bbn-clamp", type=float, default=1.0e7, help="If >0, clamp to LCDM+rad at z>=z_bbn_clamp. Use 0 to disable.")
    ap.add_argument("--n-dm", type=int, default=8192)
    ap.add_argument("--n-rs", type=int, default=8192)

    ap.add_argument("--H0", type=float, default=67.4)
    ap.add_argument("--Omega-m", dest="Omega_m", type=float, default=0.315)
    ap.add_argument("--omega-b-h2", type=float, default=0.02237)
    ap.add_argument("--omega-c-h2", type=float, default=0.1200)
    ap.add_argument("--Neff", type=float, default=3.046)
    ap.add_argument("--Tcmb-K", type=float, default=2.7255)

    ap.add_argument("--rs-min", type=float, default=0.90)
    ap.add_argument("--rs-max", type=float, default=1.20)
    ap.add_argument("--rs-step", type=float, default=1e-3)

    args = ap.parse_args(argv)

    z_bbn_clamp = float(args.z_bbn_clamp)
    if not math.isfinite(z_bbn_clamp) or z_bbn_clamp <= 0:
        z_bbn_clamp_opt = None
    else:
        z_bbn_clamp_opt = float(z_bbn_clamp)

    run(
        cmb_csv=Path(args.cmb),
        cmb_cov=Path(args.cmb_cov),
        out_dir=Path(args.outdir),
        p_late=float(args.p_late),
        z_transition=float(args.z_transition),
        z_relax_start_list=_parse_float_list(str(args.z_relax_start_list)),
        relax_scale_list=_parse_float_list(str(args.relax_scale_list)),
        p_target=float(args.p_target),
        z_bbn_clamp=z_bbn_clamp_opt,
        n_D_M=int(args.n_dm),
        n_r_s=int(args.n_rs),
        H0_km_s_Mpc=float(args.H0),
        Omega_m=float(args.Omega_m),
        omega_b_h2=float(args.omega_b_h2),
        omega_c_h2=float(args.omega_c_h2),
        Neff=float(args.Neff),
        Tcmb_K=float(args.Tcmb_K),
        rs_min=float(args.rs_min),
        rs_max=float(args.rs_max),
        rs_step=float(args.rs_step),
    )


if __name__ == "__main__":  # pragma: no cover
    main()


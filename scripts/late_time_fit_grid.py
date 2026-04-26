#!/usr/bin/env python3
"""Late-time grid-fit runner (v11.0.0).

This script performs a deterministic grid search over model parameters and
profiles nuisance parameters analytically:
- SN: delta_M (analytic, diag or full covariance)
- BAO:
  - `rd_mode=nuisance`: profile r_d via p = 1/r_d (analytic)
  - `rd_mode=early`: keep r_d fixed from early-time closure (`compute_rd_Mpc`)

Outputs:
- best-fit JSON
- top-K CSV

Notes:
- With Pantheon+ full covariance, a full scan over many points is expensive.
  Use `--two-pass` to prefilter with diagonal SN weights and only evaluate the
  full covariance for the top candidates.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import replace
import json
import math
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

from _outdir import resolve_outdir

# Allow running from repo root: add v11.0.0/ to import path.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.datasets.bao import BAOBlock1D, BAOBlock2D, BAOBlockND, BAODataset  # noqa: E402
from gsc.datasets.drift import DriftDataset  # noqa: E402
from gsc.datasets.cmb_priors import CMBPriorsDataset  # noqa: E402
from gsc.datasets.cmb_priors_driver import CMBPriorsLikelihood  # noqa: E402
from gsc.early_time import compute_rd_Mpc, early_time_params_from_namespace, z_star_hu_sugiyama  # noqa: E402
from gsc.early_time.cmb_distance_priors import _RS_STAR_CALIB_CHW2018  # noqa: E402
from gsc.early_time.cmb_priors_driver import CMBPriorsDriverConfig  # noqa: E402
from gsc.datasets.sn import SNDataset  # noqa: E402
from gsc.fit import FitPoint, iter_param_grid, parse_grid_spec, profile_H0_from_drift  # noqa: E402
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

_CHW2018_PREFIX = "planck2018_distance_priors_chw2018_"


def _is_chw2018_distance_priors_csv(path: Path) -> bool:
    name = path.name.lower()
    return name.startswith(_CHW2018_PREFIX) and name.endswith(".csv")


def _require_numpy():
    try:
        import numpy as np  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise SystemExit("numpy is required for late_time_fit_grid.py") from e
    return np


def _require_scipy():
    try:
        from scipy.linalg import solve_triangular  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise SystemExit("scipy is required for fast full-covariance SN fitting") from e
    return solve_triangular


def _build_dm_interpolator(model, *, z_max: float, n_grid: int):
    """Return a function dm(zs) -> D_M(z) in meters using a cumulative trapezoid grid."""
    if z_max <= 0:
        raise ValueError("z_max must be positive")
    if n_grid <= 10:
        raise ValueError("n_grid too small")

    np = _require_numpy()
    z_grid = np.linspace(0.0, float(z_max), int(n_grid) + 1, dtype=float)
    inv_H = np.empty_like(z_grid)
    for i, z in enumerate(z_grid):
        Hz = float(model.H(float(z)))
        if Hz <= 0:
            raise ValueError("H(z) must be positive")
        inv_H[i] = 1.0 / Hz
    dz = float(z_grid[1] - z_grid[0])
    # cumulative trapezoid
    cum = np.empty_like(z_grid)
    cum[0] = 0.0
    cum[1:] = np.cumsum(0.5 * (inv_H[:-1] + inv_H[1:]) * dz)
    chi_grid = float(C_SI) * cum

    def dm(zs):
        return np.interp(zs, z_grid, chi_grid)

    return dm


class PreparedSN:
    def __init__(self, ds: SNDataset, *, mode: str):
        self.name = ds.name
        self.mode = mode

        np = _require_numpy()
        self.z = np.asarray(ds.z, dtype=float)
        self.mu_obs = np.asarray(ds.mu, dtype=float)

        if mode == "cov":
            if ds.cov is None:
                raise ValueError("PreparedSN(cov) requires ds.cov")
            cov = ds.cov
            if not hasattr(cov, "shape"):
                cov = np.asarray(cov, dtype=float)
            self.cov = cov
            # Cholesky factorization once.
            self.L = np.linalg.cholesky(cov)
            solve_triangular = _require_scipy()
            ones = np.ones(len(self.z), dtype=float)
            # Precompute v = L^{-1} 1 and b = v^T v for delta_M profiling.
            v = solve_triangular(self.L, ones, lower=True, check_finite=False)
            self.v = v
            with np.errstate(all="ignore"):
                self.b = float(v @ v)
            if not (math.isfinite(self.b) and self.b > 0):
                raise ValueError("Invalid SN covariance precompute (b)")
        elif mode == "diag":
            self.sigma = _require_numpy().asarray(ds.sigma_mu, dtype=float)
            if (self.sigma <= 0).any():
                raise ValueError("SN sigma_mu must be positive")
            self.w = 1.0 / (self.sigma * self.sigma)
            self.w_sum = float(self.w.sum())
            if not (math.isfinite(self.w_sum) and self.w_sum > 0):
                raise ValueError("Invalid SN weights")
        else:
            raise ValueError("Unknown PreparedSN mode")

    def chi2_from_mu_theory(self, mu_th) -> Tuple[float, float, int]:
        """Return (chi2, delta_M, ndof)."""
        np = _require_numpy()
        r0 = self.mu_obs - np.asarray(mu_th, dtype=float)
        n = int(r0.shape[0])
        if self.mode == "diag":
            with np.errstate(all="ignore"):
                delta_M = float((self.w @ r0) / self.w_sum)
            rr = r0 - delta_M
            chi2 = float((self.w * rr * rr).sum())
            return (chi2, delta_M, n - 1)

        # cov mode: use whitened space to avoid C^{-1} explicitly.
        solve_triangular = _require_scipy()
        u = solve_triangular(self.L, r0, lower=True, check_finite=False)  # u = L^{-1} r0
        with np.errstate(all="ignore"):
            chi2_0 = float(u @ u)
            a = float(self.v @ u)  # a = 1^T C^{-1} r0 = (L^{-1}1)^T (L^{-1}r0)
        delta_M = a / self.b
        chi2 = chi2_0 - (a * a) / self.b
        return (float(chi2), float(delta_M), n - 1)


class PreparedBAO:
    def __init__(self, ds: BAODataset):
        self.name = ds.name
        self.blocks = ds.blocks

        # Precompute Cholesky for ND blocks (tiny; but keeps per-iteration clean).
        np = _require_numpy()
        solve_triangular = _require_scipy()
        self._nd: Dict[int, Any] = {}
        for b in self.blocks:
            if isinstance(b, BAOBlockND):
                cov = b.cov
                if not hasattr(cov, "shape"):
                    cov = np.asarray(cov, dtype=float)
                L = np.linalg.cholesky(cov)
                self._nd[id(b)] = (np.asarray(b.y, dtype=float), np.asarray(b.kinds, dtype=str), np.asarray(b.zs, dtype=float), L)

        self._solve_triangular = solve_triangular

    def chi2(self, *, dm_fn, H_of_z, rd_m: Optional[float] = None) -> Tuple[float, float, int]:
        """Return (chi2, rd_m, ndof), profiling r_d unless fixed `rd_m` is given."""
        np = _require_numpy()

        A = 0.0
        B = 0.0
        C = 0.0
        n_obs = 0

        for b in self.blocks:
            if isinstance(b, BAOBlock1D):
                z = float(b.z)
                dm = float(dm_fn(np.array([z], dtype=float))[0])
                Hz = float(H_of_z(z))
                if Hz <= 0:
                    raise ValueError("H(z) must be positive")
                dh = float(C_SI) / Hz
                dv = (z * dh * dm * dm) ** (1.0 / 3.0)
                w = 1.0 / (float(b.sigma) ** 2)
                A += (dv * dv) * w
                B += (dv * float(b.y)) * w
                C += (float(b.y) * float(b.y)) * w
                n_obs += 1
            elif isinstance(b, BAOBlock2D):
                z = float(b.z)
                dm = float(dm_fn(np.array([z], dtype=float))[0])
                Hz = float(H_of_z(z))
                if Hz <= 0:
                    raise ValueError("H(z) must be positive")
                dh = float(C_SI) / Hz

                a = float(b.sigma_dm) ** 2
                c = float(b.sigma_dh) ** 2
                bb = float(b.rho_dm_dh) * float(b.sigma_dm) * float(b.sigma_dh)
                det = a * c - bb * bb
                if det <= 0:
                    raise ValueError("Invalid 2x2 BAO covariance (det<=0)")
                inv00 = c / det
                inv01 = -bb / det
                inv11 = a / det

                y_dm = float(b.y_dm)
                y_dh = float(b.y_dh)

                A += dm * (inv00 * dm + inv01 * dh) + dh * (inv01 * dm + inv11 * dh)
                B += dm * (inv00 * y_dm + inv01 * y_dh) + dh * (inv01 * y_dm + inv11 * y_dh)
                C += y_dm * (inv00 * y_dm + inv01 * y_dh) + y_dh * (inv01 * y_dm + inv11 * y_dh)
                n_obs += 2
            else:
                # ND vector block
                y, kinds, zs, L = self._nd[id(b)]
                d_list = []
                for k, z in zip(kinds, zs):
                    kk = str(k).strip().upper()
                    zz = float(z)
                    if kk == "DM":
                        d_list.append(float(dm_fn(np.array([zz], dtype=float))[0]))
                    elif kk == "DH":
                        Hz = float(H_of_z(zz))
                        if Hz <= 0:
                            raise ValueError("H(z) must be positive")
                        d_list.append(float(C_SI) / Hz)
                    elif kk == "DV":
                        dm = float(dm_fn(np.array([zz], dtype=float))[0])
                        Hz = float(H_of_z(zz))
                        if Hz <= 0:
                            raise ValueError("H(z) must be positive")
                        dh = float(C_SI) / Hz
                        d_list.append((zz * dh * dm * dm) ** (1.0 / 3.0))
                    else:
                        raise ValueError(f"Unknown BAO kind in vector block: {k!r}")

                d = np.asarray(d_list, dtype=float)
                # Whiten with L: u = L^{-1} x
                u_d = self._solve_triangular(L, d, lower=True, check_finite=False)
                u_y = self._solve_triangular(L, y, lower=True, check_finite=False)
                A += float(u_d @ u_d)
                B += float(u_d @ u_y)
                C += float(u_y @ u_y)
                n_obs += int(len(y))

        if not (A > 0 and math.isfinite(A) and math.isfinite(B) and math.isfinite(C)):
            raise ValueError("Invalid BAO quadratic form (A,B,C)")

        if rd_m is None:
            p_star = B / A
            if p_star <= 0:
                raise ValueError("Profiled BAO p_star <= 0 (non-physical r_d)")
            chi2 = C - (B * B) / A
            rd_m_use = 1.0 / p_star
            ndof = n_obs - 1
        else:
            if not (rd_m > 0 and math.isfinite(rd_m)):
                raise ValueError("Fixed rd_m must be positive and finite")
            p_use = 1.0 / float(rd_m)
            chi2 = A * p_use * p_use - 2.0 * B * p_use + C
            rd_m_use = float(rd_m)
            ndof = n_obs

        return (float(chi2), float(rd_m_use), int(ndof))


def _model_from_params(model_name: str, params: Dict[str, float]):
    H0_si = H0_to_SI(params["H0"])
    if model_name == "lcdm":
        Om = float(params["Omega_m"])
        Ol = 1.0 - Om
        return FlatLambdaCDMHistory(H0=H0_si, Omega_m=Om, Omega_Lambda=Ol)
    if model_name == "gsc_powerlaw":
        p = float(params["p"])
        return PowerLawHistory(H0=H0_si, p=p)
    if model_name == "gsc_transition":
        Om = float(params["Omega_m"])
        Ol = 1.0 - Om
        p = float(params["p"])
        zt = float(params["z_transition"])
        return GSCTransitionHistory(H0=H0_si, Omega_m=Om, Omega_Lambda=Ol, p=p, z_transition=zt)
    raise ValueError(f"Unknown model {model_name!r}")


def _guardrail_gsc(model, *, z_max: float = 5.0) -> None:
    """Enforce the model-history positive-drift hypothesis on a grid up to z_max.

    This guardrail constrains the specific late-time H(z) family used in this
    run. It is a history condition, not a conformal-frame property.
    """
    H0 = float(model.H(0.0))
    for i in range(1, 101):
        z = float(z_max) * i / 100.0
        zdot = z_dot_sandage_loeb(z=z, H0=H0, H_of_z=model.H)
        if zdot <= 0:
            raise ValueError(f"Guardrail failed: expected positive drift at z={z:.3f}")


def _write_top_csv(path: Path, rows: Sequence[FitPoint], *, model: str) -> None:
    # Flatten to a simple table.
    keys = sorted({k for r in rows for k in r.params.keys()})
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["model", "chi2", "ndof"] + keys)
        for r in rows:
            w.writerow([model, f"{r.chi2:.12g}", r.ndof] + [f"{r.params.get(k, float('nan')):.12g}" for k in keys])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=["lcdm", "gsc_powerlaw", "gsc_transition"], required=True)

    # datasets
    ap.add_argument("--sn", type=Path, help="SN CSV (columns: z, mu, sigma_mu)")
    ap.add_argument("--sn-cov", type=Path, help="SN covariance (.cov or .npz); enables full-cov mode")
    ap.add_argument("--bao", type=Path, help="BAO CSV (block format)")
    ap.add_argument("--cmb", type=Path, help="Compressed CMB priors CSV (columns: name,value,sigma)")
    ap.add_argument("--cmb-cov", type=Path, help="Compressed CMB covariance file (.cov/.npz)")
    ap.add_argument(
        "--cmb-mode",
        choices=["theta_star", "distance_priors"],
        default="theta_star",
        help="Compressed CMB interpretation mode.",
    )
    ap.add_argument(
        "--cmb-bridge-z",
        type=float,
        default=None,
        help="For non-LCDM models, enable an E1 bridge by specifying z_bridge (e.g. 5 or 10).",
    )
    ap.add_argument("--drift", type=Path, help="Drift CSV (columns: z, dv_cm_s, sigma_dv_cm_s)")
    ap.add_argument("--drift-baseline-years", type=float, default=None)
    ap.add_argument(
        "--rd-mode",
        choices=["nuisance", "early"],
        default="nuisance",
        help="BAO sound-horizon treatment: profile nuisance r_d or use early-time derived r_d.",
    )
    ap.add_argument(
        "--rd-method",
        type=str,
        default="eisenstein_hu_1998",
        help="Method for early-time r_d when --rd-mode=early.",
    )
    ap.add_argument("--omega-b-h2", type=float, default=None, help="Physical baryon density for --rd-mode=early")
    ap.add_argument("--omega-c-h2", type=float, default=None, help="Physical CDM density for --rd-mode=early")
    ap.add_argument("--Neff", type=float, default=3.046, help="Effective neutrino number for --rd-mode=early")
    ap.add_argument("--Tcmb-K", type=float, default=2.7255, help="CMB temperature today in K for --rd-mode=early")

    # grids (strings)
    ap.add_argument("--H0-grid", default="67.4", help="H0 grid in km/s/Mpc (comma list or start:stop:step)")
    ap.add_argument("--Omega-m-grid", default="0.315", help="Omega_m grid (flatness enforced: Omega_L=1-Omega_m)")
    ap.add_argument("--p-grid", default="0.6", help="GSC power-law exponent grid (0<p<1)")
    ap.add_argument("--ztrans-grid", default="1.8", help="GSC transition redshift grid")

    # performance / outputs
    ap.add_argument(
        "--out-dir",
        "--outdir",
        dest="out_dir",
        type=Path,
        default=None,
        help="Output directory (CLI > GSC_OUTDIR/late_time_fit > default artifacts/release/late_time_fit).",
    )
    ap.add_argument("--tag", type=str, default=None, help="Optional filename tag (defaults to model)")
    ap.add_argument("--n-grid", type=int, default=6000, help="Integration grid steps for D_M interpolation")
    ap.add_argument("--two-pass", action="store_true", help="Use diag SN prefilter, then full-cov for top points.")
    ap.add_argument("--two-pass-top", type=int, default=60, help="Number of candidates to rescore with full SN cov.")
    ap.add_argument("--top-k", type=int, default=50, help="Save top-K results from the first pass.")
    ap.add_argument(
        "--profile-H0",
        action="store_true",
        help="If drift data is provided, profile H0 analytically (no H0 grid scan).",
    )

    args = ap.parse_args()

    if args.cmb is not None:
        # Strict E1.1 mode guardrail: CHW2018 distance priors are only valid
        # with the published covariance (vector likelihood).
        if _is_chw2018_distance_priors_csv(args.cmb) and args.cmb_cov is None:
            raise SystemExit("CHW2018 Planck distance priors require --cmb-cov (strict E1.1 mode).")
        # Footgun guardrail: CHW2018 files are distance-priors vectors (R, lA, omega_b_h2),
        # not theta_star priors. Our CHW2018-specific r_s(z*) stopgap calibration is only
        # applied in the distance_priors path.
        if _is_chw2018_distance_priors_csv(args.cmb) and args.cmb_mode != "distance_priors":
            raise SystemExit(
                "CHW2018 distance priors require --cmb-mode distance_priors "
                "(strict path; rs_star_calibration is only applied there)."
            )

    needs_early_time = bool(args.rd_mode == "early" or args.cmb is not None)
    early_time_context = "--rd-mode early and --cmb" if args.rd_mode == "early" and args.cmb is not None else (
        "--rd-mode early" if args.rd_mode == "early" else "--cmb"
    )
    try:
        early_time_params = early_time_params_from_namespace(
            args,
            require=needs_early_time,
            context=early_time_context,
        )
    except ValueError as e:
        raise SystemExit(str(e))

    if args.cmb is not None and args.model != "lcdm":
        print(
            "[WARN] --cmb with non-LCDM models is an E1 bridge / diagnostic-only check (not evidence/fit).",
            file=sys.stderr,
        )
        if _is_chw2018_distance_priors_csv(args.cmb):
            print(
                "[WARN] CHW2018 distance priors are derived assuming LCDM; treat pulls/chi2 as diagnostic tension only.",
                file=sys.stderr,
            )

    rs_star_calib = (
        float(_RS_STAR_CALIB_CHW2018)
        if (args.cmb is not None and _is_chw2018_distance_priors_csv(args.cmb) and args.cmb_mode == "distance_priors")
        else 1.0
    )

    np = _require_numpy()
    H0_grid_vals = [float(x) for x in parse_grid_spec(args.H0_grid)]
    H0_ref_km_s_Mpc = float(H0_grid_vals[0])
    H0_min_km_s_Mpc = float(min(H0_grid_vals))
    H0_max_km_s_Mpc = float(max(H0_grid_vals))
    H0_min_si = H0_to_SI(H0_min_km_s_Mpc)
    H0_max_si = H0_to_SI(H0_max_km_s_Mpc)

    # Load datasets.
    sn_diag: Optional[PreparedSN] = None
    sn_cov: Optional[PreparedSN] = None
    sn_ds: Optional[SNDataset] = None
    if args.sn is not None:
        if args.sn_cov is not None:
            sn_ds = SNDataset.from_csv_and_cov(args.sn, args.sn_cov, name="sn")
            sn_diag = PreparedSN(sn_ds, mode="diag")
            sn_cov = PreparedSN(sn_ds, mode="cov")
        else:
            sn_ds = SNDataset.from_csv(args.sn, name="sn")
            sn_diag = PreparedSN(sn_ds, mode="diag")

    bao_ds: Optional[PreparedBAO] = None
    bao_src: Optional[BAODataset] = None
    if args.bao is not None:
        bao_src = BAODataset.from_csv(args.bao, name="bao")
        bao_ds = PreparedBAO(bao_src)

    rd_early_m: Optional[float] = None
    rd_config: Dict[str, Any] = {"rd_mode": str(args.rd_mode)}
    if args.rd_mode == "early":
        if bao_ds is None:
            raise SystemExit("--rd-mode early requires --bao")
        if early_time_params is None:  # pragma: no cover - guarded by parse helper
            raise SystemExit("--rd-mode early requires --omega-b-h2 and --omega-c-h2")
        try:
            rd_mpc = compute_rd_Mpc(**early_time_params.to_rd_kwargs())
        except Exception as e:
            raise SystemExit(f"Failed to compute early-time r_d: {e}")
        rd_early_m = float(rd_mpc) * float(MPC_SI)
        rd_config.update(early_time_params.to_metadata(include_rd_method=True))
        rd_config.update(
            {
                "rd_Mpc": float(rd_mpc),
                "rd_m": float(rd_early_m),
            }
        )

    drift_ds: Optional[DriftDataset] = None
    if args.drift is not None:
        drift_ds = DriftDataset.from_csv(args.drift, baseline_years=args.drift_baseline_years, name="drift")

    cmb_ds: Optional[CMBPriorsDataset] = None
    cmb_like: Optional[CMBPriorsLikelihood] = None
    if args.cmb is not None:
        cmb_ds = CMBPriorsDataset.from_csv(args.cmb, cov_path=args.cmb_cov, name="cmb")
        if args.model != "lcdm" and args.cmb_bridge_z is None:
            raise SystemExit("--cmb for non-LCDM models requires --cmb-bridge-z (E1 bridge).")
        if early_time_params is None:  # pragma: no cover - guarded by parse helper
            raise SystemExit("--cmb requires --omega-b-h2 and --omega-c-h2")
        cmb_mode = "distance_priors" if str(args.cmb_mode) == "distance_priors" else "shift_params"
        cmb_like = CMBPriorsLikelihood(
            priors=cmb_ds,
            driver_config=CMBPriorsDriverConfig(
                **early_time_params.to_cmb_driver_kwargs(),
                mode=str(cmb_mode),
                z_bridge=None if args.model == "lcdm" else float(args.cmb_bridge_z),
                rs_star_calibration=float(rs_star_calib),
            ),
        )

    if sn_diag is None and bao_ds is None and drift_ds is None and cmb_ds is None:
        raise SystemExit("No datasets provided. Use --sn and/or --bao and/or --drift and/or --cmb.")

    # Determine z_max needed for distance interpolation.
    z_need: List[float] = []
    if sn_diag is not None:
        z_need.extend([float(z) for z in sn_diag.z])
    if bao_src is not None:
        for b in bao_src.blocks:
            if isinstance(b, (BAOBlock1D, BAOBlock2D)):
                z_need.append(float(b.z))
            else:
                z_need.extend([float(z) for z in b.zs])
    z_max = max(z_need) if z_need else 1.0
    z_max = max(z_max, 0.5)
    if cmb_ds is not None and args.model != "lcdm" and args.cmb_bridge_z is not None:
        z_max = max(float(z_max), float(args.cmb_bridge_z))

    # Build parameter grid.
    grid: Dict[str, Sequence[float]] = {}
    if args.profile_H0:
        if drift_ds is None:
            raise SystemExit("--profile-H0 requires --drift")
    else:
        grid["H0"] = H0_grid_vals
    if args.model in ("lcdm", "gsc_transition"):
        grid["Omega_m"] = parse_grid_spec(args.Omega_m_grid)
    if args.model in ("gsc_powerlaw", "gsc_transition"):
        grid["p"] = parse_grid_spec(args.p_grid)
    if args.model == "gsc_transition":
        grid["z_transition"] = parse_grid_spec(args.ztrans_grid)

    tag = args.tag or args.model
    if args.out_dir is not None:
        out_dir = Path(args.out_dir).expanduser().resolve()
    else:
        out_root = resolve_outdir(None, v101_dir=ROOT)
        out_dir = (out_root / "late_time_fit").resolve()
    print(f"[info] OUTDIR={out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)

    def eval_point(params: Dict[str, float], *, sn_mode: str) -> FitPoint:
        # Validate ranges.
        if args.model in ("gsc_powerlaw", "gsc_transition"):
            pval = float(params["p"])
            if not (0.0 < pval < 1.0):
                return FitPoint(params=params, chi2=1e99, ndof=0, parts={"error": "p outside (0,1)"})
        if "Omega_m" in params:
            Om = float(params["Omega_m"])
            if not (0.0 <= Om <= 1.0):
                return FitPoint(params=params, chi2=1e99, ndof=0, parts={"error": "Omega_m outside [0,1]"})
        if "z_transition" in params:
            if float(params["z_transition"]) < 0:
                return FitPoint(params=params, chi2=1e99, ndof=0, parts={"error": "z_transition < 0"})

        # Build a shape model at a reference H0 to validate and (optionally)
        # profile H0 from drift. Any positive H0 works if H(z) is linear in H0.
        params_use = dict(params)
        params_ref = dict(params)
        params_ref["H0"] = H0_ref_km_s_Mpc

        try:
            model_ref = _model_from_params(args.model, params_ref)
            if args.model.startswith("gsc_"):
                _guardrail_gsc(model_ref, z_max=5.0)
        except Exception as e:
            return FitPoint(params=params, chi2=1e99, ndof=0, parts={"error": str(e)})

        drift_profiled: Optional[Dict[str, float]] = None
        if args.profile_H0 and drift_ds is not None:
            try:
                drift_profiled = profile_H0_from_drift(
                    drift=drift_ds,
                    model_ref=model_ref,
                    H0_bounds_km_s_Mpc=(float(H0_min_km_s_Mpc), float(H0_max_km_s_Mpc)),
                )
            except Exception as e:
                return FitPoint(params=params, chi2=1e99, ndof=0, parts={"error": f"drift profile failed: {e}"})

            params_use["H0"] = float(drift_profiled["H0_km_s_Mpc"])
        else:
            # H0 is scanned.
            if "H0" not in params_use:
                params_use["H0"] = params_ref["H0"]

        try:
            model = _model_from_params(args.model, params_use)
        except Exception as e:
            return FitPoint(params=params_use, chi2=1e99, ndof=0, parts={"error": str(e)})

        # Distance interpolation (flat).
        dm_fn = _build_dm_interpolator(model, z_max=z_max, n_grid=args.n_grid)

        chi2_total = 0.0
        ndof_total = 0
        parts: Dict[str, Any] = {}

        # SN
        if sn_diag is not None:
            dm_sn = dm_fn(sn_diag.z)
            dl = (1.0 + sn_diag.z) * dm_sn
            mu_th = 5.0 * np.log10(dl / (10.0 * float(PC_SI)))
            sn_use = sn_cov if (sn_mode == "cov" and sn_cov is not None) else sn_diag
            chi2_sn, delta_M, ndof_sn = sn_use.chi2_from_mu_theory(mu_th)
            parts["sn"] = {"chi2": chi2_sn, "ndof": ndof_sn, "delta_M": delta_M, "mode": sn_use.mode}
            chi2_total += chi2_sn
            ndof_total += ndof_sn

        # BAO
        if bao_ds is not None:
            if args.rd_mode == "early":
                chi2_bao, rd_m, ndof_bao = bao_ds.chi2(dm_fn=dm_fn, H_of_z=model.H, rd_m=rd_early_m)
                rd_fit_mode = "fixed"
            else:
                chi2_bao, rd_m, ndof_bao = bao_ds.chi2(dm_fn=dm_fn, H_of_z=model.H, rd_m=None)
                rd_fit_mode = "profile"
            parts["bao"] = {
                "chi2": chi2_bao,
                "ndof": ndof_bao,
                "rd_m": rd_m,
                "rd_Mpc": rd_m / float(MPC_SI),
                "rd_mode": str(args.rd_mode),
                "rd_fit_mode": rd_fit_mode,
            }
            if args.rd_mode == "early":
                parts["bao"]["rd_method"] = str(args.rd_method)
            chi2_total += chi2_bao
            ndof_total += ndof_bao

        # compressed CMB priors via Phase 2 unified driver path
        if cmb_like is not None:
            try:
                cmb_like_use = cmb_like
                z_bridge = cmb_like.driver_config.z_bridge
                if z_bridge is not None:
                    z_star_use = z_star_hu_sugiyama(
                        omega_b_h2=float(cmb_like.driver_config.omega_b_h2),
                        omega_m_h2=float(cmb_like.driver_config.omega_b_h2)
                        + float(cmb_like.driver_config.omega_c_h2),
                    )
                    z_b = float(min(float(z_bridge), float(z_star_use)))
                    d_low_m = float(dm_fn(np.array([z_b], dtype=float))[0])
                    cfg_use = replace(cmb_like.driver_config, D_M_model_to_z_bridge_m=float(d_low_m))
                    cmb_like_use = CMBPriorsLikelihood(
                        priors=cmb_like.priors,
                        driver_config=cfg_use,
                        name=cmb_like.name,
                        key_aliases=cmb_like.key_aliases,
                    )
                cmb_eval = cmb_like_use.evaluate(model)
                r_cmb = cmb_like_use.chi2_from_evaluation(cmb_eval)
            except Exception as e:
                return FitPoint(
                    params=params_use,
                    chi2=1e99,
                    ndof=0,
                    parts={"error": f"cmb prior evaluation failed: {e}"},
                )
            keys_used = [str(k) for k in cmb_eval.predicted_for_keys.keys()]
            cmb_part: Dict[str, Any] = {
                "chi2": float(r_cmb.chi2),
                "ndof": int(r_cmb.ndof),
                "mode": str(args.cmb_mode),
                "method": str(r_cmb.meta.get("method", "diag")),
                "keys": list(keys_used),
                "keys_used": list(keys_used),
                "predicted": {str(k): float(v) for k, v in cmb_eval.predicted_for_keys.items()},
            }
            bridge_z = cmb_eval.predicted_all.get("bridge_z")
            if bridge_z is not None:
                cmb_part["bridge_z"] = float(bridge_z)
            bridge_H_ratio = cmb_eval.predicted_all.get("bridge_H_ratio")
            if bridge_H_ratio is not None:
                cmb_part["bridge_H_ratio"] = float(bridge_H_ratio)
            parts["cmb"] = cmb_part
            chi2_total += float(r_cmb.chi2)
            ndof_total += int(r_cmb.ndof)

        # drift
        if drift_ds is not None:
            if drift_profiled is not None:
                chi2_drift = float(drift_profiled["chi2"])
                ndof_drift = int(drift_profiled.get("ndof", max(0, len(drift_ds.z) - 1)))
                parts["drift"] = {
                    "chi2": float(chi2_drift),
                    "ndof": int(ndof_drift),
                    "profile_H0": True,
                    "H0_km_s_Mpc": float(drift_profiled.get("H0_km_s_Mpc", float("nan"))),
                    "clamped": bool(drift_profiled.get("clamped", False)),
                    "H0_bounds_km_s_Mpc": list(drift_profiled.get("H0_bounds_km_s_Mpc", [H0_min_km_s_Mpc, H0_max_km_s_Mpc])),
                }
                chi2_total += float(chi2_drift)
                ndof_total += int(ndof_drift)
            else:
                H0 = float(model.H(0.0))
                chi2_drift = 0.0
                for i, (z, dv_obs, sig) in enumerate(zip(drift_ds.z, drift_ds.dv_cm_s, drift_ds.sigma_dv_cm_s)):
                    years = (
                        drift_ds.baseline_years_by_row[i]
                        if drift_ds.baseline_years_by_row is not None
                        else drift_ds.baseline_years
                    )
                    zdot = z_dot_sandage_loeb(z=float(z), H0=H0, H_of_z=model.H)
                    dv_pred = 100.0 * (float(C_SI) * zdot / (1.0 + float(z))) * (years * float(SEC_PER_YR))
                    r = (float(dv_obs) - dv_pred) / float(sig)
                    chi2_drift += r * r
                ndof_drift = len(drift_ds.z)
                parts["drift"] = {"chi2": float(chi2_drift), "ndof": int(ndof_drift), "profile_H0": False}
                chi2_total += float(chi2_drift)
                ndof_total += int(ndof_drift)

        return FitPoint(params=dict(params_use), chi2=float(chi2_total), ndof=int(ndof_total), parts=parts)

    # Pass 1: either full or diag.
    use_two_pass = bool(args.two_pass and sn_cov is not None and sn_diag is not None)
    pass1_mode = "diag" if use_two_pass else ("cov" if sn_cov is not None else "diag")

    top_k = int(args.top_k)
    top: List[FitPoint] = []
    best: Optional[FitPoint] = None
    for params in iter_param_grid(grid):
        fp = eval_point(params, sn_mode=pass1_mode)
        if best is None or fp.chi2 < best.chi2:
            best = fp
        # maintain top-k
        inserted = False
        for i, existing in enumerate(top):
            if fp.chi2 < existing.chi2:
                top.insert(i, fp)
                inserted = True
                break
        if not inserted:
            top.append(fp)
        if len(top) > top_k:
            top = top[:top_k]

    if best is None:
        raise SystemExit("No fit points evaluated")

    final_best = best
    final_top = top

    # Pass 2: rescore only the best candidates with full SN covariance.
    if use_two_pass:
        cand = top[: int(args.two_pass_top)]
        best2: Optional[FitPoint] = None
        top2: List[FitPoint] = []
        for fp in cand:
            fp2 = eval_point(fp.params, sn_mode="cov")
            if best2 is None or fp2.chi2 < best2.chi2:
                best2 = fp2
            top2.append(fp2)
        top2.sort(key=lambda r: r.chi2)
        if best2 is not None:
            final_best = best2
            final_top = top2

    if "error" in final_best.parts:
        raise SystemExit(f"Fit failed: {final_best.parts.get('error')}")

    # Write outputs.
    best_path = out_dir / f"{tag}_bestfit.json"
    top_path = out_dir / f"{tag}_top.csv"

    early_time_payload = dict(rd_config)
    if early_time_params is not None:
        early_time_payload.update(early_time_params.to_metadata(include_rd_method=True))
    payload = {
        "model": args.model,
        "grid": {k: list(v) for k, v in grid.items()},
        "z_max": z_max,
        "n_grid": args.n_grid,
        "two_pass": use_two_pass,
        "profile_H0": bool(args.profile_H0),
        "rd": rd_config,
        "datasets": {
            "sn": str(args.sn) if args.sn is not None else None,
            "sn_cov": str(args.sn_cov) if args.sn_cov is not None else None,
            "bao": str(args.bao) if args.bao is not None else None,
            "cmb": str(args.cmb) if args.cmb is not None else None,
            "cmb_cov": str(args.cmb_cov) if args.cmb_cov is not None else None,
            "drift": str(args.drift) if args.drift is not None else None,
        },
        "cmb": {
            "mode": str(args.cmb_mode),
            "path": str(args.cmb) if args.cmb is not None else None,
            "cov_path": str(args.cmb_cov) if args.cmb_cov is not None else None,
            "bridge_z": float(args.cmb_bridge_z) if args.cmb_bridge_z is not None else None,
        },
        "early_time": early_time_payload,
        "best": {
            "params": final_best.params,
            "chi2": final_best.chi2,
            "ndof": final_best.ndof,
            "parts": final_best.parts,
        },
    }
    best_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_top_csv(top_path, final_top, model=args.model)

    print(f"WROTE {best_path}")
    print(f"WROTE {top_path}")
    print(f"best: chi2={final_best.chi2:.6g}  ndof={final_best.ndof}")
    if final_best.ndof > 0:
        print(f"best: chi2/ndof={final_best.chi2/final_best.ndof:.6g}")
    for k in sorted(final_best.parts.keys()):
        print(f"  {k}: {final_best.parts[k]}")


if __name__ == "__main__":
    main()

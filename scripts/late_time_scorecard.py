#!/usr/bin/env python3
"""Late-time scorecard runner (v11.0.0).

This is a lightweight harness to compute χ² for a chosen H(z) history against
provided CSV datasets, using the Option-2 measurement model translation.

Examples:
  python3 v11.0.0/scripts/late_time_scorecard.py --model powerlaw --p 0.5
  python3 v11.0.0/scripts/late_time_scorecard.py --model lcdm --sn data/sn_mu.csv
  python3 v11.0.0/scripts/late_time_scorecard.py --model lcdm --drift data/drift.csv --drift-baseline-years 1.0
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


# Allow running from repo root: add v11.0.0/ to import path.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.datasets.drift import DriftDataset  # noqa: E402
from gsc.datasets.sn import SNDataset  # noqa: E402
from gsc.datasets.bao import BAODataset, BAODatasetFixedRd  # noqa: E402
from gsc.datasets.base import Chi2Result  # noqa: E402
from gsc.datasets.cmb_priors import CMBPriorsDataset  # noqa: E402
from gsc.datasets.cmb_priors_driver import CMBPriorsLikelihood  # noqa: E402
from gsc.early_time import compute_rd_Mpc, early_time_params_from_namespace  # noqa: E402
from gsc.early_time.cmb_distance_priors import _RS_STAR_CALIB_CHW2018  # noqa: E402
from gsc.early_time.cmb_priors_driver import CMBPriorsDriverConfig  # noqa: E402
from gsc.likelihood import chi2_total  # noqa: E402
from gsc.measurement_model import (  # noqa: E402
    FlatLambdaCDMHistory,
    GSCTransitionHistory,
    H0_to_SI,
    MPC_SI,
    PowerLawHistory,
    z_dot_sandage_loeb,
)

_CHW2018_PREFIX = "planck2018_distance_priors_chw2018_"


def _is_chw2018_distance_priors_csv(path: Path) -> bool:
    name = path.name.lower()
    return name.startswith(_CHW2018_PREFIX) and name.endswith(".csv")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--model",
        choices=["powerlaw", "lcdm", "gsc_powerlaw", "gsc_transition"],
        default="powerlaw",
        help="History model used to generate H(z) and derived observables.",
    )
    p.add_argument("--H0", type=float, default=67.4, help="H0 in km/s/Mpc (late-time)")

    # powerlaw params
    p.add_argument("--p", type=float, default=0.5, help="Power-law exponent for H(z)=H0(1+z)^p")

    # gsc params (Option 2 late-time scorecard)
    p.add_argument("--gsc-p", dest="gsc_p", type=float, default=0.5, help="GSC power-law exponent (0<p<1)")
    p.add_argument("--gsc-ztrans", dest="gsc_ztrans", type=float, default=1.8, help="Transition redshift z_t (GSC)")

    # lcdm params
    p.add_argument("--Omega-m", dest="Omega_m", type=float, default=0.315)
    p.add_argument("--Omega-L", dest="Omega_L", type=float, default=0.685)

    # datasets
    p.add_argument("--sn", type=Path, help="SN CSV (columns: z, mu, sigma_mu)")
    p.add_argument("--sn-cov", type=Path, help="SN covariance (.cov or .npz); requires numpy")
    p.add_argument("--bao", type=Path, help="BAO CSV (block format; r_d profiled by default)")
    p.add_argument("--rd-mode", choices=["nuisance", "early"], default="nuisance", help="BAO sound-horizon mode.")
    p.add_argument("--rd-method", default="eisenstein_hu_1998", help="Method for early-time r_d when --rd-mode=early.")
    p.add_argument("--omega-b-h2", type=float, default=None, help="Physical baryon density for early-time bridge modes.")
    p.add_argument("--omega-c-h2", type=float, default=None, help="Physical CDM density for early-time bridge modes.")
    p.add_argument("--Neff", type=float, default=3.046, help="Effective neutrino number for early-time bridge modes.")
    p.add_argument("--Tcmb-K", type=float, default=2.7255, help="CMB temperature today in K for early-time bridge modes.")
    p.add_argument("--bao-rd-fixed", type=float, default=None, help="Fix r_d (meters) instead of profiling it.")
    p.add_argument("--cmb", type=Path, help="Compressed CMB priors CSV (columns: name,value,sigma)")
    p.add_argument("--cmb-cov", type=Path, help="Compressed CMB covariance file (.cov/.npz)")
    p.add_argument(
        "--cmb-mode",
        choices=["theta_star", "distance_priors"],
        default="theta_star",
        help="Compressed CMB interpretation mode.",
    )
    p.add_argument(
        "--cmb-bridge-z",
        type=float,
        default=None,
        help="For non-LCDM models, enable an E1 bridge by specifying z_bridge (e.g. 5 or 10).",
    )
    p.add_argument(
        "--cmb-debug",
        action="store_true",
        help="Print predicted vs prior values for the compressed CMB block.",
    )
    p.add_argument("--drift", type=Path, help="Drift CSV (columns: z, dv_cm_s, sigma_dv_cm_s)")
    p.add_argument(
        "--drift-baseline-years",
        type=float,
        default=None,
        help="Override baseline years for drift dataset (otherwise read baseline_years/baseline_yr from CSV).",
    )

    args = p.parse_args()

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

    H0_si = H0_to_SI(args.H0)
    if args.model == "lcdm":
        model = FlatLambdaCDMHistory(H0=H0_si, Omega_m=args.Omega_m, Omega_Lambda=args.Omega_L)
    elif args.model == "gsc_powerlaw":
        if not (0.0 < args.gsc_p < 1.0):
            raise SystemExit("--gsc-p must satisfy 0 < p < 1 to ensure positive drift at z>0")
        model = PowerLawHistory(H0=H0_si, p=args.gsc_p)
    elif args.model == "gsc_transition":
        if not (0.0 < args.gsc_p < 1.0):
            raise SystemExit("--gsc-p must satisfy 0 < p < 1 to ensure positive drift at high z")
        model = GSCTransitionHistory(
            H0=H0_si,
            Omega_m=args.Omega_m,
            Omega_Lambda=args.Omega_L,
            p=args.gsc_p,
            z_transition=args.gsc_ztrans,
        )
    else:
        model = PowerLawHistory(H0=H0_si, p=args.p)

    # Guardrail for the Option-2 "GSC" interpretation: drift should remain
    # positive out to the high-z range of interest (z ~ 2–5).
    if args.model in ("gsc_powerlaw", "gsc_transition"):
        for i in range(1, 101):
            z = 5.0 * i / 100.0
            zdot = z_dot_sandage_loeb(z=z, H0=H0_si, H_of_z=model.H)
            if zdot <= 0:
                raise SystemExit(
                    f"GSC guardrail failed: expected positive drift at z={z:.3f} "
                    f"but got z_dot={zdot:.3e} 1/s. Adjust --gsc-p/--gsc-ztrans."
                )

    datasets = []
    if args.sn is not None:
        if args.sn_cov is not None:
            datasets.append(SNDataset.from_csv_and_cov(args.sn, args.sn_cov, name="sn"))
        else:
            datasets.append(SNDataset.from_csv(args.sn, name="sn"))
    if args.bao is not None:
        bao = BAODataset.from_csv(args.bao, name="bao")
        if args.bao_rd_fixed is not None:
            datasets.append(BAODatasetFixedRd(base=bao, rd_m=args.bao_rd_fixed, name="bao"))
        elif args.rd_mode == "early":
            if early_time_params is None:  # pragma: no cover - guarded by parse helper
                raise SystemExit("--rd-mode early requires --omega-b-h2 and --omega-c-h2")
            rd_mpc = compute_rd_Mpc(**early_time_params.to_rd_kwargs())
            datasets.append(BAODatasetFixedRd(base=bao, rd_m=float(rd_mpc) * float(MPC_SI), name="bao"))
        else:
            datasets.append(bao)
    if args.drift is not None:
        datasets.append(DriftDataset.from_csv(args.drift, baseline_years=args.drift_baseline_years, name="drift"))

    if not datasets:
        if args.cmb is None:
            print("No datasets provided. Use --sn and/or --bao and/or --drift and/or --cmb.")
            return

    # Print per-dataset breakdown, then total.
    per = []
    for ds in datasets:
        r_ds = ds.chi2(model)
        per.append((ds.name, r_ds))

    r = chi2_total(model=model, datasets=datasets)

    if args.cmb is not None:
        if early_time_params is None:  # pragma: no cover - guarded by parse helper
            raise SystemExit("--cmb requires --omega-b-h2 and --omega-c-h2")
        if _is_chw2018_distance_priors_csv(args.cmb) and args.cmb_cov is None:
            raise SystemExit("CHW2018 Planck distance priors require --cmb-cov (strict E1.1 mode).")
        if _is_chw2018_distance_priors_csv(args.cmb) and args.cmb_mode != "distance_priors":
            raise SystemExit(
                "CHW2018 distance priors require --cmb-mode distance_priors "
                "(strict path; rs_star_calibration is only applied there)."
            )

        if args.model != "lcdm":
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
            if (_is_chw2018_distance_priors_csv(args.cmb) and args.cmb_mode == "distance_priors")
            else 1.0
        )
        if args.model != "lcdm" and args.cmb_bridge_z is None:
            raise SystemExit("--cmb for non-LCDM models requires --cmb-bridge-z (E1 bridge).")
        cmb_ds = CMBPriorsDataset.from_csv(args.cmb, cov_path=args.cmb_cov, name="cmb")
        cmb_mode = "distance_priors" if str(args.cmb_mode) == "distance_priors" else "shift_params"
        cmb_like = CMBPriorsLikelihood(
            priors=cmb_ds,
            driver_config=CMBPriorsDriverConfig(
                **early_time_params.to_cmb_driver_kwargs(),
                mode=str(cmb_mode),
                z_bridge=None if args.model == "lcdm" else float(args.cmb_bridge_z),
                rs_star_calibration=rs_star_calib,
                H0_km_s_Mpc=float(args.H0) if args.model == "lcdm" else None,
                Omega_m=float(args.Omega_m) if args.model == "lcdm" else None,
            ),
        )
        try:
            cmb_eval = cmb_like.evaluate(model)
            r_cmb = cmb_like.chi2_from_evaluation(cmb_eval)
        except Exception as e:
            raise SystemExit(f"CMB priors evaluation failed: {e}") from e

        pred = dict(cmb_eval.predicted_for_keys)
        pred_all = dict(cmb_eval.predicted_all)
        # Guardrail: for gsc_transition, if bridge_z <= z_transition then the
        # CMB D_M(z*) integral never enters the powerlaw segment.
        if args.model == "gsc_transition":
            import math

            bridge_z_used = float(pred_all.get("bridge_z", float("nan")))
            zt = float(args.gsc_ztrans)
            if math.isfinite(bridge_z_used) and bridge_z_used <= zt:
                print(
                    f"[WARN] gsc_transition degeneracy: bridge_z_used={bridge_z_used:g} <= z_transition={zt:g}; "
                    "CMB D_M(z*) integral is LCDM-only (not diagnostic for the powerlaw segment)."
                )
        per.append((cmb_ds.name, r_cmb))
        r = Chi2Result(chi2=float(r.chi2 + r_cmb.chi2), ndof=int(r.ndof + r_cmb.ndof), params=dict(r.params))
        if args.cmb_debug:
            import math

            print("cmb debug:")
            for k in ("z_star", "r_s_star_Mpc", "D_M_star_Mpc", "theta_star", "lA", "R", "rd_Mpc"):
                if k in pred_all:
                    print(f"  pred.{k} = {pred_all[k]:.16g}")
            for k in ("bridge_z", "bridge_H_ratio", "Omega_m_early", "Omega_r"):
                if k in pred_all:
                    print(f"  pred.{k} = {pred_all[k]:.16g}")
            for pr in cmb_ds.priors:
                k = pr.name
                y = float(pr.value)
                y_pred = float(pred.get(k, float("nan")))
                sigma_eff = math.sqrt(float(pr.sigma) ** 2 + float(pr.sigma_theory) ** 2)
                r_sig = (y_pred - y) / sigma_eff if sigma_eff > 0 and math.isfinite(y_pred) else float("nan")
                contrib = r_sig * r_sig if math.isfinite(r_sig) else float("nan")
                print(
                    f"  {k}: prior={y:.16g}  pred={y_pred:.16g}  "
                    f"sigma={pr.sigma:.6g}  sigma_theory={pr.sigma_theory:.6g}  "
                    f"pull={r_sig:.6g}  chi2={contrib:.6g}"
                )

    print(f"model={args.model}  H0={args.H0} km/s/Mpc")
    for name, r_ds in per:
        line = f"{name}: chi2={r_ds.chi2:.6f}  ndof={r_ds.ndof}"
        if r_ds.ndof > 0:
            line += f"  chi2/ndof={r_ds.chi2/r_ds.ndof:.6f}"
        method = r_ds.meta.get("method")
        if method:
            line += f"  method={method}"
        print(line)

    print(f"total: chi2={r.chi2:.6f}  ndof={r.ndof}")
    if r.ndof > 0:
        print(f"total: chi2/ndof={r.chi2/r.ndof:.6f}")
    if r.params:
        print("params:")
        for k in sorted(r.params.keys()):
            print(f"  {k} = {r.params[k]:.12g}")


if __name__ == "__main__":
    main()

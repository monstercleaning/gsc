#!/usr/bin/env python3
"""Evaluate compressed CMB priors via the reusable Phase 2 early-time driver."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import sys
from typing import Any, Dict, Sequence


V101_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V101_DIR))

from _outdir import resolve_outdir, resolve_path_under_outdir  # noqa: E402
from gsc.datasets.cmb_priors import CMBPriorsDataset  # noqa: E402
from gsc.datasets.cmb_priors_driver import CMBPriorsLikelihood  # noqa: E402
from gsc.early_time.cmb_priors_driver import CMBPriorsDriverConfig  # noqa: E402
from gsc.early_time.params import early_time_params_from_namespace  # noqa: E402
from gsc.measurement_model import (  # noqa: E402
    FlatLambdaCDMHistory,
    GSCTransitionHistory,
    H0_to_SI,
    PowerLawHistory,
)


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, ds: CMBPriorsDataset, predicted: Dict[str, float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["name", "prior", "sigma", "sigma_theory", "pred", "diag_pull", "diag_contrib"])
        for pr in ds.priors:
            pred = float(predicted[pr.name])
            sigma_eff = math.sqrt(float(pr.sigma) ** 2 + float(pr.sigma_theory) ** 2)
            pull = (pred - float(pr.value)) / sigma_eff if sigma_eff > 0.0 else float("nan")
            w.writerow(
                [
                    pr.name,
                    f"{float(pr.value):.16g}",
                    f"{float(pr.sigma):.16g}",
                    f"{float(pr.sigma_theory):.16g}",
                    f"{pred:.16g}",
                    f"{pull:.16g}",
                    f"{(pull * pull):.16g}",
                ]
            )


def _build_model(args: argparse.Namespace):
    h0_si = H0_to_SI(float(args.H0))
    if args.model == "lcdm":
        omega_l = 1.0 - float(args.Omega_m)
        return FlatLambdaCDMHistory(
            H0=float(h0_si),
            Omega_m=float(args.Omega_m),
            Omega_Lambda=float(omega_l),
        )
    if args.model == "gsc_powerlaw":
        return PowerLawHistory(H0=float(h0_si), p=float(args.gsc_p))
    return GSCTransitionHistory(
        H0=float(h0_si),
        Omega_m=float(args.Omega_m),
        Omega_Lambda=float(args.Omega_L),
        p=float(args.gsc_p),
        z_transition=float(args.gsc_ztrans),
    )


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="early_time_cmb_priors_chi2",
        description="Phase 2 M2 driver: evaluate compressed CMB priors chi2 via reusable early-time component.",
    )
    ap.add_argument("--model", choices=["lcdm", "gsc_powerlaw", "gsc_transition"], default="lcdm")
    ap.add_argument("--H0", type=float, default=67.4)
    ap.add_argument("--Omega-m", dest="Omega_m", type=float, default=0.315)
    ap.add_argument("--Omega-L", dest="Omega_L", type=float, default=0.685)
    ap.add_argument("--gsc-p", type=float, default=0.6)
    ap.add_argument("--gsc-ztrans", type=float, default=1.8)
    ap.add_argument("--cmb", type=Path, required=True, help="Compressed CMB priors CSV.")
    ap.add_argument("--cmb-cov", type=Path, default=None, help="Optional covariance (.cov/.npz).")
    ap.add_argument("--cmb-mode", choices=["shift_params", "distance_priors"], default="distance_priors")
    ap.add_argument("--cmb-bridge-z", type=float, default=None)
    ap.add_argument("--omega-b-h2", type=float, required=True)
    ap.add_argument("--omega-c-h2", type=float, required=True)
    ap.add_argument("--Neff", dest="N_eff", type=float, default=3.046)
    ap.add_argument("--Tcmb-K", type=float, default=2.7255)
    ap.add_argument(
        "--out-dir",
        "--outdir",
        dest="outdir",
        type=Path,
        default=None,
        help="Output root (CLI > GSC_OUTDIR > v11.0.0/artifacts/release).",
    )
    ap.add_argument("--out", type=Path, default=Path("early_time/cmb_priors_report.json"))
    ap.add_argument("--out-csv", type=Path, default=Path("early_time/cmb_priors_table.csv"))
    args = ap.parse_args(argv)

    if args.model != "lcdm" and args.cmb_bridge_z is None:
        raise SystemExit("--cmb-bridge-z is required for non-LCDM models.")

    try:
        early_time_params = early_time_params_from_namespace(
            args,
            require=True,
            context="CMB priors chi2",
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if early_time_params is None:  # pragma: no cover - guarded above
        raise SystemExit("CMB priors chi2 requires --omega-b-h2 and --omega-c-h2")

    out_root = resolve_outdir(args.outdir, v101_dir=V101_DIR)
    out_json = resolve_path_under_outdir(args.out, out_root=out_root)
    out_csv = resolve_path_under_outdir(args.out_csv, out_root=out_root)
    if out_json is None or out_csv is None:  # pragma: no cover
        raise SystemExit("failed to resolve output paths")

    print(f"[info] OUTDIR={out_root}")
    print(f"[info] REPORT={out_json}")
    print(f"[info] TABLE={out_csv}")

    model = _build_model(args)
    driver_cfg = CMBPriorsDriverConfig(
        **early_time_params.to_cmb_driver_kwargs(),
        mode=str(args.cmb_mode),
        z_bridge=None if args.cmb_bridge_z is None else float(args.cmb_bridge_z),
        H0_km_s_Mpc=float(args.H0) if args.model == "lcdm" else None,
        Omega_m=float(args.Omega_m) if args.model == "lcdm" else None,
    )
    ds = CMBPriorsDataset.from_csv(args.cmb, cov_path=args.cmb_cov, name="cmb")
    likelihood = CMBPriorsLikelihood(priors=ds, driver_config=driver_cfg)

    try:
        evaluation = likelihood.evaluate(model)
        result = likelihood.chi2_from_evaluation(evaluation)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    payload = {
        "model": str(args.model),
        "inputs": {
            "H0_km_s_Mpc": float(args.H0),
            "Omega_m": float(args.Omega_m),
            "Omega_L": float(args.Omega_L),
            "gsc_p": float(args.gsc_p),
            "gsc_ztrans": float(args.gsc_ztrans),
            "omega_b_h2": float(early_time_params.omega_b_h2),
            "omega_c_h2": float(early_time_params.omega_c_h2),
            "N_eff": float(early_time_params.N_eff),
            "Tcmb_K": float(early_time_params.Tcmb_K),
            "cmb_mode": str(args.cmb_mode),
            "cmb_bridge_z": None if args.cmb_bridge_z is None else float(args.cmb_bridge_z),
        },
        "priors": {
            "csv": str(args.cmb.expanduser().resolve()),
            "cov": str(args.cmb_cov.expanduser().resolve()) if args.cmb_cov is not None else None,
            "keys": list(ds.keys),
        },
        "result": {
            "chi2": float(result.chi2),
            "ndof": int(result.ndof),
            "meta": dict(result.meta),
        },
        "predicted": dict(evaluation.predicted_for_keys),
        "predicted_all": dict(evaluation.predicted_all),
    }
    _write_json(out_json, payload)
    _write_csv(out_csv, ds, evaluation.predicted_for_keys)
    print(f"[ok] wrote {out_json}")
    print(f"[ok] wrote {out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

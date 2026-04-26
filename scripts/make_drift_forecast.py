#!/usr/bin/env python3
"""Generate a canonical redshift-drift (Sandage–Loeb) mock/forecast CSV (v11.0.0).

This script is dependency-free (stdlib only). It writes a CSV compatible with
`gsc.datasets.drift.DriftDataset`.

Example (recreate the committed ANDES-style mock):
  python3 v11.0.0/scripts/make_drift_forecast.py \\
    --model lcdm --H0 67.4 --Omega-m 0.315 \\
    --baseline-years 20 \\
    --z-list \"2.0,2.5,3.0,3.5,4.0,4.5\" \\
    --sigma-cm-s 1.0 \\
    --out v11.0.0/data/drift/andes_20yr_mock_lcdm_fiducial.csv
"""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path
import sys
from typing import List


# Allow running from repo root: add v11.0.0/ to import path.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.measurement_model import (  # noqa: E402
    FlatLambdaCDMHistory,
    GSCTransitionHistory,
    H0_to_SI,
    PowerLawHistory,
    delta_v_cm_s,
)


def _parse_grid(spec: str) -> List[float]:
    s = spec.strip()
    if not s:
        raise ValueError("empty z spec")
    if ":" in s:
        parts = [p.strip() for p in s.split(":")]
        if len(parts) != 3:
            raise ValueError("range spec must be 'start:stop:step'")
        start, stop, step = (float(parts[0]), float(parts[1]), float(parts[2]))
        if step <= 0:
            raise ValueError("step must be positive")
        out: List[float] = []
        v = start
        tol = 1e-12 * max(1.0, abs(stop))
        while v <= stop + tol:
            out.append(float(v))
            v += step
        if not out:
            raise ValueError("empty range after parsing")
        return out
    return [float(tok.strip()) for tok in s.split(",") if tok.strip()]


def _build_model(args):
    H0_si = H0_to_SI(float(args.H0))
    if args.model == "lcdm":
        Om = float(args.Omega_m)
        return FlatLambdaCDMHistory(H0=H0_si, Omega_m=Om, Omega_Lambda=1.0 - Om)
    if args.model == "gsc_powerlaw":
        return PowerLawHistory(H0=H0_si, p=float(args.p))
    if args.model == "gsc_transition":
        Om = float(args.Omega_m)
        return GSCTransitionHistory(
            H0=H0_si,
            Omega_m=Om,
            Omega_Lambda=1.0 - Om,
            p=float(args.p),
            z_transition=float(args.z_transition),
        )
    raise ValueError(f"unknown model: {args.model!r}")


def _sigma_dv_liske_elt_cm_s(
    *,
    z: float,
    snr: float,
    n_qso: int,
    sigma_e: float,
    lambda_exp: float,
) -> float:
    """ELT/ANDES-like velocity drift uncertainty (cm/s) from a standard forecast scaling.

    This follows the widely-used Liske/ELT scaling form:
      sigma_dv = sigma_e * (SNR / 2370)^(-1) * (N_QSO / 30)^(-1/2) * ((1+z)/5)^(-lambda)

    Notes:
    - sigma_dv is treated as independent of the baseline; baseline enters the *signal*.
    - We take lambda as a positive number and apply a minus sign (decreasing uncertainty with z).
    """
    if z < 0:
        raise ValueError("z must be >= 0 for this sigma model")
    if snr <= 0:
        raise ValueError("snr must be positive")
    if n_qso <= 0:
        raise ValueError("n_qso must be positive")
    if sigma_e <= 0:
        raise ValueError("sigma_e must be positive")
    if lambda_exp <= 0:
        raise ValueError("lambda_exp must be positive")

    snr_factor = (snr / 2370.0) ** (-1.0)
    n_factor = (float(n_qso) / 30.0) ** (-0.5)
    z_factor = ((1.0 + float(z)) / 5.0) ** (-float(lambda_exp))
    return float(sigma_e) * float(snr_factor) * float(n_factor) * float(z_factor)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=["lcdm", "gsc_powerlaw", "gsc_transition"], default="lcdm")
    ap.add_argument(
        "--scenario",
        choices=["elt_andes_liske_conservative"],
        default=None,
        help="Optional preset for standard literature drift forecasts.",
    )
    ap.add_argument("--H0", type=float, default=67.4, help="H0 in km/s/Mpc (fiducial for generating dv)")
    ap.add_argument("--Omega-m", dest="Omega_m", type=float, default=0.315, help="Omega_m (lcdm/transition)")
    ap.add_argument("--p", type=float, default=0.6, help="power-law exponent (gsc_*)")
    ap.add_argument("--z-transition", dest="z_transition", type=float, default=1.8, help="transition redshift (gsc_transition)")

    ap.add_argument("--baseline-years", type=float, default=None)
    ap.add_argument("--z-list", type=str, default=None, help="comma list or start:stop:step")
    ap.add_argument("--z-range", type=str, default=None, help="alias for --z-list with start:stop:step")

    ap.add_argument("--sigma-cm-s", type=float, default=1.0, help="1σ error per point/bin, in cm/s (constant sigma mode)")
    ap.add_argument("--snr", type=float, default=3000.0, help="S/N for Liske/ELT sigma(z) model")
    ap.add_argument("--n-qso", dest="n_qso", type=int, default=6, help="N_QSO for Liske/ELT sigma(z) model")
    ap.add_argument("--sigma-e", dest="sigma_e", type=float, default=1.35, help="sigma_e prefactor for Liske/ELT sigma(z) model")
    ap.add_argument(
        "--lambda-le4",
        dest="lambda_le4",
        type=float,
        default=1.7,
        help="lambda exponent for z<=4 in Liske/ELT sigma(z) model",
    )
    ap.add_argument(
        "--lambda-gt4",
        dest="lambda_gt4",
        type=float,
        default=0.9,
        help="lambda exponent for z>4 in Liske/ELT sigma(z) model",
    )
    ap.add_argument("--seed", type=int, default=None, help="PRNG seed for optional noise")
    ap.add_argument("--add-noise", action="store_true", help="add Gaussian noise consistent with sigma")

    ap.add_argument("--label", type=str, default=None)
    ap.add_argument("--source", type=str, default="Synthetic; generated by this repo")
    ap.add_argument("--note", type=str, default=None)
    ap.add_argument("--out", type=Path, required=True)

    args = ap.parse_args()

    if args.scenario == "elt_andes_liske_conservative":
        if args.z_list is None and args.z_range is None:
            args.z_list = "2.0,2.5,3.0,3.5,4.5"
        if args.baseline_years is None:
            args.baseline_years = 20.0

    if args.baseline_years is None or args.baseline_years <= 0:
        raise SystemExit("--baseline-years must be positive (or use a scenario that sets it)")
    if args.sigma_cm_s <= 0:
        raise SystemExit("--sigma-cm-s must be positive")

    z_spec = args.z_list or args.z_range
    if z_spec is None:
        raise SystemExit("Provide --z-list (or --z-range)")
    zs = _parse_grid(z_spec)
    if not zs:
        raise SystemExit("Empty z list")
    if any(z < 0 for z in zs):
        raise SystemExit("Require z>=0 for drift forecast points")

    model = _build_model(args)
    H0_si = float(model.H(0.0))

    rng = random.Random(args.seed) if args.seed is not None else None

    label = args.label
    if label is None:
        label = f"{args.model} mock"
    if args.scenario == "elt_andes_liske_conservative":
        note_default = (
            "ELT/ANDES-like conservative drift forecast using a standard Liske/ELT sigma(z) scaling: "
            f"SNR={float(args.snr):g}, N_QSO={int(args.n_qso)}, sigma_e={float(args.sigma_e):g}, "
            f"lambda(z<=4)={float(args.lambda_le4):g}, lambda(z>4)={float(args.lambda_gt4):g}. "
            f"Signal dv is generated from the chosen fiducial history (H0={float(args.H0):g}) over "
            f"baseline={float(args.baseline_years):g} years."
        )
    else:
        note_default = (
            f"Mock dataset: dv values are generated from {args.model} fiducial "
            f"(H0={float(args.H0):g}, baseline={float(args.baseline_years):g}y), "
            f"with illustrative sigma={float(args.sigma_cm_s):g} cm/s."
        )
    note = args.note or note_default

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["z", "dv_cm_s", "sigma_dv_cm_s", "baseline_years", "label", "source", "note"])
        for z in zs:
            if args.scenario == "elt_andes_liske_conservative":
                lam = float(args.lambda_le4) if float(z) <= 4.0 else float(args.lambda_gt4)
                sigma = _sigma_dv_liske_elt_cm_s(
                    z=float(z),
                    snr=float(args.snr),
                    n_qso=int(args.n_qso),
                    sigma_e=float(args.sigma_e),
                    lambda_exp=float(lam),
                )
            else:
                sigma = float(args.sigma_cm_s)
            dv_true = float(delta_v_cm_s(z=float(z), years=float(args.baseline_years), H0=H0_si, H_of_z=model.H))
            dv_obs = dv_true
            if args.add_noise:
                if rng is None:
                    rng = random.Random(0)
                dv_obs = dv_true + rng.gauss(0.0, float(sigma))
            w.writerow(
                [
                    f"{float(z):.10g}",
                    f"{float(dv_obs):.10g}",
                    f"{float(sigma):.10g}",
                    f"{float(args.baseline_years):.10g}",
                    label,
                    args.source,
                    note,
                ]
            )

    print(f"WROTE {args.out} (N={len(zs)})")


if __name__ == "__main__":
    main()

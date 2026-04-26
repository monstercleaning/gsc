#!/usr/bin/env python3
"""
predictions_compute_P9.py — compute Prediction P9 (constancy of μ = m_p/m_e).

Under strict universal coherent scaling (Section 1.3 of GSC_Framework.md),
the proton-electron mass ratio μ = m_p/m_e is σ-invariant:

    μ ∝ m_p / m_e ∝ σ^{-1} / σ^{-1} = σ^0

The framework therefore predicts μ̇/μ = 0 to all orders in σ-evolution.
Any non-zero detection of μ̇/μ at any redshift falsifies the universal-
scaling assumption (T1).

The pipeline encodes this null prediction and provides infrastructure
for non-universal-coupling exploration via the --non-universal flag.

Usage:
    python3 scripts/predictions_compute_P9.py
    python3 scripts/predictions_compute_P9.py --non-universal --eta-qcd 0.01
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_REDSHIFTS = (0.0, 0.7, 1.0, 2.0, 3.0)

DEFAULTS = {
    # Strict universal scaling: differential coupling is zero by definition.
    "eta_qcd_minus_eta_higgs": 0.0,
    "p_powerlaw": 0.001,
    "H0_per_yr": 6.9e-11,  # H_0 in 1/yr units (~67 km/s/Mpc)
}


def predicted_mu_evolution(
    *,
    redshifts: tuple,
    eta_diff: float,
    p_powerlaw: float,
    H0_per_yr: float,
) -> dict:
    """Compute predicted μ̇/μ at z=0 and Δμ/μ at given redshifts.

    Under universal scaling (eta_diff = 0): all values are 0.
    Under non-universal coupling (eta_diff != 0): proportional to differential
    sector coupling and to σ-evolution rate.
    """
    mu_dot_over_mu_z0 = eta_diff * (-p_powerlaw * H0_per_yr)

    rows = []
    for z in redshifts:
        # σ(z)/σ(0) = (1+z)^(-p) under powerlaw
        sigma_ratio = (1.0 + z) ** (-p_powerlaw)
        # Under non-universal coupling, Δμ/μ = eta_diff × ln(σ(z)/σ(0))
        delta_mu_over_mu = eta_diff * (-p_powerlaw) * float(__import__("math").log(1.0 + z) if z > 0 else 0.0)
        rows.append(
            {
                "z": float(z),
                "sigma_ratio": float(f"{sigma_ratio:.9e}"),
                "delta_mu_over_mu_predicted": float(f"{delta_mu_over_mu:.6e}"),
            }
        )

    return {
        "mu_dot_over_mu_z0_per_yr": float(f"{mu_dot_over_mu_z0:.6e}"),
        "differential_coupling_eta_diff": float(eta_diff),
        "powerlaw_p": float(p_powerlaw),
        "trajectory": rows,
    }


def make_record(
    *,
    eta_diff: float,
    p_powerlaw: float,
    H0_per_yr: float,
    redshifts: tuple,
    non_universal: bool,
) -> dict:
    pred = predicted_mu_evolution(
        redshifts=redshifts,
        eta_diff=eta_diff,
        p_powerlaw=p_powerlaw,
        H0_per_yr=H0_per_yr,
    )
    return {
        "schema": "predictions_p9_pipeline_output_v1",
        "prediction_id": "P9",
        "title": "Constancy of μ = m_p/m_e under universal coherent scaling",
        "tier": "T1 (consistency check)",
        "tool": "predictions_compute_P9",
        "tool_version": "v0.1",
        "physics_status": (
            "Under strict universal coherent scaling (geometric lock), μ is "
            "σ-invariant by construction; predicted μ̇/μ = 0 to all orders. "
            "The non-universal opt-in mode parametrises differential coupling "
            "η_QCD - η_Higgs to explore how detection of μ̇/μ would constrain "
            "the universality assumption."
        ),
        "scaling_mode": (
            "non-universal (geometric-lock violated)"
            if non_universal
            else "universal coherent scaling (geometric-lock honoured)"
        ),
        "prediction": pred,
        "framework_implications": {
            "universal_scaling_outcome": (
                "Predicted μ̇/μ = 0 and Δμ/μ = 0 at all z. Any observed non-zero "
                "value at any significance falsifies the universal coherent-"
                "scaling assumption (T1) and propagates to all higher tiers."
            ),
        },
        "determinism_note": (
            "This file intentionally contains no timestamp; SHA-256 is a function "
            "only of the registered inputs."
        ),
    }


def write_output(record: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(record, indent=2, sort_keys=True) + "\n"
    output_path.write_text(text, encoding="utf-8")
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    sys.stdout.write(f"wrote {output_path}\n  SHA-256: {sha}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--eta-qcd",
        type=float,
        default=DEFAULTS["eta_qcd_minus_eta_higgs"],
        help=(
            "differential coupling η_QCD - η_Higgs (default 0 under universal "
            "scaling)"
        ),
    )
    parser.add_argument(
        "--p", type=float, default=DEFAULTS["p_powerlaw"]
    )
    parser.add_argument(
        "--H0-per-yr", type=float, default=DEFAULTS["H0_per_yr"]
    )
    parser.add_argument(
        "--non-universal",
        action="store_true",
        help="enable non-universal coupling mode (geometric-lock violated)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT
        / "predictions_register"
        / "P9_proton_electron_mass_ratio"
        / "pipeline_output.json",
    )
    parser.add_argument("--print", action="store_true")
    args = parser.parse_args(argv)

    record = make_record(
        eta_diff=args.eta_qcd,
        p_powerlaw=args.p,
        H0_per_yr=args.H0_per_yr,
        redshifts=DEFAULT_REDSHIFTS,
        non_universal=args.non_universal,
    )
    if args.print:
        sys.stdout.write(json.dumps(record, indent=2, sort_keys=True) + "\n")
    write_output(record, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
predictions_compute_P10.py — compute Prediction P10 (TeV blazar dispersion).

Computes the GSC-predicted energy-flat stochastic arrival-time dispersion
for representative TeV blazars under the σ(x,t) extension (Section 6 of
GSC_Framework.md).

Physics:

If σ has spatial gradients ∇σ sourced by gravitational potential, photons
traversing varying σ accumulate path-dependent arrival-time variance:

    σ²_t = k_grad² × ∫₀^{d_L} (∇σ)² dℓ

Under universal coherent scaling, this is energy-FLAT (no E-dependence),
distinguishing GSC from quantum-gravity LIV.

The implementation parametrises (∇σ)² × ∫dℓ as k_grad² × (d_L / 1 Gpc) × ε
where ε is a typical fractional σ-fluctuation amplitude expected in the
late-universe linear-density-perturbation regime.

Usage:
    python3 scripts/predictions_compute_P10.py
    python3 scripts/predictions_compute_P10.py --k-grad 1e-15 --epsilon 1e-3
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Representative TeV blazar lines of sight (z, distance scale).
BLAZARS = [
    {"name": "Mrk 421", "z": 0.030, "d_L_Gpc": 0.130},
    {"name": "Mrk 501", "z": 0.034, "d_L_Gpc": 0.150},
    {"name": "PKS 2155-304", "z": 0.116, "d_L_Gpc": 0.520},
    {"name": "1ES 1101-232", "z": 0.186, "d_L_Gpc": 0.860},
    {"name": "3C 279", "z": 0.536, "d_L_Gpc": 3.000},
]

DEFAULTS = {
    # σ-gradient coupling.
    # CORRECTED v0.2: previously declared "dimensionless"; this was inconsistent
    # with the formula σ²_t = k_grad² × d_L × ε which requires k_grad to have
    # units of [seconds × length^{-1/2}] for σ_t to come out in seconds.
    # In SI (where length is in meters), reasonable k_grad ~ 10^-22 s/m^{1/2}
    # would give σ_t ~ 1 ns at 1 Gpc — sub-threshold for any current detector.
    # The framework's natural scale is k_grad ~ √(σ²_t / d_L) where σ²_t is
    # set by the σ-gradient amplitude. The default below is parametric.
    "k_grad_seconds_per_sqrt_meter": 3e-23,
    # fractional σ fluctuation amplitude along the line of sight
    "epsilon_sigma_fluctuation": 1e-3,
    "n_paths_per_blazar": 100,
}

# Detector capabilities (representative).
DETECTOR_TARGETS = {
    "HESS (current archival)": {"min_resolvable_sigma_t_s": 30.0},
    "MAGIC (current archival)": {"min_resolvable_sigma_t_s": 25.0},
    "CTAO (commissioning 2026, science 2027)": {"min_resolvable_sigma_t_s": 1.0},
}


def predicted_dispersion(*, blazar: dict, k_grad: float, epsilon: float) -> dict:
    """Predicted σ_t (RMS arrival-time spread) for one blazar line-of-sight.

    Dimensional consistency:
        σ²_t [s²] = k_grad² [s²/m] × d_L [m] × ε [dimensionless]
                  = k_grad² × d_L_meters × ε  (all in SI)

    where k_grad has units s × m^{-1/2}.
    """
    d_L_Gpc = blazar["d_L_Gpc"]
    meters_per_Gpc = 3.0857e25  # 1 Gpc in meters
    d_L_meters = d_L_Gpc * meters_per_Gpc

    # Dimensionally consistent computation:
    sigma_sq_t = (k_grad ** 2) * d_L_meters * epsilon
    sigma_t_seconds = math.sqrt(max(sigma_sq_t, 0.0))
    return {
        "name": blazar["name"],
        "z": blazar["z"],
        "d_L_Gpc": d_L_Gpc,
        "predicted_sigma_t_seconds": float(f"{sigma_t_seconds:.3e}"),
    }


def detectability_assessment(predictions: list, detectors: dict) -> dict:
    """For each detector, list which blazars are above its sensitivity floor."""
    results = {}
    for label, target in sorted(detectors.items()):
        threshold = float(target["min_resolvable_sigma_t_s"])
        detectable = [
            p["name"] for p in predictions
            if p["predicted_sigma_t_seconds"] > threshold
        ]
        results[label] = {
            "min_resolvable_sigma_t_s": threshold,
            "detectable_blazars": detectable,
            "any_detectable": len(detectable) > 0,
        }
    return results


def make_record(*, k_grad: float, epsilon: float, blazars: list, detectors: dict) -> dict:
    predictions = [
        predicted_dispersion(blazar=b, k_grad=k_grad, epsilon=epsilon)
        for b in blazars
    ]
    detect = detectability_assessment(predictions, detectors)

    return {
        "schema": "predictions_p10_pipeline_output_v1",
        "prediction_id": "P10",
        "title": "TeV blazar arrival-time dispersion (energy-flat, structure-correlated)",
        "tier": "T4 (σ(x) spatial-extension test)",
        "tool": "predictions_compute_P10",
        "tool_version": "v0.2-dimensionally-consistent",
        "physics_status": (
            "Parametric σ(x) gradient model. The k_grad coupling is a free "
            "parameter; the σ(x,t) field equation derivation in Section 6 of "
            "GSC_Framework.md is gating piece for narrowing it to a specific "
            "predicted value. Energy-flat signature distinguishes from QG-LIV."
        ),
        "registered_couplings": {
            "k_grad_seconds_per_sqrt_meter": float(f"{k_grad:.3e}"),
            "k_grad_units_note": "k_grad has SI units of s × m^{-1/2}; corrected v0.2 from earlier dimensionless misdescription",
            "epsilon_sigma_fluctuation": float(f"{epsilon:.3e}"),
        },
        "blazar_predictions": predictions,
        "detector_assessment": detect,
        "discriminator_vs_qg_liv": (
            "Standard QG-LIV signatures are energy-dependent: Δt ∝ E (linear) "
            "or Δt ∝ E² (quadratic). GSC predicts NO E-dependence; instead, "
            "stochastic variance correlated with line-of-sight DM column "
            "density. A positive observation of energy-flat structure-"
            "correlated dispersion would distinguish GSC σ(x) from QG-LIV."
        ),
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
        "--k-grad",
        type=float,
        default=DEFAULTS["k_grad_seconds_per_sqrt_meter"],
        help="σ-gradient coupling in s × m^{-1/2} (default 3e-23)",
    )
    parser.add_argument("--epsilon", type=float, default=DEFAULTS["epsilon_sigma_fluctuation"])
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT
        / "predictions_register"
        / "P10_tev_blazar_dispersion"
        / "pipeline_output.json",
    )
    parser.add_argument("--print", action="store_true")
    args = parser.parse_args(argv)

    record = make_record(
        k_grad=args.k_grad,
        epsilon=args.epsilon,
        blazars=BLAZARS,
        detectors=DETECTOR_TARGETS,
    )
    if args.print:
        sys.stdout.write(json.dumps(record, indent=2, sort_keys=True) + "\n")
    write_output(record, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
predictions_compute_P3.py — compute Prediction P3 (neutron-lifetime beam-trap).

Computes the GSC-predicted neutron lifetime difference between beam and trap
experimental geometries under σ-environmental dependence (Section 6 of
GSC_Framework.md).

PHYSICS — CORRECTED in v0.2 (was wrong-by-factor-of-five-and-sign in v0.1):

Under universal coherent scaling (Section 3.3 of GSC_Framework.md) the
relevant scalings are:

    m ∝ σ^{-1}  →  Δm = m_n - m_p ∝ σ^{-1},  (Δm)^5 ∝ σ^{-5}
    M_W ∝ σ^{-1}  →  G_F = √2 g^2 / (8 M_W^2) ∝ σ^{+2},  G_F^2 ∝ σ^{+4}

β-decay rate:
    Γ_β ∝ G_F^2 × (Δm)^5 × (dimensionless phase-space) ∝ σ^{+4-5} = σ^{-1}
    τ_n = 1/Γ_β ∝ σ^{+1}

Therefore the σ-sensitivity is

    d ln τ_n / d ln σ = +1     (NOT -5 as in v0.1)

THE GEOMETRIC-LOCK PROBLEM
==========================

τ_n is measured by counting atomic-clock ticks. Atomic transition periods
also scale: T_atomic ∝ ω_atomic^{-1} ∝ (Ry)^{-1} ∝ σ^{+1}. Then:

    τ_n (in seconds, measured by atomic clock) ∝ τ_n^{phys} / T_atomic
                                                 ∝ σ^{+1} / σ^{+1} = σ^0

This is the geometric lock: under universal coherent scaling, τ_n measured
in atomic-clock seconds is INVARIANT under any σ-shift. The framework's
universality requirement therefore predicts NO beam-trap discrepancy.

CONSEQUENCES
============

Within strict universal coherent scaling (Sections 1.3, 2.4 of
GSC_Framework.md), the standard GSC framework PREDICTS NO SUCH DISCREPANCY.
The observed +9.3 ± 2.3 s anomaly is therefore NOT EXPLAINED by GSC at
the T1+T2 level.

To recover an explanation, the σ(x,t) extension (Section 6) would need
to be promoted to NON-UNIVERSAL local coupling — σ couples to the
SU(2)_L sector (G_F, M_W) differently than to the atomic Schrödinger
sector (m_e, α). This is a violation of the geometric lock and lies
beyond the canonical T1 framework. P3 then becomes a test of NON-UNIVERSAL
σ-coupling, not of GSC proper.

The pipeline below records this corrected analysis. The output now reports
that with universal scaling, τ_n^beam = τ_n^trap (no GSC contribution to
the anomaly). The historical phenomenological parameter `delta_sigma_fraction`
is retained as a non-universal-coupling exploration mode but is no longer
the default.

Usage:
    python3 scripts/predictions_compute_P3.py
    python3 scripts/predictions_compute_P3.py --non-universal --delta-sigma-fraction -0.0105
    python3 scripts/predictions_compute_P3.py --output predictions_register/P3_neutron_lifetime/pipeline_output.json


Usage:
    python3 scripts/predictions_compute_P3.py
    python3 scripts/predictions_compute_P3.py --delta-sigma-fraction -0.002
    python3 scripts/predictions_compute_P3.py --output predictions_register/P3_neutron_lifetime/pipeline_output.json

Output schema: predictions_p3_pipeline_output_v1.

Status: leading-order parametric model. The actual δσ/σ between trap
and beam environments requires solving the σ(x,t) field equation with
realistic geometry (gating piece for Section 6 of GSC_Framework.md).
The current implementation parametrizes δσ/σ directly and propagates
to predicted τ_n^trap - τ_n^beam.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Experimental world averages (PDG-style, conservative as of 2024).
# These are the targets that GSC needs to explain.
TAU_N_BEAM_S = 887.7        # beam-method world average (s)
TAU_N_BEAM_SIGMA_S = 2.2    # systematic + statistical
TAU_N_TRAP_S = 878.4        # trap-method world average (s)
TAU_N_TRAP_SIGMA_S = 0.5    # systematic + statistical

# Sensitivity coefficients: d ln(τ_n) / d ln(σ).
# Corrected derivation (see module docstring): under universal coherent scaling,
#     τ_n^phys ∝ σ^{+1}        from G_F^2 (Δm)^5 with M_W, m ∝ σ^{-1}
# But τ_n measured in atomic-clock seconds:
#     τ_n^obs ∝ τ_n^phys / T_atomic ∝ σ^{+1} / σ^{+1} = σ^0
DLN_TAU_DLN_SIGMA_PHYSICAL = +1.0
DLN_TAU_DLN_SIGMA_OBSERVED_UNIVERSAL = 0.0

DEFAULTS = {
    "tau_n_intrinsic_s": 887.7,
    # Default mode: STRICT universal scaling. Predicted Δτ = 0 regardless of δσ.
    "delta_sigma_fraction_trap_minus_beam": 0.0,
}


def predicted_tau_difference(
    *,
    tau_intrinsic_s: float,
    delta_sigma_fraction: float,
    non_universal: bool,
) -> dict:
    """Compute (τ_n^beam, τ_n^trap, Δ) given intrinsic τ_n and δσ/σ.

    Convention: delta_sigma_fraction = (σ_trap - σ_beam) / σ_beam.

    Two modes:
    - Universal (default): τ_n in atomic-clock seconds is σ-invariant.
      Sensitivity is 0; predicted Δτ = 0 regardless of δσ.
    - Non-universal (opt-in): the SU(2)_L sector sees a different local σ
      from the atomic sector; the observable sensitivity is +1.
      A NEGATIVE δσ/σ (σ smaller in trap walls) gives a POSITIVE Δτ.
    """
    if non_universal:
        sensitivity = DLN_TAU_DLN_SIGMA_PHYSICAL
        mode = "non-universal (geometric-lock violated)"
    else:
        sensitivity = DLN_TAU_DLN_SIGMA_OBSERVED_UNIVERSAL
        mode = "universal coherent scaling (geometric-lock honoured)"

    delta_ln_tau_trap = sensitivity * delta_sigma_fraction
    tau_trap_predicted = tau_intrinsic_s * (1.0 + delta_ln_tau_trap)
    tau_beam_predicted = tau_intrinsic_s
    delta_tau = tau_beam_predicted - tau_trap_predicted

    return {
        "tau_n_beam_predicted_s": round(tau_beam_predicted, 4),
        "tau_n_trap_predicted_s": round(tau_trap_predicted, 4),
        "delta_tau_beam_minus_trap_s": round(delta_tau, 4),
        "delta_sigma_fraction_trap_minus_beam": float(delta_sigma_fraction),
        "tau_intrinsic_s": float(tau_intrinsic_s),
        "sensitivity_dlntau_dlnsigma": sensitivity,
        "scaling_mode": mode,
    }


def compute_consistency(prediction: dict) -> dict:
    """Compare the predicted τ_n values to observed beam and trap world averages."""
    tau_b_pred = prediction["tau_n_beam_predicted_s"]
    tau_t_pred = prediction["tau_n_trap_predicted_s"]
    delta_pred = prediction["delta_tau_beam_minus_trap_s"]

    delta_obs = TAU_N_BEAM_S - TAU_N_TRAP_S
    sigma_delta_obs = (TAU_N_BEAM_SIGMA_S ** 2 + TAU_N_TRAP_SIGMA_S ** 2) ** 0.5

    z_beam = (tau_b_pred - TAU_N_BEAM_S) / TAU_N_BEAM_SIGMA_S
    z_trap = (tau_t_pred - TAU_N_TRAP_S) / TAU_N_TRAP_SIGMA_S
    z_diff = (delta_pred - delta_obs) / sigma_delta_obs

    return {
        "observed_tau_n_beam_s": TAU_N_BEAM_S,
        "observed_tau_n_beam_sigma_s": TAU_N_BEAM_SIGMA_S,
        "observed_tau_n_trap_s": TAU_N_TRAP_S,
        "observed_tau_n_trap_sigma_s": TAU_N_TRAP_SIGMA_S,
        "observed_delta_beam_minus_trap_s": round(delta_obs, 4),
        "observed_delta_sigma_s": round(sigma_delta_obs, 4),
        "z_score_tau_beam": round(z_beam, 4),
        "z_score_tau_trap": round(z_trap, 4),
        "z_score_delta": round(z_diff, 4),
        "consistent_at_2sigma": (
            abs(z_beam) < 2.0 and abs(z_trap) < 2.0 and abs(z_diff) < 2.0
        ),
        "explains_observed_anomaly": abs(z_diff) < 1.0,
    }


def make_record(
    *,
    tau_intrinsic_s: float,
    delta_sigma_fraction: float,
    non_universal: bool,
) -> dict:
    pred = predicted_tau_difference(
        tau_intrinsic_s=tau_intrinsic_s,
        delta_sigma_fraction=delta_sigma_fraction,
        non_universal=non_universal,
    )
    consistency = compute_consistency(pred)

    return {
        "schema": "predictions_p3_pipeline_output_v1",
        "prediction_id": "P3",
        "title": "Neutron-lifetime beam-trap discrepancy",
        "tier": "T4",
        "tool": "predictions_compute_P3",
        "tool_version": "v0.2-corrected-geometric-lock",
        "physics_status": (
            "CORRECTED v0.2: under strict universal coherent scaling "
            "(Sections 1.3, 2.4 of GSC_Framework.md), atomic-clock-measured τ_n "
            "is σ-invariant (sensitivity coefficient = 0). The framework PREDICTS "
            "NO contribution to the beam-trap anomaly. To recover an explanation "
            "requires NON-UNIVERSAL σ-coupling (geometric-lock violated), which "
            "is beyond the canonical T1 framework. The previous v0.1 used a "
            "wrong sensitivity coefficient (-5 instead of +1 in physical units, "
            "and ignored the cancellation with atomic-clock σ-dependence)."
        ),
        "prediction": pred,
        "consistency_with_observed_anomaly": consistency,
        "framework_implications": {
            "universal_scaling_outcome": (
                "FAIL — predicted Δτ = 0 under universal coherent scaling, "
                "but observed +9.3 s anomaly is real. Framework cannot explain "
                "the discrepancy at T1+T2 level."
            ),
            "non_universal_extension_outcome": (
                "Possible explanation requires δσ/σ ≈ -1.05% non-universal local "
                "shift, which violates the geometric-lock condition and conflicts "
                "with EP-violation bounds (MICROSCOPE η < 10^-15) at >10σ."
            ),
            "honest_verdict": (
                "P3 cannot be claimed as 'GSC explains the beam-trap anomaly' "
                "within the canonical framework. The earlier v0.1 PASS verdict "
                "was a numerical artefact of two cancelling errors (sign of mass "
                "scaling and missing G_F running). P3 is downgraded to: "
                "'GSC predicts NO anomaly — observed discrepancy must have "
                "another origin (Standard Model systematic? new non-σ physics?).'"
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
        "--tau-intrinsic-s",
        type=float,
        default=DEFAULTS["tau_n_intrinsic_s"],
        help="GSC-frame intrinsic τ_n in seconds (default 887.7, beam-method WA)",
    )
    parser.add_argument(
        "--delta-sigma-fraction",
        type=float,
        default=DEFAULTS["delta_sigma_fraction_trap_minus_beam"],
        help="δσ/σ between trap and beam environments (default 0 in universal mode)",
    )
    parser.add_argument(
        "--non-universal",
        action="store_true",
        help=(
            "Use non-universal coupling mode (sensitivity = +1 instead of 0). "
            "This violates the geometric-lock condition and is beyond canonical "
            "GSC; only useful for exploring how much non-universality would be "
            "needed to match the anomaly."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT
        / "predictions_register"
        / "P3_neutron_lifetime"
        / "pipeline_output.json",
    )
    parser.add_argument("--print", action="store_true")
    args = parser.parse_args(argv)

    record = make_record(
        tau_intrinsic_s=args.tau_intrinsic_s,
        delta_sigma_fraction=args.delta_sigma_fraction,
        non_universal=args.non_universal,
    )

    if args.print:
        sys.stdout.write(json.dumps(record, indent=2, sort_keys=True) + "\n")

    write_output(record, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
predictions_compute_P2.py — compute Prediction P2 (21cm Cosmic-Dawn signal).

Computes the GSC-predicted globally-averaged 21cm differential brightness
temperature δT_b at the Cosmic Dawn epoch (z ≈ 15–25) and its deviation
from the ΛCDM expectation due to σ-evolution of recombination, spin
temperature coupling, and X-ray heating.

Physics (parametric first pass):

The standard 21cm absorption profile in ΛCDM has a characteristic minimum
near z ≈ 17 (frequency ≈ 78 MHz) with depth δT_b ≈ -200 mK in the
adiabatic-cooling-limited model.

EDGES 2018 reported an anomalously deep absorption ≈ -500 mK at z ≈ 17,
currently unexplained.

Under GSC, σ-evolution between recombination and Cosmic Dawn modifies:

  1. Recombination history: σ-shift of z_rec via Δm = m_n - m_p ∝ σ.
  2. Spin temperature coupling: Lyα flux from first stars depends on
     σ-modified atomic transition rates.
  3. X-ray heating: σ-modified cross-sections.

A parametric model captures the leading effect through a single dimensionless
"σ-amplification factor" K_σ such that:

  δT_b^GSC(z) = δT_b^LCDM(z) × (1 + K_σ × Δσ/σ(z))

where Δσ/σ(z) = 1 - σ(z)/σ_today is the cumulative σ-evolution.

The ΛCDM baseline profile is taken from the standard adiabatic-cooling
formula at the registered z grid.

Usage:
    python3 scripts/predictions_compute_P2.py
    python3 scripts/predictions_compute_P2.py --K-sigma 50 --p 0.001
    python3 scripts/predictions_compute_P2.py --output predictions_register/P2_21cm_cosmic_dawn/pipeline_output.json

Output schema: predictions_p2_pipeline_output_v1.

Status: parametric leading-order. The proper computation requires a
gsc/cosmic_dawn/ module (recombination, spin-temperature evolution, Lyα
coupling, X-ray heating) which is gating work for the M202 milestone
(estimated 2–3 months). The current K_σ amplification is a shorthand
for the cumulative effect of all these σ-modifications.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_REDSHIFTS = (15.0, 16.0, 17.0, 18.0, 19.0, 20.0, 22.0, 25.0)

DEFAULTS = {
    "K_sigma": 50.0,             # parametric σ-amplification factor (dimensionless)
    "p_powerlaw": 0.001,
    "T_cmb_today_K": 2.7255,
    "Omega_b_h2": 0.02237,
    "Omega_m_h2": 0.1430,
}

# EDGES 2018 reported absorption (controversial but unexplained):
EDGES_DEPTH_MK = -500.0
EDGES_DEPTH_SIGMA_MK = 80.0
EDGES_Z_CENTRE = 17.2

# Standard adiabatic-cooling ΛCDM expectation at z ≈ 17:
LCDM_ADIABATIC_DEPTH_AT_Z17_MK = -200.0


def sigma_evolution(z: float, p: float) -> float:
    if z < 0.0:
        raise ValueError("z must be non-negative")
    return (1.0 + z) ** (-p)


def lcdm_21cm_depth_mk(z: float) -> float:
    """Standard adiabatic-cooling ΛCDM 21cm depth at redshift z.

    A simplified parametrization that matches the canonical ~-200 mK at
    z ≈ 17 with a roughly Gaussian profile in z.

    Width chosen to be consistent with the standard cosmic-dawn calculation;
    full implementation in M202 will replace this with the proper spin-
    temperature evolution.
    """
    sigma_z = 3.0  # Gaussian width in redshift
    return LCDM_ADIABATIC_DEPTH_AT_Z17_MK * math.exp(
        -((z - 17.0) ** 2) / (2.0 * sigma_z ** 2)
    )


def gsc_21cm_depth_mk(*, z: float, K_sigma: float, p: float) -> float:
    """GSC 21cm depth: ΛCDM × (1 + K_σ × Δσ/σ)."""
    sigma_ratio = sigma_evolution(z, p)
    delta_sigma_over_sigma = 1.0 - sigma_ratio  # > 0 for σ shrinking
    amplification = 1.0 + K_sigma * delta_sigma_over_sigma
    return lcdm_21cm_depth_mk(z) * amplification


def compute_profile(
    *, K_sigma: float, p: float, redshifts: tuple
) -> list:
    """Compute (z, δT_b^LCDM, δT_b^GSC, diff) at each registered z."""
    rows = []
    for z in redshifts:
        lcdm = lcdm_21cm_depth_mk(z)
        gsc = gsc_21cm_depth_mk(z=z, K_sigma=K_sigma, p=p)
        rows.append(
            {
                "z": float(z),
                "frequency_MHz": round(1420.405751768 / (1.0 + z), 4),
                "delta_T_b_lcdm_mK": round(lcdm, 4),
                "delta_T_b_gsc_mK": round(gsc, 4),
                "delta_T_b_diff_mK": round(gsc - lcdm, 4),
            }
        )
    return rows


def compute_edges_consistency(rows: list) -> dict:
    """Compare GSC prediction at z ≈ 17.2 to EDGES 2018 reported depth."""
    closest = min(rows, key=lambda r: abs(r["z"] - EDGES_Z_CENTRE))
    gsc_at_edges = closest["delta_T_b_gsc_mK"]
    diff_vs_edges = gsc_at_edges - EDGES_DEPTH_MK
    z_score = diff_vs_edges / EDGES_DEPTH_SIGMA_MK
    return {
        "edges_z_centre": EDGES_Z_CENTRE,
        "edges_depth_mk": EDGES_DEPTH_MK,
        "edges_depth_sigma_mk": EDGES_DEPTH_SIGMA_MK,
        "edges_caveat": (
            "EDGES 2018 absorption profile is reported but the cosmological "
            "interpretation remains controversial (foreground systematics "
            "challenged by SARAS3). Comparison is illustrative."
        ),
        "closest_evaluated_z": closest["z"],
        "gsc_predicted_depth_mk": gsc_at_edges,
        "lcdm_baseline_depth_mk": closest["delta_T_b_lcdm_mK"],
        "predicted_minus_edges_mk": round(diff_vs_edges, 4),
        "z_score_vs_edges": round(z_score, 4),
        "consistent_with_edges_at_2sigma": abs(z_score) < 2.0,
    }


def make_record(*, K_sigma: float, p: float, redshifts: tuple) -> dict:
    rows = compute_profile(K_sigma=K_sigma, p=p, redshifts=redshifts)
    edges = compute_edges_consistency(rows)

    return {
        "schema": "predictions_p2_pipeline_output_v1",
        "prediction_id": "P2",
        "title": "21cm Cosmic-Dawn signal in scale-covariant cosmology",
        "tier": "T2/T3",
        "tool": "predictions_compute_P2",
        "tool_version": "v0.1-parametric-amplification",
        "physics_status": (
            "Parametric K_σ amplification shorthand for σ-modified recombination, "
            "spin-temperature coupling, and X-ray heating. Full computation "
            "requires gsc/cosmic_dawn/ module (M202 milestone, ~2-3 months). "
            "The ΛCDM baseline profile is a simplified Gaussian; M202 will "
            "replace it with proper spin-temperature evolution."
        ),
        "ansatz": "powerlaw",
        "ansatz_parameters": {"p": p},
        "registered_couplings": {
            "K_sigma_amplification": float(K_sigma),
        },
        "cosmology_inputs": {
            "Omega_b_h2": DEFAULTS["Omega_b_h2"],
            "Omega_m_h2": DEFAULTS["Omega_m_h2"],
            "T_cmb_today_K": DEFAULTS["T_cmb_today_K"],
        },
        "profile": rows,
        "consistency_with_edges_2018": edges,
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
        "--K-sigma",
        type=float,
        default=DEFAULTS["K_sigma"],
        help="σ-amplification factor (parametric, default 50)",
    )
    parser.add_argument(
        "--p",
        type=float,
        default=DEFAULTS["p_powerlaw"],
        help="powerlaw σ(z) ∝ (1+z)^(-p) exponent (default 0.001)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT
        / "predictions_register"
        / "P2_21cm_cosmic_dawn"
        / "pipeline_output.json",
    )
    parser.add_argument("--print", action="store_true")
    args = parser.parse_args(argv)

    record = make_record(
        K_sigma=args.K_sigma, p=args.p, redshifts=DEFAULT_REDSHIFTS
    )
    if args.print:
        sys.stdout.write(json.dumps(record, indent=2, sort_keys=True) + "\n")
    write_output(record, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())

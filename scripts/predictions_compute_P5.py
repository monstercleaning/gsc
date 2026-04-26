#!/usr/bin/env python3
"""
predictions_compute_P5.py — compute Prediction P5 (strong-CP θ-bound consistency).

Computes the GSC-predicted cosmological evolution of the effective QCD theta
angle θ_eff(z) under σ-relaxation (Section 4 of GSC_Framework.md), and
verifies consistency with current nEDM bounds.

Physics:

Under the σ-axion equivalence proposal (Section 4), the σ-F̃F coupling drives
θ_eff to an attractor at θ_eff = 0. Parametrise the cosmological trajectory:

    θ_eff(z) = θ_eff(0) + (g_θ / f_σ) × (σ(z) - σ(0)) / σ(0)
            = θ_eff(0) + (g_θ / f_σ) × ((1+z)^(-p) - 1)            [powerlaw]

At z=0, θ_eff equals the bare attractor offset (must be small to satisfy
nEDM bound). At higher z, σ was different, so θ_eff was different.

Test against nEDM (n2EDM 2024): |d_n| < 1.8 × 10^-26 e·cm
                                ⇒ |θ_eff(z=0)| < 10^-10

Test against quasar absorption isospin (e.g., Mn II, Fe II line ratios at z~2):
sensitive to |Δθ_eff(z=2) - θ_eff(0)| < ~10^-5 (very rough order-of-magnitude
sensitivity; actual bounds depend on assumed isospin structure).

Usage:
    python3 scripts/predictions_compute_P5.py
    python3 scripts/predictions_compute_P5.py --theta-z0 5e-11 --g-theta-over-f 0.01
    python3 scripts/predictions_compute_P5.py --output predictions_register/P5_strong_cp_bound/pipeline_output.json

Output schema: predictions_p5_pipeline_output_v1.

Status: parametrized trajectory in θ_eff(z). The σ-θ coupling parameter
g_θ/f_σ is a free parameter pending the FRG calculation in Paper B (joint with P4).
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


# Current nEDM bound: |d_n| < 1.8e-26 e·cm at 90% CL (n2EDM 2024).
# This translates approximately to |θ_eff(z=0)| < ~10^-10.
NEDM_THETA_BOUND = 1e-10
NEDM_THETA_REFERENCE = "n2EDM 2024 (|d_n| < 1.8e-26 e·cm at 90% CL)"

DEFAULT_REDSHIFTS = (0.1, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0, 100.0, 1100.0)

DEFAULTS = {
    # current θ_eff(z=0), set well within current n2EDM bound 1e-10
    "theta_eff_z0": 5e-11,
    # Literature-grounded σ-θ coupling. Same FRG mechanism as g_CS in P4:
    # the gravitational fixed point induces an anomalous dimension on the
    # dimension-4 topological term. Naive estimate: g_θ/f_σ ≈ G_*/(4π M_Planck)
    # times an O(1) factor from the topological-operator matrix element.
    # Adopting the same characteristic combination G_* × η ≈ 0.45,
    # and converting to dimensionless g_θ/f_σ ≈ 0.45/(4π) ≈ 0.036 in
    # σ(0)=1 units. Plausible range [0.005, 0.2].
    "g_theta_over_f_sigma": 0.036,
    "p_powerlaw": 0.001,
}


def sigma_evolution(z: float, p: float) -> float:
    """σ(z)/σ(0) for powerlaw ansatz."""
    if z < 0.0:
        raise ValueError("z must be non-negative")
    return (1.0 + z) ** (-p)


def theta_eff_trajectory(
    *, z: float, theta_z0: float, g_theta_over_f: float, p: float
) -> float:
    """θ_eff(z) for the powerlaw σ-evolution and registered coupling."""
    delta_sigma = sigma_evolution(z, p) - 1.0
    return theta_z0 + g_theta_over_f * delta_sigma


def compute_trajectory(
    *,
    theta_z0: float,
    g_theta_over_f: float,
    p: float,
    redshifts: tuple,
) -> list:
    """Compute θ_eff at each redshift in the grid."""
    rows = []
    for z in redshifts:
        theta = theta_eff_trajectory(
            z=z, theta_z0=theta_z0, g_theta_over_f=g_theta_over_f, p=p
        )
        rows.append(
            {
                "z": float(z),
                "sigma_over_sigma0": round(sigma_evolution(z, p), 9),
                "theta_eff": float(f"{theta:.3e}"),
                "delta_theta_vs_z0": float(f"{(theta - theta_z0):.3e}"),
            }
        )
    return rows


def compute_nedm_consistency(theta_z0: float) -> dict:
    """Verify the registered θ_eff(z=0) is within current nEDM bound."""
    abs_theta = abs(theta_z0)
    fraction_of_bound = abs_theta / NEDM_THETA_BOUND
    return {
        "nedm_bound_reference": NEDM_THETA_REFERENCE,
        "nedm_theta_bound_abs": NEDM_THETA_BOUND,
        "registered_abs_theta_z0": float(f"{abs_theta:.3e}"),
        "fraction_of_current_bound": round(fraction_of_bound, 6),
        "consistent_with_nedm": abs_theta < NEDM_THETA_BOUND,
    }


def compute_quasar_consistency(
    *, theta_z0: float, g_theta_over_f: float, p: float
) -> dict:
    """Order-of-magnitude consistency with quasar absorption isospin bounds.

    Assumes a sensitivity floor of |Δθ_eff(z=2)| < 10^-5 from absorption-line
    isospin-breaking spectroscopy. The actual bound is much more nuanced and
    depends on assumed nuclear physics; this is a rough first-pass.
    """
    QUASAR_DELTA_THETA_FLOOR = 1e-5  # order-of-magnitude rough bound at z~2
    delta_theta_at_z2 = abs(
        theta_eff_trajectory(
            z=2.0, theta_z0=theta_z0, g_theta_over_f=g_theta_over_f, p=p
        )
        - theta_z0
    )
    return {
        "quasar_z_probe": 2.0,
        "rough_quasar_bound_abs_delta_theta": QUASAR_DELTA_THETA_FLOOR,
        "predicted_abs_delta_theta_at_z2": float(f"{delta_theta_at_z2:.3e}"),
        "consistent_with_quasar_rough": (
            delta_theta_at_z2 < QUASAR_DELTA_THETA_FLOOR
        ),
        "quasar_caveat": (
            "Order-of-magnitude only. Actual quasar bounds on θ-evolution "
            "depend on assumed isospin structure and require a full nuclear-"
            "physics interpretation; this comparison is illustrative."
        ),
    }


def make_record(
    *,
    theta_z0: float,
    g_theta_over_f: float,
    p: float,
    redshifts: tuple,
) -> dict:
    rows = compute_trajectory(
        theta_z0=theta_z0,
        g_theta_over_f=g_theta_over_f,
        p=p,
        redshifts=redshifts,
    )
    nedm = compute_nedm_consistency(theta_z0)
    quasar = compute_quasar_consistency(
        theta_z0=theta_z0, g_theta_over_f=g_theta_over_f, p=p
    )

    return {
        "schema": "predictions_p5_pipeline_output_v1",
        "prediction_id": "P5",
        "title": "Strong-CP θ-bound consistency with σ-axion-equivalence",
        "tier": "T3",
        "tool": "predictions_compute_P5",
        "tool_version": "v0.1-parametrized-trajectory",
        "physics_status": (
            "Parametrized trajectory θ_eff(z) under σ-relaxation. The coupling "
            "g_θ/f_σ is a free parameter; the FRG calculation in Paper B (joint "
            "with P4) is gating piece for narrowing it to a derived value."
        ),
        "ansatz": "powerlaw",
        "ansatz_parameters": {"p": p},
        "registered_couplings": {
            "theta_eff_z0": float(f"{theta_z0:.3e}"),
            "g_theta_over_f_sigma": float(f"{g_theta_over_f:.3e}"),
        },
        "trajectory": rows,
        "consistency_with_nedm": nedm,
        "consistency_with_quasar_rough": quasar,
        "joint_consistency_with_P4": {
            "note": (
                "P4 (CMB birefringence) and P5 (strong-CP θ-bound) probe the "
                "same σ-F̃F coupling. Joint consistency requires that the "
                "g_CS amplitude in P4 and the g_θ/f_σ coupling here arise from "
                "the same FRG-derived f_σ. Cross-check is implemented in the "
                "M201 joint scoring layer."
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
        "--theta-z0",
        type=float,
        default=DEFAULTS["theta_eff_z0"],
        help="θ_eff(z=0); must be within nEDM bound (default 5e-11)",
    )
    parser.add_argument(
        "--g-theta-over-f",
        type=float,
        default=DEFAULTS["g_theta_over_f_sigma"],
        help="σ-θ coupling parameter g_θ/f_σ (default 0.01)",
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
        / "P5_strong_cp_bound"
        / "pipeline_output.json",
    )
    parser.add_argument("--print", action="store_true")
    args = parser.parse_args(argv)

    record = make_record(
        theta_z0=args.theta_z0,
        g_theta_over_f=args.g_theta_over_f,
        p=args.p,
        redshifts=DEFAULT_REDSHIFTS,
    )

    if args.print:
        sys.stdout.write(json.dumps(record, indent=2, sort_keys=True) + "\n")

    write_output(record, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())

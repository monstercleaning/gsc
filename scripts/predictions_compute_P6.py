#!/usr/bin/env python3
"""
predictions_compute_P6.py — compute Prediction P6 (Kibble-Zurek defect spectrum).

Computes the GSC-predicted topological-defect density and stochastic GW
spectrum from the σ_*-crossing as a continuous phase transition with
finite-rate quench (Section 5 of GSC_Framework.md).

Physics (parametric first pass):

The Kibble-Zurek scaling for defect density at the freeze-out of a
continuous phase transition with quench timescale τ_quench:

    n_defects ~ ξ_KZ^{-d} ~ τ_quench^{-d ν / (1 + ν z)}

where ν and z are the critical exponents of the gravitational FRG fixed
point at σ_* and d is the spatial dimension.

For cosmic strings (d=3 codimension 2), the linear mass density is
μ ~ M_*^2 where M_* is the σ_* energy scale. The stochastic GW background
from a string network has characteristic spectrum

    Ω_GW(f) ∝ G μ × p(f / f_*)

where f_* depends on string tension and network evolution.

Usage:
    python3 scripts/predictions_compute_P6.py
    python3 scripts/predictions_compute_P6.py --nu 0.5 --z-crit 1.0 --M-star-GeV 1e16
    python3 scripts/predictions_compute_P6.py --output predictions_register/P6_kz_defect_spectrum/pipeline_output.json

Output schema: predictions_p6_pipeline_output_v1.

Status: parametric KZ scaling. Critical exponents (ν, z) at the σ_*-crossing
fixed point are NOT YET COMPUTED — they are the gating piece for both this
prediction and Section 5 of GSC_Framework.md (the vortex-DM derivation).
The current pipeline records the parametric form and produces a band of
predictions over plausible (ν, z) values.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Frequency bands for stochastic GW background detection.
# Centre frequency in Hz, characteristic strain-amplitude (h_c) sensitivity.
GW_BAND_TARGETS = {
    "NANOGrav (15-yr)": {"f_centre_Hz": 1e-8, "h_c_sensitivity": 1e-15},
    "EPTA / IPTA": {"f_centre_Hz": 1e-8, "h_c_sensitivity": 5e-16},
    "LISA (~2035)": {"f_centre_Hz": 1e-3, "h_c_sensitivity": 1e-21},
    "Einstein Telescope": {"f_centre_Hz": 1e1, "h_c_sensitivity": 1e-24},
}

DEFAULTS = {
    "nu_critical_exponent": 0.5,    # PARAMETRIC; FRG calculation pending
    "z_dynamic_exponent": 1.0,      # PARAMETRIC; FRG calculation pending
    "M_star_GeV": 1e16,             # σ_* energy scale (parametric)
    "tau_quench_s": 1e-6,           # quench timescale at σ_*-crossing (parametric)
    "spatial_dimension": 3,
}


def kz_defect_density(
    *, nu: float, z_crit: float, tau_quench: float, d: int
) -> dict:
    """Compute KZ defect density per Hubble volume.

    n_defects ~ tau_quench^{-d ν / (1 + ν z)}

    Returns a dict with the scaling exponent and a normalised density ratio.
    """
    if 1.0 + nu * z_crit <= 0:
        raise ValueError("denominator (1 + ν z) must be positive")
    exponent = -d * nu / (1.0 + nu * z_crit)
    # Normalise relative to a reference τ = 1 s; the absolute density requires
    # the FRG-derived prefactor (gating piece).
    density_ratio = tau_quench ** exponent
    return {
        "scaling_exponent_minus_d_nu_over_1_plus_nu_z": round(exponent, 6),
        "density_ratio_to_unit_tau": float(f"{density_ratio:.3e}"),
        "tau_quench_s": float(tau_quench),
    }


def gw_background_spectrum(
    *, M_star_GeV: float, density_relative: float
) -> dict:
    """Compute predicted stochastic GW background amplitude per band.

    Order-of-magnitude estimate:
      G μ ~ (M_*/M_Planck)^2
      Ω_GW ~ G μ × density_relative

    Where density_relative is set to 1 for "current" GSC and scales with
    the KZ defect density.
    """
    M_PLANCK_GeV = 1.22e19
    G_mu = (M_star_GeV / M_PLANCK_GeV) ** 2
    Omega_GW_typical = G_mu * density_relative
    # Convert Ω_GW to characteristic strain h_c at a representative frequency
    # h_c^2 ~ Ω_GW (very rough)
    h_c_estimate = Omega_GW_typical ** 0.5

    band_predictions = {}
    for label, target in sorted(GW_BAND_TARGETS.items()):
        snr = h_c_estimate / target["h_c_sensitivity"]
        band_predictions[label] = {
            "f_centre_Hz": target["f_centre_Hz"],
            "experiment_h_c_sensitivity": target["h_c_sensitivity"],
            "predicted_h_c_estimate": float(f"{h_c_estimate:.3e}"),
            "snr_estimate": float(f"{snr:.3e}"),
            "detectable_at_3sigma": snr > 3.0,
        }

    return {
        "G_mu_dimensionless": float(f"{G_mu:.3e}"),
        "M_star_GeV": float(f"{M_star_GeV:.3e}"),
        "Omega_GW_typical": float(f"{Omega_GW_typical:.3e}"),
        "h_c_estimate": float(f"{h_c_estimate:.3e}"),
        "band_predictions": band_predictions,
    }


def make_record(
    *,
    nu: float,
    z_crit: float,
    tau_quench: float,
    M_star_GeV: float,
    d: int,
) -> dict:
    kz = kz_defect_density(nu=nu, z_crit=z_crit, tau_quench=tau_quench, d=d)
    gw = gw_background_spectrum(
        M_star_GeV=M_star_GeV,
        density_relative=kz["density_ratio_to_unit_tau"],
    )

    return {
        "schema": "predictions_p6_pipeline_output_v1",
        "prediction_id": "P6",
        "title": "Kibble–Zurek defect spectrum from σ_*-crossing",
        "tier": "T4",
        "tool": "predictions_compute_P6",
        "tool_version": "v0.1-parametric-KZ",
        "physics_status": (
            "Parametric Kibble-Zurek scaling. The critical exponents (ν, z) at "
            "the σ_*-crossing FRG fixed point are NOT YET COMPUTED — gating "
            "piece for this prediction and Section 5 of GSC_Framework.md "
            "(vortex-DM derivation). Plausible-range bracketed defaults are "
            "used; FRG calculation will narrow to a derived value."
        ),
        "registered_parameters": {
            "nu_critical_exponent": float(nu),
            "z_dynamic_exponent": float(z_crit),
            "tau_quench_s": float(tau_quench),
            "M_star_GeV": float(f"{M_star_GeV:.3e}"),
            "spatial_dimension": int(d),
        },
        "kz_defect_density": kz,
        "gw_background_prediction": gw,
        "joint_consistency_with_C1_vortex_dm": {
            "note": (
                "P6 (KZ defect spectrum) and Section 5 of GSC_Framework.md "
                "(vortex DM derivation) probe the same underlying physics. "
                "Joint consistency requires that the KZ-derived defect density "
                "matches the dark-matter abundance Ω_DM ≈ 0.265. This cross-"
                "check is implemented in the M201+ joint scoring layer once "
                "FRG critical exponents are available."
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
        "--nu",
        type=float,
        default=DEFAULTS["nu_critical_exponent"],
        help="critical exponent ν (parametric, default 0.5)",
    )
    parser.add_argument(
        "--z-crit",
        type=float,
        default=DEFAULTS["z_dynamic_exponent"],
        help="dynamic critical exponent z (parametric, default 1.0)",
    )
    parser.add_argument(
        "--tau-quench",
        type=float,
        default=DEFAULTS["tau_quench_s"],
        help="quench timescale at σ_*-crossing in seconds (default 1e-6)",
    )
    parser.add_argument(
        "--M-star-GeV",
        type=float,
        default=DEFAULTS["M_star_GeV"],
        help="σ_* energy scale in GeV (default 1e16)",
    )
    parser.add_argument(
        "--d",
        type=int,
        default=DEFAULTS["spatial_dimension"],
        help="spatial dimension (default 3)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT
        / "predictions_register"
        / "P6_kz_defect_spectrum"
        / "pipeline_output.json",
    )
    parser.add_argument("--print", action="store_true")
    args = parser.parse_args(argv)

    record = make_record(
        nu=args.nu,
        z_crit=args.z_crit,
        tau_quench=args.tau_quench,
        M_star_GeV=args.M_star_GeV,
        d=args.d,
    )
    if args.print:
        sys.stdout.write(json.dumps(record, indent=2, sort_keys=True) + "\n")
    write_output(record, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())

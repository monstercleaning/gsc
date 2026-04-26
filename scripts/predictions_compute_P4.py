#!/usr/bin/env python3
"""
predictions_compute_P4.py — compute Prediction P4 (CMB cosmic birefringence).

Computes the GSC-predicted CMB cosmic-birefringence rotation angle β arising
from the σ-F̃F coupling derived in Section 4 of GSC_Framework.md.

The angle is the line-of-sight integral

    β = (1/2) ∫_0^{z_CMB} (Δσ(z) / f_σ) (dt/dz) dz

where Δσ(z) = σ(0) - σ(z) is the cumulative σ-evolution between recombination
and today, and f_σ is the σ-F̃F coupling scale (set by FRG; parametric here).

Compared with Planck 2020 hint (Minami & Komatsu): β ≈ 0.35° ± 0.14°.
Tested by LiteBIRD ≈ 2030 with target precision ~0.05°.

Usage:
    python3 scripts/predictions_compute_P4.py
    python3 scripts/predictions_compute_P4.py --p 0.001 --f-sigma-amplitude 0.5
    python3 scripts/predictions_compute_P4.py --output predictions_register/P4_cmb_birefringence/pipeline_output.json

Output schema: predictions_p4_pipeline_output_v1.

Status: leading-order σ-Chern-Simons coupling. The proportionality
constant f_σ is the gating piece (FRG calculation, Paper B). For pre-registration,
we parametrize as a dimensionless σ-Chern-Simons amplitude g_CS such that

    β [rad] ≈ g_CS × ⟨Δσ/σ⟩_{0 → z_CMB}

with ⟨...⟩ a redshift-weighted average. g_CS = 1 corresponds to a maximally-strong
σ-photon Chern-Simons coupling; realistic values from FRG estimates fall in
g_CS ∈ [10^-3, 10^-1].
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gsc.measurement_model import (  # noqa: E402
    FlatLambdaCDMHistory,
    H0_to_SI,
    integrate_trapezoid,
)


DEFAULTS = {
    "H0_km_s_Mpc": 67.4,
    "Omega_m": 0.315,
    "Omega_L": 0.685,
    "z_CMB": 1100.0,
    "p_powerlaw": 0.001,
    # Literature-grounded estimate for the σ-Chern-Simons amplitude.
    # g_CS ≈ G_* × η_F̃F / (4π) where:
    #   G_*  ≈ 1.5  — Reuter-Saueressig FRG fixed-point value for the dimensionless
    #                 gravitational coupling at the NGFP (Einstein-Hilbert truncation;
    #                 see Reuter & Saueressig 2002, Phys. Rev. D 65, 065016).
    #   η_F̃F ≈ 0.3 — gravity-induced anomalous dimension on dimension-4 matter
    #                 operators at the gravitational NGFP, characteristic value
    #                 from Eichhorn-style matter-coupled FRG analyses
    #                 (e.g. Eichhorn & Versteegen, JHEP 08, 147 (2018)).
    # Numerical value: g_CS ≈ 1.5 × 0.3 / (4π) ≈ 0.036.
    # Range over plausible (G_*, η_F̃F) is g_CS ∈ [0.005, 0.2].
    "g_CS": 0.036,
    "n_steps": 5000,
}

PLANCK_BIREFRINGENCE_HINT_DEG = 0.35
PLANCK_BIREFRINGENCE_HINT_SIGMA_DEG = 0.14


def sigma_evolution(z: float, *, ansatz: str, params: dict) -> float:
    """Return σ(z) / σ(0) for the registered ansatz.

    Parallel of `sigma_ratio_at_z` in predictions_compute_P1.py but inverted
    convention: returns σ(z)/σ(0), so for shrinking-atoms σ(z) > σ(0) at z > 0
    means atoms were larger in the past.
    """
    if z < 0.0:
        raise ValueError("z must be non-negative")

    if ansatz == "powerlaw":
        p = float(params.get("p", DEFAULTS["p_powerlaw"]))
        # σ(z) ∝ (1+z)^(-p)  ⇒  σ(z)/σ(0) = (1+z)^(-p)
        return (1.0 + z) ** (-p)

    if ansatz == "transition":
        p_low = float(params.get("p_low", 0.001))
        p_high = float(params.get("p_high", 0.005))
        z_t = float(params.get("z_t", 1.0))
        dz = max(float(params.get("dz", 0.5)), 1e-3)
        w = 0.5 * (1.0 + math.tanh((z - z_t) / dz))
        p_eff = (1.0 - w) * p_low + w * p_high
        return (1.0 + z) ** (-p_eff)

    raise ValueError(f"Unknown ansatz: {ansatz!r}")


def compute_birefringence_integral(
    *,
    ansatz: str,
    params: dict,
    g_CS: float,
    z_CMB: float,
    history: FlatLambdaCDMHistory,
    H0_si: float,
    n_steps: int,
) -> dict:
    """Compute the line-of-sight birefringence integral.

    Returns the predicted β in radians and degrees, plus diagnostic intermediates.

    The integrand is

        f(z) = (Δσ(z) / σ(0)) × (1/(1+z)) × (1/H(z))    [units of time]

    integrated and multiplied by g_CS to give a dimensionless rotation, then
    converted to a small angle in radians.
    """
    def integrand(z: float) -> float:
        # Δσ(z)/σ(0) = 1 - σ(z)/σ(0)
        sigma_ratio = sigma_evolution(z, ansatz=ansatz, params=params)
        delta_sigma_over_sigma0 = 1.0 - sigma_ratio
        H_z = history.H(z)
        if H_z <= 0:
            raise ValueError(f"non-positive H(z={z}): {H_z}")
        return delta_sigma_over_sigma0 / ((1.0 + z) * H_z)

    integral = integrate_trapezoid(integrand, 0.0, z_CMB, n=n_steps)
    # Multiply by H0 to make the integral dimensionless
    # (it has units 1/H0 from the 1/H(z) factor).
    # The integration is in z so the result has units of time (1/H).
    # Multiply by H0 to dimensionless.
    integral_dimless = integral * H0_si
    beta_rad = g_CS * integral_dimless
    beta_deg = beta_rad * (180.0 / math.pi)

    return {
        "beta_rad": round(beta_rad, 9),
        "beta_deg": round(beta_deg, 6),
        "integral_dimensionless": round(integral_dimless, 9),
        "g_CS": round(g_CS, 9),
        "z_CMB": float(z_CMB),
    }


def compute_consistency_with_planck(beta_deg_predicted: float) -> dict:
    """Compare predicted β to Planck 2020 hint."""
    diff = beta_deg_predicted - PLANCK_BIREFRINGENCE_HINT_DEG
    z_score = diff / PLANCK_BIREFRINGENCE_HINT_SIGMA_DEG
    return {
        "planck_hint_deg": PLANCK_BIREFRINGENCE_HINT_DEG,
        "planck_hint_sigma_deg": PLANCK_BIREFRINGENCE_HINT_SIGMA_DEG,
        "predicted_minus_observed_deg": round(diff, 6),
        "z_score_vs_planck_hint": round(z_score, 4),
        "consistent_with_planck_at_2sigma": abs(z_score) < 2.0,
    }


def make_record(
    *,
    ansatz: str,
    params: dict,
    g_CS: float,
    H0_km_s_Mpc: float,
    Omega_m: float,
    Omega_L: float,
    z_CMB: float,
    n_steps: int,
) -> dict:
    H0_si = H0_to_SI(H0_km_s_Mpc)
    history = FlatLambdaCDMHistory(
        H0=H0_si, Omega_m=Omega_m, Omega_Lambda=Omega_L
    )
    integral = compute_birefringence_integral(
        ansatz=ansatz,
        params=params,
        g_CS=g_CS,
        z_CMB=z_CMB,
        history=history,
        H0_si=H0_si,
        n_steps=n_steps,
    )
    consistency = compute_consistency_with_planck(integral["beta_deg"])

    return {
        "schema": "predictions_p4_pipeline_output_v1",
        "prediction_id": "P4",
        "title": "CMB cosmic birefringence from σ-F̃F coupling",
        "tier": "T3",
        "tool": "predictions_compute_P4",
        "tool_version": "v0.1-leading-order-CS",
        "physics_status": (
            "Leading-order line-of-sight Chern-Simons rotation. The g_CS amplitude "
            "is a parametric placeholder for the FRG-derived σ-F̃F coupling f_σ; "
            "Paper B FRG calculation is gating piece for narrowing g_CS to a "
            "specific predicted value."
        ),
        "ansatz": ansatz,
        "ansatz_parameters": dict(sorted(params.items())),
        "lcdm_baseline": {
            "H0_km_s_Mpc": H0_km_s_Mpc,
            "Omega_m": Omega_m,
            "Omega_L": Omega_L,
        },
        "n_integration_steps": n_steps,
        "prediction": integral,
        "consistency_with_planck_2020_hint": consistency,
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
        "--ansatz", choices=("powerlaw", "transition"), default="powerlaw"
    )
    parser.add_argument("--p", type=float, default=DEFAULTS["p_powerlaw"])
    parser.add_argument(
        "--g-CS",
        type=float,
        default=DEFAULTS["g_CS"],
        help="dimensionless σ-Chern-Simons amplitude (parametric until FRG calc lands)",
    )
    parser.add_argument("--H0", type=float, default=DEFAULTS["H0_km_s_Mpc"], dest="H0")
    parser.add_argument("--Omega-m", type=float, default=DEFAULTS["Omega_m"])
    parser.add_argument("--Omega-L", type=float, default=DEFAULTS["Omega_L"])
    parser.add_argument("--z-CMB", type=float, default=DEFAULTS["z_CMB"])
    parser.add_argument("--n-steps", type=int, default=DEFAULTS["n_steps"])
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT
        / "predictions_register"
        / "P4_cmb_birefringence"
        / "pipeline_output.json",
    )
    parser.add_argument("--print", action="store_true")
    args = parser.parse_args(argv)

    if args.ansatz == "powerlaw":
        params = {"p": args.p}
    else:
        params = {
            "p_low": args.p,
            "p_high": args.p * 5.0,
            "z_t": 1.0,
            "dz": 0.5,
        }

    record = make_record(
        ansatz=args.ansatz,
        params=params,
        g_CS=args.g_CS,
        H0_km_s_Mpc=args.H0,
        Omega_m=args.Omega_m,
        Omega_L=args.Omega_L,
        z_CMB=args.z_CMB,
        n_steps=args.n_steps,
    )

    if args.print:
        sys.stdout.write(json.dumps(record, indent=2, sort_keys=True) + "\n")

    write_output(record, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())

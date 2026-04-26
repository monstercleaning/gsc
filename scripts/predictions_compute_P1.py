#!/usr/bin/env python3
"""
predictions_compute_P1.py — compute Prediction P1 (BAO standard-ruler shift).

Computes the GSC-predicted BAO sound-horizon scale r_s and its relative shift
versus the ΛCDM baseline, for a registered σ(t) ansatz.

Usage:
    python3 scripts/predictions_compute_P1.py
    python3 scripts/predictions_compute_P1.py --ansatz powerlaw --sigma-shift-amplitude 0.005
    python3 scripts/predictions_compute_P1.py --output predictions_register/P1_bao_ruler_shift/pipeline_output.json

Status: FIRST-PASS PIPELINE. Uses Eisenstein–Hu 1998 fitting formula for the
ΛCDM baseline and a parametrized σ-shift factor for the GSC modification.

Physics caveat: the σ-shift factor encodes the cumulative effect of GSC's
σ-evolution between recombination and today as observed in today's atomic units.
The first-pass parametrization is sigma_shift_amplitude * f_ansatz(z); a complete
derivation from σ(t) and the σ-modified recombination history is gating work
for v12-cycle M201. Until that derivation lands, this script produces a
parameter-band prediction, NOT a single deterministic point. Pre-registration
should record the band and the derivation status explicitly.

Output format: see schemas/predictions_p1_pipeline_output_v1.schema.json (TBD).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Import existing GSC machinery for the ΛCDM baseline.
from gsc.early_time.rd import (  # noqa: E402
    z_drag_eisenstein_hu,
    omega_r_h2,
    omega_gamma_h2_from_Tcmb,
)


# ---------------------------------------------------------------------------
# Defaults — Planck 2018 best-fit ΛCDM (Aghanim et al. 2020)
# ---------------------------------------------------------------------------
DEFAULTS = {
    "omega_m_h2": 0.1430,   # Planck 2018 TT,TE,EE+lowE+lensing
    "omega_b_h2": 0.02237,  # Planck 2018
    "h": 0.6736,            # Planck 2018
    "Tcmb_K": 2.7255,       # COBE/FIRAS
    "N_eff": 3.046,
}


def rd_eisenstein_hu_1998_mpc(
    *,
    omega_m_h2: float,
    omega_b_h2: float,
    Tcmb_K: float = 2.7255,
    N_eff: float = 3.046,
) -> float:
    """Compute the BAO sound-horizon r_d at the drag epoch via Eisenstein–Hu (1998).

    Returns r_d in Mpc. Uses the standard fitting formula adopted in the
    GSC late-time pipeline.
    """
    z_d = z_drag_eisenstein_hu(omega_m_h2=omega_m_h2, omega_b_h2=omega_b_h2)

    # Effective sound speed integral via the EH98 closed form.
    # See gsc/early_time/rd.py for the full form; here we re-implement
    # the canonical EH98 expression directly to avoid relying on internal helpers.
    omega_g_h2 = omega_gamma_h2_from_Tcmb(Tcmb_K)
    omega_r_h2_val = omega_r_h2(Tcmb_K=Tcmb_K, N_eff=N_eff)

    # z_eq: matter-radiation equality
    z_eq = 2.5e4 * omega_m_h2 * (Tcmb_K / 2.7) ** -4

    # k_eq in Mpc^{-1}
    k_eq = 7.46e-2 * omega_m_h2 * (Tcmb_K / 2.7) ** -2

    # R: baryon-to-photon momentum density ratio
    def R(z: float) -> float:
        return 31.5 * omega_b_h2 * (Tcmb_K / 2.7) ** -4 * (1000.0 / z)

    R_eq = R(z_eq)
    R_d = R(z_d)

    # Sound-horizon at drag epoch (EH98 eq. 6)
    rd_mpc = (
        (2.0 / (3.0 * k_eq))
        * math.sqrt(6.0 / R_eq)
        * math.log(
            (math.sqrt(1.0 + R_d) + math.sqrt(R_d + R_eq))
            / (1.0 + math.sqrt(R_eq))
        )
    )
    return rd_mpc


def sigma_ratio_at_z(z: float, ansatz: str, params: dict) -> float:
    """Return σ(z=0) / σ(z), the freeze-frame metrology ratio.

    Under universal coherent scaling, a physical length at redshift z measured
    in today's atomic units differs from its measurement in atoms-of-the-time
    by exactly this ratio. By construction, sigma_ratio_at_z(0) == 1.

    Ansatz catalogue:

    * "powerlaw" — σ(z) ∝ (1+z)^p; ratio = (1+z)^(-p).
      Required params: {"p": float}. p > 0 for atoms larger in past.
    * "transition" — smooth interpolation between two power-law regimes around
      a transition redshift z_t with width Δz.
      Required params: {"p_low": float, "p_high": float, "z_t": float, "dz": float}.
    * "rg_profile" — σ(z) numerically integrated from a G(σ) RG ansatz.
      For now uses a Padé-fit-like approximation; full integration pending the
      RG flow table (gsc/rg/) integration.
      Required params: {"p_eff": float, "sigma_star_z": float, "alpha": float}.
    """
    z = float(z)
    if z < 0.0:
        raise ValueError("z must be non-negative")

    if ansatz == "powerlaw":
        p = float(params.get("p", 0.001))
        return (1.0 + z) ** (-p)

    if ansatz == "transition":
        p_low = float(params.get("p_low", 0.001))
        p_high = float(params.get("p_high", 0.005))
        z_t = float(params.get("z_t", 1.0))
        dz = max(float(params.get("dz", 0.5)), 1e-3)
        # Smooth transition via tanh interpolation in p.
        w = 0.5 * (1.0 + math.tanh((z - z_t) / dz))
        p_eff = (1.0 - w) * p_low + w * p_high
        return (1.0 + z) ** (-p_eff)

    if ansatz == "rg_profile":
        p_eff = float(params.get("p_eff", 0.001))
        sigma_star_z = float(params.get("sigma_star_z", 1e6))  # arbitrary high-z scale
        alpha = float(params.get("alpha", 0.5))
        # Padé-like approximation: deviates from powerlaw near sigma_star_z
        # to mimic RG enhancement at high z. Honest first-pass; full RG flow
        # table integration is gating piece (gsc/rg/).
        base = (1.0 + z) ** (-p_eff)
        rg_correction = 1.0 / (1.0 + alpha * (z / sigma_star_z) ** 2)
        return base * rg_correction

    raise ValueError(f"Unknown ansatz: {ansatz!r}")


def gsc_bao_metrology_shift(
    *, ansatz: str, params: dict, z_drag: float
) -> float:
    """Return the multiplicative factor f such that r_d_GSC = f * r_d_LCDM.

    Physics: in the freeze-frame, the BAO sound horizon at the drag epoch is
    a physical length r_d_phys (the same in any frame). When we observe it
    today, we measure it against today's atomic units, which differ from
    drag-epoch atomic units by σ(z=0)/σ(z_drag). Therefore:

        r_d_GSC_observed (in today-Mpc) = r_d_phys × σ(z_drag) / σ(z=0)
                                        = r_d_phys / sigma_ratio_at_z(z_drag)

    Since the ΛCDM EH98 r_d is computed assuming no σ-evolution
    (effectively σ_drag == σ_today), we have r_d_LCDM == r_d_phys to leading
    order, and so:

        r_d_GSC = r_d_LCDM / sigma_ratio_at_z(z_drag)

    The factor returned is therefore 1 / σ(0)/σ(z_drag) = σ(z_drag)/σ(0).

    Caveat: this captures the leading freeze-frame metrology shift only.
    A complete prediction additionally requires σ-modified recombination
    physics (modified z_drag, modified c_s(z) inside the sound-horizon
    integral). Those corrections enter at second order in σ-evolution
    amplitude and are gating work for v12-cycle M201+.
    """
    sr = sigma_ratio_at_z(z_drag, ansatz=ansatz, params=params)
    if sr <= 0.0:
        raise ValueError(f"non-positive sigma ratio: {sr}")
    return 1.0 / sr


def compute_p1(
    *,
    ansatz: str,
    params: dict,
    omega_m_h2: float,
    omega_b_h2: float,
    h: float,
    Tcmb_K: float,
    N_eff: float,
) -> dict:
    """Compute P1 prediction record for a single ansatz/parameter set."""
    rd_lcdm_mpc = rd_eisenstein_hu_1998_mpc(
        omega_m_h2=omega_m_h2,
        omega_b_h2=omega_b_h2,
        Tcmb_K=Tcmb_K,
        N_eff=N_eff,
    )
    z_drag = z_drag_eisenstein_hu(omega_m_h2=omega_m_h2, omega_b_h2=omega_b_h2)
    sigma_ratio_today_to_drag = sigma_ratio_at_z(z_drag, ansatz=ansatz, params=params)
    shift_factor = gsc_bao_metrology_shift(
        ansatz=ansatz, params=params, z_drag=z_drag
    )
    rd_gsc_mpc = rd_lcdm_mpc * shift_factor
    delta_rs_relative = (rd_gsc_mpc - rd_lcdm_mpc) / rd_lcdm_mpc

    return {
        "ansatz": ansatz,
        "ansatz_parameters": dict(sorted(params.items())),
        "cosmology_inputs": {
            "omega_m_h2": omega_m_h2,
            "omega_b_h2": omega_b_h2,
            "h": h,
            "Tcmb_K": Tcmb_K,
            "N_eff": N_eff,
        },
        "z_drag": round(z_drag, 4),
        "sigma_ratio_today_over_drag": round(sigma_ratio_today_to_drag, 9),
        "r_s_lcdm_baseline_mpc": round(rd_lcdm_mpc, 6),
        "r_s_gsc_predicted_mpc": round(rd_gsc_mpc, 6),
        "delta_rs_relative": round(delta_rs_relative, 9),
        "shift_factor": round(shift_factor, 9),
        "physics_status": (
            "Includes leading freeze-frame metrology shift (σ(z=0)/σ(z_drag) ratio). "
            "Does NOT yet include second-order σ-modified recombination corrections "
            "(modified z_drag, modified c_s(z) inside the sound-horizon integral). "
            "These are gating work for v12-cycle M201+ and will narrow the prediction "
            "band."
        ),
    }


DEFAULT_ANSATZE = [
    {"ansatz": "powerlaw", "params": {"p": 0.001}},
    {
        "ansatz": "transition",
        "params": {"p_low": 0.001, "p_high": 0.005, "z_t": 1.0, "dz": 0.5},
    },
    {
        "ansatz": "rg_profile",
        "params": {"p_eff": 0.001, "sigma_star_z": 1e6, "alpha": 0.5},
    },
]


def make_record(
    *,
    ansatze: list[dict],
    omega_m_h2: float,
    omega_b_h2: float,
    h: float,
    Tcmb_K: float,
    N_eff: float,
) -> dict:
    """Build the full pipeline-output record with all registered sub-predictions."""
    sub_predictions = []
    for cfg in ansatze:
        sub_predictions.append(
            compute_p1(
                ansatz=cfg["ansatz"],
                params=cfg.get("params", {}),
                omega_m_h2=omega_m_h2,
                omega_b_h2=omega_b_h2,
                h=h,
                Tcmb_K=Tcmb_K,
                N_eff=N_eff,
            )
        )
    return {
        "schema": "predictions_p1_pipeline_output_v1",
        "prediction_id": "P1",
        "title": "BAO standard-ruler shift in DESI Year-3",
        "tier": "T2",
        "tool": "predictions_compute_P1",
        "tool_version": "v0.2-leading-order-metrology",
        "physics_status": (
            "leading-order σ-metrology shift implemented; second-order σ-modified "
            "recombination pending (M201)"
        ),
        "sub_predictions": sub_predictions,
        "lcdm_baseline_reference": {
            "method": "Eisenstein–Hu (1998) fitting formula",
            "r_d_mpc": sub_predictions[0]["r_s_lcdm_baseline_mpc"],
            "implementation": "gsc/early_time/rd.py",
        },
        "determinism_note": (
            "This file intentionally contains no timestamp. The signing record "
            "(signature_timestamp in prediction.md) supplies the temporal anchor; "
            "the SHA-256 of this file is a function only of the registered inputs."
        ),
    }


def write_output(record: dict, output_path: Path) -> None:
    """Write the record deterministically (sorted keys, fixed indent, trailing newline)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(record, indent=2, sort_keys=True) + "\n"
    output_path.write_text(text, encoding="utf-8")
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    sys.stdout.write(f"wrote {output_path}\n  SHA-256: {sha}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--ansatz",
        choices=("powerlaw", "transition", "rg_profile", "all"),
        default="all",
        help="σ(t) ansatz family (default: all three sub-predictions)",
    )
    parser.add_argument(
        "--p",
        type=float,
        default=0.001,
        help="powerlaw exponent p in σ(z) ∝ (1+z)^(-p) (default 0.001)",
    )
    parser.add_argument(
        "--omega-m-h2", type=float, default=DEFAULTS["omega_m_h2"]
    )
    parser.add_argument(
        "--omega-b-h2", type=float, default=DEFAULTS["omega_b_h2"]
    )
    parser.add_argument("--h", type=float, default=DEFAULTS["h"])
    parser.add_argument("--Tcmb-K", type=float, default=DEFAULTS["Tcmb_K"])
    parser.add_argument("--N-eff", type=float, default=DEFAULTS["N_eff"])
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT
        / "predictions_register"
        / "P1_bao_ruler_shift"
        / "pipeline_output.json",
        help="output path for the pipeline_output.json record",
    )
    parser.add_argument(
        "--print",
        action="store_true",
        help="also print the JSON record to stdout",
    )
    args = parser.parse_args(argv)

    if args.ansatz == "all":
        ansatze = [
            {"ansatz": "powerlaw", "params": {"p": args.p}},
            {
                "ansatz": "transition",
                "params": {
                    "p_low": args.p,
                    "p_high": args.p * 5.0,
                    "z_t": 1.0,
                    "dz": 0.5,
                },
            },
            {
                "ansatz": "rg_profile",
                "params": {"p_eff": args.p, "sigma_star_z": 1e6, "alpha": 0.5},
            },
        ]
    elif args.ansatz == "powerlaw":
        ansatze = [{"ansatz": "powerlaw", "params": {"p": args.p}}]
    elif args.ansatz == "transition":
        ansatze = [
            {
                "ansatz": "transition",
                "params": {
                    "p_low": args.p,
                    "p_high": args.p * 5.0,
                    "z_t": 1.0,
                    "dz": 0.5,
                },
            }
        ]
    else:  # rg_profile
        ansatze = [
            {
                "ansatz": "rg_profile",
                "params": {"p_eff": args.p, "sigma_star_z": 1e6, "alpha": 0.5},
            }
        ]

    record = make_record(
        ansatze=ansatze,
        omega_m_h2=args.omega_m_h2,
        omega_b_h2=args.omega_b_h2,
        h=args.h,
        Tcmb_K=args.Tcmb_K,
        N_eff=args.N_eff,
    )

    if args.print:
        sys.stdout.write(json.dumps(record, indent=2, sort_keys=True) + "\n")

    write_output(record, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())

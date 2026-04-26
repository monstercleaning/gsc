#!/usr/bin/env python3
"""
predictions_compute_P8.py — compute Prediction P8 (Sandage–Loeb redshift drift).

Computes the GSC-predicted redshift-drift Δv(z) at z ∈ {0.1, 0.5, 1.0, 1.5, 2.0,
3.0, 4.0, 5.0} for the registered σ(t) ansatz, alongside the ΛCDM baseline.

Usage:
    python3 scripts/predictions_compute_P8.py
    python3 scripts/predictions_compute_P8.py --p 0.001 --years 10
    python3 scripts/predictions_compute_P8.py --output predictions_register/P8_redshift_drift/pipeline_output.json

Output schema: predictions_p8_pipeline_output_v1.

Wraps the existing redshift_drift_table.py infrastructure with a deterministic
JSON serialisation and the standard predictions-register record format.
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

from gsc.measurement_model import (  # noqa: E402
    FlatLambdaCDMHistory,
    H0_to_SI,
    PowerLawHistory,
    delta_v_cm_s,
)


# Sandage–Loeb evaluation grid (matches the historical drift table).
DEFAULT_REDSHIFTS = (0.1, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0)

# Planck 2018-like baseline (consistent with predictions_compute_P1.py).
DEFAULTS = {
    "H0_km_s_Mpc": 67.4,
    "Omega_m": 0.315,
    "Omega_L": 0.685,
    "years": 10.0,
    "p_powerlaw": 0.001,  # σ(z) ∝ (1+z)^(-p) ↔ a(z) ∝ (1+z)^p in PowerLawHistory
}


def make_history(*, ansatz: str, params: dict, H0_si: float):
    """Construct an H(z) callable for the named ansatz.

    Maps σ-ansatz parameters into the existing measurement_model history classes.
    """
    if ansatz == "lcdm":
        return FlatLambdaCDMHistory(
            H0=H0_si,
            Omega_m=float(params.get("Omega_m", DEFAULTS["Omega_m"])),
            Omega_Lambda=float(params.get("Omega_L", DEFAULTS["Omega_L"])),
        )
    if ansatz == "powerlaw":
        # PowerLawHistory: a(t) ∝ t^p, so σ(t) ∝ a^{-1} ∝ t^{-p}.
        p = float(params.get("p", DEFAULTS["p_powerlaw"]))
        # Convert from σ-ansatz exponent to PowerLawHistory exponent.
        # Mapping: σ(z) ∝ (1+z)^(-p_sigma) ⇒ a(z) ∝ (1+z)^p_sigma ⇒ p_a = p_sigma.
        return PowerLawHistory(H0=H0_si, p=p)
    raise ValueError(f"Unknown ansatz: {ansatz!r}")


def compute_p8_row(
    *,
    z: float,
    ansatz: str,
    params: dict,
    lcdm_baseline: dict,
    years: float,
) -> dict:
    """Compute one row of the drift table for a given (z, ansatz)."""
    H0_si = H0_to_SI(lcdm_baseline["H0_km_s_Mpc"])

    lcdm_history = make_history(
        ansatz="lcdm", params=lcdm_baseline, H0_si=H0_si
    )
    dv_lcdm = delta_v_cm_s(
        z=z,
        years=years,
        H0=H0_si,
        H_of_z=lcdm_history.H,
    )

    gsc_history = make_history(ansatz=ansatz, params=params, H0_si=H0_si)
    dv_gsc = delta_v_cm_s(
        z=z,
        years=years,
        H0=H0_si,
        H_of_z=gsc_history.H,
    )

    return {
        "z": float(z),
        "delta_v_lcdm_cm_s": round(dv_lcdm, 6),
        "delta_v_gsc_cm_s": round(dv_gsc, 6),
        "delta_v_diff_cm_s": round(dv_gsc - dv_lcdm, 6),
        "sign_flip_vs_lcdm": (dv_lcdm * dv_gsc < 0.0),
    }


def make_record(
    *,
    ansatz: str,
    params: dict,
    H0_km_s_Mpc: float,
    Omega_m: float,
    Omega_L: float,
    years: float,
    redshifts: tuple,
) -> dict:
    lcdm_baseline = {
        "H0_km_s_Mpc": H0_km_s_Mpc,
        "Omega_m": Omega_m,
        "Omega_L": Omega_L,
    }
    rows = [
        compute_p8_row(
            z=z,
            ansatz=ansatz,
            params=params,
            lcdm_baseline=lcdm_baseline,
            years=years,
        )
        for z in redshifts
    ]
    return {
        "schema": "predictions_p8_pipeline_output_v1",
        "prediction_id": "P8",
        "title": "Redshift-drift sign and amplitude (supporting discriminator)",
        "tier": "T2 (supporting only, not primary)",
        "tool": "predictions_compute_P8",
        "tool_version": "v0.1",
        "physics_status": (
            "Computed from registered σ(t) ansatz via gsc/measurement_model.py "
            "Sandage–Loeb formula. ELT/ANDES integration time of `years` is "
            "the registered observation interval."
        ),
        "ansatz": ansatz,
        "ansatz_parameters": dict(sorted(params.items())),
        "lcdm_baseline": dict(sorted(lcdm_baseline.items())),
        "observation_interval_years": float(years),
        "drift_table": rows,
        "summary": {
            "any_sign_flip_vs_lcdm": any(r["sign_flip_vs_lcdm"] for r in rows),
            "max_abs_diff_cm_s": round(
                max(abs(r["delta_v_diff_cm_s"]) for r in rows), 6
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
        "--ansatz",
        choices=("powerlaw",),
        default="powerlaw",
        help="σ(t) ansatz family (currently only powerlaw is wired to drift table)",
    )
    parser.add_argument(
        "--p",
        type=float,
        default=DEFAULTS["p_powerlaw"],
        help="σ(z) ∝ (1+z)^(-p) exponent (default 0.001)",
    )
    parser.add_argument(
        "--H0", type=float, default=DEFAULTS["H0_km_s_Mpc"], dest="H0_km_s_Mpc"
    )
    parser.add_argument("--Omega-m", type=float, default=DEFAULTS["Omega_m"])
    parser.add_argument("--Omega-L", type=float, default=DEFAULTS["Omega_L"])
    parser.add_argument(
        "--years", type=float, default=DEFAULTS["years"], help="ELT integration interval"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT
        / "predictions_register"
        / "P8_redshift_drift"
        / "pipeline_output.json",
    )
    parser.add_argument("--print", action="store_true")
    args = parser.parse_args(argv)

    record = make_record(
        ansatz=args.ansatz,
        params={"p": args.p},
        H0_km_s_Mpc=args.H0_km_s_Mpc,
        Omega_m=args.Omega_m,
        Omega_L=args.Omega_L,
        years=args.years,
        redshifts=DEFAULT_REDSHIFTS,
    )

    if args.print:
        sys.stdout.write(json.dumps(record, indent=2, sort_keys=True) + "\n")

    write_output(record, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())

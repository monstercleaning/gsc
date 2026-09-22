#!/usr/bin/env python3
"""
predictions_compute_P8.py — compute Prediction P8 (Sandage–Loeb redshift drift), revision r2.

Computes the GSC-predicted redshift-drift Δv(z) at z ∈ {0.1, 0.5, 1.0, 1.5, 2.0,
3.0, 4.0, 5.0} for the registered σ(t) ansatz, alongside the ΛCDM baseline.

REVISION r2 (v12.7) — what changed and why
-------------------------------------------
Through v12.6 this pipeline built the "GSC" history with ``PowerLawHistory``,
the v10.1 toy in which the shared exponent p is the WHOLE expansion law,
H(z) = H0 (1+z)^p. With the canonical T2 metrology exponent p = 6e-4 that is a
coasting universe (H ≈ H0), which the bundled DESI DR1 BAO data exclude at
+7σ … +128σ per point — and which contradicts the framework's own statement
that T1 is conformally ΛCDM-equivalent. The registered "positive drift at all z /
sign flip vs ΛCDM" was an artefact of that toy, not a prediction of the surviving
framework (the project's archived Roadmap v2.8 §E.1 had already established that
positive drift at z > 2 is impossible for standard matter content; the v12 layout
lost that knowledge). The historical r1 output is retained as
``pipeline_output.r1_superseded.json`` for provenance.

r2 uses the T2-consistent history ``SigmaModulatedLCDMHistory``:
H(z) = H_ΛCDM(z) · (1+z)^p — the same metrology exponent P1 applies to the BAO
ruler. Result: GSC's drift equals ΛCDM's to within 0.03 cm/s at every grid point
(sub-percent relative deviation away from ΛCDM's zero crossing near z ≈ 2, where
relative differences are ill-defined), with identical sign structure. P8 is therefore a ΛCDM-degenerate consistency
test at any foreseeable precision, not a discriminator.

Usage:
    python3 scripts/predictions_compute_P8.py
    python3 scripts/predictions_compute_P8.py --years 10
    python3 scripts/predictions_compute_P8.py --output predictions_register/P8_redshift_drift/pipeline_output.json
    # reproduce the superseded r1 numbers (provenance only, loudly named):
    python3 scripts/predictions_compute_P8.py --ansatz coasting_toy_r1_superseded --output /tmp/p8_r1.json

Output schema: predictions_p8_pipeline_output_v2 (r1 used v1).
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

from gsc.canonical_params import CANONICAL_P  # noqa: E402

from gsc.measurement_model import (  # noqa: E402
    FlatLambdaCDMHistory,
    H0_to_SI,
    SigmaModulatedLCDMHistory,
    delta_v_cm_s,
)


# Sandage–Loeb evaluation grid (unchanged from r1 for comparability).
DEFAULT_REDSHIFTS = (0.1, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0)

# Planck 2018-like baseline (consistent with predictions_compute_P1.py).
DEFAULTS = {
    "H0_km_s_Mpc": 67.4,
    "Omega_m": 0.315,
    "Omega_L": 0.685,
    "years": 10.0,
    "p_metrology": CANONICAL_P,  # σ(z)/σ(0) = (1+z)^(-p): the T2 METROLOGY exponent (P1's p)
}

R1_SUPERSEDED_FILE = "pipeline_output.r1_superseded.json"


def make_history(*, ansatz: str, params: dict, H0_si: float):
    """Construct an H(z) callable for the named ansatz."""
    Om = float(params.get("Omega_m", DEFAULTS["Omega_m"]))
    Ol = float(params.get("Omega_L", DEFAULTS["Omega_L"]))
    if ansatz == "lcdm":
        return FlatLambdaCDMHistory(H0=H0_si, Omega_m=Om, Omega_Lambda=Ol)
    if ansatz == "powerlaw_metrology":
        # T2-consistent: ΛCDM background × leading-order σ-metrology modulation.
        p = float(params.get("p", DEFAULTS["p_metrology"]))
        return SigmaModulatedLCDMHistory(H0=H0_si, Omega_m=Om, Omega_Lambda=Ol, p=p)
    if ansatz == "coasting_toy_r1_superseded":
        # Provenance-only reproduction of the superseded r1 history. Imported
        # lazily and deliberately not the default: see module docstring.
        # The explicit alias keeps CLAIMS.json's guard
        # (`registered-pipelines-never-use-coasting-toy-history`) meaningful:
        # any plain use of the toy in a registered pipeline is caught; this
        # provenance-only path is the one deliberate, loudly-labelled exception.
        from gsc.measurement_model import PowerLawHistory as _CoastingToyR1  # noqa: E402

        p = float(params.get("p", DEFAULTS["p_metrology"]))
        return _CoastingToyR1(H0=H0_si, p=p)
    raise ValueError(f"Unknown ansatz: {ansatz!r}")


def compute_p8_row(*, z: float, ansatz: str, params: dict, lcdm_baseline: dict, years: float) -> dict:
    """Compute one row of the drift table for a given (z, ansatz)."""
    H0_si = H0_to_SI(lcdm_baseline["H0_km_s_Mpc"])
    lcdm_history = make_history(ansatz="lcdm", params=lcdm_baseline, H0_si=H0_si)
    dv_lcdm = delta_v_cm_s(z=z, years=years, H0=H0_si, H_of_z=lcdm_history.H)

    gsc_params = dict(lcdm_baseline)
    gsc_params.update(params)
    gsc_history = make_history(ansatz=ansatz, params=gsc_params, H0_si=H0_si)
    dv_gsc = delta_v_cm_s(z=z, years=years, H0=H0_si, H_of_z=gsc_history.H)

    diff = dv_gsc - dv_lcdm
    rel = (100.0 * diff / abs(dv_lcdm)) if dv_lcdm != 0.0 else 0.0
    return {
        "z": float(z),
        "delta_v_lcdm_cm_s": round(dv_lcdm, 6),
        "delta_v_gsc_cm_s": round(dv_gsc, 6),
        "delta_v_diff_cm_s": round(diff, 6),
        "rel_diff_percent": round(rel, 4),  # informational; ill-defined near LCDM zero crossing
        "same_sign_as_lcdm": (dv_lcdm * dv_gsc > 0.0),
    }


def _sign_flip_interval(rows: list, key: str):
    """Return [z_lo, z_hi] bracketing the first sign change of `key`, or None."""
    for a, b in zip(rows, rows[1:]):
        if a[key] * b[key] < 0.0:
            return [a["z"], b["z"]]
    return None


def make_record(*, ansatz: str, params: dict, H0_km_s_Mpc: float, Omega_m: float,
                Omega_L: float, years: float, redshifts: tuple) -> dict:
    lcdm_baseline = {"H0_km_s_Mpc": H0_km_s_Mpc, "Omega_m": Omega_m, "Omega_L": Omega_L}
    rows = [
        compute_p8_row(z=z, ansatz=ansatz, params=params, lcdm_baseline=lcdm_baseline, years=years)
        for z in redshifts
    ]
    r1_path = REPO_ROOT / "predictions_register" / "P8_redshift_drift" / R1_SUPERSEDED_FILE
    r1_sha = hashlib.sha256(r1_path.read_bytes()).hexdigest() if r1_path.is_file() else None
    return {
        "schema": "predictions_p8_pipeline_output_v2",
        "prediction_id": "P8",
        "revision": "r2",
        "title": "Redshift drift — ΛCDM-degenerate consistency test at foreseeable precision (r2, v12.7)",
        "tier": "T2 (supporting only, not primary; no framework-specific discriminating power)",
        "tool": "predictions_compute_P8",
        "tool_version": "v0.2",
        "physics_status": (
            "Computed from the registered T2 ansatz via the T2-consistent history "
            "H(z) = H_LCDM(z) * (1+z)^p (SigmaModulatedLCDMHistory), where p is the "
            "metrology exponent shared with P1. The r1 output used the v10.1 coasting "
            "toy H = H0 (1+z)^p, excluded at >100 sigma by the bundled DESI BAO and "
            "inconsistent with T1's LCDM equivalence; its 'positive drift at all z / "
            "sign flip' was an artefact of that toy. ELT/ANDES integration time "
            "`years` is the registered observation interval."
        ),
        "supersedes": {
            "revision": "r1",
            "file": R1_SUPERSEDED_FILE,
            "sha256": r1_sha,
            "history_used_by_r1": "PowerLawHistory H(z) = H0 (1+z)^p (coasting at p = 6e-4)",
            "reason": (
                "r1's history is excluded by the framework's own bundled DESI DR1 BAO "
                "(+7 to +128 sigma per point) and contradicts T1's conformal equivalence "
                "to LCDM; the archived Roadmap v2.8 §E.1 had already shown positive drift "
                "at z > 2 is impossible for standard matter content (Omega_m0 > 1/(1+z))."
            ),
        },
        "ansatz": ansatz,
        "ansatz_parameters": dict(sorted(params.items())),
        "lcdm_baseline": dict(sorted(lcdm_baseline.items())),
        "observation_interval_years": float(years),
        "drift_table": rows,
        "summary": {
            "all_same_sign_as_lcdm": all(r["same_sign_as_lcdm"] for r in rows),
            "max_abs_rel_diff_percent": round(max(abs(r["rel_diff_percent"]) for r in rows), 4),
            "max_abs_diff_cm_s": round(max(abs(r["delta_v_diff_cm_s"]) for r in rows), 6),
            "lcdm_sign_flip_z_interval": _sign_flip_interval(rows, "delta_v_lcdm_cm_s"),
            "gsc_sign_flip_z_interval": _sign_flip_interval(rows, "delta_v_gsc_cm_s"),
            "discriminating_power": (
                "none at foreseeable precision: |delta_v_GSC - delta_v_LCDM| <= 0.03 cm/s at every "
                "grid point (relative deviation sub-percent away from LCDM's zero crossing near "
                "z ~ 2, where relative values are ill-defined); identical sign structure"
            ),
        },
        "framework_implications": {
            "status": (
                "P8 is a LCDM-degenerate consistency test: it can fail only if LCDM-class "
                "kinematics fail, and therefore carries no framework-specific "
                "discriminating power. It remains registered (forward: ELT/ANDES data "
                "unreleased) but is no longer described as a structural 'sign-flip' "
                "prediction anywhere in the package."
            ),
            "kill_test": (
                "A robust drift measurement inconsistent with the LCDM-class sign "
                "structure at z >= 2 falsifies T1/T2 exactly as it falsifies LCDM; no "
                "rescue is permitted."
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
        choices=("powerlaw_metrology", "coasting_toy_r1_superseded"),
        default="powerlaw_metrology",
        help="T2-consistent history (default) or provenance-only reproduction of the superseded r1 toy",
    )
    parser.add_argument(
        "--p", type=float, default=DEFAULTS["p_metrology"],
        help="T2 metrology exponent, σ(z)/σ(0) = (1+z)^(-p) (default: canonical, gsc/canonical_params.py)",
    )
    parser.add_argument("--H0", type=float, default=DEFAULTS["H0_km_s_Mpc"], dest="H0_km_s_Mpc")
    parser.add_argument("--Omega-m", type=float, default=DEFAULTS["Omega_m"])
    parser.add_argument("--Omega-L", type=float, default=DEFAULTS["Omega_L"])
    parser.add_argument("--years", type=float, default=DEFAULTS["years"], help="ELT integration interval")
    parser.add_argument(
        "--output", type=Path,
        default=REPO_ROOT / "predictions_register" / "P8_redshift_drift" / "pipeline_output.json",
    )
    parser.add_argument("--print", action="store_true")
    args = parser.parse_args(argv)

    record = make_record(
        ansatz=args.ansatz, params={"p": args.p}, H0_km_s_Mpc=args.H0_km_s_Mpc,
        Omega_m=args.Omega_m, Omega_L=args.Omega_L, years=args.years, redshifts=DEFAULT_REDSHIFTS,
    )
    if args.ansatz != "powerlaw_metrology":
        record["schema"] = "predictions_p8_pipeline_output_v2"
        record["title"] = "[PROVENANCE ONLY] superseded r1 coasting-toy reproduction — not the registered prediction"
    if args.print:
        sys.stdout.write(json.dumps(record, indent=2, sort_keys=True) + "\n")
    write_output(record, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""predictions_compute_P14.py — compute Prediction P14 (early-universe gravity, registered in v20.1).

Physics
-------
The only coherent reading of the canonical exponent (OPEN_PROBLEMS.md,
problem 1) lets particle masses drift relative to the Planck mass before the
transition redshift z_t = 10 and freezes them afterwards. In the Einstein frame
the masses are m = m0 g(z_E) with

    g(z_E) = 1                              for z_E < z_t
    g(z_E) = ((1 + z_E)/(1 + z_t))^(-q)     above it,

and the observed redshift is 1 + z = (1 + z_E)/g. Measured in atomic units,
this is a gravitational coupling that was weaker in the early universe:

    G(z)/G0 = g(z_E)^2 = ((1 + z_E)/(1 + z_t))^(-2q)   above z_t, exactly 1 below.

The exponent q = 8.65e-4 is inherited from P1: it is the value for which the
variant reproduces P1's registered BAO shift at fixed cosmological parameters
(analyses/p_role_consistency.py). A joint CMB + BAO fit shows that distance
data do not constrain q (analyses/joint_fit.md), so the value is a commitment,
not a fit. This pipeline evaluates the registered consequences; it fits nothing.

Output is deterministic (no timestamps, values rounded to fixed decimals).
Standard library only.

Usage:
    python3 pipelines/predictions_compute_P14.py [--output PATH] [--print]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

TOOL = "predictions_compute_P14.py"
TOOL_VERSION = "0.1"
SCHEMA = "predictions_p14_pipeline_output_v1"

Q = 8.65e-4                 # inherited from P1's registered shift (see docstring)
Z_TRANSITION = 10.0
EPOCHS = [
    # name, observed redshift, description
    ("recombination", 1089.95, "z* of Planck 2018 (TT,TE,EE+lowE)"),
    ("nucleosynthesis", 4.3e8, "deuterium formation, T ~ 0.1 MeV"),
    ("weak_freeze_out", 3.0e9, "neutron-proton freeze-out, T ~ 1 MeV (allowing for e+e- annihilation)"),
]


def einstein_redshift(z_obs: float) -> float:
    """Invert 1 + z = (1 + z_E)^(1+q) (1 + z_t)^(-q), valid above the transition."""
    if z_obs < Z_TRANSITION:
        return z_obs
    return ((1.0 + z_obs) * (1.0 + Z_TRANSITION) ** Q) ** (1.0 / (1.0 + Q)) - 1.0


def g_over_g0(z_obs: float) -> float:
    z_e = einstein_redshift(z_obs)
    if z_e < Z_TRANSITION:
        return 1.0
    return ((1.0 + z_e) / (1.0 + Z_TRANSITION)) ** (-2.0 * Q)


def build_record() -> dict:
    epochs = []
    for name, z, note in EPOCHS:
        ratio = g_over_g0(z)
        epochs.append({"epoch": name, "z_obs": z, "note": note,
                       "G_over_G0": round(ratio, 6),
                       "deviation_percent": round(100.0 * (ratio - 1.0), 4)})
    by = {e["epoch"]: e for e in epochs}
    ln_ratio = (math.log(g_over_g0(4.3e8)) / math.log(g_over_g0(1089.95)))
    rec, bbn = by["recombination"], by["nucleosynthesis"]
    return {
        "schema": SCHEMA,
        "prediction_id": "P14",
        "title": "Early-universe gravity weaker relative to atoms: G/G0 = 0.992 at recombination, 0.970 at nucleosynthesis",
        "tier": "T2 (coherent reading of the canonical exponent; OPEN_PROBLEMS.md problem 1)",
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "determinism_note": ("This file intentionally contains no timestamp; SHA-256 is a function only of the "
                             "registered inputs."),
        "physics_status": ("Exact consequence of the early-transition reading for the registered q. Not a fit: "
                           "CMB + BAO distance data do not constrain q (analyses/joint_fit.md)."),
        "registered_parameters": {
            "q": Q,
            "z_transition": Z_TRANSITION,
            "q_provenance": ("Inherited from P1: the value for which the variant reproduces P1's registered BAO "
                             "shift at fixed cosmological parameters (analyses/p_role_consistency.py)."),
        },
        "prediction": {
            "epochs": epochs,
            "late_universe": {"z_obs_below": Z_TRANSITION, "G_over_G0": 1.0,
                              "note": "Exactly 1 below the transition: no local drift, consistent with kill condition K2."},
            "relation_between_epochs": {
                "ln_G_bbn_over_ln_G_rec": round(ln_ratio, 4),
                "note": ("ln(G/G0) at nucleosynthesis over ln(G/G0) at recombination; fixed by the transition shape "
                         "for any q, so two measurements test the shape as well as the amplitude."),
            },
            "summary": (f"G/G0 = {rec['G_over_G0']:.4f} at recombination ({rec['deviation_percent']:+.2f}%) and "
                        f"{bbn['G_over_G0']:.4f} at nucleosynthesis ({bbn['deviation_percent']:+.2f}%)."),
        },
        "scoring_rule": {
            "statistic": ("For each epoch with a published determination r_obs +/- sigma of G/G0 (1 sigma; for "
                          "asymmetric errors the side facing the prediction) from an analysis that lets G at that "
                          "epoch differ from today's: z = (r_pred - r_obs)/sigma."),
            "fail": "|z| >= 3 at any scored epoch, or a fit of this one-parameter model excluding the registered q at >= 3 sigma.",
            "pass": "|z| < 3 at every scored epoch, with at least one sigma <= |r_pred - 1|/2 (a measurement able to tell the prediction from G = G0).",
            "sub_threshold": "|z| < 3 everywhere, but no measurement yet precise enough to tell the prediction from G = G0.",
        },
        "framework_implications": {
            "on_failure": ("The GSC core (T1-T3) then has no registered content that distinguishes it from LCDM, and "
                           "the conformal-reduction clause K0.4 applies: GSC is falsified as a distinct theory."),
            "k0_status": ("Registered under K0.3 as a new forward prediction; the scope and threshold of K0 are "
                          "unchanged. The failure clause above only adds a way for the framework to die."),
            "not_a_rescue_of_P1": "P1 stands as registered, with its editorial flag; P14 does not score or replace it.",
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output",
                        default=str(REPO_ROOT / "predictions" / "P14_early_gravity" / "pipeline_output.json"),
                        help="output path for the pipeline_output.json record")
    parser.add_argument("--print", action="store_true", help="also print the JSON record to stdout")
    args = parser.parse_args(argv)
    payload = json.dumps(build_record(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(payload, encoding="utf-8")
    print(f"wrote {out}")
    print(f"SHA-256: {hashlib.sha256(payload.encode('utf-8')).hexdigest()}")
    if args.print:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

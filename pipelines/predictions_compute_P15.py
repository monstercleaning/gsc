#!/usr/bin/env python3
"""predictions_compute_P15.py — compute Prediction P15 (a0 follows the dark-energy density, registered in v20.2).

Physics
-------
Galaxies show dark matter only below an acceleration a0, the scale of the
radial acceleration relation (McGaugh, Lelli & Schombert, PRL 117, 201101,
2016). Its value is close to c sqrt(Lambda), Milgrom's coincidence. Read that
way, a0 is set by the dark-energy density, and if dark energy evolves, a0
follows it:

    a0(z) / a0(0)       = sqrt(rho_DE(z) / rho_DE(0))
    rho_DE(z)/rho_DE(0) = (1 + z)^(3 (1 + w0 + wa)) exp(-3 wa z / (1 + z))   (CPL)

with (w0, wa) fixed at DESI DR2's four published fits (arXiv:2503.14738 v3,
eqs. 25-28). The spread over the four data combinations is the registered
band; DESI+CMB+DESY5 gives the central value. The reading a0 proportional to
H(z) is excluded by 100 rotation curves at z = 0.6-2.5 (OPEN_PROBLEMS.md,
problem 11); this dark-energy form was suggested by the same data, which
therefore cannot score it. This pipeline evaluates the registered formula; it
fits nothing.

Output is deterministic (no timestamps, values rounded to fixed decimals).
Standard library only.

Usage:
    python3 pipelines/predictions_compute_P15.py [--output PATH] [--print]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

TOOL = "predictions_compute_P15.py"
TOOL_VERSION = "0.1"
SCHEMA = "predictions_p15_pipeline_output_v1"

# DESI DR2 Results II, arXiv:2503.14738 v3, eqs. 25-28 (w0waCDM, CPL).
DESI_DR2 = {
    "DESI+CMB": (-0.42, -1.75),
    "DESI+CMB+Pantheon+": (-0.838, -0.62),
    "DESI+CMB+Union3": (-0.667, -1.09),
    "DESI+CMB+DESY5": (-0.752, -0.86),
}
CENTRAL = "DESI+CMB+DESY5"
Z_GRID = (2.0, 2.22, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 6.0)
SAME_SURVEY_PAIRS = ((0.83, 2.22), (1.0, 3.0))
LOW_Z_RANGE = (0.33, 1.44)            # Ciocan et al. (A&A 709, L16, 2026): the range where a0 was seen to rise
OMEGA_M = 0.315                       # for the a0 ∝ H(z) comparison only (Planck 2018)
A0_LOCAL = [1.20, 0.24]               # McGaugh, Lelli & Schombert 2016; systematic uncertainty


def rho_de_ratio(z: float, w0: float, wa: float) -> float:
    return (1.0 + z) ** (3.0 * (1.0 + w0 + wa)) * math.exp(-3.0 * wa * z / (1.0 + z))


def a0_ratio(z: float, w0: float, wa: float) -> float:
    return math.sqrt(rho_de_ratio(z, w0, wa))


def band(values) -> list:
    return [round(min(values), 4), round(max(values), 4)]


def build_record() -> dict:
    grid = []
    for z in Z_GRID:
        by = {k: round(a0_ratio(z, *wv), 4) for k, wv in DESI_DR2.items()}
        grid.append({"z": z, "central": by[CENTRAL], "band": band(by.values()), "by_history": by})
    pairs = []
    for z_lo, z_hi in SAME_SURVEY_PAIRS:
        by = {k: round(a0_ratio(z_hi, *wv) / a0_ratio(z_lo, *wv), 4) for k, wv in DESI_DR2.items()}
        pairs.append({"z_low": z_lo, "z_high": z_hi, "central": by[CENTRAL], "band": band(by.values()),
                      "by_history": by})
    low = {k: round(a0_ratio(LOW_Z_RANGE[1], *wv) / a0_ratio(LOW_Z_RANGE[0], *wv), 4) for k, wv in DESI_DR2.items()}
    at3 = next(g for g in grid if g["z"] == 3.0)
    e3 = math.sqrt(OMEGA_M * 4.0 ** 3 + 1.0 - OMEGA_M)
    return {
        "schema": SCHEMA,
        "prediction_id": "P15",
        "title": ("Milgrom's acceleration scale follows the dark-energy density: a0 at z = 3 is "
                  f"{at3['central']:.2f} ({at3['band'][0]:.2f}-{at3['band'][1]:.2f}) of today's"),
        "tier": "T4 (MOND-like phenomenology, THEORY.md §6.2)",
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "determinism_note": ("This file intentionally contains no timestamp; SHA-256 is a function only of the "
                             "registered inputs."),
        "physics_status": ("Exact consequence of a0 proportional to the square root of the dark-energy density, "
                           "with DESI DR2's published dark-energy histories. Not a fit: the shape has no free "
                           "parameter, and only ratios to today's a0 are predicted."),
        "registered_parameters": {
            "relation": "a0(z)/a0(0) = sqrt(rho_DE(z)/rho_DE(0)); rho_DE from the CPL form",
            "dark_energy_histories": {k: {"w0": w0, "wa": wa} for k, (w0, wa) in DESI_DR2.items()},
            "central_history": CENTRAL,
            "source": "DESI DR2 Results II, arXiv:2503.14738 v3, eqs. 25-28",
            "a0_today_reference": {"value": A0_LOCAL[0], "sigma": A0_LOCAL[1], "unit": "1e-10 m/s^2",
                                   "source": "McGaugh, Lelli & Schombert, PRL 117, 201101 (2016); systematic"},
        },
        "prediction": {
            "ratio_to_today": grid,
            "same_survey_ratios": pairs,
            "below_z_1_5": {"z_low": LOW_Z_RANGE[0], "z_high": LOW_Z_RANGE[1], "band": band(low.values()),
                            "note": ("Predicted change of a0 over the redshift range in which Ciocan et al. (2026) "
                                     "see a0 rise by a factor of about 2; not in the scored range.")},
            "comparison_at_z3": {"constant_a0": 1.0, "a0_proportional_to_H": round(e3, 4),
                                 "this_prediction_band": at3["band"],
                                 "lcdm_simulations": "rising (Mayer et al., arXiv:2206.04333: about 3 times by z = 2)"},
            "summary": (f"a0(z)/a0(0) = {at3['central']:.2f} ({at3['band'][0]:.2f}-{at3['band'][1]:.2f}) at z = 3, "
                        f"{next(g for g in grid if g['z'] == 4.0)['central']:.2f} at z = 4 and "
                        f"{next(g for g in grid if g['z'] == 5.0)['central']:.2f} at z = 5 (DESI+CMB+DESY5)."),
        },
        "scoring_rule": {
            "statistic": ("For each published determination of the relation's acceleration scale from rotation "
                          "curves of at least 10 galaxies with median redshift z >= 2: r_obs = a0(z)/a0_ref +/- sigma "
                          "(1 sigma; for asymmetric errors the side facing the band). a0_ref is the same method's "
                          "value at z <= 0.1, or its value in a lower-redshift bin of the same survey (the prediction "
                          "is then the ratio of the formula at the two median redshifts), or else the canonical "
                          "1.20 +/- 0.24, whose uncertainty is added to sigma. d is the distance from r_obs to the "
                          "registered band at that redshift (0 inside it), and z = d/sigma."),
            "fail": "z >= 3 for any scored determination.",
            "pass": ("z < 3 for every scored determination, and at least one has sigma <= (1 - upper band edge)/2, "
                     "so that it can tell the prediction from a constant a0."),
            "sub_threshold": "z < 3 everywhere, but no determination yet precise enough to tell the prediction from a constant a0.",
            "scope": ("Determinations published after this registration. RC100 (Nestor Shachar et al., ApJ 944, 78, "
                      "2023) suggested the prediction and is not scored."),
        },
        "framework_implications": {
            "on_failure": ("a0 is not set by the dark-energy density in this form, and the evolving MOND-like scale of "
                           "THEORY.md §6.2 loses its registered form. The GSC core (T1-T3) is unaffected."),
            "k0_status": "A T4 forward prediction; the scope and threshold of kill condition K0 are unchanged.",
            "dependence_on_dark_energy": ("The numbers are fixed at DESI DR2's dark energy. With a true cosmological "
                                          "constant the same idea gives a constant a0, which a precise enough "
                                          "determination would score as a FAIL of this entry."),
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output",
                        default=str(REPO_ROOT / "predictions" / "P15_a0_dark_energy" / "pipeline_output.json"),
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

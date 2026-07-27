#!/usr/bin/env python3
"""predictions_compute_P12.py — compute Prediction P12 (nuclear-electronic clock-ratio null).

Physics
-------
Under GSC's UNIVERSAL coherent scaling (the T1 geometric lock) every local
dimensionless observable is sigma-invariant. The frequency ratio of the
Th-229m nuclear isomeric transition (148 nm) to the Sr-87 electronic clock
transition is such an observable. Therefore GSC predicts

    d ln( nu(Th-229m) / nu(Sr-87) ) / dt = 0   EXACTLY, at all epochs.

This is a *null* prediction with teeth in one direction only:

* It does NOT discriminate GSC from LCDM+GR (both predict a constant ratio).
* It DOES give the framework its first registered channel with HADRONIC-sector
  leverage: the Th-229m transition's alpha-sensitivity is measured at
  K = 5900(2300) (arXiv:2407.17300) and its quark-mass/strong-sector leverage
  is theory-estimated at ~1e4 — no electronic-electronic clock comparison has
  this reach. A robust nonzero drift falsifies universal scaling (T1) outright
  via the sudden-death clause (GSC_Framework.md section 12.2.1b).

Anchor: nu(Th-229m)/nu(Sr-87) = 4.707072615078(18), Zhang et al., Nature 633,
63 (2024), arXiv:2406.18719 — the first and (at registration, 2026-07-27) only
epoch. This registration is genuinely FORWARD: it commits the framework before
any second-epoch data exist.

Output is deterministic (no timestamps); SHA-256 is a function of the
registered inputs only. Stdlib only.

Usage:
    python3 scripts/predictions_compute_P12.py [--output PATH] [--print]
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

TOOL = "predictions_compute_P12.py"
TOOL_VERSION = "0.1"
SCHEMA = "predictions_p12_pipeline_output_v1"

# Registered anchor (first-epoch measurement, already public at registration).
ANCHOR_RATIO = 4.707072615078
ANCHOR_UNCERTAINTY_LAST_TWO_DIGITS = 18
ANCHOR_SOURCE = "Zhang et al., Nature 633, 63 (2024); arXiv:2406.18719"


def build_record() -> dict:
    return {
        "schema": SCHEMA,
        "prediction_id": "P12",
        "title": (
            "Nuclear-electronic clock-ratio null: d ln(nu_Th229m/nu_Sr87)/dt = 0 "
            "exactly under universal coherent scaling"
        ),
        "tier": "T1 (falsification channel on the geometric lock, hadronic sector)",
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "scaling_mode": "universal_coherent",
        "determinism_note": (
            "This file intentionally contains no timestamp; SHA-256 is a function "
            "only of the registered inputs."
        ),
        "physics_status": (
            "Exact consequence of the T1 geometric lock: every local dimensionless "
            "ratio is sigma-invariant, including nuclear-to-electronic transition "
            "frequency ratios. Not a fit; no free parameters. The measured "
            "alpha-sensitivity K = 5900(2300) (arXiv:2407.17300) and theory-level "
            "~1e4 quark-mass leverage give this null hadronic-sector reach no "
            "electronic clock comparison has. Sector-coupled sigma extensions "
            "(all retired/bounded T3-T4 modules) would violate it; the canonical "
            "framework carries no such term."
        ),
        "prediction": {
            "dln_ratio_dt_per_yr": 0.0,
            "sector_coverage": {
                "alpha_sensitivity_K_measured": 5900,
                "alpha_sensitivity_K_sigma": 2300,
                "quark_mass_sensitivity_theory": "~1e4 (theory estimate, not measurement)",
                "coverage_note": (
                    "GSC predicts zero drift in every sector simultaneously; a "
                    "drift induced through ANY sector (alpha, quark masses, "
                    "strong-sector condensates) would move the ratio and fail "
                    "the score."
                ),
            },
            "anchor": {
                "ratio_nu_Th229m_over_nu_Sr87": ANCHOR_RATIO,
                "uncertainty_in_last_two_digits": ANCHOR_UNCERTAINTY_LAST_TWO_DIGITS,
                "source": ANCHOR_SOURCE,
            },
            "parametrization_note": (
                "For ANY parametrization of secular ratio drift the predicted "
                "coefficient is identically zero; the registered scoring statistic "
                "is z = (r - 0)/sigma_r on the two-epoch drift rate r."
            ),
        },
        "scoring_preconditions": {
            "min_epoch_separation_yr": 0.5,
            "max_fractional_uncertainty_per_epoch": 1e-13,
            "note": (
                "Registered 2026-07-27 with exactly one public epoch (the anchor). "
                "Scoring begins when a qualifying second epoch is published by any "
                "group; the scorer script ships then, so the active-scorer count "
                "continues to reflect scoreable predictions only."
            ),
        },
        "framework_implications": {
            "universal_scaling_outcome": (
                "Predicted drift exactly zero at all epochs. A robust nonzero "
                "drift (>= 3 sigma, stable under systematic reanalysis, "
                "independently reproduced — all three) falsifies universal "
                "coherent scaling (T1) outright via the sudden-death clause "
                "12.2.1b. A single qualifying detection suffices; no rescue "
                "mechanism is permitted."
            ),
            "discrimination_note": (
                "The null is shared with LCDM+GR: this prediction does not "
                "distinguish GSC from the standard model. It distinguishes GSC "
                "from sector-coupled varying-constants scenarios (including "
                "GSC's own retired non-universal extensions) and pre-commits "
                "the framework to death if any local dimensionless ratio drifts."
            ),
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "predictions_register" / "P12_nuclear_clock_ratio" / "pipeline_output.json"),
        help="output path for the pipeline_output.json record",
    )
    parser.add_argument("--print", action="store_true", help="also print the JSON record to stdout")
    args = parser.parse_args(argv)

    record = build_record()
    payload = json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(payload, encoding="utf-8")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    print(f"wrote {out}")
    print(f"SHA-256: {digest}")
    if args.print:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

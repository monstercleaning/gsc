#!/usr/bin/env python3
"""predictions_compute_P13.py — compute Prediction P13 (GW-EM duality null).

Physics
-------
Standard-siren cosmology parametrizes modified GW propagation as

    d_L^GW(z) / d_L^EM(z) = Xi_0 + (1 - Xi_0) / (1+z)^n

with Xi_0 = 1 recovering general relativity (Belgacem et al. convention, as
used by the LVK GWTC cosmology analyses). Under GSC's UNIVERSAL coherent
scaling (the T1 geometric lock) the freeze-frame is an exact conformal
relabeling of FLRW: no coupling singles out the tensor sector, and the GW and
EM luminosity distances are relabeled identically. Therefore GSC predicts

    Xi_0 = 1   EXACTLY, with d_L^GW/d_L^EM = 1 at all z (n irrelevant).

This is a *null* prediction with teeth in one direction only:

* It does NOT discriminate GSC from LCDM+GR (both predict Xi_0 = 1).
* It DOES give the framework a standing tensor-sector falsification channel:
  a robust (>= 3 sigma, systematics-stable, independently reproduced) Xi_0
  detection away from 1 falsifies universal scaling (T1) outright — and it
  discriminates GSC from modified-gravity scenarios with tensor friction or
  leakage (running Planck mass, extra dimensions, alpha_M != 0).

Together with P9 (matter), P11 (photon), and P12 (nuclear/hadronic) this
completes the four-sector null package of the universal core.

Output is deterministic (no timestamps); SHA-256 is a function of the
registered inputs only. Stdlib only.

Usage:
    python3 scripts/predictions_compute_P13.py [--output PATH] [--print]
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

TOOL = "predictions_compute_P13.py"
TOOL_VERSION = "0.1"
SCHEMA = "predictions_p13_pipeline_output_v1"

# Representative redshift grid spanning the dark-siren range of current LVK
# catalogs. Values are exact by construction.
Z_GRID = [0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0, 1.5]


def build_record() -> dict:
    return {
        "schema": SCHEMA,
        "prediction_id": "P13",
        "title": (
            "GW-EM luminosity-distance duality: Xi_0 = 1 exactly under "
            "universal coherent scaling"
        ),
        "tier": "T1 (falsification channel on the geometric lock, tensor sector)",
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "scaling_mode": "universal_coherent",
        "determinism_note": (
            "This file intentionally contains no timestamp; SHA-256 is a function "
            "only of the registered inputs."
        ),
        "physics_status": (
            "Exact consequence of the T1 conformal relabeling: GW and EM "
            "luminosity distances are relabeled identically, so their ratio is 1 "
            "at every redshift. Not a fit; no free parameters. No GSC sector "
            "couples to the tensor sector non-universally; the canonical "
            "framework carries no term that could break this."
        ),
        "prediction": {
            "distance_ratio_of_z": [{"z": z, "dl_gw_over_dl_em": 1.0} for z in Z_GRID],
            "xi0": 1.0,
            "xi0_deviation": 0.0,
            "parametrization_note": (
                "For the Xi_0-n parametrization used by LVK GWTC cosmology "
                "analyses, GSC predicts Xi_0 = 1 exactly and the ratio is 1 at "
                "all z, so n is irrelevant. For ANY parametrization of modified "
                "GW propagation the predicted deviation is identically zero."
            ),
        },
        "framework_implications": {
            "universal_scaling_outcome": (
                "Predicted d_L^GW/d_L^EM = 1 at all z, exactly. A robust "
                "(>= 3 sigma, systematics-stable, independently reproduced) "
                "Xi_0 != 1 falsifies universal coherent scaling (T1) outright "
                "via the tensor-sector sudden-death extension of 12.2.1a. A "
                "single qualifying detection suffices; no rescue is permitted."
            ),
            "discrimination_note": (
                "Xi_0 = 1 is shared with LCDM+GR: this prediction does not "
                "distinguish GSC from the standard model. It distinguishes GSC "
                "from tensor-friction/leakage modified gravity and pre-commits "
                "the framework to death if the tensor-sector duality breaks."
            ),
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "predictions_register" / "P13_gw_em_duality" / "pipeline_output.json"),
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

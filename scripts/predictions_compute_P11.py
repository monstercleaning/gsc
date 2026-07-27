#!/usr/bin/env python3
"""predictions_compute_P11.py — compute Prediction P11 (distance-duality null).

Physics
-------
The Etherington reciprocity relation, D_L(z) = (1+z)^2 D_A(z), holds in any
spacetime where (i) photon number is conserved along the beam and (ii) photons
propagate on null geodesics of a metric theory, independently of the field
equations. Define

    eta(z) = D_L(z) / [(1+z)^2 D_A(z)]          (Etherington 1933)

Under GSC's UNIVERSAL coherent scaling (the T1 geometric lock), the freeze-frame
is related to FLRW by an exact conformal relabeling: photon number is conserved,
the redshift is achromatic, and no photon-sector coupling singles out
electromagnetism. Therefore GSC predicts

    eta(z) = 1   EXACTLY, at every redshift, to all orders in the scaling.

This is a *null* prediction with teeth in one direction only:

* It does NOT discriminate GSC from LCDM (both predict eta = 1).
* It DOES give the framework a hard, standing falsification channel: any robust
  (model-independent, calibration-robust, >= 3 sigma) violation of distance
  duality falsifies the universal-scaling axiom T1 outright — and with it every
  higher tier. It also discriminates GSC from DDR-violating alternatives
  (photon-axion mixing, varying-c/varying-hbar models, opacity models).

The only GSC sector that could produce eta != 1 is the non-universal sigma-F.F
photon coupling — a T3 opt-in module that is already independently bounded; the
canonical framework carries no such term.

Output is deterministic (no timestamps); SHA-256 is a function of the
registered inputs only. Stdlib only.

Usage:
    python3 scripts/predictions_compute_P11.py [--output PATH] [--print]
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

TOOL = "predictions_compute_P11.py"
TOOL_VERSION = "0.1"
SCHEMA = "predictions_p11_pipeline_output_v1"

# Representative redshift grid spanning the SN x BAO overlap where DDR tests
# operate (Pantheon+/DES-SN5YR x DESI). Values are exact by construction.
Z_GRID = [0.1, 0.3, 0.5, 0.7, 1.0, 1.3, 1.7, 2.0, 2.33]


def build_record() -> dict:
    return {
        "schema": SCHEMA,
        "prediction_id": "P11",
        "title": "Distance-duality (Etherington) relation: eta(z) = 1 exactly under universal coherent scaling",
        "tier": "T1 (falsification channel on the geometric lock, photon sector)",
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "scaling_mode": "universal_coherent",
        "determinism_note": (
            "This file intentionally contains no timestamp; SHA-256 is a function "
            "only of the registered inputs."
        ),
        "physics_status": (
            "Exact consequence of the T1 conformal relabeling: photon-number "
            "conservation + achromatic redshift + no photon-sector coupling imply "
            "Etherington reciprocity is preserved identically. Not a fit; no free "
            "parameters. The non-universal sigma-F.F opt-in module (T3) is the only "
            "GSC sector that could break this, and it is independently bounded."
        ),
        "prediction": {
            "eta_of_z": [{"z": z, "eta": 1.0} for z in Z_GRID],
            "eta0_deviation": 0.0,
            "eta1_linear_coefficient": 0.0,
            "parametrization_note": (
                "For linear parametrizations eta(z) = 1 + eta1*z (as used in current "
                "DESI-era DDR tests), GSC predicts eta1 = 0 exactly. For ANY "
                "parametrization, the predicted deviation is identically zero."
            ),
        },
        "framework_implications": {
            "universal_scaling_outcome": (
                "Predicted eta(z) = 1 at all z, exactly. Any robust, "
                "calibration-robust violation of distance duality at >= 3 sigma "
                "falsifies universal coherent scaling (T1) and propagates to all "
                "higher tiers. This is a standing sudden-death channel: unlike the "
                "majority rule over forward tests, a single confirmed DDR violation "
                "suffices."
            ),
            "discrimination_note": (
                "eta(z) = 1 is shared with LCDM: this prediction does not "
                "distinguish GSC from the standard model. It distinguishes GSC from "
                "DDR-violating alternatives and pre-commits the framework to death "
                "if duality breaks."
            ),
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "predictions_register" / "P11_distance_duality" / "pipeline_output.json"),
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

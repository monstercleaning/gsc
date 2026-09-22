#!/usr/bin/env python3
"""Negative control for the claim detector: it must still catch a known false claim.

This test inverts the usual polarity: it succeeds only if the detector FAILS a
tree. The tree is `fixtures/historical_false_claim/`, a verbatim copy of the
prose in which an earlier release asserted that the prediction register was
"cryptographically signed" while no entry was signed. The detector must report
`register-gpg-signed` as UNBACKED there, on at least MIN_SITES of the 18
historical assertion sites.

Why a sensitivity floor and not just "does it still fire": an over-broad hedge
once silenced 17 of the 18 sites while still technically firing on the last
one. Firing on one line is not detection; it is luck.

Why a fixture and not git history: the check must work in shallow clones, in
unzipped deposits, and in any repository layout. The fixture carries its own
provenance (verification/fixtures/README.md).

Usage:  python3 verification/retro_test.py
Exit:   0 = detector still fires (good); 1 = detector went blind (bad).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "historical_false_claim"
MUST_FAIL_CLAIM = "register-gpg-signed"
HISTORICAL_SITES = 18
MIN_SITES = 10


def main() -> int:
    print("=== claim-detector negative control ===")
    print(f"  fixture: {FIXTURE.relative_to(HERE.parent)}")
    proc = subprocess.run(
        [sys.executable, str(HERE / "verify_claims.py"), "--root", str(FIXTURE),
         "--claims", str(HERE / "claims.json"), "--format", "json"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
    )
    doc = json.loads(proc.stdout.decode("utf-8"))
    by_id = {r["id"]: r for r in doc.get("results", [])}
    target = by_id.get(MUST_FAIL_CLAIM)
    if target is None:
        print(f"  RESULT: FAIL — claim {MUST_FAIL_CLAIM!r} is no longer in the manifest.")
        return 1
    if MUST_FAIL_CLAIM not in doc.get("unbacked", []):
        print(f"  RESULT: FAIL — detector went blind ({target['verdict']}): {target['detail']}")
        print("          Most likely cause: an `unless` hedge or pattern edit that over-generalized.")
        return 1
    n = len(target.get("sites", []))
    if n < MIN_SITES:
        print(f"  RESULT: FAIL — sensitivity collapsed: {n} of {HISTORICAL_SITES} sites (floor {MIN_SITES}).")
        return 1
    print(f"  RESULT: PASS — {n} of {HISTORICAL_SITES} historical assertion sites caught (floor {MIN_SITES}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

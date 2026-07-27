"""Canonical σ(t) ansatz parameters — single source of truth (v12.5 revival).

Why this module exists
----------------------
The July 2026 cross-prediction consistency audit found that every prediction
pipeline hard-coded its own copy of the scaling exponent (``p = 0.001`` in six
separate DEFAULTS dicts). The values happened to agree by copy-paste, which
means they were one careless edit away from silently fracturing the "one
framework" claim into N independently tuned models. All pipelines now import
the canonical value from here.

Provenance of the value (v12.5 re-centering, 2026-07)
-----------------------------------------------------
The v12.2 central value p = 1.0e-3 FAILS the registered DESI Year-1
relative-shift test at z = +3.93 (rule: |z| < 3) and sits in tension with
lunar-laser-ranging Ġ/G. A p-scan through the actual P1 pipeline against the
registered DESI Y1 precision (0.26/147.09) gives:

    survival boundary (|z| = 3):  p = 7.63e-4
    canonical choice:             p = 6.00e-4
        -> Delta r_d / r_d = +0.417%  (z_Y1 = +2.36, PASSES with ~21% margin)
        -> Gdot/G ~ -8.4e-14 /yr      (8.3x under the LLR bound 2±7e-13 /yr)

The re-centering uses ONLY already-public data (DESI Y1, LLR) and is therefore
a retrodictive constraint, not a prediction. The forward risk is carried by
the pre-registered forward set (P1@DESI-Y3, P2, P10, P11): at Y3-era BAO
precision the +0.417% shift is decisively testable. Framework-level kill
condition: GSC_Framework.md §12.2.1.

Honesty note: choosing p near the survival boundary maximises
distinguishability; choosing p -> 0 would make the framework observationally
identical to ΛCDM (T1 is conformally equivalent by construction). A theory
kept alive by shrinking its observables to zero is not alive. The canonical
value is deliberately large enough to die by.
"""

from __future__ import annotations

# Canonical powerlaw exponent: σ(z) ∝ (1+z)^(-p).
CANONICAL_P: float = 6.0e-4

# v12.2 historical central value, kept for provenance/reproduction of the
# retrodictive Y1 scorecard analysis. Do NOT use in new pipelines.
V12_2_HISTORICAL_P: float = 1.0e-3

# Transition-ansatz companion parameters scale with the canonical value so the
# three σ(z) families stay mutually comparable (high-z leg = 5x low-z leg, as
# in the v12.2 registration).
CANONICAL_P_TRANSITION_LOW: float = CANONICAL_P
CANONICAL_P_TRANSITION_HIGH: float = 5.0 * CANONICAL_P

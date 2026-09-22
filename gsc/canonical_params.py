"""Canonical σ(t) ansatz parameters — the single source of truth for every pipeline.

Why this module exists
----------------------
An audit once found every prediction pipeline hard-coding its own copy of the
scaling exponent. The copies agreed only by copy-paste, one careless edit away
from silently splitting "one framework" into several independently tuned
models. All pipelines import the canonical value from here.

Provenance of the value
-----------------------
An earlier central value, p = 1.0e-3, fails the registered DESI Year-1
relative-shift check at z = +3.93 (rule |z| < 3). A p-scan through the P1
pipeline against the registered DESI Year-1 precision (0.26/147.09 Mpc) gives:

    survival boundary (|z| = 3):  p = 7.63e-4
    canonical choice:             p = 6.00e-4
        -> Delta r_d / r_d = +0.417%   (z_Y1 = +2.36, passes with ~21% margin)

The value uses only already-public data, so it is a retrodictive constraint,
not a prediction. It is deliberately near the boundary: p -> 0 would make the
framework observationally identical to ΛCDM, and a theory kept alive by
shrinking its observables to zero is not alive.

Open problem (OPEN_PROBLEMS.md, problem 1): which sector carries p. A universal
rescaling is unobservable; the only reading that reproduces P1's shift (masses
drifting relative to the Planck mass) implies a present-day drift of G in atomic
units that lunar laser ranging (arXiv:2012.12032) excludes at about 9σ for the
power law. Kill conditions: THEORY.md §8.
"""

from __future__ import annotations

# Canonical power-law exponent: σ(z)/σ(0) = (1+z)^(-p).
#
# ROLE: a METROLOGY exponent — a leading-order modulation of atomic units
# relative to a flat-ΛCDM background. It is NOT an expansion-history exponent
# and must never be passed to gsc.measurement_model.PowerLawHistory (the toy
# H = H0 (1+z)^p, in which the same letter is the whole expansion law): at
# p ~ 6e-4 that toy is a coasting universe excluded at >100σ by the package's
# own DESI BAO data. The P8 revision r1 was computed that way and is superseded;
# verification/claims.json forbids registered pipelines from using the toy.
CANONICAL_P: float = 6.0e-4
CANONICAL_P_ROLE: str = "sigma_metrology_exponent"  # not an expansion-history exponent

# The earlier central value (fails the registered DESI Year-1 check); kept only
# to reproduce that historical check. Do NOT use in new pipelines.
V12_2_HISTORICAL_P: float = 1.0e-3

# Transition-ansatz companion parameters scale with the canonical value so the
# σ(z) families stay comparable (high-redshift leg = 5x the low-redshift leg).
CANONICAL_P_TRANSITION_LOW: float = CANONICAL_P
CANONICAL_P_TRANSITION_HIGH: float = 5.0 * CANONICAL_P

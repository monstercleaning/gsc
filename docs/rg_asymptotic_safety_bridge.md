# RG/Asymptotic-Safety Bridge Note

This note defines the claim boundary for how the current framework references asymptotic safety / FRG language.

## What the current framework says

- We use a minimal, phenomenological running-coupling proxy for `G(k)` to model rapid UV-scale amplification.
- The current implementation uses a Landau-pole-like parametrization as a toy crossover form.
- This is a modeling ansatz used in a late-time/early-time diagnostic pipeline, not a first-principles FRG construction.
- In standard asymptotic-safety UV scaling one expects `G(k) ~ g*/k^2` (UV weakening in dimensionful `G`), which is not the same object as the pole-like toy proxy used here.
- The pole-like ansatz is phenomenological and should not be labeled "standard AS output".
- Phase-4 epsilon inference work does not rely on AS/FRG-collapse as a base pillar.

## What the current framework does **not** say

- We do not claim that asymptotic safety predicts the exact Landau-pole-like form used in the toy model.
- We do not claim that the scale-identification map (`k` versus cosmological/structural scales, e.g. `k ~ 1/sigma`) is derived.
- We do not claim an FRG derivation of the beta functions used by the scan tools in this release.

## Why mention asymptotic safety / FRG at all

- Conceptual motivation only: gravity couplings can run with scale in nonperturbative RG frameworks.
- The present scripts use that motivation to choose a compact phenomenological parameterization and test observational consistency.

## Open problem and roadmap

A controlled bridge would require, at minimum:

- a non-trivial cosmological scale-identification prescription for `k`,
- explicit truncation choices and flow equations,
- matching conditions to matter-sector scales,
- and consistency checks against the same data pipeline used in the current release.

Until then, the AS/FRG link in the current framework remains conceptual and ansatz-level.

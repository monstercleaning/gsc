---
prediction_id: P13
title: GW-EM luminosity-distance duality — Xi_0 = 1 exactly under universal coherent scaling
tier: T1 (falsification channel on the geometric lock, tensor sector)
ansatz: universal coherent scaling (no tensor-sector coupling); parameter-free
target_dataset: LVK standard-siren catalogs (GWTC-4.0 current; GWTC-5.0/O5 and beyond tighten automatically)
target_release_date: continuous (each observing run tightens the constraint on others' timelines)
status: SCAFFOLD — git-timestamped, GPG-signing pending; RETRODICTIVE current-bounds check + FORWARD sudden-death falsification channel
signed_by: —
signature_timestamp: —
repo_commit_at_signing: —
pipeline_output_hash: —
---

# Prediction P13 — GW–EM duality: Ξ₀ = 1 exactly (added v12.6)

## Statement

Gravitational waves and electromagnetic radiation propagating through the same
cosmology define two luminosity distances, d_L^GW(z) and d_L^EM(z). Modified
GW propagation is parametrized in the standard-siren literature by

```
d_L^GW(z) / d_L^EM(z) = Ξ₀ + (1 − Ξ₀) / (1+z)^n        (Ξ₀–n parametrization)
```

with Ξ₀ = 1 recovering general relativity. Under GSC's universal coherent
scaling (T1 geometric lock) the freeze-frame is an exact conformal relabeling
of FLRW: no coupling singles out the tensor sector, and both distances are
relabeled identically. Therefore

```
Ξ₀ = 1    exactly (and the ratio is 1 at all z, making n irrelevant).
```

**This is a parameter-free exact null** — the tensor-sector counterpart to
P11's photon-sector distance duality.

## What this prediction is and is not

- It is **not** a discriminator against ΛCDM+GR — both predict Ξ₀ = 1.
- It **is** a standing **sudden-death falsification channel**: a robust
  Ξ₀ ≠ 1 detection falsifies T1 outright (§12.2.1a, tensor-sector extension).
- It **does** discriminate GSC from modified-gravity scenarios with extra
  tensor friction/leakage (extra dimensions, running Planck mass, scalar–
  tensor theories with α_M ≠ 0).
- Together with P9 (matter), P11 (photon), and P12 (nuclear/hadronic), it
  completes a four-sector null package: the universal core predicts that
  *every* sector's duality/ratio test returns exactly the GR/ΛCDM value.

## Tier

**T1** — consistency check on the geometric lock, tensor sector.

## Pipeline

- `scripts/predictions_compute_P13.py` — deterministic, parameter-free output.
- `scripts/predictions_score_P13.py` — scores Ξ₀ against the recorded constraint.

## Current observational status (retrodictive check)

GWTC-4.0 dark-siren analysis (142 events × GLADE+): Ξ₀ = 1.2 +0.8/−0.4
(68.3% credibility), "Ξ₀ = 1 recovers the behavior of general relativity"
(LVK, arXiv:2509.04348; abstract verified via INSPIRE record 2026-07-27).
GSC's Ξ₀ = 1 sits at z = +0.5 → PASS at the registered rule. GWTC-5.0
(236 sources) reports "no departures from GR in parameterized tests of GW
propagation" (arXiv:2605.27227, verbatim abstract).

## Scoring algorithm

```
z = (Ξ₀_observed − 1) / σ_toward_null
```

where, for asymmetric uncertainties, σ_toward_null is the error bar on the
side facing the null (here the lower bar: the observed value sits above 1,
so σ = 0.4). PASS if |z| < 3 (registered rule, same convention as P1/P3/P4/
P11). This is the conservative choice: it uses the smaller error bar between
the measurement and the null, maximizing |z|.

## Kill-test

A robust Ξ₀ ≠ 1 — ≥ 3σ, stable under galaxy-catalog and population-model
systematics, and reproduced across independent siren analyses (all three) —
falsifies universal coherent scaling (T1) outright via the tensor-sector
sudden-death extension of §12.2.1a. No tier-demotion, non-universal
extension, or unimplemented correction may be invoked to rescue it.
Conversely, every observing run that tightens Ξ₀ around 1 is a passed test
of the lock, on other people's instruments and timelines.

## Significance

O4/O5 siren catalogs grow without any involvement from this project, and the
Ξ₀ constraint tightens automatically. The framework pre-commits now: the
answer will be exactly 1, forever, in every sector at once.

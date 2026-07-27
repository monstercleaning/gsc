---
prediction_id: P11
title: Distance-duality (Etherington) relation — eta(z) = 1 exactly under universal coherent scaling
tier: T1 (falsification channel on the geometric lock, photon sector)
ansatz: universal coherent scaling (no photon-sector coupling); parameter-free
target_dataset: DDR compilations (DESI BAO x Pantheon+/DES-SN5YR x cosmic chronometers), current and future
target_release_date: continuous (DESI DR2-era constraints public; precision tightens through full five-year DESI + LSST era)
status: SCAFFOLD — git-timestamped, GPG-signing pending; RETRODICTIVE current-bounds check + FORWARD sudden-death falsification channel
signed_by: —
signature_timestamp: —
repo_commit_at_signing: —
pipeline_output_hash: —
---

# Prediction P11 — Distance duality: η(z) = 1 exactly (added v12.5)

## Statement

The Etherington reciprocity relation D_L = (1+z)² D_A holds in any metric theory
with photon-number conservation, independently of field equations. Under GSC's
universal coherent scaling (T1 geometric lock) the freeze-frame is an exact
conformal relabeling of FLRW: photon number is conserved, redshift is
achromatic, and no coupling singles out the photon sector. Therefore

```
η(z) = D_L / [(1+z)² D_A] = 1    exactly, at all z, to all orders.
```

**This is a parameter-free exact null.** For the linear parametrization
η(z) = 1 + η₁z used in current DESI-era tests, GSC predicts η₁ = 0 exactly.

## What this prediction is and is not

- It is **not** a discriminator against ΛCDM — both predict η = 1.
- It **is** a standing **sudden-death falsification channel**: any robust
  (calibration-robust, model-independent) DDR violation at ≥ 3σ falsifies T1
  outright and propagates to every higher tier. Unlike the majority rule over
  the forward set (§12.2.1), a **single** confirmed violation suffices
  (§12.2.1a).
- It **does** discriminate GSC from DDR-violating alternatives: photon–axion
  mixing models, varying-c/varying-ħ proposals (e.g. Nguyen, arXiv:2412.04257),
  and cosmic-opacity models.
- The only GSC sector that could break duality is the non-universal σ-F̃F
  photon coupling — a T3 opt-in module, independently bounded; the canonical
  framework carries no such term.

## Tier

**T1** — like P9, a consistency check on the geometric lock itself; the photon-sector
counterpart to P9's matter-sector μ-constancy null.

## Pipeline

- `scripts/predictions_compute_P11.py` — deterministic, parameter-free output.
- `scripts/predictions_score_P11.py` — scores η₁ against the recorded constraint.

## Current observational status (retrodictive check)

DESI DR2 BAO + Pantheon+ + cosmic chronometers give η₁ = 0.023 ± 0.027,
consistent with zero (Zhang et al. 2025, arXiv:2506.17926). GSC's η₁ = 0 sits
at z = +0.85 → PASS at the registered rule. Claimed parametrized deviations in
the literature (up to 6σ) appear only with specific external calibrations
(BBN+SH0ES) and vanish in model-independent reconstructions (Keil et al. 2025,
arXiv:2504.01750) — hence the robustness qualifiers in the kill condition.

## Scoring algorithm

```
z = (η₁_observed − 0) / σ_obs
```

PASS if |z| < 3 (registered rule). The sudden-death clause additionally
requires, before T1 is declared falsified, that a claimed violation be
(i) ≥ 3σ, (ii) robust to SN calibration choices, and (iii) present in
model-independent (non-parametric) reconstructions — all three, to prevent a
calibration artefact from executing the framework.

## Kill-test

Robust DDR violation ⇒ universal coherent scaling (T1) is false ⇒ GSC core
falsified as a distinct theory. No tier-demotion, no non-universal extension,
and no unimplemented correction may be invoked to rescue it (§12.2.1).

## Significance

This is the framework's cleanest suicide switch: exact, parameter-free,
continuously tested by data that improves without any dedicated instrument
(full five-year DESI, LSST-era SNe). A theory that pre-commits to dying on a
single confirmed measurement is falsifiable in the operational sense this
repository exists to enforce.

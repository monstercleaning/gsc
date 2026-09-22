---
prediction_id: P10
title: TeV blazar arrival-time dispersion — energy-flat, structure-correlated
tier: T4 (σ(x) spatial-extension test)
ansatz: σ(x,t) field with spatial gradients sourced by large-scale structure
target_dataset: CTAO archival blazar arrival-time data, line-of-sight cross-correlated with Planck-Compton-Y / kSZ tomography
target_release_date: CTAO commissioning 2026; first archival reanalysis 2027-2028
status: SCAFFOLD — NOT YET SIGNED
signed_by: —
signature_timestamp: —
repo_commit_at_signing: —
pipeline_output_hash: —
---

# Prediction P10 — TeV blazar arrival-time dispersion

## Statement

If σ is a spatial field with gradients ∇σ tracking gravitational potential (the σ(x,t) extension of Section 6 of `GSC_Framework.md`), then TeV photons traversing line-of-sight integrals over varying σ accumulate path-dependent arrival-time dispersion proportional to ∫(∇σ)²·dℓ.

Critically, this dispersion is **energy-flat** under universal coherent scaling — all photons see the same effective metric perturbation. This distinguishes it from quantum-gravity Lorentz-invariance violation (LIV), which predicts *energy-dependent* delays Δt ∝ E (linear) or Δt ∝ E² (quadratic).

The prediction is

```
σ²_t(z, lineofsight) = (k_grad)² · ∫₀^d_L (∇σ)² dℓ
```

where k_grad is the σ-gradient coupling (parametric until σ(x,t) field equation is derived) and the integral is along the photon path. The variance σ²_t scales with line-of-sight column density of dark matter (since σ-gradients track gravitational potential gradients).

## Tier

**T4 (σ(x) spatial-extension test)** — depends on the σ(x,t) field-theoretic extension. Failure does not affect T1-T3 or other T4 modules; success would be the first direct evidence for the spatial σ extension.

## Why this is novel

Standard QG-LIV searches (e.g., Mrk 501 with MAGIC; HESS catalogue) look for monotonic energy-dependent delays. The signature predicted here is fundamentally different:

- **Energy-flat** (independent of photon energy);
- **Structure-correlated** (tracks line-of-sight DM column density);
- **Stochastic, not systematic** (variance, not mean delay).

A positive observation would provide a discriminator *against* QG-LIV and *for* a soft cosmological scalar field — exactly the kind of differential test that distinguishes among models.

## Pipeline

To be implemented as `scripts/predictions_compute_P10.py`. Outputs:

- Predicted σ²_t for representative blazar lines of sight (PKS 2155-304, Mrk 421, Mrk 501) parameterised by k_grad amplitude.
- Cross-correlation strength prediction with Planck-Compton-Y / kSZ tomography of same lines of sight.
- Order-of-magnitude estimate against current (HESS, MAGIC, VERITAS) and future (CTAO) sensitivity.

## Target observation

- **Current archival data:** HESS, MAGIC, VERITAS catalogues (~50 blazars at z = 0.01–0.6 with TeV detections).
- **Near-future:** CTAO — Cherenkov Telescope Array Observatory commissioning 2026, first science 2027.
- **Cross-correlation:** Planck-Compton-Y full-sky tomography (already public); ACT and SPT updates.

## Scoring algorithm

Two-channel test:

1. **Direct dispersion bound:** for each blazar with TeV time-resolved data, fit Δt vs E. GSC predicts no E-dependence, but excess energy-flat variance σ²_t > 0. Compare to fit residuals.

2. **Structure correlation:** stack arrival-time variance across blazars sorted by line-of-sight Compton-Y; GSC predicts positive correlation slope.

PASS if both tests are consistent with predicted k_grad band; FAIL if either tightly excludes.

## Effort estimate

≈ 2 weeks for first-pass parametric pipeline; ≈ 2-3 months for full statistical-inference pipeline including cross-correlation with structure tomography.

## Significance

P10 is the framework's first prediction targeting a *spatial* property of σ (Section 6 of `GSC_Framework.md`), distinct from the cosmological-time evolution explored in P1-P5, P8-P9. A positive detection would provide direct evidence for the σ(x,t) extension; a tight upper limit would constrain the σ-matter coupling strength.

This is also the most directly publishable comparison vs the QG-LIV community — same data, different signature.

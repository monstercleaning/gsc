---
prediction_id: P3
title: Neutron-lifetime beam–trap discrepancy as σ-environmental dependence
tier: T4
ansatz: σ(x,t) with matter-density coupling — to be specified at signing time
target_dataset: Neutron lifetime measurements in beam (BL-NPDγ, BL3, ATRAP-style) and trap (UCNτ, μSR, magnetic trap) configurations
target_release_date: continuous (ongoing UCNτ campaigns, BL3 startup ≈ 2026)
status: SCAFFOLD — NOT YET SIGNED
signed_by: —
signature_timestamp: —
repo_commit_at_signing: —
pipeline_output_hash: —
---

# Prediction P3 — Neutron-lifetime beam–trap discrepancy

## Statement

The currently-unexplained ~9 second discrepancy between beam (τ_n^beam ≈ 887.7 s) and trap (τ_n^trap ≈ 878.4 s) measurements of free-neutron lifetime arises from σ-environmental dependence: σ takes slightly different equilibrium values in the high-density trap-wall environment vs. the beam free-vacuum environment, modifying the β-decay rate.

The prediction is

```
Δτ_n / τ_n |_{trap - beam} = (∂τ_n / ∂σ) · Δσ_environmental
```

where Δσ_environmental is computed from the GSC σ(x,t) field equation in the two experimental geometries, and ∂τ_n/∂σ is computed from the σ-dependence of V_ud, M_n − M_p, and Fermi coupling G_F.

## Tier

**T4** — depends on the σ(x,t) field-theoretic extension (Section 6 of GSC_Framework.md). Failure of this prediction does not affect T1–T3.

## Pipeline

To be implemented:

1. New module `gsc/neutron_lifetime/sigma_environmental.py` — solves σ(x) equation of motion in idealized geometries (open beam vs. cylindrical/magnetic trap with wall density profile).
2. New module `gsc/neutron_lifetime/beta_decay_rate.py` — computes ∂(τ_n)/∂σ from σ-dependence of the relevant SM parameters.
3. New script `scripts/predictions_compute_P3.py` — produces (τ_n^beam, τ_n^trap) for the registered σ(x,t) ansatz.

## Target observation

- **Beam experiments:** BL-NPDγ (NIST, ongoing), BL3 (planned 2026 startup);
- **Trap experiments:** UCNτ (LANL, ongoing), τSPECT, JaP-trap;
- **Released ahead of P3:** the existing world averages (PDG); pre-registration must specify the *next* unreleased measurement.

## Scoring algorithm

For each new measurement of τ_n with reported uncertainty σ_τ:

```
z_beam = (τ_n^beam_observed - τ_n^beam_predicted) / sqrt(σ_obs^2 + σ_pred^2)
z_trap = (τ_n^trap_observed - τ_n^trap_predicted) / sqrt(σ_obs^2 + σ_pred^2)
z_diff = ((τ_n^trap - τ_n^beam)_observed - Δτ_n_predicted) / sqrt(...)
```

Pass if all three z-scores are within registered confidence band (default |z| < 3).

The differential `Δτ_n` is the most informative test, because it cancels common-mode systematics.

## Effort estimate

≈ 1 month for first-pass:
- σ(x) solver with simple geometry (1 week);
- β-decay rate σ-derivative (1 week);
- Cross-validation against published wall-effect bounds (1 week);
- Pre-register (a few days).

## Significance

This is the **table-top test** of GSC. If validated, GSC explains a real ~4σ experimental anomaly using a single field-theoretic extension. If different trap geometries show *no* corresponding τ_n variation, the σ(x,t) extension (Section 6) is excluded — but T1–T3 survive.

A particularly clean test: comparing τ_n in a magnetic trap (no wall material near the neutrons) vs. a material trap. GSC predicts a non-zero difference; standard physics predicts zero.

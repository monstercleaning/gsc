---
prediction_id: P5
title: Strong-CP θ-bound consistency with σ-axion-equivalence
tier: T3
ansatz: σ(t) + σ-θ coupling (Section 4) — to be specified at signing time
target_dataset: Neutron electric dipole moment (nEDM) measurements bounding |θ_eff|
target_release_date: continuous (active n2EDM, PSI nEDM upgrades, 2027+)
status: SCAFFOLD — NOT YET SIGNED
signed_by: —
signature_timestamp: —
repo_commit_at_signing: —
pipeline_output_hash: —
---

# Prediction P5 — Strong-CP θ-bound consistency

## Statement

The σ-θ coupling (Section 4 of GSC_Framework.md) drives θ_eff(z) along a calculable cosmological trajectory. The current limit |θ_eff(z=0)| ≲ 10^{-10} (from |d_n| < 1.8 × 10^{-26} e·cm, n2EDM 2024) constrains the σ-coupling parameter f_σ.

The prediction is a *trajectory* θ_eff(z) for the registered σ(t) ansatz and σ-θ coupling f_σ, with the present-day endpoint θ_eff(z=0) consistent with current nEDM bounds. Future tighter nEDM bounds will then test the relaxation efficacy of the σ-mechanism.

## Tier

**T3** — same as P4 (both test the σ-F̃F coupling). P4 and P5 are joint-consistency predictions.

## Pipeline

Shares the f_σ computation infrastructure with P4. Additional component:

1. Module `gsc/strong_cp/theta_evolution.py` — solves the cosmological θ-relaxation equation for the registered σ(t).
2. Script `scripts/predictions_compute_P5.py` — produces θ_eff(z=0) and the trajectory θ_eff(z) for z ∈ [0, 1100], with uncertainty band.

## Target observation

- **Current bound:** n2EDM 2024 (|d_n| < 1.8 × 10^{-26} e·cm at 90% CL → |θ_eff| ≲ 10^{-10}).
- **Future bounds:** PSI n2EDM upgrade (~2027, factor 10 improvement targeted), HUNTER, Yale-PSI consortium.

## Scoring algorithm

For each released bound B_θ on |θ_eff|:

```
pass if |θ_eff^predicted(z=0)| < B_θ at registered CL
```

Joint consistency with P4: the same f_σ value must satisfy both the nEDM bound (P5) and the CMB birefringence amplitude (P4). Joint failure indicates the σ-axion-equivalence is incorrect.

## Effort estimate

Shares ~2 weeks with P4 for the f_σ machinery; θ-relaxation evolution adds ~1 week.

## Significance

The σ-axion-equivalence is among the most ambitious claims of GSC. Three layered tests:

1. **Existence test (P5):** does any σ-θ coupling consistent with nEDM bounds exist?
2. **Joint consistency (P4 + P5):** does the same f_σ work for both birefringence and nEDM?
3. **Cosmological evolution test:** does θ_eff(z) trajectory leave imprints in high-z absorption-line nuclear-physics signatures (e.g., Fe II isospin breaking)?

Layer (3) is too speculative for v12 pre-registration; it is a v13+ candidate. P5 + P4 are sufficient for v12.

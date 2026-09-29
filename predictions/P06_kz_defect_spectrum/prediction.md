---
prediction_id: P6
title: Kibble–Zurek defect spectrum from σ_*-crossing
tier: T4
ansatz: σ(t) + RG critical exponents (ν, z) at σ_*-crossing — to be specified at signing time
target_dataset: Stochastic gravitational-wave background (NANOGrav, EPTA, LISA)
target_release_date: continuous (NANOGrav 30-yr ≈ 2030); LISA ≈ 2035
status: SCAFFOLD — git-timestamped, GPG-signing pending; RETRODICTIVE consistency check (target data already public)
signed_by: —
signature_timestamp: —
repo_commit_at_signing: —
pipeline_output_hash: —
---

# Prediction P6 — Kibble–Zurek defect spectrum

## Statement

The cosmological evolution of σ(t) crosses the effective critical scale σ_* with finite rate τ_quench ~ (σ̇/σ)^{-1}|_{σ=σ_*}. By Kibble–Zurek scaling, this generates topological defects with density:

```
n_defects ~ ξ_KZ^{-3} ~ τ_quench^{-3ν/(1+νz)}
```

where ν and z are the critical exponents of the gravitational FRG fixed point at σ_*. The resulting cosmic string network produces a stochastic GW background with characteristic frequency spectrum dN/df predictable from the registered σ(t) and (ν, z).

## Tier

**T4** — depends on the KZ derivation of vortex DM (Section 6.1 of THEORY.md). Failure does not affect T1–T3 or other T4 modules.

## Pipeline

> **Editorial flag (added at the reorganization; the registered text below is unchanged):** the modules this section names were planned at registration and never built. The registered output comes from `pipelines/predictions_compute_P6.py`, a simplified parametric implementation. See OPEN_PROBLEMS.md, problem 6.

To be implemented:

1. Module `gsc/topological_defects/kz_density.py` — computes n_defects from registered σ(t) and (ν, z).
2. Module `gsc/topological_defects/string_network_evolution.py` — evolves the cosmic string network from formation to today (Vilenkin–Shellard formalism, σ-modified).
3. Module `gsc/topological_defects/gw_spectrum.py` — produces stochastic GW spectrum dN/df for current and future detectors.
4. Script `pipelines/predictions_compute_P6.py`.

## Target observation

- **NANOGrav 15-yr:** detected stochastic GW background (~nHz); origin still debated.
- **NANOGrav 30-yr (~2030):** improved constraints on stochastic background origin.
- **EPTA, IPTA:** complementary nHz constraints.
- **LISA (~2035):** mHz band, sensitive to lower-mass defect populations.

## Scoring algorithm

> **Editorial flag (v20.2, external review; the registered text below is unchanged):** the pipeline converts Ω_GW to
> strain as h_c = √Ω_GW. The correct relation is h_c = √(3/2π²) (H₀/f) √Ω_GW, so at 10⁻⁸ Hz the stored strain (0.82)
> is too large by about ten orders of magnitude (≈ 7×10⁻¹¹), and the stored signal-to-noise ratios and detectability
> flags are invalid. The FAIL compares Ω_GW with the PTA bound directly and stands at this order-of-magnitude level.
> The scorer's remark that a TeV-scale crossing is required is wrong: with the pipeline's own Ω_GW = (M_*/M_Pl)² × 10⁶
> and the bound 10⁻⁹, the requirement is M_* ≲ 4×10¹¹ GeV.

For each released stochastic GW spectrum upper limit or detection at frequency band [f1, f2]:

```
S = ∫_{f1}^{f2} [Ω_GW^obs(f) - Ω_GW^predicted(f)]^2 / σ_obs(f)^2 df
```

Pass if S < threshold (registered).

GSC may also be in *tension* with the NANOGrav 15-yr signal if the predicted amplitude is too low — in this case the σ-crossing+KZ is not the dominant source, but does not falsify the framework as such.

## Effort estimate

Substantial (~3–4 months):
- FRG critical exponents at σ_* fixed point (collaboration-dependent);
- String-network evolution code (port public Vilenkin–Shellard with σ-modification);
- GW spectrum computation;
- Multiple comparison analysis.

Lower priority than P1–P5 for first-cycle implementation.

## Significance

This is the test of the **vortex-DM-from-KZ** module (Section 5). If the predicted GW spectrum is observed at the right amplitude, GSC has *derived* (not postulated) a dark-matter mechanism. If excluded, vortex DM remains a postulate at most.

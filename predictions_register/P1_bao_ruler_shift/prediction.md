---
prediction_id: P1
title: BAO standard-ruler shift in DESI Year-3
tier: T2
ansatz: σ(t) — to be specified at signing time
target_dataset: DESI Year-3 galaxy-clustering BAO peak position
target_release_date: 2027 (estimated)
status: SCAFFOLD — NOT YET SIGNED
signed_by: —
signature_timestamp: —
repo_commit_at_signing: —
pipeline_output_hash: —
---

# Prediction P1 — BAO standard-ruler shift in DESI Year-3

## Statement

The BAO acoustic scale `r_s` in GSC differs from the ΛCDM expectation by a calculable amount due to the σ-dependence of the sound speed `c_s` and the recombination time `t_rec`. The prediction is

```
Δr_s / r_s |_{GSC − ΛCDM} = f(σ_*, ansatz)
```

where `f(·)` is computed from the late-time fit parameters of the chosen σ(t) ansatz, propagated through the early-Universe sound-horizon integral

```
r_s = ∫_0^{t_rec} c_s(t) / a(t) dt
```

evaluated under GSC's σ(t)-dependent sound speed and recombination history.

## Tier

**T2** — this prediction tests the phenomenological σ(t) ansatz against a BAO measurement that is sensitive to early-Universe sound horizon. It is not sensitive to T3 (RG mechanism) or T4 (extension modules) details independently.

## Ansatz and parameters

To be locked at signing time. Candidate forms from `gsc/histories/`:

- `gsc_powerlaw_*` — power-law σ(t) ∝ t^p
- `gsc_transition_*` — transition between two power-law regimes around z_t
- `gsc_rg_profile_*` — numerically integrated from G(σ) ansatz of Section 3 of GSC_Framework.md

Each will produce a distinct prediction; all three should be registered as separate sub-predictions (P1.a, P1.b, P1.c) so that DESI Y3 simultaneously tests all three σ(t) families.

## Pipeline

To be implemented. Plan:

1. Extend `scripts/phase4_desi_bao_baseline.py` to compute GSC-specific `r_s` for each registered ansatz.
2. New script `scripts/predictions_compute_P1.py` that:
   - Loads the registered ansatz parameters from `pipeline_output.json`;
   - Computes `r_s(GSC)` and `r_s(ΛCDM)`;
   - Outputs the predicted `Δr_s / r_s` and its 1σ band from parameter uncertainty;
   - Writes deterministic output to `pipeline_output.json` with SHA-256.

3. Scoring script `scripts/predictions_score_P1.py` that:
   - Loads the released DESI Y3 BAO measurement;
   - Compares to the pre-registered prediction;
   - Generates `scorecard.md` with pass/fail at registered confidence level.

## Target observation

- **Dataset:** DESI Year-3 galaxy-clustering BAO peak position;
- **Instrument:** DESI;
- **Expected release:** 2027 (currently estimated; revise when DESI publishes timeline);
- **Released ahead of P1:** DESI Year-1 (already public), DESI Year-2 (in progress).

Pre-registration must use the *next unreleased increment* — at registration time, this means Y3 if Y1+Y2 are already public.

## Scoring algorithm

For each registered sub-prediction (P1.a, P1.b, P1.c):

```
z = (r_s_observed - r_s_predicted) / sqrt(σ_obs^2 + σ_pred^2)
```

Pass if |z| < 3 (2-sided 99.7% CL); fail otherwise.

If at least one sub-prediction passes, T2 is consistent with DESI Y3.
If all sub-predictions fail at >3σ, T2 is in tension with DESI Y3 and the σ(t) ansatz family is excluded.

## Dependencies on other framework decisions

This prediction depends on:

- The choice of σ(t) ansatz family (locked at signing);
- The late-time fit parameters (locked from a specific commit SHA at signing);
- The BAO sound-horizon integral implementation (locked from a specific commit SHA);
- The ΛCDM baseline used for differential prediction (Planck 2018 best-fit; locked at signing).

## Effort estimate

≈ 2 weeks of focused work to:

- Implement `predictions_compute_P1.py` (1 week);
- Run for all three ansatz families and verify reproducibility (3 days);
- Sign and register (1 day);
- Document (2 days).

This is the **lowest-effort, highest-impact** near-term test of GSC. Recommended as M201 (first pre-registration milestone of the current cycle).

## What signing requires

When ready to sign:

1. Code in `predictions_compute_P1.py` is reviewed and frozen (commit SHA recorded);
2. Pipeline is run; `pipeline_output.json` is generated;
3. Author runs `scripts/predictions_sign.py P1` which:
   - Computes SHA-256 of `pipeline_output.json`;
   - Records repo commit SHA;
   - Records ISO-8601 timestamp;
   - Writes signature to `prediction.md` front-matter;
   - Emits a GPG-signed bundle.
4. The signed entry is committed to the repository and the commit is pushed to the canonical branch.

After signing, this `prediction.md` file is **immutable**. Errors discovered post-signature are recorded as superseding predictions (P1.r2) referencing the original.

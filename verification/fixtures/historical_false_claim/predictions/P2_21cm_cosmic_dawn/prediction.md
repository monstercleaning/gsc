---
prediction_id: P2
title: 21cm Cosmic-Dawn signal in scale-covariant cosmology
tier: T2/T3
ansatz: σ(t) — to be specified at signing time
target_dataset: HERA Phase-II / SKA-Low globally averaged 21cm signal at z ≈ 15–25
target_release_date: 2027–2030 (HERA Phase-II ≈ 2027, SKA-Low precision ≈ 2030)
status: SCAFFOLD — NOT YET SIGNED
signed_by: —
signature_timestamp: —
repo_commit_at_signing: —
pipeline_output_hash: —
---

# Prediction P2 — 21cm Cosmic-Dawn signal

## Statement

The cosmological 21cm globally-averaged absorption signal at z ≈ 15–25 in GSC differs from ΛCDM expectation through σ-evolution of:

- Recombination history (z_rec, x_e);
- Lyman-α coupling efficiency in spin-temperature determination;
- X-ray heating rate of the IGM by first stars / mini-quasars;
- Wouthuysen–Field effect amplitude.

The prediction is a globally-averaged differential brightness temperature `δT_b(ν)` over 70 < ν < 200 MHz, distinct from the ΛCDM expectation by a calculable amount.

## Tier

**T2/T3** — sensitive to both the late-time σ(t) ansatz (T2) and the RG mechanism (T3) through their joint determination of recombination and early-star physics.

## Bonus target: EDGES anomaly

The EDGES 2018 anomalously-deep absorption profile at z ≈ 17 (~500 mK, vs. ~200 mK ΛCDM expectation) is currently unexplained. Whether GSC's σ-evolution naturally accounts for the depth and timing is a candidate consistency check; this is an opportunistic test, not the primary scoring target.

## Pipeline

To be implemented as `gsc/cosmic_dawn/` module.

Plan:
1. New module `gsc/cosmic_dawn/recombination.py` — σ-dependent x_e history (extends existing recfast-like routine in `gsc/early_time/`).
2. New module `gsc/cosmic_dawn/spin_temperature.py` — Wouthuysen–Field coupling with σ-evolved Lyα flux from first sources.
3. New module `gsc/cosmic_dawn/heating.py` — X-ray heating with σ-modified halo mass function.
4. New script `scripts/predictions_compute_P2.py` — computes δT_b(ν) for the registered σ(t) ansatz, outputs to `pipeline_output.json`.

## Target observation

- **Dataset:** HERA Phase-II globally-averaged 21cm spectrum;
- **Instrument:** HERA, then SKA-Low for precision improvement;
- **Expected release:** 2027 (HERA Phase-II preliminary), 2030 (SKA-Low precision).

## Scoring algorithm

Compare predicted δT_b(ν) profile to observed profile in three regions:

```
S_dark_ages = ∫_{70-90 MHz}  [δT_b^pred(ν) - δT_b^obs(ν)]^2 / σ_ν^2 dν
S_first_stars = ∫_{90-140 MHz} ...
S_reionization = ∫_{140-200 MHz} ...
```

Pass if all three integrals are within registered confidence band.

## Effort estimate

≈ 2–3 months for first-pass computation. Dependencies:

- Lyα radiation transfer code (collaborative use of existing 21cmFAST, ARES, or in-house simple);
- σ-modified halo mass function integration;
- σ-modified recombination tabulation.

The main intellectual work is the σ-modification of standard 21cm physics — the public 21cm codes assume ΛCDM. We need a tested adapter layer.

## Significance

If GSC naturally explains the EDGES profile depth and timing, this is a major consistency win. If GSC predicts a measurably different profile that HERA/SKA observe, the prediction is decisive.

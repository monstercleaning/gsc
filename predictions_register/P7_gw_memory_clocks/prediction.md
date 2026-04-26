---
prediction_id: P7
title: GW-memory-induced atomic-clock-array signature
tier: T4
ansatz: σ(t) + σ-GW coupling — to be specified at signing time
target_dataset: Optical-lattice atomic-clock comparison data (ITOC, BACON, NICT-PTB-NIST), correlated with LIGO/Virgo merger triggers
target_release_date: continuous (existing post-O3/O4 data + future O5)
status: SCAFFOLD — NOT YET SIGNED
signed_by: —
signature_timestamp: —
repo_commit_at_signing: —
pipeline_output_hash: —
---

# Prediction P7 — GW-memory atomic-clock signature

## Statement

Each LIGO/Virgo binary-merger event produces a gravitational-wave memory effect (a permanent strain shift after the GW pulse). Through σ-coupling, the GW memory permanently shifts the local σ-equilibrium, producing a permanent shift in atomic transition frequencies.

The prediction is that a globally-distributed network of optical-lattice atomic clocks should observe a *correlated* frequency shift `Δν/ν` at the time of each major GW merger, with amplitude:

```
Δν/ν ∝ h_memory · (∂ν/∂σ)_atomic
```

where h_memory is the registered GW memory amplitude (computable from LIGO waveform), and (∂ν/∂σ) is the atomic-frequency σ-derivative.

## Tier

**T4** — depends on the σ-coupling-to-GW extension (a generalization of the σ(x,t) field-theoretic framework).

## Pipeline

To be implemented:

1. Module `gsc/gw_memory/sigma_response.py` — computes the σ-equilibrium shift induced by a GW memory of given amplitude.
2. Module `gsc/gw_memory/atomic_frequency_shift.py` — computes the atomic transition frequency shift for given clock species (Sr, Yb, Al+, etc.).
3. Module `gsc/gw_memory/correlation_analysis.py` — cross-correlates predicted shifts at multiple stations against LIGO/Virgo trigger times.
4. Script `scripts/predictions_compute_P7.py`.

## Target observation

- **Existing data:** ITOC, BACON, NICT-PTB-NIST clock comparisons during 2017–2025 covering O1–O3.
- **Future:** BACON-II, post-O5 data with improved clock stability.

## Scoring algorithm

For each candidate GW event with memory amplitude h_mem, look in the post-event clock data for a correlated frequency-shift signature:

```
χ²_event = Σ_stations [(Δν/ν)_observed_station - (Δν/ν)_predicted]^2 / σ_clock^2
```

Stack over events with significance weighting by h_mem to extract a coherent signal. Pass if combined significance is above registered threshold or null signal is consistent with GSC-predicted upper limit.

## Effort estimate

The analysis is straightforward in principle (~2 months) but depends on:

- Access to atomic-clock comparison time-series in the relevant time windows;
- Collaboration with clock metrology groups;
- LIGO public-data analysis tooling (PyCBC).

## Significance

This is a **zero-additional-instrument test** — uses entirely existing infrastructure. If a correlation is observed, GSC has identified a new coupling channel between gravity and metrology. If null, the σ-GW coupling is bounded.

The most important asset of P7 is its low cost. Any positive result would be highly novel; even tight upper limits constrain the σ-coupling parameter space at orders of magnitude beyond current constraints.

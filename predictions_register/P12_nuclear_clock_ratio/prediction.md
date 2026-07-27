---
prediction_id: P12
title: Nuclear–electronic clock-ratio drift — d ln(nu_Th / nu_Sr)/dt = 0 exactly under universal coherent scaling
tier: T1 (falsification channel on the geometric lock, hadronic sector)
ansatz: universal coherent scaling (no sector-dependent coupling); parameter-free
target_dataset: repeat Th-229m/Sr-87 (or equivalent clock-network) frequency-ratio measurements; JILA / PTB / TU Wien solid-state and trapped-ion nuclear-clock campaigns
target_release_date: first qualifying second epoch expected ~2027-2029 (closed-loop solid-state clocks operating since 2026)
status: SCAFFOLD — git-timestamped, GPG-signing pending; GENUINE FORWARD registration (no second-epoch ratio data existed at registration, 2026-07-27)
signed_by: —
signature_timestamp: —
repo_commit_at_signing: —
pipeline_output_hash: —
---

# Prediction P12 — Nuclear–electronic clock-ratio null: d ln(ν_Th/ν_Sr)/dt = 0 exactly (added v12.6)

## Statement

Under GSC's universal coherent scaling (T1 geometric lock) every local
dimensionless observable is σ-invariant. The ratio of a *nuclear* transition
frequency (the ²²⁹ᵐTh isomer at 148 nm) to an *electronic* clock transition
(⁸⁷Sr) is such an observable. Therefore

```
d ln( ν(Th-229m) / ν(Sr-87) ) / dt = 0    exactly, at all epochs.
```

**This is a parameter-free exact null**, and it is the framework's first
registered channel with *hadronic-sector* leverage: the Th-229m transition's
sensitivity to variation of the fine-structure constant is **measured** at
K = 5900(2300) (Beeks et al. 2024, arXiv:2407.17300 — "three orders of
magnitude enhancement over atomic clock schemes"), and its sensitivity to
quark-mass/strong-sector parameters is theory-estimated at ~10⁴ (Flambaum-type
analyses; theory, not measurement). No electronic–electronic clock comparison
has this reach. GSC predicts zero in every sector at once.

## Anchor (first-epoch measurement, already public)

ν(²²⁹ᵐTh)/ν(⁸⁷Sr) = **4.707072615078(18)** — first direct nuclear–electronic
frequency ratio, JILA VUV frequency comb (Zhang et al., Nature 633, 63 (2024),
arXiv:2406.18719); fractional uncertainty ~4×10⁻¹².

Instrument trajectory (all on other groups' timelines, no involvement from
this project): closed-loop solid-state Th-229 clock with fractional instability
3×10⁻¹² √(τ/s), reaching ~10⁻¹⁵ per day of averaging, already used to
constrain slow drifts of strong-sector couplings beyond previous limits
(Toscani De Col et al. 2026, arXiv:2606.04997); solid-state frequency
reproducibility demonstrated (Nature 2025); PTB/TU Wien programs ongoing.

## What this prediction is and is not

- It is **not** a discriminator against ΛCDM+GR — both predict a constant ratio.
- It **is** a standing **sudden-death falsification channel** (§12.2.1b): a
  robust nonzero secular drift falsifies T1 outright.
- It **does** discriminate GSC from every varying-constants scenario with
  sector dependence — varying-α models, varying-quark-mass models, dilaton
  models with composition-dependent couplings — including GSC's **own retired
  non-universal extensions** (the σ-environmental and σ-F̃F modules).
- It is a **genuine forward registration**: exactly one epoch of ratio data
  existed when this entry was written. The prediction is that every future
  epoch reproduces the anchor within combined uncertainties, forever.

## Tier

**T1** — hadronic-sector counterpart to P9 (μ-constancy, matter sector) and
P11 (distance duality, photon sector). Together the three form the local-null
package enforced by §12.2.1b.

## Pipeline

- `scripts/predictions_compute_P12.py` — deterministic, parameter-free output.
- Scorer: **deliberately not yet implemented.** The scoring rule is registered
  below; the scorer script ships when a qualifying second epoch exists, so that
  the active-scorer count continues to reflect scoreable predictions only.

## Scoring algorithm (registered now, scored later)

Preconditions: ≥ 2 epochs of the ratio (or an equivalent clock-network chain
connecting the same transitions) separated by Δt ≥ 0.5 yr, each with fractional
uncertainty ≤ 1×10⁻¹³, published by any group(s).

```
r      = [ln(ratio_epoch2) − ln(ratio_epoch1)] / Δt      (yr⁻¹)
z      = (r − 0) / σ_r
```

PASS if |z| < 3 (registered rule, same convention as P1/P3/P4/P11).

## Kill-test

A robust nonzero drift — **all three** of: (i) ≥ 3σ, (ii) stable under
systematic/calibration reanalysis, (iii) reproduced on an independent
apparatus — falsifies universal coherent scaling (T1) outright via the
sudden-death clause §12.2.1b. No tier-demotion, non-universal extension, or
screening mechanism may be invoked to rescue it. Conversely, every published
tightening of the drift bound that GSC survives is a passed test of the lock.

## Context bounds (electronic sector, for calibration of expectations)

Best current electronic-clock drift bounds: d ln α/dt = 1.8(2.5)×10⁻¹⁹ /yr
(Filzinger et al. 2023, PRL 130, 253001, Yb⁺ E3/E2 vs Sr); d ln μ/dt =
−8(36)×10⁻¹⁸ /yr (Lange et al. 2021, PRL 126, 011102). A Th/Sr ratio campaign
at 1×10⁻¹⁵/yr precision would probe α-drift at ~1.7×10⁻¹⁹/yr via K — matching
the best electronic bound while *simultaneously* covering the hadronic sector
no electronic comparison sees. GSC's registered value in all sectors: 0.

## Significance

P12 completes a three-sector local-null package (P9 matter, P11 photon, P12
nuclear/hadronic) whose data streams all improve on other people's timelines.
The framework's surviving testable content is deliberately concentrated in
exact nulls plus one metrology-level BAO shift — each null a standing
opportunity to die, none a free parameter.

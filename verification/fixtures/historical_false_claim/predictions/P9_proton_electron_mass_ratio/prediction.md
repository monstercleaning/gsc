---
prediction_id: P9
title: Constancy of μ = m_p/m_e under universal coherent scaling
tier: T1 (consistency check on geometric lock)
ansatz: universal coherent scaling (Section 1.3 of GSC_Framework.md)
target_dataset: H₂, CH₃OH, HD⁺ molecular spectroscopy of cosmological absorbers + laboratory ion-trap measurements
target_release_date: continuous (current bounds; HD⁺ ion-trap improvements 2026-2028)
status: SCAFFOLD — NOT YET SIGNED
signed_by: —
signature_timestamp: —
repo_commit_at_signing: —
pipeline_output_hash: —
---

# Prediction P9 — Constancy of μ = m_p/m_e

## Honest framing (revised v12.2)

P9 is **not an independent prediction** in the sense that P1, P4, P6 are. It is a *consistency test of the geometric-lock axiom* — under strict universal coherent scaling (Section 1.3 of `GSC_Framework.md`), all dimensionless ratios are σ-invariant *by definition*. Calling this a "prediction" is partially tautological: it asks whether the framework's defining axiom is consistent with the data that motivates it.

The scientific value of registering P9 is twofold:
1. **Negative result is informative**: a future detection of μ̇/μ ≠ 0 falsifies the universal-scaling axiom and propagates to all higher tiers.
2. **Independent of σ-axion claim**: if Paper B's σ-F̃F coupling claim survives the de Brito-Eichhorn-Lino dos Santos 2022 obstruction, then σ couples non-universally to gauge bosons. This non-universality could in principle leak into the QCD-vs-electroweak sectoral split that distinguishes m_p (≈99% QCD trace anomaly) from m_e (Higgs VEV). P9 then becomes a quantitative test of that leakage.

The non-universal opt-in mode in `predictions_compute_P9.py` parametrises the differential coupling η_diff = η_QCD − η_Higgs and produces a non-zero μ̇/μ proportional to η_diff. This connects P9 to the same underlying σ-coupling structure that P4 and P5 explore.

## Statement

Under strict universal coherent scaling (default mode):

```
μ̇/μ = 0                  (at z=0, present epoch)
Δμ/μ |_{z>0 vs z=0} = 0   (cosmological invariance)
```

Under non-universal opt-in mode (parametric η_diff):

```
μ̇/μ ≈ -η_diff × p × H_0
Δμ/μ(z) ≈ -η_diff × p × ln(1+z)
```

**For the literature-grounded coupling g_CS ≈ 0.036 used in P4 and P5**, the natural η_diff scale is comparable; explicit derivation pending the FRG calculation. If η_diff ≈ 0.036 and p ≈ 10⁻³, predicted μ̇/μ ≈ -2.5 × 10⁻¹⁵/yr — within 2 orders of magnitude of the current HD⁺ bound but beyond it. This is the joint-consistency test with P4/P5 that the v12.2 audit identified as missing.

## Tier

**T1 (consistency check)** — this is a direct test of the geometric-lock condition that defines the kinematic frame of the framework. Failure here propagates to T2, T3, T4 (since they all assume universal coherent scaling).

## Physics rationale

The proton mass receives ≈99% of its value from the QCD trace anomaly (gluon dynamics, quark-antiquark condensates) and ≈1% from quark current masses (Higgs VEV). The electron mass is entirely from the Higgs VEV.

Under non-universal σ-coupling — for instance, σ couples to the QCD coupling g_s with one strength and to the Higgs sector with a different strength — the ratio μ would acquire σ-dependence. The resulting μ̇/μ would be a calculable function of σ̇/σ and the differential coupling.

Under STRICT universal coherent scaling (the canonical GSC framework), all dimensionless particle-physics ratios are σ-invariant. μ is one of the most precisely measured of these (current bound at the 10⁻¹⁷/yr level), making it a sharp test of the universality assumption.

## Pipeline

To be implemented as `scripts/predictions_compute_P9.py`. Outputs:

- Predicted μ̇/μ (= 0 under universal scaling)
- Predicted Δμ/μ at z = 0.7, 1.0, 2.0, 3.0 (= 0 under universal scaling)
- Comparison band against current observational bounds

The compute is trivial under universal scaling (the prediction is 0). The pipeline records the prediction structure so that future relaxations to non-universal coupling can be scored against the same data.

## Target observation

- **Laboratory:** HD⁺ ion-trap spectroscopy at PTB (Patra et al. 2020, μ̇/μ < 5×10⁻¹⁷/yr); MPQ subsequent improvements.
- **Cosmological:** H₂ Lyman/Werner-band absorbers in quasar spectra (Ubachs, Bagdonaite et al.); CH₃OH absorbers (Kanekar et al.) at PKS 1830-211 (z ≈ 0.89).
- **Future:** improved HD⁺ Doppler-free spectroscopy could push laboratory bound to ~10⁻¹⁹/yr by 2030.

## Scoring algorithm

For each observed bound or measurement of |Δμ/μ|:

```
z_score = |μ̇/μ_observed - 0| / σ_obs
```

PASS if |z_score| < confidence threshold. The framework's prediction is 0; passing means the observed bound is consistent with 0 (which it currently is at all redshifts).

A *detection* of non-zero μ̇/μ at any significance would FAIL the prediction and trigger the non-universal-coupling extension analysis (similar to P3's non-universal opt-in mode).

## Effort estimate

≈ 1 day for the trivial null-prediction pipeline; ≈ 3 days to add the non-universal-coupling exploration mode for parallel constraint analysis.

## Significance

P9 is the most precise test of GSC's geometric-lock condition currently available. The bound on μ̇/μ at the 10⁻¹⁷/yr level constrains any non-universal σ-coupling between QCD and electroweak sectors at extremely high precision. If GSC is correct in its universal-scaling form, P9 PASSes by construction; if a measurement detects μ̇/μ ≠ 0, the universal-scaling assumption is falsified.

In the v12.1 cycle, P9 status is **a clean PASS** at current bounds. As bounds tighten, this is one of the framework's lowest-risk predictions.

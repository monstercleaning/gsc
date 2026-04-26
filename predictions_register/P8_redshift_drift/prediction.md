---
prediction_id: P8
title: Redshift-drift sign and amplitude (supporting discriminator)
tier: T2 (supporting only, not primary)
ansatz: σ(t) — late-time fit ansatz from Paper A
target_dataset: ELT/ANDES Sandage–Loeb redshift-drift measurements at z ≈ 2–5
target_release_date: ≥ 2040 (ELT/ANDES first-light + integration time)
status: SCAFFOLD — NOT YET SIGNED
signed_by: —
signature_timestamp: —
repo_commit_at_signing: —
pipeline_output_hash: —
---

# Prediction P8 — Redshift-drift sign and amplitude

## Statement

The redshift-drift `dz/dt = H_0(1+z) - H(z)` differs between GSC and ΛCDM at moderate-to-high redshift. For the registered σ(t) ansatz, the predicted Δv velocity drift (for an observation interval Δt = 10 yr) is calculable as:

```
Δv ≈ c · (dz/dt) / (1+z) · Δt
```

at each redshift z. The historical GSC framing was that the *sign* of dz/dt at z ≈ 2–5 differs between GSC accelerated-collapse models and ΛCDM. **This is now framed as a *supporting* test, not the primary discriminator.** The primary near-term discriminators are P1 (BAO ruler shift) and the P4+P5 strong-CP joint consistency.

## Tier

**T2 (supporting only)** — refines the late-time σ(t) ansatz but is not in the primary kill-test path. P1 and P4+P5 will resolve the framework's status well before ELT/ANDES delivers drift measurements.

## Pipeline

Already implemented in the existing late-time pipeline. New computation:

1. Script `scripts/predictions_compute_P8.py` — wraps `scripts/redshift_drift_table.py` to produce dz/dt(z) and Δv(z, Δt=10yr) for the registered σ(t).
2. The output is a tabulated prediction at z = 0.1, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0.

## Target observation

- **ELT/ANDES:** Sandage–Loeb test, expected first integrated-time results ≥ 2040.
- **Earlier proxies:** none currently competitive.

## Scoring algorithm

When ELT delivers Δv(z) measurements, score as:

```
z_chi2 = Σ_z [(Δv_observed(z) - Δv_predicted(z))^2 / σ(z)^2]
```

Pass if χ²/dof is within registered band.

The *sign-flip* at high z (z > 3) is the historical "killer" indicator: ΛCDM expects `dz/dt < 0`; some GSC realizations expect `dz/dt > 0`. This sign-flip is *retained* as a structural prediction even though it is no longer framed as the primary discriminator.

## Effort estimate

Trivial (~3 days) — wraps existing implementations.

## Significance

P8 is the historical primary GSC discriminator, demoted in the current framework cycle to supporting status because:

1. Earlier release of P1 (DESI 2027) and P4+P5 (LiteBIRD 2030) will resolve the framework's status well before ELT/ANDES delivers (≥ 2040);
2. Refined late-time data have narrowed the parameter region in which GSC predicts a sign-flip at z ≈ 2–5;
3. Confidence in any specific pre-registered amplitude depends on choices that may evolve over the 15-year run-up.

It is retained as P8 because:

1. The sign-flip remains a clean, falsifiable, *structural* prediction;
2. Pre-registering it now provides historical record of what GSC predicted before the data;
3. ELT/ANDES will test it eventually regardless of whether GSC is the focus by then.

**Pre-register but do not weight as primary.**

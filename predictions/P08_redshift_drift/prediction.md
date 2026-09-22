---
prediction_id: P8
revision: r2
title: Redshift drift — ΛCDM-degenerate consistency test at foreseeable precision (r2, v12.7)
tier: T2 (supporting only; no framework-specific discriminating power)
ansatz: σ(t) powerlaw metrology exponent (canonical p) applied to a flat-ΛCDM background — SigmaModulatedLCDMHistory
target_dataset: ELT/ANDES Sandage–Loeb redshift-drift measurements at z ≈ 0.1–5 (first direct ESPRESSO limits already exist)
target_release_date: ≥ 2040 (ELT/ANDES first-light + integration time)
status: SCAFFOLD — git-timestamped, GPG-signing pending; FORWARD registration (awaiting unreleased data); REVISION r2 supersedes r1 (see below)
supersedes: r1 (pipeline_output.r1_superseded.json) — computed with the v10.1 coasting toy history; withdrawn v12.7
signed_by: —
signature_timestamp: —
repo_commit_at_signing: —
pipeline_output_hash: —
---

# Prediction P8 — Sandage–Loeb redshift drift (revision r2, v12.7)

## Why there is a revision r2 (correction disclosed in full)

The r1 entry (v12.2–v12.6) registered a structural claim, quoted here as history [r1 — superseded]:

> [r1 — superseded] *"for the canonical ansatz the drift is positive across the grid,*
> [r1 — superseded] *in contrast to ΛCDM's sign flip near z ≈ 1.7; the sign-flip is*
> [r1 — superseded] *retained as a structural prediction."*

Those numbers were produced by feeding the canonical T2
metrology exponent p = 6×10⁻⁴ into `PowerLawHistory`, the v10.1 toy in which
the same letter is the **whole expansion law**, H(z) = H₀(1+z)^p. At that p
the toy is a coasting universe (H ≈ H₀), which the DESI DR1 BAO points bundled
with this package exclude at +7σ (D_M/r_d, z = 0.51) to +128σ (D_H/r_d,
z = 2.33) — and which contradicts the framework's own T1 statement of conformal
equivalence to ΛCDM. The project's archived Roadmap v2.8 §E.1 had already shown
that positive drift at z > 2 is impossible for standard matter content
(Ω_m0 < 1/(1+z) would be required); the v12 layout lost that result, and the
v12.5 "single source of truth" refactor wired P8 to the shared constant
without checking its role.

Per the append-only discipline the r1 output is **retained** as
`pipeline_output.r1_superseded.json` (its SHA-256 is recorded inside the r2
output under `supersedes`), and it can be reproduced with the loudly-named
provenance option `--ansatz coasting_toy_r1_superseded`. Nothing was deleted;
the claim is withdrawn.

## Statement (r2)

> **Editorial flag (added at the reorganization; the registered statement below is unchanged):** the history below is described as "the same p that P1 applies"; computed consistently it moves the BAO ruler in the opposite direction to P1. The conclusion — no framework-specific discriminating power — is unaffected. See OPEN_PROBLEMS.md, problem 2.

The T2-consistent late-time history is flat ΛCDM with the leading-order
σ-metrology modulation — the same p that P1 applies to the BAO ruler:

```
H(z) = H_ΛCDM(z) · (1+z)^p ,   p = 6×10⁻⁴   (SigmaModulatedLCDMHistory)
dz/dt = H₀(1+z) − H(z) ,      Δv ≈ c · (dz/dt)/(1+z) · Δt
```

For a 10-year interval the registered table (`pipeline_output.json`) gives, at
every grid point z ∈ {0.1, 0.5, 1, 1.5, 2, 3, 4, 5}:

- |Δv_GSC − Δv_ΛCDM| ≤ 0.03 cm/s (maximum at z = 5);
- identical sign structure — both flip from positive to negative between
  z = 1.5 and z = 2.0;
- relative deviations sub-percent away from ΛCDM's zero crossing (relative
  values are ill-defined near z ≈ 2, where the absolute difference is
  0.014 cm/s).

**P8 therefore carries no framework-specific discriminating power at any
foreseeable precision** (first direct ESPRESSO limits: ±3.6 m/s/yr,
arXiv:2603.02318; ELT/ANDES targets of order cm/s per decade). It is a
ΛCDM-degenerate consistency test.

## Tier

**T2 (supporting only).** The drift is a genuine observable and remains
registered because its data are unreleased, but it can fail only if ΛCDM-class
kinematics fail — in which case it falsifies T1/T2 exactly as it falsifies
ΛCDM, with no rescue permitted.

## Pipeline

- `pipelines/predictions_compute_P8.py` (v0.2) — default ansatz
  `powerlaw_metrology`; schema `predictions_p8_pipeline_output_v2`.
- Provenance reproduction of r1: `--ansatz coasting_toy_r1_superseded`
  (never the default; not the registered prediction).

## Scoring algorithm (registered)

When ELT/ANDES delivers Δv(z) measurements:

```
z_chi2 = Σ_z [(Δv_observed(z) − Δv_predicted(z))² / σ(z)²]
```

Pass if χ²/dof is within the registered band; because Δv_predicted equals the
ΛCDM prediction to 0.03 cm/s, a PASS or FAIL for P8 is a PASS or FAIL for
ΛCDM-class kinematics.

## Kill-test

A robust drift measurement inconsistent with the ΛCDM-class sign structure at
z ≥ 2 falsifies T1/T2 outright — and ΛCDM with it. No tier-demotion,
non-universal extension, or unimplemented correction may be invoked.

## Significance

The honest value of P8 after r2 is negative-space: it demonstrates that the
framework's late-time content beyond ΛCDM is confined to the BAO metrology
shift (P1) and the exact-null package (P9, P11, P12, P13), and it documents —
mechanically, via the new verification/claims.json guards — the class of error that produced
r1: one symbol feeding two incompatible models. The pre-v12.7 description of
P8 as a "clean structural falsifier" is withdrawn [r1 — superseded].

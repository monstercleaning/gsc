---
prediction_id: P15
title: Milgrom's acceleration scale follows the dark-energy density — a0 at z = 3 is 0.74 (0.63–0.78) of today's
tier: T4 (MOND-like phenomenology, THEORY.md §6.2)
ansatz: a0(z)/a0(0) = sqrt(rho_DE(z)/rho_DE(0)), with DESI DR2's dark-energy histories (CPL; four data combinations; DESI+CMB+DESY5 central)
target_dataset: radial-acceleration-relation fits of galaxy rotation curves at median redshift z ≥ 2 (ALMA, JWST, VLT), including same-survey comparisons with a lower-redshift bin
target_release_date: continuous (each new determination of a0 at z ≥ 2 scores it)
status: SCAFFOLD — git-timestamped, GPG-signing pending; FORWARD registration (v20.2; suggested by the RC100 trend at z = 0.6–2.5, which therefore cannot score it)
signed_by: —
signature_timestamp: —
repo_commit_at_signing: —
pipeline_output_hash: —
---

# Prediction P15 — Milgrom's acceleration scale follows the dark-energy density (registered v20.2)

## Statement

Galaxies show dark matter only below an acceleration a0 ≈ 1.2 × 10⁻¹⁰ m/s², the scale of the radial acceleration
relation (McGaugh, Lelli & Schombert, PRL 117, 201101, 2016). Its value is close to c √Λ. Read as a link to the
dark-energy density rather than to the expansion rate (a0 ∝ H(z) is excluded by 100 rotation curves at z = 0.6–2.5,
[OPEN_PROBLEMS.md](../../OPEN_PROBLEMS.md) problem 11), a0 follows the dark energy:

```
a0(z) / a0(0)        = sqrt(rho_DE(z) / rho_DE(0))
rho_DE(z) / rho_DE(0) = (1 + z)^(3 (1 + w0 + wa)) exp(-3 wa z / (1 + z))
```

with (w0, wa) fixed at DESI DR2's four published fits (arXiv:2503.14738 v3, eqs. 25–28): DESI+CMB (−0.42, −1.75),
DESI+CMB+Pantheon+ (−0.838, −0.62), DESI+CMB+Union3 (−0.667, −1.09) and DESI+CMB+DESY5 (−0.752, −0.86). The spread over
the four is the registered band; DESI+CMB+DESY5 gives the central value. The registered values, computed by
`pipelines/predictions_compute_P15.py`:

| z | a0(z)/a0(0), central | Band |
|---|---|---|
| 2.22 | 0.83 | 0.78–0.85 |
| 3 | 0.74 | 0.63–0.78 |
| 4 | 0.64 | 0.48–0.70 |
| 5 | 0.57 | 0.38–0.63 |

Within one survey measured with one method, a0 at z = 2.22 over a0 at z = 0.83 is 0.81 (0.69–0.84).

## What this prediction is and is not

- **It distinguishes between readings.** At z = 3, a constant a0 gives 1, a0 ∝ H(z) gives 4.57, ΛCDM simulations
  give a rise (Mayer et al., arXiv:2206.04333: about 3 times by z = 2), and this prediction gives 0.63–0.78.
- **It was suggested by the data it cannot use.** On the 100 RC100 rotation curves the same shape fits better than a
  constant a0 in every variant tried, weakly (about 2σ at most; [analyses/a0_evolution.md](../../analyses/a0_evolution.md)).
  RC100 is therefore not scored.
- **It is contradicted by the one sample in which a0 rises.** Ciocan et al. (A&A 709, L16, 2026) find a0 rising by
  about 2 times over z = 0.33–1.44, where this prediction gives a change by a factor of 0.85–0.91. The same sample
  contradicts every universal a0(z), including a constant, and disagrees with RC100 where the two overlap; that
  conflict is unresolved. It lies below the scored range and predates this registration.
- **It depends on DESI DR2's dark energy**, whose evolution is itself 2.8–4.2σ. With a true cosmological constant the
  same idea gives a constant a0, and a precise enough determination would score that as a FAIL of this entry.
- **It is not unique to GSC.** It is Milgrom's a0 ≈ c √Λ combined with DESI's dark energy. What GSC adds is the
  reading of a0 as set by the dark-energy part of the cosmic shrinking rate, and the registration.

## Tier

T4, the MOND-like phenomenology module of THEORY.md §6.2 (an evolving scale). The GSC core (T1–T3) does not depend on
it, and kill condition K0 is unchanged.

## Pipeline

`pipelines/predictions_compute_P15.py` evaluates the formula above for the registered dark-energy histories; it fits
nothing. Output: `pipeline_output.json` (schema `predictions_p15_pipeline_output_v1`), deterministic, standard
library only.

## Current observational status (not scored)

- **RC100** (Nestor Shachar et al., ApJ 944, 78, 2023; 100 disks at z = 0.6–2.5): a0 at z ≈ 2.2 over a0 at z ≈ 0.8 is
  0.63 (0.51–0.77), against 0.69–0.84 predicted. It suggested the prediction and is not scored.
- **Ciocan et al. 2026** (79 galaxies at z = 0.33–1.44): contradicts it, as described above.
- **Rotation curves at z ≈ 4–5** from ALMA exist for a few galaxies. They were not examined before this registration
  and will be checked afterwards, as a retrodictive test.

## Scoring algorithm

For each published determination of the relation's acceleration scale from rotation curves of at least 10 galaxies
with median redshift z ≥ 2:

```
r_obs = a0(z) / a0_ref ± σ          (1σ; for asymmetric errors, the side facing the band)
d     = distance from r_obs to the registered band at that redshift (0 inside it)
z     = d / σ
```

a0_ref is the same method's value at z ≤ 0.1, or its value in a lower-redshift bin of the same survey (the
prediction is then the ratio of the formula at the two median redshifts), or else the canonical 1.20 ± 0.24, whose
uncertainty is added to σ.

- **FAIL** if z ≥ 3 for any scored determination.
- **PASS** if z < 3 for every scored determination and at least one has σ ≤ (1 − upper band edge)/2, so that it can
  tell the prediction from a constant a0.
- **SUB-THRESHOLD** if z < 3 everywhere but no determination is yet that precise.

Only determinations published after this registration count.

## Kill-test

If P15 fails, a0 is not set by the dark-energy density in this form, and the evolving MOND-like scale of THEORY.md
§6.2 loses its registered form. The GSC core (T1–T3) is unaffected.

## Significance

This is the only registered link between the two dark components. If it passes, dark energy sets the scale at which
galaxies show dark matter. It is sharp: no free shape parameter, and a fall of a quarter to a half by z ≈ 3–5, which neither
a constant a0 nor ΛCDM simulations predict.

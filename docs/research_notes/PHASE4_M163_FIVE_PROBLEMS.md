# Phase4 M163 — Five Problems Integration (Research Note)

Status: research note only. This document is not peer-reviewed and is not an end-to-end cosmology claim.

## Scope and claim discipline

This note records a deterministic Phase-4 diagnostic that integrates three checks:

1. Kinetic-barrier behavior for the toy scalar-tensor coupling
   `F(sigma)=1-(sigma_star/sigma)^2`.
2. Numerical scale-separation estimate around `k_star` derived from `Lambda_QCD`.
3. Honest CHW2018 tension recalculation for a barely-positive-drift toy deformation.

Non-claims:

- This is not a full action-derived cosmological fit.
- This is not a full CMB likelihood analysis.
- A toy redshift-window deformation is not treated as a derived prediction.

## What is new in M163

- The previous informal "53 sigma" style wording is replaced by explicit, reproducible computation against CHW2018 `sigma_R`.
- The new diagnostic uses repo-native the current framework modules (`gsc.early_time`, `gsc.datasets.cmb_priors`) and emits schema-validated JSON/MD artifacts.
- Output is deterministic (`created_utc` pin), portable (`paths_redacted=true`), and unittest-covered.

## Key interpretation points

### 1) Kinetic barrier

The canonicalization check computes

`(dphi/dsigma)^2 = (3/2)*(d ln F/dsigma)^2 + omega0/F`.

As `sigma -> sigma_star+`, the canonical distance grows and acts as a barrier in this toy setup.

### 2) Scale separation

Using `Lambda_QCD=0.2 GeV`, the implied `k_star` is extremely UV compared with cosmological `k` values (`H0`, CMB, BAO, galaxy), and the report tabulates `log10((k/k_star)^2)` explicitly.

### 3) Barely positive drift vs CHW2018

For the diagnostic toy background

- `H(z)=0.99*H0*(1+z)` in `z in [2,5]`,
- LCDM+rad elsewhere,
- `r_s_star` held at LCDM baseline for this late-time-only deformation,

the report computes `R_toy` and `lA_toy`, then evaluates

`n_sigma_R = (R_toy-R_mean)/sigma_R` with CHW2018 values from
`data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv`.

With default settings (`drift_eps=0.01`, diagonal mode), the diagnostic gives
`n_sigma_R ~ 13` (order-of-magnitude O(10), not O(50)).

## How to reproduce

```bash
python3 scripts/phase4_m163_five_problems_report.py \
  --outdir out/m163_five_problems \
  --format text \
  --created-utc 946684800 \
  --sigma-star-ratio 0.85 \
  --omega0 500 \
  --lambda-qcd-gev 0.2 \
  --drift-eps 0.01 \
  --z-drift-min 2 \
  --z-drift-max 5 \
  --use-cov 0

python3 scripts/phase2_schema_validate.py \
  --auto \
  --schema-dir schemas \
  --json out/m163_five_problems/FIVE_PROBLEMS_REPORT.json
```

Expected artifacts:

- `FIVE_PROBLEMS_REPORT.json`
- `FIVE_PROBLEMS_REPORT.md`

Schema id:

- `phase4_m163_five_problems_report_v1`

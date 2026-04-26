# Redshift Drift Data (v11.0.0)

This folder contains small CSV datasets for the Sandage–Loeb (redshift drift)
observable used in the late-time scorecard.

## Notes

### Canonical CSV Contract

- Required columns:
  - `z`
  - `dv_cm_s` (signed; accumulated over the baseline)
  - `sigma_dv_cm_s`
- Baseline:
  - preferred: `baseline_years` (per-row)
  - accepted alias: `baseline_yr`
  - alternatively: omit the baseline column and provide it via CLI (only if the loader is told a scalar baseline)
- Units:
  - `dv_cm_s` is the accumulated spectroscopic velocity drift Δv in **cm/s** over the specified baseline
  - i.e. do **not** store "cm/s per year" in `dv_cm_s` (that would double-count baseline in the model)

Optional columns (ignored by the loader): `label`, `source`, `note`, etc.

## Files

- `trost_2025_lcdm_benchmark.csv`
  - A **benchmark expectation** for ΛCDM quoted in Trost et al. (A&A 699, A159, 2025),
    used as a sanity check / reproducibility target (not an observed detection).
- `elt_andes_liske_conservative_20yr_asimov.csv`
  - A **canonical forecast input** (Asimov; noiseless) meant to be
    publication-defensible as a standard Sandage–Loeb "ELT/ANDES-like" scenario.
  - Bins: z = 2.0, 2.5, 3.0, 3.5, 4.5; baseline = 20 yr.
  - Uses a standard Liske/ELT-style `sigma_dv_cm_s(z)` scaling (see `make_drift_forecast.py`).
- `elt_andes_liske_conservative_10yr_asimov.csv`
  - Same as above, but with baseline = 10 yr (signal halves; `sigma_dv_cm_s(z)` unchanged).
- `elt_andes_liske_conservative_20yr_mock_seed123.csv`
  - Same scenario, but with deterministic Gaussian noise added (seed=123).
- `andes_20yr_mock_lcdm_fiducial.csv`
  - A **legacy synthetic/mock** dataset used earlier to exercise the pipeline
    with an illustrative constant `σ=1 cm/s` per bin.

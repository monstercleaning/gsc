# Structure dataset notes (`f\sigma_8` diagnostic)

This directory contains a small reference CSV used by the stdlib diagnostic
scripts in `v11.0.0/scripts/phase2_sf_fsigma8_report.py` and Phase-2 overlay
wiring.

## File

- `fsigma8_gold2017_plus_zhao2018.csv`

## What it is

A compact `f\sigma_8` point compilation used for diagnostic-level linear-growth
comparisons (not a survey-complete likelihood).

## Sources / provenance

- Gold-2017 growth-rate compilation context, as summarized in:
  - Nesseris et al., *Internal Robustness of Growth Rate data*, arXiv:1806.10822
- Zhao et al. 2018 updates included in the same compilation context.
- Individual point `ref_key` values in the CSV provide row-level trace labels.

## Usage note

Values in this CSV are transcribed from published tables/compilations for
reproducible diagnostics. The repository does not claim this as an original
survey dataset release.

## Column schema

- `z`: redshift
- `fsigma8`: observed `f\sigma_8` value
- `sigma`: 1-sigma uncertainty (diagonal treatment in current diagnostic mode)
- `omega_m_ref`: reference `\Omega_m` used by source analysis (for optional AP-like correction)
- `ref_key`: short source marker

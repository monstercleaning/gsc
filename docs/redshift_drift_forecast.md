# Redshift Drift Forecast (Diagnostic; Systematic Floor)

**Status:** Diagnostic-only note (out of submission scope).

This module provides a coarse answer to: **"When will redshift-drift become decisive?"**

It compares the predicted Sandage–Loeb **velocity drift** `Δv(z)` between two background
histories (default: `ΛCDM` vs `GSC transition`) and computes a simple Fisher-style
significance as a function of the baseline duration (years), assuming a per-bin
uncertainty with a **systematic floor**:

- `σ_tot = sqrt(σ_stat^2 + σ_sys^2)`
- `significance(years) = sqrt( Σ_i [ (Δv_A(z_i; years) - Δv_B(z_i; years)) / σ_tot ]^2 )`

This is **not** an exposure-time calculator; it is a diagnostic scaling tool with an
explicit floor parameter.

## How To Reproduce

```bash
bash scripts/reproduce_v10_1_drift_forecast_diagnostic.sh --sync-paper-assets
```

Outputs:

- `results/diagnostic_drift_forecast/`
  - `tables/significance_vs_years.csv`
  - `figures/significance_vs_years.png` (if matplotlib is available)
  - `manifest.json`
- `paper_assets_drift_forecast_diagnostic/` (opt-in snapshot for sharing)

## Interpretation (Diagnostic Only)

- A non-zero `σ_sys` acts as a floor on per-bin `Δv` precision. Increasing the baseline
  increases the signal roughly linearly, so the forecasted significance grows with time,
  but at a rate set by `σ_tot`.
- This module is intended to help answer reviewer-facing "timeline" questions without
  putting instrument-performance claims into the submission PDF.


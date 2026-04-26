# Distance Duality (Etherington Reciprocity) — diagnostic module

**Status:** Diagnostic-only (opt-in).  
**Not part of submission scope.** This does not modify the canonical late-time pipeline outputs.

## Goal

Treat distance duality as a **testable hypothesis** by fitting a single deviation parameter from
late-time SN+BAO consistency.

We introduce:

`D_L(z) = (1+z) * D_M(z) * (1+z)^{epsilon_dd}`

Equivalently, for SN distance modulus:

`mu_th(z; epsilon_dd) = mu_th(z; 0) + 5 * epsilon_dd * log10(1+z)`.

`epsilon_dd = 0` corresponds to the baseline distance-duality relation.

## What is fitted (and what is not)

For each `epsilon_dd`, the diagnostic profiles analytically over:

- SN nuisance `delta_M` (additive magnitude offset)
- BAO nuisance `r_d` (sound-horizon scale, treated as late-time nuisance at the current framework scope)

No early-time microphysics is assumed; this is a late-time consistency test.

## How to run

One command:

```bash
bash scripts/reproduce_v10_1_distance_duality_diagnostic.sh --sync-paper-assets
```

Outputs:

- `results/diagnostic_distance_duality/` (tables/figures/manifest)
- `paper_assets_distance_duality_diagnostic/` (synced view; opt-in)
- `paper_assets_distance_duality_diagnostic_r0.zip` (gitignored release asset)

## Outputs

- `tables/chi2_vs_epsilon_dd.csv` (chi2_total, chi2_sn, chi2_bao, profiled nuisances)
- `figures/chi2_vs_epsilon_dd.png` (Δchi² relative to best-fit)
- `manifest.json` (strict JSON provenance; repo-relative paths)

## Interpretation (diagnostic-only)

- If best-fit `epsilon_dd` is consistent with 0 and `Δchi²(eps=0)` is small, distance duality is
  consistent with the SN+BAO dataset under the chosen late-time history.
- If best-fit is significantly away from 0, this flags either:
  - a real deviation from distance duality, or
  - a modeling/systematics mismatch (e.g. SN calibration, selection effects, BAO systematics).

This module is a *risk/consistency diagnostic* and is not a submission claim.


# SN Two-Pass Sensitivity (Diagnostic-Only)

This diagnostic checks whether diagonal-SN prefiltering (`two-pass`: diag -> fullcov)
can miss the global full-covariance best point on representative grids.

## What is tested

- Models: default `lcdm` and `gsc_transition`.
- Scoring: total chi2 with SN (diag + fullcov), BAO nuisance profiling, optional drift contribution.
- Two-pass sensitivity points: `two_pass_top in {60, 200, 500}` by default.
- Key metric: rank position of the global fullcov best point in diagonal ordering.

## Outputs

- `results/diagnostic_sn_two_pass_sensitivity/tables/sn_two_pass_sensitivity.csv`
- `results/diagnostic_sn_two_pass_sensitivity/tables/sn_two_pass_points.csv`
- `results/diagnostic_sn_two_pass_sensitivity/figures/chi2_best_vs_two_pass_top.png`
- `results/diagnostic_sn_two_pass_sensitivity/figures/best_rank_position_vs_two_pass_top.png`
- `results/diagnostic_sn_two_pass_sensitivity/manifest.json`

## Reproduce

```bash
bash scripts/reproduce_v10_1_sn_two_pass_sensitivity_diagnostic.sh --sync-paper-assets
```

Asset ZIP (diagnostic pre-release line):

- `paper_assets_sn_two_pass_sensitivity_diagnostic_r0.zip`

## Practical interpretation

- If `delta_chi2_to_global` is near zero for moderate `two_pass_top`, the two-pass approximation is stable
  on the tested grid.
- If the global fullcov best has very poor diagonal rank and is repeatedly excluded for practical `two_pass_top`,
  that indicates a ranking-risk region to track in roadmap work.
- This module is diagnostic only and does not change canonical late-time pipeline defaults.

# Early-Time E2 Executive Summary (Diagnostic-Only)

Scope statement:
This note summarizes the E2 bridge/full-history diagnostics as a reviewer-facing evidence layer.
It does **not** change canonical late-time claims or submission scope. Early-time/CMB closure remains
an opt-in diagnostic/Phase-2 topic in the current framework.

## Key Findings (WS7-WS13)

- Distance-budget diagnostics localize the non-degenerate mismatch mainly to the low handoff interval
  `z in [2,5]`, with representative `Delta D_M(z*)` dominated there (diagnostic split), not at `z>5`.
- Full-history fast relax can reduce no-fudge CMB tension, but when relax starts too low it contaminates
  the drift discriminator window (`z~2-5`) by flipping or degrading the positive-drift signature.
- Guarded relax (start after drift window) preserves drift sign but typically fails to close strict CHW2018
  no-fudge chi2 in tested families (diagnostic no-go trend).
- High-z post-recombination H-boost-only repair can improve `l_A`, but `R` / `D_M(z*)` remains the hard
  constraint; delaying repair start too high leaves insufficient integral lever arm.
- Neutrino-sector knobs (`Delta N_eff`-style) primarily rebalance `r_s(z*)`; they do not remove the core
  distance-closure requirement in `D_M(z*)` in tested setups.
- Closure mapping (`dm_fit -> A_required`) is transparent and quantitative: representative `dm~0.93` implies
  moderate `A` if repair starts near `z~5`, but rapidly larger `A` as start is pushed to `z~10+`.
- Consolidated WS13 result: “repair-start too high” is practical no-go in the tested deformation family;
  either closure starts near low handoff (`z~5`) or requires richer early-time physics.

## Core E2 Diagnostic Artifacts (Recommended)

| Module | Tag | Asset | SHA256 |
|---|---|---|---|
| WS7.1 full-history no-stitch closure | [`v10.1.1-bridge-e2-full-history-closure-diagnostic-r1`](https://github.com/morfikus/GSC/releases/tag/v10.1.1-bridge-e2-full-history-closure-diagnostic-r1) | `paper_assets_cmb_e2_full_history_closure_diagnostic_r1.zip` | `2ca99a88b4f583dc6d79d12bc28dc8d36b6f6171d249f3f44d01f6912f93e350` |
| WS11 guarded-relax drift-safe scan | [`v10.1.1-bridge-e2-full-history-guarded-relax-diagnostic-r0`](https://github.com/morfikus/GSC/releases/tag/v10.1.1-bridge-e2-full-history-guarded-relax-diagnostic-r0) | `paper_assets_cmb_e2_full_history_guarded_relax_diagnostic_r0.zip` | `3dc84a29ae55e422b4b61779f7e63dbdcc5a6d0ca838c4a9a5a865f92aa45640` |
| WS12 z* / recombination definition audit | [`v10.1.1-bridge-e2-zstar-recombination-audit-r0`](https://github.com/morfikus/GSC/releases/tag/v10.1.1-bridge-e2-zstar-recombination-audit-r0) | `paper_assets_cmb_e2_zstar_recombination_audit_diagnostic_r0.zip` | `335ac75b64160b5a2524dc7c86deb06e0124b06a92c90ef2196e8289184c5707` |
| WS13 closure requirements / no-go map | [`v10.1.1-bridge-e2-closure-requirements-diagnostic-r0`](https://github.com/morfikus/GSC/releases/tag/v10.1.1-bridge-e2-closure-requirements-diagnostic-r0) | `paper_assets_cmb_e2_closure_requirements_r0.zip` | `dc0dffd51c12655bb3e2a093fd41e872ea996b8d96541198ac49d21d2a21bbd3` |

## Figure pointer

Use WS13 consolidation plot:

- `paper_assets_cmb_e2_closure_requirements/figures/A_required_vs_zstart.png`

This is the compact reviewer view for “closure requirement vs repair start redshift”.

## Next-step discipline

- Keep canonical late-time/submission bundles frozen.
- Keep E2 diagnostics opt-in with isolated outputs and manifest provenance.
- Treat E2 closure conclusions as diagnostic constraints on future physical model-building.

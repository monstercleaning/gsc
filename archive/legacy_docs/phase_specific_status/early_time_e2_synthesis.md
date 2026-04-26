# Early-Time E2 Synthesis (Referee Verdict, Diagnostic-Only)

Status: diagnostic consolidation for referee reading.  
Submission scope remains unchanged: canonical the framework claims are late-time; early-time/CMB closure is out of scope for the submission and tracked only through opt-in diagnostics.

Companion drill-down notes for the latest bounds:

- `docs/early_time_e2_drift_constrained_bound.md`
- `docs/early_time_e2_closure_to_physical_knobs.md`

## Scope statement

The the current framework submission remains late-time and drift-first. Early-time/CMB diagnostics are included to quantify what closure would require, not to claim a solved early-time model. All entries below are diagnostic tags/assets and do not alter frozen artifacts (`v10.1.1-late-time-r4`, `v10.1.1-submission-r2`, `v10.1.1-referee-pack-r4`).

## What we tested

| Module | Release tag | Asset | SHA256 | Reproduce entrypoint |
|---|---|---|---|---|
| WS13 closure requirements / no-go map | [`v10.1.1-bridge-e2-closure-requirements-diagnostic-r0`](https://github.com/morfikus/GSC/releases/tag/v10.1.1-bridge-e2-closure-requirements-diagnostic-r0) | `paper_assets_cmb_e2_closure_requirements_r0.zip` | `dc0dffd51c12655bb3e2a093fd41e872ea996b8d96541198ac49d21d2a21bbd3` | `bash scripts/reproduce_v10_1_e2_closure_requirements.sh --sync-paper-assets` |
| E1.3 distance-budget diagnostic | [`v10.1.1-bridge-e1.3-diagnostic-r3`](https://github.com/morfikus/GSC/releases/tag/v10.1.1-bridge-e1.3-diagnostic-r3) | `paper_assets_cmb_e13_diagnostic_r3.zip` | `cd04c04f0574039f303f9b52ef2d32b9b0f67a9bc86180dea9a452fb4b4f3dee` | `bash scripts/reproduce_v10_1_late_time_e1_3_diagnostic.sh --sync-paper-assets` |
| Drift↔closure correlation (WS1.2) | [`v10.1.1-bridge-e2-drift-cmb-correlation-r2`](https://github.com/morfikus/GSC/releases/tag/v10.1.1-bridge-e2-drift-cmb-correlation-r2) | `paper_assets_cmb_e2_drift_cmb_correlation_r2.zip` | `db213280f9d5c9fb2b9b0efe236b2a353ce9f1e34612e2a6a07576bdfe344fa1` | `bash scripts/reproduce_v10_1_e2_drift_cmb_correlation.sh --sync-paper-assets` |
| Full-history closure (no-stitch, r1) | [`v10.1.1-bridge-e2-full-history-closure-diagnostic-r1`](https://github.com/morfikus/GSC/releases/tag/v10.1.1-bridge-e2-full-history-closure-diagnostic-r1) | `paper_assets_cmb_e2_full_history_closure_diagnostic_r1.zip` | `2ca99a88b4f583dc6d79d12bc28dc8d36b6f6171d249f3f44d01f6912f93e350` | `bash scripts/reproduce_v10_1_e2_full_history_closure_diagnostic.sh --sync-paper-assets` |
| Guarded-relax (drift-protected, WS11) | [`v10.1.1-bridge-e2-full-history-guarded-relax-diagnostic-r0`](https://github.com/morfikus/GSC/releases/tag/v10.1.1-bridge-e2-full-history-guarded-relax-diagnostic-r0) | `paper_assets_cmb_e2_full_history_guarded_relax_diagnostic_r0.zip` | `3dc84a29ae55e422b4b61779f7e63dbdcc5a6d0ca838c4a9a5a865f92aa45640` | `bash scripts/reproduce_v10_1_e2_full_history_guarded_relax_diagnostic.sh --sync-paper-assets` |
| High-z H-boost repair (WS13/E2.10) | [`v10.1.1-bridge-e2-highz-hboost-repair-diagnostic-r0`](https://github.com/morfikus/GSC/releases/tag/v10.1.1-bridge-e2-highz-hboost-repair-diagnostic-r0) | `paper_assets_cmb_e2_highz_hboost_repair_diagnostic_r0.zip` | `fde266f0bf4347185f1027eca07b9f736b3e1eb8e705200c49cfd7bfd5d59039` | `bash scripts/reproduce_v10_1_e2_highz_hboost_repair_diagnostic.sh --sync-paper-assets` |
| Drift-constrained closure bound (WS14/E2.10) | [`v10.1.1-bridge-e2-drift-constrained-closure-bound-r0`](https://github.com/morfikus/GSC/releases/tag/v10.1.1-bridge-e2-drift-constrained-closure-bound-r0) | `paper_assets_cmb_e2_drift_constrained_closure_bound_r0.zip` | `215d0573a9b4bac4c69051838a781d6c8242fe2822836da795771bfb47e292f2` | `bash scripts/reproduce_v10_1_e2_drift_constrained_closure_bound.sh --sync-paper-assets` |
| Closure->physical knobs (WS15/E2.11) | [`v10.1.1-bridge-e2-closure-to-physical-knobs-r0`](https://github.com/morfikus/GSC/releases/tag/v10.1.1-bridge-e2-closure-to-physical-knobs-r0) | `paper_assets_cmb_e2_closure_to_physical_knobs_r0.zip` | `cc3bd5bf13e7ac5a3b21dad0f223d407e1a25ef360ee08f88469493a32507986` | `bash scripts/reproduce_v10_1_e2_closure_to_physical_knobs.sh --sync-paper-assets` |
| Neutrino knob (WS5/E2.6) | [`v10.1.1-bridge-e2-neutrino-knob-diagnostic-r0`](https://github.com/morfikus/GSC/releases/tag/v10.1.1-bridge-e2-neutrino-knob-diagnostic-r0) | `paper_assets_cmb_e2_neutrino_knob_diagnostic_r0.zip` | `61451ad52aff2653cc07224213357f66613006b4b918d0f769e41343c8330c11` | `bash scripts/reproduce_v10_1_e2_neutrino_knob_diagnostic.sh --sync-paper-assets` |
| `r_s(z*)` numerics audit (WS10) | [`v10.1.1-bridge-e2-rs-star-numerics-audit-r0`](https://github.com/morfikus/GSC/releases/tag/v10.1.1-bridge-e2-rs-star-numerics-audit-r0) | `paper_assets_cmb_e2_rs_star_numerics_audit_r0.zip` | `f4ab8e51e2272178c568279ed10de3f6165f48ca06e1a02af82ffe8ead2cfbb4` | `bash scripts/reproduce_v10_1_rs_star_numerics_audit.sh --sync-paper-assets` |
| `z*` recombination audit (WS12/E2.9) | [`v10.1.1-bridge-e2-zstar-recombination-audit-r0`](https://github.com/morfikus/GSC/releases/tag/v10.1.1-bridge-e2-zstar-recombination-audit-r0) | `paper_assets_cmb_e2_zstar_recombination_audit_diagnostic_r0.zip` | `335ac75b64160b5a2524dc7c86deb06e0124b06a92c90ef2196e8289184c5707` | `bash scripts/reproduce_v10_1_e2_zstar_recombination_audit_diagnostic.sh --sync-paper-assets` |

## Key findings (diagnostic)

- The dominant `D_M(z*)` excess in non-degenerate bridge diagnostics is localized to `z in [2,5]`; this is the high-leverage failure localization.
- Mapping `dm_fit -> A_required` shows practical no-go behavior when repair starts too high: delaying repair to `z~10+` drives required deformation steeply upward.
- Full-history fast relax can reduce CMB closure tension but contaminates the late-time drift window (`z~2-5`) by flipping/eroding the sign discriminator.
- Guarded relax preserves drift sign in the protected window but, in tested families, cannot close strict CHW2018 no-fudge chi2 on its own.
- High-z-only H-boost repair can improve `lA`, but `R`/`D_M(z*)` remains the dominant bottleneck when repair starts too high.
- Drift-constrained Pareto scan shows a hard tradeoff: squeezing `Delta v(z=4)` toward `0+` still leaves strict CHW2018 chi2 at `O(10^4)` under the tested construction.
- Neutrino-sector knob mainly shifts `r_s(z*)`; it does not remove the dominant distance-closure requirement on `D_M(z*)`.
- Translating WS13 targets to effective physical knobs gives large required scales as repair start moves high: e.g. median `deltaG ~ 0.42` at `z_start=5` and `~0.67` at `z_start=10`.
- `r_s(z*)` stopgap mismatch is not primarily quadrature noise; numerics + recombination-method audits point to definition/compression + `z*` approximation effects.

## Assumptions behind E2 diagnostics

- CHW2018 compressed distance priors (`R`, `lA`, `omega_b_h2`) are used as a proxy objective, not as a full Boltzmann-likelihood replacement.
- Diagnostic families are explicit and finite: bridge scans, full-history relax, guarded-relax, high-z `H`-boost, drift-constrained Pareto deformation, and closure-target mappings.
- Drift checks use FLRW Sandage-Loeb kinematics: `dot(z)=H0(1+z)-H(z)` and `drift_sign_ok` is defined by positive drift in `z={2,3,4,5}` (plus dense guard where noted).
- No-fudge closure means `dm=1`, `rs=1` in strict distance-priors evaluation; fitted `dm_fit/rs_fit` are used only in clearly labeled diagnostic "what-would-it-take" modules.
- Distance and history mappings are exactly those encoded in the diagnostic scripts/manifests; no hidden priors or optimizer-only postprocessing is used.
- Conclusions are scoped to the tested families and assumptions above; they are not global impossibility proofs for all possible early-time models.

## WS14: Drift-Constrained Closure Bound (E2.10, diagnostic)

- Baseline point (`s=0`): `chi2_cmb ~= 8.32e4` and `Delta v(z=4,10y) ~= 4.53 cm/s`.
- Near drift-boundary point (`s=0.995`): `Delta v(z=4,10y) ~= 0.0227 cm/s`, but `chi2_cmb ~= 1.54e4`.
- All scan points keep `drift_sign_ok=True` (discrete `z={2,3,4,5}` and dense check on `[2,5]`).
- Referee takeaway: even with almost zero positive drift amplitude, strict CHW2018 closure remains catastrophic.
- This indicates a structural incompatibility under the tested deformation family, not just "too large drift amplitude".
- Companion analytic sanity bound (`Delta chi_min=(c/H0)ln2` for `z in [2,5]`) is documented in:
  `docs/early_time_e2_drift_bound_analytic.md`.

## WS15: Closure Requirements -> Physical Knobs (E2.11, diagnostic)

- Mapping used: `deltaG = A^2 - 1` (equivalently `delta rho/rho = A^2 - 1` in an effective bookkeeping sense).
- For `z_start=5`: median required scale is `deltaG ~= 0.420`.
- For `z_start=10`: median required scale is `deltaG ~= 0.666`.
- p90 values exceed unity when repair start is delayed, showing rapidly increasing deformation demand.
- Rule of thumb from tested targets: higher repair-start redshift implies larger `O(1)` effective deformation.

## What would have to change to reopen E2

- Replace compressed-prior proxy dependence with a full early-time observables pipeline (e.g. full CMB transfer/recombination treatment in freeze-frame-compatible variables).
- Introduce richer early-time dynamics beyond single-family post-recombination `H` deformations (while keeping drift-window constraints explicit).
- Reassess mapping assumptions only through explicitly versioned diagnostic modules (no hidden reinterpretation of existing `r4/r2/r4` frozen artifacts).
- If required, extend the drift observable modeling beyond the current background-level FLRW proxy in a separate, testable module.
- Any reopened branch must still satisfy the operational late-time discriminator contract (`drift_sign_ok` in the target window) or explicitly declare that contract dropped.

## Drift condition used operationally

For the FLRW Sandage-Loeb kinematic check:

`\dot z = H_0(1+z) - H(z)`, so positive drift requires `H(z) < H_0(1+z)`.

This sign condition is the late-time discriminator in the submission scope.

## E2 decision tree (diagnostic planning)

1. E2-A: Preserve positive drift in `z~2-5` as a hard constraint.
   Implication: pure high-z `H` repair families tested so far are insufficient; closure likely requires a richer mapping (distance law and/or beyond-background drift terms).
   Kill criterion: if required repair invades `z<5` and flips drift sign, this branch fails by design.
2. E2-B: Enforce strict CHW2018 compressed-prior mapping as-is.
   Implication: closure can be forced in some deformations, but drift-window contamination becomes a direct risk; sign flip becomes a concrete falsifier.
   Kill criterion: if all closures that reach low chi2 violate drift-sign guard in `z~2-5`, this branch is inconsistent with the late-time discriminator.
3. E2-C: Re-derive CMB observables in freeze-frame variables (technical companion).
   Implication: avoid over-committing to compressed-prior portability; replace bridge-era stopgaps with a consistent observables pipeline.
   Kill criterion: if re-derived observables still demand incompatible drift-window behavior, this branch also fails.

## Decision status (tested families)

Under the tested bridge/full-history deformation families, there is no region with both
`drift_sign_ok=True` in `z~2-5` and strict CHW2018 `chi2_cmb ~ O(1)` in no-fudge mode.
Current E2 status is therefore an open closure problem requiring richer early-time physics and/or
revised observable mapping assumptions beyond the current tested families.

## Key evidence figure

WS13 closure requirements map (included in referee pack):

![WS13 closure requirements map](../referee_pack_figures/closure_requirements.png)

WS14 drift-constrained Pareto bound (included in referee pack):

![WS14 drift-constrained closure bound](../referee_pack_figures/e2_drift_constrained_bound.png)

WS15 closure-to-knobs scale map (included in referee pack):

![WS15 closure to physical knobs](../referee_pack_figures/e2_closure_to_physical_knobs.png)

Interpretation of the figure: in tested constant-boost families, `A_required` grows rapidly as repair start is moved above `z~5`; this is the compact no-go trend used in referee-facing discussion.

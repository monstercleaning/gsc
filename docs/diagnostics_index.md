# Diagnostics Index (opt-in only)

This index centralizes post-submission diagnostic modules (WS* / E2*) with release tags, assets,
checksums, and entrypoints.

Scope guard:
- Diagnostic-only modules; not part of canonical submission claims.
- Frozen artifacts remain unchanged: `v10.1.1-late-time-r4`, `v10.1.1-submission-r2`, `v10.1.1-referee-pack-r4`.

Start here for E2 review:

- `docs/early_time_e2_synthesis.md`
- `docs/early_time_e2_executive_summary.md`
- `docs/early_time_e2_drift_constrained_bound.md`
- `docs/early_time_e2_drift_bound_analytic.md`
- `docs/early_time_e2_closure_to_physical_knobs.md`
- `docs/research_notes/PHASE4_M163_FIVE_PROBLEMS.md` (Phase-4 internal research note with deterministic M163 diagnostic)

## Recommended Diagnostic Modules

| Module | Release tag | Asset zip | SHA256 | Reproduce script | Output dir |
|---|---|---|---|---|---|
| WS1/WS1.1/WS1.2: Drift↔CMB closure correlation | [`v10.1.1-bridge-e2-drift-cmb-correlation-r2`](https://github.com/morfikus/GSC/releases/tag/v10.1.1-bridge-e2-drift-cmb-correlation-r2) | `paper_assets_cmb_e2_drift_cmb_correlation_r2.zip` | `db213280f9d5c9fb2b9b0efe236b2a353ce9f1e34612e2a6a07576bdfe344fa1` | `bash scripts/reproduce_v10_1_e2_drift_cmb_correlation.sh --sync-paper-assets` | `results/diagnostic_drift_cmb_correlation/` |
| WS2/WS2.1/WS2.2: GW standard sirens | [`v10.1.1-gw-standard-sirens-diagnostic-r2`](https://github.com/morfikus/GSC/releases/tag/v10.1.1-gw-standard-sirens-diagnostic-r2) | `paper_assets_gw_standard_sirens_diagnostic_r2.zip` | `165e3ab8f88dbb0b97244b47144bb91d91a2fa3c5d889d592f1f2c9829f530ab` | `bash scripts/reproduce_v10_1_gw_standard_sirens_diagnostic.sh --sync-paper-assets` | `results/diagnostic_gw_standard_sirens/` |
| WS5/WS5.1: Neutrino knob (E2.6) | [`v10.1.1-bridge-e2-neutrino-knob-diagnostic-r0`](https://github.com/morfikus/GSC/releases/tag/v10.1.1-bridge-e2-neutrino-knob-diagnostic-r0) | `paper_assets_cmb_e2_neutrino_knob_diagnostic_r0.zip` | `61451ad52aff2653cc07224213357f66613006b4b918d0f769e41343c8330c11` | `bash scripts/reproduce_v10_1_e2_neutrino_knob_diagnostic.sh --sync-paper-assets` | `results/diagnostic_cmb_e2_neutrino_knob/` |
| WS7/WS7.1: Full-history closure (no-stitch) | [`v10.1.1-bridge-e2-full-history-closure-diagnostic-r1`](https://github.com/morfikus/GSC/releases/tag/v10.1.1-bridge-e2-full-history-closure-diagnostic-r1) | `paper_assets_cmb_e2_full_history_closure_diagnostic_r1.zip` | `2ca99a88b4f583dc6d79d12bc28dc8d36b6f6171d249f3f44d01f6912f93e350` | `bash scripts/reproduce_v10_1_e2_full_history_closure_diagnostic.sh --sync-paper-assets` | `results/diagnostic_cmb_full_history/` |
| WS11/E2.8: Drift-protected guarded relax | [`v10.1.1-bridge-e2-full-history-guarded-relax-diagnostic-r0`](https://github.com/morfikus/GSC/releases/tag/v10.1.1-bridge-e2-full-history-guarded-relax-diagnostic-r0) | `paper_assets_cmb_e2_full_history_guarded_relax_diagnostic_r0.zip` | `3dc84a29ae55e422b4b61779f7e63dbdcc5a6d0ca838c4a9a5a865f92aa45640` | `bash scripts/reproduce_v10_1_e2_full_history_guarded_relax_diagnostic.sh --sync-paper-assets` | `results/diagnostic_cmb_full_history_guarded_relax/` |
| WS13/E2.10: High-z H-boost repair scan | [`v10.1.1-bridge-e2-highz-hboost-repair-diagnostic-r0`](https://github.com/morfikus/GSC/releases/tag/v10.1.1-bridge-e2-highz-hboost-repair-diagnostic-r0) | `paper_assets_cmb_e2_highz_hboost_repair_diagnostic_r0.zip` | `fde266f0bf4347185f1027eca07b9f736b3e1eb8e705200c49cfd7bfd5d59039` | `bash scripts/reproduce_v10_1_e2_highz_hboost_repair_diagnostic.sh --sync-paper-assets` | `results/diagnostic_cmb_highz_hboost_repair/` |
| WS8: Distance duality (`epsilon_dd`) | [`v10.1.1-distance-duality-diagnostic-r0`](https://github.com/morfikus/GSC/releases/tag/v10.1.1-distance-duality-diagnostic-r0) | `paper_assets_distance_duality_diagnostic_r0.zip` | `551ed4b0170ef6dc49a91a1a65dee6100d27fe1e597235a11f92e330242d4d1e` | `bash scripts/reproduce_v10_1_distance_duality_diagnostic.sh --sync-paper-assets` | `results/diagnostic_distance_duality/` |
| WS9/WS9.1: Drift forecast (systematics floor) | [`v10.1.1-drift-forecast-diagnostic-r0`](https://github.com/morfikus/GSC/releases/tag/v10.1.1-drift-forecast-diagnostic-r0) | `paper_assets_drift_forecast_diagnostic_r0.zip` | `9295c9d5e02a7abd8a2f43ef331c0c5d6d19a6a889068d5816175399fc615c29` | `bash scripts/reproduce_v10_1_drift_forecast_diagnostic.sh --sync-paper-assets` | `results/diagnostic_drift_forecast/` |
| WS10: `r_s(z*)` numerics audit | [`v10.1.1-bridge-e2-rs-star-numerics-audit-r0`](https://github.com/morfikus/GSC/releases/tag/v10.1.1-bridge-e2-rs-star-numerics-audit-r0) | `paper_assets_cmb_e2_rs_star_numerics_audit_r0.zip` | `f4ab8e51e2272178c568279ed10de3f6165f48ca06e1a02af82ffe8ead2cfbb4` | `bash scripts/reproduce_v10_1_rs_star_numerics_audit.sh --sync-paper-assets` | `results/diagnostic_rs_star_numerics/` |
| WS12/E2.9: `z*` recombination audit | [`v10.1.1-bridge-e2-zstar-recombination-audit-r0`](https://github.com/morfikus/GSC/releases/tag/v10.1.1-bridge-e2-zstar-recombination-audit-r0) | `paper_assets_cmb_e2_zstar_recombination_audit_diagnostic_r0.zip` | `335ac75b64160b5a2524dc7c86deb06e0124b06a92c90ef2196e8289184c5707` | `bash scripts/reproduce_v10_1_e2_zstar_recombination_audit_diagnostic.sh --sync-paper-assets` | `results/diagnostic_zstar_recombination_audit/` |
| WS13 consolidation: Closure requirements / no-go map | [`v10.1.1-bridge-e2-closure-requirements-diagnostic-r0`](https://github.com/morfikus/GSC/releases/tag/v10.1.1-bridge-e2-closure-requirements-diagnostic-r0) | `paper_assets_cmb_e2_closure_requirements_r0.zip` | `dc0dffd51c12655bb3e2a093fd41e872ea996b8d96541198ac49d21d2a21bbd3` | `bash scripts/reproduce_v10_1_e2_closure_requirements.sh --sync-paper-assets` | `results/diagnostic_cmb_e2_closure_requirements/` |
| WS14/E2.10: Drift-constrained closure Pareto bound | [`v10.1.1-bridge-e2-drift-constrained-closure-bound-r0`](https://github.com/morfikus/GSC/releases/tag/v10.1.1-bridge-e2-drift-constrained-closure-bound-r0) | `paper_assets_cmb_e2_drift_constrained_closure_bound_r0.zip` | `215d0573a9b4bac4c69051838a781d6c8242fe2822836da795771bfb47e292f2` | `bash scripts/reproduce_v10_1_e2_drift_constrained_closure_bound.sh --sync-paper-assets` | `results/diagnostic_cmb_drift_constrained_bound/` |
| WS15/E2.11: Closure requirements to physical knobs (`deltaG`, `delta rho/rho`) | [`v10.1.1-bridge-e2-closure-to-physical-knobs-r0`](https://github.com/morfikus/GSC/releases/tag/v10.1.1-bridge-e2-closure-to-physical-knobs-r0) | `paper_assets_cmb_e2_closure_to_physical_knobs_r0.zip` | `cc3bd5bf13e7ac5a3b21dad0f223d407e1a25ef360ee08f88469493a32507986` | `bash scripts/reproduce_v10_1_e2_closure_to_physical_knobs.sh --sync-paper-assets` | `results/diagnostic_cmb_e2_closure_to_physical_knobs/` |
| SN two-pass sensitivity robustness | [`v10.1.1-sn-two-pass-sensitivity-diagnostic-r0`](https://github.com/morfikus/GSC/releases/tag/v10.1.1-sn-two-pass-sensitivity-diagnostic-r0) | `paper_assets_sn_two_pass_sensitivity_diagnostic_r0.zip` | `741edb82f65eedb0c05da5d2e217f0979f6aaea3d1dbe16776621d1d443e83dd` | `bash scripts/reproduce_v10_1_sn_two_pass_sensitivity_diagnostic.sh --sync-paper-assets` | `results/diagnostic_sn_two_pass_sensitivity/` |

## WS14 / WS15 key takeaways

### WS14 (drift-constrained closure Pareto bound)

- Baseline (`s=0`): `chi2_cmb ~= 8.32e4`, `Delta v(z=4,10y) ~= 4.53 cm/s`.
- Near-boundary (`s=0.995`): `Delta v(z=4,10y) ~= 0.0227 cm/s`, but `chi2_cmb ~= 1.54e4`.
- All scan points remain `drift_sign_ok=True`, yet strict CHW2018 closure stays far from `O(1)`.

### WS15 (closure to physical knobs)

- Mapping: `deltaG = A^2 - 1` (`delta rho/rho` same effective scale).
- Median required scale: `deltaG ~= 0.420` at `z_start=5`, `deltaG ~= 0.666` at `z_start=10`.
- Delaying repair start pushes required effective deformation into large `O(1)` regime.

## Notes

- These modules are diagnostic and do not alter canonical late-time results/pipeline defaults.
- `docs/popular/**` remains excluded from submission and referee pack bundle contracts.
- For release-independent local verification, use each module's `manifest.json` and checksum above.
- Consolidated referee-facing verdict and decision tree: `docs/early_time_e2_synthesis.md`.
- Analytic sanity appendix for WS14: `docs/early_time_e2_drift_bound_analytic.md` (`scripts/e2_drift_bound_analytic.py`).
- Paper narrative discipline checklist: `docs/paper_sanity_checklist.md`.
- ToE-track sharing is maintained as a separate bundle line (`v10.1.1-toe-track-r2` recommended; `r0`/`r1` frozen) via:
  `bash scripts/make_toe_bundle.sh toe_bundle_v10.1.1-r2.zip` and
  `bash scripts/verify_toe_bundle.sh toe_bundle_v10.1.1-r2.zip`.
- ToE-track entrypoint index: `docs/popular/TOE_INDEX.md` (explicitly outside submission/referee scope).

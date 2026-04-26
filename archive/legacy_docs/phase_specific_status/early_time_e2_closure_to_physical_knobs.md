# E2.11 Closure Requirements to Physical Knobs (Diagnostic-Only)

Scope: diagnostic translation of closure requirements; not a microphysical claim and not part of submission scope.

## Mapping

Given a closure requirement expressed as `A_required_const` (effective `H` boost on `[z_start, z*]`):

- `deltaH_over_H = A_required_const - 1`
- `deltaG_required = A_required_const^2 - 1` (if interpreted as effective running-`G`, since `H ~ sqrt(G)`)
- `delta_rho_over_rho_required = A_required_const^2 - 1` (if interpreted as equivalent extra density, since `H^2 ~ rho`)

These are effective bookkeeping maps for E2 planning.

## Representative numbers (from WS13 targets)

For the WS13 target set (anchor + p10/p50/p90 from E2.4 `dm_fit`, bridge-z reference 5):

- `z_start = 5`:
  - `A` p10/p50/p90: `1.053 / 1.191 / 1.391`
  - `deltaG` p10/p50/p90: `0.114 / 0.420 / 0.948`
- `z_start = 10`:
  - `A` p10/p50/p90: `1.079 / 1.290 / 1.659`
  - `deltaG` p10/p50/p90: `0.177 / 0.666 / 1.796`

Interpretation: delaying repair start pushes required effective deformation into large (`O(1)`) territory in tested families.

## Artifacts and Repro

- Pre-release tag: `v10.1.1-bridge-e2-closure-to-physical-knobs-r0`
- Asset zip: `paper_assets_cmb_e2_closure_to_physical_knobs_r0.zip`
- SHA256: `cc3bd5bf13e7ac5a3b21dad0f223d407e1a25ef360ee08f88469493a32507986`
- Reproduce:
  - `bash scripts/reproduce_v10_1_e2_closure_to_physical_knobs.sh --sync-paper-assets`

Outputs:

- `results/diagnostic_cmb_e2_closure_to_physical_knobs/`
- `paper_assets_cmb_e2_closure_to_physical_knobs/`

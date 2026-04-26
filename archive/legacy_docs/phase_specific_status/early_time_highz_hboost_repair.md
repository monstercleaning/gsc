# E2.10 High-z H-boost repair (full-history, drift-safe) — diagnostic note

**Status:** Diagnostic-only (opt-in).  
**Not part of submission scope.** This does not modify the canonical late-time pipeline outputs.

## Goal

E2.10 tests whether the strict CHW2018 compressed-CMB distance priors can be made compatible in
**full-history (no-stitch)** mode by applying only an explicit high-z deformation:

`H(z) -> A(z) H(z)` for `z > z_boost_start`,

while keeping the late-time **redshift-drift falsifier** intact by enforcing:

- `A(z)=1` for `z <= z_boost_start` (protect the drift window `z~2–5`), and
- `A(z)=1` for `z >= z_bbn_clamp` (preserve the BBN safety clamp).

In addition, the scan applies the boost only on the **post-recombination distance integral**
`z ∈ (z_boost_start, z*)` so `r_s(z*)` is not modified by construction (matching the E2.3 closure mapping).

This is a “what would it take” closure probe. It is **not** a physical early-universe model.

## Relation to E2.3 mapping

E2.2 suggests a required distance-closure factor `dm_star_calibration_fit` to make strict CHW2018
compatible under a non-degenerate bridge, and E2.3 maps this to an **effective constant high-z
boost** `A_required` on `[z_boost_start, z*]`.

E2.10 implements that mapping as an explicit full-history option and tests whether it can reduce
the **no-fudge** strict CHW2018 chi² to `O(1)` while preserving `drift_sign_ok=True`.

## Implementation

Code:

- `gsc/histories/full_range.py`:
  - `GSCTransitionFullHistory` (full-range base history, diagnostic-only)
  - `HBoostWrapper` (applies `A(z)` above `z_boost_start`, disables it above `z_bbn_clamp`)
- `scripts/cmb_e2_highz_hboost_repair_scan.py`:
  - scans `A_const` and `z_boost_start`
  - computes strict CHW2018 chi² (no `dm` / `rs` fit knobs; `dm=1`)
  - records drift amplitudes `Δv(z)` at `z={2,3,4,5}` over 10 years and the boolean `drift_sign_ok`
  - records BBN clamp sanity at `z={1e8,1e9}` via `H/H_lcdm_rad - 1`.

## Outputs

Written only to diagnostic outdirs:

- `results/diagnostic_cmb_highz_hboost_repair/`
  - `tables/cmb_highz_hboost_scan.csv`
  - `tables/feasible_subset.csv`
  - `tables/summary.txt`
  - `figures/chi2_vs_A_by_zbooststart.png`
  - `figures/drift_vs_A.png`
  - `manifest.json`

Optional paper-assets sync (gitignored):

- `paper_assets_cmb_e2_highz_hboost_repair_diagnostic/`

## Reproduce (1 command)

```bash
bash scripts/reproduce_v10_1_e2_highz_hboost_repair_diagnostic.sh --sync-paper-assets
```

This generates the results directory and (optionally) a zip asset suitable for attaching to a
diagnostic pre-release.

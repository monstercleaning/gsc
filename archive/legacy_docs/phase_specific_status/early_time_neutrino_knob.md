# E2.6 Diagnostic: Neutrino-Sector Knob (Delta N_eff)

**Status:** diagnostic-only (out of submission scope).  
**Scope:** explores how an early-time radiation-density knob, implemented as `Delta N_eff`, changes the *required* compressed-CMB closure calibrations for non-degenerate bridges.

## What This Is

We vary:

- `N_eff = N_eff_base + Delta N_eff`

and record how this shifts the CHW2018 distance-priors tension (baseline `chi2`) and the fitted diagnostic closure knobs:

- `dm_star_calibration_fit` (rescales `D_M(z*)`)
- `rs_star_calibration_fit` (rescales `r_s(z*)`)

We also report an **interpretation-only** effective mapping `A_required_const` (E2.3-style):

> "What constant multiplicative boost `H -> A H` on `[bridge_z, z*]` would reproduce the required `dm_fit`?"

This mapping is **not** a physical model and is only used to quantify the magnitude of early-time distance closure implied by a late-time history + bridge choice.

## How To Reproduce

Run:

```bash
bash scripts/reproduce_v10_1_e2_neutrino_knob_diagnostic.sh --sync-paper-assets
```

Outputs:

- Results directory: `results/diagnostic_cmb_e2_neutrino_knob/`
- Optional shareable assets zip: `paper_assets_cmb_e2_neutrino_knob_diagnostic_r0.zip`

The artifact contains:

- `tables/cmb_e2_neutrino_knob_scan.csv`
- `figures/neutrino_knob_dm_rs_A_vs_delta_neff.png`
- `manifest.json` (strict JSON, repo-relative paths)

## Snapshot Results (r0; diagnostic only)

Baseline late-time checkpoint: `gsc_transition (p=0.6, z_transition=1.8)` with a **non-degenerate** bridge.

Key point: varying `Delta N_eff` can move `r_s(z*)`, but the **required distance closure** `dm_fit` remains the
dominant requirement for strict CHW2018 compatibility.

Representative fitted closures:

- `bridge_z_used=5`:
  - `dm_fit ≈ 0.9282–0.9293` (about **-7%** in `D_M(z*)`)
  - `A_required_const ≈ 1.217–1.221` (about **+22%** effective boost in `H(z)` on `[5,z*]`)
  - `rs_fit` shifts noticeably with `Delta N_eff` (e.g. `~0.969` at `Delta N_eff=-1` to `~1.0375` at `+1`)
- `bridge_z_used=10`:
  - `dm_fit ≈ 0.7948–0.7956` (about **-20%** in `D_M(z*)`)
  - `A_required_const ≈ 6.30–6.37` (very large effective boost)

Interpretation (still diagnostic-only):

- A neutrino-sector knob (via `Delta N_eff`) primarily affects `r_s(z*)` and therefore `lA`, but the strict CHW2018
  `R`/`D_M(z*)` closure remains the controlling tension for non-degenerate bridges in this checkpoint.

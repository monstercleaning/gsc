# E2.7 Full-Range (No-Stitch) Early-Time History — diagnostic note

**Status:** Diagnostic-only (opt-in).  
**Not part of submission scope.** This does not modify the canonical late-time pipeline outputs.

## Goal

E2.7 replaces “bridge stitch” reasoning with a **single full-range history** `H(z)` defined for
`z ∈ [0, z*]`, so we can test whether early-time closure can be improved by:

- relaxing the late-time toy exponent `p` into a running `p_eff(z)` at high redshift, and
- enforcing a BBN-safety guardrail (so high-z behavior is not pathological).

## Full-range histories

Implemented in `gsc/histories/full_range.py`:

- `FlatLCDMRadHistory`: flat LCDM with radiation (baseline reference).
- `GSCTransitionFullHistory`: late-time GSC transition + high-z convergence.

### Construction (diagnostic)

We define a late-time/GSC component `H_gsc(z)` and add radiation in quadrature:

`H(z)^2 = H_gsc(z)^2 + H_rad(z)^2`,

with `H_rad(z) = H0 * sqrt(Omega_r) * (1+z)^2`.

### p(z) relax (1-parameter)

Above the transition redshift `z_transition`, an effective exponent `p_eff(z)` relaxes from the
late-time value `p_late` toward the matter-era slope `1.5` over a scale `z_relax`:

`p_eff(z) = p_late + (1.5 - p_late) * (1 - exp(-(z - z_transition)/z_relax))`, for `z > z_transition`.

This is a **diagnostic knob** (“RG effect fades / convergence to matter era”), not a physical claim.

### BBN guardrail (diagnostic clamp)

To avoid BBN-toxic high-z behavior, an explicit clamp is allowed:

- for `z >= z_bbn_clamp`, force `H(z) = H_LCDM+rad(z)` exactly.

This is recorded in manifests (`bbn_clamp_enabled`, `z_bbn_clamp`) and exists only as a safety
guardrail for diagnostics.

## What the E2.7 scan does

Script: `scripts/cmb_e2_full_history_closure_scan.py`.

For a coarse grid in `(p, z_transition)` and a small set of `z_relax` values, it computes:

1. Reference **bridged** CHW2018 strict chi2 (as in E2.4), at `bridge_z_ref`.
2. **Full-history** CHW2018 strict chi2 (no stitch) for each `z_relax`.
3. A deterministic diagnostic closure fit `(dm_fit, rs_fit)` against strict CHW2018 distance priors
   (optional interpretation-only knobs; not used in canonical runs).

Outputs are written only to diagnostic outdirs:

- `results/diagnostic_cmb_full_history/` (tables/figures/manifest)
- optional paper-assets sync: `paper_assets_cmb_e2_full_history_closure_diagnostic/`

## Reproduce (1 command)

```bash
bash scripts/reproduce_v10_1_e2_full_history_closure_diagnostic.sh --sync-paper-assets
```

This writes diagnostic outputs and produces a zip (gitignored) suitable for attaching to a
diagnostic pre-release.

## Guarded relax (E2.8): protect the drift window

E2.7 revealed a key tension: an aggressive high-z relax can reduce strict CHW2018 chi² in the
full-history mode, but it can also contaminate the **historical late-time drift diagnostic**
in the critical `z~2–5` window.

E2.8 introduces a minimal, diagnostic-only guard:

- keep the exact late-time GSC power-law component up to a chosen `z_relax_start` (e.g. `>=5`);
- allow the relax of `p_eff(z)` (toward `p_target=1.5`) only for `z > z_relax_start`.

Implementation note (guarded mode only):

- the relax is defined in `x = ln((1+z)/(1+z_relax_start))` so the integrated `H(z)` is consistent with
  the desired slope `d ln H / d ln(1+z) = p_eff(z)`.

Tooling:

- `scripts/cmb_e2_full_history_guarded_relax_scan.py`
- `scripts/reproduce_v10_1_e2_full_history_guarded_relax_diagnostic.sh`

Outputs:

- `results/diagnostic_cmb_full_history_guarded_relax/`
- (optional) `paper_assets_cmb_e2_full_history_guarded_relax_diagnostic/`

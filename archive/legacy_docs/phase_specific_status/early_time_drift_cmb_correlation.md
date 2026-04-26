# Early-Time Diagnostic: Drift ↔ CMB Closure Correlation (E2.5)

**Status:** Diagnostic-only note (out of submission scope).

This note documents a simple *correlation diagnostic* that links:

1. **late-time redshift-drift amplitudes** (look-back observable; evaluated at `z={2,3,4,5}`), and
2. the **required early-time distance-closure knobs** from the strict CHW2018 distance-priors fits
   (`dm_fit`, `rs_fit`, and simple “effective” high-z closure deformation mappings).

The point is not to claim an early-universe mechanism, but to quantify “what would it take”:
if a late-time history implies a certain drift amplitude in `z~2–5`, what size of early-time
compensation is *forced* by strict compressed-CMB distance priors under a non-degenerate bridge.

## What Is Correlated

- **Drift amplitude:** we report the Sandage–Loeb velocity drift as **`Δv` over `10 yr`**, in `cm/s`,
  using the kinematic relation:
  - `ż = H0(1+z) - H(z)`
  - equivalently: `Δz = Δt0 * [ H0(1+z) - H(z) ]`
  - `Δv = c * ż/(1+z) * Δt`
- **Required CMB closure (E2.4):** the diagnostic best-fit `dm_fit` (multiplying `D_M(z*)`) and `rs_fit`
  (multiplying `r_s(z*)`) that minimize strict CHW2018 distance-priors `χ²`.
- **Closure deformation families (E2.5+):** for each scan point, we map `dm_fit` into a few toy
  deformation families for the high-z bridge history on `[bridge_z, z*]` (diagnostic only):
  - constant boost: `H -> A*H` (E2.3 mapping)
  - power-law boost: `A(z)=1 + B*((1+z)/(1+bridge_z))^n`
  - logistic crossover: `A(z)=1 + (Amax-1)/(1+exp((z-zc)/s))`
  - localized bump: `A(z)=A_bump` on `[z1,z2]`, `A(z)=1` otherwise (clamped to `[bridge_z,z*]`)

  The goal is *not* to propose microphysics, but to quantify what type of high-z modification is
  required to realize the distance closure implied by strict CHW2018 priors.

### Why “shape freedom” matters (diagnostic)

The constant-`A` mapping is intentionally the **most rigid** deformation: it applies the same boost
to all redshifts above the chosen start (e.g. `z >= bridge_z` or `z >= 10`). If a required closure
cannot be achieved without a very large constant `A`, then any viable E2 closure would need either:

- a different start redshift, and/or
- a deformation with **shape freedom** (localized or evolving repair) to concentrate the modification
  where it buys the most distance-integral leverage.

For the constant-`A` mapping:

- **Effective mapping (E2.3):** for each scan point, we map `dm_fit` to an *equivalent constant* boost
  `A` applied to `H(z)` on `[bridge_z, z*]`:
  - `D_M(0->bridge) + D_M(bridge->z*)/A = dm_fit * D_M(0->z*)`
  - This is an interpretation aid only (not a physical model).

## How To Reproduce

1. Run the correlation diagnostic (also runs/uses an E2.4 scan in an isolated outdir):

```bash
bash scripts/reproduce_v10_1_e2_drift_cmb_correlation.sh --sync-paper-assets
```

2. Outputs:

- `results/diagnostic_drift_cmb_correlation/`
  - `tables/e2_drift_cmb_correlation.csv`
  - `tables/drift_cmb_closure_summary.csv`
  - `tables/cmb_drift_cmb_correlation_shapes.csv`
  - `figures/A_required_vs_drift_z4.png`
  - `figures/Amax_required_logistic_vs_drift_z4.png`
  - `figures/A_required_by_shape.png`
  - `manifest.json`
- `paper_assets_drift_cmb_correlation/` (opt-in snapshot for sharing)

## Interpretation (Diagnostic Only)

- If the scan shows that **positive drift in `z~2–5`** generically implies **large `A`** (large effective
  `H(z)` boost at `z >= bridge_z`) to satisfy strict CHW2018 distance priors, then early-time closure is not
  a small perturbation: it becomes a central E2 requirement.
- Conversely, if a subset of late-time histories yields positive drift while requiring only modest `A`,
  those points are natural targets for E2 development.

This is *not* part of the submission scope; it is a roadmap tool for E2.

## Conclusions (Diagnostic)

- Allowing **shape freedom** (e.g. a localized bump) can reduce the **peak amplitude** required for distance closure
  compared to a constant-`A` boost applied over the full `[bridge_z,z*]` interval, but it cannot eliminate the
  need for **distance closure** when the bridge is non-degenerate.
- If a given bridge choice (e.g. `bridge_z=10`) requires an implausibly large `Amax` even with flexible shapes,
  that points to a hard early-time requirement rather than a small correction.
- This diagnostic is a planning tool: it quantifies “what would it take” without claiming a microphysical mechanism.

## Related Diagnostics

- For a coarse “when will drift become decisive?” timeline tool with an explicit systematic floor, see:
  `docs/redshift_drift_forecast.md`.

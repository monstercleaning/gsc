# the current framework Project Scope (Decision + Definition of Done)

## Decision: Option 2 (Freeze-Frame Measurement Model)

For the current framework we adopt **Option 2**:
we do **not** assume the standard automatic translation
“observation → H(z), D_L, D_A, CMB…” used in ΛCDM/FLRW.

Instead we define a **measurement model** first (clocks/rods/atomic standards),
and only then map raw observations to reported cosmological observables.

Canonical source:
- `docs/measurement_model.md`

## Universal Scaling (Baseline Axiom Set)

v11.0.0 assumes **universal/coherent scaling**:
- bound lengths `ℓ_bound ∝ σ(t)`
- particle masses `m ∝ σ(t)^(-1)`
- Planck mass co-scales `M_Pl ∝ σ(t)^(-1)` ⇒ IR Newton coupling `G ∝ σ(t)^(+2)`
- dimensionless couplings/ratios are (approximately) constant
- purely local dimensionless comparisons predict **null drift**

## “Done” for the current framework (Honest Scope)

v11.0.0 is explicitly **late-time focused**.

Done-v11.0.0 means:
1. A clear, formal measurement model spec (Option 2).
2. Working translation code for:
   - redshift `z`
   - redshift drift `ż` (and Δv over finite baselines)
   - baseline distances `D_M, D_A, D_L` under an explicitly stated hypothesis
3. Reproducible pipeline + regression tests for core invariants.
4. Primary physics discriminator (Roadmap v2.8):
   - `epsilon` / measurement-model inference + cross-probe consistency triangles.
5. Redshift drift at `z ~ 2–5` remains in scope as:
   - supporting no-go diagnostic / pre-check for specific history classes,
     and historical framing from earlier milestones (not the primary discriminator).

## “Done” for v10+ (Out of the current framework Scope)

Done-v10+ requires completing early-universe / full-likelihood translation in
the freeze-frame measurement model:
- recombination + sound horizon + transfer functions in the correct frame
- full CMB (and lensing) predictions with likelihood interfaces
- global multi-dataset fits (SN+BAO+RSD+CMB+…)

## Simulations vs Canonical Translation

Phase10 / mochi_class under `B/` is treated as an **engineering solver**
and consistency tool. It is not, by itself, the canonical translation layer
under Option 2.

Legacy/bridge packages under `bridges/` are useful diagnostics but were
originally written with standard effective-FLRW translation; treat them as
support tools until explicitly refactored to Option 2.

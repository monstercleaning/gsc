# Early-Time E2 Closure Requirements (WS13 consolidation, diagnostic-only)

**Status:** Referee-pack diagnostic note (not part of submission scope).  
**Scope guard:** no change to canonical late-time/submission artifacts; no pipeline side effects.

## Executive takeaway

- Non-degenerate bridge diagnostics (E1.3/E2.2/E2.4) show that CHW2018 strict distance-priors tension is dominated by a **distance-closure** requirement in `D_M(z*)`, not by `r_s(z*)` alone.
- Representative fits imply a target near `dm_fit ~ 0.93` (order `~7%` reduction in `D_M(z*)` at `z*`) for baseline non-degenerate checkpoints.
- Mapping this target to a constant high-z repair `H -> A H` shows:
  - if repair starts near `z~5`, required `A` is moderate (`O(1.2)`),
  - if repair is delayed toward `z~10+`, required `A` grows rapidly (often implausible in this deformation family).
- Full-history guarded-relax and post-recombination high-z boost scans both preserve drift-sign in `z∈[2,5]`, but do not reach `chi2_cmb ~ O(1)` in strict CHW2018 no-fudge mode for the tested high-start repairs.

## Drift-sign condition (explicit)

The kinematic redshift-drift relation used throughout diagnostics is:

`\dot z = H_0(1+z) - H(z)`.

Therefore, positive drift at a given redshift requires:

`\dot z > 0  \iff  H(z) < H_0(1+z)`.

This is the operational sign test used in the drift window `z≈2–5`.

## Constant-A closure mapping (analytic)

For a chosen `z_boost_start`, split the comoving distance:

`D_M(z*) = D_M(0->z_boost_start) + D_M(z_boost_start->z*)`.

Define a closure target `D_M,target = dm * D_M(z*)`, where `dm` is a diagnostic closure factor
(e.g., from E2.4 quantiles or E2.2 anchor points). For a constant high-z boost on
`[z_boost_start, z*]`, `H -> A H` implies:

`D_M(z_boost_start->z*) -> D_M(z_boost_start->z*) / A`.

So `A_required` satisfies:

`D_M(0->z_boost_start) + D_M(z_boost_start->z*)/A_required = D_M,target`,

hence:

`A_required = D_M(z_boost_start->z*) / (D_M,target - D_M(0->z_boost_start))`.

Interpretation: as `z_boost_start` increases, less distance remains to repair, so `A_required`
must rise quickly to achieve the same `dm` target.

## What this rules out / what it requires

- **Ruled out in tested family:** “repair starts too high” (`z_boost_start~10+`) as a practical way to close strict CHW2018 while keeping drift-safe behavior in `z∈[2,5]`.
- **Required by diagnostics:** if closure is attempted in this class, deformation must begin near the lower edge of the early-time handoff region (`z~5`) or be replaced by a richer early-time mechanism (beyond constant post-recombination boost).
- This is a diagnostic no-go/requirement map, not a physical claim.

## Reproduce

```bash
bash scripts/reproduce_v10_1_e2_closure_requirements.sh --sync-paper-assets
```

Outputs:

- `results/diagnostic_cmb_e2_closure_requirements/`
- `paper_assets_cmb_e2_closure_requirements/` (optional sync view)


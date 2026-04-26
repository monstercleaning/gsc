# E2 Analytic Drift Bound (Diagnostic Sanity Note)

This note is diagnostic-only and serves as an analytic intuition appendix for WS14.

## One-line bound

If drift is positive in a window (`H(z) < H0(1+z)`), then:

- `integral_{z1}^{z2} dz / H(z) > (1/H0) * ln[(1+z2)/(1+z1)]`

Multiplying by `c` gives a comoving-distance lower bound:

- `Delta chi_min = (c/H0) * ln[(1+z2)/(1+z1)]`

For `(z1,z2)=(2,5)`:

- `Delta chi_min = (c/H0) * ln 2`

At `H0=67.4 km/s/Mpc`, this yields:

- `Delta chi_min ~= 3.08e3 Mpc`.

## Purpose

- This does not prove full no-go by itself.
- It provides a compact analytic reason why keeping strict positive drift while trying to strongly compress distance contributions in `z in [2,5]` is nontrivial.
- It complements WS14 numerical Pareto scans; it does not replace them.

## Reproduce

- `bash scripts/reproduce_v10_1_e2_drift_bound_analytic.sh --sync-paper-assets`

Outputs:

- `results/diagnostic_e2_drift_bound_analytic/`
- `paper_assets_cmb_e2_drift_bound_analytic/` (optional sync)

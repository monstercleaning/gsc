# GW Standard Sirens (Diagnostic Module; Out of Submission Scope)

**Status:** Diagnostic / ToE-track note (not part of submission claims).

This note records a lightweight, pipeline-unused diagnostic module for **GW standard sirens**.
The goal is to keep a second, look-back observable channel (orthogonal to redshift drift) ready
for roadmap work without mixing it into the late-time submission scope.

## Minimal Parameterizations (Diagnostic)

This repo keeps two standard, *diagnostic* parameterization paths for modified GW propagation.

### (A) Phenomenological: \(\Xi_0, n\)

Widely used in the standard-siren modified-propagation literature:

- `Xi(z) = Xi0 + (1 - Xi0) / (1+z)^n`
- `d_L^{GW}(z) = Xi(z) * d_L^{EM}(z)`

Properties:

- `Xi(0) = 1` exactly.
- For `n>0`, `Xi(z)` approaches `Xi0` monotonically as `z` increases.

### (B) “Friction / Planck-mass running” hooks

An alternative diagnostic interface is to write the ratio as an integral over a dimensionless
“friction modification” function:

- `d_L^{GW}(z) / d_L^{EM}(z) = exp( ∫_0^z [delta(z')/(1+z')] dz' )`

> **Theory box (diagnostic):** sign conventions vary across the literature depending on how the
> friction term is defined in the GW propagation equation. In this repo’s diagnostic tooling we
> adopt the plus-sign convention above so that the constant-`delta` case admits an analytic check:
> `delta(z)=delta0` implies `d_L^{GW}/d_L^{EM} = (1+z)^{delta0}`.

A common mapping (under additional assumptions such as `c_T ~ 1`) is also:

- `d_L^{GW}(z) / d_L^{EM}(z) = M_*(0) / M_*(z)`

These are **diagnostic hooks only**. We do not assume a microphysical origin in the current framework.

## Tooling

- Script: `scripts/gw_standard_sirens_diagnostic.py`
- Helper module: `gsc/diagnostics/gw_sirens.py`

Reproduce (isolated outputs + optional paper-assets snapshot):

```bash
bash scripts/reproduce_v10_1_gw_standard_sirens_diagnostic.sh --sync-paper-assets
```

Outputs:

- `results/diagnostic_gw_standard_sirens/`
  - `tables/gw_xi_vs_z.csv`
  - `figures/gw_dL_ratio_vs_z.png`
  - `manifest.json`
- `paper_assets_gw_standard_sirens/` (opt-in snapshot for sharing)

## References (Starter Pointers)

- Belgacem et al., *Gravitational-wave luminosity distance in modified gravity theories* (Phys. Rev. D 97, 104066, 2018).
  - PDF: [PhysRevD.97.104066](https://dspace.library.uu.nl/bitstream/handle/1874/419323/PhysRevD.97.104066.pdf?isAllowed=y&sequence=2)

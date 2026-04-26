# BAO Data (v11.0.0)

This folder is intended for small BAO datasets used by the late-time scorecard.

## Current Dataset

- `v11.0.0/data/bao/bao_6df_mgs_boss_dr12.csv`
  - 6dFGS (z=0.106): isotropic `D_V/r_d`
  - SDSS MGS (z=0.15): isotropic `D_V/r_d`
  - BOSS DR12 (z=0.38, 0.51, 0.61): anisotropic `(D_M/r_d, D_H/r_d)` with per-bin
    correlation `rho_dm_dh`
- `v11.0.0/data/bao/bao_6df_mgs_boss_dr12_cov6.csv` (recommended)
  - same isotropic points
  - BOSS DR12 represented as a single `VECTOR_over_rd` block with a full 6×6
    covariance (includes cross-bin correlations)
- `v11.0.0/data/bao/bao_6df_mgs_boss_dr12_cov6_plus_lya.csv` (recommended for high-z)
  - same isotropic points
  - BOSS DR12 6×6 covariance block (as above)
  - eBOSS DR16 Lyα combined Gaussian constraint at z=2.33 as a 2×2 `VECTOR_over_rd`
    block on `(D_M/r_d, D_H/r_d)`
- `v11.0.0/data/bao/bao_6df_mgs_boss_dr12_cov6_plus_lya_qso.csv` (recommended for high-z + QSO)
  - same as `bao_6df_mgs_boss_dr12_cov6_plus_lya.csv`
  - adds SDSS/eBOSS DR16 QSO anisotropic constraint at z=1.48 as a 2×2 `VECTOR_over_rd`
    block on `(D_M/r_d, D_H/r_d)`

## File Format (Block CSV)

Each row is a *block* with a `type`:

- `DV_over_rd` (isotropic):
  - `z, dv_over_rd, sigma_dv_over_rd`
- `DM_over_rd__DH_over_rd` (anisotropic):
  - `z, dm_over_rd, dh_over_rd, sigma_dm_over_rd, sigma_dh_over_rd, rho_dm_dh`
- `VECTOR_over_rd` (covariance block; requires `numpy`):
  - `values_path, cov_path`
  - values CSV format: rows `kind,z,y` with `kind ∈ {DV,DM,DH}`

Optional columns (ignored by the loader):
- `label`, `survey`

## Late-Time Policy

At v11.0.0 scope `r_d` is treated as a free nuisance parameter (no drag-epoch
physics is assumed). The harness profiles `r_d` analytically.

## Notes / Caveats

- The BOSS DR12 rows were converted from the common published scaled form
  `D_M * (r_d,fid/r_d)` and `H * (r_d/r_d,fid)` into our internal ratios
  `D_M/r_d` and `D_H/r_d = c/(H r_d)`, using a first-order (linearized) error
  propagation for the `1/H` mapping and flipping the sign of the correlation.
- For publication-grade BAO, prefer `bao_6df_mgs_boss_dr12_cov6.csv`, which uses
  a full 6×6 covariance block for the BOSS DR12 consensus (cross-bin
  correlations included).
- For high-z BAO, prefer `bao_6df_mgs_boss_dr12_cov6_plus_lya.csv`. The Lyα
  block is taken from `CobayaSampler/bao_data` "combined" constraint. Do not add
  Lyα auto + cross as separate blocks unless you also include their cross-cov
  (otherwise you risk double counting).
- The older `bao_6df_mgs_boss_dr12.csv` treats each BOSS redshift bin
  independently (no cross-bin covariance). Keep it only as a lightweight
  smoke-test dataset.

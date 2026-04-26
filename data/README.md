# Data (v11.0.0)

This folder contains small, reproducible late-time datasets used by the
`v11.0.0/` harness code.

## Supernovae (SN Ia)

Pantheon+SH0ES DataRelease (public):

- Source table:
  - `v11.0.0/data/sn/pantheon_plus_shoes/Pantheon+SH0ES.dat`
- Covariance:
  - `v11.0.0/data/sn/pantheon_plus_shoes/Pantheon+SH0ES_STAT+SYS.cov`
- Harness CSVs (diagonal errors only):
  - `v11.0.0/data/sn/pantheon_plus_shoes/pantheon_plus_shoes_mu.csv`
  - `v11.0.0/data/sn/pantheon_plus_shoes/pantheon_plus_shoes_hflow_mu.csv`

Fetch script:
- `v11.0.0/scripts/fetch_pantheon_plus_shoes.sh`

Conversion script (stdlib-only; .dat -> .csv):
- `v11.0.0/scripts/pantheon_plus_shoes_to_csv.py`

Notes:
- CSV mapping is: `z=zHD`, `mu=MU_SH0ES`, `sigma_mu=MU_SH0ES_ERR_DIAG`.
- The Hubble-flow subset is `IS_CALIBRATOR==0`.
- Derived CSVs include a provenance column `row_full` (0-based row index in the
  original `.dat`). When `--sn-cov` is used, the loader uses `row_full` to
  subset the full covariance automatically (so Hubble-flow can reuse the same
  `STAT+SYS.cov` source of truth).
- Full `STAT+SYS` covariance (publication-ready) is supported via:
  - `v11.0.0/data/sn/pantheon_plus_shoes/Pantheon+SH0ES_STAT+SYS.cov`
  - optional cache: `Pantheon+SH0ES_STAT+SYS.cov.npz` (auto-created)

Covariance mode requires `numpy` and is enabled in:
- `v11.0.0/scripts/late_time_scorecard.py` via `--sn-cov ...`

## Redshift Drift

- `v11.0.0/data/drift/`

## BAO

- `v11.0.0/data/bao/`
- Initial late-time-safe block-CSV:
  - `v11.0.0/data/bao/bao_6df_mgs_boss_dr12.csv`
    - 6dFGS + SDSS-MGS isotropic `D_V/r_d`
    - BOSS DR12 anisotropic `(D_M/r_d, D_H/r_d)`
    - `r_d` is treated as a profiled nuisance parameter at v11.0.0 scope
- Publication-grade BOSS covariance variant:
  - `v11.0.0/data/bao/bao_6df_mgs_boss_dr12_cov6.csv` (recommended)

# DATA_SOURCES

This file lists the main in-repo datasets used by the current tooling, with
deterministic file hashes and source pointers.

Scope note:

- This is a provenance map for packaged inputs.
- It does not add new physics claims.

## Core dataset table

| Dataset ID | File | SHA256 | Source / citation pointer | License / usage note |
|---|---|---|---|---|
| `rsd_fsigma8_gold2017_plus_zhao2018` | `data/structure/fsigma8_gold2017_plus_zhao2018.csv` | `488a069e3002bfb39c45a072a783b5803b9b3f2934bdfd285f818743b2af30d3` | See `data/structure/README.md` (Gold 2017 + Zhao 2018 compilation context) | Transcribed diagnostic compilation; not an original survey-data release claim |
| `cmb_chw2018_distance_priors` | `data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv` | `d03c68c9d05385d2680acd2d73e8bfb8be64c8931083f1588f2b1e0ba4afa339` | CHW2018 distance-priors pointer in `data/cmb/README.md` | Compressed-priors bridge input; not full spectra likelihood |
| `cmb_chw2018_covariance` | `data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov` | `3f2fda4d0008fcc871021a0debbfb52aaa1dab854b0335e3e4493f82bff979da` | CHW2018 covariance pointer in `data/cmb/README.md` | Used only in explicit compressed-priors mode |
| `bao_cov6_plus_lya` | `data/bao/bao_6df_mgs_boss_dr12_cov6_plus_lya.csv` | `773cc46f4e6959d0de8f8f1fc2800045b7aab8b7f39feaaaa39a22773a1d159a` | BAO block-format notes in `data/bao/README.md` | Late-time BAO constraints with published-source conversion notes |
| `bao_cov6_plus_lya_qso` | `data/bao/bao_6df_mgs_boss_dr12_cov6_plus_lya_qso.csv` | `eae634710759068d2f27813eb288084e1ca47fec42d4d879ceca1be2640c8407` | BAO block-format notes in `data/bao/README.md` | Late-time BAO constraints with published-source conversion notes |
| `drift_trost_2025_benchmark` | `data/drift/trost_2025_lcdm_benchmark.csv` | `0d0d71f98c1bc3bfa70d7fff62d7bbb2fda938a5e63e4285fba2b0ad8892d8e7` | Drift benchmark notes in `data/drift/README.md` | Benchmark/diagnostic input |
| `sn_pantheon_plus_shoes_hflow` | `data/sn/pantheon_plus_shoes/pantheon_plus_shoes_hflow_mu.csv` | `ea3bfbc9600daf799c2f4e3749dd05e66339280c307270610ae74929c1c7228e` | Pantheon+SH0ES mapping in `data/README.md` | Derived CSV for harness; original release files documented in same folder |

## How to recompute hashes

```bash
sha256sum data/structure/fsigma8_gold2017_plus_zhao2018.csv \
  data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv \
  data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov \
  data/bao/bao_6df_mgs_boss_dr12_cov6_plus_lya.csv \
  data/bao/bao_6df_mgs_boss_dr12_cov6_plus_lya_qso.csv \
  data/drift/trost_2025_lcdm_benchmark.csv \
  data/sn/pantheon_plus_shoes/pantheon_plus_shoes_hflow_mu.csv
```

## Related references

- `data/README.md`
- `data/cmb/README.md`
- `data/bao/README.md`
- `data/structure/README.md`

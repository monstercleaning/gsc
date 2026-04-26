# Data Licenses and Sources

This file enumerates committed files under `data/**` for reviewer
traceability.

Scope note:

- These files are small, committed diagnostic/reviewer inputs.
- Upstream survey/release licensing remains the authoritative source for reuse.
- Repository usage is focused on reproducible methodology checks.

| File | Dataset name | Origin / source pointer | License / usage note | Why included |
|---|---|---|---|---|
| `data/README.md` | Data root README | Repository-authored data index | Repository documentation (`LICENSE` at repo root) | Reviewer orientation |
| `data/bao/README.md` | BAO README | Repository-authored BAO notes | Repository documentation | BAO format/provenance guidance |
| `data/bao/bao_6df_mgs_boss_dr12.csv` | BAO lightweight block set | 6dFGS + SDSS MGS + BOSS DR12, see BAO README | Published-measurement compilation for diagnostics; check upstream terms for external redistribution | Fast BAO smoke/diagnostic runs |
| `data/bao/bao_6df_mgs_boss_dr12_cov6.csv` | BAO DR12 cov6 block set | BAO README (full DR12 6x6 covariance block) | Published-measurement derived table for diagnostic use | Preferred DR12 covariance-aware BAO block |
| `data/bao/bao_6df_mgs_boss_dr12_cov6_plus_lya.csv` | BAO DR12+Lyα block set | BAO README (includes eBOSS DR16 Lyα block) | Published-measurement derived table for diagnostic use | High-z BAO diagnostic option |
| `data/bao/bao_6df_mgs_boss_dr12_cov6_plus_lya_qso.csv` | BAO DR12+Lyα+QSO block set | BAO README (adds DR16 QSO block) | Published-measurement derived table for diagnostic use | High-z BAO + QSO diagnostics |
| `data/bao/boss_dr12_dm_dh_over_rd.csv` | BOSS DR12 values table | BAO source table used by conversion flow | Published-source derived values for diagnostic tooling | Intermediate/traceable BAO values |
| `data/bao/boss_dr12_dm_dh_over_rd_cov6.cov` | BOSS DR12 cov6 matrix | BAO covariance source in conversion flow | Published-source covariance for diagnostic tooling | Intermediate/traceable BAO covariance |
| `data/bao/eboss_dr16_lya_dm_dh_over_rd.csv` | eBOSS DR16 Lyα values | BAO README source pointer | Published-source derived values for diagnostics | Lyα block input |
| `data/bao/eboss_dr16_lya_dm_dh_over_rd_cov2.cov` | eBOSS DR16 Lyα covariance | BAO README source pointer | Published-source covariance for diagnostics | Lyα block covariance |
| `data/bao/eboss_dr16_qso_dm_dh_over_rd.csv` | eBOSS DR16 QSO values | BAO README source pointer | Published-source derived values for diagnostics | QSO block input |
| `data/bao/eboss_dr16_qso_dm_dh_over_rd_cov2.cov` | eBOSS DR16 QSO covariance | BAO README source pointer | Published-source covariance for diagnostics | QSO block covariance |
| `data/bao/desi/README.md` | DESI BAO compact baseline README | Repository-authored DESI baseline notes | Repository documentation | Scope/provenance notes for Triangle-1 BAO leg |
| `data/bao/desi/desi_dr1_bao_baseline.csv` | DESI DR1 compact BAO baseline block table | Public DESI BAO DR1 summary values (compact diagnostic bundle) | Diagnostic compact bundle; verify upstream DESI terms/licensing for external redistribution | Deterministic Triangle-1 BAO baseline leg (M156) |
| `data/cmb/README.md` | CMB priors README | Repository-authored compressed-priors notes | Repository documentation | CMB bridge usage/scope notes |
| `data/cmb/planck2018_distance_priors.csv` | Placeholder CMB priors | CMB README (placeholder wiring file) | Internal placeholder for wiring/tests | Loader/schema wiring checks |
| `data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv` | CHW2018 Planck2018 priors vector | CMB README cites CHW2018 (arXiv:1808.05724) | Compressed-priors diagnostic input; not full spectra likelihood | Canonical CMB bridge vector |
| `data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov` | CHW2018 covariance | CMB README cites CHW2018 covariance | Compressed-priors diagnostic covariance | Canonical CMB bridge covariance |
| `data/cmb/planck2018_distance_priors_with_theory_floor.csv` | CMB priors with theory floor | CMB README (bridge/dev variant) | Development/bridge diagnostic variant | Optional bridge stress tests |
| `data/drift/README.md` | Drift README | Repository-authored drift dataset notes | Repository documentation | Drift contract and provenance guidance |
| `data/drift/andes_20yr_mock_lcdm_fiducial.csv` | Legacy drift mock | Drift README | Synthetic benchmark-style diagnostic data | Pipeline smoke/regression checks |
| `data/drift/elt_andes_liske_conservative_10yr_asimov.csv` | 10-year Asimov drift forecast | Drift README (Liske/ELT-style) | Forecast-style synthetic diagnostic data | Deterministic drift scenario |
| `data/drift/elt_andes_liske_conservative_20yr_asimov.csv` | 20-year Asimov drift forecast | Drift README (Liske/ELT-style) | Forecast-style synthetic diagnostic data | Canonical drift scenario |
| `data/drift/elt_andes_liske_conservative_20yr_mock_seed123.csv` | 20-year noisy drift mock (seeded) | Drift README | Deterministic seeded mock for diagnostics | Regression reproducibility checks |
| `data/drift/trost_2025_lcdm_benchmark.csv` | Trost 2025 benchmark table | Drift README citation pointer | Benchmark expectation table for diagnostics | External benchmark reference |
| `data/sn/pantheon_plus_shoes/pantheon_plus_shoes_hflow_mu.csv` | Pantheon+SH0ES Hubble-flow CSV | `data/README.md` conversion notes | Derived CSV from public release columns; verify upstream release terms for redistribution | SN Hubble-flow diagnostics |
| `data/sn/pantheon_plus_shoes/pantheon_plus_shoes_mu.csv` | Pantheon+SH0ES full CSV | `data/README.md` conversion notes | Derived CSV from public release columns; verify upstream release terms for redistribution | SN full-sample diagnostics |
| `data/structure/README.md` | Structure README | Repository-authored structure notes | Repository documentation | Structure data provenance guidance |
| `data/structure/fsigma8_gold2017_plus_zhao2018.csv` | fσ8 compilation | Structure README (Gold 2017 + Zhao 2018 context) | Transcribed compilation for diagnostic use | Growth/fσ8 diagnostic overlay |

## Reviewer guidance

For publication-facing reuse outside this repository snapshot, cite and verify
upstream dataset terms from the source papers/releases listed in the
corresponding data-folder README files.

## Pantheon+ full-covariance fetch path (M154)

- The canonical paper-grade SN epsilon path can consume full covariance via
  `scripts/phase4_pantheon_plus_epsilon_posterior.py --covariance-mode full`.
- Large upstream covariance assets are intentionally not required to be
  committed in git.
- Use `scripts/fetch_pantheon_plus_release.py` to fetch/copy pinned
  `mu` + `cov` files and emit deterministic SHA256 manifest metadata.
- The posterior script can verify that manifest (`--data-manifest`) and fails
  closed on SHA mismatches.

## DESI BAO baseline fetch path (M156)

- The canonical BAO baseline leg path can consume pinned compact products via
  `scripts/fetch_desi_bao_products.py`.
- The fetch helper emits deterministic SHA256 manifest metadata
  (`phase4_desi_bao_fetch_manifest_v1`) and can be used with
  `scripts/phase4_desi_bao_epsilon_or_rd_diagnostic.py --data-manifest ...`.
- Roadmap wording policy is timeline-agnostic:
  DR1 baseline; DR2 BAO/cosmology products as robustness checks when
  public/available in chosen likelihood tooling.
- Authoritative DESI references:
  - DR1 BAO/cosmology VAC documentation:
    https://data.desi.lbl.gov/doc/releases/dr1/vac/bao-cosmo-params/
  - DR2 papers/cosmology docs index:
    https://data.desi.lbl.gov/doc/papers/dr2/
  - DESI release note on DR2 cosmology chains/products:
    https://www.desi.lbl.gov/2025/10/06/desi-dr2-cosmology-chains-and-data-products-released/

## DESI DR1 Gaussian summary products for Triangle-1 paper-grade path (M157)

- Upstream source for BAO Gaussian summary files:
  `CobayaSampler/bao_data` repository (DESI 2024 BAO products), files:
  - `desi_2024_gaussian_bao_ALL_GCcomb_mean.txt`
  - `desi_2024_gaussian_bao_ALL_GCcomb_cov.txt`
- Conversion to internal loader format is deterministic via:
  `scripts/phase4_desi_bao_convert_gaussian_to_internal.py`
  producing `values.csv`, `cov.txt`, `dataset.csv` (`VECTOR_over_rd`).
- Fetch helper supports pinned preset:
  `scripts/fetch_desi_bao_products.py --preset dr1_gaussian_all_gccomb`
  (pinned commit + SHA256 manifest output).
- Terminology note (referee-safe):
  - **DR1** = full public data release portal baseline.
  - **DR2** = cosmology-results/chains summary products for inference robustness,
    not a claim that full underlying spectra/redshift products are publicly released.

## Planck compressed acoustic prior used in Triangle-1 closure (M157)

- Triangle-1 joint tool uses CHW2018 compressed Planck `lA` prior from:
  - `data/cmb/planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv`
- The tool derives `theta*=pi/lA` and propagates uncertainty to the BAO transformed covariance.
- This remains compressed-prior usage only; not a full CMB spectra likelihood.

## Paper-2 committed artifact policy (M158)

- Repository keeps source and templates under
  `papers/paper2_measurement_model_epsilon/` and deterministic build scripts.
- Large upstream Pantheon+/DESI source products stay outside git and are tracked through
  fetch manifests with SHA256 rows.
- Regeneration commands are documented in:
  - `docs/PAPER2_BUILD_AND_REPRODUCIBILITY.md`
  - `docs/ARXIV_SUBMISSION_CHECKLIST.md`

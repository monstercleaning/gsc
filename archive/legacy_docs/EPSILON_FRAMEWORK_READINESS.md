# Epsilon Framework Readiness (Phase-4A.9 Checklist)

## Scope & Non-claims
- This document is a **readiness audit** for Phase-4 epsilon-workstream planning.
- It is **not** a Paper-2 scientific result and does not claim new epsilon constraints.
- It does not alter physics semantics in current SigmaTensor/Phase-2/Phase-3 pipelines.
- It is a reviewer-facing checklist to make gaps machine-verifiable and testable.

## Current state (facts)
- Deterministic repo/snapshot/reviewer-pack machinery exists (`make_repo_snapshot.py`, `preflight_share_check.py`, reviewer packs).
- Deterministic claim-safety and schema-validation tooling exists (`docs_claims_lint.py`, `phase2_schema_validate.py`).
- Measurement-model core exists (`gsc/measurement_model.py`) with explicit scope/non-claim docs.
- Phase-3 low-z diagnostics exist (joint SN+BAO+RSD, scan, analysis, dossier flow).
- Drift-sign pre-check and no-go gap diagnostics exist (`phase4_sigmatensor_drift_sign_diagnostic.py`, `phase4_sigmatensor_optimal_control_gap_diagnostic.py`).
- Red-team and golden-demo automation exists (`phase4_red_team_check.py`, `phase4_cosmofalsify_demo.py`).
- Pantheon+ and BAO datasets are present for baseline low-z workflows under `data/`.

## M148 implemented: translator MVP
- Added minimal package API:
  - `gsc/epsilon/translator.py`
  - `gsc/epsilon/__init__.py`
- Added deterministic translator report tool:
  - `scripts/phase4_epsilon_translator_mvp.py`
  - output artifacts: `EPSILON_TRANSLATOR_MVP.json` and `EPSILON_TRANSLATOR_MVP.md`
- Added schema:
  - `schemas/phase4_epsilon_translator_report_v1.schema.json`
- Added deterministic + schema + git-less tests for the MVP report.

Run:

```bash
python3 scripts/phase4_epsilon_translator_mvp.py --repo-root the current framework --outdir out/epsilon_translator_mvp --deterministic 1 --format text
python3 scripts/phase2_schema_validate.py --auto --schema-dir schemas --json out/epsilon_translator_mvp/EPSILON_TRANSLATOR_MVP.json
```

What this proves:
- deterministic, portable translator artifact generation
- explicit toy input/output contract for epsilon channels

What this does **not** prove:
- no validated precision-test constraints
- no coupled SN/BAO likelihood wiring
- no coupling-model-conditioned bound combination

## M149 implemented: epsilon sensitivity matrix (toy)
- Added deterministic sensitivity scaffold:
  - `scripts/phase4_epsilon_sensitivity_matrix_toy.py`
  - output artifacts: `EPSILON_SENSITIVITY_MATRIX_TOY.json` and `EPSILON_SENSITIVITY_MATRIX_TOY.md`
- Added schema:
  - `schemas/phase4_epsilon_sensitivity_matrix_report_v1.schema.json`
- Added deterministic + schema + git-less tests for the sensitivity report.

Run:

```bash
python3 scripts/phase4_epsilon_sensitivity_matrix_toy.py --repo-root the current framework --outdir out/epsilon_sensitivity_toy --deterministic 1 --format text
python3 scripts/phase2_schema_validate.py --auto --schema-dir schemas --json out/epsilon_sensitivity_toy/EPSILON_SENSITIVITY_MATRIX_TOY.json
```

What this proves:
- deterministic analytic vs finite-difference sensitivity agreement in a toy setup
- explicit machine-readable sensitivity artifact for reviewer checks

What this does **not** prove:
- no real likelihood/covariance inference
- no precision-test data integration beyond pivot-proxy scaffolding

## M150 implemented: Pantheon+ epsilon posterior (SN-only, inference-layer)
- Added deterministic SN-only posterior report tool:
  - `scripts/phase4_pantheon_plus_epsilon_posterior.py`
  - output artifacts: `PANTHEON_EPSILON_POSTERIOR_REPORT.json`, `PANTHEON_EPSILON_POSTERIOR_REPORT.md`, deterministic PNG quicklooks
- Added schema:
  - `schemas/phase4_pantheon_plus_epsilon_posterior_report_v1.schema.json`
- Added deterministic + schema + git-less tests for the report tool.

Run:

```bash
python3 scripts/phase4_pantheon_plus_epsilon_posterior.py --repo-root the current framework --outdir out/pantheon_epsilon_posterior --deterministic 1 --format text
python3 scripts/phase2_schema_validate.py --auto --schema-dir schemas --json out/pantheon_epsilon_posterior/PANTHEON_EPSILON_POSTERIOR_REPORT.json
```

What this proves:
- deterministic inference-layer SN-only epsilon artifact exists
- measurement-model redshift remapping can be audited through schema-validated outputs

What this does **not** prove:
- no multi-probe epsilon inference (DESI BAO and precision constraints still open)

## M154 implemented: Pantheon+ full-covariance paper-grade path
- Extended posterior tool with explicit covariance switch:
  - `--covariance-mode {diag_only_proof_of_concept,full}`
  - full mode computes profile-likelihood chi2 with full covariance inverse.
- Added deterministic fetch/manifest helper:
  - `scripts/fetch_pantheon_plus_release.py`
  - emits pinned SHA256 manifest (`phase4_pantheon_plus_fetch_manifest_v1`).
- Added offline full-cov toy fixtures + deterministic/schema/git-less tests.

Run (toy full-cov, offline):

```bash
python3 scripts/phase4_pantheon_plus_epsilon_posterior.py --repo-root the current framework --outdir out/pantheon_epsilon_fullcov --deterministic 1 --format text --covariance-mode full --dataset tests/fixtures/phase4_m154/pantheon_toy_mu_fullcov.csv --covariance tests/fixtures/phase4_m154/pantheon_toy_cov.txt
python3 scripts/phase2_schema_validate.py --auto --schema-dir schemas --json out/pantheon_epsilon_fullcov/PANTHEON_EPSILON_POSTERIOR_REPORT.json
```

What this proves:
- deterministic full-covariance likelihood path exists
- report contract carries covariance mode + covariance metadata + optional pinned data-manifest metadata

What this does **not** prove:
- no multi-probe epsilon inference (DESI BAO and precision constraints still open)

## M155 implemented: Pantheon+ paper-grade plotting/report contract (v2)
- Added `--run-mode {demo,paper_grade}`:
  - `paper_grade` requires `--covariance-mode full`, `--data-manifest`, and matplotlib availability.
  - `demo` mode remains offline-safe with deterministic fallback plotting.
- Added deterministic always-on plot artifacts:
  - `epsilon_posterior_1d.png`
  - `omega_m_vs_epsilon.png`
- Added report schema v2:
  - `schemas/phase4_pantheon_plus_epsilon_posterior_report_v2.schema.json`
  - includes `run_mode`, `plot_backend`, artifact SHA rows, and optional `data_manifest_sha256`.

Run:

```bash
python3 scripts/phase4_pantheon_plus_epsilon_posterior.py --repo-root the current framework --outdir out/pantheon_eps_demo --deterministic 1 --format text --run-mode demo --toy 1
python3 scripts/phase4_pantheon_plus_epsilon_posterior.py --repo-root the current framework --outdir out/pantheon_eps_paper --deterministic 1 --format text --run-mode paper_grade --covariance-mode full --dataset tests/fixtures/phase4_m154/pantheon_toy_mu_fullcov.csv --covariance tests/fixtures/phase4_m154/pantheon_toy_cov.txt --data-manifest tests/fixtures/phase4_m154/pantheon_toy_manifest.json
python3 scripts/phase2_schema_validate.py --auto --schema-dir schemas --json out/pantheon_eps_paper/PANTHEON_EPSILON_POSTERIOR_REPORT.json
```

## M156 implemented: DESI BAO Triangle-1 baseline leg
- Added pinned compact-product fetch helper:
  - `scripts/fetch_desi_bao_products.py`
  - schema: `schemas/phase4_desi_bao_fetch_manifest_v1.schema.json`
- Added deterministic BAO leg diagnostic:
  - `scripts/phase4_desi_bao_epsilon_or_rd_diagnostic.py`
  - artifacts: `DESI_BAO_TRIANGLE1_REPORT.json`, `DESI_BAO_TRIANGLE1_REPORT.md`,
    `epsilon_posterior_1d.png`, `omega_m_vs_epsilon.png`
  - schema: `schemas/phase4_desi_bao_triangle1_report_v1.schema.json`
- Baseline policy wording:
  - DR1 baseline in the compact deterministic bundle
  - DR2 BAO/cosmology products as robustness checks once public/available in chosen tooling

Run:

```bash
python3 scripts/fetch_desi_bao_products.py --source data/bao/desi --outdir out/desi_bao_cache --manifest-out out/desi_bao_cache/DESI_FETCH_MANIFEST.json --deterministic 1 --format text
python3 scripts/phase4_desi_bao_epsilon_or_rd_diagnostic.py --repo-root the current framework --outdir out/desi_bao_triangle1 --deterministic 1 --format text --dataset data/bao/desi/desi_dr1_bao_baseline.csv --data-manifest out/desi_bao_cache/DESI_FETCH_MANIFEST.json
python3 scripts/phase2_schema_validate.py --auto --schema-dir schemas --json out/desi_bao_triangle1/DESI_BAO_TRIANGLE1_REPORT.json
```

## M157 implemented: Triangle-1 joint SN+BAO+Planck acoustic-scale closure
- Added deterministic joint runner:
  - `scripts/phase4_triangle1_sn_bao_planck_thetastar.py`
  - artifacts: `TRIANGLE1_SN_BAO_PLANCK_REPORT.json/.md` and deterministic PNG plots
- Added deterministic converter for official DR1 Gaussian summary text files:
  - `scripts/phase4_desi_bao_convert_gaussian_to_internal.py`
  - converts `desi_2024_gaussian_bao_ALL_GCcomb_{mean,cov}.txt` into internal `VECTOR_over_rd` dataset files
- Added schema:
  - `schemas/phase4_triangle1_report_v1.schema.json`
- Joint assumptions are explicit in report:
  - inference-layer epsilon mapping
  - `r_d≈r_s` closure via Planck compressed `lA` prior (`theta*=pi/lA`)
  - compressed CMB prior only (not full CMB likelihood)

Run (demo):

```bash
python3 scripts/phase4_triangle1_sn_bao_planck_thetastar.py --repo-root the current framework --outdir out/triangle1_demo --deterministic 1 --run-mode demo --toy 1 --format text
python3 scripts/phase2_schema_validate.py --auto --schema-dir schemas --json out/triangle1_demo/TRIANGLE1_SN_BAO_PLANCK_REPORT.json
```

## M158 implemented: publication-pack wiring for Paper 2 / Paper 4
- Added deterministic Paper-2 assets builder:
  - `scripts/phase4_build_paper2_assets.py`
  - schema `schemas/phase4_paper2_assets_manifest_v1.schema.json`
- Added Paper-2 source/build/submission path:
  - `papers/paper2_measurement_model_epsilon/`
  - `scripts/build_paper2.sh`
  - `scripts/phase4_make_arxiv_bundle_paper2.py`
  - `docs/ARXIV_SUBMISSION_CHECKLIST.md`
  - `docs/PAPER2_BUILD_AND_REPRODUCIBILITY.md`
- Added JOSS preflight workflow:
  - `scripts/phase4_joss_preflight.py`
  - schema `schemas/phase4_joss_preflight_report_v1.schema.json`
  - `docs/JOSS_SUBMISSION.md`
  - `docs/JOSS_SUBMISSION_CHECKLIST.md`

Run:

```bash
python3 scripts/phase4_build_paper2_assets.py --preset ci_smoke --seed 0 --workdir out/paper2_ci_work --outdir out/paper2_ci_assets --format text
python3 scripts/phase2_schema_validate.py --auto --schema-dir schemas --json out/paper2_ci_assets/paper2_assets_manifest.json
python3 scripts/phase4_joss_preflight.py --repo-root . --format json
```

## What is missing (remaining gaps)

### Theory/modeling gaps
- [ ] **TH-001** Coupling-model conditionality for combining precision bounds is not encoded as machine-readable policy.
- [ ] **TH-004** No deterministic consistency checker for cross-probe epsilon mapping assumptions.

### Data/likelihood gaps
- [x] **DATA-002** DESI BAO baseline leg is wired to epsilon remapping and r_d handling (`phase4_desi_bao_epsilon_or_rd_diagnostic.py`, M156).
- [x] **DATA-003** Deterministic Triangle-1 joint SN+BAO+Planck artifact implemented (`phase4_triangle1_sn_bao_planck_thetastar.py`, M157).
- [ ] **DATA-004** No explicit covariance/inter-dependence treatment for mixed precision-test + cosmology combinations.

### Implementation gaps
- [ ] **IMPL-002** No non-toy epsilon report coupled to real precision-test likelihood inputs.
- [ ] **IMPL-003** No dedicated epsilon regression/unit test suite for translator branches and policy toggles.
- [x] **IMPL-005** Publication/reviewer-pack integration path exists via deterministic paper artifact + submission workflow tooling (M158).

## MVP definition for 4B.1 (translator module)
- **Input contract (minimum):**
  - baseline cosmology record (H0, Omega_m, optional nuisance set)
  - deterministic probe metadata (probe id, redshift support, observable type)
  - coupling-model selector (explicit enum, no implicit default coupling assumptions)
- **Output contract (minimum):**
  - translator record JSON with `schema` id, deterministic `created_utc`, and `paths_redacted=true`
  - normalized epsilon parameter vector + covariance (or diagonal fallback with explicit marker)
  - validity flags (domain limits, assumptions, coupling-model branch id)
  - digest/hash for deterministic reproducibility across runs
- **Validation gates (minimum):**
  - schema auto-validation via `phase2_schema_validate.py --auto`
  - deterministic byte-equality test under fixed inputs
  - git-less snapshot execution test

## Risk notes
- **Apples vs oranges risk:** Combining precision-test channels without an explicit coupling model can produce invalid aggregate statements.
- **Conditioned interpretation:** Any combined bound must be labeled as conditional on the selected coupling-model branch.
- **Cross-probe covariance risk:** Naive quadrature/independence assumptions can understate uncertainty.
- **Reviewer safety rule:** If coupling assumptions are not explicit, report single-channel bounds only.

## Effort estimate (S/M/L)
- TH-001 coupling-policy encoding: **M**
- TH-004 cross-probe consistency checker: **M**
- DATA-001 Pantheon+ epsilon full-covariance path: **Completed (M154)**
- DATA-002 DESI BAO baseline leg: **Completed (M156)**; full collaboration-likelihood parity remains future work.
- DATA-003 deterministic joint epsilon report: **M**
- DATA-004 covariance conditionality policy: **L**
- IMPL-002 deterministic epsilon report + real-input bridge: **M**
- IMPL-003 epsilon tests (unit + regression): **M**
- IMPL-005 reviewer-pack epsilon profile: **Completed (M158)**

## Recommended next milestones (outline)
- **M158 (4B.6):** conditional bound-combination policy checker (coupling-model aware).
- **M159:** precision-test data bridge with explicit apples-vs-oranges coupling branch controls.

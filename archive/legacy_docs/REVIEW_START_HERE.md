# Review Start Here (Phase-4, current v11 series)

Introduced in M139; maintained through current Phase-4 milestones.

This page is the fastest way for a reviewer to validate repository reality and
scope boundaries.

Maintainer affiliation note: Dimitar Baev (independent) with sponsor support from
Monster Cleaning Labs; see `docs/AFFILIATION_AND_BRANDING.md`.

## 1) Read in this order

1. `docs/project_status_and_roadmap.md` (current status + scope)
2. `docs/GSC_Consolidated_Roadmap_v2.8.md` (forward roadmap, canonical)
   Roadmap wording patch: `docs/GSC_Consolidated_Roadmap_v2.8.1_patch.md`
   clarifies DESI DR2 semantics (BAO/cosmology products vs full portal release labels).
3. `docs/phase3_sigma_tensor_model_v1.md` (model scope)
4. `docs/VERIFICATION_MATRIX.md` (claim-to-check mapping)
5. `docs/FRAMES_UNITS_INVARIANTS.md` (what is invariant vs definitional)
6. `docs/PRIOR_ART_AND_NOVELTY_MAP.md` (prior-art boundaries)

## Legacy artifacts

- Legacy `v10*`-named files are retained for provenance only.
- Active reviewer path is still this v11 entrypoint and linked v11 docs/tools.
- Policy + allowlist:
  `docs/LEGACY_VERSIONED_ARTIFACTS.md`

## 2) Run these checks first

```bash
python3 scripts/phase2_repo_inventory.py --repo-root the current framework --require-present --format text
python3 scripts/docs_claims_lint.py --repo-root the current framework
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -v
```

## 2b) Task 4A.-1 pre-check (Paper 1 supporting no-go drift diagnostic)

```bash
python3 scripts/phase4_sigmatensor_drift_sign_diagnostic.py --outdir out/drift_sign_diagnostic --format text
python3 scripts/phase2_schema_validate.py --auto --schema-dir schemas --json out/drift_sign_diagnostic/DRIFT_SIGN_DIAGNOSTIC.json
```

This diagnostic provides deterministic supporting no-go evidence via
`dz/dt0 = H0(1+z)-H(z)` over a configurable lambda grid and includes mandatory
evaluation points `z={2,3,4,5}`. In Roadmap v2.8 it is not the primary
falsifier channel.

## 2c) Task 4A.-0 repurposed: no-go gap quantification

```bash
python3 scripts/phase4_sigmatensor_optimal_control_gap_diagnostic.py --outdir out/gap_diagnostic --format text
python3 scripts/phase2_schema_validate.py --auto --schema-dir schemas --json out/gap_diagnostic/GAP_DIAGNOSTIC.json
```

This diagnostic quantifies how much multiplicative deformation `A(z)` of
SigmaTensor `H(z)` is needed to force positive drift over `z={2,3,4,5}`, while
minimizing comoving-distance mismatch and checking canonical `w(z) >= -1`.

## 2d) Task 4A.9 epsilon-framework readiness audit

```bash
python3 scripts/phase4_epsilon_framework_readiness_audit.py --repo-root the current framework --outdir out/epsilon_readiness --deterministic 1 --format text
python3 scripts/phase2_schema_validate.py --auto --schema-dir schemas --json out/epsilon_readiness/EPSILON_FRAMEWORK_READINESS_AUDIT.json
```

Expected artifacts:
- `out/epsilon_readiness/EPSILON_FRAMEWORK_READINESS_AUDIT.json`
- `out/epsilon_readiness/EPSILON_FRAMEWORK_READINESS_AUDIT.md`

Success condition:
- schema auto-validation exits 0
- `gap_list` and `recommended_next_tasks` are present
- report keeps `paths_redacted=true` and uses relative detected asset paths

## 2e) Task 4B.1 epsilon translator MVP

```bash
python3 scripts/phase4_epsilon_translator_mvp.py --repo-root the current framework --outdir out/epsilon_translator_mvp --deterministic 1 --format text
python3 scripts/phase2_schema_validate.py --auto --schema-dir schemas --json out/epsilon_translator_mvp/EPSILON_TRANSLATOR_MVP.json
```

Expected artifacts:
- `out/epsilon_translator_mvp/EPSILON_TRANSLATOR_MVP.json`
- `out/epsilon_translator_mvp/EPSILON_TRANSLATOR_MVP.md`

Success condition:
- translator script exits 0
- report schema auto-validation exits 0
- report includes `paths_redacted=true` and deterministic `created_utc`

## 2f) Task 4B.2 epsilon sensitivity matrix (toy)

```bash
python3 scripts/phase4_epsilon_sensitivity_matrix_toy.py --repo-root the current framework --outdir out/epsilon_sensitivity_toy --deterministic 1 --format text
```

Expected artifacts:
- `out/epsilon_sensitivity_toy/EPSILON_SENSITIVITY_MATRIX_TOY.json`
- `out/epsilon_sensitivity_toy/EPSILON_SENSITIVITY_MATRIX_TOY.md`

Success condition:
- script exits 0
- report has `status=ok` and `self_check.self_check_ok=true`
- report is schema-valid via:
  `python3 scripts/phase2_schema_validate.py --auto --schema-dir schemas --json out/epsilon_sensitivity_toy/EPSILON_SENSITIVITY_MATRIX_TOY.json`

## 2g) Task 4B.3 Pantheon+ epsilon posterior (SN-only; M155 paper-grade preset)

```bash
# demo/offline mode (works without matplotlib using deterministic fallback plots)
python3 scripts/phase4_pantheon_plus_epsilon_posterior.py --repo-root the current framework --outdir out/pantheon_epsilon_posterior_demo --deterministic 1 --format text --run-mode demo --toy 1

# paper-grade preset (requires matplotlib + full covariance + pinned data manifest)
python3 scripts/phase4_pantheon_plus_epsilon_posterior.py --repo-root the current framework --outdir out/pantheon_epsilon_posterior --deterministic 1 --format text --run-mode paper_grade --covariance-mode full --dataset tests/fixtures/phase4_m154/pantheon_toy_mu_fullcov.csv --covariance tests/fixtures/phase4_m154/pantheon_toy_cov.txt --data-manifest tests/fixtures/phase4_m154/pantheon_toy_manifest.json
python3 scripts/phase2_schema_validate.py --auto --schema-dir schemas --json out/pantheon_epsilon_posterior/PANTHEON_EPSILON_POSTERIOR_REPORT.json
```

Expected artifacts:
- `out/pantheon_epsilon_posterior/PANTHEON_EPSILON_POSTERIOR_REPORT.json`
- `out/pantheon_epsilon_posterior/PANTHEON_EPSILON_POSTERIOR_REPORT.md`
- `out/pantheon_epsilon_posterior/epsilon_posterior_1d.png`
- `out/pantheon_epsilon_posterior/omega_m_vs_epsilon.png`

Success condition:
- script exits 0 and schema auto-validation exits 0
- report has `schema=phase4_pantheon_plus_epsilon_posterior_report_v2`
- report has `covariance_mode=full`, `run_mode=paper_grade`, and `plot_backend=matplotlib` for paper-grade runs
- report has `paths_redacted=true` and portability count equals zero

Note:
- M150 diagonal mode (`diag_only_proof_of_concept`) remains available as a fast proof-of-concept path.
- M154 full mode is the canonical covariance-aware path; M155 adds the explicit `paper_grade` preset gate.
- For external Pantheon+ assets, generate a pinned SHA256 manifest with:
  `python3 scripts/fetch_pantheon_plus_release.py --source <release_dir_or_url> --outdir <cache_dir> --manifest-out <cache_dir>/PANTHEON_FETCH_MANIFEST.json`

## 2h) Task 4B.4 Triangle-1 BAO baseline leg (M156)

```bash
# deterministic local baseline fetch/manifest (offline-friendly)
python3 scripts/fetch_desi_bao_products.py --source data/bao/desi --outdir out/desi_bao_cache --manifest-out out/desi_bao_cache/DESI_FETCH_MANIFEST.json --deterministic 1 --format text

# deterministic BAO leg diagnostic
python3 scripts/phase4_desi_bao_epsilon_or_rd_diagnostic.py --repo-root the current framework --outdir out/desi_bao_triangle1 --deterministic 1 --format text --dataset data/bao/desi/desi_dr1_bao_baseline.csv --data-manifest out/desi_bao_cache/DESI_FETCH_MANIFEST.json
python3 scripts/phase2_schema_validate.py --auto --schema-dir schemas --json out/desi_bao_triangle1/DESI_BAO_TRIANGLE1_REPORT.json
```

Expected artifacts:
- `out/desi_bao_triangle1/DESI_BAO_TRIANGLE1_REPORT.json`
- `out/desi_bao_triangle1/DESI_BAO_TRIANGLE1_REPORT.md`
- `out/desi_bao_triangle1/epsilon_posterior_1d.png`
- `out/desi_bao_triangle1/omega_m_vs_epsilon.png`

Success condition:
- script exits 0 and schema auto-validation exits 0
- report has `schema=phase4_desi_bao_triangle1_report_v1`
- report documents `rd_handling.mode=profile_rd` (or explicit fixed mode when selected)
- report keeps `paths_redacted=true` and portability match count equal to zero

## 2i) Task 4B.5 Triangle-1 joint SN+BAO+Planck acoustic scale (M157)

```bash
# demo/toy (offline fast path)
python3 scripts/phase4_triangle1_sn_bao_planck_thetastar.py --repo-root the current framework --outdir out/triangle1_demo --deterministic 1 --run-mode demo --toy 1 --format text

# paper-grade path (requires full-cov Pantheon manifest + converted DESI DR1 Gaussian dataset + BAO manifest)
python3 scripts/phase4_triangle1_sn_bao_planck_thetastar.py --repo-root the current framework --outdir out/triangle1_paper --deterministic 1 --run-mode paper_grade --covariance-mode full --pantheon-mu-csv <mu.csv> --pantheon-covariance <cov.cov> --pantheon-data-manifest <pantheon_manifest.json> --bao-desi-dr1-dataset <dataset.csv> --bao-data-manifest <desi_manifest.json> --format text
python3 scripts/phase2_schema_validate.py --auto --schema-dir schemas --json out/triangle1_paper/TRIANGLE1_SN_BAO_PLANCK_REPORT.json
```

Expected artifacts:
- `out/triangle1_paper/TRIANGLE1_SN_BAO_PLANCK_REPORT.json`
- `out/triangle1_paper/TRIANGLE1_SN_BAO_PLANCK_REPORT.md`
- `out/triangle1_paper/epsilon_posterior_1d.png`
- `out/triangle1_paper/omega_m_vs_epsilon.png`

Success condition:
- script exits 0 and schema auto-validation exits 0 (`phase4_triangle1_report_v1`)
- report includes explicit assumptions (`r_d≈r_s` closure and compressed Planck prior scope)
- deterministic reruns are byte-identical (JSON/MD/PNG) under fixed inputs

## 2j) Publish readiness (Paper 2 + Paper 4 workflows)

```bash
# Paper 2 deterministic CI smoke assets
python3 scripts/phase4_build_paper2_assets.py --preset ci_smoke --seed 0 --workdir out/paper2_ci_work --outdir out/paper2_ci_assets --format text
# optional supplementary theory annex (QCD<->Gravity sanity-check bundle)
python3 scripts/phase4_build_paper2_assets.py --preset ci_smoke --seed 0 --workdir out/paper2_ci_work --outdir out/paper2_ci_assets --include-theory-annex --format text
python3 scripts/phase2_schema_validate.py --auto --schema-dir schemas --json out/paper2_ci_assets/paper2_assets_manifest.json

# Paper 2 PDF + arXiv bundle
export PAPER2_ASSETS_DIR=out/paper2_ci_assets
bash scripts/build_paper2.sh
python3 scripts/phase4_make_arxiv_bundle_paper2.py --paper-dir papers/paper2_measurement_model_epsilon --assets-dir out/paper2_ci_assets --out-tar paper_assets/paper2_arxiv_bundle.tar.gz --format text

# JOSS (Paper 4) repository preflight
python3 scripts/phase4_joss_preflight.py --repo-root . --format json
```

Expected artifacts:
- `out/paper2_ci_assets/paper2_assets_manifest.json`
- `out/paper2_ci_assets/numbers.tex`
- `out/paper2_ci_assets/theory/qcd_gravity_bridge/` (when `--include-theory-annex` is enabled)
- `paper_assets/paper2_measurement_model_epsilon.pdf`
- `paper_assets/paper2_arxiv_bundle.tar.gz`

Success condition:
- assets manifest schema validates (`phase4_paper2_assets_manifest_v1`)
- arXiv bundle script emits deterministic tarball summary
- JOSS preflight exits 0 and JSON schema is `phase4_joss_preflight_report_v1`

Operator docs:
- `docs/ARXIV_SUBMISSION_CHECKLIST.md`
- `docs/ARXIV_UPLOAD_CHECKLIST.md`
- `docs/ARXIV_METADATA.md`
- `docs/PAPER2_BUILD_AND_REPRODUCIBILITY.md`
- `docs/PAPER2_SUBMISSION_GUIDE.md`
- `docs/JOSS_AUTHORS.md`
- `docs/JOSS_SUBMISSION_CHECKLIST.md`
- `docs/JOSS_SUBMISSION_GUIDE.md`
- `docs/AFFILIATION_AND_BRANDING.md`
- `outreach/labs_site_copy/labs_transparency.md`

## 3) Red Team quick check

```bash
python3 scripts/phase4_red_team_check.py --repo-root the current framework --outdir out/red_team --strict 1 --format text
```

Inspect:
- `out/red_team/RED_TEAM_REPORT.json`
- `out/red_team/RED_TEAM_REPORT.md`

## 4) CosmoFalsify demo quickstart (3 commands)

```bash
python3 scripts/phase4_cosmofalsify_demo.py --outdir out/cosmofalsify_demo --created-utc 946684800 --format text
python3 scripts/phase2_schema_validate.py --auto --schema-dir schemas --json out/cosmofalsify_demo/cosmofalsify_demo_report.json
cat out/cosmofalsify_demo/cosmofalsify_demo_report.json
```

Expected artifacts:
- `out/cosmofalsify_demo/cosmofalsify_demo_report.json`
- `out/cosmofalsify_demo/cosmofalsify_demo_report.md`
- `out/cosmofalsify_demo/artifacts/bundle.zip`

Success condition:
- report `status` is `ok`
- all stage rows in `stages` are `ok`
- schema validation command exits 0

## 5) Verify packaged-share hygiene

```bash
python3 scripts/make_repo_snapshot.py --profile review_with_data --zip-out GSC_review_with_data.zip
python3 scripts/preflight_share_check.py --path GSC_review_with_data.zip --max-mb 800 --format text
```

## 6) Canonical artifacts to inspect

- Scan plans/rows: `phase3_scan_sigmatensor_lowz_joint.py`
- Scan analysis + top candidates: `phase3_analyze_sigmatensor_lowz_scan.py`
- Candidate dossier: `phase3_make_sigmatensor_candidate_dossier_pack.py`
- Dossier quicklook: `phase3_dossier_quicklook_report.py`
- Provenance/schema checks: `phase2_lineage_dag.py`, `phase2_schema_validate.py`

## 7) Scope discipline

- The repository is positioned as a reproducible evaluation framework.
- Current deliverables are diagnostic and falsification-oriented.
- CMB-facing diagnostics in this branch are compressed-priors diagnostic-only;
  full perturbation closure and full CMB spectra likelihood fitting are not
  claimed as completed.

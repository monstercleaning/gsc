# Project Status and Roadmap

## Status snapshot (what exists today)

- **Late-time (canonical):** measurement-model pipeline, SN/BAO likelihood paths, and redshift-drift supporting no-go diagnostic tooling are implemented and reproducible.
- **Early-time Phase-2 E2 (bridge):** compressed CMB priors / shift-parameter diagnostics, deterministic scan-plan-shard-merge-bundle workflow, and explicit closure diagnostics are implemented; closure remains in progress.
- **Structure formation (bridge):** linear-theory diagnostics exist (`T(k)` approximations, linear growth `D,f`, `fσ8` reporting, RSD overlay), integrated as optional diagnostics in Phase-2 triage.

## Phase-4 pivot (M139)

- Consolidated roadmap source of truth: `docs/GSC_Consolidated_Roadmap_v2.8.md`.
- Referee-safe wording patch for DESI DR2 semantics:
  `docs/GSC_Consolidated_Roadmap_v2.8.1_patch.md`.
- Focus shift: reviewer UX, verification traceability, and claim-discipline hardening.
- New reviewer-start and verification docs map scripts/tests directly to acceptance checks.
- New frames/units note separates definitional choices from invariant observables.
- New data/license and onboarding policy docs formalize small committed reviewer datasets.
- New DM memo formalizes interpretation stance and future evidence gates.
- M141 adds a deterministic red-team regression script (`phase4_red_team_check.py`) and a prior-art/novelty boundary map for reviewer audits.
- M142 adds Paper-4 submission scaffold files (`paper.md`, `paper.bib`, contribution/conduct docs) and a deterministic git-less golden demo (`phase4_cosmofalsify_demo.py`) with schema-validated reporting.
- M145 adds Task 4A.-1 deterministic drift-sign diagnostics (`phase4_sigmatensor_drift_sign_diagnostic.py`) with schema-validated reviewer artifacts (`phase4_sigmatensor_drift_sign_diagnostic_report_v1`).
- M146 repurposes Task 4A.-0 into a deterministic no-go gap quantification artifact (`phase4_sigmatensor_optimal_control_gap_diagnostic.py`) with schema-validated report outputs (`phase4_sigmatensor_optimal_control_gap_diagnostic_report_v1`).
- M147 adds Task 4A.9 epsilon-framework readiness assessment artifacts (`EPSILON_FRAMEWORK_READINESS.md` + `phase4_epsilon_framework_readiness_audit.py`) with deterministic schema-validated audit reporting.
- M148 implements Task 4B.1 translator MVP artifacts (`gsc/epsilon/translator.py` + `phase4_epsilon_translator_mvp.py`) with deterministic schema-validated reporting (`phase4_epsilon_translator_report_v1`) and git-less snapshot tests.
- M149 implements Task 4B.2 toy epsilon sensitivity matrix artifacts (`gsc/epsilon/sensitivity.py` + `phase4_epsilon_sensitivity_matrix_toy.py`) with deterministic analytic-vs-finite-difference self-check reporting (`phase4_epsilon_sensitivity_matrix_report_v1`) and git-less snapshot tests.
- M150 syncs canonical narrative with Roadmap v2.8 (drift-sign as supporting no-go diagnostic, not primary discriminator) and adds deterministic SN-only Pantheon+ epsilon posterior artifacts (`phase4_pantheon_plus_epsilon_posterior.py`, schema `phase4_pantheon_plus_epsilon_posterior_report_v1`).
- M154 upgrades the Pantheon+ epsilon posterior path with deterministic full-covariance support and pinned data-manifest verification (`fetch_pantheon_plus_release.py` + `phase4_pantheon_plus_epsilon_posterior.py --covariance-mode full`), while keeping the M150 diagonal mode as a proof-of-concept fallback.
- M155 adds a paper-grade preset gate to the Pantheon+ posterior tool (`--run-mode paper_grade` requires `--covariance-mode full` + `--data-manifest` + matplotlib) and deterministic reviewer plots (`epsilon_posterior_1d.png`, `omega_m_vs_epsilon.png`) under schema `phase4_pantheon_plus_epsilon_posterior_report_v2`.
- M156 adds the deterministic DESI BAO Triangle-1 baseline leg: pinned compact-product fetch manifesting (`fetch_desi_bao_products.py`, schema `phase4_desi_bao_fetch_manifest_v1`) plus a schema-validated BAO epsilon/r_d diagnostic report (`phase4_desi_bao_epsilon_or_rd_diagnostic.py`, schema `phase4_desi_bao_triangle1_report_v1`) with deterministic PNG artifacts.
- M157 adds a deterministic Triangle-1 joint SN+BAO+Planck acoustic-scale artifact (`phase4_triangle1_sn_bao_planck_thetastar.py`, schema `phase4_triangle1_report_v1`) and a deterministic DESI DR1 Gaussian converter (`phase4_desi_bao_convert_gaussian_to_internal.py`) for paper-grade BAO full-covariance inputs.
- M158 adds publication-pack tooling: deterministic Paper-2 assets builder (`phase4_build_paper2_assets.py`, schema `phase4_paper2_assets_manifest_v1`), Paper-2 LaTeX/arXiv workflow (`build_paper2.sh`, `phase4_make_arxiv_bundle_paper2.py`, `docs/ARXIV_SUBMISSION_CHECKLIST.md`, `docs/PAPER2_BUILD_AND_REPRODUCIBILITY.md`), and JOSS readiness workflow (`phase4_joss_preflight.py`, schema `phase4_joss_preflight_report_v1`, `docs/JOSS_SUBMISSION_CHECKLIST.md`).
- M160 adds a deterministic QCD<->Gravity bridge sanity-check annex (`bridges/phase4_qcd_gravity_bridge_v0.1`) with explicit non-claim guardrails, order-of-magnitude induced-gravity/vacuum-scaling numbers, and a model-conditional kill-test matrix; `phase4_build_paper2_assets.py --include-theory-annex` can copy this supplementary bundle into Paper-2 assets without changing core Paper-2 claims.
- M161 adds publication/outreach branding pack content (Monster Cleaning Labs affiliation notes, labs-site copy pages, and white-hat outreach templates) with deterministic inventory/test gating; no physics semantics changed.
- M159 adds operator-ready submission packaging docs/metadata for immediate UI upload: `docs/ARXIV_METADATA.md`, `docs/ARXIV_UPLOAD_CHECKLIST.md`, `docs/PAPER2_SUBMISSION_GUIDE.md`, `docs/JOSS_AUTHORS.md`, `docs/JOSS_SUBMISSION_GUIDE.md`, plus root `.zenodo.json` release metadata.
- M153 completes residual narrative/tooling sync after the v2.8 pivot: onboarding and canonical verification/docs now enforce drift-sign as historical/supporting only (never a primary discriminator), with a dedicated regression guard test.
- M152 adds a reviewer-safe legacy filename hygiene policy (`docs/LEGACY_VERSIONED_ARTIFACTS.md`) plus a deterministic git-less guardrail test that blocks new `v10*` filenames outside approved legacy provenance zones.
- Scope remains diagnostic/falsification-oriented; this milestone does not add physics semantics.
- Publication readiness note: after M159, the repository includes deterministic workflows and operator-facing upload guides/metadata for Paper 2 (arXiv) and Paper 4 (JOSS), while preserving claim-safe scope boundaries.

## External expert feedback (summary) and current status

- **Early-time/CMB bridge risk:** acknowledged. Current Phase-2 E2 workflow uses compressed/distance priors diagnostics; full TT/TE/EE spectra fitting is not implemented in canonical scope.
- **Origin of `sigma(t)`:** acknowledged. `k(sigma)` remains an ansatz/identification choice in this release; FRG/asymptotic-safety derivation-level support is future work.
- **Structure formation / DM stance:** acknowledged. We provide linear-theory diagnostics (transfer + growth + RSD overlays), but we do not claim full perturbation closure and we do not claim dark matter is solved/eliminated.
- **Operational sharing hygiene:** acknowledged. Share snapshots should use `make_repo_snapshot.py --profile share`; do not zip raw worktrees containing `.git/.venv/results/paper_assets` and OS junk.

## External expert feedback -> applied actions (M93 update)

- **Early-universe bridge:** deterministic Phase-2 E2 compressed-priors pipeline remains active; full CMB spectra remain deferred scope.
- **Sigma-origin track:** flow-table ingestion scaffold (M92) is extended with Padé `k_*` fit reporting (M93) for quantitative comparison against externally provided RG/FRG tables.
- **Structure track:** linear growth/transfer/fsigma8/RSD diagnostics remain integrated as optional sanity overlays; full perturbation and non-linear pipelines remain deferred.
- **Hygiene track:** snapshot/cleanup workflow remains the canonical sharing path to avoid `.git/.venv/results/paper_assets` archive bloat.

## External expert feedback — addressed vs open (M94)

- **Addressed in Phase-2 (operational):**
  - CMB bridge is wired through compressed-priors E2 diagnostics with deterministic scan/merge/report tooling.
  - Structure-growth sanity checks are integrated via linear-theory `fσ8` overlays and can now drive refine-plan ranking with joint `chi2_total + rsd_chi2`.
  - Sigma-origin groundwork includes deterministic FRG flow-table ingestion and Padé `k_*` fit reporting.
- **Open / deferred scope:**
  - Full TT/TE/EE peak-level CMB spectra fitting is not implemented in canonical the current framework scope.
  - First-principles FRG/asymptotic-safety derivation of `sigma(t)` is not implemented.
  - Full perturbation/non-linear structure-formation pipeline is not implemented.
  - Dark-matter interpretation is not marked as resolved; current diagnostics use standard effective matter-content parameterization.

### Share snapshot hygiene (operational reminder)

- Do not include `.git/`, `.venv/`, `__MACOSX/`, `.DS_Store`, `results/`, `paper_assets*/`, or local legacy unpack trees in ad-hoc manual archives.
- Use deterministic share export:
  `python3 scripts/make_repo_snapshot.py --profile share --format zip --out GSC_share.zip`
- If local ignored bloat grows, run:
  `python3 scripts/clean_ignored_bloat.py --root . --mode report`

## External expert feedback (M95 follow-through): explicit model knobs

- **Early-universe bridge status (implemented):** Phase-2 E2 scan/jobgen/merge/bundle
  remains deterministic around compressed CMB priors and microphysics-plausibility
  diagnostics; this is still not a full TT/TE/EE spectra pipeline.
- **Sigma-origin status (implemented as tooling):** FRG flow-table ingest + Padé
  fit reports remain exploratory, phenomenological ansatz-level interfaces and
  are not first-principles derivations.
- **Structure overlay reproducibility (implemented):**
  `phase2_e2_scan.py --rsd-overlay` now supports explicit
  `--rsd-transfer-model`, `--rsd-ns`, and `--rsd-k-pivot` knobs. They are
  effective only in `derived_As` mode and are tracked in additive `rsd_*`
  metadata.
- **Open items (unchanged):** full CMB anisotropy spectra, full Boltzmann
  perturbations, non-linear structure formation, and dark-matter microphysics
  interpretation remain future work (not implemented in the current framework canonical scope).

## External expert feedback (M96 follow-through): joint scan objective wiring

- Phase-2 scan now supports an opt-in joint scalar objective
  (`--chi2-objective joint`) that combines compressed-priors CMB and RSD
  overlay terms for scan-time scoring.
- Default behavior is unchanged (`--chi2-objective cmb`), so legacy CMB-only
  runs remain byte-compatible unless the new flags are enabled.
- This remains an operational linear-diagnostic bridge (compressed CMB priors +
  linear-growth RSD overlay), not a full TT/TE/EE spectra pipeline and not a
  full perturbation/non-linear structure-formation closure.

## External review themes -> project reality (as of v10.1.1-phase2-m97)

- **Early Universe / CMB bridge:** implemented as compressed-priors/shift-parameter
  diagnostics with deterministic Phase-2 scan+bundle tooling; full TT/TE/EE
  peak-level Boltzmann spectra fitting remains deferred.
- **Sigma-field origin / FRG:** implemented as claim-safe status docs plus
  deterministic ingestion/fit scaffolds for externally supplied flow tables;
  deterministic RG status snippets are now wired into Phase-2 paper-assets and
  bundle verification;
  this is exploratory tooling and not a first-principles derivation of
  `sigma(t)` or `k(sigma)`.
- **Structure formation / DM scope:** implemented linear-theory transfer/growth
  diagnostics, `fσ8` reporting, RSD overlay, and opt-in joint objective
  ranking/certification; non-linear closure and particle-level DM microphysics
  interpretation remain open.
- **Operational reproducibility:** implemented deterministic snapshots and
  ignored-bloat cleanup workflows; ad-hoc full-worktree zip sharing is outside
  recommended process.
- **External-review handoff (M100):** deterministic reviewer-pack composition is
  available via `scripts/phase2_e2_make_reviewer_pack.py` to bundle a
  share snapshot, selected Phase-2 bundle, generated paper-assets, and verify
  outputs in one reproducible artifact.

## External feedback -> roadmap mapping (M99)

- Consolidated mapping document:
  `docs/external_reviewer_feedback.md`
- **In scope in the current framework Phase-2:**
  - compressed-priors CMB bridge diagnostics and deterministic E2 operations;
  - linear/approximate structure diagnostics (`T(k)`, growth, `fσ8`, RSD
    overlays and optional joint objective tooling);
  - sigma-origin status tooling with explicit ansatz boundaries.
- **Out of scope in the current framework Phase-2:**
  - full CMB anisotropy spectra (`TT/TE/EE`) Boltzmann-class fitting;
  - first-principles FRG derivation of `sigma(t)` / unique `k(sigma)` map;
  - full perturbation/non-linear structure closure and dark-matter
    microphysics resolution claims.

## External feedback alignment (M101)

- Canonical response map:
  `docs/external_reviewer_feedback.md`
- **Already addressed by Phase-2 tooling:**
  - compressed-priors CMB bridge workflow (`phase2_e2_scan.py` plus
    scan/merge/bundle/verify/report chain);
  - linear structure overlays (`fσ8`/RSD diagnostics and optional joint
    objective paths);
  - sigma-origin status diagnostics (flow-table + Padé-fit reporting as
    exploratory tooling).
- **Still open and explicitly deferred:**
  - full CMB anisotropy spectra (TT/TE/EE) with Boltzmann-class peak fitting;
  - perturbation closure beyond linear approximations;
  - dark-matter microphysics interpretation/resolution claims;
- first-principles FRG derivation for `sigma(t)` and `k(sigma)`.

## Structure formation & DM scope (M102)

- Canonical scope boundary is now summarized in
  `docs/perturbations_and_dm_scope.md`.
- Current Phase-2 deliverables include linear-theory structure diagnostics and
  RSD overlays/joint objective tooling; these are operational consistency
  channels, not full nonlinear closure.
- Phase-2 paper assets now include a deterministic structure snippet
  (`phase2_sf_fsigma8.{md,tex}`) in the gated bundle path for reviewer-facing
  reproducibility.
- Full TT/TE/EE spectra fitting remains future work; current CMB-facing usage is
  compressed-priors diagnostics only (not a full spectra fit). Full Boltzmann
  perturbation closure and dark-matter microphysics resolution claims also
  remain out of current scope.

## External feedback alignment (M103): perturbations export readiness

- New deterministic export bridge:
  `scripts/phase2_pt_boltzmann_export_pack.py`
  (export-only, compressed-priors diagnostic context; not a full spectra fit).
- The tool selects one best eligible Phase-2 candidate (`cmb`/`rsd`/`joint`)
  for handoff diagnostics and emits a small pack with:
  `EXPORT_SUMMARY.json`, `CANDIDATE_RECORD.json`, and CLASS/CAMB input templates.
- Scope boundary is unchanged: this is export-only readiness for external
  perturbations/Boltzmann workflows; canonical the current framework still uses compressed
  CMB priors diagnostics and does not implement a full TT/TE/EE spectra fit.

## External feedback alignment (M105): reviewer-pack Boltzmann export wiring

- Reviewer packs can include a pre-generated Boltzmann export handoff and an
  offline helper (`boltzmann_export.sh`) so external reviewers can regenerate
  CLASS/CAMB templates without ad-hoc commands.
- This improves operational reviewability only; it does not change model
  physics or add a full in-repo Boltzmann TT/TE/EE solver. Canonical Phase-2
  remains compressed-priors diagnostics only and does not claim a full spectra
  fit.

## External feedback alignment (M106): Boltzmann results packaging

- New deterministic results-pack tool ingests external CLASS/CAMB run outputs
  plus the export pack and writes checksummed reviewer artifacts, within the
  existing compressed-priors diagnostic scope (not a full spectra fit).
- Reviewer packs can optionally include this pre-generated results pack for
  offline inspection (`RESULTS_SUMMARY.json`, checksums, allowlisted outputs).
- Scope boundary is unchanged: this is packaging/traceability for external
  solver outputs, not an in-repo full TT/TE/EE likelihood fit.

## Implemented vs deferred (reviewer-safe matrix)

- **Early-time/CMB**
  - Implemented: compressed/distance-priors E2 bridge diagnostics and deterministic scan/bundle verification workflow.
  - Deferred: full TT/TE/EE anisotropy spectra with Boltzmann-class peak-level fitting.
- **Sigma-field origin**
  - Implemented: phenomenological ansatz path with explicit `k(sigma)` working-identification wording.
  - Implemented (M92 scaffold): deterministic flow-table ingestion/report (`phase2_rg_flow_table_report.py`) for external FRG CSV inputs.
  - Implemented (M93 bridge): deterministic Padé pole-fit report (`phase2_rg_pade_fit_report.py`) that estimates `G_IR` and `k_*` from supplied flow tables.
  - Deferred: first-principles FRG/asymptotic-safety derivation of `sigma(t)` and unique scale-identification map.
- **Structure formation**
  - Implemented: linear-theory diagnostics (`T(k)` approximations, growth `D,f`, `fσ8`, RSD overlay).
  - Deferred: full perturbation pipeline and non-linear survey-complete LSS likelihood integration.
- **Dark matter scope**
  - Implemented: standard CDM-like effective matter-density parameterization in baseline diagnostics.
  - Deferred: any claim that dark matter is eliminated or fundamentally solved.

## What GSC does not claim (explicit non-claims)

- GSC the current framework does **not** claim a full CMB anisotropy-spectra fit (no TT/TE/EE Boltzmann-class peak pipeline in canonical scope; compressed priors are diagnostic only).
- GSC does **not** claim a first-principles FRG derivation of `sigma(t)`; the `k(sigma)` map is treated as a working ansatz / identification choice.
- GSC does **not** claim dark-matter elimination; current linear structure diagnostics keep standard matter-content assumptions for baseline tests.
- GSC does **not** claim full non-linear structure-formation closure or a survey-complete EFT-of-LSS pipeline.

## Why this is still useful and falsifiable

The central discriminator is operational and inference-level: epsilon/measurement-model posteriors and cross-probe consistency checks are machine-verifiable and reproducible. Drift-sign remains a supporting no-go diagnostic for specific history classes, not the primary Phase-4 discriminator.

## Roadmap (Phase-3 and later)

- **Phase-3A scaffold (M122):** action-based SigmaTensor-v1 background solver is now
  implemented as deterministic stdlib tooling (`gsc/theory/sigmatensor_v1.py` +
  `phase3_st_sigmatensor_background_report.py`), explicitly scoped to
  background-only dynamics.
- **Phase-3A consistency checkpoint (M123):** deterministic SigmaTensor-v1
  stability/consistency reporting (`phase3_st_sigmatensor_consistency_report.py`)
  with opt-in gate checks (background-only scope).
- **Phase-3A/B bridge (M124):** endpoint-tolerant SigmaTensor interpolation fix
  for high-`z` report probes and a deterministic EFT diagnostic export pack
  (`phase3_pt_sigmatensor_eft_export_pack.py`) for background-level alpha
  scaffolding.
- **Phase-3B backend bridge (M125):** deterministic SigmaTensor -> CLASS export
  pack (`phase3_pt_sigmatensor_class_export_pack.py`) compatible with existing
  Phase-2 run-harness/results-pack tooling for reproducible external runs.
- **Phase-3B spectra sanity suite (M126):** deterministic
  `phase3_pt_spectra_sanity_report.py` for external CLASS/CAMB outputs,
  with header-based TT parsing and optional strict gates; this is a
  format/consistency check layer, not a fit.
- **Phase-3B growth/fσ8 diagnostics (M127):** deterministic
  `phase3_sf_sigmatensor_fsigma8_report.py` now provides background-driven GR
  growth (`D`, `f`) and `fσ8` reporting with optional RSD chi2/AP correction;
  this remains a diagnostic bridge and not a full perturbation closure.
- **Phase-3B low-z joint diagnostics (M128):** deterministic
  `phase3_joint_sigmatensor_lowz_report.py` now combines BAO + SN + RSD blocks
  with analytic nuisance profiling and optional LCDM baseline deltas
  (`delta_chi2`); this remains diagnostic chi2 reporting, not a full global fit.
- **Phase-3B CMB bridge extension (M129):** `phase3_joint_sigmatensor_lowz_report.py`
  adds an optional compressed CMB distance-priors block (Planck-2018 CHW2018,
  covariance mode) and corresponding baseline deltas; this is bridge-mode
  diagnostic chi2 only, not a full CMB likelihood.
- **Phase-3B scan scaffold (M130):** deterministic
  `phase3_scan_sigmatensor_lowz_joint.py` adds plan + slice + resume JSONL
  diagnostics over the LOWZ_JOINT objective, with merge-compatible
  `plan_point_id`/`plan_source_sha256` rows for triage (not MCMC, not a full
  global fit).
- **Phase-3B scan analysis and triage (M131):** deterministic
  `phase3_analyze_sigmatensor_lowz_scan.py` analyzes merged/sharded JSONL scan
  outputs, emits top-candidate summaries, and writes optional reproduce scripts
  for follow-up diagnostics.
- **Phase-3B candidate dossier packaging (M132):** deterministic
  `phase3_make_sigmatensor_candidate_dossier_pack.py` builds top-candidate
  dossier packs (joint + fsigma8 + EFT + CLASS-export diagnostics), with
  portable-content linting and optional deterministic zip output.
- **Phase-3B CLASS mapping validation (M135):** deterministic
  `phase3_pt_sigmatensor_class_mapping_report.py` evaluates the w0wa fluid
  approximation against the SigmaTensor diagnostic grid and is integrated into
  dossier generation by default as a claim-safe mapping-consistency report.
- **Phase-3B dossier quicklook aggregation (M136):** deterministic
  `phase3_dossier_quicklook_report.py` provides a compact per-candidate
  aggregate view (joint chi2 blocks, mapping residuals, and spectra sanity) and
  is wired into dossier generation as a default reviewer-facing summary layer.
- **Phase-3B scan jobgen orchestration pack (M137):** deterministic
  `phase3_lowz_jobgen.py` emits portable bash/slurm job packs for
  plan -> slice-run -> merge -> analyze -> dossier execution, using runtime
  repo/python environment overrides without embedding host-specific absolute
  paths.
- **Scope boundary (unchanged):** this does not add perturbations/Boltzmann
  closure and does not claim full TT/TE/EE spectra compatibility.
- Add full CMB anisotropy handling as future work (Boltzmann-class code path or a validated high-fidelity surrogate; out of scope in the current framework canonical release).
- Improve recombination fidelity (HyRec/CosmoRec-grade treatment or calibrated equivalent).
- Extend perturbation theory in freeze-frame variables with explicit invariants and consistency checks.
- Tighten `sigma(t)` microphysics / FRG linkage from conceptual motivation toward derivation-level support.
- Expand structure diagnostics beyond linear theory toward non-linear and survey-level likelihood integration.
- Keep FRG flow-table scaffold as an integration interface; upgrade from heuristic ingestion to derivation-level closure only with explicit formal checks.

## Pointers to existing docs

- `docs/early_time_e2_status.md`
- `docs/structure_formation_status.md`
- `docs/perturbations_and_dm_scope.md`
- `docs/rg_scale_identification.md`
- `docs/rg_asymptotic_safety_bridge.md`
- `docs/sigma_field_origin_status.md`
- `docs/measurement_model.md`
- `docs/reviewer_faq.md`

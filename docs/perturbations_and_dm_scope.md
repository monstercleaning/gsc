# Perturbations & Dark Matter scope boundary (Phase-2)

This note defines the reviewer-safe boundary for perturbations and dark-matter
claims in the current Phase-2 toolchain.

## What is implemented now

- Linear transfer approximations are available in the structure module:
  `BBKS` and optional `EH98 no-wiggle` (`gsc/structure/transfer_*.py`).
- A deterministic GR-baseline linear growth solver is available
  (`gsc/structure/growth_factor.py`) with `D(z)`, `f(z)`, and
  `g(z)=fD` diagnostics.
- Linear `P(k)` + `sigma8` bridge tooling is available in
  `gsc/structure/power_spectrum_linear.py`.
- Reproducible `fσ8` reporting and RSD chi2 diagnostics are available via
  `scripts/phase2_sf_fsigma8_report.py`.
- Operational RSD overlay and optional joint objective wiring exist in the
  Phase-2 E2 workflow (scan/report/certificate/reviewer-pack paths).

## What is NOT implemented / out of scope (current)

- Full Boltzmann perturbation hierarchy and full Planck TT/TE/EE peak-level
  spectra fitting are not implemented in canonical the current framework scope; current
  CMB-facing checks are compressed-priors diagnostics only.
- Survey-complete nonlinear structure-formation inference is not implemented
  (nonlinear clustering, baryonic-feedback systematics, halo-model closure).
- Full galaxy power-spectrum and weak-lensing likelihood pipelines are not
  implemented in this release path.
- Neutrino-mass-driven full perturbation closure is not part of current
  Phase-2 deliverables.

## Dark matter assumptions (claim-safe)

- Current Phase-2 structure diagnostics use a standard effective matter-content
  parameterization (`Omega_m`) with the baseline CDM+baryon interpretation.
- We do not claim dark matter is solved, replaced, or eliminated in the current framework.
- Current RSD/growth outputs are consistency diagnostics under explicit
  assumptions, not particle-physics-level dark-matter resolution claims.

## Next milestones (roadmap hooks)

- Full CMB anisotropy spectra support requires either a Boltzmann-class code
  path or an explicit dependency-policy decision for an external validated
  equivalent; current Phase-2 usage remains compressed-priors and diagnostic.
- Perturbations beyond linear growth and survey-level nonlinear fits are Phase-3
  candidates.
- Dark-matter microphysics interpretation remains an open roadmap question.
- First-principles `sigma(t)` / FRG derivation remains an open problem; current
  `k(sigma)` usage is ansatz-level / not derived and is tracked in
  `docs/sigma_field_origin_status.md`.

## Boltzmann export pack (M103)

- Deterministic export-only handoff tooling is available via
  `scripts/phase2_pt_boltzmann_export_pack.py`.
- Example command:
  `python3 scripts/phase2_pt_boltzmann_export_pack.py --input merged.jsonl.gz --rank-by joint --eligible-status ok_only --created-utc 2026-02-24T00:00:00Z --outdir /tmp/boltzmann_export --zip-out /tmp/boltzmann_export.zip`
- The pack exports one selected candidate record plus CLASS/CAMB template files.
- Scope boundary: this tool does not compute spectra; it is a deterministic
  export bridge for external perturbation/Boltzmann workflows.

## Reviewer-pack integration (M105)

- `phase2_e2_make_reviewer_pack.py` can now pre-generate this export bridge
  inside reviewer packs and include an offline helper script:
  `boltzmann_export.sh`.
- Example:
  `python3 scripts/phase2_e2_make_reviewer_pack.py --bundle /path/to/bundle.zip --outdir reviewer_pack_out --zip-out reviewer_pack.zip --include-boltzmann-export on --boltzmann-rank-by cmb`
- Reviewers can run `./boltzmann_export.sh` inside the pack root to regenerate
  `boltzmann_export/EXPORT_SUMMARY.json`, `CANDIDATE_RECORD.json`, and
  CLASS/CAMB templates.
- Scope boundary is unchanged: this is an export-only handoff path and does not
  compute full TT/TE/EE spectra. Canonical Phase-2 remains a compressed-priors
  diagnostic path rather than a full spectra fit.

## Boltzmann results pack (M106)

- New deterministic results packaging tool:
  `scripts/phase2_pt_boltzmann_results_pack.py`.
- Purpose: ingest externally generated CLASS/CAMB outputs plus an export pack,
  then emit checksummed reviewer artifacts (`RESULTS_SUMMARY.json`, `outputs/`,
  claim-safe `README.md`).
- Portability default (M115): summary metadata avoids machine-local absolute
  paths and emits `RUN_METADATA_REDACTED.json` when the external run metadata
  contains absolute path values.
- Portability hardening (M120): leaking `run.log` content is redacted by default
  into `outputs/run_REDACTED.log`; unredacted logs are opt-in via
  `--include-unredacted-logs`.
- Example:
  `python3 scripts/phase2_pt_boltzmann_results_pack.py --export-pack /tmp/boltzmann_export --run-dir /tmp/class_or_camb_outputs --code auto --outdir /tmp/boltzmann_results --created-utc 2026-02-24T00:00:00Z --zip-out /tmp/boltzmann_results.zip --require tt_spectrum`
- Reviewer-pack integration now supports optional pre-generation of this results
  pack via `phase2_e2_make_reviewer_pack.py --include-boltzmann-results on`.
- M107 adds one-command offline helpers:
  - reviewer packs now include `./boltzmann_results.sh`
  - cluster job packs from `phase2_e2_jobgen.py` now include `./boltzmann_results.sh`
  - example: `GSC_BOLTZMANN_RUN_DIR=/path/to/external_outputs ./boltzmann_results.sh`
- Scope boundary is unchanged: this is packaging/traceability for external
  solver outputs and is not an in-repo full spectra likelihood fit.

## Boltzmann run harness (M110)

- Deterministic external run harness:
  `scripts/phase2_pt_boltzmann_run_harness.py`.
- Purpose: run CLASS/CAMB externally (native binary or docker), while capturing
  deterministic run metadata in `RUN_METADATA.json`.
- Portability default (M115): run metadata redacts machine-local absolute paths
  unless `--include-absolute-paths` is explicitly requested.
- Portability hardening (M120): `run.log` is portable by default (redacted
  command argv and run-dir path replacement); absolute-path log content is
  opt-in via `--include-absolute-paths`.
- Provenance hardening (M121): `RUN_METADATA.json` captures external solver
  identity (`external_code`) for docker/native runs in deterministic form.
- Docker reproducibility gate (M121): `--require-pinned-image` optionally
  enforces pinned docker refs (digest or non-`latest` explicit tag).
- Native mode uses explicit user-provided binaries (`GSC_CLASS_BIN`,
  `GSC_CAMB_BIN` or `--bin`); docker mode is optional and only used when
  available in the environment.
- Example:
  `python3 scripts/phase2_pt_boltzmann_run_harness.py --export-pack /tmp/boltzmann_export --code class --runner native --run-dir /tmp/boltzmann_run_class --created-utc 2026-02-24T00:00:00Z --overwrite`
- Jobgen and reviewer packs now include one-command helpers:
  `./boltzmann_run_class.sh` and `./boltzmann_run_camb.sh`.
- Scope boundary is unchanged: this is execution/traceability plumbing for
  external solvers and does not compute spectra internally.

## Optional rs/z* reference audit and BBN hook (M112)

- `scripts/phase2_cmb_rs_zstar_reference_audit.py` provides a
  deterministic audit comparing approximate in-repo `r_s(z_*)` / `z_*` values
  against externally produced CLASS/CAMB outputs when available.
- This remains a compressed-priors diagnostic context only and is not a full
  CMB spectra fit.
- `phase2_e2_make_paper_assets.py` can emit this audit artifact optionally via
  `--emit-rs-zstar-reference-audit` (with optional `--reference-audit-run-dir`).
- `phase2_e2_scan.py` also provides an optional BBN-inspired prior term
  (`--bbn-prior weak|standard`, default `none`) and deterministic multi-start
  optimization knobs for robustness (`--opt-multistart`, `--opt-init`,
  `--opt-seed`).
- Scope boundary is unchanged: these are audit/robustness diagnostics only and
  do not claim an in-repo full CMB spectra likelihood fit.

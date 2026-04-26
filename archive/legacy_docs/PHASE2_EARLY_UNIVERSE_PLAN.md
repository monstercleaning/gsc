# Phase 2 Early Universe Plan (Baseline: v10.1.1-dx1)

## Scope
This document defines Phase 2 kickoff scope for early-universe observables that were intentionally deferred in the v10.1 line.

Baseline:
- Tag: `v10.1.1-dx1`
- Branch: `codex/phase2/early-universe`
- DX constraints: keep optional-deps gating, outdir contract, artifact policy, and CI split intact.

## Current Inventory (What Already Exists)

### Core early-time module surface
- `gsc/early_time/rd.py`
  - EH98-style drag scale helper:
    - `compute_rd_Mpc(...)`
    - `z_drag_eisenstein_hu(...)`
    - `omega_gamma_h2_from_Tcmb(...)`
    - `omega_r_h2(...)`
  - Deterministic, stdlib-first formulas; no heavy runtime side effects.
- `gsc/early_time/cmb_distance_priors.py`
  - Compressed-CMB bridge-level predictors:
    - `compute_lcdm_distance_priors(...)`
    - `compute_bridged_distance_priors(...)`
    - `compute_full_history_distance_priors(...)`
    - `z_star_hu_sugiyama(...)`
  - Provides `theta_star`, `lA`, `R`, `z_star`, and related diagnostic fields.
  - Uses `_require_numpy()` and is explicitly described as bridge-level, not full Boltzmann/recombination physics.
- `gsc/early_time/__init__.py`
  - Public exports for rd and compressed-CMB bridge helpers.

### Related numerical and diagnostic infrastructure
- `gsc/diagnostics/recombination.py`
  - Peebles-style recombination/visibility diagnostic for `z_star` sanity checks.
- `gsc/histories/full_range.py`
  - Full-range histories with explicit radiation and BBN guardrails for high-z stability.
- `gsc/datasets/cmb_priors.py`
  - Dataset loaders and covariance path for compressed CMB priors.

### Existing scripts and tests relevant to early time
- Scripts (examples):
  - `scripts/cmb_chw2018_benchmark.py`
  - `scripts/cmb_rs_star_calibration_fit_e2.py`
  - `scripts/cmb_rs_star_numerics_audit.py`
  - `scripts/cmb_e2_zstar_recombination_audit.py`
- Tests already covering early-time/bridge behavior:
  - `tests/test_early_time_bridge.py`
  - `tests/test_cmb_distance_priors.py`
  - `tests/test_cmb_bridge_regression.py`
  - `tests/test_zstar_recombination_audit.py`
  - `tests/test_rs_star_numerics_audit.py`

## Gap Analysis (What Phase 2 Must Add)

### Missing for M1 (shift-parameter pipeline)
- Dedicated, explicit Phase 2 interface for shift-parameter outputs and artifact generation under outdir policy.
- A single canonical script that writes machine-readable outputs for early-time shift parameters (JSON first).
- Tight acceptance checks around baseline LCDM values and numerical tolerances.

### Missing for M2 (freeze-frame consistency checks)
- Explicit invariant-focused tests around dimensionless observables (`theta_star`, ratios) under frame map assumptions.
- Monotonic/sensitivity checks separated from fitting workflows.

### Missing for M3 (primordial transfer function bridge)
- Initial transfer-function approximation module (approx-first, not Boltzmann engine).
- Interface designed for future replacement without changing calling contract.

### Missing for M4 (CI early-time smoke)
- Full-stack early-time smoke command wired into CI that emits outputs only under outdir.

## Constraints and Guardrails (Must Stay True)

### DX and reproducibility constraints
- Optional deps:
  - No import-time crashes for missing optional deps.
  - Continue module-level `SkipTest` in numpy-tier suites when deps are unavailable.
- Output paths:
  - Keep contract: `--out-dir/--outdir` > `GSC_OUTDIR` > `artifacts/release`.
  - Generated artifacts must stay out of tracked source paths unless explicitly canonical metadata.
- Artifact governance:
  - `scripts/audit_repo_footprint.py` remains a required guard.
  - No large tracked artifacts outside allowlisted policy exceptions.
- CI tiers:
  - `stdlib_only` remains dependency-light and stable.
  - Early-time smoke belongs in `full_stack` only.

### Scientific-scope guardrails
- Phase 2 implementation PRs remain engineering-first and test-first.
- Do not promote deferred/speculative claims into canonical science text without dedicated validation work.
- Pinned deferred-ideas reference:
  - `GSC_v10_1_release/docs/DEFERRED_IDEAS_v10.md`

## Milestone Breakdown

### M1 (PR #2): CMB shift-parameters pipeline
Deliverables:
- New module for explicit shift-parameter computation path.
- New script to emit `cmb_shift_params.json` under outdir.
- New numpy-tier tests with baseline LCDM tolerance checks.

Definition of Done:
- Full-stack tests: `errors=0`, `failures=0`.
- Script writes only to outdir.
- No new tracked heavy artifacts.

### M2 (PR #3): Freeze-frame consistency checks
Deliverables:
- Invariant and monotonicity sanity tests for dimensionless quantities.

Definition of Done:
- Fast deterministic tests.
- No fragile unexplained golden values.

### M3 (PR #4): Primordial transfer function approximation
Deliverables:
- Approximation-first transfer-function module with documented limitations.
- Interface stable for later replacement/upgrades.

Definition of Done:
- Outputs under outdir.
- No dataset bloat in git.

### M4 (post-M1 stabilization): CI early-time smoke
Deliverables:
- Full-stack smoke path that runs early-time JSON generation and verifies artifact location.

Definition of Done:
- CI runtime remains acceptable.
- No writes outside outdir in smoke run.

## Immediate Next Action
Open PR #1 (docs-only): add this plan document and link it from Issue #80 as the Phase 2 kickoff reference.

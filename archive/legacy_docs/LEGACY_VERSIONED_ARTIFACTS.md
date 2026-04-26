# Legacy Versioned Artifacts Policy (v11 series)

This repository retains some `v10*` / `v10.1*` / `v10_1*`-named artifacts for
provenance and reproducibility of historical releases.

These artifacts are **not** the canonical active program for reviewer
evaluation in the v11 series.

Canonical reviewer entrypoint:
- `docs/REVIEW_START_HERE.md`

## Policy

- Legacy `v10*` names are allowed only inside explicit approved prefixes.
- Any new `v10*` filename outside the allowlist is a regression.
- Guardrail test:
  `tests/test_phase4_m152_legacy_versioned_filenames_bounded.py`

## Approved allowlist prefixes

Baseline legacy zones:

- `GSC/GSC_v10_1_release/`
- `GSC/GSC_v10_1_simulations/`
- `GSC/scripts/reproduce_v10_1_`
- `GSC/GSC_Framework_v10_1_FINAL.`
- `GSC/GSC_Framework_v10`

Additional retained provenance zones currently present in-repo:

- `GSC/archive/legacy/`
- `GSC/B/GSC_Phase10_MochiClass_Integration_v10_8.pdf`

If a path contains `v10` and does not match one of these prefixes, treat it as
a filename-hygiene regression and either rename it or explicitly extend this
policy with justification.

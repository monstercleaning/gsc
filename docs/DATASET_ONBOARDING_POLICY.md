# Dataset Onboarding Policy (Phase-4 M139)

This policy defines how datasets are added or refreshed in `data/**`
without breaking reproducibility, portability, or legal hygiene.

## 1) Mandatory metadata for every new/updated dataset

- File path under `data/**`
- Dataset name and short purpose statement
- Source pointer (paper/release/README entry)
- License/usage note (or explicit "upstream terms required")
- Deterministic checksum (SHA256)
- Loader/consumer script(s) and tests that use it

## 2) Legal and usage gate

A dataset update is blocked unless one of the following is true:

- Redistribution terms are clearly compatible and recorded, or
- The repository stores only derived small diagnostic tables with explicit
  provenance and a note that upstream terms govern broader redistribution.

## 3) Size and footprint gate

- Changes must keep
  `python3 scripts/audit_repo_footprint.py --max-mb 10` passing.
- Prefer small reviewer-focused tables committed in git.
- Large external assets must use fetch scripts + pinned checksums, not direct
  commits.

## 4) Determinism and portability gate

- No machine-local absolute paths in committed data metadata/docs.
- Dataset-dependent artifacts must be reproducible with fixed inputs.
- Snapshot preflight and portable-content lint should pass on reviewer bundles.

## 5) Update process (checklist)

1. Add/update dataset file(s) under `data/**`.
2. Update source/license documentation (`DATA_SOURCES.md` and
   `DATA_LICENSES_AND_SOURCES.md`).
3. Add or update tests that exercise loaders/consumers.
4. Run quality gates (`audit_repo_footprint`, `docs_claims_lint`, full
   unittest discovery).
5. Validate snapshot/reviewer-pack behavior before release tag.

## 6) Reviewer-pack expectations

If a dataset is required for unit tests or review workflows, it must be present
in the `review_with_data` snapshot profile and pass preflight checks.

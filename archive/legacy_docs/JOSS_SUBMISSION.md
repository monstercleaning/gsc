# JOSS Submission Workflow (Paper 4 / Methodology)

This runbook covers repository-side readiness checks. Human submission to the Open
Journals system is still manual.

## Pre-submission checklist

1. License and policy files exist (`LICENSE`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`).
2. `paper.md` and `paper.bib` are present with non-placeholder metadata.
3. `CITATION.cff` is present and current.
4. Quality gates pass:
   - `python3 scripts/audit_repo_footprint.py --max-mb 10`
   - `python3 scripts/docs_claims_lint.py --repo-root v11.0.0`
   - `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -v`

## Run JOSS preflight

```bash
python3 scripts/phase4_joss_preflight.py --repo-root . --format text
```

The script exits nonzero if required JOSS metadata is missing or still placeholder.

## Archive DOI path (recommended)

1. Create GitHub release tag for the shipped milestone.
2. Ensure Zenodo GitHub integration is enabled.
3. Let Zenodo mint DOI for that release archive.
4. Use minted DOI + version in JOSS submission form.

## Human submission steps

1. Open a new JOSS submission issue with paper title, repository URL, archive DOI, and version.
2. Paste the preflight output and quality-gate summary.
3. Respond to reviewer/editor requests with linked deterministic artifacts and acceptance archives.

Operator checklist shortcut:
- `docs/JOSS_SUBMISSION_CHECKLIST.md`

## Scope reminder

Paper 4 is a methodology/software paper. It documents deterministic falsification tooling,
schema contracts, and reviewer workflows. It does not claim novel fundamental physics.

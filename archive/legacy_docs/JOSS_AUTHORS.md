# JOSS Authors / UI Notes

Use this page when filling the JOSS submission form.

## Project summary (short)
GSC is a deterministic, schema-first framework for reviewer-grade cosmology inference diagnostics and falsification workflows.

## Installation / run
- Repository: `https://github.com/morfikus/GSC`
- Canonical entrypoint: `docs/REVIEW_START_HERE.md`
- Core reproducibility checks:
  - `python3 scripts/phase2_repo_inventory.py --repo-root the current framework --require-present --format text`
  - `python3 scripts/docs_claims_lint.py --repo-root v11.0.0`

## Statement of need (short)
Cosmology diagnostic pipelines are often difficult to audit. GSC enforces deterministic outputs, explicit schema contracts, and acceptance-archive preflight checks so reviewers can independently reproduce and falsify claims.

## Impact statement (short)
The repository reduces review friction by standardizing claim-to-artifact traceability, git-less snapshot validation, and deterministic report production for both methodology and physics-facing diagnostics.

## License
MIT (`LICENSE` in project root).

## References
Primary software-paper sources are in root-level `paper.md` and `paper.bib`.

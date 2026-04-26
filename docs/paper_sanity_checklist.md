# Paper Sanity Checklist (Release Discipline, Docs-Only)

Use this checklist before any paper-facing release discipline updates.

Automated helper:
- `python3 scripts/paper_readiness_lint.py` (pattern-based lint for the core reviewer-facing markers).
- `python3 scripts/pointer_sot_lint.py` (canonical tag/asset/SHA pointer lint vs `canonical_artifacts.json`).
- `bash scripts/release_candidate_check.sh --artifacts-dir .` (full offline RC stack: canonical SHA checks + submission/referee/toe verifiers + readiness lint).
- `bash scripts/operator_one_button.sh --artifacts-dir . --fetch-missing --report /tmp/operator_report.json` (cold-start end-to-end operator flow).
- `bash scripts/fetch_canonical_artifacts.sh --artifacts-dir . --fetch-missing` (opt-in cold-start fetch + SHA verify).
- `bash scripts/arxiv_preflight_check.sh submission_bundle_v10.1.1-late-time-r4.zip` (arXiv/journal hygiene checks).
- Operator runbook: `docs/submission_runbook.md` (what to upload / what not to upload).

- [ ] Scope/claims/kill-tests box is present on page 1 (after title/abstract area) in the canonical TeX.
- [ ] Drift-sign condition is written explicitly as `dot z > 0 <=> H(z) < H0(1+z)` (not slogan-only wording).
- [ ] Drift section makes clear that sign is a historical/supporting no-go diagnostic (not the primary discriminator); amplitudes are illustrative.
- [ ] Submission text keeps early-time/CMB closure out of core scope; diagnostics are pointed to companion docs.
- [ ] “Not tired light” statement is present and concise (time dilation + Tolman tests retained).
- [ ] Universality/non-universality wording remains risk-parameterized (no claim creep).
- [ ] `docs/popular/**` remains excluded from submission/referee bundle builders.
- [ ] Canonical frozen artifacts remain untouched: `late-time-r4`, `submission-r2`, `referee-pack-r4`.
- [ ] Submission bundle verify with smoke compile remains green.
- [ ] Referee pack verify remains green and includes intended diagnostic docs.
- [ ] One-command RC check reports `RC OK`:
  - `bash scripts/release_candidate_check.sh --artifacts-dir .`

This checklist is procedural only; it does not alter physics, fit settings, or canonical outputs.

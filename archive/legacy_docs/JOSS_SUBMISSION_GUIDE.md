# JOSS Submission Guide

This checklist is for the human operator submitting through the JOSS UI.

## 1) Pre-submit repository checks
```bash
python3 scripts/phase4_joss_preflight.py --repo-root . --format text
```
Ensure it passes.

## 2) Create release + archive DOI
1. Create GitHub release tag (must point to merge commit).
2. Sync release with Zenodo/figshare to mint archive DOI.
3. Keep DOI metadata aligned with:
   - `CITATION.cff`
   - `.zenodo.json`

## 3) Prepare JOSS submission inputs
- Repository URL
- Archive DOI
- `paper.md`
- `paper.bib`
- License (`MIT`)

## 4) Submit in JOSS UI
- Submit at [joss.theoj.org](https://joss.theoj.org/)
- Expect review in a GitHub issue
- Track changes via tagged releases and deterministic acceptance archives

## 5) Release discipline
- Build reviewer archive from shipped tag worktree only.
- Keep claims bounded to implemented and schema-validated artifacts.

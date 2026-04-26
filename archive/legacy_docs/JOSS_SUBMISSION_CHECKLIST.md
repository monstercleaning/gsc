# JOSS Submission Checklist (Paper 4 / CosmoFalsify)

1. Run deterministic JOSS preflight:

```bash
python3 scripts/phase4_joss_preflight.py --repo-root . --format text
```

2. Ensure `paper.md` and `paper.bib` are final and consistent with `CITATION.cff`.
3. Create release tag pointing to merged commit.
4. Archive the release on Zenodo/figshare and obtain DOI.
5. Mint Zenodo DOI for tag `v11.0.0-phase4-m159`, then update `CITATION.cff` and `.zenodo.json` with the final DOI (human step, post-mint).
6. Submit to JOSS at [joss.theoj.org](https://joss.theoj.org/) with repository URL and archive DOI.
7. Track review in the GitHub-issue workflow and keep responses reproducible.

## Discipline notes

- Use tag-based release artifacts only (no workspace-local state).
- Build reviewer archive from shipped tag worktree.
- Keep claims bounded to deterministic tooling and validated artifacts.

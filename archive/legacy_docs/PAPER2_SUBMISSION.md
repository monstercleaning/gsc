# Paper 2 Submission (arXiv) — Deterministic Workflow

This runbook builds Paper 2 assets and the arXiv bundle with deterministic tooling.

## 1) Prepare pinned manifests

Pantheon+ and DESI BAO manifests are required for paper-grade runs.

## 2) Build paper assets

```bash
python3 scripts/phase4_build_paper2_assets.py \
  --preset paper_grade \
  --seed 0 \
  --workdir out/paper2_pg_work \
  --outdir out/paper2_pg_assets \
  --pantheon-manifest <pantheon_manifest.json> \
  --desi-bao-manifest <desi_manifest.json> \
  --format text
```

## 3) Build PDF

```bash
export PAPER2_ASSETS_DIR=out/paper2_pg_assets
bash scripts/build_paper2.sh
```

## 4) Build arXiv bundle

```bash
python3 scripts/phase4_make_arxiv_bundle_paper2.py \
  --paper-dir papers/paper2_measurement_model_epsilon \
  --assets-dir out/paper2_pg_assets \
  --out-tar paper_assets/paper2_arxiv_bundle.tar.gz \
  --format text
```

## Operator notes

- Canonical checklists:
  - `docs/ARXIV_SUBMISSION_CHECKLIST.md`
  - `docs/PAPER2_BUILD_AND_REPRODUCIBILITY.md`
- arXiv endorsement policy update:
  [blog.arxiv.org/2026/01/21/attention-authors-updated-endorsement-policy](https://blog.arxiv.org/2026/01/21/attention-authors-updated-endorsement-policy/)

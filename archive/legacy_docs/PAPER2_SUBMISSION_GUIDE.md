# Paper 2 Submission Guide (arXiv UI)

This is the operator guide for a no-manual-preprocessing upload path.

## 1) Build deterministic assets
```bash
python3 scripts/phase4_build_paper2_assets.py --preset paper_grade --seed 0 --workdir out/paper2_pg_work --outdir out/paper2_pg_assets --pantheon-manifest <pantheon_manifest.json> --desi-bao-manifest <desi_manifest.json> --format text
```

## 2) Build arXiv tarball
```bash
python3 scripts/phase4_make_arxiv_bundle_paper2.py --paper-dir papers/paper2_measurement_model_epsilon --assets-dir out/paper2_pg_assets --out-tar paper_assets/paper2_arxiv_bundle.tar.gz --format text
```

## 3) Verify tarball quickly
```bash
tar tzvf paper_assets/paper2_arxiv_bundle.tar.gz
```
Expected key members:
- `main.tex`
- `main.bbl`
- `numbers.tex`
- `figures/*`
- `00README`

## 4) Upload to arXiv UI
- Use metadata from `docs/ARXIV_METADATA.md`.
- Run final checklist from `docs/ARXIV_UPLOAD_CHECKLIST.md`.

## 5) Category guidance
Suggested primary category: `astro-ph.CO`; optional secondary: `gr-qc`.

## 6) Notes
- This workflow is deterministic and git-less snapshot compatible.
- Keep DR1/DR2 wording referee-safe per `docs/DATA_LICENSES_AND_SOURCES.md`.

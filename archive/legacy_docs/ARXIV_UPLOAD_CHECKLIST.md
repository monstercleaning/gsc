# arXiv Upload Checklist (Paper 2)

1. Build deterministic assets and bundle:
```bash
python3 scripts/phase4_build_paper2_assets.py --preset paper_grade --seed 0 --workdir out/paper2_pg_work --outdir out/paper2_pg_assets --pantheon-manifest <pantheon_manifest.json> --desi-bao-manifest <desi_manifest.json> --format text
python3 scripts/phase4_make_arxiv_bundle_paper2.py --paper-dir papers/paper2_measurement_model_epsilon --assets-dir out/paper2_pg_assets --out-tar paper_assets/paper2_arxiv_bundle.tar.gz --format text
```
2. Confirm archive contents:
```bash
tar tzvf paper_assets/paper2_arxiv_bundle.tar.gz
```
3. Confirm bibliography is present (`main.bbl`) and figures are PDF/PNG/JPG/JPEG compatible with pdfLaTeX on arXiv.
4. Paste metadata from `docs/ARXIV_METADATA.md` in the UI.
5. Verify subject class and license before final submit.
6. If endorsement is required for the selected category, check:
   [arXiv endorsement help](https://info.arxiv.org/help/endorsement/)

Reference policies:
- [Updated endorsement policy (2026-01-21)](https://blog.arxiv.org/2026/01/21/attention-authors-updated-endorsement-policy/)
- [TeX Live constraints on arXiv](https://info.arxiv.org/help/faq/texlive.html)

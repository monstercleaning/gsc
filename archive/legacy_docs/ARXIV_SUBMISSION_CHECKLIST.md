# ArXiv Submission Checklist (Paper 2)

1. Build deterministic paper assets first (paper-grade mode):

```bash
python3 scripts/phase4_build_paper2_assets.py \
  --preset paper_grade \
  --seed 0 \
  --workdir out/paper2_build_work \
  --outdir out/paper2_assets \
  --pantheon-manifest <pantheon_manifest.json> \
  --desi-bao-manifest <desi_bao_manifest.json> \
  --format text
```

2. Build arXiv bundle (no submission, bundle only):

```bash
python3 scripts/phase4_make_arxiv_bundle_paper2.py \
  --paper-dir papers/paper2_measurement_model_epsilon \
  --assets-dir out/paper2_assets \
  --out-tar paper_assets/paper2_arxiv_bundle.tar.gz \
  --format text
```

3. Compile locally with your TeX toolchain and check bibliography/figures render.
4. Upload tarball manually to arXiv submission UI.
5. Confirm endorsement prerequisites for the selected category before upload:
   [arXiv endorsement help](https://info.arxiv.org/help/endorsement/)

## Policy notes

- Updated endorsement policy: [Attention Authors: Updated Endorsement Policy](https://blog.arxiv.org/2026/01/21/attention-authors-updated-endorsement-policy/)
- TeX Live constraints on arXiv: [arXiv TeX Live FAQ](https://info.arxiv.org/help/faq/texlive.html)
- Keep wording reviewer-safe: DR1 baseline; DR2 references only as cosmology summary products where applicable.

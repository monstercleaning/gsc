# Paper 2 Build And Reproducibility

## CI smoke (offline)

```bash
python3 scripts/phase4_build_paper2_assets.py \
  --preset ci_smoke \
  --seed 0 \
  --workdir out/paper2_ci_work \
  --outdir out/paper2_ci_assets \
  --format text

python3 scripts/phase2_schema_validate.py --auto \
  --schema-dir schemas \
  --json out/paper2_ci_assets/paper2_assets_manifest.json
```

## Paper-grade assets (requires pinned manifests)

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

## Build manuscript PDF

```bash
bash scripts/build_paper2.sh
```

## Optional theory annex (QCD<->Gravity sanity-check bundle)

```bash
python3 scripts/phase4_build_paper2_assets.py \
  --preset ci_smoke \
  --seed 0 \
  --workdir out/paper2_ci_work \
  --outdir out/paper2_ci_assets \
  --include-theory-annex \
  --format text
```

Expected supplementary outputs:
- `out/paper2_ci_assets/theory/qcd_gravity_bridge/qcd_gravity_bridge_numbers.json`
- `out/paper2_ci_assets/theory/qcd_gravity_bridge/qcd_gravity_bridge_kill_matrix.csv`
- `out/paper2_ci_assets/theory/qcd_gravity_bridge/qcd_gravity_bridge_scale_plot.png`

## Build arXiv tarball

```bash
python3 scripts/phase4_make_arxiv_bundle_paper2.py \
  --paper-dir papers/paper2_measurement_model_epsilon \
  --assets-dir out/paper2_pg_assets \
  --out-tar paper_assets/paper2_arxiv_bundle.tar.gz \
  --format text
```

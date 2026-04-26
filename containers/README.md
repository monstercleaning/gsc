# External Boltzmann Container Recipes (M110)

These Dockerfiles provide reproducible build recipes for external CLASS/CAMB
runs used by the Phase-2 harness path.

Scope boundary:

- These recipes are optional and external.
- They do not change in-repo physics semantics.
- They support execution/traceability workflows only.

## Build images

```bash
docker build -f v11.0.0/containers/CLASS.Dockerfile -t gsc-class:latest v11.0.0
docker build -f v11.0.0/containers/CAMB.Dockerfile -t gsc-camb:latest v11.0.0
```

Override refs at build time:

```bash
docker build -f v11.0.0/containers/CLASS.Dockerfile \
  --build-arg CLASS_REF=v3.2.0 \
  -t gsc-class:v3.2.0 v11.0.0
docker build -f v11.0.0/containers/CAMB.Dockerfile \
  --build-arg CAMB_REF=CAMB_1.5.8 \
  -t gsc-camb:1.5.8 v11.0.0
```

## Expected run-dir mapping

Harness scripts mount a run directory as `/work`:

- input templates under `/work/inputs/`
- solver outputs written under `/work/`
- metadata/logs: `RUN_METADATA.json`, `run.log`

This layout is consumed by:

- `v11.0.0/scripts/phase2_pt_boltzmann_run_harness.py`
- `v11.0.0/scripts/phase2_pt_boltzmann_results_pack.py`

## Reproducibility note (M121)

- Prefer pinned image references (digest or non-`latest` explicit tags).
- Harness strict gate is available via:
  `python3 v11.0.0/scripts/phase2_pt_boltzmann_run_harness.py ... --runner docker --require-pinned-image`.
- `RUN_METADATA.json` now captures solver identity/provenance fields for docker
  or native runs; portability defaults keep machine-local absolute paths
  redacted unless explicitly requested.

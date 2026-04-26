# SBOM (minimal)

This software bill of materials is intentionally minimal and deterministic.
It is focused on reproducibility plumbing and does not introduce runtime
requirements beyond the current repository policy.

## Runtime model

- Python runtime: CPython 3.x (project scripts are stdlib-first where possible).
- Core package root: `gsc/`.
- Primary script entrypoints: `scripts/`.

## Declared Python dependencies

From `requirements.txt`:

- `numpy>=1.22`
- `scipy>=1.9`
- `matplotlib>=3.7`

Notes:

- Many governance/packaging tools remain stdlib-only.
- Some scientific and plotting workflows are optional-dependency paths.

## Reproducible environment capture (optional)

To generate a local dependency snapshot for audits:

```bash
python3 -m pip freeze | LC_ALL=C sort > /tmp/gsc_pip_freeze_sorted.txt
```

To record interpreter information:

```bash
python3 - <<'PY'
import platform, sys
print(platform.platform())
print(sys.version)
PY
```

## Related provenance documents

- `docs/provenance_and_schemas.md`
- `docs/DATA_SOURCES.md`
- `docs/sharing_and_snapshots.md`

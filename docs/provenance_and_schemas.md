# Provenance and schemas (Phase-2)

This note documents two operational artifacts for Phase-2 reproducibility:

- `LINEAGE.json`: deterministic provenance DAG for bundle files.
- JSON schemas under `schemas/` for machine-readable artifact contracts.

These artifacts improve traceability and validation. They do not add new physics
claims or replace external perturbation/spectra workflows.

## LINEAGE.json

`LINEAGE.json` is generated from a Phase-2 bundle directory and records:

- nodes (file path, type, sha256, size)
- edges (stable DAG links between plan/scan config/shards/merge/manifest/reviewer-plan)
- portable bundle locator metadata (`bundle_dir` defaults to `"."`)

Generate manually:

`python3 scripts/phase2_lineage_dag.py --bundle-dir /path/to/bundle_dir --out /path/to/bundle_dir/LINEAGE.json --format json`

Portable default behavior:

- `bundle_dir` is emitted as `"."` for share-safe reproducibility.
- Absolute bundle paths are opt-in only via `--include-absolute-paths`
  (adds `bundle_dir_abs`).

Bundle flow integration:

- `phase2_e2_bundle.py` writes `LINEAGE.json` during bundle creation.
- `phase2_e2_verify_bundle.py` verifies lineage presence and hash consistency.
- `phase2_e2_make_reviewer_pack.py` includes `bundle/LINEAGE.json` in reviewer packs.

## Schemas

Phase-2 schemas are located in `schemas/`:

- `phase2_scan_row_v1.schema.json`
- `phase2_candidate_record_v1.schema.json`
- `phase2_bundle_manifest_v1.schema.json`
- `phase2_reviewer_pack_plan_v1.schema.json`
- `phase2_lineage_dag_v1.schema.json`
- `phase2_consistency_report_v1.schema.json`
- `phase2_pt_boltzmann_run_metadata_v1.schema.json`
- `phase2_pt_boltzmann_results_pack_v1.schema.json`
- `phase2_cmb_rs_zstar_reference_audit_v1.schema.json`
- `gsc_repo_snapshot_manifest_v1.schema.json`

Schemas are conservative and additive-friendly by default (`additionalProperties` allowed).

## Validation tool

Use:

`python3 scripts/phase2_schema_validate.py --schema <schema.json> --json <payload.json> --format text`

Or auto-select by payload schema id:

`python3 scripts/phase2_schema_validate.py --auto --schema-dir schemas --json <payload.json> --format text`

Options:

- `--strict`: fail on unknown keys.
- `--format json`: machine-readable output.

Validation engine behavior:

- If `jsonschema` is available, it is used.
- Otherwise, the tool runs stdlib minimal checks (required keys + basic type checks).

Exit codes:

- `0`: validation passed.
- `2`: validation failed.

## Verify-bundle wiring

`phase2_e2_verify_bundle.py` supports optional validation gates:

- `--validate-schemas`: validates bundle manifest, `LINEAGE.json`, and consistency report payloads (when present) via `phase2_schema_validate.py --auto`.
- `--lint-portable-content`: runs JSON/JSONL content lint for machine-local absolute path tokens.

Both are opt-in to preserve backward compatibility with older artifacts.

Reviewer-pack integration:

- `phase2_e2_make_reviewer_pack.py` runs verify on the included bundle with strict gates by default
  (`--validate-schemas` + `--lint-portable-content`) so portability/schema issues are caught before packaging.
- Reviewer-pack subtools run against the staged copy `bundle/bundle.zip`, so verification/paper-assets are hermetic
  with respect to the artifact actually included in the pack.
- Use `--verify-strict 0` for legacy compatibility runs, or `--skip-portable-content-lint` to bypass content lint only.

# Artifact Policy

This policy defines what belongs in git and what must be treated as release/local artifacts.

## Tiers

`Tier 0 — Source-of-Truth (tracked)`
- Code, tests, text docs, manifests, small canonical inputs.
- These must be diff-friendly and reviewable.

`Tier 1 — Canonical metadata (tracked)`
- Checksums, artifact pointers, and verification metadata.
- Single source of truth: `canonical_artifacts.json`.

`Tier 2 — Release artifacts (not tracked)`
- Bundles and packaged binaries (`*.zip`, generated PDFs, upload bundles).
- Generated operator/analysis reports (for example: `early_time/cmb_priors_report.json`, `early_time/cmb_priors_table.csv`).
- Publish via release assets; verify via checksum tooling.

`Tier 3 — Local/generated/cache (not tracked)`
- Runtime outputs and caches (`results`, generated figures/tables, temporary data).

## Framework Document SoT

Authoritative source text is:
- `GSC_Framework_v10_1_FINAL.md`

Derived formats (`.tex`, `.pdf`) are release-facing outputs and should not be used as the editorial source of truth.

## Output Layout

Generated artifacts should be written under:
- `artifacts/canonical/` (tracked metadata only)
- `artifacts/release/` (ignored)
- `artifacts/local/` (ignored)
- `artifacts/cache/` (ignored)

Output root resolution contract for scripts:
- CLI `--outdir` (or `--out-dir`) takes highest precedence.
- Else `GSC_OUTDIR` is used when set.
- Else default is `artifacts/release/`.

Early-time reporting outputs are expected under:
- `artifacts/release/early_time/cmb_priors_report.json`
- `artifacts/release/early_time/cmb_priors_table.csv`

## Guardrails

- CI runs `scripts/audit_repo_footprint.py` to detect oversized tracked files.
- Legacy large files are grandfathered via:
  - `docs/repo_footprint_allowlist.txt`
- New large tracked files should be exceptional and explicitly reviewed.

# Sharing and snapshots

Manual zips of a full checkout are error-prone and often huge. They can include
`.git/`, `.venv/`, platform junk (`__MACOSX/`, `.DS_Store`), and local generated
artifacts. That makes archives nondeterministic and hard to review.

## Approved share methods

- Deterministic code snapshot:
  `python3 scripts/make_repo_snapshot.py --profile share --zip-out GSC_share.zip`
- Deterministic review snapshot with tracked data inputs (for git-less test/review runs):
  `python3 scripts/make_repo_snapshot.py --profile review_with_data --zip-out GSC_review_with_data.zip`
- Reviewer-oriented pack (bundle + docs + manifests + verify outputs):
  `python3 scripts/phase2_e2_make_reviewer_pack.py --bundle /path/to/bundle.zip --outdir reviewer_pack_out --zip-out reviewer_pack.zip`
  By default, reviewer-pack verify uses strict checks on the included bundle:
  `--validate-schemas` + `--lint-portable-content` (disable only when needed with `--verify-strict 0`
  or `--skip-portable-content-lint`).

`make_repo_snapshot.py` keeps `--out` for backward compatibility; `--zip-out`
is an explicit zip alias and the recommended form for share commands.

Snapshot manifest portability (default):

- `repo_snapshot_manifest.json` now uses `repo_root="."` by default.
- Machine-local absolute paths are excluded unless explicitly requested with
  `--include-absolute-paths` (adds `repo_root_abs`).

## Preflight safety check

Before sending any directory/zip, run:

`python3 scripts/preflight_share_check.py --path <zip_or_dir> --max-mb 50 --format text`

This checks size budget and forbidden path patterns (for example `.git/`,
`__MACOSX/`, `.DS_Store`, `.venv/`, build/dist artifacts).

Path preflight does not inspect JSON/JSONL file contents. For content-level
portability checks (machine-local absolute paths embedded inside artifacts), run:

`python3 scripts/phase2_portable_content_lint.py --path <zip_or_dir> --format text`

Use both checks together before sharing reviewer-facing archives.

If you need custom policy for one run, add:

- `--forbid-pattern <pattern>` (repeatable)
- `--allow-pattern <pattern>` (repeatable exception list)

## Deterministic Phase-2 inventory check

To verify Phase-2 contract files exist in your checkout:

`python3 scripts/phase2_repo_inventory.py --repo-root the current framework --require-present --format text`

For machine-readable output:

`python3 scripts/phase2_repo_inventory.py --repo-root the current framework --require-present --format json --write phase2_inventory.json`

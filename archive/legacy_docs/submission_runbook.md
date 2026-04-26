# Submission Runbook (operator)

## What to upload

Upload only:
- `submission_bundle_v10.1.1-late-time-r4.zip`

Do not upload:
- `referee_pack_*.zip`
- `toe_bundle_*.zip`
- diagnostic assets (`paper_assets_*diagnostic*.zip`)

## Fast path (copy-paste)

```bash
bash scripts/fetch_canonical_artifacts.sh --artifacts-dir . --fetch-missing
bash scripts/operator_one_button.sh --artifacts-dir . --fetch-missing --report /tmp/operator_report.json
bash scripts/release_candidate_check.sh --artifacts-dir . --print-required
```

Expected report signals (`/tmp/operator_report.json`):
- `overall_status: "PASS"`
- `artifacts[*].sha256_match: true`
- `artifacts[*].fetched_during_run` (true/false per artifact)
- `steps[*].duration_sec` and `summary.duration_sec_total`

## Publication-grade preflight

Run this before real upload:

```bash
bash scripts/arxiv_preflight_check.sh submission_bundle_v10.1.1-late-time-r4.zip
```

Interpretation:
- `PASS`: no hard blockers detected.
- `WARN`: upload can proceed, but review warnings (size/filename/layout/log hints).
- `FAIL`: do not upload; fix listed blockers first.

Local reproduction for compile hygiene is printed automatically on `FAIL` (including `pdflatex`/`bibtex` passes).

## One-command upload portal (ready-to-send folder)

```bash
bash scripts/operator_one_button.sh \
  --artifacts-dir . \
  --fetch-missing \
  --prepare-upload-dir /tmp/gsc_upload_portal \
  --prepare-upload-zip /tmp/gsc_upload_portal.zip \
  --report /tmp/operator_report.json
```

The generated directory contains:
- `/tmp/gsc_upload_portal/arxiv/submission_bundle_*.zip` (upload this to arXiv/journal)
- `/tmp/gsc_upload_portal/referee_pack/referee_pack_*.zip` (separate referee material)
- `/tmp/gsc_upload_portal/toe/toe_bundle_*.zip` (separate ToE package)
- `/tmp/gsc_upload_portal/late_time/paper_assets_*.zip` (canonical late-time assets archive)
- `/tmp/gsc_upload_portal/late_time/GSC_Framework_v10_1_FINAL.pdf` (if preflight full-compile produced it from canonical submission zip)
- `/tmp/gsc_upload_portal/late_time/PDF_PROVENANCE.txt` (source submission zip + SHA + produced PDF SHA)
- `/tmp/gsc_upload_portal/reports/operator_report.json` (operator workflow report)
- `/tmp/gsc_upload_portal/reports/rc_check.json` (RC checker report)
- `/tmp/gsc_upload_portal/reports/arxiv_preflight.json` (publication preflight report)
- `/tmp/gsc_upload_portal/reports/README_REPORTS.md` (PASS/WARN/FAIL semantics)
- `/tmp/gsc_upload_portal/CHECKLIST_PUBLISH.md` (upload targets + verification checklist)
- `/tmp/gsc_upload_portal/checksums/SHA256SUMS.txt` + `/tmp/gsc_upload_portal/README_UPLOAD.md`
- `/tmp/gsc_upload_portal/REPORT_OPERATOR_SUMMARY.txt` (human-readable PASS/FAIL summary)
- `/tmp/gsc_upload_portal.zip` + `/tmp/gsc_upload_portal.zip.sha256` (optional single-file handoff archive)

## Verified on clean clone

Verified flow (clean checkout / empty artifact dir):

```bash
bash scripts/fetch_canonical_artifacts.sh --artifacts-dir . --fetch-missing
bash scripts/operator_one_button.sh --artifacts-dir . --fetch-missing --prepare-upload-dir /tmp/gsc_upload_portal_final --report /tmp/operator_report_final.json
bash scripts/release_candidate_check.sh --artifacts-dir . --print-required
bash scripts/arxiv_preflight_check.sh submission_bundle_v10.1.1-late-time-r4.zip
```

Expected outcome:
- `operator_one_button` prints `RESULT: PASS` and writes `/tmp/operator_report_final.json` (`overall_status=PASS`).
- `/tmp/gsc_upload_portal_final/` contains the 4 canonical zips, checksums, and operator summary.
- Direct GitHub release URLs may return `404` in restricted environments; automatic `gh release download` fallback + SHA256 verification is expected.

## Cold start (fresh clone)

```bash
bash scripts/fetch_canonical_artifacts.sh --artifacts-dir . --fetch-missing
bash scripts/operator_one_button.sh --artifacts-dir . --fetch-missing --report /tmp/operator_report.json
bash scripts/release_candidate_check.sh --artifacts-dir . --print-required
```

Upload only:
- `submission_bundle_v10.1.1-late-time-r4.zip`

Do not upload:
- `referee_pack_v10.1.1-late-time-r4-r7.zip`
- `toe_bundle_v10.1.1-r2.zip`
- diagnostic assets (`paper_assets_*diagnostic*.zip`)

## Build fresh submission bundle from canonical paper assets

```bash
bash scripts/make_submission_bundle.sh /path/to/paper_assets_v10.1.1-late-time-r4.zip
bash scripts/verify_submission_bundle.sh --smoke-compile submission_bundle_v10.1.1-late-time-r4.zip
```

Manual compile from canonical submission zip:

```bash
TMP="$(mktemp -d)"
unzip -q submission_bundle_v10.1.1-late-time-r4.zip -d "$TMP"
cd "$TMP"
pdflatex -interaction=nonstopmode -halt-on-error GSC_Framework_v10_1_FINAL.tex
pdflatex -interaction=nonstopmode -halt-on-error GSC_Framework_v10_1_FINAL.tex
pdflatex -interaction=nonstopmode -halt-on-error GSC_Framework_v10_1_FINAL.tex
```

Verify-only workflow using an existing portal (no rerun needed):

```bash
cd /tmp/gsc_upload_portal
shasum -a 256 -c checksums/SHA256SUMS.txt
cat REPORT_OPERATOR_SUMMARY.txt
cat reports/README_REPORTS.md
```

## Common failures & fixes

| Symptom | Meaning | Operator action |
|---|---|---|
| `WARN: bundle_vs_repo_tex_drift` | Frozen canonical submission TeX differs from current repo wording. | Expected for frozen `submission-r2`; upload canonical submission zip unless project lead explicitly re-cuts submission tag. |
| `ERROR: missing required canonical artifact` | One or more canonical zips are absent in `--artifacts-dir`. | Run `bash scripts/fetch_canonical_artifacts.sh --artifacts-dir . --fetch-missing`, then rerun operator command. |
| `sha256 mismatch` | Local file exists but is not the canonical artifact bytes. | Delete/re-download exact asset; verify with `shasum -a 256`. |
| `arXiv preflight` hard FAIL | Submission zip contains unsafe/junk/missing TeX assets. | Rebuild from canonical late-time assets and rerun preflight. |
| Direct release URL returns `404/403` | Environment blocks unauthenticated direct download. | Let fetcher fallback to `gh release download` or use manual `curl` command printed by fetcher and verify SHA. |

- Missing artifact file:
  - Run `bash scripts/fetch_canonical_artifacts.sh --artifacts-dir . --fetch-missing`.
  - Or run `bash scripts/release_candidate_check.sh --artifacts-dir . --print-required` and place the listed zip files in `.` (or pass the correct `--artifacts-dir`).
- SHA256 mismatch:
  - Re-download the exact asset from the tag in `canonical_artifacts.json`; do not reuse renamed/manual zips.
- arXiv preflight failure (`.aux/.log`/nested zip/symlink):
  - Rebuild canonical submission bundle from canonical paper assets and rerun preflight:
    - `bash scripts/make_submission_bundle.sh /path/to/paper_assets_v10.1.1-late-time-r4.zip`
    - `bash scripts/arxiv_preflight_check.sh submission_bundle_v10.1.1-late-time-r4.zip`
  - If preflight reports forbidden TeX constructs (`\write18` / shell-escape hints), remove those lines and rebuild the submission bundle.
  - If preflight reports missing TeX-referenced assets, rebuild submission from the canonical late-time assets zip (do not hand-edit bundle contents).
  - If preflight reports only `WARN:` lines (for example large files/non-standard extensions), upload is still generally safe; keep the warning note in your submission log and proceed unless your journal has stricter limits.
- `pdflatex` missing during smoke compile:
  - Install TeX (`pdflatex`) or run RC check on a machine with LaTeX.
- Pointer SoT lint failure:
  - Fix stale tag/asset/SHA pointers in `README.md`, `GSC_ONBOARDING_NEXT_SESSION.md`, `README.md`, or `docs/**` (excluding `docs/popular/**`), then rerun RC check.
- Referee/toe verify failure:
  - Confirm the exact canonical filenames from `--print-required` and verify those files directly.
- Wrong artifacts directory:
  - If zips are not in repo root, use `--artifacts-dir /path/to/dir` for both `operator_one_button.sh` and `release_candidate_check.sh`.
- Want report-only output first:
  - Run `bash scripts/operator_one_button.sh --artifacts-dir . --dry-run`.
- Need a machine-readable run result:
  - Run `bash scripts/operator_one_button.sh --artifacts-dir . --report /tmp/operator_report.json`.
- Network fetch failed:
  - Use the printed `release_url` + `asset_filename` + `expected_sha256` from fetch output, download manually, then re-run `release_candidate_check`.
  - For private release assets: run `gh auth login` (or export `GITHUB_TOKEN`) and retry `fetch_canonical_artifacts.sh` (it can fallback to `gh release download`).
- `operator_one_button` fails at `build_paper --no-reproduce` in a fresh clone:
  - Ensure `paper_assets_v10.1.1-late-time-r4.zip` is present in `--artifacts-dir`.
  - Re-run with fetch enabled:
    - `bash scripts/operator_one_button.sh --artifacts-dir . --fetch-missing`
  - The operator flow now auto-materializes `paper_assets/` from the canonical late-time zip when missing.
- Local default referee-pack filename confusion:
  - Local build default from `make_referee_pack.sh` is not necessarily the canonical release asset name; canonical names/SHAs always come from `canonical_artifacts.json`.

## Canonical SoT

Machine-readable source of truth:
- `canonical_artifacts.json`

Human-readable companion:
- `docs/status_canonical_artifacts.md`

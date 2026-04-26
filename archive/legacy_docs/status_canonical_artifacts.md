# Canonical Artifacts Status

Machine-readable source of truth:
- `canonical_artifacts.json`

One-command offline RC check:
- `bash scripts/release_candidate_check.sh --artifacts-dir .`
- Operator one-button command:
  - `bash scripts/operator_one_button.sh --artifacts-dir .`

Canonical set (exactly what the RC checker validates from JSON):

| Line | Tag | Asset | SHA256 | Verify |
|---|---|---|---|---|
| late-time | `v10.1.1-late-time-r4` | `paper_assets_v10.1.1-late-time-r4.zip` | `b29d5cb0e30941d2bb0cb4b2930f21a4a219a7e0a8439f7fec82704134cf4823` | `bash scripts/verify_release_bundle.sh /path/to/paper_assets_v10.1.1-late-time-r4.zip` |
| submission | `v10.1.1-submission-r2` | `submission_bundle_v10.1.1-late-time-r4.zip` | `fa06a2ce85a7991fa63670eb867a03fda4213989ca981b437e2ae2c5d8c3efe5` | `bash scripts/verify_submission_bundle.sh --smoke-compile submission_bundle_v10.1.1-late-time-r4.zip` |
| referee pack (recommended) | `v10.1.1-referee-pack-r7` | `referee_pack_v10.1.1-late-time-r4-r7.zip` | `4faf0f4d5754bcd18c401c709396965229d4da7dc73cd4aa7bec38cebca1a2b0` | `bash scripts/verify_referee_pack.sh referee_pack_v10.1.1-late-time-r4-r7.zip` |
| ToE bundle (recommended) | `v10.1.1-toe-track-r2` | `toe_bundle_v10.1.1-r2.zip` | `0d328efefc59e4744b6998b7ea14c3c3c932ad8575377d7a5629ec2fe5663894` | `bash scripts/verify_toe_bundle.sh toe_bundle_v10.1.1-r2.zip` |

Frozen guardrails (do not retag/regenerate):
- `v10.1.1-late-time-r4`
- `v10.1.1-submission-r2`
- `v10.1.1-referee-pack-r4` (frozen baseline remains valid even though `r7` is recommended)

Useful helper commands:
- Fetch missing canonical assets (opt-in network + SHA verify):
  - `bash scripts/fetch_canonical_artifacts.sh --artifacts-dir . --fetch-missing`
- arXiv/journal preflight for canonical submission zip:
  - `bash scripts/arxiv_preflight_check.sh submission_bundle_v10.1.1-late-time-r4.zip`
- Print required filenames/SHA from SoT without running checks:
  - `bash scripts/release_candidate_check.sh --artifacts-dir . --print-required`
- Lint pointers against SoT (README/onboarding/docs):
  - `python3 scripts/pointer_sot_lint.py`
- Verify catalog/SHA + per-artifact validators:
  - `bash scripts/verify_all_canonical_artifacts.sh --artifacts-dir .`

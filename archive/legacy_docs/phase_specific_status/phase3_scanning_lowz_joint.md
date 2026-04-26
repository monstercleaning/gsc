# Phase-3 scanning over LOWZ_JOINT (diagnostic)

This document describes deterministic mini-scan scaffolding for
`phase3_joint_sigmatensor_lowz_report.py`.

Scope boundary: this is a diagnostic triage workflow, not MCMC and not a full
global likelihood fit.

## 1) Generate a deterministic plan

```bash
python3 scripts/phase3_scan_sigmatensor_lowz_joint.py \
  --plan-out /tmp/phase3_lowz_plan.json \
  --H0-km-s-Mpc 67.4 \
  --Omega-m-min 0.28 --Omega-m-max 0.34 --Omega-m-steps 4 \
  --w0-min -1.05 --w0-max -0.85 --w0-steps 5 \
  --lambda-min 0.0 --lambda-max 0.8 --lambda-steps 5 \
  --created-utc 2000-01-01T00:00:00Z
```

The plan stores `plan_point_id` and `plan_source_sha256` for deterministic
resume/merge behavior.

## 2) Run scan (single worker)

```bash
python3 scripts/phase3_scan_sigmatensor_lowz_joint.py \
  --plan /tmp/phase3_lowz_plan.json \
  --out-jsonl /tmp/phase3_lowz_scan.jsonl.gz \
  --joint-extra-arg --bao --joint-extra-arg 1 \
  --joint-extra-arg --sn --joint-extra-arg 1 \
  --joint-extra-arg --rsd --joint-extra-arg 1 \
  --joint-extra-arg --cmb --joint-extra-arg 0 \
  --joint-extra-arg --compare-lcdm --joint-extra-arg 1 \
  --created-utc 2000-01-01T00:00:00Z
```

## 3) Plan slicing for cluster arrays

```bash
python3 scripts/phase3_scan_sigmatensor_lowz_joint.py \
  --plan /tmp/phase3_lowz_plan.json \
  --plan-slice 0/8 \
  --out-jsonl /tmp/shards/slice_0.jsonl.gz \
  --joint-extra-arg --bao --joint-extra-arg 1 \
  --joint-extra-arg --sn --joint-extra-arg 1 \
  --joint-extra-arg --rsd --joint-extra-arg 0 \
  --joint-extra-arg --cmb --joint-extra-arg 0
```

Repeat with `1/8`, `2/8`, ..., `7/8`.

## 4) Merge shards with existing deterministic tool

```bash
python3 scripts/phase2_e2_merge_jsonl.py \
  --inputs /tmp/shards \
  --out /tmp/merged.jsonl.gz \
  --dedupe-key plan_point_id \
  --prefer ok_then_lowest_chi2
```

## 5) Inspect best rows (quick shell snippets)

```bash
gzip -cd /tmp/merged.jsonl.gz | jq -c 'select(.status=="ok")' | head
```

```bash
gzip -cd /tmp/merged.jsonl.gz | jq -s 'map(select(.status=="ok")) | sort_by(.chi2_total) | .[0]'
```

## 6) Analyze scan outputs and extract top candidates

```bash
python3 scripts/phase3_analyze_sigmatensor_lowz_scan.py \
  --inputs /tmp/shards \
  --outdir /tmp/analysis \
  --top-k 10 \
  --metric chi2_total \
  --emit-reproduce 1 \
  --joint-extra-arg --bao --joint-extra-arg 1 \
  --joint-extra-arg --sn --joint-extra-arg 1 \
  --joint-extra-arg --rsd --joint-extra-arg 1 \
  --joint-extra-arg --cmb --joint-extra-arg 1 \
  --joint-extra-arg --compare-lcdm --joint-extra-arg 1 \
  --created-utc 2000-01-01T00:00:00Z
```

This writes deterministic portable artifacts:

- `SCAN_ANALYSIS.json`
- `SCAN_ANALYSIS.md`
- `BEST_CANDIDATES.csv`
- `REPRODUCE_TOP_CANDIDATES.sh` (optional helper commands only)

## 7) Build candidate dossier pack (top-N)

```bash
python3 scripts/phase3_make_sigmatensor_candidate_dossier_pack.py \
  --analysis /tmp/analysis/SCAN_ANALYSIS.json \
  --outdir /tmp/dossier \
  --top-k 5 \
  --joint-extra-arg --bao --joint-extra-arg 1 \
  --joint-extra-arg --sn --joint-extra-arg 1 \
  --joint-extra-arg --rsd --joint-extra-arg 0 \
  --joint-extra-arg --cmb --joint-extra-arg 1 \
  --fsigma8-extra-arg --rsd --fsigma8-extra-arg 0 \
  --emit-zip 1 --zip-out /tmp/dossier.zip \
  --created-utc 2000-01-01T00:00:00Z
```

The dossier pack writes per-candidate deterministic outputs for joint/fsigma8/EFT/CLASS-export
reports plus `DOSSIER_MANIFEST.json`, reproducible shell scripts, and optional deterministic zip.

By default, dossier generation also writes a CLASS mapping validation report:
`class_mapping/CLASS_MAPPING_REPORT.{json,md}`. This compares the SigmaTensor
diagnostic grid against the w0wa fluid approximation used by the CLASS ini
template. Disable it with `--include-class-mapping-report 0`.

When `--emit-zip 1` is used, the zip includes the full dossier tree, including
`DOSSIER_MANIFEST.json` and `DOSSIER_MANIFEST.md`. The zip checksum is written as
an external sidecar file (`<zip>.sha256`) because embedding zip sha256 inside the
zip content itself would be circular.

## 8) Dossier quicklook report

Generate an aggregate reviewer-facing summary of key metrics across all dossier candidates:

```bash
python3 scripts/phase3_dossier_quicklook_report.py \
  --dossier /tmp/dossier \
  --outdir /tmp/dossier \
  --created-utc 2000-01-01T00:00:00Z \
  --format text
```

This writes:

- `DOSSIER_QUICKLOOK.json`
- `DOSSIER_QUICKLOOK.csv`
- `DOSSIER_QUICKLOOK.md`

`DOSSIER_QUICKLOOK.json` includes per-candidate aggregates for low-z joint chi2
blocks, optional deltas, CLASS mapping residuals, and spectra-TT sanity metrics.
The dossier pack emits this quicklook by default; disable with `--emit-quicklook 0`.

## 9) Optional: run CLASS and attach results + spectra sanity

```bash
python3 scripts/phase3_make_sigmatensor_candidate_dossier_pack.py \
  --analysis /tmp/analysis/SCAN_ANALYSIS.json \
  --outdir /tmp/dossier_with_runs \
  --top-k 2 \
  --joint-extra-arg --bao --joint-extra-arg 0 \
  --joint-extra-arg --sn --joint-extra-arg 0 \
  --joint-extra-arg --rsd --joint-extra-arg 0 \
  --joint-extra-arg --cmb --joint-extra-arg 0 \
  --joint-extra-arg --compare-lcdm --joint-extra-arg 0 \
  --fsigma8-extra-arg --rsd --fsigma8-extra-arg 0 \
  --include-class-run 1 \
  --class-runner native \
  --created-utc 2000-01-01T00:00:00Z
```

Pipeline order inside each candidate directory:
`class/` export pack -> `class_run/` run harness outputs -> `class_results/`
results pack -> `spectra_sanity/` deterministic sanity report.

## 10) Jobgen pack (bash/slurm)

For repeatable cluster/local orchestration, generate a deterministic job pack
that wires:
plan -> run slices -> merge -> analyze -> dossier.

Grid-spec plan mode:

```bash
python3 scripts/phase3_lowz_jobgen.py \
  --outdir /tmp/phase3_lowz_job_pack \
  --slices 8 \
  --scheduler slurm_array \
  --shards-compress gzip \
  --H0-km-s-Mpc 67.4 \
  --Omega-m-min 0.28 --Omega-m-max 0.34 --Omega-m-steps 4 \
  --w0-min -1.05 --w0-max -0.85 --w0-steps 5 \
  --lambda-min 0.0 --lambda-max 0.8 --lambda-steps 5 \
  --joint-extra-arg --bao --joint-extra-arg 1 \
  --joint-extra-arg --sn --joint-extra-arg 1 \
  --joint-extra-arg --rsd --joint-extra-arg 0 \
  --joint-extra-arg --cmb --joint-extra-arg 1 \
  --joint-extra-arg --compare-lcdm --joint-extra-arg 1 \
  --created-utc 2000-01-01T00:00:00Z
```

Plan-copy mode:

```bash
python3 scripts/phase3_lowz_jobgen.py \
  --outdir /tmp/phase3_lowz_job_pack \
  --slices 8 \
  --plan /tmp/phase3_lowz_plan.json \
  --created-utc 2000-01-01T00:00:00Z
```

The pack includes:

- `run_slice_XX_of_NN.sh` (slice workers)
- `run_all_local.sh` and optional `slurm_array_job.sh`
- `merge_shards.sh`
- `analyze.sh`
- `dossier.sh`
- `status.sh`

`--slices 1` is supported for local/toy runs. In this mode, merge still works
with a single shard (`shards/shard_slice_00_of_01.jsonl.gz` by default).

Runtime overrides are environment-based and portable by default:
`GSC_REPO_ROOT`, `GSC_PYTHON`, `GSC_CREATED_UTC`, plus optional dossier class-run
flags (`GSC_INCLUDE_CLASS_RUN`, `GSC_CLASS_RUNNER`, `GSC_CLASS_BIN`,
`GSC_CLASS_DOCKER_IMAGE`).

#!/usr/bin/env python3
"""Generate deterministic distributed job packs for Phase-2 E2 plan slicing.

This tool is stdlib-only and additive: it does not change scan/merge/bundle
interfaces. It emits runnable bash or Slurm-array wrappers around
``phase2_e2_scan.py --plan --plan-slice I/N``.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shlex
import stat
import subprocess
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


V101_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V101_DIR))

from gsc.early_time.refine_plan_v1 import (  # noqa: E402
    get_plan_source_sha256,
    iter_plan_points,
    load_refine_plan_v1,
    write_refine_plan_v1,
)


_SCHEMA = "phase2_e2_jobgen_v1"
_RESERVED_SCAN_FLAGS = {
    "--plan",
    "--plan-slice",
    "--resume",
    "--dry-run",
    "--out-dir",
    "--outdir",
}


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _normalize_created_utc(value: Optional[str]) -> str:
    if value is None:
        return _now_utc()
    text = str(value).strip()
    if not text:
        return _now_utc()
    try:
        _ = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception as exc:
        raise SystemExit(f"Invalid --created-utc value: {value!r}") from exc
    return text


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _split_prefix_and_scan_args(argv: Sequence[str]) -> Tuple[List[str], List[str]]:
    tokens = list(argv)
    if "--" not in tokens:
        return tokens, []
    idx = tokens.index("--")
    return tokens[:idx], tokens[idx + 1 :]


def _extract_scan_extra_args(prefix_tokens: Sequence[str]) -> Tuple[List[str], List[str]]:
    cleaned: List[str] = []
    extra: List[str] = []
    idx = 0
    tokens = list(prefix_tokens)
    while idx < len(tokens):
        token = str(tokens[idx])
        if token == "--scan-extra-arg":
            if idx + 1 >= len(tokens):
                raise SystemExit("--scan-extra-arg requires one literal token argument")
            extra.append(str(tokens[idx + 1]))
            idx += 2
            continue
        if token.startswith("--scan-extra-arg="):
            extra.append(str(token.split("=", 1)[1]))
            idx += 1
            continue
        cleaned.append(token)
        idx += 1
    return cleaned, extra


def _contains_model_flag(extra_args: Sequence[str]) -> bool:
    for idx, token in enumerate(extra_args):
        text = str(token)
        if text == "--model":
            if idx + 1 < len(extra_args):
                nxt = str(extra_args[idx + 1]).strip()
                if nxt and not nxt.startswith("--"):
                    return True
        if text.startswith("--model="):
            rhs = text.split("=", 1)[1].strip()
            if rhs:
                return True
    return False


def _validate_scan_extra_args(extra_args: Sequence[str]) -> None:
    for token in extra_args:
        text = str(token).strip()
        if not text:
            continue
        for flag in _RESERVED_SCAN_FLAGS:
            if text == flag or text.startswith(flag + "="):
                raise SystemExit(
                    f"Scan pass-through args must not include {flag}; jobgen controls this flag."
                )
    if not _contains_model_flag(extra_args):
        raise SystemExit(
            "Scan pass-through args must include --model <name> (or --model=<name>). "
            "Pass scan args after '--', e.g. -- --model lcdm --toy"
        )


def _resolve_repo_root(path: Optional[Path]) -> Path:
    if path is None:
        return V101_DIR
    return path.expanduser().resolve()


def _git_sha(repo_root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            text=True,
            capture_output=True,
            check=True,
        )
        out = str((proc.stdout or "").strip())
        return out or "unknown"
    except Exception:
        return "unknown"


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _write_text(path: Path, text: str, *, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if executable:
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _bash_quote(value: str) -> str:
    return shlex.quote(str(value))


def _shell_literal_list(items: Sequence[str]) -> str:
    if not items:
        return "()"
    return "(" + " ".join(_bash_quote(str(item)) for item in items) + ")"


def _common_shell_prelude(*, repo_root_fallback: Path, python_fallback: str) -> List[str]:
    return [
        "set -euo pipefail",
        "",
        'JOB_ROOT="$(cd "$(dirname "$0")" && pwd)"',
        f'REPO_ROOT="${{GSC_REPO_ROOT:-{_bash_quote(str(repo_root_fallback))}}}"',
        f'PY="${{GSC_PYTHON:-{_bash_quote(str(python_fallback))}}}"',
        "",
        'if [[ -f "$REPO_ROOT/scripts/phase2_e2_scan.py" ]]; then',
        '  SCRIPTS_ROOT="$REPO_ROOT/scripts"',
        'elif [[ -f "$REPO_ROOT/v11.0.0/scripts/phase2_e2_scan.py" ]]; then',
        '  SCRIPTS_ROOT="$REPO_ROOT/v11.0.0/scripts"',
        "else",
        '  echo "Could not locate scripts directory under REPO_ROOT=$REPO_ROOT" >&2',
        "  exit 2",
        "fi",
        "",
    ]


def _slice_labels(index: int, total: int, width: int) -> Tuple[str, str]:
    return (f"{int(index):0{int(width)}d}", f"{int(total):0{int(width)}d}")


def _default_merged_jsonl_name(shards_compress: str) -> str:
    return "merged.jsonl.gz" if str(shards_compress) == "gzip" else "merged.jsonl"


def _emit_bash_slice_script(
    *,
    outdir: Path,
    index: int,
    total: int,
    width: int,
    repo_root_fallback: Path,
    python_fallback: str,
    scan_extra_args: Sequence[str],
    shards_compress: str,
) -> Path:
    i_label, n_label = _slice_labels(index, total, width)
    script_path = outdir / f"run_slice_{i_label}_of_{n_label}.sh"
    rel_out_dir = f'slice_{i_label}_of_{n_label}'
    points_jsonl_name = "e2_scan_points.jsonl.gz" if str(shards_compress) == "gzip" else "e2_scan_points.jsonl"
    lines: List[str] = ["#!/usr/bin/env bash"]
    lines.extend(_common_shell_prelude(repo_root_fallback=repo_root_fallback, python_fallback=python_fallback))
    lines.extend(
        [
            'SCAN_SCRIPT="$SCRIPTS_ROOT/phase2_e2_scan.py"',
            'PLAN="$JOB_ROOT/plan.json"',
            f'SLICE_OUTDIR="$JOB_ROOT/shards/{rel_out_dir}"',
            f'POINTS_JSONL_NAME="{points_jsonl_name}"',
            'OUT_JSONL="$SLICE_OUTDIR/$POINTS_JSONL_NAME"',
            f'EXTRA_ARGS={_shell_literal_list(scan_extra_args)}',
            "",
            'mkdir -p "$SLICE_OUTDIR"',
            'cd "$REPO_ROOT"',
            "",
            'cmd=(',
            '  "$PY" "$SCAN_SCRIPT"',
            '  "--plan" "$PLAN"',
            f'  "--plan-slice" "{int(index)}/{int(total)}"',
            '  "--out-dir" "$SLICE_OUTDIR"',
            '  "--points-jsonl-name" "$POINTS_JSONL_NAME"',
            '  "--resume"',
            ')',
            'if [[ "${#EXTRA_ARGS[@]}" -gt 0 ]]; then',
            '  cmd+=("${EXTRA_ARGS[@]}")',
            "fi",
            "",
            '"${cmd[@]}"',
            'echo "[ok] slice '
            + f'{int(index)}/{int(total)}'
            + ' -> $OUT_JSONL"',
            "",
        ]
    )
    _write_text(script_path, "\n".join(lines), executable=True)
    return script_path


def _emit_slurm_array_script(
    *,
    outdir: Path,
    total: int,
    width: int,
    repo_root_fallback: Path,
    python_fallback: str,
    scan_extra_args: Sequence[str],
    shards_compress: str,
) -> Path:
    script_path = outdir / "slurm_array.sbatch"
    points_jsonl_name = "e2_scan_points.jsonl.gz" if str(shards_compress) == "gzip" else "e2_scan_points.jsonl"
    lines: List[str] = [
        "#!/usr/bin/env bash",
        f"#SBATCH --array=0-{int(total) - 1}",
        "#SBATCH --job-name=gsc_e2_slice",
        "#SBATCH --output=slurm_%A_%a.out",
        "#SBATCH --error=slurm_%A_%a.err",
        "",
    ]
    lines.extend(_common_shell_prelude(repo_root_fallback=repo_root_fallback, python_fallback=python_fallback))
    lines.extend(
        [
            f'N="{int(total)}"',
            f'PAD="{int(width)}"',
            'i="${SLURM_ARRAY_TASK_ID:?SLURM_ARRAY_TASK_ID is required}"',
            'if [[ "$i" -lt 0 || "$i" -ge "$N" ]]; then',
            '  echo "SLURM_ARRAY_TASK_ID out of range: $i (N=$N)" >&2',
            "  exit 2",
            "fi",
            'i_label="$(printf "%0${PAD}d" "$i")"',
            'n_label="$(printf "%0${PAD}d" "$N")"',
            'SCAN_SCRIPT="$SCRIPTS_ROOT/phase2_e2_scan.py"',
            'PLAN="$JOB_ROOT/plan.json"',
            'SLICE_OUTDIR="$JOB_ROOT/shards/slice_${i_label}_of_${n_label}"',
            f'POINTS_JSONL_NAME="{points_jsonl_name}"',
            'OUT_JSONL="$SLICE_OUTDIR/$POINTS_JSONL_NAME"',
            f'EXTRA_ARGS={_shell_literal_list(scan_extra_args)}',
            "",
            'mkdir -p "$SLICE_OUTDIR"',
            'cd "$REPO_ROOT"',
            "",
            'cmd=(',
            '  "$PY" "$SCAN_SCRIPT"',
            '  "--plan" "$PLAN"',
            '  "--plan-slice" "${i}/${N}"',
            '  "--out-dir" "$SLICE_OUTDIR"',
            '  "--points-jsonl-name" "$POINTS_JSONL_NAME"',
            '  "--resume"',
            ')',
            'if [[ "${#EXTRA_ARGS[@]}" -gt 0 ]]; then',
            '  cmd+=("${EXTRA_ARGS[@]}")',
            "fi",
            "",
            '"${cmd[@]}"',
            'echo "[ok] slice ${i}/${N} -> $OUT_JSONL"',
            "",
        ]
    )
    _write_text(script_path, "\n".join(lines), executable=True)
    return script_path


def _emit_merge_script(
    *,
    outdir: Path,
    repo_root_fallback: Path,
    python_fallback: str,
    shards_compress: str,
) -> Path:
    script_path = outdir / "merge_shards.sh"
    points_jsonl_name = "e2_scan_points.jsonl.gz" if str(shards_compress) == "gzip" else "e2_scan_points.jsonl"
    merged_jsonl_name = _default_merged_jsonl_name(str(shards_compress))
    lines: List[str] = ["#!/usr/bin/env bash"]
    lines.extend(_common_shell_prelude(repo_root_fallback=repo_root_fallback, python_fallback=python_fallback))
    lines.extend(
        [
            'MERGE_SCRIPT="$SCRIPTS_ROOT/phase2_e2_merge_jsonl.py"',
            'PLAN="$JOB_ROOT/plan.json"',
            f'POINTS_JSONL_NAME="{points_jsonl_name}"',
            f'MERGED_JSONL="${{MERGED_JSONL:-{merged_jsonl_name}}}"',
            'MERGE_CHUNK_RECORDS="${GSC_MERGE_CHUNK_RECORDS:-200000}"',
            'MERGE_TMPDIR="${GSC_MERGE_TMPDIR:-$JOB_ROOT/tmp_merge}"',
            'MERGE_KEEP_TMP="${GSC_MERGE_KEEP_TMP:-0}"',
            'if [[ "$MERGED_JSONL" = /* ]]; then',
            '  MERGED_PATH="$MERGED_JSONL"',
            "else",
            '  MERGED_PATH="$JOB_ROOT/$MERGED_JSONL"',
            "fi",
            'mkdir -p "$MERGE_TMPDIR"',
            "SHARD_JSONLS=()",
            'while IFS= read -r path; do',
            '  SHARD_JSONLS+=("$path")',
            'done < <(find "$JOB_ROOT/shards" -type f -name "$POINTS_JSONL_NAME" -print | LC_ALL=C sort)',
            'if [[ "${#SHARD_JSONLS[@]}" -lt 1 ]]; then',
            '  echo "No shard JSONL files found under $JOB_ROOT/shards with filename=$POINTS_JSONL_NAME" >&2',
            "  exit 2",
            "fi",
            "",
            'if [[ ! -f "$PLAN" ]]; then',
            '  echo "Missing plan file: $PLAN" >&2',
            "  exit 2",
            "fi",
            "",
            'cmd=("$PY" "$MERGE_SCRIPT")',
            'for path in "${SHARD_JSONLS[@]}"; do',
            '  cmd+=("$path")',
            "done",
            'if [[ "${#SHARD_JSONLS[@]}" -eq 1 ]]; then',
            '  cmd+=("${SHARD_JSONLS[0]}")',
            "fi",
            'cmd+=(',
            '  "--out" "$MERGED_PATH"',
            '  "--report-out" "$JOB_ROOT/merge_report.json"',
            '  "--canonicalize"',
            '  "--plan" "$PLAN"',
            '  "--plan-source-policy" "match_plan"',
            '  "--scan-config-sha-policy" "require"',
            '  "--external-sort"',
            '  "--chunk-records" "$MERGE_CHUNK_RECORDS"',
            '  "--tmpdir" "$MERGE_TMPDIR"',
            ')',
            'if [[ "$MERGE_KEEP_TMP" == "1" ]]; then',
            '  cmd+=("--keep-tmp")',
            "fi",
            'cd "$REPO_ROOT"',
            '"${cmd[@]}"',
            'echo "[ok] merged -> $MERGED_PATH"',
            "",
        ]
    )
    _write_text(script_path, "\n".join(lines), executable=True)
    return script_path


def _emit_bundle_script(
    *,
    outdir: Path,
    repo_root_fallback: Path,
    python_fallback: str,
    paper_assets_mode: str,
    shards_compress: str,
) -> Path:
    script_path = outdir / "bundle.sh"
    merged_jsonl_name = _default_merged_jsonl_name(str(shards_compress))
    lines: List[str] = ["#!/usr/bin/env bash"]
    lines.extend(_common_shell_prelude(repo_root_fallback=repo_root_fallback, python_fallback=python_fallback))
    lines.extend(
        [
            'BUNDLE_SCRIPT="$SCRIPTS_ROOT/phase2_e2_bundle.py"',
            'MANIFEST_SCRIPT="$SCRIPTS_ROOT/phase2_e2_make_manifest.py"',
            'LINEAGE_SCRIPT="$SCRIPTS_ROOT/phase2_lineage_dag.py"',
            f'MERGED_JSONL="${{MERGED_JSONL:-{merged_jsonl_name}}}"',
            'if [[ "$MERGED_JSONL" = /* ]]; then',
            '  MERGED_PATH="$MERGED_JSONL"',
            "else",
            '  MERGED_PATH="$JOB_ROOT/$MERGED_JSONL"',
            "fi",
            'if [[ ! -f "$MERGED_PATH" ]]; then',
            '  echo "Missing merged JSONL: $MERGED_PATH" >&2',
            "  exit 2",
            "fi",
            "",
            'BUNDLE_DIR="$JOB_ROOT/bundle_dir"',
            f'PAPER_ASSETS_MODE="{str(paper_assets_mode)}"',
            'mkdir -p "$BUNDLE_DIR"',
            'cd "$REPO_ROOT"',
            '"$PY" "$BUNDLE_SCRIPT" \\',
            '  --in "$MERGED_PATH" \\',
            '  --outdir "$BUNDLE_DIR" \\',
            '  --overwrite \\',
            '  --steps merge,pareto,diagnostics,tension,sensitivity,paper_assets,manifest,meta \\',
            '  --paper-assets "$PAPER_ASSETS_MODE"',
            "",
            'cp "$JOB_ROOT/plan.json" "$BUNDLE_DIR/plan.json"',
            'rm -f "$BUNDLE_DIR/LINEAGE.json"',
            "",
            '"$PY" "$MANIFEST_SCRIPT" \\',
            '  --outdir "$BUNDLE_DIR" \\',
            '  --repo-root "$REPO_ROOT" \\',
            '  --manifest-name manifest.json \\',
            '  --deterministic \\',
            '  --input "$JOB_ROOT/plan.json" \\',
            '  --input "$MERGED_PATH" \\',
            '  --input "$SCRIPTS_ROOT/phase2_e2_bundle.py" \\',
            '  --input "$SCRIPTS_ROOT/phase2_e2_make_manifest.py" \\',
            '  --input "$SCRIPTS_ROOT/phase2_e2_merge_jsonl.py" \\',
            '  --input "$SCRIPTS_ROOT/phase2_e2_verify_bundle.py"',
            "",
            '"$PY" "$LINEAGE_SCRIPT" \\',
            '  --bundle-dir "$BUNDLE_DIR" \\',
            '  --out "$BUNDLE_DIR/LINEAGE.json" \\',
            '  --format json',
            "",
            'echo "[ok] bundle directory -> $BUNDLE_DIR"',
            "",
        ]
    )
    _write_text(script_path, "\n".join(lines), executable=True)
    return script_path


def _emit_verify_script(
    *,
    outdir: Path,
    repo_root_fallback: Path,
    python_fallback: str,
    paper_assets_mode: str,
) -> Path:
    script_path = outdir / "verify.sh"
    lines: List[str] = ["#!/usr/bin/env bash"]
    lines.extend(_common_shell_prelude(repo_root_fallback=repo_root_fallback, python_fallback=python_fallback))
    lines.extend(
        [
            'VERIFY_SCRIPT="$SCRIPTS_ROOT/phase2_e2_verify_bundle.py"',
            'BUNDLE_DIR="$JOB_ROOT/bundle_dir"',
            f'PAPER_ASSETS_MODE="{str(paper_assets_mode)}"',
            'VERIFY_PAPER_ASSETS="ignore"',
            'if [[ "$PAPER_ASSETS_MODE" != "none" ]]; then',
            '  VERIFY_PAPER_ASSETS="require"',
            "fi",
            'if [[ ! -d "$BUNDLE_DIR" ]]; then',
            '  echo "Missing bundle directory: $BUNDLE_DIR" >&2',
            "  exit 2",
            "fi",
            "",
            'cd "$REPO_ROOT"',
            '"$PY" "$VERIFY_SCRIPT" \\',
            '  --bundle "$BUNDLE_DIR" \\',
            '  --plan-coverage complete \\',
            '  --require-plan-source match_plan \\',
            '  --require-scan-config-sha 1 \\',
            '  --paper-assets "$VERIFY_PAPER_ASSETS" \\',
            '  --json-out "$JOB_ROOT/bundle_verify.json"',
            "",
            'echo "[ok] verified bundle directory $BUNDLE_DIR"',
            "",
        ]
    )
    _write_text(script_path, "\n".join(lines), executable=True)
    return script_path


def _emit_status_script(
    *,
    outdir: Path,
    repo_root_fallback: Path,
    python_fallback: str,
    shards_compress: str,
) -> Path:
    script_path = outdir / "status.sh"
    merged_jsonl_name = _default_merged_jsonl_name(str(shards_compress))
    lines: List[str] = ["#!/usr/bin/env bash"]
    lines.extend(_common_shell_prelude(repo_root_fallback=repo_root_fallback, python_fallback=python_fallback))
    lines.extend(
        [
            'STATUS_SCRIPT="$SCRIPTS_ROOT/phase2_e2_live_status.py"',
            'PLAN="$JOB_ROOT/plan.json"',
            f'MERGED_JSONL="${{MERGED_JSONL:-{merged_jsonl_name}}}"',
            'if [[ "$MERGED_JSONL" = /* ]]; then',
            '  MERGED_PATH="$MERGED_JSONL"',
            "else",
            '  MERGED_PATH="$JOB_ROOT/$MERGED_JSONL"',
            "fi",
            'SHARDS="$JOB_ROOT/shards"',
            "",
            'INPUT_ARGS=()',
            'if [[ -f "$MERGED_PATH" ]]; then',
            '  INPUT_ARGS+=("--input" "$MERGED_PATH")',
            "else",
            '  INPUT_ARGS+=("--input" "$SHARDS")',
            "fi",
            "",
            'PLAN_ARGS=()',
            'if [[ -f "$PLAN" ]]; then',
            '  PLAN_ARGS+=("--plan" "$PLAN")',
            "fi",
            "",
            'MODE_ARGS=("--mode" "summary")',
            'if [[ "${1:-}" == "--by-file" ]]; then',
            '  MODE_ARGS=("--mode" "by_file")',
            "  shift",
            "fi",
            '# phase2_e2_live_status auto-prints an "RSD overlay" section when rsd_* fields are present.',
            "",
            'cmd=(',
            '  "$PY" "$STATUS_SCRIPT"',
            '  "${INPUT_ARGS[@]}"',
            '  "${PLAN_ARGS[@]}"',
            '  "${MODE_ARGS[@]}"',
            '  "--format" "text"',
            '  "--tail-safe"',
            '  "--include-slice-summary"',
            ')',
            'if [[ "$#" -gt 0 ]]; then',
            '  cmd+=("$@")',
            "fi",
            "",
            'cd "$REPO_ROOT"',
            '"${cmd[@]}"',
            "",
        ]
    )
    _write_text(script_path, "\n".join(lines), executable=True)
    return script_path


def _emit_watch_script(
    *,
    outdir: Path,
    repo_root_fallback: Path,
    python_fallback: str,
) -> Path:
    script_path = outdir / "watch.sh"
    lines: List[str] = ["#!/usr/bin/env bash"]
    lines.extend(_common_shell_prelude(repo_root_fallback=repo_root_fallback, python_fallback=python_fallback))
    lines.extend(
        [
            'INTERVAL="60"',
            'if [[ "${1:-}" =~ ^[0-9]+$ ]]; then',
            '  INTERVAL="$1"',
            "  shift",
            "fi",
            'if [[ "$INTERVAL" -lt 1 ]]; then',
            '  echo "Interval must be >= 1 seconds" >&2',
            "  exit 2",
            "fi",
            "",
            'while true; do',
            '  printf "\\n[%s] phase2_e2_live_status\\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"',
            '  "$JOB_ROOT/status.sh" "$@"',
            '  sleep "$INTERVAL"',
            "done",
            "",
        ]
    )
    _write_text(script_path, "\n".join(lines), executable=True)
    return script_path


def _emit_requeue_script(
    *,
    outdir: Path,
    repo_root_fallback: Path,
    python_fallback: str,
    shards_compress: str,
) -> Path:
    script_path = outdir / "requeue.sh"
    merged_jsonl_name = _default_merged_jsonl_name(str(shards_compress))
    lines: List[str] = ["#!/usr/bin/env bash"]
    lines.extend(_common_shell_prelude(repo_root_fallback=repo_root_fallback, python_fallback=python_fallback))
    lines.extend(
        [
            'REQUEUE_SCRIPT="$SCRIPTS_ROOT/phase2_e2_requeue_plan.py"',
            'PLAN="$JOB_ROOT/plan.json"',
            f'MERGED_JSONL="${{MERGED_JSONL:-{merged_jsonl_name}}}"',
            'if [[ "$MERGED_JSONL" = /* ]]; then',
            '  MERGED_PATH="$MERGED_JSONL"',
            "else",
            '  MERGED_PATH="$JOB_ROOT/$MERGED_JSONL"',
            "fi",
            'SHARDS="$JOB_ROOT/shards"',
            'OUT_PLAN="$JOB_ROOT/plan_requeue.json"',
            "",
            'INPUT_ARGS=()',
            'if [[ -d "$SHARDS" ]]; then',
            '  INPUT_ARGS+=("--input" "$SHARDS")',
            "fi",
            'if [[ -f "$MERGED_PATH" ]]; then',
            '  INPUT_ARGS+=("--input" "$MERGED_PATH")',
            "fi",
            'if [[ "${#INPUT_ARGS[@]}" -lt 1 ]]; then',
            '  echo "No inputs found for requeue under $JOB_ROOT (expected shards/ or $MERGED_PATH)" >&2',
            "  exit 2",
            "fi",
            "",
            'PLAN_ARGS=()',
            'if [[ -f "$PLAN" ]]; then',
            '  PLAN_ARGS+=("--plan" "$PLAN")',
            "fi",
            'if [[ "${#PLAN_ARGS[@]}" -lt 1 ]]; then',
            '  echo "Missing plan file: $PLAN" >&2',
            "  exit 2",
            "fi",
            "",
            'cmd=(',
            '  "$PY" "$REQUEUE_SCRIPT"',
            '  "${PLAN_ARGS[@]}"',
            '  "${INPUT_ARGS[@]}"',
            '  "--select" "unresolved"',
            '  "--output-plan" "$OUT_PLAN"',
            '  "--format" "text"',
            ')',
            'if [[ "$#" -gt 0 ]]; then',
            '  cmd+=("$@")',
            "fi",
            "",
            'cd "$REPO_ROOT"',
            '"${cmd[@]}"',
            "",
            'echo "[ok] wrote requeue plan -> $OUT_PLAN"',
            'echo "next: run jobgen with --plan $OUT_PLAN and the same scan args"',
            "",
        ]
    )
    _write_text(script_path, "\n".join(lines), executable=True)
    return script_path


def _emit_rsd_overlay_script(
    *,
    outdir: Path,
    repo_root_fallback: Path,
    python_fallback: str,
    shards_compress: str,
) -> Path:
    script_path = outdir / "rsd_overlay.sh"
    merged_jsonl_name = _default_merged_jsonl_name(str(shards_compress))
    lines: List[str] = ["#!/usr/bin/env bash"]
    lines.extend(_common_shell_prelude(repo_root_fallback=repo_root_fallback, python_fallback=python_fallback))
    lines.extend(
        [
            'PARETO_SCRIPT="$SCRIPTS_ROOT/phase2_e2_pareto_report.py"',
            'PLAN="$JOB_ROOT/plan.json"',
            'DATA_ROOT="$(cd "$SCRIPTS_ROOT/.." && pwd)"',
            'RSD_DATA="${GSC_RSD_DATA:-$DATA_ROOT/data/structure/fsigma8_gold2017_plus_zhao2018.csv}"',
            'RSD_WEIGHT="${GSC_RSD_WEIGHT:-1.0}"',
            'RSD_AP_CORRECTION="${GSC_RSD_AP_CORRECTION:-off}"',
            'RSD_MODE="${GSC_RSD_MODE:-nuisance_sigma8}"',
            f'MERGED_JSONL="${{MERGED_JSONL:-{merged_jsonl_name}}}"',
            'if [[ "$MERGED_JSONL" = /* ]]; then',
            '  MERGED_PATH="$MERGED_JSONL"',
            "else",
            '  MERGED_PATH="$JOB_ROOT/$MERGED_JSONL"',
            "fi",
            'SHARDS="$JOB_ROOT/shards"',
            'TXT_OUT="$JOB_ROOT/pareto_rsd_overlay.txt"',
            'JSON_OUT="$JOB_ROOT/pareto_rsd_overlay.json"',
            'FRONTIER_OUT="$JOB_ROOT/pareto_rsd_overlay_frontier.csv"',
            'TOP_OUT="$JOB_ROOT/pareto_rsd_overlay_top_positive.csv"',
            'REPORT_OUT="$JOB_ROOT/pareto_rsd_overlay_report.md"',
            "",
            'INPUT_ARGS=()',
            'if [[ -f "$MERGED_PATH" ]]; then',
            '  INPUT_ARGS+=("--jsonl" "$MERGED_PATH")',
            'elif [[ -d "$SHARDS" ]]; then',
            '  INPUT_ARGS+=("--jsonl-dir" "$SHARDS")',
            "else",
            '  echo "No inputs found for RSD overlay under $JOB_ROOT (expected $MERGED_PATH or shards/)" >&2',
            "  exit 2",
            "fi",
            "",
            'PLAN_ARGS=()',
            'if [[ -f "$PLAN" ]]; then',
            '  PLAN_ARGS+=("--plan" "$PLAN")',
            "fi",
            "",
            'cmd=(',
            '  "$PY" "$PARETO_SCRIPT"',
            '  "${INPUT_ARGS[@]}"',
            '  "${PLAN_ARGS[@]}"',
            '  "--out-dir" "$JOB_ROOT"',
            '  "--out-summary" "$JSON_OUT"',
            '  "--out-frontier" "$FRONTIER_OUT"',
            '  "--out-top-positive" "$TOP_OUT"',
            '  "--out-report-md" "$REPORT_OUT"',
            '  "--rsd-overlay" "on"',
            '  "--rsd-data" "$RSD_DATA"',
            '  "--rsd-ap-correction" "$RSD_AP_CORRECTION"',
            '  "--rsd-mode" "$RSD_MODE"',
            '  "--rsd-weight" "$RSD_WEIGHT"',
            ')',
            'if [[ "$#" -gt 0 ]]; then',
            '  cmd+=("$@")',
            "fi",
            "",
            'cd "$REPO_ROOT"',
            '"${cmd[@]}" | tee "$TXT_OUT"',
            'echo "[ok] wrote $TXT_OUT"',
            'echo "[ok] wrote $JSON_OUT"',
            "",
        ]
    )
    _write_text(script_path, "\n".join(lines), executable=True)
    return script_path


def _emit_boltzmann_export_script(
    *,
    outdir: Path,
    repo_root_fallback: Path,
    python_fallback: str,
    shards_compress: str,
    created_utc: str,
) -> Path:
    script_path = outdir / "boltzmann_export.sh"
    merged_jsonl_name = _default_merged_jsonl_name(str(shards_compress))
    lines: List[str] = ["#!/usr/bin/env bash"]
    lines.extend(_common_shell_prelude(repo_root_fallback=repo_root_fallback, python_fallback=python_fallback))
    lines.extend(
        [
            'EXPORT_SCRIPT="$SCRIPTS_ROOT/phase2_pt_boltzmann_export_pack.py"',
            'PLAN="$JOB_ROOT/plan.json"',
            f'CREATED_UTC_DEFAULT="{str(created_utc)}"',
            'CREATED_UTC="${GSC_BOLTZMANN_CREATED_UTC:-$CREATED_UTC_DEFAULT}"',
            'RANK_BY="${GSC_RANK_BY:-cmb}"',
            'ELIGIBLE_STATUS="${GSC_ELIGIBLE_STATUS:-ok_only}"',
            'RSD_CHI2_FIELD="${GSC_RSD_CHI2_FIELD:-}"',
            'OUTDIR_RAW="${GSC_BOLTZMANN_OUTDIR:-boltzmann_export_pack}"',
            'ZIP_OUT_RAW="${GSC_BOLTZMANN_ZIP_OUT:-}"',
            'MAX_ZIP_MB="${GSC_BOLTZMANN_MAX_ZIP_MB:-50}"',
            f'MERGED_JSONL="${{MERGED_JSONL:-{merged_jsonl_name}}}"',
            'if [[ "$MERGED_JSONL" = /* ]]; then',
            '  MERGED_PATH="$MERGED_JSONL"',
            "else",
            '  MERGED_PATH="$JOB_ROOT/$MERGED_JSONL"',
            "fi",
            'MERGED_CANDIDATES=("$MERGED_PATH" "$JOB_ROOT/merged.jsonl.gz" "$JOB_ROOT/merged.jsonl")',
            'SELECTED_INPUT=""',
            'for candidate in "${MERGED_CANDIDATES[@]}"; do',
            '  if [[ -f "$candidate" ]]; then',
            '    SELECTED_INPUT="$candidate"',
            "    break",
            "  fi",
            "done",
            "",
            'if [[ "$OUTDIR_RAW" = /* ]]; then',
            '  OUTDIR="$OUTDIR_RAW"',
            "else",
            '  OUTDIR="$JOB_ROOT/$OUTDIR_RAW"',
            "fi",
            "",
            'ZIP_ARGS=()',
            'if [[ -n "$ZIP_OUT_RAW" ]]; then',
            '  if [[ "$ZIP_OUT_RAW" = /* ]]; then',
            '    ZIP_OUT="$ZIP_OUT_RAW"',
            "  else",
            '    ZIP_OUT="$JOB_ROOT/$ZIP_OUT_RAW"',
            "  fi",
            '  ZIP_ARGS+=("--zip-out" "$ZIP_OUT")',
            '  ZIP_ARGS+=("--max-zip-mb" "$MAX_ZIP_MB")',
            "fi",
            "",
            'INPUT_ARGS=()',
            'INPUT_SOURCE="shards:$JOB_ROOT/shards"',
            'if [[ -n "$SELECTED_INPUT" ]]; then',
            '  INPUT_ARGS+=("--input" "$SELECTED_INPUT")',
            '  INPUT_SOURCE="merged:$SELECTED_INPUT"',
            'elif [[ -d "$JOB_ROOT/shards" ]]; then',
            '  INPUT_ARGS+=("--input" "$JOB_ROOT/shards")',
            "else",
            '  echo "No inputs found for boltzmann export under $JOB_ROOT (expected merged.jsonl(.gz) or shards/)" >&2',
            "  exit 2",
            "fi",
            "",
            'case "$RANK_BY" in',
            "  cmb|rsd|joint) ;;",
            '  *) echo "Invalid GSC_RANK_BY=$RANK_BY (allowed: cmb|rsd|joint)" >&2; exit 2 ;;',
            "esac",
            'case "$ELIGIBLE_STATUS" in',
            "  ok_only|any_eligible) ;;",
            '  *) echo "Invalid GSC_ELIGIBLE_STATUS=$ELIGIBLE_STATUS (allowed: ok_only|any_eligible)" >&2; exit 2 ;;',
            "esac",
            "",
            'PLAN_ARGS=()',
            'if [[ -f "$PLAN" ]]; then',
            '  if "$PY" "$EXPORT_SCRIPT" --help 2>/dev/null | grep -q -- "--plan"; then',
            '    PLAN_ARGS+=("--plan" "$PLAN")',
            "  fi",
            "fi",
            "",
            'if [[ -n "$ZIP_OUT_RAW" ]]; then',
            '  ZIP_NOTE="$ZIP_OUT_RAW"',
            "else",
            '  ZIP_NOTE="<none>"',
            "fi",
            'echo "[info] boltzmann_export input=$INPUT_SOURCE rank_by=$RANK_BY eligible_status=$ELIGIBLE_STATUS outdir=$OUTDIR zip_out=$ZIP_NOTE"',
            "",
            'cmd=(',
            '  "$PY" "$EXPORT_SCRIPT"',
            ')',
            'if [[ "${#INPUT_ARGS[@]}" -gt 0 ]]; then',
            '  cmd+=("${INPUT_ARGS[@]}")',
            "fi",
            'if [[ "${#PLAN_ARGS[@]}" -gt 0 ]]; then',
            '  cmd+=("${PLAN_ARGS[@]}")',
            "fi",
            'cmd+=(',
            '  "--rank-by" "$RANK_BY"',
            '  "--eligible-status" "$ELIGIBLE_STATUS"',
            '  "--created-utc" "$CREATED_UTC"',
            '  "--outdir" "$OUTDIR"',
            '  "--format" "text"',
            ')',
            'if [[ -n "$RSD_CHI2_FIELD" ]]; then',
            '  cmd+=("--rsd-chi2-field" "$RSD_CHI2_FIELD")',
            "fi",
            'if [[ "${#ZIP_ARGS[@]}" -gt 0 ]]; then',
            '  cmd+=("${ZIP_ARGS[@]}")',
            "fi",
            'if [[ "$#" -gt 0 ]]; then',
            '  cmd+=("$@")',
            "fi",
            "",
            'cd "$REPO_ROOT"',
            '"${cmd[@]}"',
            'echo "[ok] boltzmann export -> $OUTDIR"',
            "",
        ]
    )
    _write_text(script_path, "\n".join(lines), executable=True)
    return script_path


def _emit_boltzmann_results_script(
    *,
    outdir: Path,
    repo_root_fallback: Path,
    python_fallback: str,
    created_utc: str,
) -> Path:
    script_path = outdir / "boltzmann_results.sh"
    lines: List[str] = ["#!/usr/bin/env bash"]
    lines.extend(_common_shell_prelude(repo_root_fallback=repo_root_fallback, python_fallback=python_fallback))
    lines.extend(
        [
            'RESULTS_SCRIPT="$SCRIPTS_ROOT/phase2_pt_boltzmann_results_pack.py"',
            f'CREATED_UTC_DEFAULT="{str(created_utc)}"',
            'CREATED_UTC="${GSC_BOLTZMANN_RESULTS_CREATED_UTC:-${GSC_BOLTZMANN_CREATED_UTC:-$CREATED_UTC_DEFAULT}}"',
            'CODE="${GSC_BOLTZMANN_RESULTS_CODE:-auto}"',
            'REQUIRE="${GSC_BOLTZMANN_RESULTS_REQUIRE:-none}"',
            'EXPORT_PACK_RAW="${GSC_BOLTZMANN_EXPORT_PACK:-${GSC_BOLTZMANN_OUTDIR:-boltzmann_export_pack}}"',
            'RUN_DIR_RAW="${GSC_BOLTZMANN_RUN_DIR:-${GSC_BOLTZMANN_RESULTS_RUN_DIR:-}}"',
            'OUTDIR_RAW="${GSC_BOLTZMANN_RESULTS_OUTDIR:-boltzmann_results_pack}"',
            'ZIP_OUT_RAW="${GSC_BOLTZMANN_RESULTS_ZIP_OUT:-}"',
            'MAX_ZIP_MB="${GSC_BOLTZMANN_RESULTS_MAX_ZIP_MB:-50}"',
            "",
            'case "$CODE" in',
            "  auto|class|camb) ;;",
            '  *) echo "Invalid GSC_BOLTZMANN_RESULTS_CODE=$CODE (allowed: auto|class|camb)" >&2; exit 2 ;;',
            "esac",
            'case "$REQUIRE" in',
            "  none|any_outputs|tt_spectrum) ;;",
            '  *) echo "Invalid GSC_BOLTZMANN_RESULTS_REQUIRE=$REQUIRE (allowed: none|any_outputs|tt_spectrum)" >&2; exit 2 ;;',
            "esac",
            "",
            'if [[ -z "$RUN_DIR_RAW" ]]; then',
            '  echo "GSC_BOLTZMANN_RUN_DIR (or GSC_BOLTZMANN_RESULTS_RUN_DIR) is required for boltzmann_results.sh" >&2',
            "  exit 2",
            "fi",
            "",
            'if [[ "$EXPORT_PACK_RAW" = /* ]]; then',
            '  EXPORT_PACK="$EXPORT_PACK_RAW"',
            "else",
            '  EXPORT_PACK="$JOB_ROOT/$EXPORT_PACK_RAW"',
            "fi",
            'if [[ "$RUN_DIR_RAW" = /* ]]; then',
            '  RUN_DIR="$RUN_DIR_RAW"',
            "else",
            '  RUN_DIR="$JOB_ROOT/$RUN_DIR_RAW"',
            "fi",
            'if [[ "$OUTDIR_RAW" = /* ]]; then',
            '  OUTDIR="$OUTDIR_RAW"',
            "else",
            '  OUTDIR="$JOB_ROOT/$OUTDIR_RAW"',
            "fi",
            "",
            'if [[ ! -d "$EXPORT_PACK" ]]; then',
            '  echo "Export pack directory not found: $EXPORT_PACK" >&2',
            "  exit 2",
            "fi",
            'if [[ ! -f "$EXPORT_PACK/EXPORT_SUMMARY.json" ]]; then',
            '  echo "Missing required export-pack file: $EXPORT_PACK/EXPORT_SUMMARY.json" >&2',
            "  exit 2",
            "fi",
            'if [[ ! -f "$EXPORT_PACK/CANDIDATE_RECORD.json" ]]; then',
            '  echo "Missing required export-pack file: $EXPORT_PACK/CANDIDATE_RECORD.json" >&2',
            "  exit 2",
            "fi",
            'if [[ ! -d "$RUN_DIR" ]]; then',
            '  echo "External Boltzmann run directory not found: $RUN_DIR" >&2',
            "  exit 2",
            "fi",
            "",
            'ZIP_ARGS=()',
            'if [[ -n "$ZIP_OUT_RAW" ]]; then',
            '  if [[ "$ZIP_OUT_RAW" = /* ]]; then',
            '    ZIP_OUT="$ZIP_OUT_RAW"',
            "  else",
            '    ZIP_OUT="$JOB_ROOT/$ZIP_OUT_RAW"',
            "  fi",
            '  ZIP_ARGS+=("--zip-out" "$ZIP_OUT")',
            '  ZIP_ARGS+=("--max-zip-mb" "$MAX_ZIP_MB")',
            "fi",
            "",
            'if [[ -n "$ZIP_OUT_RAW" ]]; then',
            '  ZIP_NOTE="$ZIP_OUT_RAW"',
            "else",
            '  ZIP_NOTE="<none>"',
            "fi",
            'echo "[info] boltzmann_results export_pack=$EXPORT_PACK run_dir=$RUN_DIR code=$CODE require=$REQUIRE outdir=$OUTDIR zip_out=$ZIP_NOTE"',
            "",
            'cmd=(',
            '  "$PY" "$RESULTS_SCRIPT"',
            '  "--export-pack" "$EXPORT_PACK"',
            '  "--run-dir" "$RUN_DIR"',
            '  "--code" "$CODE"',
            '  "--require" "$REQUIRE"',
            '  "--outdir" "$OUTDIR"',
            '  "--overwrite"',
            '  "--created-utc" "$CREATED_UTC"',
            '  "--format" "text"',
            ')',
            'if [[ "${#ZIP_ARGS[@]}" -gt 0 ]]; then',
            '  cmd+=("${ZIP_ARGS[@]}")',
            "fi",
            'if [[ "$#" -gt 0 ]]; then',
            '  cmd+=("$@")',
            "fi",
            "",
            'cd "$REPO_ROOT"',
            '"${cmd[@]}"',
            'echo "[ok] boltzmann results -> $OUTDIR"',
            "",
        ]
    )
    _write_text(script_path, "\n".join(lines), executable=True)
    return script_path


def _emit_boltzmann_run_script(
    *,
    outdir: Path,
    repo_root_fallback: Path,
    python_fallback: str,
    created_utc: str,
    code: str,
) -> Path:
    code_name = str(code)
    if code_name not in {"class", "camb"}:
        raise SystemExit(f"internal error: unsupported boltzmann run code={code_name!r}")
    script_path = outdir / f"boltzmann_run_{code_name}.sh"
    bin_env = "GSC_CLASS_BIN" if code_name == "class" else "GSC_CAMB_BIN"
    default_out = f"boltzmann_run_{code_name}"
    template_name = (
        "BOLTZMANN_INPUT_TEMPLATE_CLASS.ini"
        if code_name == "class"
        else "BOLTZMANN_INPUT_TEMPLATE_CAMB.ini"
    )
    lines: List[str] = ["#!/usr/bin/env bash"]
    lines.extend(_common_shell_prelude(repo_root_fallback=repo_root_fallback, python_fallback=python_fallback))
    lines.extend(
        [
            'RUN_SCRIPT="$SCRIPTS_ROOT/phase2_pt_boltzmann_run_harness.py"',
            f'CODE="{code_name}"',
            f'CREATED_UTC_DEFAULT="{str(created_utc)}"',
            'CREATED_UTC="${GSC_BOLTZMANN_RESULTS_CREATED_UTC:-${GSC_BOLTZMANN_CREATED_UTC:-$CREATED_UTC_DEFAULT}}"',
            'RUNNER="${GSC_BOLTZMANN_RUNNER:-native}"',
            'EXPORT_PACK_RAW="${GSC_BOLTZMANN_EXPORT_PACK:-${GSC_BOLTZMANN_OUTDIR:-boltzmann_export_pack}}"',
            f'RUN_DIR_RAW="${{GSC_BOLTZMANN_RUN_OUTDIR:-{default_out}}}"',
            f'BIN_RAW="${{{bin_env}:-${{GSC_BOLTZMANN_BIN:-}}}}"',
            "",
            'case "$RUNNER" in',
            "  native|docker) ;;",
            '  *) echo "Invalid GSC_BOLTZMANN_RUNNER=$RUNNER (allowed: native|docker)" >&2; exit 2 ;;',
            "esac",
            "",
            'if [[ "$EXPORT_PACK_RAW" = /* ]]; then',
            '  EXPORT_PACK="$EXPORT_PACK_RAW"',
            "else",
            '  EXPORT_PACK="$JOB_ROOT/$EXPORT_PACK_RAW"',
            "fi",
            'if [[ "$RUN_DIR_RAW" = /* ]]; then',
            '  RUN_DIR="$RUN_DIR_RAW"',
            "else",
            '  RUN_DIR="$JOB_ROOT/$RUN_DIR_RAW"',
            "fi",
            "",
            'if [[ ! -d "$EXPORT_PACK" ]]; then',
            '  echo "Export pack directory not found: $EXPORT_PACK" >&2',
            "  exit 2",
            "fi",
            'if [[ ! -f "$EXPORT_PACK/EXPORT_SUMMARY.json" ]]; then',
            '  echo "Missing required export-pack file: $EXPORT_PACK/EXPORT_SUMMARY.json" >&2',
            "  exit 2",
            "fi",
            'if [[ ! -f "$EXPORT_PACK/CANDIDATE_RECORD.json" ]]; then',
            '  echo "Missing required export-pack file: $EXPORT_PACK/CANDIDATE_RECORD.json" >&2',
            "  exit 2",
            "fi",
            f'if [[ ! -f "$EXPORT_PACK/{template_name}" ]]; then',
            f'  echo "Missing required export-pack file: $EXPORT_PACK/{template_name}" >&2',
            "  exit 2",
            "fi",
            "",
            'if [[ "$RUNNER" == "native" && -z "$BIN_RAW" ]]; then',
            f'  echo "{bin_env} (or GSC_BOLTZMANN_BIN) is required when GSC_BOLTZMANN_RUNNER=native" >&2',
            "  exit 2",
            "fi",
            'if [[ "$RUNNER" == "docker" ]]; then',
            '  if ! command -v docker >/dev/null 2>&1; then',
            '    echo "docker not found in PATH" >&2',
            "    exit 2",
            "  fi",
            "fi",
            "",
            'cmd=(',
            '  "$PY" "$RUN_SCRIPT"',
            '  "--export-pack" "$EXPORT_PACK"',
            '  "--code" "$CODE"',
            '  "--runner" "$RUNNER"',
            '  "--run-dir" "$RUN_DIR"',
            '  "--overwrite"',
            '  "--created-utc" "$CREATED_UTC"',
            '  "--format" "text"',
            ')',
            'if [[ "$RUNNER" == "native" && -n "$BIN_RAW" ]]; then',
            '  cmd+=("--bin" "$BIN_RAW")',
            "fi",
            'if [[ "$#" -gt 0 ]]; then',
            '  cmd+=("$@")',
            "fi",
            "",
            'echo "[info] boltzmann_run code=$CODE runner=$RUNNER export_pack=$EXPORT_PACK run_dir=$RUN_DIR"',
            'cd "$REPO_ROOT"',
            '"${cmd[@]}"',
            'echo "[ok] boltzmann run metadata -> $RUN_DIR/RUN_METADATA.json"',
            "",
        ]
    )
    _write_text(script_path, "\n".join(lines), executable=True)
    return script_path


def _emit_readme(
    *,
    outdir: Path,
    slices: int,
    scheduler: str,
    scan_extra_args: Sequence[str],
    paper_assets_mode: str,
    shards_compress: str,
) -> Path:
    pass_args = " ".join(_bash_quote(str(arg)) for arg in scan_extra_args) or "<none>"
    merged_jsonl_default = _default_merged_jsonl_name(str(shards_compress))
    template_tokens = [
        '"$PY"',
        '"$SCAN_SCRIPT"',
        '"--plan"',
        '"$PLAN"',
        '"--plan-slice"',
        '"<I>/<N>"',
        '"--out-dir"',
        '"$SLICE_OUTDIR"',
        '"--points-jsonl-name"',
        '"' + ("e2_scan_points.jsonl.gz" if str(shards_compress) == "gzip" else "e2_scan_points.jsonl") + '"',
        '"--resume"',
    ]
    template_tokens.extend(_bash_quote(str(arg)) for arg in scan_extra_args)
    cmd_template = " ".join(template_tokens)
    lines = [
        "# Phase-2 E2 Distributed Job Pack",
        "",
        "Generated by `phase2_e2_jobgen.py`.",
        "",
        "## Contents",
        "- `plan.json`: portable copy of input refine plan",
        "- `shards/`: per-slice output directories (`e2_scan_points.jsonl` or `e2_scan_points.jsonl.gz`)",
        "- slice runner scripts (`run_slice_*` or `slurm_array.sbatch`)",
        "- `merge_shards.sh`: deterministic merge to `$MERGED_JSONL`",
        "- `bundle.sh`: build bundle directory with reports + manifest",
        "- `verify.sh`: offline integrity + plan-coverage verification",
        "- `status.sh`: live/instant progress status on shards or merged output",
        "- `watch.sh`: repeat status snapshots on an interval",
        "- `requeue.sh`: emit `plan_requeue.json` for unresolved/missing/error points",
        "- `rsd_overlay.sh`: optional structure-growth sanity overlay (`fσ8` RSD) on Pareto outputs",
        "- `boltzmann_export.sh`: one-command deterministic export pack for external CLASS/CAMB runs",
        "- `boltzmann_run_class.sh`: one-command external CLASS run harness (native/docker)",
        "- `boltzmann_run_camb.sh`: one-command external CAMB run harness (native/docker)",
        "- `boltzmann_results.sh`: one-command deterministic results pack for external CLASS/CAMB outputs",
        "- `jobgen_manifest.json`: generation metadata (SHA256, args, settings)",
        "",
        "## Scan pass-through args",
        f"- `{pass_args}`",
        "",
        "## Scan command template",
        f"- `{cmd_template}`",
        "",
        "## Paper assets",
        f"- mode: `{paper_assets_mode}`",
        "- `bundle.sh` forwards this mode to `phase2_e2_bundle.py --paper-assets ...`",
        "- `verify.sh` enforces `--paper-assets require` when mode is not `none`.",
        "",
        "## Workflow",
        "1. Run all slices (`run_slice_*` scripts or submit `slurm_array.sbatch`).",
        "2. Run `./merge_shards.sh`.",
        "3. Run `./bundle.sh`.",
        "4. Run `./verify.sh`.",
        "5. Run `./status.sh` anytime for progress/coverage summary.",
        "6. Optional: run `./rsd_overlay.sh` for structure-growth sanity diagnostics.",
        "7. Optional: run `./boltzmann_export.sh` to generate a deterministic CLASS/CAMB handoff pack.",
        "8. Optional: run external solver via harness (`./boltzmann_run_class.sh` or `./boltzmann_run_camb.sh`).",
        "9. Optional: after external CLASS/CAMB run, set `GSC_BOLTZMANN_RUN_DIR=/path/to/run_outputs` and run `./boltzmann_results.sh`.",
        "",
        "## Merged output path",
        f"- default: `MERGED_JSONL={merged_jsonl_default}`",
        "- override to plain JSONL if needed: `MERGED_JSONL=merged.jsonl ./merge_shards.sh`",
        "- the same `MERGED_JSONL` override applies to `status.sh`, `bundle.sh`, and `requeue.sh`.",
        "",
        "## Merging large shards (memory-safe)",
        "- `merge_shards.sh` defaults to memory-bounded external-sort merge.",
        "- Tune chunk size with `GSC_MERGE_CHUNK_RECORDS` (default `200000`).",
        "- Override temp workspace with `GSC_MERGE_TMPDIR` (default `$JOB_ROOT/tmp_merge`).",
        "- Keep temporary chunk files for debugging with `GSC_MERGE_KEEP_TMP=1`.",
        "",
        "```bash",
        "./merge_shards.sh",
        "MERGED_JSONL=merged.jsonl ./merge_shards.sh",
        "GSC_MERGE_CHUNK_RECORDS=50000 ./merge_shards.sh",
        "GSC_MERGE_TMPDIR=/scratch/gsc_merge_tmp GSC_MERGE_KEEP_TMP=1 ./merge_shards.sh",
        "```",
        "",
        "## Compressed shards (gzip)",
        f"- configured mode: `{str(shards_compress)}`",
        "- enable at generation time with `--shards-compress gzip`.",
        "- when gzip mode is enabled, per-slice outputs use `e2_scan_points.jsonl.gz`.",
        "- when gzip mode is enabled, merged output defaults to `merged.jsonl.gz`.",
        "- merge and status tools read `.jsonl` and `.jsonl.gz` transparently.",
        "",
        "```bash",
        "gzip -cd shards/slice_*/e2_scan_points.jsonl.gz | head",
        "```",
        "",
        "## Monitoring progress (live)",
        "- To emit per-record RSD proxy fields during scanning, add `--scan-extra-arg --rsd-overlay` when generating this pack.",
        "- For reproducible derived-As overlay campaigns, pin the same RSD model knobs on every slice/shard:",
        "  `--scan-extra-arg --rsd-mode --scan-extra-arg derived_As --scan-extra-arg --rsd-transfer-model --scan-extra-arg eh98_nowiggle --scan-extra-arg --rsd-ns --scan-extra-arg 0.965 --scan-extra-arg --rsd-k-pivot --scan-extra-arg 0.05`.",
        "- Joint objective (CMB+RSD) is opt-in; default scan objective remains CMB-only.",
        "- To run joint objective scans, append literal `--scan-extra-arg` tokens:",
        "  `--scan-extra-arg --rsd-overlay --scan-extra-arg --chi2-objective --scan-extra-arg joint --scan-extra-arg --rsd-chi2-field --scan-extra-arg rsd_chi2_total --scan-extra-arg --rsd-chi2-weight --scan-extra-arg 1.0`.",
        "- Important: keep identical `--scan-extra-arg` RSD knobs across all slices, or merge guardrails can fail on mixed `scan_config_sha256`.",
        "- Live status will then include an `RSD overlay` section automatically.",
        "```bash",
        "./status.sh",
        "./status.sh --by-file",
        "./status.sh --format json --json-out status.json",
        "./watch.sh",
        "./watch.sh 30 --by-file",
        "python3 v11.0.0/scripts/phase2_e2_jobgen.py --plan plan.json --outdir pack --slices 32 --scheduler slurm_array --scan-extra-arg --rsd-overlay --scan-extra-arg --rsd-mode --scan-extra-arg derived_As --scan-extra-arg --rsd-transfer-model --scan-extra-arg eh98_nowiggle --scan-extra-arg --rsd-ns --scan-extra-arg 0.965 --scan-extra-arg --rsd-k-pivot --scan-extra-arg 0.05 -- --model lcdm --toy",
        "```",
        "",
        "## Structure-growth sanity check (RSD fσ8 overlay)",
        "- This is an optional linear-growth overlay on Pareto candidates.",
        "- It is diagnostic-only and not a full perturbation/LSS likelihood fit.",
        "",
        "```bash",
        "./rsd_overlay.sh",
        "GSC_RSD_AP_CORRECTION=on ./rsd_overlay.sh",
        "GSC_RSD_WEIGHT=0.5 ./rsd_overlay.sh --refine-score chi2_combined",
        "```",
        "",
        "## Boltzmann export (perturbations)",
        "- One-command deterministic export pack for external perturbations/Planck spectra tools.",
        "- Generates templates/metadata only; running CLASS/CAMB is outside this repository.",
        "- Scope details: `v11.0.0/docs/perturbations_and_dm_scope.md`.",
        "",
        "Environment knobs:",
        "- `GSC_BOLTZMANN_OUTDIR` (default `boltzmann_export_pack`)",
        "- `GSC_BOLTZMANN_ZIP_OUT` (default empty; set to write deterministic zip)",
        "- `GSC_BOLTZMANN_MAX_ZIP_MB` (default `50`)",
        "- `GSC_RANK_BY` (default `cmb`, allowed `cmb|rsd|joint`)",
        "- `GSC_ELIGIBLE_STATUS` (default `ok_only`, allowed `ok_only|any_eligible`)",
        "- `GSC_RSD_CHI2_FIELD` (optional override for RSD chi2 field)",
        "",
        "```bash",
        "./boltzmann_export.sh",
        "GSC_RANK_BY=joint GSC_BOLTZMANN_ZIP_OUT=boltzmann_export.zip ./boltzmann_export.sh",
        "```",
        "",
        "## Boltzmann results (perturbations)",
        "- One-command deterministic packaging of external CLASS/CAMB outputs.",
        "- This packages external artifacts only; it does not run perturbation solvers.",
        "- Scope details: `v11.0.0/docs/perturbations_and_dm_scope.md`.",
        "",
        "Environment knobs:",
        "- `GSC_BOLTZMANN_RUN_DIR` or `GSC_BOLTZMANN_RESULTS_RUN_DIR` (required external outputs dir)",
        "- `GSC_BOLTZMANN_RESULTS_OUTDIR` (default `boltzmann_results_pack`)",
        "- `GSC_BOLTZMANN_EXPORT_PACK` (default follows `GSC_BOLTZMANN_OUTDIR` or `boltzmann_export_pack`)",
        "- `GSC_BOLTZMANN_RESULTS_CODE` (default `auto`, allowed `auto|class|camb`)",
        "- `GSC_BOLTZMANN_RESULTS_REQUIRE` (default `none`, allowed `none|any_outputs|tt_spectrum`)",
        "- `GSC_BOLTZMANN_RESULTS_ZIP_OUT` (optional deterministic zip output)",
        "- `GSC_BOLTZMANN_RESULTS_MAX_ZIP_MB` (default `50`)",
        "",
        "```bash",
        "GSC_BOLTZMANN_RUN_DIR=/path/to/class_outputs ./boltzmann_results.sh",
        "GSC_BOLTZMANN_RESULTS_REQUIRE=tt_spectrum GSC_BOLTZMANN_RESULTS_ZIP_OUT=boltzmann_results.zip ./boltzmann_results.sh",
        "```",
        "",
        "## Boltzmann run harness (external execution)",
        "- One-command deterministic harness for running external CLASS/CAMB from export-pack templates.",
        "- Supports `GSC_BOLTZMANN_RUNNER=native|docker` with explicit requirement checks.",
        "- Scope details: `v11.0.0/docs/perturbations_and_dm_scope.md`.",
        "",
        "Environment knobs:",
        "- `GSC_BOLTZMANN_RUNNER` (default `native`, allowed `native|docker`)",
        "- `GSC_BOLTZMANN_EXPORT_PACK` (default follows `GSC_BOLTZMANN_OUTDIR` or `boltzmann_export_pack`)",
        "- `GSC_BOLTZMANN_RUN_OUTDIR` (default `boltzmann_run_class` or `boltzmann_run_camb`)",
        "- `GSC_CLASS_BIN` / `GSC_CAMB_BIN` (required for native runner; fallback `GSC_BOLTZMANN_BIN`)",
        "- Docker image overrides: `GSC_CLASS_DOCKER_IMAGE`, `GSC_CAMB_DOCKER_IMAGE`",
        "",
        "```bash",
        "GSC_CLASS_BIN=/path/to/class ./boltzmann_run_class.sh",
        "GSC_CAMB_BIN=/path/to/camb ./boltzmann_run_camb.sh",
        "GSC_BOLTZMANN_RUNNER=docker GSC_CLASS_DOCKER_IMAGE=gsc-class:latest ./boltzmann_run_class.sh",
        "```",
        "",
        "## Requeue / rerun unresolved points",
        "```bash",
        "./requeue.sh",
        "./requeue.sh --select missing",
        "./requeue.sh --select errors --format json --json-out requeue_status.json",
        '"$PY" "$SCRIPTS_ROOT/phase2_e2_requeue_plan.py" --plan "$JOB_ROOT/plan.json" --input "$JOB_ROOT/shards" --select unresolved --output-plan "$JOB_ROOT/plan_requeue.json" --format json --json-out "$JOB_ROOT/requeue_status.json"',
        "```",
        "",
        "## Plan integrity guardrails",
        "- `merge_shards.sh` enforces `--plan-source-policy match_plan` against `plan.json`.",
        "- `merge_shards.sh` enforces `--scan-config-sha-policy require` so mixed run configs fail fast.",
        "- `verify.sh` enforces `--require-plan-source match_plan` on the bundle output.",
        "- `verify.sh` enforces `--require-scan-config-sha 1` for bundle-level provenance checks.",
        "- If shards from different campaigns are mixed, merge/verify fails deterministically.",
        "- Unsafe override (manual, not recommended): use `--plan-source-policy ignore` or `--require-plan-source off` only when you explicitly accept mixed-plan risk.",
        "",
        "## Provenance / scan_config_sha256",
        "- Every scan record includes `scan_config_sha256` for effective non-volatile scan settings.",
        "- `./status.sh` reports `scan_config_sha256` and prints `MIXED_SCAN_CONFIG_SHA256` when mixed inputs are detected.",
        "- Do not merge when mixed scan-config values are reported; isolate shards from one campaign first.",
        "",
        "## Example commands",
    ]
    if scheduler == "bash":
        lines.extend(
            [
                "```bash",
                "./run_slice_000_of_" + f"{slices:0{max(3, len(str(slices)))}d}.sh",
                "# ... run remaining slice scripts ...",
                "./merge_shards.sh",
                "./bundle.sh",
                "./verify.sh",
                "./status.sh",
                "./watch.sh",
                "./requeue.sh",
                "```",
            ]
        )
    else:
        lines.extend(
            [
                "```bash",
                "sbatch slurm_array.sbatch",
                "./merge_shards.sh",
                "./bundle.sh",
                "./verify.sh",
                "./status.sh",
                "./watch.sh",
                "./requeue.sh",
                "```",
            ]
        )
    readme_path = outdir / "README.md"
    _write_text(readme_path, "\n".join(lines) + "\n", executable=False)
    return readme_path


def _scan_slice_counts(*, n_points: int, slices: int) -> List[int]:
    counts = [0 for _ in range(int(slices))]
    for idx in range(int(n_points)):
        counts[int(idx % int(slices))] += 1
    return counts


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv_all = list(argv if argv is not None else sys.argv[1:])
    prefix_args, trailing_scan_extra_args = _split_prefix_and_scan_args(argv_all)
    prefix_args, explicit_scan_extra_args = _extract_scan_extra_args(prefix_args)
    scan_extra_args = list(explicit_scan_extra_args) + list(trailing_scan_extra_args)

    ap = argparse.ArgumentParser(
        prog="phase2_e2_jobgen",
        description="Generate deterministic bash/Slurm job packs for distributed plan-slice E2 scans.",
    )
    ap.add_argument("--plan", required=True, type=Path, help="Input refine plan JSON (phase2_e2_refine_plan_v1).")
    ap.add_argument("--outdir", required=True, type=Path, help="Output directory for generated job pack.")
    ap.add_argument("--slices", required=True, type=int, help="Number of deterministic plan slices (N >= 1).")
    ap.add_argument("--scheduler", choices=["bash", "slurm_array"], default="bash")
    ap.add_argument(
        "--repo-root",
        type=Path,
        default=V101_DIR,
        help="Fallback repository root embedded in generated scripts (default: v11.0.0 root).",
    )
    ap.add_argument("--python", dest="python_exec", type=str, default="python3", help="Fallback Python executable embedded in generated scripts.")
    ap.add_argument("--created-utc", type=str, default=None, help="Optional fixed UTC timestamp for deterministic manifests.")
    ap.add_argument(
        "--scan-extra-arg",
        action="append",
        default=[],
        metavar="ARG",
        help=(
            "Append one literal token to generated phase2_e2_scan.py invocations "
            "(repeatable). For tokens that start with '-', pass each token via a separate "
            "--scan-extra-arg occurrence."
        ),
    )
    ap.add_argument(
        "--paper-assets",
        choices=["none", "data", "snippets"],
        default="none",
        help="Forward paper-assets mode into generated bundle/verify scripts.",
    )
    ap.add_argument(
        "--shards-compress",
        choices=["none", "gzip"],
        default="none",
        help="Per-slice shard output compression mode (default: none).",
    )
    ap.add_argument("--force", action="store_true", help="Allow writing into an existing non-empty output directory.")
    args = ap.parse_args(prefix_args)

    if int(args.slices) < 1:
        raise SystemExit("--slices must be >= 1")
    scan_extra_args.extend(str(token) for token in (args.scan_extra_arg or []))
    _validate_scan_extra_args(scan_extra_args)

    outdir = args.outdir.expanduser().resolve()
    if outdir.exists():
        if outdir.is_file():
            raise SystemExit(f"--outdir points to a file: {outdir}")
        has_content = any(outdir.iterdir())
        if has_content and not bool(args.force):
            raise SystemExit(f"--outdir exists and is not empty (use --force): {outdir}")
    else:
        outdir.mkdir(parents=True, exist_ok=True)

    plan_path = args.plan.expanduser().resolve()
    try:
        plan_payload = load_refine_plan_v1(plan_path)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    point_ids: List[str] = []
    for point_id, _, _ in iter_plan_points(plan_payload):
        point_ids.append(str(point_id))
    if not point_ids:
        raise SystemExit("Refine plan has no points")
    counts: Dict[str, int] = {}
    for pid in point_ids:
        counts[pid] = int(counts.get(pid, 0) + 1)
    dupes = sorted(pid for pid, count in counts.items() if int(count) > 1)
    if dupes:
        raise SystemExit(f"Refine plan has duplicate point IDs: {dupes[:5]}")

    created_utc = _normalize_created_utc(args.created_utc)
    repo_root_fallback = _resolve_repo_root(args.repo_root)

    plan_copy = outdir / "plan.json"
    write_refine_plan_v1(plan_copy, plan_payload)
    plan_sha256 = _sha256_file(plan_copy)

    (outdir / "shards").mkdir(parents=True, exist_ok=True)
    generated_script_paths: List[Path] = []

    width = max(3, len(str(int(args.slices))))
    if str(args.scheduler) == "bash":
        for i in range(int(args.slices)):
            generated_script_paths.append(
                _emit_bash_slice_script(
                    outdir=outdir,
                    index=i,
                    total=int(args.slices),
                    width=width,
                    repo_root_fallback=repo_root_fallback,
                    python_fallback=str(args.python_exec),
                    scan_extra_args=scan_extra_args,
                    shards_compress=str(args.shards_compress),
                )
            )
    else:
        generated_script_paths.append(
            _emit_slurm_array_script(
                outdir=outdir,
                total=int(args.slices),
                width=width,
                repo_root_fallback=repo_root_fallback,
                python_fallback=str(args.python_exec),
                scan_extra_args=scan_extra_args,
                shards_compress=str(args.shards_compress),
            )
        )

    merge_script = _emit_merge_script(
        outdir=outdir,
        repo_root_fallback=repo_root_fallback,
        python_fallback=str(args.python_exec),
        shards_compress=str(args.shards_compress),
    )
    bundle_script = _emit_bundle_script(
        outdir=outdir,
        repo_root_fallback=repo_root_fallback,
        python_fallback=str(args.python_exec),
        paper_assets_mode=str(args.paper_assets),
        shards_compress=str(args.shards_compress),
    )
    verify_script = _emit_verify_script(
        outdir=outdir,
        repo_root_fallback=repo_root_fallback,
        python_fallback=str(args.python_exec),
        paper_assets_mode=str(args.paper_assets),
    )
    status_script = _emit_status_script(
        outdir=outdir,
        repo_root_fallback=repo_root_fallback,
        python_fallback=str(args.python_exec),
        shards_compress=str(args.shards_compress),
    )
    watch_script = _emit_watch_script(
        outdir=outdir,
        repo_root_fallback=repo_root_fallback,
        python_fallback=str(args.python_exec),
    )
    requeue_script = _emit_requeue_script(
        outdir=outdir,
        repo_root_fallback=repo_root_fallback,
        python_fallback=str(args.python_exec),
        shards_compress=str(args.shards_compress),
    )
    rsd_overlay_script = _emit_rsd_overlay_script(
        outdir=outdir,
        repo_root_fallback=repo_root_fallback,
        python_fallback=str(args.python_exec),
        shards_compress=str(args.shards_compress),
    )
    boltzmann_export_script = _emit_boltzmann_export_script(
        outdir=outdir,
        repo_root_fallback=repo_root_fallback,
        python_fallback=str(args.python_exec),
        shards_compress=str(args.shards_compress),
        created_utc=created_utc,
    )
    boltzmann_results_script = _emit_boltzmann_results_script(
        outdir=outdir,
        repo_root_fallback=repo_root_fallback,
        python_fallback=str(args.python_exec),
        created_utc=created_utc,
    )
    boltzmann_run_class_script = _emit_boltzmann_run_script(
        outdir=outdir,
        repo_root_fallback=repo_root_fallback,
        python_fallback=str(args.python_exec),
        created_utc=created_utc,
        code="class",
    )
    boltzmann_run_camb_script = _emit_boltzmann_run_script(
        outdir=outdir,
        repo_root_fallback=repo_root_fallback,
        python_fallback=str(args.python_exec),
        created_utc=created_utc,
        code="camb",
    )
    readme = _emit_readme(
        outdir=outdir,
        slices=int(args.slices),
        scheduler=str(args.scheduler),
        scan_extra_args=scan_extra_args,
        paper_assets_mode=str(args.paper_assets),
        shards_compress=str(args.shards_compress),
    )

    generated_script_paths.extend(
        [
            merge_script,
            bundle_script,
            verify_script,
            status_script,
            watch_script,
            requeue_script,
            rsd_overlay_script,
            boltzmann_export_script,
            boltzmann_run_class_script,
            boltzmann_run_camb_script,
            boltzmann_results_script,
        ]
    )

    manifest_path = outdir / "jobgen_manifest.json"
    file_entries: List[Dict[str, Any]] = []
    for path in sorted([plan_copy, readme, manifest_path, *generated_script_paths], key=lambda p: str(p)):
        if path == manifest_path:
            continue
        file_entries.append(
            {
                "path": str(path.relative_to(outdir)),
                "sha256": _sha256_file(path),
                "bytes": int(path.stat().st_size),
            }
        )

    manifest_payload: Dict[str, Any] = {
        "schema": _SCHEMA,
        "created_utc": created_utc,
        "repo_root_fallback": str(repo_root_fallback),
        "python_fallback": str(args.python_exec),
        "plan_filename": "plan.json",
        "plan_sha256": plan_sha256,
        "plan_source_sha256": str(get_plan_source_sha256(plan_payload)),
        "slices_n": int(args.slices),
        "scheduler": str(args.scheduler),
        "scan_extra_args": [str(arg) for arg in scan_extra_args],
        "paper_assets_mode": str(args.paper_assets),
        "shards_compress": str(args.shards_compress),
        "shard_points_filename": (
            "e2_scan_points.jsonl.gz" if str(args.shards_compress) == "gzip" else "e2_scan_points.jsonl"
        ),
        "merged_jsonl_default": _default_merged_jsonl_name(str(args.shards_compress)),
        "generator_version": "phase2_m43",
        "git_sha": _git_sha(repo_root_fallback),
        "plan_points_total": int(len(point_ids)),
        "slice_point_counts": _scan_slice_counts(n_points=len(point_ids), slices=int(args.slices)),
        "generated_files": file_entries,
    }
    _write_text(manifest_path, _canonical_json(manifest_payload), executable=False)

    summary = {
        "ok": True,
        "schema": _SCHEMA,
        "outdir": str(outdir),
        "slices_n": int(args.slices),
        "scheduler": str(args.scheduler),
        "plan_points_total": int(len(point_ids)),
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

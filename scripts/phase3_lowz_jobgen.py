#!/usr/bin/env python3
"""Generate deterministic Phase-3 low-z joint scan job packs (bash/slurm)."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]

TOOL = "phase3_lowz_jobgen"
SCHEMA = "phase3_lowz_job_pack_manifest_v1"
PLAN_SCHEMA = "phase3_sigmatensor_lowz_scan_plan_v1"
DEFAULT_CREATED_UTC = "2000-01-01T00:00:00Z"
CREATED_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
ABS_WIN_RE = re.compile(r"^[A-Za-z]:\\")
ABS_TOKENS = ("/Users/", "/home/", "/var/folders/", "C:\\Users\\")

SCAN_SCRIPT_NAME = "phase3_scan_sigmatensor_lowz_joint.py"
SCAN_SCRIPT = ROOT / "scripts" / SCAN_SCRIPT_NAME
MERGE_SCRIPT_NAME = "phase2_e2_merge_jsonl.py"
ANALYZE_SCRIPT_NAME = "phase3_analyze_sigmatensor_lowz_scan.py"
DOSSIER_SCRIPT_NAME = "phase3_make_sigmatensor_candidate_dossier_pack.py"


class UsageError(Exception):
    """Usage/configuration error (exit 1)."""


def _normalize_created_utc(raw: str) -> str:
    text = str(raw or "").strip()
    if not CREATED_UTC_RE.match(text):
        raise UsageError("--created-utc must match YYYY-MM-DDTHH:MM:SSZ")
    try:
        parsed = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise UsageError("--created-utc must match YYYY-MM-DDTHH:MM:SSZ") from exc
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def _json_pretty(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_text(path: Path, text: str, *, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if executable:
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _sanitize_error(text: str) -> str:
    out = " ".join(str(text or "").split())
    out = out.replace(str(ROOT.resolve()), ".")
    out = out.replace(str(ROOT.parent.resolve()), ".")
    for token in ABS_TOKENS:
        out = out.replace(token, "[abs]/")
    if len(out) > 600:
        return out[:600]
    return out


def _bash_quote(value: str) -> str:
    return shlex.quote(str(value))


def _shell_array(items: Sequence[str]) -> str:
    if not items:
        return "()"
    return "(" + " ".join(_bash_quote(x) for x in items) + ")"


def _validate_joint_extra_args(values: Sequence[str]) -> List[str]:
    out: List[str] = []
    for raw in values:
        token = str(raw)
        if not token:
            continue
        if token.startswith("/") or ABS_WIN_RE.match(token):
            raise UsageError(f"--joint-extra-arg must not be an absolute-path token: {token}")
        for bad in ABS_TOKENS:
            if bad in token:
                raise UsageError(f"--joint-extra-arg must not contain absolute-path marker {bad!r}: {token}")
        out.append(token)
    return out


def _normalize_argv(argv: Sequence[str]) -> List[str]:
    tokens = list(argv)
    out: List[str] = []
    i = 0
    while i < len(tokens):
        t = str(tokens[i])
        if t == "--joint-extra-arg":
            if i + 1 >= len(tokens):
                raise UsageError("--joint-extra-arg requires one literal token")
            out.append(f"--joint-extra-arg={tokens[i + 1]}")
            i += 2
            continue
        out.append(t)
        i += 1
    return out


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Deterministic job pack generator for Phase-3 low-z joint scan workflow.")
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--slices", type=int, required=True)

    ap.add_argument("--plan", type=Path, default=None)
    ap.add_argument("--H0-km-s-Mpc", dest="H0_km_s_Mpc", type=float, default=None)
    ap.add_argument("--Tcmb-K", dest="Tcmb_K", type=float, default=2.7255)
    ap.add_argument("--N-eff", dest="N_eff", type=float, default=3.046)
    ap.add_argument("--Omega-r0-override", dest="Omega_r0_override", type=float, default=None)
    ap.add_argument("--sign-u0", dest="sign_u0", type=int, choices=(-1, +1), default=+1)

    ap.add_argument("--Omega-m-min", dest="Omega_m_min", type=float, default=None)
    ap.add_argument("--Omega-m-max", dest="Omega_m_max", type=float, default=None)
    ap.add_argument("--Omega-m-steps", dest="Omega_m_steps", type=int, default=None)
    ap.add_argument("--w0-min", dest="w0_min", type=float, default=None)
    ap.add_argument("--w0-max", dest="w0_max", type=float, default=None)
    ap.add_argument("--w0-steps", dest="w0_steps", type=int, default=None)
    ap.add_argument("--lambda-min", dest="lambda_min", type=float, default=None)
    ap.add_argument("--lambda-max", dest="lambda_max", type=float, default=None)
    ap.add_argument("--lambda-steps", dest="lambda_steps", type=int, default=None)

    ap.add_argument("--scheduler", choices=("bash", "slurm_array"), default="bash")
    ap.add_argument("--shards-compress", choices=("none", "gzip"), default="gzip")
    ap.add_argument("--created-utc", default=DEFAULT_CREATED_UTC)
    ap.add_argument("--joint-extra-arg", action="append", default=[])
    ap.add_argument("--analysis-top-k", type=int, default=10)
    ap.add_argument("--analysis-metric", choices=("chi2_total", "delta_chi2_total"), default="chi2_total")
    ap.add_argument("--force", action="store_true")

    raw = list(sys.argv[1:] if argv is None else list(argv))
    args = ap.parse_args(_normalize_argv(raw))

    if int(args.slices) < 1:
        raise UsageError("--slices must be >= 1")
    if int(args.analysis_top_k) < 1:
        raise UsageError("--analysis-top-k must be >= 1")

    created_utc = _normalize_created_utc(str(args.created_utc))
    setattr(args, "created_utc", created_utc)
    setattr(args, "joint_extra_arg", _validate_joint_extra_args(list(args.joint_extra_arg or [])))

    has_plan = args.plan is not None
    grid_fields = (
        args.H0_km_s_Mpc,
        args.Omega_m_min,
        args.Omega_m_max,
        args.Omega_m_steps,
        args.w0_min,
        args.w0_max,
        args.w0_steps,
        args.lambda_min,
        args.lambda_max,
        args.lambda_steps,
    )
    has_any_grid = any(x is not None for x in grid_fields)

    if has_plan and has_any_grid:
        raise UsageError("use exactly one plan mode: --plan OR grid-spec args")
    if not has_plan and not has_any_grid:
        raise UsageError("missing plan mode: provide --plan OR required grid-spec args")
    if not has_plan:
        required_names = (
            "H0_km_s_Mpc",
            "Omega_m_min",
            "Omega_m_max",
            "Omega_m_steps",
            "w0_min",
            "w0_max",
            "w0_steps",
            "lambda_min",
            "lambda_max",
            "lambda_steps",
        )
        for name in required_names:
            if getattr(args, name) is None:
                raise UsageError(f"grid-spec mode requires --{name.replace('_', '-')}")
        if int(args.Omega_m_steps) < 1 or int(args.w0_steps) < 1 or int(args.lambda_steps) < 1:
            raise UsageError("grid steps must be >= 1")

    return args


def _validate_plan_payload(payload: Mapping[str, Any]) -> None:
    schema = str(payload.get("schema") or "")
    if schema != PLAN_SCHEMA:
        raise UsageError(f"plan schema mismatch: expected {PLAN_SCHEMA}, got {schema or 'missing'}")
    points = payload.get("points")
    if not isinstance(points, list):
        raise UsageError("plan JSON missing points list")


def _prepare_outdir(path: Path, *, force: bool) -> Path:
    outdir = path.expanduser().resolve()
    if outdir.exists():
        if not outdir.is_dir():
            raise UsageError(f"--outdir exists and is not a directory: {outdir}")
        if any(outdir.iterdir()):
            if not force:
                raise UsageError("--outdir must be empty (or pass --force)")
            shutil.rmtree(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    return outdir


def _load_plan(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise UsageError(f"failed to parse plan JSON: {path}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise UsageError("plan JSON root must be an object")
    _validate_plan_payload(payload)
    return payload


def _write_plan_from_input(src: Path, dst: Path) -> Mapping[str, Any]:
    src_path = src.expanduser().resolve()
    if not src_path.is_file():
        raise UsageError(f"--plan file not found: {src_path}")
    payload = _load_plan(src_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(src_path.read_bytes())
    return payload


def _generate_plan_with_scan_tool(args: argparse.Namespace, dst: Path) -> Mapping[str, Any]:
    if not SCAN_SCRIPT.is_file():
        raise UsageError(f"missing scan tool script: {SCAN_SCRIPT}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd: List[str] = [
        sys.executable,
        str(SCAN_SCRIPT),
        "--plan-out",
        str(dst),
        "--created-utc",
        str(args.created_utc),
        "--H0-km-s-Mpc",
        f"{float(args.H0_km_s_Mpc):.17g}",
        "--Omega-m-min",
        f"{float(args.Omega_m_min):.17g}",
        "--Omega-m-max",
        f"{float(args.Omega_m_max):.17g}",
        "--Omega-m-steps",
        str(int(args.Omega_m_steps)),
        "--w0-min",
        f"{float(args.w0_min):.17g}",
        "--w0-max",
        f"{float(args.w0_max):.17g}",
        "--w0-steps",
        str(int(args.w0_steps)),
        "--lambda-min",
        f"{float(args.lambda_min):.17g}",
        "--lambda-max",
        f"{float(args.lambda_max):.17g}",
        "--lambda-steps",
        str(int(args.lambda_steps)),
        "--Tcmb-K",
        f"{float(args.Tcmb_K):.17g}",
        "--N-eff",
        f"{float(args.N_eff):.17g}",
        "--sign-u0",
        str(int(args.sign_u0)),
        "--format",
        "text",
    ]
    if args.Omega_r0_override is not None:
        cmd.extend(["--Omega-r0-override", f"{float(args.Omega_r0_override):.17g}"])

    proc = subprocess.run(cmd, cwd=str(ROOT.parent), text=True, capture_output=True)
    if int(proc.returncode) != 0:
        msg = _sanitize_error(proc.stderr if (proc.stderr or "").strip() else (proc.stdout or ""))
        raise UsageError(f"plan generation via {SCAN_SCRIPT_NAME} failed: {msg}")
    payload = _load_plan(dst)
    return payload


def _slice_width(n: int) -> int:
    return max(2, len(str(int(n))))


def _slice_labels(index: int, total: int) -> Tuple[str, str]:
    width = _slice_width(total)
    return (f"{int(index):0{width}d}", f"{int(total):0{width}d}")


def _joint_extra_flag_tokens(values: Sequence[str]) -> List[str]:
    return [f"--joint-extra-arg={v}" for v in values]


def _common_shell_prelude() -> List[str]:
    return [
        "set -euo pipefail",
        "",
        'JOB_ROOT="$(cd "$(dirname "$0")" && pwd)"',
        'PY="${GSC_PYTHON:-python3}"',
        'REPO_ROOT="${GSC_REPO_ROOT:-}"',
        'if [[ -z "$REPO_ROOT" ]]; then',
        f'  if [[ -f "$JOB_ROOT/scripts/{SCAN_SCRIPT_NAME}" ]] || [[ -f "$JOB_ROOT/v11.0.0/scripts/{SCAN_SCRIPT_NAME}" ]]; then',
        '    REPO_ROOT="$JOB_ROOT"',
        f'  elif [[ -f "$JOB_ROOT/../scripts/{SCAN_SCRIPT_NAME}" ]] || [[ -f "$JOB_ROOT/../v11.0.0/scripts/{SCAN_SCRIPT_NAME}" ]]; then',
        '    REPO_ROOT="$(cd "$JOB_ROOT/.." && pwd)"',
        "  else",
        '    echo "Could not resolve REPO_ROOT from JOB_ROOT=$JOB_ROOT. Set GSC_REPO_ROOT." >&2',
        "    exit 2",
        "  fi",
        "fi",
        "",
        f'if [[ -f "$REPO_ROOT/scripts/{SCAN_SCRIPT_NAME}" ]]; then',
        '  SCRIPTS_ROOT="$REPO_ROOT/scripts"',
        f'elif [[ -f "$REPO_ROOT/v11.0.0/scripts/{SCAN_SCRIPT_NAME}" ]]; then',
        '  SCRIPTS_ROOT="$REPO_ROOT/v11.0.0/scripts"',
        "else",
        f'  echo "Could not locate {SCAN_SCRIPT_NAME} under REPO_ROOT=$REPO_ROOT" >&2',
        "  exit 2",
        "fi",
        "",
    ]


def _emit_run_slice_script(
    *,
    outdir: Path,
    index: int,
    slices: int,
    shards_compress: str,
    created_utc: str,
    joint_tokens: Sequence[str],
) -> Path:
    i_label, n_label = _slice_labels(index, slices)
    ext = ".jsonl.gz" if shards_compress == "gzip" else ".jsonl"
    shard_name = f"shard_slice_{i_label}_of_{n_label}{ext}"
    path = outdir / f"run_slice_{i_label}_of_{n_label}.sh"

    lines: List[str] = ["#!/usr/bin/env bash"]
    lines.extend(_common_shell_prelude())
    lines.extend(
        [
            f'CREATED_UTC_DEFAULT="{created_utc}"',
            'CREATED_UTC="${GSC_CREATED_UTC:-$CREATED_UTC_DEFAULT}"',
            f'JOINT_EXTRA_ARGS={_shell_array(joint_tokens)}',
            'SCAN_SCRIPT="$SCRIPTS_ROOT/phase3_scan_sigmatensor_lowz_joint.py"',
            'PLAN_JSON="$JOB_ROOT/plan/LOWZ_SCAN_PLAN.json"',
            f'SHARD_PATH="$JOB_ROOT/shards/{shard_name}"',
            'mkdir -p "$JOB_ROOT/shards"',
            'if [[ ! -f "$PLAN_JSON" ]]; then',
            '  echo "Missing plan file: $PLAN_JSON" >&2',
            '  exit 2',
            'fi',
            'cmd=(',
            '  "$PY" "$SCAN_SCRIPT"',
            '  "--plan" "$PLAN_JSON"',
            '  "--out-jsonl" "$SHARD_PATH"',
            f'  "--plan-slice" "{int(index)}/{int(slices)}"',
            '  "--resume" "1"',
            '  "--created-utc" "$CREATED_UTC"',
            '  "--format" "text"',
            ')',
            'if [[ "${#JOINT_EXTRA_ARGS[@]}" -gt 0 ]]; then',
            '  cmd+=("${JOINT_EXTRA_ARGS[@]}")',
            'fi',
            'cd "$REPO_ROOT"',
            '"${cmd[@]}"',
            'echo "[ok] wrote shard: $SHARD_PATH"',
            '',
        ]
    )
    _write_text(path, "\n".join(lines), executable=True)
    return path


def _emit_run_all_local_script(*, outdir: Path, slices: int) -> Path:
    path = outdir / "run_all_local.sh"
    width = _slice_width(slices)
    lines: List[str] = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        'JOB_ROOT="$(cd "$(dirname "$0")" && pwd)"',
        f'N="{int(slices)}"',
        f'PAD="{int(width)}"',
        'for ((i=0; i<N; i++)); do',
        '  i_label="$(printf "%0${PAD}d" "$i")"',
        '  n_label="$(printf "%0${PAD}d" "$N")"',
        '  script="$JOB_ROOT/run_slice_${i_label}_of_${n_label}.sh"',
        '  if [[ ! -x "$script" ]]; then',
        '    echo "Missing slice script: $script" >&2',
        '    exit 2',
        '  fi',
        '  bash "$script"',
        'done',
        'echo "[ok] all slices completed"',
        '',
    ]
    _write_text(path, "\n".join(lines), executable=True)
    return path


def _emit_slurm_array_script(*, outdir: Path, slices: int) -> Path:
    path = outdir / "slurm_array_job.sh"
    width = _slice_width(slices)
    lines: List[str] = [
        "#!/usr/bin/env bash",
        f"#SBATCH --array=0-{int(slices)-1}",
        "#SBATCH --job-name=gsc_phase3_lowz",
        "#SBATCH --output=slurm_%A_%a.out",
        "#SBATCH --error=slurm_%A_%a.err",
        "",
        "set -euo pipefail",
        "",
        'JOB_ROOT="$(cd "$(dirname "$0")" && pwd)"',
        f'N="{int(slices)}"',
        f'PAD="{int(width)}"',
        'idx="${SLURM_ARRAY_TASK_ID:?SLURM_ARRAY_TASK_ID is required}"',
        'if [[ "$idx" -lt 0 || "$idx" -ge "$N" ]]; then',
        '  echo "SLURM_ARRAY_TASK_ID out of range: idx=$idx N=$N" >&2',
        '  exit 2',
        'fi',
        'i_label="$(printf "%0${PAD}d" "$idx")"',
        'n_label="$(printf "%0${PAD}d" "$N")"',
        'script="$JOB_ROOT/run_slice_${i_label}_of_${n_label}.sh"',
        'if [[ ! -x "$script" ]]; then',
        '  echo "Missing slice script: $script" >&2',
        '  exit 2',
        'fi',
        'bash "$script"',
        '',
    ]
    _write_text(path, "\n".join(lines), executable=True)
    return path


def _emit_merge_script(*, outdir: Path, shards_compress: str) -> Path:
    path = outdir / "merge_shards.sh"
    merged_name = "merged.jsonl.gz" if shards_compress == "gzip" else "merged.jsonl"
    shard_pattern = "shard_slice_*.jsonl.gz" if shards_compress == "gzip" else "shard_slice_*.jsonl"

    lines: List[str] = ["#!/usr/bin/env bash"]
    lines.extend(_common_shell_prelude())
    lines.extend(
        [
            f'SHARD_PATTERN="{shard_pattern}"',
            f'MERGED_JSONL_DEFAULT="{merged_name}"',
            'MERGED_JSONL="${GSC_MERGED_JSONL:-$MERGED_JSONL_DEFAULT}"',
            'if [[ "$MERGED_JSONL" = /* ]]; then',
            '  MERGED_PATH="$MERGED_JSONL"',
            'else',
            '  MERGED_PATH="$JOB_ROOT/merged/$MERGED_JSONL"',
            'fi',
            'mkdir -p "$JOB_ROOT/merged"',
            'SHARDS=()',
            'while IFS= read -r shard_path; do',
            '  SHARDS+=("$shard_path")',
            'done < <(find "$JOB_ROOT/shards" -type f -name "$SHARD_PATTERN" -print | LC_ALL=C sort)',
            'if [[ "${#SHARDS[@]}" -lt 1 ]]; then',
            '  echo "Need at least 1 shard file before merge (found ${#SHARDS[@]})" >&2',
            '  exit 2',
            'fi',
            'PLAN_JSON="$JOB_ROOT/plan/LOWZ_SCAN_PLAN.json"',
            'if [[ ! -f "$PLAN_JSON" ]]; then',
            '  echo "Missing plan file: $PLAN_JSON" >&2',
            '  exit 2',
            'fi',
            f'MERGE_SCRIPT="$SCRIPTS_ROOT/{MERGE_SCRIPT_NAME}"',
            'cmd=(',
            '  "$PY" "$MERGE_SCRIPT"',
            '  "$JOB_ROOT/shards"',
            '  "--out" "$MERGED_PATH"',
            '  "--plan" "$PLAN_JSON"',
            '  "--report-out" "$JOB_ROOT/merged/MERGE_REPORT.json"',
            '  "--dedupe-key" "plan_point_id"',
            '  "--prefer" "ok_then_lowest_chi2"',
            ')',
            'cd "$REPO_ROOT"',
            '"${cmd[@]}"',
            'echo "[ok] merged -> $MERGED_PATH"',
            '',
        ]
    )
    _write_text(path, "\n".join(lines), executable=True)
    return path


def _emit_analyze_script(
    *,
    outdir: Path,
    shards_compress: str,
    created_utc: str,
    analysis_top_k: int,
    analysis_metric: str,
    joint_tokens: Sequence[str],
) -> Path:
    path = outdir / "analyze.sh"
    merged_name = "merged.jsonl.gz" if shards_compress == "gzip" else "merged.jsonl"

    lines: List[str] = ["#!/usr/bin/env bash"]
    lines.extend(_common_shell_prelude())
    lines.extend(
        [
            f'CREATED_UTC_DEFAULT="{created_utc}"',
            'CREATED_UTC="${GSC_CREATED_UTC:-$CREATED_UTC_DEFAULT}"',
            f'ANALYSIS_TOP_K_DEFAULT="{int(analysis_top_k)}"',
            'ANALYSIS_TOP_K="${GSC_ANALYSIS_TOP_K:-$ANALYSIS_TOP_K_DEFAULT}"',
            f'ANALYSIS_METRIC_DEFAULT="{str(analysis_metric)}"',
            'ANALYSIS_METRIC="${GSC_ANALYSIS_METRIC:-$ANALYSIS_METRIC_DEFAULT}"',
            f'JOINT_EXTRA_ARGS={_shell_array(joint_tokens)}',
            f'ANALYZE_SCRIPT="$SCRIPTS_ROOT/{ANALYZE_SCRIPT_NAME}"',
            f'MERGED_PATH="$JOB_ROOT/merged/{merged_name}"',
            'if [[ ! -f "$MERGED_PATH" ]]; then',
            '  echo "Missing merged JSONL: $MERGED_PATH" >&2',
            '  exit 2',
            'fi',
            'mkdir -p "$JOB_ROOT/analysis"',
            'cmd=(',
            '  "$PY" "$ANALYZE_SCRIPT"',
            '  "--inputs" "$MERGED_PATH"',
            '  "--outdir" "$JOB_ROOT/analysis"',
            '  "--top-k" "$ANALYSIS_TOP_K"',
            '  "--metric" "$ANALYSIS_METRIC"',
            '  "--emit-reproduce" "1"',
            '  "--created-utc" "$CREATED_UTC"',
            '  "--format" "text"',
            ')',
            'if [[ "${#JOINT_EXTRA_ARGS[@]}" -gt 0 ]]; then',
            '  cmd+=("${JOINT_EXTRA_ARGS[@]}")',
            'fi',
            'cd "$REPO_ROOT"',
            '"${cmd[@]}"',
            'echo "[ok] analysis -> $JOB_ROOT/analysis/SCAN_ANALYSIS.json"',
            '',
        ]
    )
    _write_text(path, "\n".join(lines), executable=True)
    return path


def _emit_dossier_script(
    *,
    outdir: Path,
    created_utc: str,
    analysis_top_k: int,
    joint_tokens: Sequence[str],
) -> Path:
    path = outdir / "dossier.sh"
    lines: List[str] = ["#!/usr/bin/env bash"]
    lines.extend(_common_shell_prelude())
    lines.extend(
        [
            f'CREATED_UTC_DEFAULT="{created_utc}"',
            'CREATED_UTC="${GSC_CREATED_UTC:-$CREATED_UTC_DEFAULT}"',
            f'DOSSIER_TOP_K_DEFAULT="{int(analysis_top_k)}"',
            'DOSSIER_TOP_K="${GSC_DOSSIER_TOP_K:-$DOSSIER_TOP_K_DEFAULT}"',
            'INCLUDE_CLASS_RUN="${GSC_INCLUDE_CLASS_RUN:-0}"',
            'CLASS_RUNNER="${GSC_CLASS_RUNNER:-native}"',
            'CLASS_BIN="${GSC_CLASS_BIN:-}"',
            'CLASS_DOCKER_IMAGE="${GSC_CLASS_DOCKER_IMAGE:-}"',
            'CLASS_REQUIRE_PINNED="${GSC_CLASS_REQUIRE_PINNED_IMAGE:-0}"',
            'EMIT_QUICKLOOK="${GSC_EMIT_QUICKLOOK:-1}"',
            f'JOINT_EXTRA_ARGS={_shell_array(joint_tokens)}',
            f'DOSSIER_SCRIPT="$SCRIPTS_ROOT/{DOSSIER_SCRIPT_NAME}"',
            'ANALYSIS_JSON="$JOB_ROOT/analysis/SCAN_ANALYSIS.json"',
            'if [[ ! -f "$ANALYSIS_JSON" ]]; then',
            '  echo "Missing analysis JSON: $ANALYSIS_JSON" >&2',
            '  exit 2',
            'fi',
            'cmd=(',
            '  "$PY" "$DOSSIER_SCRIPT"',
            '  "--analysis" "$ANALYSIS_JSON"',
            '  "--outdir" "$JOB_ROOT/dossier"',
            '  "--top-k" "$DOSSIER_TOP_K"',
            '  "--include-class-run" "$INCLUDE_CLASS_RUN"',
            '  "--class-runner" "$CLASS_RUNNER"',
            '  "--class-require-pinned-image" "$CLASS_REQUIRE_PINNED"',
            '  "--emit-quicklook" "$EMIT_QUICKLOOK"',
            '  "--created-utc" "$CREATED_UTC"',
            '  "--format" "text"',
            ')',
            'if [[ -n "$CLASS_BIN" ]]; then',
            '  cmd+=("--class-bin" "$CLASS_BIN")',
            'fi',
            'if [[ -n "$CLASS_DOCKER_IMAGE" ]]; then',
            '  cmd+=("--class-docker-image" "$CLASS_DOCKER_IMAGE")',
            'fi',
            'if [[ "${#JOINT_EXTRA_ARGS[@]}" -gt 0 ]]; then',
            '  cmd+=("${JOINT_EXTRA_ARGS[@]}")',
            'fi',
            'cd "$REPO_ROOT"',
            '"${cmd[@]}"',
            'echo "[ok] dossier -> $JOB_ROOT/dossier"',
            '',
        ]
    )
    _write_text(path, "\n".join(lines), executable=True)
    return path


def _emit_status_script(*, outdir: Path, shards_compress: str) -> Path:
    path = outdir / "status.sh"
    shard_pattern = "shard_slice_*.jsonl.gz" if shards_compress == "gzip" else "shard_slice_*.jsonl"
    merged_name = "merged.jsonl.gz" if shards_compress == "gzip" else "merged.jsonl"
    lines: List[str] = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        'JOB_ROOT="$(cd "$(dirname "$0")" && pwd)"',
        f'SHARD_PATTERN="{shard_pattern}"',
        f'MERGED_PATH="$JOB_ROOT/merged/{merged_name}"',
        'PLAN_PATH="$JOB_ROOT/plan/LOWZ_SCAN_PLAN.json"',
        'ANALYSIS_PATH="$JOB_ROOT/analysis/SCAN_ANALYSIS.json"',
        'DOSSIER_QUICKLOOK_PATH="$JOB_ROOT/dossier/DOSSIER_QUICKLOOK.json"',
        'shard_count="$(find "$JOB_ROOT/shards" -type f -name "$SHARD_PATTERN" -print 2>/dev/null | wc -l | tr -d " ")"',
        'echo "job_root=$JOB_ROOT"',
        'echo "plan_exists=$([[ -f "$PLAN_PATH" ]] && echo 1 || echo 0)"',
        'echo "shard_count=$shard_count"',
        'echo "merged_exists=$([[ -f "$MERGED_PATH" ]] && echo 1 || echo 0)"',
        'echo "analysis_exists=$([[ -f "$ANALYSIS_PATH" ]] && echo 1 || echo 0)"',
        'echo "dossier_quicklook_exists=$([[ -f "$DOSSIER_QUICKLOOK_PATH" ]] && echo 1 || echo 0)"',
        '',
    ]
    _write_text(path, "\n".join(lines), executable=True)
    return path


def _emit_readme(
    *,
    outdir: Path,
    slices: int,
    scheduler: str,
    shards_compress: str,
    created_utc: str,
    analysis_top_k: int,
    analysis_metric: str,
    has_joint_args: bool,
) -> Path:
    lines: List[str] = []
    lines.append("# Phase-3 low-z joint scan job pack")
    lines.append("")
    lines.append("Deterministic orchestration pack for:")
    lines.append("plan -> run slices -> merge shards -> analyze -> dossier")
    lines.append("")
    lines.append("Scope boundary: job orchestration only (no physics/model semantics changes).")
    lines.append("")
    lines.append("## Pack parameters")
    lines.append("")
    lines.append(f"- created_utc: `{created_utc}`")
    lines.append(f"- slices: `{int(slices)}`")
    lines.append(f"- scheduler: `{scheduler}`")
    lines.append(f"- shards_compress: `{shards_compress}`")
    lines.append(f"- analysis_top_k: `{int(analysis_top_k)}`")
    lines.append(f"- analysis_metric: `{analysis_metric}`")
    lines.append(f"- joint_extra_args_present: `{bool(has_joint_args)}`")
    lines.append("")
    lines.append("## Directory layout")
    lines.append("")
    lines.append("- `plan/LOWZ_SCAN_PLAN.json`")
    lines.append("- `shards/`")
    lines.append("- `merged/merged.jsonl[.gz]` + `merged/MERGE_REPORT.json`")
    lines.append("- `analysis/SCAN_ANALYSIS.json`")
    lines.append("- `dossier/` (includes quicklook by default)")
    lines.append("")
    lines.append("## Runtime overrides")
    lines.append("")
    lines.append("- `GSC_REPO_ROOT`: explicit repo root (optional)")
    lines.append("- `GSC_PYTHON`: python executable (optional)")
    lines.append("- `GSC_CREATED_UTC`: override created_utc used by scripts")
    lines.append("")
    lines.append("Dossier class-run toggles:")
    lines.append("")
    lines.append("- `GSC_INCLUDE_CLASS_RUN=1`")
    lines.append("- `GSC_CLASS_RUNNER=native|docker`")
    lines.append("- `GSC_CLASS_BIN=<path>` (optional, native)")
    lines.append("- `GSC_CLASS_DOCKER_IMAGE=<ref>` (optional, docker)")
    lines.append("- `GSC_CLASS_REQUIRE_PINNED_IMAGE=0|1` (optional)")
    lines.append("- `GSC_EMIT_QUICKLOOK=0|1` (default `1`)")
    lines.append("")
    lines.append("## Local execution")
    lines.append("")
    lines.append("```bash")
    lines.append("bash ./run_all_local.sh")
    lines.append("bash ./merge_shards.sh")
    lines.append("bash ./analyze.sh")
    lines.append("bash ./dossier.sh")
    lines.append("bash ./status.sh")
    lines.append("```")
    lines.append("")
    lines.append("## Slurm array")
    lines.append("")
    if scheduler == "slurm_array":
        lines.append("```bash")
        lines.append("sbatch ./slurm_array_job.sh")
        lines.append("bash ./merge_shards.sh")
        lines.append("bash ./analyze.sh")
        lines.append("bash ./dossier.sh")
        lines.append("```")
    else:
        lines.append("Scheduler mode is `bash`; `slurm_array_job.sh` was not generated.")
    lines.append("")
    lines.append("All generated scripts are portable by default and avoid embedded host-specific absolute paths.")
    lines.append("")

    path = outdir / "README.md"
    _write_text(path, "\n".join(lines))
    return path


def _build_manifest(
    *,
    outdir: Path,
    created_utc: str,
    slices: int,
    scheduler: str,
    shards_compress: str,
    plan_path: Path,
    plan_payload: Mapping[str, Any],
    joint_extra_args: Sequence[str],
    analysis_top_k: int,
    analysis_metric: str,
    generated_files: Sequence[Path],
) -> Dict[str, Any]:
    scripts_meta: List[Dict[str, str]] = []
    for path in sorted(generated_files, key=lambda p: p.name):
        scripts_meta.append({"basename": path.name, "sha256": _sha256_file(path)})

    plan_source_sha = str(plan_payload.get("plan_source_sha256") or "")
    manifest: Dict[str, Any] = {
        "schema": SCHEMA,
        "tool": TOOL,
        "created_utc": str(created_utc),
        "slices": int(slices),
        "scheduler": str(scheduler),
        "shards_compress": str(shards_compress),
        "plan": {
            "basename": str(plan_path.name),
            "sha256": _sha256_file(plan_path),
            "schema": str(plan_payload.get("schema") or ""),
            "plan_source_sha256": plan_source_sha,
        },
        "analysis": {
            "top_k": int(analysis_top_k),
            "metric": str(analysis_metric),
        },
        "joint_extra_args": [str(x) for x in joint_extra_args],
        "scripts": scripts_meta,
    }
    return manifest


def _emit_pack(args: argparse.Namespace) -> Path:
    outdir = _prepare_outdir(Path(args.outdir), force=bool(args.force))
    plan_dir = outdir / "plan"
    plan_path = plan_dir / "LOWZ_SCAN_PLAN.json"

    if args.plan is not None:
        plan_payload = _write_plan_from_input(Path(args.plan), plan_path)
    else:
        plan_payload = _generate_plan_with_scan_tool(args, plan_path)

    _validate_plan_payload(plan_payload)

    joint_tokens = _joint_extra_flag_tokens(list(args.joint_extra_arg or []))

    generated_scripts: List[Path] = []
    for idx in range(int(args.slices)):
        generated_scripts.append(
            _emit_run_slice_script(
                outdir=outdir,
                index=idx,
                slices=int(args.slices),
                shards_compress=str(args.shards_compress),
                created_utc=str(args.created_utc),
                joint_tokens=joint_tokens,
            )
        )

    generated_scripts.append(_emit_run_all_local_script(outdir=outdir, slices=int(args.slices)))
    if str(args.scheduler) == "slurm_array":
        generated_scripts.append(_emit_slurm_array_script(outdir=outdir, slices=int(args.slices)))

    generated_scripts.append(_emit_merge_script(outdir=outdir, shards_compress=str(args.shards_compress)))
    generated_scripts.append(
        _emit_analyze_script(
            outdir=outdir,
            shards_compress=str(args.shards_compress),
            created_utc=str(args.created_utc),
            analysis_top_k=int(args.analysis_top_k),
            analysis_metric=str(args.analysis_metric),
            joint_tokens=joint_tokens,
        )
    )
    generated_scripts.append(
        _emit_dossier_script(
            outdir=outdir,
            created_utc=str(args.created_utc),
            analysis_top_k=int(args.analysis_top_k),
            joint_tokens=joint_tokens,
        )
    )
    generated_scripts.append(_emit_status_script(outdir=outdir, shards_compress=str(args.shards_compress)))

    readme = _emit_readme(
        outdir=outdir,
        slices=int(args.slices),
        scheduler=str(args.scheduler),
        shards_compress=str(args.shards_compress),
        created_utc=str(args.created_utc),
        analysis_top_k=int(args.analysis_top_k),
        analysis_metric=str(args.analysis_metric),
        has_joint_args=bool(joint_tokens),
    )

    manifest = _build_manifest(
        outdir=outdir,
        created_utc=str(args.created_utc),
        slices=int(args.slices),
        scheduler=str(args.scheduler),
        shards_compress=str(args.shards_compress),
        plan_path=plan_path,
        plan_payload=plan_payload,
        joint_extra_args=list(args.joint_extra_arg or []),
        analysis_top_k=int(args.analysis_top_k),
        analysis_metric=str(args.analysis_metric),
        generated_files=[*generated_scripts, readme],
    )
    _write_text(outdir / "PACK_MANIFEST.json", _json_pretty(manifest))
    return outdir


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = _parse_args(argv)
        outdir = _emit_pack(args)
    except UsageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        "job_pack "
        f"outdir={outdir} "
        f"slices={int(args.slices)} "
        f"scheduler={str(args.scheduler)} "
        f"shards_compress={str(args.shards_compress)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

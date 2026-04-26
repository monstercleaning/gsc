#!/usr/bin/env python3
"""Deterministic git-less CosmoFalsify golden demo runner (Phase-4 M142)."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import zipfile
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


TOOL = "phase4_cosmofalsify_demo"
TOOL_VERSION = "m142-v1"
SCHEMA = "phase4_cosmofalsify_demo_report_v1"
DEFAULT_CREATED_UTC_EPOCH = 946684800  # 2000-01-01T00:00:00Z
WORKSPACE_REL = "v11.0.0/out/cosmofalsify_demo_work"
ABS_TOKENS: Tuple[str, ...] = ("/Users/", "/home/", "/var/folders/", "C:\\Users\\")
ABS_WIN_RE = re.compile(r"[A-Za-z]:\\\\[^\s\"']+")
TMP_PATH_RE = re.compile(r"/(?:private/)?tmp/[^\s\"']+")
MAX_EXCERPT_CHARS = 600


class UsageError(Exception):
    """Invalid CLI usage."""


def _json_pretty(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sanitize_text(text: str, *, extra_paths: Sequence[Path] = ()) -> str:
    out = str(text or "")
    for path in extra_paths:
        raw = str(Path(path).resolve()).replace("\\", "/")
        if raw:
            out = out.replace(raw, ".")
    for token in ABS_TOKENS:
        out = out.replace(token, "[abs]/")
    out = TMP_PATH_RE.sub(".", out)
    out = ABS_WIN_RE.sub("[abs]", out)
    out = out.strip()
    if len(out) > MAX_EXCERPT_CHARS:
        return out[:MAX_EXCERPT_CHARS]
    return out


def _tail_excerpt(text: str) -> str:
    value = str(text or "")
    if not value:
        return ""
    lines = value.strip().splitlines()
    if not lines:
        return ""
    snippet = "\n".join(lines[-8:])
    if len(snippet) > MAX_EXCERPT_CHARS:
        snippet = snippet[-MAX_EXCERPT_CHARS:]
    return snippet


def _to_iso_utc(epoch_seconds: int) -> str:
    try:
        dt = datetime.fromtimestamp(int(epoch_seconds), tz=timezone.utc)
    except Exception as exc:  # pragma: no cover - defensive
        raise UsageError("--created-utc must be a valid integer epoch seconds value") from exc
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _rel_to(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return path.name


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _deterministic_zip(
    *,
    source_dir: Path,
    out_zip: Path,
    skip_relpaths: Sequence[str],
) -> List[str]:
    source = source_dir.resolve()
    skip = {str(x).replace("\\", "/") for x in skip_relpaths}
    out_zip_resolved = out_zip.resolve()

    members: List[Tuple[str, Path]] = []
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        if path.resolve() == out_zip_resolved:
            continue
        rel = path.resolve().relative_to(source).as_posix()
        if rel in skip:
            continue
        members.append((rel, path))

    out_zip.parent.mkdir(parents=True, exist_ok=True)
    fixed_dt = (2000, 1, 1, 0, 0, 0)
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel, path in members:
            data = path.read_bytes()
            info = zipfile.ZipInfo(filename=rel, date_time=fixed_dt)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (0o100644 & 0xFFFF) << 16
            zf.writestr(info, data)
    return [rel for rel, _ in members]


def _prepare_outdir(outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    for name in ("work", "artifacts", "cosmofalsify_demo_report.json", "cosmofalsify_demo_report.md"):
        path = outdir / name
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)


def _prepare_workspace(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _run_stage(
    *,
    stage: str,
    argv: Sequence[str],
    cwd: Path,
    redact_paths: Sequence[Path],
) -> Dict[str, Any]:
    proc = subprocess.run(
        [str(x) for x in argv],
        cwd=str(cwd),
        text=True,
        capture_output=True,
    )
    row: Dict[str, Any] = {
        "stage": str(stage),
        "argv": [str(x) for x in argv],
        "returncode": int(proc.returncode),
        "status": "ok" if proc.returncode == 0 else "fail",
    }
    if proc.returncode != 0:
        row["stdout_excerpt"] = _sanitize_text(_tail_excerpt(proc.stdout or ""), extra_paths=redact_paths)
        row["stderr_excerpt"] = _sanitize_text(_tail_excerpt(proc.stderr or ""), extra_paths=redact_paths)
    return row


def _render_md(payload: Mapping[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# CosmoFalsify Demo Report")
    lines.append("")
    lines.append(f"- schema: `{payload.get('schema')}`")
    lines.append(f"- tool: `{payload.get('tool')}`")
    lines.append(f"- tool_version: `{payload.get('tool_version')}`")
    lines.append(f"- created_utc: `{payload.get('created_utc')}`")
    lines.append(f"- status: `{payload.get('status')}`")
    lines.append("")
    lines.append("## Stages")
    lines.append("")
    for row in payload.get("stages", []):
        if not isinstance(row, Mapping):
            continue
        lines.append(f"- `{row.get('stage')}`: status={row.get('status')} returncode={row.get('returncode')}")
    lines.append("")
    artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), Mapping) else {}
    bundle = artifacts.get("bundle_zip") if isinstance(artifacts, Mapping) else {}
    if isinstance(bundle, Mapping):
        lines.append("## Bundle artifact")
        lines.append("")
        lines.append(f"- path: `{bundle.get('path')}`")
        lines.append(f"- sha256: `{bundle.get('sha256')}`")
        lines.append("")
    demo_zip = artifacts.get("demo_pack_zip") if isinstance(artifacts, Mapping) else None
    if isinstance(demo_zip, Mapping):
        lines.append("## Demo pack zip")
        lines.append("")
        lines.append(f"- path: `{demo_zip.get('path')}`")
        lines.append(f"- sha256: `{demo_zip.get('sha256')}`")
        lines.append("")
    lines.append("Success means all stages report `status=ok` and verify-after-paper-assets passed.")
    lines.append("")
    return "\n".join(lines)


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Run deterministic Phase-4 CosmoFalsify golden demo pipeline.")
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--zip-out", type=Path, default=None, help="Optional deterministic zip path for demo outputs.")
    ap.add_argument(
        "--created-utc",
        type=int,
        default=DEFAULT_CREATED_UTC_EPOCH,
        help="UTC epoch-seconds used for deterministic created_utc (default: 946684800).",
    )
    ap.add_argument("--keep-work", type=int, choices=(0, 1), default=0)
    ap.add_argument("--format", choices=("json", "text"), default="text")
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = _parse_args(argv)
        created_epoch = int(args.created_utc)
        created_utc = _to_iso_utc(created_epoch)
        outdir = Path(args.outdir).expanduser().resolve()
        keep_work = bool(int(args.keep_work))
    except UsageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    repo_root = Path(__file__).resolve().parents[1]
    repo_parent = repo_root.parent
    workspace = (repo_parent / WORKSPACE_REL).resolve()

    _prepare_outdir(outdir)
    _prepare_workspace(workspace)

    artifacts_dir = outdir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    report_path = outdir / "cosmofalsify_demo_report.json"
    report_md_path = outdir / "cosmofalsify_demo_report.md"

    stage_cmds: List[Tuple[str, List[str]]] = [
        (
            "scan_toy",
            [
                "python3",
                "v11.0.0/scripts/phase2_e2_scan.py",
                "--toy",
                "--model",
                "lcdm",
                "--grid",
                "H0=70",
                "--grid",
                "Omega_m=0.3",
                "--out-dir",
                f"{WORKSPACE_REL}/scan",
                "--points-jsonl-name",
                "e2_scan_points.jsonl",
            ],
        ),
        (
            "bundle",
            [
                "python3",
                "v11.0.0/scripts/phase2_e2_bundle.py",
                "--in",
                f"{WORKSPACE_REL}/scan/e2_scan_points.jsonl",
                "--outdir",
                f"{WORKSPACE_REL}/bundle",
                "--overwrite",
            ],
        ),
        (
            "verify_before_paper_assets",
            [
                "python3",
                "v11.0.0/scripts/phase2_e2_verify_bundle.py",
                "--bundle",
                f"{WORKSPACE_REL}/bundle",
                "--paper-assets",
                "ignore",
                "--json-out",
                f"{WORKSPACE_REL}/verify_before_paper_assets.json",
            ],
        ),
        (
            "make_paper_assets",
            [
                "python3",
                "v11.0.0/scripts/phase2_e2_make_paper_assets.py",
                "--bundle",
                f"{WORKSPACE_REL}/bundle",
                "--outdir",
                f"{WORKSPACE_REL}/bundle/paper_assets",
                "--mode",
                "all",
                "--overwrite",
                "--emit-snippets",
                "--snippets-format",
                "both",
                "--created-utc",
                created_utc,
            ],
        ),
        (
            "verify_after_paper_assets",
            [
                "python3",
                "v11.0.0/scripts/phase2_e2_verify_bundle.py",
                "--bundle",
                f"{WORKSPACE_REL}/bundle",
                "--paper-assets",
                "require",
                "--json-out",
                f"{WORKSPACE_REL}/verify_after_paper_assets.json",
            ],
        ),
    ]

    stages: List[Dict[str, Any]] = []
    failed = False
    for stage_name, cmd in stage_cmds:
        row = _run_stage(
            stage=stage_name,
            argv=cmd,
            cwd=repo_parent,
            redact_paths=(outdir, workspace, artifacts_dir, repo_parent),
        )
        stages.append(row)
        if row.get("status") != "ok":
            failed = True
            break

    for stage_name, cmd in stage_cmds[len(stages) :]:
        stages.append(
            {
                "stage": stage_name,
                "argv": cmd,
                "returncode": None,
                "status": "not_run",
            }
        )

    artifacts: Dict[str, Any] = {
        "bundle_zip": None,
        "demo_pack_zip": None,
    }

    if not failed:
        bundle_dir = workspace / "bundle"
        bundle_zip = artifacts_dir / "bundle.zip"
        _deterministic_zip(source_dir=bundle_dir, out_zip=bundle_zip, skip_relpaths=())
        artifacts["bundle_zip"] = {
            "path": _rel_to(bundle_zip, outdir),
            "sha256": _sha256_file(bundle_zip),
        }

    payload: Dict[str, Any] = {
        "schema": SCHEMA,
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "created_utc": created_utc,
        "created_utc_epoch": created_epoch,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "repo_version_dir": "v11.0.0",
        "paths_redacted": True,
        "status": "ok" if not failed else "fail",
        "commands_executed": [{"stage": str(name), "argv": [str(x) for x in cmd]} for name, cmd in stage_cmds],
        "stages": stages,
        "artifacts": artifacts,
    }

    _write_text(report_path, _json_pretty(payload))
    _write_text(report_md_path, _render_md(payload))

    if not failed and args.zip_out is not None:
        zip_out = Path(args.zip_out).expanduser().resolve()
        zipped_relpaths = _deterministic_zip(
            source_dir=outdir,
            out_zip=zip_out,
            skip_relpaths=(
                _rel_to(report_path, outdir),
                _rel_to(report_md_path, outdir),
            ),
        )
        payload["artifacts"]["demo_pack_zip"] = {
            "path": _rel_to(zip_out, outdir),
            "sha256": _sha256_file(zip_out),
            "n_members": len(zipped_relpaths),
            "report_included": False,
        }
        _write_text(report_path, _json_pretty(payload))
        _write_text(report_md_path, _render_md(payload))

    if keep_work:
        debug_work = outdir / "work"
        if debug_work.exists():
            shutil.rmtree(debug_work)
        if workspace.exists():
            shutil.copytree(workspace, debug_work)

    if workspace.exists():
        shutil.rmtree(workspace)

    if str(args.format) == "json":
        print(_json_pretty(payload), end="")
    else:
        print(f"status={payload['status']} report={report_path.name}")

    return 0 if payload["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())

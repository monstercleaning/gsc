#!/usr/bin/env python3
"""Deterministic Phase-4 red-team regression checks (stdlib-only)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple


TOOL = "phase4_red_team_check"
SCHEMA = "phase4_red_team_check_report_v1"
DEFAULT_REPO_ROOT = "v11.0.0"
DEFAULT_FORMAT = "json"
DEFAULT_STRICT = 1
ABS_TOKENS: Tuple[str, ...] = ("/Users/", "/home/", "/var/folders/", "C:\\Users\\")
ABS_WIN_RE = re.compile(r"[A-Za-z]:\\[^\s\"']+")
TMP_PATH_RE = re.compile(r"/(?:private/)?tmp/[^\s\"']+")
GITLESS_MARKER = "not a git repository"


class UsageError(Exception):
    """Usage/configuration error (exit 1)."""


def _json_pretty(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def _sanitize_text(text: str, *, repo_root: Path, extra_paths: Sequence[Path] = ()) -> str:
    out = str(text or "")
    replace_roots = [repo_root.resolve(), *[Path(p).resolve() for p in extra_paths]]
    for path in replace_roots:
        raw = str(path).replace("\\", "/")
        if raw:
            out = out.replace(raw, ".")
    for token in ABS_TOKENS:
        out = out.replace(token, "[abs]/")
    out = TMP_PATH_RE.sub(".", out)
    out = ABS_WIN_RE.sub("[abs]", out)
    out = " ".join(out.split())
    if len(out) > 300:
        out = out[:300]
    return out


def _run_subprocess(cmd: Sequence[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(x) for x in cmd],
        cwd=str(cwd),
        text=True,
        capture_output=True,
    )


def _run_check_docs_claims_lint(repo_root: Path) -> Dict[str, Any]:
    script = repo_root / "scripts" / "docs_claims_lint.py"
    proc = _run_subprocess(
        [sys.executable, str(script), "--repo-root", str(repo_root)],
        cwd=repo_root.parent,
    )
    result: Dict[str, Any] = {
        "status": "ok" if proc.returncode == 0 else "fail",
        "returncode": int(proc.returncode),
    }
    if proc.returncode != 0:
        msg = _sanitize_text((proc.stderr or "") + "\n" + (proc.stdout or ""), repo_root=repo_root)
        result["message"] = msg
    return result


def _run_check_repo_footprint(repo_root: Path) -> Dict[str, Any]:
    script = repo_root / "scripts" / "audit_repo_footprint.py"
    git_metadata_available = (repo_root / ".git").exists() or (repo_root.parent / ".git").exists()
    proc = _run_subprocess(
        [sys.executable, str(script), "--repo-root", str(repo_root), "--max-mb", "10"],
        cwd=repo_root.parent,
    )
    first_line = ""
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if line:
            first_line = line
            break
    result: Dict[str, Any] = {
        "status": "ok" if proc.returncode == 0 else "fail",
        "returncode": int(proc.returncode),
    }
    if not git_metadata_available:
        result["git_metadata_unavailable"] = True
    combined = (proc.stderr or "") + "\n" + (proc.stdout or "")
    combined_lower = combined.lower()
    if proc.returncode != 0 and GITLESS_MARKER in combined_lower:
        result["status"] = "ok"
        result["summary"] = "git metadata unavailable; skipped tracked-file footprint check"
        result["git_metadata_unavailable"] = True
        return result
    if first_line:
        result["summary"] = _sanitize_text(first_line, repo_root=repo_root)
    if proc.returncode != 0:
        msg = _sanitize_text(combined, repo_root=repo_root)
        result["message"] = msg
    return result


def _run_check_inventory(repo_root: Path) -> Dict[str, Any]:
    script = repo_root / "scripts" / "phase2_repo_inventory.py"
    proc = _run_subprocess(
        [
            sys.executable,
            str(script),
            "--repo-root",
            str(repo_root),
            "--require-present",
            "--format",
            "json",
        ],
        cwd=repo_root.parent,
    )
    result: Dict[str, Any] = {
        "status": "ok" if proc.returncode == 0 else "fail",
        "returncode": int(proc.returncode),
    }
    if proc.stdout.strip():
        try:
            payload = json.loads(proc.stdout)
        except Exception:
            payload = None
        if isinstance(payload, Mapping):
            counts = payload.get("counts")
            if isinstance(counts, Mapping):
                result["counts"] = {
                    "total": int(counts.get("total") or 0),
                    "present": int(counts.get("present") or 0),
                    "missing": int(counts.get("missing") or 0),
                    "required_missing": int(counts.get("required_missing") or 0),
                }
            missing_required = payload.get("missing_required")
            if isinstance(missing_required, list):
                result["missing_required"] = [str(x) for x in missing_required]
    if proc.returncode != 0:
        msg = _sanitize_text((proc.stderr or "") + "\n" + (proc.stdout or ""), repo_root=repo_root)
        result["message"] = msg
    return result


def _run_check_snapshot_portability(repo_root: Path) -> Dict[str, Any]:
    make_snapshot = repo_root / "scripts" / "make_repo_snapshot.py"
    preflight = repo_root / "scripts" / "preflight_share_check.py"

    with tempfile.TemporaryDirectory(prefix="phase4_red_team_") as td:
        temp_dir = Path(td)
        zip_path = temp_dir / "GSC_share_snapshot.zip"

        proc_snapshot = _run_subprocess(
            [
                sys.executable,
                str(make_snapshot),
                "--profile",
                "share",
                "--zip-out",
                str(zip_path),
            ],
            cwd=repo_root.parent,
        )
        if proc_snapshot.returncode != 0:
            return {
                "status": "fail",
                "returncode": int(proc_snapshot.returncode),
                "message": _sanitize_text(
                    (proc_snapshot.stderr or "") + "\n" + (proc_snapshot.stdout or ""),
                    repo_root=repo_root,
                    extra_paths=(temp_dir,),
                ),
            }

        proc_preflight = _run_subprocess(
            [
                sys.executable,
                str(preflight),
                "--path",
                str(zip_path),
                "--max-mb",
                "800",
                "--format",
                "json",
            ],
            cwd=repo_root.parent,
        )

        result: Dict[str, Any] = {
            "status": "fail",
            "snapshot_name": "GSC_share_snapshot.zip",
            "preflight_returncode": int(proc_preflight.returncode),
            "forbidden_match_count": None,
            "size_budget_ok": None,
        }

        payload: Optional[Mapping[str, Any]] = None
        if proc_preflight.stdout.strip():
            try:
                parsed = json.loads(proc_preflight.stdout)
            except Exception:
                parsed = None
            if isinstance(parsed, Mapping):
                payload = parsed

        if payload is None:
            result["message"] = _sanitize_text(
                (proc_preflight.stderr or "") + "\n" + (proc_preflight.stdout or ""),
                repo_root=repo_root,
                extra_paths=(temp_dir,),
            )
            return result

        forbidden = int(payload.get("forbidden_match_count") or 0)
        size_budget_ok = bool(payload.get("size_budget_ok"))
        result["forbidden_match_count"] = forbidden
        result["size_budget_ok"] = size_budget_ok
        result["total_mib"] = float(payload.get("total_mib") or 0.0)

        ok = proc_preflight.returncode == 0 and forbidden == 0 and size_budget_ok
        result["status"] = "ok" if ok else "fail"
        if not ok:
            result["message"] = _sanitize_text(
                (proc_preflight.stderr or "") + "\n" + (proc_preflight.stdout or ""),
                repo_root=repo_root,
                extra_paths=(temp_dir,),
            )
        return result


def _render_md(payload: Mapping[str, Any]) -> str:
    checks = payload.get("checks")
    rows: List[Tuple[str, Mapping[str, Any]]] = []
    if isinstance(checks, Mapping):
        for key in sorted(str(k) for k in checks.keys()):
            value = checks.get(key)
            if isinstance(value, Mapping):
                rows.append((key, value))

    lines: List[str] = []
    lines.append("# Phase-4 Red Team Check Report")
    lines.append("")
    lines.append(f"- tool: `{payload.get('tool')}`")
    lines.append(f"- schema: `{payload.get('schema')}`")
    lines.append(f"- repo_version_dir: `{payload.get('repo_version_dir')}`")
    lines.append(f"- strict: {int(bool(payload.get('strict')))}")
    lines.append(f"- overall_status: `{payload.get('overall_status')}`")
    lines.append(f"- paths_redacted: `{bool(payload.get('paths_redacted'))}`")
    lines.append("")
    lines.append("| check_id | status | summary |")
    lines.append("|---|---|---|")
    for key, row in rows:
        status = str(row.get("status") or "")
        summary = str(row.get("summary") or row.get("message") or "")
        lines.append(f"| `{key}` | `{status}` | {summary} |")

    lines.append("")
    lines.append("## Reviewer usage")
    lines.append("Run `python3 v11.0.0/scripts/phase4_red_team_check.py --repo-root v11.0.0 --outdir v11.0.0/out/red_team --strict 1`.")
    lines.append("Inspect `RED_TEAM_REPORT.json` for machine-readable check status and `RED_TEAM_REPORT.md` for a quick summary.")
    lines.append("")
    return "\n".join(lines) + "\n"


def _render_text(payload: Mapping[str, Any]) -> str:
    lines = [
        f"schema={payload.get('schema')}",
        f"repo_version_dir={payload.get('repo_version_dir')}",
        f"overall_status={payload.get('overall_status')}",
        f"strict={int(bool(payload.get('strict')))}",
        f"paths_redacted={bool(payload.get('paths_redacted'))}",
    ]
    checks = payload.get("checks")
    if isinstance(checks, Mapping):
        for key in sorted(str(k) for k in checks.keys()):
            row = checks.get(key)
            if not isinstance(row, Mapping):
                continue
            lines.append(f"check.{key}.status={row.get('status')}")
    return "\n".join(lines) + "\n"


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Run deterministic Phase-4 red-team checks and emit a portable report.")
    ap.add_argument("--repo-root", default=DEFAULT_REPO_ROOT)
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--format", choices=("json", "text"), default=DEFAULT_FORMAT)
    ap.add_argument("--strict", choices=(0, 1), type=int, default=DEFAULT_STRICT)
    return ap.parse_args(argv)


def _build_report(args: argparse.Namespace) -> Tuple[Dict[str, Any], Path]:
    repo_root = Path(str(args.repo_root)).expanduser().resolve()
    if not repo_root.is_dir():
        raise UsageError(f"--repo-root directory not found: {repo_root}")

    repo_version_dir = repo_root.name
    scripts_dir = repo_root / "scripts"
    if not scripts_dir.is_dir():
        raise UsageError(f"scripts directory not found under repo root: {scripts_dir}")

    outdir = Path(str(args.outdir)).expanduser().resolve() if args.outdir else (repo_root / "out" / "red_team")
    outdir.mkdir(parents=True, exist_ok=True)

    check_funcs: List[Tuple[str, Callable[[Path], Dict[str, Any]]]] = [
        ("docs_claims_lint", _run_check_docs_claims_lint),
        ("inventory", _run_check_inventory),
        ("repo_footprint", _run_check_repo_footprint),
        ("snapshot_portability", _run_check_snapshot_portability),
    ]

    checks: Dict[str, Any] = {}
    for check_id, fn in check_funcs:
        checks[check_id] = fn(repo_root)

    all_ok = all(isinstance(v, Mapping) and str(v.get("status")) == "ok" for v in checks.values())
    payload: Dict[str, Any] = {
        "schema": SCHEMA,
        "tool": TOOL,
        "repo_version_dir": repo_version_dir,
        "strict": bool(args.strict),
        "overall_status": "ok" if all_ok else "fail",
        "paths_redacted": True,
        "checks": checks,
    }

    return payload, outdir


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = _parse_args(argv)
        payload, outdir = _build_report(args)
    except UsageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    report_json = _json_pretty(payload)
    report_md = _render_md(payload)
    (outdir / "RED_TEAM_REPORT.json").write_text(report_json, encoding="utf-8")
    (outdir / "RED_TEAM_REPORT.md").write_text(report_md, encoding="utf-8")

    if str(args.format) == "json":
        print(report_json, end="")
    else:
        print(_render_text(payload), end="")

    any_fail = str(payload.get("overall_status")) != "ok"
    if int(args.strict) == 1 and any_fail:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

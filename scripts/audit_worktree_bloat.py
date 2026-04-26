#!/usr/bin/env python3
"""Stdlib-only worktree bloat audit with deterministic output."""

from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple


SCHEMA_ID = "gsc_worktree_bloat_report_v1"


class AuditError(RuntimeError):
    """Hard runtime failure."""


def _norm_posix(path: str) -> str:
    raw = str(path).replace("\\", "/").strip()
    if raw.startswith("./"):
        raw = raw[2:]
    if raw in {"", "."}:
        return "."
    pure = PurePosixPath(raw)
    if pure.is_absolute() or ".." in pure.parts:
        raise AuditError(f"unsafe path: {path}")
    return str(pure)


def _normalize_prefixes(values: Sequence[str]) -> List[str]:
    out: List[str] = []
    for item in values:
        token = str(item).strip()
        if not token:
            continue
        norm = _norm_posix(token)
        if norm == ".":
            continue
        out.append(norm)
    out = sorted(set(out))
    return out


def _prefix_match(path: str, prefix: str) -> bool:
    p = str(path)
    q = str(prefix)
    return p == q or p.startswith(q + "/")


def _is_excluded(path: str, prefixes: Sequence[str]) -> bool:
    return any(_prefix_match(path, p) for p in prefixes)


def _run_git(root: Path, args: Sequence[str]) -> str:
    cmd = ["git", "-C", str(root)] + [str(a) for a in args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        stdout = (proc.stdout or "").strip()
        details = stderr or stdout or f"git exited {proc.returncode}"
        raise AuditError(f"git command failed ({' '.join(args)}): {details}")
    return proc.stdout


def _git_set(root: Path, args: Sequence[str]) -> Set[str]:
    out = _run_git(root, [*args, "-z"])
    rows = [x for x in out.split("\0") if x]
    return {_norm_posix(x) for x in rows}


def _git_available(root: Path) -> bool:
    try:
        _run_git(root, ["rev-parse", "--is-inside-work-tree"])
        return True
    except AuditError:
        return False


def _sorted_kv_desc(mapping: Dict[str, int], top_n: int) -> List[Dict[str, Any]]:
    rows = [{"path": k, "bytes": int(v)} for k, v in mapping.items()]
    rows.sort(key=lambda r: (-int(r["bytes"]), str(r["path"])))
    return rows[: int(top_n)]


def _scan_tree(root: Path, *, max_depth: int, top_n: int, exclude_prefixes: Sequence[str]) -> Dict[str, Any]:
    file_rows: List[Tuple[str, int]] = []
    dir_sizes: Dict[str, int] = {}
    skipped_permission = 0
    skipped_broken_symlink = 0
    n_dirs = 0

    root_resolved = root.resolve()

    for current, dirnames, filenames in os.walk(root_resolved, topdown=True, followlinks=False):
        current_path = Path(current)

        kept_dirs: List[str] = []
        for name in sorted(dirnames):
            abs_dir = current_path / name
            try:
                rel = _norm_posix(str(abs_dir.relative_to(root_resolved)))
            except Exception:
                continue
            if _is_excluded(rel, exclude_prefixes):
                continue
            kept_dirs.append(name)
            n_dirs += 1
        dirnames[:] = kept_dirs

        for name in sorted(filenames):
            abs_file = current_path / name
            try:
                rel = _norm_posix(str(abs_file.relative_to(root_resolved)))
            except Exception:
                continue
            if _is_excluded(rel, exclude_prefixes):
                continue

            try:
                if abs_file.is_symlink():
                    if not abs_file.exists():
                        skipped_broken_symlink += 1
                    continue
                st = abs_file.stat()
            except PermissionError:
                skipped_permission += 1
                continue
            except OSError:
                continue

            if not stat.S_ISREG(st.st_mode):
                continue

            size = int(st.st_size)
            file_rows.append((rel, size))

            parts = rel.split("/")
            max_part = min(int(max_depth), max(0, len(parts) - 1))
            for i in range(1, max_part + 1):
                key = "/".join(parts[:i])
                dir_sizes[key] = int(dir_sizes.get(key, 0)) + int(size)

    file_rows.sort(key=lambda item: (-int(item[1]), str(item[0])))
    total_bytes = int(sum(int(size) for _, size in file_rows))

    top_files = [{"path": p, "bytes": int(b)} for p, b in file_rows[: int(top_n)]]
    top_dirs = _sorted_kv_desc(dir_sizes, int(top_n))

    file_size_map = {p: int(b) for p, b in file_rows}

    return {
        "root": str(root_resolved),
        "total_bytes": int(total_bytes),
        "n_files": int(len(file_rows)),
        "n_dirs": int(n_dirs),
        "top_dirs": top_dirs,
        "top_files": top_files,
        "file_size_map": file_size_map,
        "skipped": {
            "permission_errors": int(skipped_permission),
            "broken_symlinks": int(skipped_broken_symlink),
        },
    }


def _git_breakdown(root: Path, file_size_map: Dict[str, int], top_n: int) -> Dict[str, Any]:
    tracked = _git_set(root, ["ls-files"])
    untracked = _git_set(root, ["ls-files", "--others", "--exclude-standard"])
    ignored = _git_set(root, ["ls-files", "--others", "-i", "--exclude-standard"])

    classes = {
        "tracked": {"bytes": 0, "count": 0, "top": []},
        "untracked": {"bytes": 0, "count": 0, "top": []},
        "ignored": {"bytes": 0, "count": 0, "top": []},
    }
    tops: Dict[str, List[Tuple[str, int]]] = {"tracked": [], "untracked": [], "ignored": []}

    for path, size in file_size_map.items():
        if path in tracked:
            bucket = "tracked"
        elif path in ignored:
            bucket = "ignored"
        elif path in untracked:
            bucket = "untracked"
        else:
            bucket = "untracked"
        classes[bucket]["bytes"] = int(classes[bucket]["bytes"]) + int(size)
        classes[bucket]["count"] = int(classes[bucket]["count"]) + 1
        tops[bucket].append((path, int(size)))

    for bucket, rows in tops.items():
        rows.sort(key=lambda item: (-int(item[1]), str(item[0])))
        classes[bucket]["top"] = [{"path": p, "bytes": int(b)} for p, b in rows[: int(top_n)]]

    return classes


def _classify_category(path: str) -> Optional[str]:
    parts = str(path).split("/")
    if str(path).startswith(".git/"):
        return "git_dir_bytes"
    if ".venv" in parts:
        return "venv_bytes"
    if str(path).startswith("v11.0.0/results/"):
        return "results_bytes"
    if str(path).startswith("v11.0.0/paper_assets"):
        return "paper_assets_bytes"
    if str(path).startswith("v11.0.0/data/") and (str(path).endswith(".cov") or str(path).endswith(".npz")):
        return "data_cov_npz_bytes"
    return None


def _category_bytes(file_size_map: Dict[str, int], *, ignored_paths: Optional[Set[str]] = None) -> Dict[str, int]:
    rows: Dict[str, int] = {
        "git_dir_bytes": 0,
        "venv_bytes": 0,
        "results_bytes": 0,
        "paper_assets_bytes": 0,
        "data_cov_npz_bytes": 0,
        "other_ignored_bytes": 0,
    }
    ignored = set(ignored_paths or set())
    for path, size in file_size_map.items():
        bucket = _classify_category(path)
        if bucket is not None:
            rows[bucket] = int(rows[bucket]) + int(size)
        elif path in ignored:
            rows["other_ignored_bytes"] = int(rows["other_ignored_bytes"]) + int(size)
    return rows


def _print_text(report: Dict[str, Any], *, emit_clean_hints: bool) -> None:
    print("== Root summary ==")
    print(
        f"root={report['root']} total_bytes={report['total_bytes']} "
        f"n_files={report['n_files']} n_dirs={report['n_dirs']}"
    )

    print("== Top directories ==")
    for row in report.get("top_dirs", []):
        print(f"dir={row['path']} bytes={row['bytes']}")

    print("== Top files ==")
    for row in report.get("top_files", []):
        print(f"file={row['path']} bytes={row['bytes']}")

    git = report.get("git")
    if isinstance(git, dict):
        print("== Git breakdown ==")
        print(
            f"tracked_bytes={git['tracked']['bytes']} tracked_count={git['tracked']['count']} "
            f"untracked_bytes={git['untracked']['bytes']} untracked_count={git['untracked']['count']} "
            f"ignored_bytes={git['ignored']['bytes']} ignored_count={git['ignored']['count']}"
        )
        for bucket in ("tracked", "untracked", "ignored"):
            for row in git.get(bucket, {}).get("top", []):
                print(f"git_{bucket}_file={row['path']} bytes={row['bytes']}")

    categories = report.get("category_bytes")
    if isinstance(categories, dict):
        print("== Category bytes ==")
        for key in (
            "git_dir_bytes",
            "venv_bytes",
            "results_bytes",
            "paper_assets_bytes",
            "data_cov_npz_bytes",
            "other_ignored_bytes",
        ):
            print(f"{key}={int(categories.get(key, 0))}")

    if emit_clean_hints:
        print("== Hints ==")
        print(
            "hint_snapshot=python3 v11.0.0/scripts/make_repo_snapshot.py "
            "--profile share --snapshot-format zip --output gsc_snapshot_share.zip"
        )
        print("hint_audit_zip=python3 v11.0.0/scripts/phase2_e2_audit_zip_bloat.py --zip GSC.zip --top 30")
        print("hint_cleanup=git clean -fdX")


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Audit worktree bloat (stdlib-only).")
    ap.add_argument("--root", default=".", help="Root directory to audit (default: .)")
    ap.add_argument("--max-depth", type=int, default=3, help="Directory aggregation depth (default: 3)")
    ap.add_argument("--top-n", type=int, default=25, help="Number of top dirs/files to report (default: 25)")
    ap.add_argument("--exclude", action="append", default=[], help="Repeatable path-prefix exclude.")
    ap.add_argument("--format", choices=("text", "json"), default="text", help="Output format.")
    ap.add_argument("--json-out", default=None, help="Optional JSON report path.")
    ap.add_argument("--git-mode", choices=("auto", "on", "off"), default="auto", help="Git classification mode.")
    ap.add_argument("--emit-clean-hints", action="store_true", help="Emit actionable cleanup/snapshot hints in text mode.")
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = parse_args(argv)
        root = Path(args.root).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise AuditError(f"invalid --root: {root}")
        if int(args.max_depth) < 0:
            raise AuditError("--max-depth must be >= 0")
        if int(args.top_n) <= 0:
            raise AuditError("--top-n must be > 0")

        excludes = _normalize_prefixes(list(args.exclude or []))
        scan = _scan_tree(root, max_depth=int(args.max_depth), top_n=int(args.top_n), exclude_prefixes=excludes)

        report: Dict[str, Any] = {
            "schema": SCHEMA_ID,
            "root": scan["root"],
            "total_bytes": scan["total_bytes"],
            "n_files": scan["n_files"],
            "n_dirs": scan["n_dirs"],
            "top_dirs": scan["top_dirs"],
            "top_files": scan["top_files"],
            "excluded_prefixes": excludes,
            "skipped": scan["skipped"],
        }

        git_mode = str(args.git_mode)
        ignored_paths: Optional[Set[str]] = None
        if git_mode == "off":
            pass
        else:
            available = _git_available(root)
            if git_mode == "on" and not available:
                raise AuditError("git-mode=on but git repository metadata is unavailable")
            if available:
                report["git"] = _git_breakdown(root, scan["file_size_map"], int(args.top_n))
                ignored_paths = _git_set(root, ["ls-files", "--others", "-i", "--exclude-standard"])

        report["category_bytes"] = _category_bytes(scan["file_size_map"], ignored_paths=ignored_paths)

        if args.json_out:
            _write_json(Path(args.json_out).expanduser().resolve(), report)

        if str(args.format) == "json":
            print(json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False))
        else:
            _print_text(report, emit_clean_hints=bool(args.emit_clean_hints))
        return 0

    except AuditError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

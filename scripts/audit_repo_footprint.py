#!/usr/bin/env python3
"""Audit tracked file sizes against repository footprint policy.

This check is intentionally stdlib-only so it can run in minimal CI jobs.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Set


V101_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = V101_DIR.parent
DEFAULT_CANONICAL = V101_DIR / "canonical_artifacts.json"
DEFAULT_ALLOWLIST = V101_DIR / "docs" / "repo_footprint_allowlist.txt"


def _git_ls_files(repo_root: Path) -> List[Path]:
    out = subprocess.check_output(
        ["git", "ls-files", "-z"],
        cwd=str(repo_root),
        stderr=subprocess.DEVNULL,
    )
    items = [Path(p.decode("utf-8")) for p in out.split(b"\x00") if p]
    return items


def _manifest_ls_files(repo_root: Path) -> List[Path]:
    candidate_paths = [
        repo_root / "repo_snapshot_manifest.json",
        repo_root.parent / "repo_snapshot_manifest.json",
    ]
    for manifest_path in candidate_paths:
        if not manifest_path.is_file():
            continue
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        files = payload.get("files")
        if not isinstance(files, list):
            continue
        out: List[Path] = []
        for rec in files:
            if not isinstance(rec, dict):
                continue
            rel = str(rec.get("path", "")).strip()
            if rel:
                out.append(Path(rel))
        if out:
            return out
    return []


def _tracked_files(repo_root: Path) -> List[Path]:
    try:
        return _git_ls_files(repo_root)
    except Exception:
        fallback = _manifest_ls_files(repo_root)
        if fallback:
            return fallback
        raise


def _load_allowlist(path: Path) -> List[str]:
    if not path.is_file():
        return []
    lines: List[str] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        lines.append(s)
    return lines


def _canonical_whitelist(canonical_json: Path) -> Set[str]:
    if not canonical_json.is_file():
        return set()
    obj = json.loads(canonical_json.read_text(encoding="utf-8"))
    arts = obj.get("artifacts")
    if not isinstance(arts, dict):
        return set()
    out: Set[str] = set()
    for rec in arts.values():
        if not isinstance(rec, dict):
            continue
        asset = str(rec.get("asset", "")).strip()
        if not asset:
            continue
        out.add(asset)
        out.add(f"v11.0.0/{asset}")
    return out


def _is_allowed(rel: str, *, canonical_paths: Set[str], allow_globs: Iterable[str]) -> bool:
    if rel in canonical_paths:
        return True
    return any(fnmatch.fnmatch(rel, pat) for pat in allow_globs)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="audit_repo_footprint",
        description="Fail when tracked files exceed a size threshold unless allowlisted.",
    )
    ap.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    ap.add_argument("--max-mb", type=float, default=10.0, help="Maximum tracked file size (MB) before policy fail")
    ap.add_argument("--canonical-json", type=Path, default=DEFAULT_CANONICAL)
    ap.add_argument("--allowlist", type=Path, default=DEFAULT_ALLOWLIST)
    ap.add_argument("--top", type=int, default=50)
    args = ap.parse_args(argv)

    repo_root = args.repo_root.expanduser().resolve()
    if args.max_mb <= 0:
        print("ERROR: --max-mb must be > 0", file=sys.stderr)
        return 2
    max_bytes = int(args.max_mb * 1024 * 1024)

    allow_globs = _load_allowlist(args.allowlist.expanduser().resolve())
    canonical = _canonical_whitelist(args.canonical_json.expanduser().resolve())

    offenders: List[tuple[int, str]] = []
    for rel_path in _tracked_files(repo_root):
        full = repo_root / rel_path
        if not full.is_file():
            continue
        size = full.stat().st_size
        rel = rel_path.as_posix()
        if size > max_bytes and not _is_allowed(rel, canonical_paths=canonical, allow_globs=allow_globs):
            offenders.append((size, rel))

    if offenders:
        offenders.sort(reverse=True)
        print(f"ERROR: tracked files exceed {args.max_mb:g} MB and are not allowlisted:")
        for size, rel in offenders[: max(1, int(args.top))]:
            print(f"  {size / (1024 * 1024):8.2f} MB  {rel}")
        print("If intentional, add a precise pattern to:")
        print(f"  {args.allowlist}")
        return 2

    print(
        "OK: repository footprint policy passed "
        f"(threshold={args.max_mb:g} MB, allowlist_entries={len(allow_globs)}, canonical_entries={len(canonical)})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

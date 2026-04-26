#!/usr/bin/env python3
"""Content-level portability lint for JSON/JSONL artifacts (stdlib-only)."""

from __future__ import annotations

import argparse
import fnmatch
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
import os
import zipfile


SCHEMA = "phase2_portable_content_lint_v1"
MARKER = "PORTABLE_CONTENT_LINT_ABSOLUTE_PATHS"
MAX_HITS = 200
DEFAULT_INCLUDE_GLOBS: Tuple[str, ...] = ("*.json", "*.jsonl")
DEFAULT_TOKENS: Tuple[str, ...] = (
    "/Users/",
    "/home/",
    "/var/folders/",
    "C:\\Users\\",
)


class PortableContentLintError(Exception):
    """Hard usage/IO error."""


def _normalize_relpath(path: str) -> str:
    text = str(path or "").strip().replace("\\", "/")
    if text.startswith("./"):
        text = text[2:]
    return text.lstrip("/")


def _normalize_tokens(raw: Optional[str]) -> List[str]:
    if raw is None:
        return list(DEFAULT_TOKENS)
    items = [str(x).strip() for x in str(raw).split(",")]
    out = [x for x in items if x]
    return out if out else list(DEFAULT_TOKENS)


def _matches_globs(relpath: str, patterns: Sequence[str]) -> bool:
    if not patterns:
        return False
    rel = _normalize_relpath(relpath)
    for pat in patterns:
        p = str(pat or "").strip()
        if not p:
            continue
        if fnmatch.fnmatch(rel, p):
            return True
        name = Path(rel).name
        if fnmatch.fnmatch(name, p):
            return True
    return False


def _iter_dir_entries(root: Path) -> Iterable[Tuple[str, int, Path]]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        filenames.sort()
        dpath = Path(dirpath)
        for name in filenames:
            path = dpath / name
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            yield rel, int(path.stat().st_size), path


def _iter_zip_entries(path: Path) -> Iterable[Tuple[str, int]]:
    with zipfile.ZipFile(path, "r") as zf:
        for info in sorted(zf.infolist(), key=lambda x: x.filename):
            name = str(info.filename)
            if not name or name.endswith("/"):
                continue
            yield _normalize_relpath(name), int(info.file_size)


def _read_file_bytes_limited(path: Path, *, max_bytes: int) -> bytes:
    with path.open("rb") as fh:
        return fh.read(max(1, int(max_bytes) + 1))


def _read_zip_member_bytes_limited(zf: zipfile.ZipFile, member: str, *, max_bytes: int) -> bytes:
    with zf.open(member, "r") as fh:
        return fh.read(max(1, int(max_bytes) + 1))


def _decode_for_scan(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def _scan_text_for_tokens(text: str, tokens: Sequence[str]) -> Optional[str]:
    for token in tokens:
        if token and token in text:
            return token
    return None


def _slice_jsonl_text(text: str, *, max_lines: int) -> str:
    if max_lines <= 0:
        return ""
    lines = text.splitlines()
    return "\n".join(lines[: int(max_lines)])


def _build_payload(
    *,
    path: Path,
    kind: str,
    include_globs: Sequence[str],
    exclude_globs: Sequence[str],
    tokens: Sequence[str],
    max_bytes_per_file: int,
    max_jsonl_lines: int,
    total_files_seen: int,
    total_files_scanned: int,
    total_bytes_scanned: int,
    offenders: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    offenders_list = list(offenders)
    extra_count = max(0, len(offenders_list) - MAX_HITS)
    offenders_capped = offenders_list[:MAX_HITS]
    status = "fail" if offenders_list else "ok"
    return {
        "schema": SCHEMA,
        "tool": "phase2_portable_content_lint",
        "path": str(path),
        "kind": kind,
        "status": status,
        "marker": MARKER if offenders_list else None,
        "tokens": [str(t) for t in tokens],
        "include_globs": [str(x) for x in include_globs],
        "exclude_globs": [str(x) for x in exclude_globs],
        "max_bytes_per_file": int(max_bytes_per_file),
        "max_jsonl_lines": int(max_jsonl_lines),
        "total_files_seen": int(total_files_seen),
        "total_files_scanned": int(total_files_scanned),
        "total_bytes_scanned": int(total_bytes_scanned),
        "offending_file_count": int(len(offenders_list)),
        "offending_files": [
            {
                "path": str(row.get("path", "")),
                "token": str(row.get("token", "")),
                "kind": str(row.get("kind", "")),
            }
            for row in offenders_capped
        ],
        "offending_files_extra_count": int(extra_count),
        "recommendations": [
            "Fix/redact machine-local absolute paths in JSON/JSONL artifacts before sharing.",
            "Run this lint together with preflight_share_check.py (path-level check).",
        ],
    }


def _render_text(payload: Mapping[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"schema={payload.get('schema')}")
    lines.append(f"path={payload.get('path')}")
    lines.append(f"kind={payload.get('kind')}")
    lines.append(f"status={payload.get('status')}")
    lines.append(
        "counts="
        f"seen={payload.get('total_files_seen')} "
        f"scanned={payload.get('total_files_scanned')} "
        f"bytes_scanned={payload.get('total_bytes_scanned')}"
    )
    lines.append(f"offending_file_count={payload.get('offending_file_count')}")
    offenders = payload.get("offending_files")
    if isinstance(offenders, list) and offenders:
        lines.append("offending_files:")
        for row in offenders:
            if not isinstance(row, Mapping):
                continue
            lines.append(f"  - path={row.get('path')} token={row.get('token')} kind={row.get('kind')}")
        extra = int(payload.get("offending_files_extra_count") or 0)
        if extra > 0:
            lines.append(f"  - +{extra} more")
    marker = payload.get("marker")
    if marker:
        lines.append(f"marker={marker}")
    return "\n".join(lines) + "\n"


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Detect machine-local absolute path tokens inside JSON/JSONL content.")
    ap.add_argument("--path", required=True, help="Directory or zip path to scan")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    ap.add_argument("--include-glob", action="append", default=None, help="Include glob (repeatable, default: *.json,*.jsonl)")
    ap.add_argument("--exclude-glob", action="append", default=[], help="Exclude glob (repeatable)")
    ap.add_argument("--max-bytes-per-file", type=int, default=2_000_000)
    ap.add_argument("--max-jsonl-lines", type=int, default=2000)
    ap.add_argument("--tokens", default=None, help="Comma-separated absolute-path tokens override")
    return ap.parse_args(argv)


def _scan_dir(
    path: Path,
    *,
    include_globs: Sequence[str],
    exclude_globs: Sequence[str],
    tokens: Sequence[str],
    max_bytes_per_file: int,
    max_jsonl_lines: int,
) -> Dict[str, Any]:
    total_seen = 0
    total_scanned = 0
    total_bytes_scanned = 0
    offenders: List[Dict[str, Any]] = []

    for rel, _size, abs_path in _iter_dir_entries(path):
        total_seen += 1
        if not _matches_globs(rel, include_globs):
            continue
        if _matches_globs(rel, exclude_globs):
            continue

        data = _read_file_bytes_limited(abs_path, max_bytes=max_bytes_per_file)
        text = _decode_for_scan(data)
        kind = "jsonl" if rel.lower().endswith(".jsonl") else "json"
        scan_text = _slice_jsonl_text(text, max_lines=max_jsonl_lines) if kind == "jsonl" else text
        token = _scan_text_for_tokens(scan_text, tokens)

        total_scanned += 1
        total_bytes_scanned += min(len(data), max_bytes_per_file)

        if token is not None:
            offenders.append({"path": _normalize_relpath(rel), "token": token, "kind": kind})

    offenders.sort(key=lambda row: (str(row.get("path")), str(row.get("token"))))
    return _build_payload(
        path=path,
        kind="dir",
        include_globs=include_globs,
        exclude_globs=exclude_globs,
        tokens=tokens,
        max_bytes_per_file=max_bytes_per_file,
        max_jsonl_lines=max_jsonl_lines,
        total_files_seen=total_seen,
        total_files_scanned=total_scanned,
        total_bytes_scanned=total_bytes_scanned,
        offenders=offenders,
    )


def _scan_zip(
    path: Path,
    *,
    include_globs: Sequence[str],
    exclude_globs: Sequence[str],
    tokens: Sequence[str],
    max_bytes_per_file: int,
    max_jsonl_lines: int,
) -> Dict[str, Any]:
    total_seen = 0
    total_scanned = 0
    total_bytes_scanned = 0
    offenders: List[Dict[str, Any]] = []

    with zipfile.ZipFile(path, "r") as zf:
        for info in sorted(zf.infolist(), key=lambda x: x.filename):
            name = str(info.filename)
            if not name or name.endswith("/"):
                continue
            rel = _normalize_relpath(name)
            total_seen += 1
            if not _matches_globs(rel, include_globs):
                continue
            if _matches_globs(rel, exclude_globs):
                continue

            data = _read_zip_member_bytes_limited(zf, info.filename, max_bytes=max_bytes_per_file)
            text = _decode_for_scan(data)
            kind = "jsonl" if rel.lower().endswith(".jsonl") else "json"
            scan_text = _slice_jsonl_text(text, max_lines=max_jsonl_lines) if kind == "jsonl" else text
            token = _scan_text_for_tokens(scan_text, tokens)

            total_scanned += 1
            total_bytes_scanned += min(len(data), max_bytes_per_file)

            if token is not None:
                offenders.append({"path": rel, "token": token, "kind": kind})

    offenders.sort(key=lambda row: (str(row.get("path")), str(row.get("token"))))
    return _build_payload(
        path=path,
        kind="zip",
        include_globs=include_globs,
        exclude_globs=exclude_globs,
        tokens=tokens,
        max_bytes_per_file=max_bytes_per_file,
        max_jsonl_lines=max_jsonl_lines,
        total_files_seen=total_seen,
        total_files_scanned=total_scanned,
        total_bytes_scanned=total_bytes_scanned,
        offenders=offenders,
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = _parse_args(argv)
    except SystemExit:
        return 2

    path = Path(str(args.path)).expanduser().resolve()
    if int(args.max_bytes_per_file) <= 0:
        print("ERROR: --max-bytes-per-file must be positive")
        return 2
    if int(args.max_jsonl_lines) <= 0:
        print("ERROR: --max-jsonl-lines must be positive")
        return 2

    include_globs = list(args.include_glob or [])
    if not include_globs:
        include_globs = list(DEFAULT_INCLUDE_GLOBS)
    exclude_globs = [str(x) for x in (args.exclude_glob or []) if str(x).strip()]
    tokens = _normalize_tokens(args.tokens)

    try:
        if path.is_dir():
            payload = _scan_dir(
                path,
                include_globs=include_globs,
                exclude_globs=exclude_globs,
                tokens=tokens,
                max_bytes_per_file=int(args.max_bytes_per_file),
                max_jsonl_lines=int(args.max_jsonl_lines),
            )
        elif path.is_file() and path.suffix.lower() == ".zip":
            payload = _scan_zip(
                path,
                include_globs=include_globs,
                exclude_globs=exclude_globs,
                tokens=tokens,
                max_bytes_per_file=int(args.max_bytes_per_file),
                max_jsonl_lines=int(args.max_jsonl_lines),
            )
        else:
            raise PortableContentLintError(f"--path must be an existing directory or .zip file: {path}")
    except (OSError, zipfile.BadZipFile, PortableContentLintError) as exc:
        print(f"ERROR: {exc}")
        return 2

    if str(args.format) == "json":
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2))
    else:
        print(_render_text(payload), end="")

    if int(payload.get("offending_file_count", 0)) > 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

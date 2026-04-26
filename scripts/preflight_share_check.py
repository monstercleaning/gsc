#!/usr/bin/env python3
"""Preflight checks for share archives/directories (bloat + forbidden paths)."""

from __future__ import annotations

import argparse
import fnmatch
import json
from pathlib import Path
import zipfile
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
import os


SCHEMA = "preflight_share_check_v1"
_MATCH_CAP = 200
_DEFAULT_FORBID_PATTERNS: Tuple[str, ...] = (
    "/.git/",
    "/__MACOSX/",
    "/.DS_Store",
    "/.venv/",
    "/node_modules/",
    "/dist/",
    "/build/",
    "/paper_assets_",
    "/artifacts/",
)


def _normalize_pattern(pattern: str) -> str:
    text = str(pattern).replace("\\", "/").strip()
    if not text:
        return text
    return text if text.startswith("/") else "/" + text


def _path_norm(path: str) -> str:
    text = str(path).replace("\\", "/").strip()
    if text.startswith("./"):
        text = text[2:]
    text = text.lstrip("/")
    if not text:
        return "/"
    return "/" + text


def _matches(path_norm: str, pattern_norm: str) -> bool:
    if not pattern_norm:
        return False
    if any(ch in pattern_norm for ch in "*?[]"):
        return fnmatch.fnmatch(path_norm, pattern_norm)
    return pattern_norm in path_norm


def _iter_dir(root: Path) -> Iterable[Tuple[str, int]]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        filenames.sort()
        dpath = Path(dirpath)
        for name in filenames:
            path = dpath / name
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            yield rel, int(path.stat().st_size)


def _iter_zip(path: Path) -> Iterable[Tuple[str, int]]:
    with zipfile.ZipFile(path, "r") as zf:
        for info in sorted(zf.infolist(), key=lambda i: i.filename):
            name = str(info.filename)
            if name.endswith("/"):
                continue
            yield name, int(info.file_size)


def _scan_entries(
    entries: Iterable[Tuple[str, int]],
    *,
    forbid_patterns: Sequence[str],
    allow_patterns: Sequence[str],
) -> Dict[str, Any]:
    total_files = 0
    total_bytes = 0
    forbidden_hits: List[str] = []

    norm_forbid = [p for p in (_normalize_pattern(x) for x in forbid_patterns) if p]
    norm_allow = [p for p in (_normalize_pattern(x) for x in allow_patterns) if p]

    for rel, size in entries:
        total_files += 1
        total_bytes += int(size)

        pnorm = _path_norm(rel)
        if any(_matches(pnorm, ap) for ap in norm_allow):
            continue
        if any(_matches(pnorm, fp) for fp in norm_forbid):
            forbidden_hits.append(rel.replace("\\", "/"))

    forbidden_hits.sort()
    kept = forbidden_hits[:_MATCH_CAP]
    extra = max(0, len(forbidden_hits) - len(kept))

    return {
        "total_files": total_files,
        "total_bytes": total_bytes,
        "forbidden_match_count": len(forbidden_hits),
        "forbidden_matches": kept,
        "forbidden_matches_extra_count": extra,
        "forbid_patterns": norm_forbid,
        "allow_patterns": norm_allow,
    }


def _render_text(payload: Mapping[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"schema={payload.get('schema')}")
    lines.append(f"path={payload.get('path')}")
    lines.append(f"kind={payload.get('kind')}")
    lines.append(
        "counts="
        f"files={payload.get('total_files')} bytes={payload.get('total_bytes')} "
        f"mib={payload.get('total_mib')}"
    )
    lines.append(f"max_mb={payload.get('max_mb')}")
    lines.append(f"size_budget_ok={bool(payload.get('size_budget_ok'))}")
    lines.append(f"forbidden_match_count={payload.get('forbidden_match_count')}")

    hits = payload.get("forbidden_matches")
    if isinstance(hits, list) and hits:
        lines.append("forbidden_matches:")
        for row in hits:
            lines.append(f"  - {row}")
        extra = int(payload.get("forbidden_matches_extra_count") or 0)
        if extra > 0:
            lines.append(f"  - +{extra} more")

    rec = payload.get("recommendations")
    if isinstance(rec, list) and rec:
        lines.append("recommendations:")
        for row in rec:
            lines.append(f"  - {row}")

    if payload.get("status") == "fail":
        marker = payload.get("marker")
        if marker:
            lines.append(f"marker={marker}")
    return "\n".join(lines) + "\n"


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Preflight share safety check for directory/zip inputs.")
    ap.add_argument("--path", required=True, help="Directory or zip path to check")
    ap.add_argument("--max-mb", type=float, default=50.0, help="Max total size in MiB (default: 50)")
    ap.add_argument("--forbid-pattern", action="append", default=[], help="Additional forbidden path pattern")
    ap.add_argument("--allow-pattern", action="append", default=[], help="Allowlist override pattern")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    path = Path(str(args.path)).expanduser().resolve()

    if float(args.max_mb) <= 0:
        print("ERROR: --max-mb must be positive")
        return 1

    if path.is_dir():
        kind = "dir"
        entries = _iter_dir(path)
    elif path.is_file() and path.suffix.lower() == ".zip":
        kind = "zip"
        try:
            entries = _iter_zip(path)
        except zipfile.BadZipFile:
            print(f"ERROR: invalid zip file: {path}")
            return 1
    else:
        print(f"ERROR: --path must be an existing directory or .zip file: {path}")
        return 1

    scan = _scan_entries(
        entries,
        forbid_patterns=[*_DEFAULT_FORBID_PATTERNS, *list(args.forbid_pattern or [])],
        allow_patterns=list(args.allow_pattern or []),
    )

    total_bytes = int(scan["total_bytes"])
    total_mib = round(total_bytes / (1024.0 * 1024.0), 3)
    max_mb = float(args.max_mb)
    size_budget_ok = total_mib <= max_mb
    has_forbidden = int(scan["forbidden_match_count"]) > 0

    marker = None
    if has_forbidden:
        marker = "SHARE_PREFLIGHT_FORBIDDEN_PATHS"
    elif not size_budget_ok:
        marker = "SHARE_PREFLIGHT_SIZE_BUDGET_EXCEEDED"

    payload: Dict[str, Any] = {
        "schema": SCHEMA,
        "path": str(path),
        "kind": kind,
        "total_files": int(scan["total_files"]),
        "total_bytes": total_bytes,
        "total_mib": total_mib,
        "max_mb": max_mb,
        "size_budget_ok": bool(size_budget_ok),
        "forbidden_patterns": list(scan["forbid_patterns"]),
        "allow_patterns": list(scan["allow_patterns"]),
        "forbidden_match_count": int(scan["forbidden_match_count"]),
        "forbidden_matches": list(scan["forbidden_matches"]),
        "forbidden_matches_extra_count": int(scan["forbidden_matches_extra_count"]),
        "recommendations": [
            "Use deterministic snapshot tooling: python3 v11.0.0/scripts/make_repo_snapshot.py --profile share --zip-out <out.zip>",
            "For reviewer-ready outputs use: python3 v11.0.0/scripts/phase2_e2_make_reviewer_pack.py --bundle <bundle.zip> --outdir <dir> --zip-out <pack.zip>",
        ],
        "status": "fail" if (has_forbidden or not size_budget_ok) else "ok",
        "marker": marker,
    }

    if str(args.format) == "json":
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2))
    else:
        print(_render_text(payload), end="")

    if has_forbidden or not size_budget_ok:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

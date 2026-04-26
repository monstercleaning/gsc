#!/usr/bin/env python3
"""Stdlib-only zip bloat audit for repo-share snapshots."""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


SCHEMA_ID = "phase2_e2_zip_bloat_report_v1"


class ZipAuditError(RuntimeError):
    """Hard runtime failure."""


def _is_dir_entry(info: zipfile.ZipInfo) -> bool:
    filename = str(info.filename)
    return filename.endswith("/")


def _entry_has_venv(path: str) -> bool:
    parts = str(path).replace("\\", "/").split("/")
    return ".venv" in parts


def _entry_has_macos_junk(path: str) -> bool:
    token = str(path).replace("\\", "/")
    return token.startswith("__MACOSX/") or token.endswith("/.DS_Store") or token == ".DS_Store"


def _entry_has_paper_assets(path: str) -> bool:
    token = str(path).replace("\\", "/")
    return token.startswith("v11.0.0/paper_assets") or "/paper_assets" in token


def _entry_has_results(path: str) -> bool:
    return str(path).replace("\\", "/").startswith("v11.0.0/results/")


def _entry_has_cov_npz(path: str) -> bool:
    token = str(path)
    return token.endswith(".cov") or token.endswith(".npz")


def _analyze_zip(path: Path, *, top_n: int, max_entry_mb: float) -> Dict[str, Any]:
    if not path.is_file():
        raise ZipAuditError(f"missing --zip file: {path}")
    if int(top_n) <= 0:
        raise ZipAuditError("--top must be > 0")
    if float(max_entry_mb) <= 0.0:
        raise ZipAuditError("--max-entry-mb must be > 0")

    max_entry_bytes = int(float(max_entry_mb) * 1024.0 * 1024.0)

    try:
        with zipfile.ZipFile(path, "r") as zf:
            infos = list(zf.infolist())
    except (OSError, zipfile.BadZipFile) as exc:
        raise ZipAuditError(f"unable to read zip: {path}: {exc}") from exc

    infos_sorted = sorted(infos, key=lambda i: (-int(i.file_size), str(i.filename)))

    total_uncompressed = int(sum(int(i.file_size) for i in infos))
    total_compressed = int(sum(int(i.compress_size) for i in infos))

    has_git = False
    has_venv = False
    has_results = False
    has_cov_npz = False
    has_paper_assets = False
    has_macos_junk = False
    has_big_single = False

    for info in infos:
        name = str(info.filename).replace("\\", "/")
        if _is_dir_entry(info):
            # Directory markers still count for dedicated path flags.
            has_git = has_git or name.startswith(".git/")
            has_venv = has_venv or _entry_has_venv(name)
            has_results = has_results or _entry_has_results(name)
            has_paper_assets = has_paper_assets or _entry_has_paper_assets(name)
            has_macos_junk = has_macos_junk or _entry_has_macos_junk(name)
            continue

        has_git = has_git or name.startswith(".git/")
        has_venv = has_venv or _entry_has_venv(name)
        has_results = has_results or _entry_has_results(name)
        has_cov_npz = has_cov_npz or _entry_has_cov_npz(name)
        has_paper_assets = has_paper_assets or _entry_has_paper_assets(name)
        has_macos_junk = has_macos_junk or _entry_has_macos_junk(name)
        has_big_single = has_big_single or int(info.file_size) > int(max_entry_bytes)

    flags: Dict[str, bool] = {
        "has_git": bool(has_git),
        "has_venv": bool(has_venv),
        "has_results": bool(has_results),
        "has_cov_npz": bool(has_cov_npz),
        "has_paper_assets": bool(has_paper_assets),
        "has_macos_junk": bool(has_macos_junk),
        "has_big_single": bool(has_big_single),
    }
    flags["has_any_bloat"] = bool(
        flags["has_git"]
        or flags["has_venv"]
        or flags["has_results"]
        or flags["has_cov_npz"]
        or flags["has_paper_assets"]
        or flags["has_macos_junk"]
        or flags["has_big_single"]
    )

    top_entries: List[Dict[str, Any]] = []
    for info in infos_sorted[: int(top_n)]:
        top_entries.append(
            {
                "path": str(info.filename),
                "bytes_uncompressed": int(info.file_size),
                "bytes_compressed": int(info.compress_size),
            }
        )

    return {
        "schema": SCHEMA_ID,
        "zip_path": str(path.resolve()),
        "n_entries": int(len(infos)),
        "total_uncompressed_bytes": int(total_uncompressed),
        "total_compressed_bytes": int(total_compressed),
        "top_entries": top_entries,
        "flags": flags,
        "max_entry_mb": float(max_entry_mb),
    }


def _policy_violation(report: Dict[str, Any], fail_on: str) -> Tuple[bool, str]:
    if str(fail_on) == "none":
        return False, ""
    flags = report.get("flags")
    if not isinstance(flags, dict):
        return True, "report missing flags"
    token = str(fail_on)
    if token == "has_git":
        violated = bool(flags.get("has_git"))
    elif token == "has_venv":
        violated = bool(flags.get("has_venv"))
    elif token == "has_big_single":
        violated = bool(flags.get("has_big_single"))
    elif token == "has_any_bloat":
        violated = bool(flags.get("has_any_bloat"))
    else:
        violated = False
    return violated, token


def _print_text(report: Dict[str, Any], *, fail_on: str, violated: bool) -> None:
    print("== Summary ==")
    print(
        f"zip={report.get('zip_path')} n_entries={report.get('n_entries')} "
        f"total_uncompressed_bytes={report.get('total_uncompressed_bytes')} "
        f"total_compressed_bytes={report.get('total_compressed_bytes')}"
    )

    print("== Flags ==")
    flags = report.get("flags") or {}
    for key in (
        "has_git",
        "has_venv",
        "has_results",
        "has_cov_npz",
        "has_paper_assets",
        "has_macos_junk",
        "has_big_single",
        "has_any_bloat",
    ):
        print(f"{key}={str(bool(flags.get(key, False))).lower()}")

    print("== Top entries ==")
    for row in report.get("top_entries", []):
        if not isinstance(row, dict):
            continue
        size_mb = float(int(row.get("bytes_uncompressed", 0)) / (1024.0 * 1024.0))
        print(f"size_mb={size_mb:.3f} path={row.get('path')}")

    print("== Policy ==")
    print(f"fail_on={fail_on}")
    print(f"violation={str(bool(violated)).lower()}")
    if violated:
        print("hint=Use make_repo_snapshot --profile share instead of zipping repository root.")


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Audit zip bloat (stdlib-only).")
    ap.add_argument("--zip", required=True, help="Zip file path to audit.")
    ap.add_argument("--top", type=int, default=30, help="Top entries by uncompressed size (default: 30).")
    ap.add_argument("--format", choices=("text", "json"), default="text", help="Output format.")
    ap.add_argument("--json-out", default=None, help="Optional JSON output path.")
    ap.add_argument(
        "--fail-on",
        choices=("none", "has_git", "has_venv", "has_big_single", "has_any_bloat"),
        default="none",
        help="Policy gate (exit code 2 on violation).",
    )
    ap.add_argument(
        "--max-entry-mb",
        type=float,
        default=25.0,
        help="Threshold for has_big_single in MB (default: 25).",
    )
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = parse_args(argv)
        report = _analyze_zip(Path(args.zip).expanduser().resolve(), top_n=int(args.top), max_entry_mb=float(args.max_entry_mb))
        violated, violation_key = _policy_violation(report, str(args.fail_on))
        report["policy"] = {
            "fail_on": str(args.fail_on),
            "violated": bool(violated),
            "violation_key": str(violation_key) if violated else "",
        }

        if args.json_out:
            _write_json(Path(args.json_out).expanduser().resolve(), report)

        if str(args.format) == "json":
            print(json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False))
        else:
            _print_text(report, fail_on=str(args.fail_on), violated=bool(violated))

        if violated:
            return 2
        return 0
    except ZipAuditError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

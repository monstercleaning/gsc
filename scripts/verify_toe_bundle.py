#!/usr/bin/env python3
"""Offline verifier for ToE-track bundles."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath


_RE_WINDOWS_ABS = re.compile(r"^[A-Za-z]:[\\/]")
_RE_WINDOWS_USERS = re.compile(r"[A-Za-z]:[\\/]+Users[\\/]")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _fail(msg: str) -> "None":
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(2)


def _is_absolute(name: str) -> bool:
    if name.startswith(("/", "\\")):
        return True
    if _RE_WINDOWS_ABS.match(name) is not None:
        return True
    return False


def _has_traversal(name: str) -> bool:
    try:
        return ".." in PurePosixPath(name).parts
    except Exception:
        return True


def _is_macos_junk(name: str) -> bool:
    p = PurePosixPath(name)
    if not p.parts:
        return False
    if p.parts[0] == "__MACOSX":
        return True
    if p.name == ".DS_Store" or p.name.startswith("._"):
        return True
    return False


def _has_machine_local_path(blob: str) -> bool:
    for n in ("/Users/", "/home/", "/var/folders/"):
        if n in blob:
            return True
    return _RE_WINDOWS_USERS.search(blob) is not None


def _is_forbidden_entry(name: str) -> bool:
    p = PurePosixPath(name)
    s = p.as_posix()
    if s.startswith("paper_assets/"):
        return True
    if s.startswith("data/"):
        return True
    if "submission_bundle_" in p.name:
        return True
    if "referee_pack_" in p.name:
        return True
    return False


def _is_allowed_entry(name: str) -> bool:
    if name in {"manifest.json", "TOE_BUNDLE_README.md"}:
        return True
    if name.startswith("docs/popular/"):
        return True
    if name in {"docs/historical_context.md", "docs/HISTORICAL_CONTEXT.md"}:
        return True
    return False


def _check_repo_relative(path_text: str) -> bool:
    if _is_absolute(path_text):
        return False
    if _has_traversal(path_text):
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="verify_toe_bundle", description="Verify toe_bundle_*.zip")
    ap.add_argument("zip_path")
    ap.add_argument(
        "--require-toe-index",
        action="store_true",
        help="Fail if docs/popular/TOE_INDEX.md is missing (useful for r1+ contracts).",
    )
    args = ap.parse_args(argv)

    zip_path = Path(args.zip_path)
    if not zip_path.is_file():
        _fail(f"zip not found: {zip_path}")

    sha = _sha256_file(zip_path)

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        if not names:
            _fail("zip is empty")

        has_popular = False
        has_toe_index = False
        for n in names:
            if _is_absolute(n):
                _fail(f"absolute zip entry: {n!r}")
            if _has_traversal(n):
                _fail(f"path traversal zip entry: {n!r}")
            if _is_macos_junk(n):
                _fail(f"macOS junk entry: {n!r}")
            if _is_forbidden_entry(n):
                _fail(f"forbidden entry in TOE bundle: {n!r}")
            if not _is_allowed_entry(n):
                _fail(f"unexpected entry in TOE bundle: {n!r}")
            if n.startswith("docs/popular/") and not n.endswith("/"):
                has_popular = True
            if n == "docs/popular/TOE_INDEX.md":
                has_toe_index = True

        if not has_popular:
            _fail("missing docs/popular/** content")
        if not has_toe_index and args.require_toe_index:
            _fail("missing required docs/popular/TOE_INDEX.md")
        if not has_toe_index:
            print("WARN: docs/popular/TOE_INDEX.md missing (legacy ToE bundle accepted)", file=sys.stderr)

        if "manifest.json" in names:
            raw = zf.read("manifest.json")
            try:
                txt = raw.decode("utf-8")
            except UnicodeDecodeError as e:
                _fail(f"manifest.json not valid UTF-8: {e}")
            try:
                obj = json.loads(txt)
            except json.JSONDecodeError as e:
                _fail(f"manifest.json not valid JSON: {e}")
            if _has_machine_local_path(txt):
                _fail("manifest.json contains machine-local absolute path fragments")
            if not isinstance(obj, dict):
                _fail("manifest.json root must be a JSON object")
            outputs = obj.get("outputs", {})
            if isinstance(outputs, dict):
                bundle_zip = outputs.get("bundle_zip")
                if isinstance(bundle_zip, str) and not _check_repo_relative(bundle_zip):
                    _fail("manifest outputs.bundle_zip must be repo-relative")
            included = obj.get("included", {})
            if isinstance(included, dict):
                files = included.get("files", [])
                if isinstance(files, list):
                    for item in files:
                        if isinstance(item, str) and not _check_repo_relative(item):
                            _fail(f"manifest included file is not repo-relative: {item!r}")
                        if isinstance(item, str):
                            ok_prefix = (
                                item.startswith("docs/popular/")
                                or item in {"docs/historical_context.md", "docs/HISTORICAL_CONTEXT.md"}
                            )
                            if not ok_prefix:
                                _fail(f"manifest included file is outside allowed ToE roots: {item!r}")

    print("OK: toe bundle verified")
    print(f"  zip: {zip_path}")
    print(f"  sha256: {sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

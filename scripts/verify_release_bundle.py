#!/usr/bin/env python3
"""
Offline verifier for the canonical late-time paper-assets release bundle.

Checks:
- SHA256 matches the expected release hash (default: v10.1.1-late-time-r4)
- Zip entries are relative (no absolute paths, no path traversal)
- manifest.json inside the zip does not contain machine-specific absolute paths (e.g. /Users/...)
- Basic structure sanity: tables/, figures/, manifest.json exist
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath


DEFAULT_EXPECTED_SHA256 = "b29d5cb0e30941d2bb0cb4b2930f21a4a219a7e0a8439f7fec82704134cf4823"

_RE_WINDOWS_ABS = re.compile(r"^[A-Za-z]:[\\/]")
_RE_WINDOWS_USERS = re.compile(r"[A-Za-z]:[\\/]+Users[\\/]")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_absolute_zip_name(name: str) -> bool:
    if name.startswith(("/", "\\")):
        return True
    if _RE_WINDOWS_ABS.match(name) is not None:
        return True
    return False


def _has_path_traversal(name: str) -> bool:
    # zipfile uses forward slashes; treat it as POSIX for safety.
    try:
        parts = PurePosixPath(name).parts
    except Exception:
        return True
    return any(p == ".." for p in parts)


def _find_machine_specific_abs_path(text: str) -> str | None:
    # Keep this intentionally narrow: we only want to reject user/machine-specific paths.
    # System paths (e.g. /usr/bin/...) are not targeted here.
    needles = [
        "/Users/",
        "/home/",
        "/var/folders/",
    ]
    for n in needles:
        if n in text:
            return n
    if _RE_WINDOWS_USERS.search(text) is not None:
        return "C:\\Users\\..."
    return None


def _fail(msg: str) -> "None":
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(2)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="verify_release_bundle",
        description="Verify a paper_assets zip bundle (sha256 + portability checks).",
    )
    ap.add_argument(
        "zip_path",
        help="Path to paper_assets_v10.1.1-late-time-r4.zip (local file).",
    )
    ap.add_argument(
        "--expected-sha256",
        default=DEFAULT_EXPECTED_SHA256,
        help="Expected SHA256 hex digest. Defaults to v10.1.1-late-time-r4.",
    )
    args = ap.parse_args(argv)

    zip_path = Path(args.zip_path)
    if not zip_path.is_file():
        _fail(f"zip not found: {zip_path}")

    expected = str(args.expected_sha256).strip().lower()
    actual = _sha256_file(zip_path).lower()
    if actual != expected:
        _fail(f"sha256 mismatch: expected {expected}, got {actual}")

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        if not names:
            _fail("zip is empty")

        for name in names:
            if _is_absolute_zip_name(name):
                _fail(f"zip entry has absolute path: {name!r}")
            if _has_path_traversal(name):
                _fail(f"zip entry contains path traversal '..': {name!r}")

        if "paper_assets/manifest.json" in names:
            manifest_name = "paper_assets/manifest.json"
            tables_prefix = "paper_assets/tables/"
            figures_prefix = "paper_assets/figures/"
        elif "manifest.json" in names:
            manifest_name = "manifest.json"
            tables_prefix = "tables/"
            figures_prefix = "figures/"
        else:
            _fail("missing manifest.json (expected paper_assets/manifest.json or manifest.json at zip root)")

        if not any(n.startswith(tables_prefix) and not n.endswith("/") for n in names):
            _fail(f"missing tables/ entries (expected under {tables_prefix!r})")
        if not any(n.startswith(figures_prefix) and not n.endswith("/") for n in names):
            _fail(f"missing figures/ entries (expected under {figures_prefix!r})")

        try:
            manifest_bytes = zf.read(manifest_name)
        except KeyError:
            _fail(f"missing {manifest_name!r} in zip")
        try:
            manifest_text = manifest_bytes.decode("utf-8")
        except UnicodeDecodeError as e:
            _fail(f"{manifest_name!r} is not valid UTF-8: {e}")

        try:
            json.loads(manifest_text)
        except json.JSONDecodeError as e:
            _fail(f"{manifest_name!r} is not valid JSON: {e}")

        bad = _find_machine_specific_abs_path(manifest_text)
        if bad is not None:
            _fail(f"{manifest_name!r} contains machine-specific absolute path fragment: {bad!r}")

    print("OK: release bundle verified")
    print(f"  zip: {zip_path}")
    print(f"  sha256: {actual}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

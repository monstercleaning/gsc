#!/usr/bin/env python3
"""
Offline verifier for a referee pack zip.

Checks (stdlib-only):
- Zip entries are relative (no absolute paths, no path traversal)
- Reject macOS junk entries (__MACOSX/, .DS_Store, AppleDouble "._*")
- Require key docs under docs/
- Require data/cmb/README.md
- Reject docs/popular/** content
- manifest.json (if present) must be valid UTF-8 JSON and must not contain machine-local paths
- By default, verify the nested submission bundle using verify_submission_bundle.py (no LaTeX)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
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


def _is_absolute_zip_name(name: str) -> bool:
    if name.startswith(("/", "\\")):
        return True
    if _RE_WINDOWS_ABS.match(name) is not None:
        return True
    return False


def _has_path_traversal(name: str) -> bool:
    try:
        parts = PurePosixPath(name).parts
    except Exception:
        return True
    return any(p == ".." for p in parts)


def _is_macos_junk(name: str) -> bool:
    p = PurePosixPath(name)
    if not p.parts:
        return False
    if p.parts[0] == "__MACOSX":
        return True
    if p.name == ".DS_Store":
        return True
    if p.name.startswith("._"):
        return True
    return False


def _contains_docs_popular(name: str) -> bool:
    parts = PurePosixPath(name).parts
    for i in range(len(parts) - 1):
        if parts[i] == "docs" and parts[i + 1] == "popular":
            return True
    return False


def _find_machine_specific_abs_path(text: str) -> str | None:
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


def _verify_nested_submission(zf: zipfile.ZipFile, nested_name: str) -> None:
    verifier = Path(__file__).resolve().parent / "verify_submission_bundle.py"
    if not verifier.is_file():
        _fail(f"missing nested verifier script in repo: {verifier}")

    nested_bytes = zf.read(nested_name)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        nested_path = td / "submission.zip"
        nested_path.write_bytes(nested_bytes)
        r = subprocess.run([sys.executable, str(verifier), str(nested_path)], capture_output=True, text=True)
        out = (r.stdout or "") + (r.stderr or "")
        if r.returncode != 0:
            _fail(f"nested submission bundle failed verify_submission_bundle:\n{out.strip()}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="verify_referee_pack",
        description="Verify a referee pack zip (structure + path hygiene; optional nested submission verify).",
    )
    ap.add_argument("zip_path", help="Path to referee_pack_*.zip (local file).")
    ap.add_argument(
        "--skip-nested-submission-verify",
        action="store_true",
        help="If set, do not run verify_submission_bundle.py on the nested submission zip.",
    )
    args = ap.parse_args(argv)

    zip_path = Path(args.zip_path)
    if not zip_path.is_file():
        _fail(f"zip not found: {zip_path}")

    sha = _sha256_file(zip_path)

    # Fallback minimal requirements (used only if manifest.json is missing or
    # does not provide an explicit include list).
    required_docs_fallback = [
        "docs/reviewer_faq.md",
        "docs/risk_register.md",
        "docs/precision_constraints_translator.md",
        "docs/early_time_bridge.md",
        "docs/early_time_e2_closure_requirements.md",
        "docs/early_time_drift_cmb_correlation.md",
        "docs/gw_standard_sirens.md",
        "docs/early_time_e2_plan.md",
        "docs/redshift_drift_beyond_flrw.md",
        "docs/reproducibility.md",
        "docs/measurement_model.md",
        "data/cmb/README.md",
        "REFEREE_PACK_README.md",
    ]

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        if not names:
            _fail("zip is empty")

        for name in names:
            if _is_absolute_zip_name(name):
                _fail(f"zip entry has absolute path: {name!r}")
            if _has_path_traversal(name):
                _fail(f"zip entry contains path traversal '..': {name!r}")
            if _is_macos_junk(name):
                _fail(f"zip contains macOS junk entry: {name!r}")
            if _contains_docs_popular(name):
                _fail(f"zip contains docs/popular content (not allowed in referee pack): {name!r}")

        required_entries = list(required_docs_fallback)
        if "manifest.json" in names:
            raw = zf.read("manifest.json")
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError as e:
                _fail(f"manifest.json is not valid UTF-8: {e}")
            try:
                manifest = json.loads(text)
            except json.JSONDecodeError as e:
                _fail(f"manifest.json is not valid JSON: {e}")
            bad = _find_machine_specific_abs_path(text)
            if bad is not None:
                _fail(f"manifest.json contains machine-specific absolute path fragment: {bad!r}")
            # If present, prefer the explicit include list from the manifest to
            # keep the verifier compatible across pack revisions.
            try:
                inc = manifest.get("included", {}).get("files", None)
                if isinstance(inc, list) and all(isinstance(x, str) for x in inc):
                    required_entries = list(inc)
            except Exception:
                pass

        for req in required_entries:
            if req not in names:
                _fail(f"missing required entry: {req!r}")

        nested = [n for n in names if n.startswith("paper/") and n.endswith(".zip") and PurePosixPath(n).name.startswith("submission_bundle_")]
        if not nested:
            _fail("missing nested submission bundle under paper/ (expected paper/submission_bundle_*.zip)")
        if len(nested) != 1:
            _fail(f"expected exactly one nested submission bundle under paper/, found {len(nested)}: {nested}")

        if not args.skip_nested_submission_verify:
            _verify_nested_submission(zf, nested[0])

    print("OK: referee pack verified")
    print(f"  zip: {zip_path}")
    print(f"  sha256: {sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

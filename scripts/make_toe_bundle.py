#!/usr/bin/env python3
"""Build a standalone ToE-track bundle (docs/popular only, offline-safe).

This bundle is intentionally separated from submission/referee artifacts.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import subprocess
import shutil
import tempfile
import textwrap
import zipfile
from pathlib import Path, PurePosixPath
from typing import Dict, List


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_absolute_zip_name(name: str) -> bool:
    if name.startswith(("/", "\\")):
        return True
    if len(name) >= 3 and name[1] == ":" and name[2] in ("/", "\\"):
        return True
    return False


def _has_path_traversal(name: str) -> bool:
    try:
        return ".." in PurePosixPath(name).parts
    except Exception:
        return True


def _is_macos_junk(path: Path) -> bool:
    parts = path.parts
    if "__MACOSX" in parts:
        return True
    name = path.name
    if name == ".DS_Store" or name.startswith("._"):
        return True
    return False


def _run_git(args: List[str]) -> str:
    try:
        return subprocess.check_output(args, stderr=subprocess.STDOUT, text=True).strip()
    except Exception:
        return "<unknown>"


def _relpath(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _zip_dir(root_dir: Path, out_zip: Path) -> None:
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        fixed_dt = (1980, 1, 1, 0, 0, 0)
        for p in sorted(root_dir.rglob("*")):
            if p.is_dir():
                continue
            arc = p.relative_to(root_dir).as_posix()
            if _is_absolute_zip_name(arc) or _has_path_traversal(arc):
                raise ValueError(f"unsafe arcname: {arc!r}")
            info = zipfile.ZipInfo(filename=arc, date_time=fixed_dt)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (0o100644 & 0xFFFF) << 16
            zf.writestr(info, p.read_bytes())


def _write_readme(path: Path, *, included_files: List[str]) -> None:
    text = textwrap.dedent(
        """\
        # TOE Track Bundle (v11.0.0, non-submission)

        This zip contains ToE-track / popular notes only.

        Disclaimer:
        - Not peer-reviewed
        - Not part of the submission bundle
        - Not part of the referee-pack baseline
        - Intended for separate discussion/exploration only

        Included namespace:
        - docs/popular/**
        - required entrypoint: docs/popular/TOE_INDEX.md

        Excluded by contract:
        - paper_assets/**
        - submission_bundle_*.zip
        - referee_pack_*.zip
        - data/**
        """
    )
    text += "\nIncluded files:\n"
    for p in included_files:
        text += f"- `{p}`\n"
    path.write_text(text, encoding="utf-8")


def _write_manifest(path: Path, *, included_files: List[str], repo_root: Path, out_zip: Path) -> None:
    obj: Dict[str, object] = {
        "kind": "toe_bundle",
        "diagnostic_only": True,
        "non_submission": True,
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "git_commit": _run_git(["git", "-C", str(repo_root), "rev-parse", "HEAD"]),
        "git_branch": _run_git(["git", "-C", str(repo_root), "rev-parse", "--abbrev-ref", "HEAD"]),
        "git_dirty": bool(_run_git(["git", "-C", str(repo_root), "status", "--porcelain=v1"]).strip()),
        "included": {"files": included_files},
        "outputs": {
            "bundle_zip": _relpath(out_zip, repo_root),
        },
        "include_roots": ["docs/popular/**"],
        "excludes": [
            "paper_assets/**",
            "submission_bundle_*.zip",
            "referee_pack_*.zip",
            "data/**",
            "__MACOSX/**",
            ".DS_Store",
            "._*",
        ],
        "notes": [
            "ToE-track only; intentionally separated from submission/referee bundles.",
        ],
    }
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def main(argv: List[str] | None = None) -> int:
    script_dir = Path(__file__).resolve().parent
    v101_dir = script_dir.parent

    ap = argparse.ArgumentParser(
        prog="make_toe_bundle",
        description="Build ToE-track zip from docs/popular/** only.",
    )
    ap.add_argument(
        "--v101-dir",
        type=Path,
        default=v101_dir,
        help="Path to v11.0.0/ (default: inferred from script location; used in tests).",
    )
    ap.add_argument(
        "--out-zip",
        type=Path,
        default=Path.cwd() / "toe_bundle_v10.1.1-r2.zip",
        help="Output zip path (default: ./toe_bundle_v10.1.1-r2.zip).",
    )
    args = ap.parse_args(argv)

    v101 = args.v101_dir.expanduser().resolve()
    repo_root = v101.parent
    out_zip = args.out_zip.expanduser().resolve()

    popular_dir = v101 / "docs" / "popular"
    if not popular_dir.is_dir():
        print(f"ERROR: missing docs/popular dir: {popular_dir}")
        return 2
    if not (popular_dir / "TOE_INDEX.md").is_file():
        print("ERROR: missing required docs/popular/TOE_INDEX.md")
        return 2

    historical_candidates = [
        v101 / "docs" / "historical_context.md",
        v101 / "docs" / "HISTORICAL_CONTEXT.md",
    ]

    with tempfile.TemporaryDirectory() as td:
        stage = Path(td) / "toe_bundle"
        (stage / "docs" / "popular").mkdir(parents=True, exist_ok=True)

        included: List[str] = []

        for p in sorted(popular_dir.rglob("*")):
            if not p.is_file():
                continue
            if _is_macos_junk(p):
                continue
            rel = p.relative_to(v101).as_posix()
            dest = stage / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, dest)
            included.append(rel)

        for c in historical_candidates:
            if c.is_file():
                if _is_macos_junk(c):
                    continue
                rel = c.relative_to(v101).as_posix()
                dest = stage / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(c, dest)
                included.append(rel)

        if not included:
            print("ERROR: no files included from docs/popular/**")
            return 2

        included = sorted(set(included))
        if "docs/popular/TOE_INDEX.md" not in included:
            print("ERROR: TOE_INDEX.md was not included; refusing to build bundle.")
            return 2
        _write_readme(stage / "TOE_BUNDLE_README.md", included_files=included)
        _write_manifest(stage / "manifest.json", included_files=included, repo_root=repo_root, out_zip=out_zip)
        _zip_dir(stage, out_zip)

    print("OK: TOE bundle built")
    print(f"  zip: {out_zip}")
    print(f"  sha256: {_sha256_file(out_zip)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

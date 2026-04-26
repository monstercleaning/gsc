#!/usr/bin/env python3
"""
Build an offline-safe submission bundle (arXiv/referee zip) for the canonical v11.0.0 late-time release.

Design goals:
- Do NOT modify TeX or assets (read-only inputs; assemble a separate zip).
- Run the canonical release verifier as a preflight (sha256 + zip safety).
- Produce a zip that contains only what LaTeX expects:
  - GSC_Framework_v10_1_FINAL.tex (bundle root)
  - paper_assets/figures/** (from the canonical assets zip)
  - paper_assets/tables/** (from the canonical assets zip)
  - paper_assets/manifest.json (from the canonical assets zip, if present)
  - SUBMISSION_README.md (bundle root)
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
import textwrap
import zipfile
from pathlib import Path, PurePosixPath


CANONICAL_TAG = "v10.1.1-late-time-r4"
DEFAULT_BUNDLE_NAME = "submission_bundle_v10.1.1-late-time-r4.zip"
DEFAULT_ASSETS_ZIP_NAME = "paper_assets_v10.1.1-late-time-r4.zip"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_absolute_zip_name(name: str) -> bool:
    if name.startswith(("/", "\\")):
        return True
    # Windows drive prefix.
    if len(name) >= 3 and name[1] == ":" and name[2] in ("/", "\\"):
        return True
    return False


def _has_path_traversal(name: str) -> bool:
    try:
        parts = PurePosixPath(name).parts
    except Exception:
        return True
    return any(p == ".." for p in parts)


def _safe_extract_zip(zip_path: Path, out_dir: Path) -> None:
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            name = info.filename
            if not name:
                continue
            if _is_absolute_zip_name(name):
                raise ValueError(f"zip entry has absolute path: {name!r}")
            if _has_path_traversal(name):
                raise ValueError(f"zip entry contains path traversal '..': {name!r}")

            # Directories in zip end with "/".
            parts = PurePosixPath(name).parts
            dest = out_dir.joinpath(*parts)
            if name.endswith("/"):
                dest.mkdir(parents=True, exist_ok=True)
                continue

            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info, "r") as src, dest.open("wb") as dst:
                shutil.copyfileobj(src, dst)


def _zip_dir(root_dir: Path, out_zip: Path) -> None:
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Deterministic zip output:
        # - stable file ordering
        # - fixed timestamps (zip format supports years >= 1980)
        # - stable permissions
        fixed_dt = (1980, 1, 1, 0, 0, 0)

        for p in sorted(root_dir.rglob("*")):
            if p.is_dir():
                continue
            arc = p.relative_to(root_dir).as_posix()
            if _is_absolute_zip_name(arc) or _has_path_traversal(arc):
                raise ValueError(f"refusing to write unsafe arcname: {arc!r}")

            data = p.read_bytes()
            info = zipfile.ZipInfo(filename=arc, date_time=fixed_dt)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3  # UNIX
            # Regular file with 0644 perms.
            info.external_attr = (0o100644 & 0xFFFF) << 16
            zf.writestr(info, data)


def _run_verifier(assets_zip: Path, expected_sha256: str | None) -> str:
    verifier = Path(__file__).resolve().parent / "verify_release_bundle.py"
    if not verifier.is_file():
        raise FileNotFoundError(f"missing verifier script: {verifier}")

    cmd = [sys.executable, str(verifier), str(assets_zip)]
    if expected_sha256 is not None:
        cmd += ["--expected-sha256", expected_sha256]

    r = subprocess.run(cmd, capture_output=True, text=True)
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0:
        raise RuntimeError(f"release bundle verification failed:\n{out.strip()}")
    return out


def _write_submission_readme(
    path: Path,
    *,
    canonical_tag: str,
    assets_zip_name: str,
    assets_sha256: str,
) -> None:
    text = textwrap.dedent(
        f"""\
        # GSC submission bundle (v11.0.0 late-time)

        This zip is intended as an arXiv/referee submission bundle for the canonical late-time release.

        ## Canonical release

        - Tag/Release: `{canonical_tag}`
        - Canonical paper-assets zip: `{assets_zip_name}`
        - SHA256 (assets zip): `{assets_sha256}`

        ## Contents

        - `GSC_Framework_v10_1_FINAL.tex`
        - `paper_assets/figures/**`
        - `paper_assets/tables/**`
        - `paper_assets/manifest.json` (if present in the canonical assets zip)

        ## How to build the PDF

        From this bundle directory:

        - Recommended (if available): `latexmk -pdf GSC_Framework_v10_1_FINAL.tex`
        - Minimal: run `pdflatex GSC_Framework_v10_1_FINAL.tex` twice.
        """
    )
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    script_dir = Path(__file__).resolve().parent
    v101_dir = script_dir.parent

    default_assets_zip = v101_dir / DEFAULT_ASSETS_ZIP_NAME

    ap = argparse.ArgumentParser(
        prog="make_submission_bundle",
        description="Build a submission-grade zip (TeX + canonical paper_assets) for v11.0.0 late-time.",
    )
    ap.add_argument(
        "assets_zip",
        nargs="?",
        default=str(default_assets_zip),
        help=f"Path to canonical assets zip (default: {default_assets_zip}).",
    )
    ap.add_argument(
        "out_zip",
        nargs="?",
        default=None,
        help=f"Output zip path (default: ./{DEFAULT_BUNDLE_NAME}).",
    )
    ap.add_argument(
        "--expected-sha256",
        default=None,
        help="Override expected SHA256 for the preflight verifier (primarily for tests).",
    )
    args = ap.parse_args(argv)

    assets_zip = Path(args.assets_zip).expanduser().resolve()
    out_zip = Path(args.out_zip).expanduser().resolve() if args.out_zip else (Path.cwd() / DEFAULT_BUNDLE_NAME).resolve()

    tex = v101_dir / "GSC_Framework_v10_1_FINAL.tex"
    if not tex.is_file():
        print(f"ERROR: missing LaTeX source: {tex}", file=sys.stderr)
        return 2
    if not assets_zip.is_file():
        print(f"ERROR: assets zip not found: {assets_zip}", file=sys.stderr)
        return 2

    # Preflight: verify sha256 + portability (fails if wrong bundle is passed).
    try:
        _run_verifier(assets_zip, args.expected_sha256)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    assets_sha = _sha256_file(assets_zip)

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        extract_dir = td / "extract"
        stage_dir = td / "submission"
        extract_dir.mkdir(parents=True, exist_ok=True)
        stage_dir.mkdir(parents=True, exist_ok=True)

        try:
            _safe_extract_zip(assets_zip, extract_dir)
        except Exception as e:
            print(f"ERROR: failed to extract assets zip safely: {e}", file=sys.stderr)
            return 2

        # Canonical r2 assets zip is rooted at paper_assets/.
        if (extract_dir / "paper_assets").is_dir():
            src_assets = extract_dir / "paper_assets"
        else:
            src_assets = extract_dir

        src_fig = src_assets / "figures"
        src_tab = src_assets / "tables"
        if not src_fig.is_dir() or not src_tab.is_dir():
            print("ERROR: assets zip does not contain expected figures/ and tables/ directories", file=sys.stderr)
            return 2

        # Assemble a submission directory that matches the LaTeX expectations (do not touch the TeX file).
        shutil.copy2(tex, stage_dir / tex.name)

        dst_assets = stage_dir / "paper_assets"
        dst_assets.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src_fig, dst_assets / "figures", dirs_exist_ok=True)
        shutil.copytree(src_tab, dst_assets / "tables", dirs_exist_ok=True)

        src_manifest = src_assets / "manifest.json"
        if src_manifest.is_file():
            shutil.copy2(src_manifest, dst_assets / "manifest.json")

        _write_submission_readme(
            stage_dir / "SUBMISSION_README.md",
            canonical_tag=CANONICAL_TAG,
            assets_zip_name=assets_zip.name,
            assets_sha256=assets_sha,
        )

        try:
            _zip_dir(stage_dir, out_zip)
        except Exception as e:
            print(f"ERROR: failed to write output zip: {e}", file=sys.stderr)
            return 2

    print(f"OK: wrote {out_zip}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

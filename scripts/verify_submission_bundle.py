#!/usr/bin/env python3
"""
Offline verifier for a submission bundle zip (TeX + paper_assets).

Checks (stdlib-only):
- Zip entries are relative (no absolute paths, no path traversal)
- Reject macOS junk entries (__MACOSX/, .DS_Store, AppleDouble "._*")
- Require canonical TeX: GSC_Framework_v10_1_FINAL.tex
- Require paper_assets/{figures,tables}/ with at least one file each
- Reject popular/TOE docs (docs/popular/**)
- If paper_assets/manifest.json exists:
  - must be valid UTF-8 JSON
  - must not contain machine-local absolute paths (/Users/, /home/, /var/folders/, C:\\Users\\...)
- Optionally: --smoke-compile runs pdflatex (if available) on the extracted bundle (two passes)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
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
    # zipfile uses forward slashes; treat it as POSIX for safety.
    try:
        parts = PurePosixPath(name).parts
    except Exception:
        return True
    return any(p == ".." for p in parts)


def _find_machine_specific_abs_path(text: str) -> str | None:
    # Keep this intentionally narrow: reject user/machine-specific paths.
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


def _expand_asset_macros(s: str) -> str:
    # Expand the canonical macros used in the paper.
    # (Keep it small and explicit; we only need enough to validate bundle contents.)
    s = s.replace("\\GSCAssetsDir", "paper_assets")
    s = s.replace("\\GSCFiguresDir", "paper_assets/figures")
    s = s.replace("\\GSCTablesDir", "paper_assets/tables")
    return s


def _extract_required_assets_from_tex(tex: str) -> set[str]:
    req: set[str] = set()

    # \GSCInputAsset{...}
    for m in re.finditer(r"\\GSCInputAsset\{([^}]*)\}", tex):
        raw = m.group(1).strip()
        if not raw:
            continue
        req.add(_expand_asset_macros(raw))

    # \GSCIncludeFigure[...]{...} or \GSCIncludeFigure{...}
    for m in re.finditer(r"\\GSCIncludeFigure(?:\[[^\]]*\])?\{([^}]*)\}", tex):
        raw = m.group(1).strip()
        if not raw:
            continue
        req.add(_expand_asset_macros(raw))

    # Normalize slashes and strip accidental braces/spaces.
    out: set[str] = set()
    for p in req:
        p = p.strip()
        # Remove any surrounding quotes (defensive).
        p = p.strip("\"'")
        out.add(PurePosixPath(p).as_posix())
    return out


def _safe_extract_zip(zip_path: Path, out_dir: Path) -> None:
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            name = info.filename
            if not name:
                continue
            if _is_absolute_zip_name(name):
                _fail(f"zip entry has absolute path: {name!r}")
            if _has_path_traversal(name):
                _fail(f"zip entry contains path traversal '..': {name!r}")

            parts = PurePosixPath(name).parts
            dest = out_dir.joinpath(*parts)
            if name.endswith("/"):
                dest.mkdir(parents=True, exist_ok=True)
                continue

            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info, "r") as src, dest.open("wb") as dst:
                shutil.copyfileobj(src, dst)


def _smoke_compile(zip_path: Path) -> None:
    pdflatex = shutil.which("pdflatex")
    if not pdflatex:
        _fail("pdflatex not found on PATH (cannot run --smoke-compile)")

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        _safe_extract_zip(zip_path, td)

        tex = td / "GSC_Framework_v10_1_FINAL.tex"
        if not tex.is_file():
            _fail("missing GSC_Framework_v10_1_FINAL.tex after extraction")

        cmd = [pdflatex, "-interaction=nonstopmode", "-halt-on-error", tex.name]
        r1 = subprocess.run(cmd, cwd=str(td), capture_output=True, text=True)
        if r1.returncode != 0:
            _fail(f"pdflatex pass1 failed:\n{(r1.stdout or '') + (r1.stderr or '')}".strip())
        r2 = subprocess.run(cmd, cwd=str(td), capture_output=True, text=True)
        if r2.returncode != 0:
            _fail(f"pdflatex pass2 failed:\n{(r2.stdout or '') + (r2.stderr or '')}".strip())

        pdf = td / "GSC_Framework_v10_1_FINAL.pdf"
        if not pdf.is_file():
            _fail("missing expected PDF after pdflatex")

        log = td / "GSC_Framework_v10_1_FINAL.log"
        log_text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
        bad_patterns = [
            "Package GSC Warning: Missing asset",
            "Package GSC Warning: Missing figure",
            "LaTeX Warning: File `paper_assets/",
        ]
        for pat in bad_patterns:
            if pat in log_text:
                _fail(f"smoke compile log contains missing-asset indicator: {pat!r}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="verify_submission_bundle",
        description="Verify a submission bundle zip (structure + path hygiene; optional pdflatex smoke compile).",
    )
    ap.add_argument(
        "zip_path",
        help="Path to submission_bundle_v10.1.1-late-time-r4.zip (local file).",
    )
    ap.add_argument(
        "--smoke-compile",
        action="store_true",
        help="If set, extract to a temp dir and run pdflatex twice (fails on missing-asset warnings).",
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

        for name in names:
            if _is_absolute_zip_name(name):
                _fail(f"zip entry has absolute path: {name!r}")
            if _has_path_traversal(name):
                _fail(f"zip entry contains path traversal '..': {name!r}")
            if _is_macos_junk(name):
                _fail(f"zip contains macOS junk entry: {name!r}")
            if _contains_docs_popular(name):
                _fail(f"zip contains docs/popular content (not allowed in submission bundle): {name!r}")

        tex_name = "GSC_Framework_v10_1_FINAL.tex"
        if tex_name not in names:
            _fail(f"missing {tex_name!r} at zip root")

        figures_prefix = "paper_assets/figures/"
        tables_prefix = "paper_assets/tables/"
        if not any(n.startswith(figures_prefix) and not n.endswith("/") for n in names):
            _fail(f"missing figures/ entries (expected under {figures_prefix!r})")
        if not any(n.startswith(tables_prefix) and not n.endswith("/") for n in names):
            _fail(f"missing tables/ entries (expected under {tables_prefix!r})")

        # Parse TeX and ensure referenced assets exist in the zip.
        try:
            tex_text = zf.read(tex_name).decode("utf-8")
        except Exception as e:
            _fail(f"failed to read {tex_name!r} as UTF-8: {e}")

        required_assets = _extract_required_assets_from_tex(tex_text)
        missing: list[str] = []
        names_set = set(names)
        for p in sorted(required_assets):
            if not p:
                continue
            # Assets must be relative and within paper_assets/.
            if _is_absolute_zip_name(p) or _has_path_traversal(p):
                _fail(f"TeX references unsafe asset path: {p!r}")
            if not (p == tex_name or p.startswith("paper_assets/")):
                # Be conservative: the submission bundle is intended to be self-contained under paper_assets/.
                _fail(f"TeX references asset outside paper_assets/: {p!r}")

            if p in names_set:
                continue
            # If TeX omits extension, allow common includegraphics extensions.
            if "." not in PurePosixPath(p).name:
                found = False
                for ext in (".png", ".pdf", ".jpg", ".jpeg"):
                    if (p + ext) in names_set:
                        found = True
                        break
                if found:
                    continue
            missing.append(p)

        if missing:
            _fail("missing TeX-referenced assets in zip:\n  " + "\n  ".join(missing))

        # Optional manifest hygiene.
        manifest_name = "paper_assets/manifest.json"
        if manifest_name in names_set:
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

    if args.smoke_compile:
        _smoke_compile(zip_path)

    print("OK: submission bundle verified")
    print(f"  zip: {zip_path}")
    print(f"  sha256: {sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

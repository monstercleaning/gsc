#!/usr/bin/env python3
"""Build deterministic arXiv-ready tar.gz bundle for Paper 2."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
from typing import Any, Dict, List, Mapping, Optional, Sequence

FAIL_MARKER = "PHASE4_MAKE_ARXIV_BUNDLE_PAPER2_FAILED"
SCHEMA = "phase4_paper2_arxiv_bundle_summary_v1"
FIXED_MTIME = 946684800


class UsageError(Exception):
    """Invalid CLI usage."""


class BundleError(Exception):
    """Bundle build failure."""


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_pretty(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def _require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise BundleError(f"missing {label}: {path}")
    return path


def _run_checked(cmd: Sequence[str], cwd: Path, label: str) -> None:
    proc = subprocess.run(list(cmd), cwd=str(cwd), text=True, capture_output=True)
    if proc.returncode != 0:
        tail = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()[-1800:]
        raise BundleError(f"{label} failed (exit={proc.returncode}):\n{tail}")


def _compile_bbl(stage: Path) -> None:
    for exe in ("pdflatex", "bibtex"):
        if shutil.which(exe) is None:
            raise BundleError(f"{exe} not found on PATH")

    _run_checked(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"], stage, "pdflatex pass 1")
    aux_text = (stage / "main.aux").read_text(encoding="utf-8", errors="ignore")
    if "\\citation{" in aux_text:
        _run_checked(["bibtex", "main"], stage, "bibtex")
    else:
        # No citations in manuscript body: create deterministic empty bibliography.
        (stage / "main.bbl").write_text(
            "\\begin{thebibliography}{0}\n\\end{thebibliography}\n",
            encoding="utf-8",
        )
    _run_checked(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"], stage, "pdflatex pass 2")
    _run_checked(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"], stage, "pdflatex pass 3")

    _require_file(stage / "main.bbl", "main.bbl")


def _add_file(tf: tarfile.TarFile, src: Path, arcname: str) -> None:
    data = src.read_bytes()
    ti = tarfile.TarInfo(name=arcname)
    ti.size = len(data)
    ti.mtime = FIXED_MTIME
    ti.uid = 0
    ti.gid = 0
    ti.uname = ""
    ti.gname = ""
    ti.mode = 0o644
    tf.addfile(ti, fileobj=io.BytesIO(data))


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Create deterministic arXiv bundle for Paper 2.")
    ap.add_argument("--paper-dir", default="v11.0.0/papers/paper2_measurement_model_epsilon")
    ap.add_argument("--assets-dir", required=True)
    ap.add_argument("--out-tar", default="v11.0.0/paper_assets/paper2_arxiv_bundle.tar.gz")
    ap.add_argument("--compile-bbl", choices=("0", "1"), default="1")
    ap.add_argument("--include-bib", choices=("0", "1"), default="1")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = _parse_args(argv)
        paper_dir = Path(str(args.paper_dir)).expanduser().resolve()
        assets_dir = Path(str(args.assets_dir)).expanduser().resolve()
        out_tar = Path(str(args.out_tar)).expanduser().resolve()

        if not paper_dir.is_dir():
            raise UsageError(f"paper-dir not found: {paper_dir}")
        if not assets_dir.is_dir():
            raise UsageError(f"assets-dir not found: {assets_dir}")

        paper_tex = _require_file(paper_dir / "paper2.tex", "paper2.tex")
        paper_bib = _require_file(paper_dir / "paper2.bib", "paper2.bib")
        numbers_tex = _require_file(assets_dir / "numbers.tex", "numbers.tex")
        figures_src = assets_dir / "figures"
        if not figures_src.is_dir():
            raise BundleError(f"missing figures directory: {figures_src}")

        figure_files = sorted(p for p in figures_src.glob("*") if p.is_file() and p.suffix.lower() in {".png", ".pdf", ".jpg", ".jpeg"})
        if not figure_files:
            raise BundleError("no figure files found in assets-dir/figures")

        with tempfile.TemporaryDirectory(prefix="gsc_paper2_arxiv_stage_") as td:
            stage = Path(td) / "arxivSubmission"
            (stage / "figures").mkdir(parents=True, exist_ok=True)

            # arXiv-facing canonical names.
            shutil.copyfile(paper_tex, stage / "main.tex")
            shutil.copyfile(numbers_tex, stage / "numbers.tex")
            if str(args.include_bib) == "1":
                shutil.copyfile(paper_bib, stage / "paper2.bib")

            for fig in figure_files:
                shutil.copyfile(fig, stage / "figures" / fig.name)

            # copy optional local TeX support files
            for pattern in ("*.sty", "*.cls", "*.bst"):
                for extra in sorted(paper_dir.glob(pattern)):
                    shutil.copyfile(extra, stage / extra.name)

            if str(args.compile_bbl) == "1":
                _compile_bbl(stage)
            else:
                bbl = paper_dir / "main.bbl"
                if bbl.is_file():
                    shutil.copyfile(bbl, stage / "main.bbl")
                else:
                    raise BundleError("--compile-bbl 0 requested but main.bbl not present in paper-dir")

            readme = (
                "Paper 2 arXiv submission bundle\n"
                "- main.tex + main.bbl included\n"
                "- numbers.tex + figures/ from deterministic asset build\n"
                "- Generated by phase4_make_arxiv_bundle_paper2.py\n"
            )
            (stage / "00README").write_text(readme, encoding="utf-8")

            # Remove local build noise from staged directory.
            for pattern in ("*.aux", "*.log", "*.blg", "*.out", "*.toc", "*.fdb_latexmk", "*.fls", "main.pdf"):
                for p in stage.glob(pattern):
                    p.unlink(missing_ok=True)

            members_for_tar: List[str] = []
            for p in sorted(stage.rglob("*")):
                if p.is_file():
                    members_for_tar.append(p.relative_to(stage).as_posix())

            out_tar.parent.mkdir(parents=True, exist_ok=True)
            with out_tar.open("wb") as raw:
                with gzip.GzipFile(fileobj=raw, mode="wb", mtime=FIXED_MTIME) as gz:
                    with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tf:
                        for rel in members_for_tar:
                            _add_file(tf, stage / rel, rel)

        # produce summary after bundle is closed
        members: List[Dict[str, Any]] = []
        with gzip.open(out_tar, "rb") as gz:
            with tarfile.open(fileobj=gz, mode="r:") as tf:
                for m in sorted(tf.getmembers(), key=lambda x: x.name):
                    if m.isfile():
                        members.append({"name": m.name, "bytes": int(m.size)})

        payload: Dict[str, Any] = {
            "schema": SCHEMA,
            "bundle": {
                "filename": out_tar.name,
                "sha256": _sha256_file(out_tar),
                "bytes": int(out_tar.stat().st_size),
            },
            "members": members,
            "paths_redacted": True,
        }

        if args.format == "json":
            print(_json_pretty(payload), end="")
        else:
            print(f"schema={SCHEMA}")
            print(f"bundle={out_tar.name}")
            print(f"bundle_sha256={payload['bundle']['sha256']}")
            print("members:")
            for row in members:
                print(f"  - {row['name']} ({row['bytes']} bytes)")
        return 0

    except (UsageError, BundleError) as exc:
        print(f"{FAIL_MARKER}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

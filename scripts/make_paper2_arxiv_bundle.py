#!/usr/bin/env python3
"""Create deterministic arXiv bundle for Paper-2 draft and run preflight checks."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import zipfile
from typing import Any, Dict, Mapping, Optional, Sequence


SCHEMA = "phase4_paper2_arxiv_bundle_manifest_v1"
FAIL_MARKER = "PHASE4_PAPER2_ARXIV_BUNDLE_FAILED"
DEFAULT_CREATED_UTC_EPOCH = 946684800


class UsageError(Exception):
    """CLI usage/configuration error."""


class BundleError(Exception):
    """Bundle build/preflight error."""


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_pretty(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def _to_iso_utc(epoch_seconds: int) -> str:
    dt = datetime.fromtimestamp(int(epoch_seconds), tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _zip_dir_deterministic(root_dir: Path, out_zip: Path) -> None:
    fixed_dt = (2000, 1, 1, 0, 0, 0)
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for p in sorted(root_dir.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(root_dir).as_posix()
            data = p.read_bytes()
            info = zipfile.ZipInfo(filename=rel, date_time=fixed_dt)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (0o100644 & 0xFFFF) << 16
            zf.writestr(info, data)


def _copy_if_exists(src: Path, dst: Path) -> bool:
    if not src.is_file():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    return True


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Build deterministic arXiv bundle for Paper-2 and run preflight checks.")
    ap.add_argument("--repo-root", default="v11.0.0")
    ap.add_argument("--paper-dir", default="papers/paper2_measurement_model_epsilon")
    ap.add_argument("--artifacts-dir", default="artifacts/paper2")
    ap.add_argument("--out-zip", default="paper_assets/paper2_arxiv_bundle.zip")
    ap.add_argument("--created-utc", type=int, default=DEFAULT_CREATED_UTC_EPOCH)
    ap.add_argument("--format", choices=("text", "json"), default="text")
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = _parse_args(argv)
        repo_root = Path(str(args.repo_root)).expanduser().resolve()
        if not repo_root.is_dir():
            raise UsageError(f"repo-root not found: {repo_root}")

        paper_dir = (repo_root / str(args.paper_dir)).resolve()
        artifacts_dir = (repo_root / str(args.artifacts_dir)).resolve()
        out_zip = (repo_root / str(args.out_zip)).resolve()
        created_epoch = int(args.created_utc)
        created_utc = _to_iso_utc(created_epoch)

        main_tex = paper_dir / "main.tex"
        refs_bib = paper_dir / "refs.bib"
        if not main_tex.is_file() or not refs_bib.is_file():
            raise BundleError("paper2 source files missing (main.tex/refs.bib)")

        preflight_script = repo_root / "scripts" / "arxiv_preflight_check.py"
        if not preflight_script.is_file():
            raise BundleError("missing arxiv_preflight_check.py")

        with tempfile.TemporaryDirectory(prefix="gsc_paper2_bundle_") as td:
            td_path = Path(td)
            stage = td_path / "bundle"
            stage.mkdir(parents=True, exist_ok=True)

            # Primary paper files (kept under a source subfolder for provenance).
            src_dir = stage / "paper2_source"
            src_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(main_tex, src_dir / "main.tex")
            shutil.copyfile(refs_bib, src_dir / "refs.bib")
            _copy_if_exists(paper_dir / "README.md", src_dir / "README.md")

            # TeX/bib files used directly by arXiv preflight/main compile path.
            shutil.copyfile(refs_bib, stage / "refs.bib")

            # Compatibility copy for existing preflight checks.
            shutil.copyfile(main_tex, stage / "GSC_Framework_v10_1_FINAL.tex")

            # Figures for paper text + compatibility paper_assets tree.
            fig_stage = stage / "figures"
            fig_stage.mkdir(parents=True, exist_ok=True)
            compat_fig = stage / "paper_assets" / "figures"
            compat_fig.mkdir(parents=True, exist_ok=True)
            compat_tbl = stage / "paper_assets" / "tables"
            compat_tbl.mkdir(parents=True, exist_ok=True)

            figure_names = ("epsilon_posterior_1d.png", "omega_m_vs_epsilon.png", "bao_rd_degeneracy.png", "joint_corner_or_equivalent.png")
            copied_figures = []
            for name in figure_names:
                src = paper_dir / "figures" / name
                if not src.is_file():
                    src = artifacts_dir / name
                if src.is_file():
                    shutil.copyfile(src, fig_stage / name)
                    shutil.copyfile(src, compat_fig / name)
                    copied_figures.append(name)

            # Include compact JSON summaries as table assets.
            table_candidates = (
                "sn_epsilon_posterior_summary.json",
                "bao_leg_summary.json",
                "sn_bao_joint_summary.json",
                "artifacts_manifest.json",
            )
            copied_tables = []
            for name in table_candidates:
                src = artifacts_dir / name
                if src.is_file():
                    shutil.copyfile(src, compat_tbl / name)
                    copied_tables.append(name)

            readme_text = (
                "# Paper2 arXiv bundle\n\n"
                "This bundle is generated deterministically by make_paper2_arxiv_bundle.py.\n"
                "It contains `main.tex` and `refs.bib` plus compact figures/tables from `artifacts/paper2`.\n"
            )
            (stage / "SUBMISSION_README.md").write_text(readme_text, encoding="utf-8")

            compat_manifest = {
                "schema": SCHEMA,
                "created_utc": created_utc,
                "created_utc_epoch": created_epoch,
                "figures": sorted(copied_figures),
                "tables": sorted(copied_tables),
            }
            (stage / "paper_assets" / "manifest.json").write_text(_json_pretty(compat_manifest), encoding="utf-8")

            _zip_dir_deterministic(stage, out_zip)

            preflight_json = td_path / "preflight.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(preflight_script),
                    str(out_zip),
                    "--skip-full-compile",
                    "--json",
                    str(preflight_json),
                ],
                cwd=str(repo_root.parent),
                text=True,
                capture_output=True,
            )
            if proc.returncode != 0:
                msg = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
                raise BundleError(f"arxiv_preflight_check failed: {msg[-800:]}")

            preflight_payload = json.loads(preflight_json.read_text(encoding="utf-8"))
            if str(preflight_payload.get("result")) != "PASS":
                raise BundleError("arxiv_preflight_check returned non-PASS result")

        out_payload: Dict[str, Any] = {
            "schema": SCHEMA,
            "created_utc": created_utc,
            "created_utc_epoch": created_epoch,
            "bundle": {
                "filename": out_zip.name,
                "sha256": _sha256_file(out_zip),
                "bytes": int(out_zip.stat().st_size),
            },
            "paths_redacted": True,
        }

        if str(args.format) == "json":
            print(_json_pretty(out_payload), end="")
        else:
            print(f"schema={SCHEMA}")
            print(f"bundle={out_zip.name}")
            print(f"sha256={out_payload['bundle']['sha256']}")
            print("preflight=PASS")
        return 0

    except (UsageError, BundleError) as exc:
        print(f"{FAIL_MARKER}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

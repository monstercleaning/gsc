#!/usr/bin/env python3
"""One-button operator workflow with optional canonical-asset fetch."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Sequence

from bundle_tex_drift_detector import compare_bundle_tex_vs_repo
from _outdir import resolve_outdir, resolve_path_under_outdir
import verify_all_canonical_artifacts as verify_all


V101_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V101_DIR))
from gsc.early_time.params import early_time_params_from_namespace  # noqa: E402


SCRIPTS_DIR = Path(__file__).resolve().parent
DEFAULT_CATALOG = V101_DIR / "canonical_artifacts.json"
REQUIRED_KEYS = ("submission", "referee_pack", "toe_bundle")
ALL_CANONICAL_KEYS = ("late_time", "submission", "referee_pack", "toe_bundle")
UPLOAD_LAYOUT = {
    "late_time": "late_time",
    "submission": "arxiv",
    "referee_pack": "referee_pack",
    "toe_bundle": "toe",
}


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class StepResult:
    name: str
    cmd: List[str]
    exit_code: int
    status: str
    started_utc: str
    finished_utc: str
    duration_sec: float


def _load_entries(catalog_path: Path) -> Dict[str, Dict[str, str]]:
    catalog = verify_all.load_catalog(catalog_path)
    artifacts = catalog.get("artifacts")
    if not isinstance(artifacts, dict):
        raise verify_all.CatalogError("catalog.artifacts must be an object")
    out: Dict[str, Dict[str, str]] = {}
    for key in ("late_time", "submission", "referee_pack", "toe_bundle"):
        rec = artifacts.get(key)
        if not isinstance(rec, dict):
            raise verify_all.CatalogError(f"missing artifacts.{key}")
        out[key] = {k: str(rec[k]) for k in ("tag", "asset", "sha256", "release_url")}
    return out


def _snapshot(entries: Dict[str, Dict[str, str]], artifacts_dir: Path) -> List[Dict[str, Any]]:
    snap: List[Dict[str, Any]] = []
    for key in ("late_time", "submission", "referee_pack", "toe_bundle"):
        rec = entries[key]
        resolved = verify_all._resolve_asset_path(artifacts_dir, rec["asset"])
        snap.append(
            {
                "id": key,
                "tag": rec["tag"],
                "asset": rec["asset"],
                "sha256": rec["sha256"],
                "release_url": rec["release_url"],
                "resolved_path": str(resolved),
                "exists": resolved.is_file(),
            }
        )
    return snap


def _snapshot_with_integrity(
    entries: Dict[str, Dict[str, str]],
    artifacts_dir: Path,
    before_exists: Dict[str, bool] | None = None,
) -> List[Dict[str, Any]]:
    rows = _snapshot(entries, artifacts_dir)
    for row in rows:
        exists = bool(row["exists"])
        actual_sha: str | None = None
        sha_match: bool | None = None
        resolved = Path(str(row["resolved_path"]))
        if exists:
            try:
                actual_sha = verify_all._sha256_file(resolved)
                sha_match = actual_sha == str(row["sha256"])
            except Exception:
                actual_sha = None
                sha_match = None
        row["sha256_actual"] = actual_sha
        row["sha256_match"] = sha_match
        row["status"] = "present" if exists else "missing"
        if before_exists is not None:
            prev = bool(before_exists.get(str(row["id"]), False))
            row["present_before_fetch"] = prev
            row["present_after_fetch"] = exists
            row["fetched_during_run"] = (not prev) and exists
    return rows


def _missing_required(snapshot: List[Dict[str, Any]], required_keys: Sequence[str] = REQUIRED_KEYS) -> List[Dict[str, Any]]:
    wanted = set(required_keys)
    return [row for row in snapshot if row["id"] in wanted and not row["exists"]]


def _has_files(root: Path) -> bool:
    return any(p.is_file() for p in root.rglob("*"))


def _paper_assets_ready(assets_dir: Path) -> bool:
    figures = assets_dir / "figures"
    tables = assets_dir / "tables"
    return figures.is_dir() and tables.is_dir() and _has_files(figures) and _has_files(tables)


def _is_unsafe_zip_entry(name: str) -> bool:
    if name.startswith(("/", "\\")):
        return True
    if len(name) >= 3 and name[1] == ":" and name[2] in ("/", "\\"):
        return True
    try:
        parts = PurePosixPath(name).parts
    except Exception:
        return True
    return any(part == ".." for part in parts)


def _materialize_paper_assets_from_release_zip(late_time_zip: Path, assets_dir: Path) -> int:
    copied = 0
    with zipfile.ZipFile(late_time_zip, "r") as zf:
        names = [zi.filename for zi in zf.infolist() if zi.filename and not zi.filename.endswith("/")]
        has_root_prefix = any(n.startswith("paper_assets/") for n in names)

        for zi in zf.infolist():
            name = zi.filename
            if not name or name.endswith("/"):
                continue
            if _is_unsafe_zip_entry(name):
                raise RuntimeError(f"unsafe zip entry in late-time asset: {name!r}")

            rel = name
            if has_root_prefix:
                if not name.startswith("paper_assets/"):
                    continue
                rel = name[len("paper_assets/") :]
                if not rel:
                    continue

            rel_posix = PurePosixPath(rel).as_posix()
            if rel_posix == "manifest.json":
                pass
            elif not (rel_posix.startswith("figures/") or rel_posix.startswith("tables/")):
                continue

            if _is_unsafe_zip_entry(rel_posix):
                raise RuntimeError(f"unsafe relative path in late-time asset: {rel_posix!r}")

            dest = assets_dir.joinpath(*PurePosixPath(rel_posix).parts)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(zi, "r") as src, dest.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            copied += 1
    return copied


def _ensure_paper_assets(
    entries: Dict[str, Dict[str, str]],
    artifacts_dir: Path,
    steps: List[StepResult],
) -> int:
    name = "prepare_paper_assets"
    assets_dir = V101_DIR / "paper_assets"
    late_time_zip = verify_all._resolve_asset_path(artifacts_dir, entries["late_time"]["asset"])
    cmd = [
        "materialize",
        str(late_time_zip),
        "->",
        str(assets_dir),
    ]
    t0 = time.monotonic()
    started_utc = datetime.now(timezone.utc).isoformat()

    print(f"[step] {name}")
    print("  $ " + " ".join(cmd))

    if _paper_assets_ready(assets_dir):
        print(f"[ok] {name} (already present)")
        steps.append(
            StepResult(
                name=name,
                cmd=cmd,
                exit_code=0,
                status="PASS",
                started_utc=started_utc,
                finished_utc=datetime.now(timezone.utc).isoformat(),
                duration_sec=round(time.monotonic() - t0, 6),
            )
        )
        return 0

    if not late_time_zip.is_file():
        print(f"[fail] {name} (missing late_time zip)")
        print(f"Missing required late-time asset: {late_time_zip}")
        print(f"Expected sha256: {entries['late_time']['sha256']}")
        print("To fetch canonical artifacts:")
        print(
            "  bash v11.0.0/scripts/fetch_canonical_artifacts.sh "
            f"--artifacts-dir {shlex.quote(str(artifacts_dir))} --fetch-missing"
        )
        steps.append(
            StepResult(
                name=name,
                cmd=cmd,
                exit_code=2,
                status="FAIL",
                started_utc=started_utc,
                finished_utc=datetime.now(timezone.utc).isoformat(),
                duration_sec=round(time.monotonic() - t0, 6),
            )
        )
        return 2

    try:
        copied = _materialize_paper_assets_from_release_zip(late_time_zip, assets_dir)
    except Exception as exc:
        print(f"[fail] {name} ({exc})")
        steps.append(
            StepResult(
                name=name,
                cmd=cmd,
                exit_code=2,
                status="FAIL",
                started_utc=started_utc,
                finished_utc=datetime.now(timezone.utc).isoformat(),
                duration_sec=round(time.monotonic() - t0, 6),
            )
        )
        return 2

    if copied <= 0 or not _paper_assets_ready(assets_dir):
        print(f"[fail] {name} (paper_assets figures/tables not materialized)")
        steps.append(
            StepResult(
                name=name,
                cmd=cmd,
                exit_code=2,
                status="FAIL",
                started_utc=started_utc,
                finished_utc=datetime.now(timezone.utc).isoformat(),
                duration_sec=round(time.monotonic() - t0, 6),
            )
        )
        return 2

    print(f"[ok] {name} (copied {copied} files from canonical late-time zip)")
    steps.append(
        StepResult(
            name=name,
            cmd=cmd,
            exit_code=0,
            status="PASS",
            started_utc=started_utc,
            finished_utc=datetime.now(timezone.utc).isoformat(),
            duration_sec=round(time.monotonic() - t0, 6),
        )
    )
    return 0


def _run_step(name: str, cmd: Sequence[str], steps: List[StepResult]) -> int:
    cmd_list = [str(c) for c in cmd]
    t0 = time.monotonic()
    started_utc = datetime.now(timezone.utc).isoformat()
    print(f"[step] {name}")
    print("  $ " + " ".join(cmd_list))
    try:
        r = subprocess.run(cmd_list, capture_output=True, text=True)
    except FileNotFoundError as exc:
        print(f"[fail] {name} (missing tool: {exc})")
        steps.append(
            StepResult(
                name=name,
                cmd=cmd_list,
                exit_code=127,
                status="FAIL",
                started_utc=started_utc,
                finished_utc=datetime.now(timezone.utc).isoformat(),
                duration_sec=round(time.monotonic() - t0, 6),
            )
        )
        return 127
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    if r.returncode == 0:
        print(f"[ok] {name}")
        steps.append(
            StepResult(
                name=name,
                cmd=cmd_list,
                exit_code=0,
                status="PASS",
                started_utc=started_utc,
                finished_utc=datetime.now(timezone.utc).isoformat(),
                duration_sec=round(time.monotonic() - t0, 6),
            )
        )
        return 0
    print(f"[fail] {name} (rc={r.returncode})")
    if out:
        print(out)
    steps.append(
        StepResult(
            name=name,
            cmd=cmd_list,
            exit_code=r.returncode,
            status="FAIL",
            started_utc=started_utc,
            finished_utc=datetime.now(timezone.utc).isoformat(),
            duration_sec=round(time.monotonic() - t0, 6),
        )
    )
    return r.returncode


def _tool_version(cmd: Sequence[str]) -> str:
    try:
        r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    except Exception:
        return "not-found"
    if r.returncode != 0:
        return "not-found"
    text = ((r.stdout or "") + (r.stderr or "")).strip()
    if not text:
        return "unknown"
    return text.splitlines()[0]


def _print_missing(missing: Sequence[Dict[str, Any]], artifacts_dir: Path) -> None:
    def _download_url(row: Dict[str, Any]) -> str | None:
        release = str(row.get("release_url", ""))
        tag = str(row.get("tag", ""))
        asset = str(row.get("asset", ""))
        marker = "/releases/tag/"
        if marker not in release:
            return None
        prefix = release.split(marker, 1)[0]
        if not prefix:
            return None
        return f"{prefix}/releases/download/{tag}/{asset}"

    if not missing:
        return
    print("Missing required canonical artifacts:")
    for row in missing:
        print(f"- {row['id']}: {row['asset']}")
        print(f"  expected_sha256: {row['sha256']}")
        print(f"  tag: {row['tag']}")
        print(f"  release: {row['release_url']}")
        print(f"  looked_at: {row['resolved_path']}")
        durl = _download_url(row)
        if durl:
            print(f"  direct_download_url: {durl}")
            print(f"  curl_cmd: curl -fL --retry 3 --retry-delay 2 -o {shlex.quote(str(row['resolved_path']))} {shlex.quote(durl)}")
            print(f"  verify_cmd: shasum -a 256 {shlex.quote(str(row['resolved_path']))}")
    print("To fetch missing artifacts:")
    print(
        "  bash v11.0.0/scripts/fetch_canonical_artifacts.sh "
        f"--artifacts-dir {shlex.quote(str(artifacts_dir))} --fetch-missing"
    )


def _stage_file(src: Path, dst: Path, mode: str) -> str:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if mode == "copy":
        shutil.copy2(src, dst)
        return "copy"
    if mode == "hardlink":
        try:
            os.link(src, dst)
            return "hardlink"
        except OSError:
            shutil.copy2(src, dst)
            return "copy-fallback"
    raise ValueError(f"unknown upload mode: {mode}")


def _build_upload_readme(
    *,
    entries: Dict[str, Dict[str, str]],
    staged_artifacts: List[Dict[str, Any]],
    pdf_from_submission_bundle: bool,
    pdf_warning: str | None,
) -> str:
    rel_by_key = {str(a["id"]): str(a["staged_relpath"]) for a in staged_artifacts}
    lines = [
        "# Upload Portal (Canonical artifacts)",
        "",
        "This directory is generated from `v11.0.0/canonical_artifacts.json`.",
        "",
        "## What to upload",
        f"- arXiv/journal source upload: `{rel_by_key['submission']}`",
        "",
        "## Suggested upload order",
        "1. Upload `arxiv/` submission source zip to arXiv/journal.",
        "2. Share `referee_pack/` with editor/referees (separate channel).",
        "3. Keep `late_time/` for archival provenance checks.",
        "4. Keep `toe/` separate; do not attach to submission packages.",
        "",
        "## Keep separate (do not upload with submission source)",
        f"- Referee pack: `{rel_by_key['referee_pack']}`",
        f"- ToE bundle: `{rel_by_key['toe_bundle']}`",
        f"- Late-time canonical assets archive: `{rel_by_key['late_time']}`",
        "",
        "## Verify checksums",
        "```bash",
        "cd \"$(dirname \"$0\")\"",
        "shasum -a 256 -c checksums/SHA256SUMS.txt",
        "```",
        "",
        "## Canonical artifacts",
        "",
        "| id | filename | expected_sha256 | canonical tag | release |",
        "|---|---|---|---|---|",
    ]
    for key in ALL_CANONICAL_KEYS:
        rec = entries[key]
        rel = rel_by_key[key]
        lines.append(
            f"| `{key}` | `{rel}` | `{rec['sha256']}` | `{rec['tag']}` | {rec['release_url']} |"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "- `toe/` is NOT part of submission uploads.",
            "- `referee_pack/` is shared separately with editors/referees.",
        ]
    )
    if pdf_from_submission_bundle:
        lines.append("- `late_time/GSC_Framework_v10_1_FINAL.pdf` is compiled from canonical submission bundle TeX.")
        lines.append("- `late_time/PDF_PROVENANCE.txt` records source zip + SHA + produced PDF SHA.")
    else:
        lines.append("- No staged PDF: submission-bundle compile PDF was unavailable in this run.")
        if pdf_warning:
            lines.append(f"- Reason: {pdf_warning}")
    lines.append("")
    return "\n".join(lines)


def _build_portal_checklist(entries: Dict[str, Dict[str, str]]) -> str:
    sub_asset = entries["submission"]["asset"]
    ref_asset = entries["referee_pack"]["asset"]
    toe_asset = entries["toe_bundle"]["asset"]
    return "\n".join(
        [
            "# Publish Checklist (Upload Portal)",
            "",
            "## Upload targets",
            f"- arXiv source upload: `arxiv/{entries['submission']['asset']}`",
            f"- Referee material (separate): `referee_pack/{entries['referee_pack']['asset']}`",
            f"- ToE package (separate): `toe/{entries['toe_bundle']['asset']}`",
            f"- Late-time archive: `late_time/{entries['late_time']['asset']}` plus `late_time/GSC_Framework_v10_1_FINAL.pdf` when present",
            "",
            "## Critical warning",
            "- Upload ONLY `arxiv/submission_bundle_*.zip` to arXiv.",
            "- Do NOT upload `referee_pack/` or `toe/` to arXiv.",
            "",
            "## Verify checksums",
            "```bash",
            "cd \"$(dirname \"$0\")\"",
            "shasum -a 256 -c checksums/SHA256SUMS.txt",
            "```",
            "",
            "## Verify canonical bundles (optional)",
            "```bash",
            f"bash v11.0.0/scripts/verify_submission_bundle.sh --smoke-compile arxiv/{sub_asset}",
            f"bash v11.0.0/scripts/verify_referee_pack.sh referee_pack/{ref_asset}",
            f"bash v11.0.0/scripts/verify_toe_bundle.sh toe/{toe_asset}",
            "```",
            "",
        ]
    )


def _write_json_file(path: Path, payload: Dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return str(path)


def _build_reports_readme() -> str:
    return "\n".join(
        [
            "# Reports",
            "",
            "- `operator_report.json`: full operator workflow report (overall status, steps, durations).",
            "- `rc_check.json`: release-candidate checker output with nested verifier details.",
            "- `arxiv_preflight.json`: publication-grade submission-bundle preflight output.",
            "- `cmb_priors_report.json`: early-time CMB priors batch report (when generated in this run).",
            "- `cmb_priors_table.csv`: early-time CMB priors flat table (when generated in this run).",
            "- `numerics_invariants_report.json`: early-time numerics invariants QA report (when generated in this run).",
            "",
            "Status interpretation:",
            "- `PASS`: no blocking errors.",
            "- `WARN`: non-blocking warnings; review before external upload.",
            "- `FAIL`: blocking issue; do not upload until fixed.",
            "",
        ]
    )


def _rewrite_portal_checksums(upload_root: Path) -> str:
    checksums_dir = upload_root / "checksums"
    checksums_dir.mkdir(parents=True, exist_ok=True)
    checksum_file = checksums_dir / "SHA256SUMS.txt"

    rows: List[str] = []
    for src in sorted((p for p in upload_root.rglob("*") if p.is_file()), key=lambda p: p.relative_to(upload_root).as_posix()):
        rel = src.relative_to(upload_root).as_posix()
        if rel == "checksums/SHA256SUMS.txt":
            continue
        if rel.startswith("__MACOSX/") or rel.endswith(".DS_Store") or "/._" in rel or rel.startswith("._"):
            continue
        rows.append(f"{_sha256_file(src)}  {rel}")

    checksum_file.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return str(checksum_file)


def _prepare_upload_portal(
    *,
    entries: Dict[str, Dict[str, str]],
    artifacts_dir: Path,
    upload_dir: Path,
    mode: str,
    compile_pdf: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    if mode not in ("copy", "hardlink"):
        raise RuntimeError(f"unsupported upload mode: {mode}")

    if upload_dir.exists():
        if not upload_dir.is_dir():
            raise RuntimeError(f"upload path exists and is not a directory: {upload_dir}")
        if any(upload_dir.iterdir()):
            raise RuntimeError(f"upload directory already exists and is not empty: {upload_dir}")

    upload_dir.parent.mkdir(parents=True, exist_ok=True)
    tmp_root = Path(tempfile.mkdtemp(prefix=f".{upload_dir.name}.tmp-", dir=str(upload_dir.parent)))

    staged_relpaths: Dict[str, str] = {}
    staged_methods: Dict[str, str] = {}
    staged_artifacts: List[Dict[str, Any]] = []
    pdf_from_submission_bundle = False
    pdf_warning: str | None = None
    staged_pdf_sha256 = ""
    staged_pdf_relpath = ""
    staged_pdf_provenance_relpath = ""

    try:
        for key in ALL_CANONICAL_KEYS:
            rec = entries[key]
            src = verify_all._resolve_asset_path(artifacts_dir, rec["asset"])
            if not src.is_file():
                raise RuntimeError(f"missing canonical artifact for upload portal: {key} -> {src}")
            got = verify_all._sha256_file(src)
            expected = rec["sha256"].lower()
            if got.lower() != expected:
                raise RuntimeError(
                    f"sha256 mismatch for {key}: expected {expected}, got {got} ({src})"
                )

            subdir = UPLOAD_LAYOUT[key]
            dst = tmp_root / subdir / src.name
            method = _stage_file(src, dst, mode)
            rel = dst.relative_to(tmp_root).as_posix()
            staged_relpaths[key] = rel
            staged_methods[key] = method
            staged_artifacts.append(
                {
                    "id": key,
                    "asset": rec["asset"],
                    "staged_relpath": rel,
                    "expected_sha256": expected,
                    "actual_sha256": got.lower(),
                    "sha_match": got.lower() == expected,
                    "tag": rec["tag"],
                    "release_url": rec["release_url"],
                    "stage_method": method,
                }
            )

        if isinstance(compile_pdf, dict) and bool(compile_pdf.get("produced")):
            raw_pdf_path = str(compile_pdf.get("path") or "").strip()
            expected_pdf_sha = str(compile_pdf.get("sha256") or "").strip().lower()
            pdf_path = Path(raw_pdf_path).expanduser().resolve() if raw_pdf_path else None
            if pdf_path and pdf_path.is_file():
                got_pdf_sha = _sha256_file(pdf_path).lower()
                if expected_pdf_sha and got_pdf_sha != expected_pdf_sha:
                    pdf_warning = (
                        "submission-bundle compile PDF sha256 mismatch: "
                        f"expected {expected_pdf_sha}, got {got_pdf_sha}"
                    )
                else:
                    staged_pdf = tmp_root / "late_time" / "GSC_Framework_v10_1_FINAL.pdf"
                    _stage_file(pdf_path, staged_pdf, mode)
                    pdf_from_submission_bundle = True
                    staged_pdf_sha256 = got_pdf_sha
                    staged_pdf_relpath = staged_pdf.relative_to(tmp_root).as_posix()

                    prov = tmp_root / "late_time" / "PDF_PROVENANCE.txt"
                    prov.write_text(
                        "\n".join(
                            [
                                f"timestamp_utc={datetime.now(timezone.utc).isoformat()}",
                                f"source_submission_asset={entries['submission']['asset']}",
                                f"source_submission_sha256={entries['submission']['sha256']}",
                                f"compiled_pdf_sha256={staged_pdf_sha256}",
                                f"main_tex={compile_pdf.get('main_tex', 'GSC_Framework_v10_1_FINAL.tex')}",
                                f"bib_mode={compile_pdf.get('bib_mode', 'unknown')}",
                                "note=Compiled from canonical submission bundle; not from repo working tree.",
                                "",
                            ]
                        ),
                        encoding="utf-8",
                    )
                    staged_pdf_provenance_relpath = prov.relative_to(tmp_root).as_posix()
            else:
                pdf_warning = (
                    "submission-bundle compile PDF path is missing; "
                    f"path={raw_pdf_path!r}"
                )
        else:
            pdf_warning = "submission-bundle compile PDF unavailable (preflight did not emit compile_pdf artifact)"

        order = {k: i for i, k in enumerate(ALL_CANONICAL_KEYS)}
        staged_artifacts.sort(key=lambda a: order.get(str(a["id"]), 999))

        readme = _build_upload_readme(
            entries=entries,
            staged_artifacts=staged_artifacts,
            pdf_from_submission_bundle=pdf_from_submission_bundle,
            pdf_warning=pdf_warning,
        )
        (tmp_root / "README_UPLOAD.md").write_text(readme, encoding="utf-8")
        (tmp_root / "CHECKLIST_PUBLISH.md").write_text(_build_portal_checklist(entries), encoding="utf-8")

        _rewrite_portal_checksums(tmp_root)

        if upload_dir.exists() and not any(upload_dir.iterdir()):
            upload_dir.rmdir()
        os.replace(tmp_root, upload_dir)
    except Exception:
        shutil.rmtree(tmp_root, ignore_errors=True)
        raise

    return {
        "path": str(upload_dir),
        "mode": mode,
        "files": staged_relpaths,
        "artifacts": staged_artifacts,
        "stage_methods": staged_methods,
        "checksums_file": str((upload_dir / "checksums" / "SHA256SUMS.txt")),
        "readme_file": str((upload_dir / "README_UPLOAD.md")),
        "checklist_file": str((upload_dir / "CHECKLIST_PUBLISH.md")),
        "included_pdf": pdf_from_submission_bundle,
        "pdf_from_submission_bundle": pdf_from_submission_bundle,
        "pdf_sha256": staged_pdf_sha256,
        "pdf_relpath": staged_pdf_relpath,
        "pdf_provenance_relpath": staged_pdf_provenance_relpath,
        "portal_warnings": [pdf_warning] if pdf_warning else [],
    }


def _prepare_upload_portal_step(
    *,
    entries: Dict[str, Dict[str, str]],
    artifacts_dir: Path,
    upload_dir: Path,
    mode: str,
    steps: List[StepResult],
    rc_check: Dict[str, Any] | None = None,
) -> tuple[int, Dict[str, Any] | None]:
    name = "prepare_upload_dir"
    cmd = [
        "prepare-upload-dir",
        str(upload_dir),
        f"--mode={mode}",
    ]
    t0 = time.monotonic()
    started_utc = datetime.now(timezone.utc).isoformat()
    print(f"[step] {name}")
    print("  $ " + " ".join(cmd))
    try:
        compile_pdf: Dict[str, Any] | None = None
        if isinstance(rc_check, dict):
            arxiv_payload = rc_check.get("arxiv_preflight")
            if isinstance(arxiv_payload, dict):
                cp = arxiv_payload.get("compile_pdf")
                if isinstance(cp, dict):
                    compile_pdf = cp
        info = _prepare_upload_portal(
            entries=entries,
            artifacts_dir=artifacts_dir,
            upload_dir=upload_dir,
            mode=mode,
            compile_pdf=compile_pdf,
        )
        print(f"[ok] {name} ({upload_dir})")
        steps.append(
            StepResult(
                name=name,
                cmd=cmd,
                exit_code=0,
                status="PASS",
                started_utc=started_utc,
                finished_utc=datetime.now(timezone.utc).isoformat(),
                duration_sec=round(time.monotonic() - t0, 6),
            )
        )
        return 0, info
    except Exception as exc:
        print(f"[fail] {name} ({exc})")
        steps.append(
            StepResult(
                name=name,
                cmd=cmd,
                exit_code=2,
                status="FAIL",
                started_utc=started_utc,
                finished_utc=datetime.now(timezone.utc).isoformat(),
                duration_sec=round(time.monotonic() - t0, 6),
            )
        )
        return 2, None


def _zip_upload_portal(upload_dir: Path, zip_path: Path) -> Dict[str, str]:
    if not upload_dir.is_dir():
        raise RuntimeError(f"upload portal directory does not exist: {upload_dir}")
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()
    files = [p for p in upload_dir.rglob("*") if p.is_file()]
    if not files:
        raise RuntimeError(f"upload portal directory has no files: {upload_dir}")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for src in sorted(files, key=lambda p: p.relative_to(upload_dir).as_posix()):
            rel = src.relative_to(upload_dir).as_posix()
            if rel.startswith("__MACOSX/") or rel.endswith(".DS_Store") or "/._" in rel or rel.startswith("._"):
                continue
            zf.write(src, rel)
    sha = _sha256_file(zip_path)
    sha_path = Path(str(zip_path) + ".sha256")
    sha_path.write_text(f"{sha}  {zip_path.name}\n", encoding="utf-8")
    return {"zip_path": str(zip_path), "sha256": sha, "sha256_file": str(sha_path)}


def _prepare_upload_zip_step(
    *,
    upload_portal: Dict[str, Any],
    upload_zip: Path,
    steps: List[StepResult],
) -> tuple[int, Dict[str, str] | None]:
    name = "prepare_upload_zip"
    cmd = [
        "prepare-upload-zip",
        str(upload_zip),
    ]
    t0 = time.monotonic()
    started_utc = datetime.now(timezone.utc).isoformat()
    print(f"[step] {name}")
    print("  $ " + " ".join(cmd))
    try:
        info = _zip_upload_portal(Path(str(upload_portal["path"])), upload_zip)
        print(f"[ok] {name} ({info['zip_path']})")
        print(f"  sha256: {info['sha256']}")
        steps.append(
            StepResult(
                name=name,
                cmd=cmd,
                exit_code=0,
                status="PASS",
                started_utc=started_utc,
                finished_utc=datetime.now(timezone.utc).isoformat(),
                duration_sec=round(time.monotonic() - t0, 6),
            )
        )
        return 0, info
    except Exception as exc:
        print(f"[fail] {name} ({exc})")
        steps.append(
            StepResult(
                name=name,
                cmd=cmd,
                exit_code=2,
                status="FAIL",
                started_utc=started_utc,
                finished_utc=datetime.now(timezone.utc).isoformat(),
                duration_sec=round(time.monotonic() - t0, 6),
            )
        )
        return 2, None


def _run_early_time_cmb_priors_report_step(
    *,
    fit_dir: Path,
    cmb_csv: Path,
    cmb_cov: Path | None,
    omega_b_h2: float,
    omega_c_h2: float,
    n_eff: float,
    tcmb_k: float,
    cmb_mode: str | None,
    cmb_bridge_z: float | None,
    out_root: Path,
    steps: List[StepResult],
) -> tuple[int, Dict[str, Any] | None]:
    report_json = (out_root / "early_time" / "cmb_priors_report.json").resolve()
    report_csv = (out_root / "early_time" / "cmb_priors_table.csv").resolve()
    invariants_json = (out_root / "early_time" / "numerics_invariants_report.json").resolve()
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "early_time_cmb_priors_report.py"),
        "--fit-dir",
        str(fit_dir),
        "--cmb",
        str(cmb_csv),
        "--omega-b-h2",
        f"{float(omega_b_h2):.16g}",
        "--omega-c-h2",
        f"{float(omega_c_h2):.16g}",
        "--Neff",
        f"{float(n_eff):.16g}",
        "--Tcmb-K",
        f"{float(tcmb_k):.16g}",
        "--out-dir",
        str(out_root),
        "--out",
        "early_time/cmb_priors_report.json",
        "--out-csv",
        "early_time/cmb_priors_table.csv",
        "--out-invariants",
        "early_time/numerics_invariants_report.json",
    ]
    if cmb_cov is not None:
        cmd.extend(["--cmb-cov", str(cmb_cov)])
    if cmb_mode is not None and cmb_mode.strip():
        cmd.extend(["--cmb-mode", str(cmb_mode)])
    if cmb_bridge_z is not None:
        cmd.extend(["--cmb-bridge-z", f"{float(cmb_bridge_z):.16g}"])

    rc = _run_step("early_time_cmb_priors_report", cmd, steps)
    if rc != 0:
        return rc, None
    info = {
        "json_path": str(report_json),
        "csv_path": str(report_csv),
        "invariants_path": str(invariants_json),
        "json_exists": report_json.is_file(),
        "csv_exists": report_csv.is_file(),
        "invariants_exists": invariants_json.is_file(),
    }
    return 0, info


def _run_release_candidate_check_step(
    *,
    catalog_path: Path,
    artifacts_dir: Path,
    out_root: Path,
    require_cmb_reports: bool = False,
    cmb_report_json: Path | None = None,
    cmb_report_csv: Path | None = None,
    require_early_time_invariants: bool = False,
    early_time_invariants_report: Path | None = None,
    require_derived_rd: bool = False,
    derived_rd_fit_dir: Path | None = None,
    steps: List[StepResult],
) -> tuple[int, Dict[str, Any] | None]:
    rc_json = (out_root / "rc_check" / "rc_check.json").resolve()
    rc_json.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "release_candidate_check.py"),
        "--catalog",
        str(catalog_path),
        "--artifacts-dir",
        str(artifacts_dir),
        "--out-dir",
        str(out_root),
        "--json",
        str(rc_json),
    ]
    if require_cmb_reports:
        cmd.append("--require-cmb-reports")
    if cmb_report_json is not None:
        cmd.extend(["--cmb-report-json", str(cmb_report_json)])
    if cmb_report_csv is not None:
        cmd.extend(["--cmb-report-csv", str(cmb_report_csv)])
    if require_early_time_invariants:
        cmd.append("--require-early-time-invariants")
    if early_time_invariants_report is not None:
        cmd.extend(["--early-time-invariants-report", str(early_time_invariants_report)])
    if require_derived_rd:
        cmd.append("--require-derived-rd")
    if derived_rd_fit_dir is not None:
        cmd.extend(["--derived-rd-fit-dir", str(derived_rd_fit_dir)])
    rc = _run_step("release_candidate_check", cmd, steps)
    payload: Dict[str, Any] | None = None
    if rc_json.is_file():
        try:
            payload = json.loads(rc_json.read_text(encoding="utf-8"))
        except Exception:
            payload = {"error": "failed to parse release_candidate_check JSON payload"}
    return rc, payload


def _run_bundle_vs_repo_tex_check(entries: Dict[str, Dict[str, str]], artifacts_dir: Path) -> Dict[str, Any]:
    print("[step] bundle_vs_repo_tex_drift")
    submission_zip = verify_all._resolve_asset_path(artifacts_dir, entries["submission"]["asset"])
    repo_tex = V101_DIR / "GSC_Framework_v10_1_FINAL.tex"
    result = compare_bundle_tex_vs_repo(submission_zip, repo_tex)
    if result.get("match"):
        print("[ok] bundle_vs_repo_tex_drift")
        print(f"  sha_bundle: {result.get('sha_bundle')}")
        print(f"  sha_repo:   {result.get('sha_repo')}")
    else:
        print("[warn] bundle_vs_repo_tex_drift")
        if result.get("warning"):
            print(f"  warning: {result['warning']}")
        print(f"  sha_bundle: {result.get('sha_bundle')}")
        print(f"  sha_repo:   {result.get('sha_repo')}")
        for cmd in result.get("hint_cmds", []):
            print(f"  hint: {cmd}")
    return result


def _write_operator_summary_file(
    *,
    upload_portal: Dict[str, Any],
    result: str,
    steps: List[StepResult],
    snapshot: List[Dict[str, Any]],
    warnings: List[str],
    rc_check: Dict[str, Any] | None = None,
    reports_staged: Dict[str, bool] | None = None,
) -> str:
    root = Path(str(upload_portal["path"]))
    out = root / "REPORT_OPERATOR_SUMMARY.txt"
    total_duration = round(sum(float(s.duration_sec) for s in steps), 6)
    art_by_id = {str(a["id"]): a for a in upload_portal.get("artifacts", [])}
    snap_by_id = {str(s["id"]): s for s in snapshot}
    lines = [
        f"overall_status={result}",
        f"step_count={len(steps)} pass_count={sum(1 for s in steps if s.status == 'PASS')} fail_count={sum(1 for s in steps if s.status != 'PASS')}",
        f"duration_sec_total={total_duration}",
        "",
        "staged_artifacts:",
    ]
    for key in ALL_CANONICAL_KEYS:
        a = art_by_id.get(key, {})
        s = snap_by_id.get(key, {})
        lines.append(
            (
                f"- id={key} file={a.get('staged_relpath','n/a')} "
                f"expected_sha256={a.get('expected_sha256', s.get('sha256','n/a'))} "
                f"actual_sha256={a.get('actual_sha256', s.get('sha256_actual','n/a'))} "
                f"sha_match={a.get('sha_match', s.get('sha256_match','n/a'))}"
            )
        )
    lines.extend(["", "warnings:"])
    if warnings:
        for w in warnings:
            lines.append(f"- {w}")
    else:
        lines.append("- none")
    arxiv_preflight = None
    if isinstance(rc_check, dict):
        arxiv_preflight = rc_check.get("arxiv_preflight")
    if isinstance(arxiv_preflight, dict):
        arxiv_result = str(arxiv_preflight.get("result", "UNKNOWN"))
        arxiv_warnings = arxiv_preflight.get("warnings") or []
        first_warn = str(arxiv_warnings[0]) if arxiv_warnings else ""
        lines.extend(
            [
                "",
                f"arxiv_preflight={arxiv_result}" + (f" ({first_warn})" if first_warn else ""),
            ]
        )
    pdf_from_submission_bundle = bool(upload_portal.get("pdf_from_submission_bundle"))
    lines.append("")
    lines.append(f"pdf_from_submission_bundle={'yes' if pdf_from_submission_bundle else 'no'}")
    if pdf_from_submission_bundle:
        if upload_portal.get("pdf_sha256"):
            lines.append(f"pdf_sha256={upload_portal.get('pdf_sha256')}")
        if upload_portal.get("pdf_relpath"):
            lines.append(f"pdf_relpath={upload_portal.get('pdf_relpath')}")
        if upload_portal.get("pdf_provenance_relpath"):
            lines.append(f"pdf_provenance={upload_portal.get('pdf_provenance_relpath')}")
    lines.extend(["", "reports_staged:"])
    reports_staged = reports_staged or {}
    lines.append(f"- operator_report.json={'yes' if reports_staged.get('operator_report', False) else 'no'}")
    lines.append(f"- rc_check.json={'yes' if reports_staged.get('rc_check', False) else 'no'}")
    lines.append(f"- arxiv_preflight.json={'yes' if reports_staged.get('arxiv_preflight', False) else 'no'}")
    lines.append(f"- cmb_priors_report.json={'yes' if reports_staged.get('cmb_priors_report', False) else 'no'}")
    lines.append(f"- cmb_priors_table.csv={'yes' if reports_staged.get('cmb_priors_table', False) else 'no'}")
    lines.append(
        f"- numerics_invariants_report.json={'yes' if reports_staged.get('numerics_invariants_report', False) else 'no'}"
    )
    portal_zip = upload_portal.get("portal_zip")
    if isinstance(portal_zip, dict):
        lines.extend(
            [
                "",
                "upload_portal_zip:",
                f"- zip_path={portal_zip.get('zip_path','n/a')}",
                f"- sha256={portal_zip.get('sha256','n/a')}",
                f"- sha256_file={portal_zip.get('sha256_file','n/a')}",
            ]
        )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(out)


def _build_report_payload(
    *,
    catalog_path: Path,
    artifacts_dir: Path,
    snapshot: List[Dict[str, Any]],
    steps: List[StepResult],
    result: str,
    upload_portal: Dict[str, Any] | None = None,
    warnings: List[str] | None = None,
    bundle_vs_repo_tex: Dict[str, Any] | None = None,
    rc_check: Dict[str, Any] | None = None,
    cmb_reports: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    total_duration = round(sum(float(s.duration_sec) for s in steps), 6)
    payload: Dict[str, Any] = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "catalog": str(catalog_path),
        "artifacts_dir": str(artifacts_dir),
        "artifacts": snapshot,
        "steps": [
            {
                "name": s.name,
                "cmd": s.cmd,
                "status": s.status,
                "exit_code": s.exit_code,
                "started_utc": s.started_utc,
                "finished_utc": s.finished_utc,
                "duration_sec": s.duration_sec,
            }
            for s in steps
        ],
        "summary": {
            "step_count": len(steps),
            "pass_count": sum(1 for s in steps if s.status == "PASS"),
            "fail_count": sum(1 for s in steps if s.status != "PASS"),
            "duration_sec_total": total_duration,
        },
        "versions": {
            "python3": _tool_version([sys.executable, "--version"]),
            "pdflatex": _tool_version(["pdflatex", "--version"]),
        },
        "result": result,
        "overall_status": result,
    }
    if upload_portal is not None:
        payload["upload_portal"] = upload_portal
    if warnings is not None:
        payload["warnings"] = warnings
    if bundle_vs_repo_tex is not None:
        payload["bundle_vs_repo_tex"] = bundle_vs_repo_tex
    if rc_check is not None:
        payload["rc_check"] = rc_check
    if cmb_reports is not None:
        payload["cmb_reports"] = cmb_reports
    return payload


def _write_report_text(report_path: Path, payload: Dict[str, Any]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_report(
    report_path: Path,
    *,
    catalog_path: Path,
    artifacts_dir: Path,
    snapshot: List[Dict[str, Any]],
    steps: List[StepResult],
    result: str,
    upload_portal: Dict[str, Any] | None = None,
    warnings: List[str] | None = None,
    bundle_vs_repo_tex: Dict[str, Any] | None = None,
    rc_check: Dict[str, Any] | None = None,
    cmb_reports: Dict[str, Any] | None = None,
) -> None:
    payload = _build_report_payload(
        catalog_path=catalog_path,
        artifacts_dir=artifacts_dir,
        snapshot=snapshot,
        steps=steps,
        result=result,
        upload_portal=upload_portal,
        warnings=warnings,
        bundle_vs_repo_tex=bundle_vs_repo_tex,
        rc_check=rc_check,
        cmb_reports=cmb_reports,
    )
    _write_report_text(report_path, payload)


def _stage_portal_reports(
    *,
    upload_portal: Dict[str, Any],
    operator_payload: Dict[str, Any],
    rc_payload: Dict[str, Any] | None,
    cmb_reports: Dict[str, Any] | None = None,
) -> Dict[str, bool]:
    root = Path(str(upload_portal["path"]))
    reports_dir = root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    _write_json_file(reports_dir / "operator_report.json", operator_payload)

    rc_obj: Dict[str, Any]
    if isinstance(rc_payload, dict):
        rc_obj = rc_payload
    else:
        rc_obj = {
            "overall_status": "UNKNOWN",
            "result": "UNKNOWN",
            "warnings": ["release_candidate_check JSON payload not available"],
        }
    _write_json_file(reports_dir / "rc_check.json", rc_obj)

    arxiv_obj = rc_obj.get("arxiv_preflight") if isinstance(rc_obj, dict) else None
    if not isinstance(arxiv_obj, dict):
        arxiv_obj = {
            "overall_status": "UNKNOWN",
            "result": "UNKNOWN",
            "warnings": ["arxiv_preflight payload not available from RC report"],
        }
    _write_json_file(reports_dir / "arxiv_preflight.json", arxiv_obj)
    cmb_json_staged = False
    cmb_csv_staged = False
    invariants_json_staged = False
    if isinstance(cmb_reports, dict):
        src_json = cmb_reports.get("json_path")
        if isinstance(src_json, str) and src_json:
            p = Path(src_json)
            if p.is_file():
                shutil.copy2(p, reports_dir / "cmb_priors_report.json")
                cmb_json_staged = True
        src_csv = cmb_reports.get("csv_path")
        if isinstance(src_csv, str) and src_csv:
            p = Path(src_csv)
            if p.is_file():
                shutil.copy2(p, reports_dir / "cmb_priors_table.csv")
                cmb_csv_staged = True
        src_invariants = cmb_reports.get("invariants_path")
        if isinstance(src_invariants, str) and src_invariants:
            p = Path(src_invariants)
            if p.is_file():
                shutil.copy2(p, reports_dir / "numerics_invariants_report.json")
                invariants_json_staged = True

    (reports_dir / "README_REPORTS.md").write_text(_build_reports_readme(), encoding="utf-8")

    return {
        "operator_report": (reports_dir / "operator_report.json").is_file(),
        "rc_check": (reports_dir / "rc_check.json").is_file(),
        "arxiv_preflight": (reports_dir / "arxiv_preflight.json").is_file(),
        "cmb_priors_report": cmb_json_staged,
        "cmb_priors_table": cmb_csv_staged,
        "numerics_invariants_report": invariants_json_staged,
    }


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="operator_one_button",
        description="Operator-grade one-command verification with optional canonical-asset fetch.",
    )
    ap.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    ap.add_argument(
        "--out-dir",
        "--outdir",
        dest="outdir",
        type=Path,
        default=None,
        help="Output root (CLI > GSC_OUTDIR > v11.0.0/artifacts/release).",
    )
    ap.add_argument("--artifacts-dir", type=Path, default=Path.cwd())
    ap.add_argument("--fetch-missing", action="store_true", help="Opt-in network fetch for missing canonical assets")
    ap.add_argument("--dry-run", action="store_true", help="Report-only mode (no network/writes from this script)")
    ap.add_argument("--report", type=Path, help="Optional path to write a machine-readable JSON report")
    ap.add_argument("--prepare-upload-dir", type=Path, help="Optional upload-portal output directory")
    ap.add_argument(
        "--prepare-upload-zip",
        type=Path,
        help="Optional path to zip the prepared upload portal (requires --prepare-upload-dir)",
    )
    ap.add_argument(
        "--prepare-upload-dir-mode",
        choices=("copy", "hardlink"),
        default="copy",
        help="File staging mode for upload portal (default: copy)",
    )
    ap.add_argument("--fit-dir", type=Path, default=None, help="Optional fit directory for early-time CMB batch reporting.")
    ap.add_argument("--cmb", type=Path, default=None, help="Optional compressed CMB priors CSV for early-time reporting.")
    ap.add_argument("--cmb-cov", type=Path, default=None, help="Optional compressed CMB covariance for early-time reporting.")
    ap.add_argument("--omega-b-h2", type=float, default=None, help="Physical baryon density for early-time reporting.")
    ap.add_argument("--omega-c-h2", type=float, default=None, help="Physical CDM density for early-time reporting.")
    ap.add_argument("--Neff", type=float, default=3.046, help="Effective neutrino number for early-time reporting.")
    ap.add_argument("--Tcmb-K", type=float, default=2.7255, help="CMB temperature for early-time reporting.")
    ap.add_argument(
        "--cmb-mode",
        choices=("distance_priors", "shift_params", "theta_star"),
        default=None,
        help="Optional CMB mode override for early-time reporting.",
    )
    ap.add_argument("--cmb-bridge-z", type=float, default=None, help="Optional non-LCDM bridge z override for reporting.")
    ap.add_argument(
        "--require-early-time-invariants",
        action="store_true",
        help="Require early-time numerics invariants report checks in release_candidate_check.",
    )
    ap.add_argument(
        "--require-derived-rd",
        action="store_true",
        help="Require derived-rd metadata checks in release_candidate_check.",
    )
    ap.add_argument(
        "--derived-rd-fit-dir",
        type=Path,
        default=None,
        help="Optional fit dir for derived-rd RC validation (relative paths resolve under outdir).",
    )
    args = ap.parse_args(argv)

    catalog_path = args.catalog.expanduser().resolve()
    out_root = resolve_outdir(args.outdir, v101_dir=V101_DIR)
    report_path = resolve_path_under_outdir(args.report, out_root=out_root)
    prepare_upload_dir = resolve_path_under_outdir(args.prepare_upload_dir, out_root=out_root)
    prepare_upload_zip = resolve_path_under_outdir(args.prepare_upload_zip, out_root=out_root)
    artifacts_dir = args.artifacts_dir.expanduser().resolve()
    fit_dir = args.fit_dir.expanduser().resolve() if args.fit_dir is not None else None
    cmb_csv = args.cmb.expanduser().resolve() if args.cmb is not None else None
    cmb_cov = args.cmb_cov.expanduser().resolve() if args.cmb_cov is not None else None
    derived_rd_fit_dir = resolve_path_under_outdir(args.derived_rd_fit_dir, out_root=out_root)
    if args.require_derived_rd and derived_rd_fit_dir is None:
        derived_rd_fit_dir = resolve_path_under_outdir(Path("late_time_fit"), out_root=out_root)
    require_derived_rd = bool(args.require_derived_rd or args.derived_rd_fit_dir is not None)
    if require_derived_rd and derived_rd_fit_dir is None:
        derived_rd_fit_dir = resolve_path_under_outdir(Path("late_time_fit"), out_root=out_root)
    cmb_report_requested = any(
        x is not None
        for x in (fit_dir, cmb_csv, cmb_cov, args.omega_b_h2, args.omega_c_h2, args.cmb_mode, args.cmb_bridge_z)
    )
    try:
        early_time_params = early_time_params_from_namespace(
            args,
            require=bool(cmb_report_requested),
            context="early-time CMB reporting",
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if cmb_report_requested:
        if fit_dir is None or cmb_csv is None or early_time_params is None:
            print(
                "ERROR: early-time CMB reporting requires --fit-dir --cmb --omega-b-h2 --omega-c-h2",
                file=sys.stderr,
            )
            return 2
    print(f"[info] OUTDIR={out_root}")

    try:
        entries = _load_entries(catalog_path)
    except Exception as exc:
        print(f"ERROR: failed to load catalog: {exc}")
        return 2

    steps: List[StepResult] = []
    upload_portal_info: Dict[str, Any] | None = None
    warnings: List[str] = []
    bundle_vs_repo_tex: Dict[str, Any] | None = None
    rc_check_payload: Dict[str, Any] | None = None
    cmb_reports_payload: Dict[str, Any] | None = None
    before_snapshot = _snapshot(entries, artifacts_dir)
    before_exists = {str(row["id"]): bool(row["exists"]) for row in before_snapshot}

    if prepare_upload_zip and not prepare_upload_dir:
        print("ERROR: --prepare-upload-zip requires --prepare-upload-dir")
        return 2

    if args.fetch_missing:
        cmd_fetch = [
            sys.executable,
            str(SCRIPTS_DIR / "fetch_canonical_artifacts.py"),
            "--catalog",
            str(catalog_path),
            "--artifacts-dir",
            str(artifacts_dir),
            "--fetch-missing",
        ]
        if args.dry_run:
            cmd_fetch.append("--dry-run")
        if _run_step("fetch_canonical_artifacts", cmd_fetch, steps) != 0:
            if report_path:
                _write_report(
                    report_path,
                    catalog_path=catalog_path,
                    artifacts_dir=artifacts_dir,
                    snapshot=_snapshot_with_integrity(entries, artifacts_dir, before_exists=before_exists),
                    steps=steps,
                    result="FAIL",
                    upload_portal=upload_portal_info,
                    warnings=warnings,
                    bundle_vs_repo_tex=bundle_vs_repo_tex,
                    rc_check=rc_check_payload,
                    cmb_reports=cmb_reports_payload,
                )
            return 2

    snapshot = _snapshot_with_integrity(entries, artifacts_dir, before_exists=before_exists)
    required_keys = REQUIRED_KEYS
    if prepare_upload_dir:
        required_keys = ALL_CANONICAL_KEYS
    missing = _missing_required(snapshot, required_keys=required_keys)

    if args.dry_run:
        if not args.fetch_missing:
            cmd_probe = [
                sys.executable,
                str(SCRIPTS_DIR / "fetch_canonical_artifacts.py"),
                "--catalog",
                str(catalog_path),
                "--artifacts-dir",
                str(artifacts_dir),
                "--dry-run",
            ]
            _run_step("fetch_canonical_artifacts (report-only)", cmd_probe, steps)

        cmd_required = [
            sys.executable,
            str(SCRIPTS_DIR / "release_candidate_check.py"),
            "--catalog",
            str(catalog_path),
            "--artifacts-dir",
            str(artifacts_dir),
            "--out-dir",
            str(out_root),
            "--print-required",
        ]
        _run_step("release_candidate_check --print-required", cmd_required, steps)

        if prepare_upload_dir:
            print(f"[step] prepare_upload_dir (dry-run)")
            print(f"  $ prepare-upload-dir {prepare_upload_dir} --mode={args.prepare_upload_dir_mode}")
            print("  [dry-run] no directory changes performed")
            if prepare_upload_zip:
                print(f"[step] prepare_upload_zip (dry-run)")
                print(f"  $ prepare-upload-zip {prepare_upload_zip}")
                print("  [dry-run] no zip created")

        result = "FAIL" if missing else "PASS"
        if missing:
            _print_missing(missing, artifacts_dir)
        print(f"RESULT: {result} (dry-run)")

        if report_path:
            _write_report(
                report_path,
                catalog_path=catalog_path,
                artifacts_dir=artifacts_dir,
                snapshot=snapshot,
                steps=steps,
                result=result,
                upload_portal=upload_portal_info,
                warnings=warnings,
                bundle_vs_repo_tex=bundle_vs_repo_tex,
                rc_check=rc_check_payload,
                cmb_reports=cmb_reports_payload,
            )
        return 0 if not missing else 2

    if missing:
        _print_missing(missing, artifacts_dir)
        if report_path:
            _write_report(
                report_path,
                catalog_path=catalog_path,
                artifacts_dir=artifacts_dir,
                snapshot=snapshot,
                steps=steps,
                result="FAIL",
                upload_portal=upload_portal_info,
                warnings=warnings,
                bundle_vs_repo_tex=bundle_vs_repo_tex,
                rc_check=rc_check_payload,
                cmb_reports=cmb_reports_payload,
            )
        return 2

    bundle_vs_repo_tex = _run_bundle_vs_repo_tex_check(entries, artifacts_dir)
    if not bundle_vs_repo_tex.get("match"):
        warn = str(bundle_vs_repo_tex.get("warning") or "bundle_vs_repo_tex mismatch")
        warnings.append(f"bundle_vs_repo_tex_drift: {warn}")

    if _ensure_paper_assets(entries, artifacts_dir, steps) != 0:
        if report_path:
            _write_report(
                report_path,
                catalog_path=catalog_path,
                artifacts_dir=artifacts_dir,
                snapshot=_snapshot_with_integrity(entries, artifacts_dir, before_exists=before_exists),
                steps=steps,
                result="FAIL",
                upload_portal=upload_portal_info,
                warnings=warnings,
                bundle_vs_repo_tex=bundle_vs_repo_tex,
                rc_check=rc_check_payload,
                cmb_reports=cmb_reports_payload,
            )
        print("RESULT: FAIL")
        return 2

    if cmb_report_requested:
        rc_report, info_report = _run_early_time_cmb_priors_report_step(
            fit_dir=Path(str(fit_dir)),
            cmb_csv=Path(str(cmb_csv)),
            cmb_cov=cmb_cov,
            omega_b_h2=float(early_time_params.omega_b_h2),
            omega_c_h2=float(early_time_params.omega_c_h2),
            n_eff=float(early_time_params.N_eff),
            tcmb_k=float(early_time_params.Tcmb_K),
            cmb_mode=args.cmb_mode,
            cmb_bridge_z=args.cmb_bridge_z,
            out_root=out_root,
            steps=steps,
        )
        cmb_reports_payload = info_report
        if rc_report != 0:
            if report_path:
                _write_report(
                    report_path,
                    catalog_path=catalog_path,
                    artifacts_dir=artifacts_dir,
                    snapshot=_snapshot_with_integrity(entries, artifacts_dir, before_exists=before_exists),
                    steps=steps,
                    result="FAIL",
                    upload_portal=upload_portal_info,
                    warnings=warnings,
                    bundle_vs_repo_tex=bundle_vs_repo_tex,
                    rc_check=rc_check_payload,
                    cmb_reports=cmb_reports_payload,
                )
            print("RESULT: FAIL")
            return 2

    rc, rc_payload = _run_release_candidate_check_step(
        catalog_path=catalog_path,
        artifacts_dir=artifacts_dir,
        out_root=out_root,
        require_cmb_reports=bool(cmb_report_requested),
        cmb_report_json=(Path(cmb_reports_payload["json_path"]) if isinstance(cmb_reports_payload, dict) else None),
        cmb_report_csv=(Path(cmb_reports_payload["csv_path"]) if isinstance(cmb_reports_payload, dict) else None),
        require_early_time_invariants=bool(args.require_early_time_invariants),
        early_time_invariants_report=(
            Path(cmb_reports_payload["invariants_path"]) if isinstance(cmb_reports_payload, dict) else None
        ),
        require_derived_rd=require_derived_rd,
        derived_rd_fit_dir=derived_rd_fit_dir,
        steps=steps,
    )
    rc_check_payload = rc_payload
    if rc != 0:
        if report_path:
            _write_report(
                report_path,
                catalog_path=catalog_path,
                artifacts_dir=artifacts_dir,
                snapshot=_snapshot_with_integrity(entries, artifacts_dir, before_exists=before_exists),
                steps=steps,
                result="FAIL",
                upload_portal=upload_portal_info,
                warnings=warnings,
                bundle_vs_repo_tex=bundle_vs_repo_tex,
                rc_check=rc_check_payload,
                cmb_reports=cmb_reports_payload,
            )
        print("RESULT: FAIL")
        return 2

    ordered = [
        (
            "verify_submission_bundle",
            [
                sys.executable,
                str(SCRIPTS_DIR / "verify_submission_bundle.py"),
                str(verify_all._resolve_asset_path(artifacts_dir, entries["submission"]["asset"])),
                "--smoke-compile",
            ],
        ),
        (
            "verify_referee_pack",
            [
                sys.executable,
                str(SCRIPTS_DIR / "verify_referee_pack.py"),
                str(verify_all._resolve_asset_path(artifacts_dir, entries["referee_pack"]["asset"])),
            ],
        ),
        (
            "verify_toe_bundle",
            [
                sys.executable,
                str(SCRIPTS_DIR / "verify_toe_bundle.py"),
                str(verify_all._resolve_asset_path(artifacts_dir, entries["toe_bundle"]["asset"])),
            ],
        ),
        (
            "build_paper --no-reproduce",
            [
                "bash",
                str(SCRIPTS_DIR / "build_paper.sh"),
                "--no-reproduce",
            ],
        ),
        (
            "release_candidate_check --print-required",
            [
                sys.executable,
                str(SCRIPTS_DIR / "release_candidate_check.py"),
                "--catalog",
                str(catalog_path),
                "--artifacts-dir",
                str(artifacts_dir),
                "--out-dir",
                str(out_root),
                "--print-required",
            ],
        ),
    ]

    for name, cmd in ordered:
        if _run_step(name, cmd, steps) != 0:
            if report_path:
                _write_report(
                    report_path,
                    catalog_path=catalog_path,
                    artifacts_dir=artifacts_dir,
                    snapshot=_snapshot_with_integrity(entries, artifacts_dir, before_exists=before_exists),
                    steps=steps,
                    result="FAIL",
                    upload_portal=upload_portal_info,
                    warnings=warnings,
                    bundle_vs_repo_tex=bundle_vs_repo_tex,
                    rc_check=rc_check_payload,
                    cmb_reports=cmb_reports_payload,
                )
            print("RESULT: FAIL")
            return 2

    reports_staged: Dict[str, bool] | None = None
    pending_upload_zip: Path | None = None

    if prepare_upload_dir:
        portal_dir = prepare_upload_dir
        rc, info = _prepare_upload_portal_step(
            entries=entries,
            artifacts_dir=artifacts_dir,
            upload_dir=portal_dir,
            mode=args.prepare_upload_dir_mode,
            steps=steps,
            rc_check=rc_check_payload,
        )
        if rc != 0:
            if report_path:
                _write_report(
                    report_path,
                    catalog_path=catalog_path,
                    artifacts_dir=artifacts_dir,
                    snapshot=_snapshot_with_integrity(entries, artifacts_dir, before_exists=before_exists),
                    steps=steps,
                    result="FAIL",
                    upload_portal=upload_portal_info,
                    warnings=warnings,
                    bundle_vs_repo_tex=bundle_vs_repo_tex,
                    rc_check=rc_check_payload,
                    cmb_reports=cmb_reports_payload,
                )
            print("RESULT: FAIL")
            return 2
        upload_portal_info = info
        for w in info.get("portal_warnings", []):
            if isinstance(w, str) and w:
                warnings.append(w)
        if prepare_upload_zip:
            pending_upload_zip = prepare_upload_zip

    if upload_portal_info is not None:
        snapshot_now = _snapshot_with_integrity(entries, artifacts_dir, before_exists=before_exists)
        provisional_payload = _build_report_payload(
            catalog_path=catalog_path,
            artifacts_dir=artifacts_dir,
            snapshot=snapshot_now,
            steps=steps,
            result="PASS",
            upload_portal=upload_portal_info,
            warnings=warnings,
            bundle_vs_repo_tex=bundle_vs_repo_tex,
            rc_check=rc_check_payload,
            cmb_reports=cmb_reports_payload,
        )
        reports_staged = _stage_portal_reports(
            upload_portal=upload_portal_info,
            operator_payload=provisional_payload,
            rc_payload=rc_check_payload,
            cmb_reports=cmb_reports_payload,
        )
        summary_path = _write_operator_summary_file(
            upload_portal=upload_portal_info,
            result="PASS",
            steps=steps,
            snapshot=snapshot_now,
            warnings=warnings,
            rc_check=rc_check_payload,
            reports_staged=reports_staged,
        )
        upload_portal_info["summary_file"] = summary_path
        upload_portal_info["reports"] = {
            "operator_report": "reports/operator_report.json",
            "rc_check": "reports/rc_check.json",
            "arxiv_preflight": "reports/arxiv_preflight.json",
            "cmb_priors_report": "reports/cmb_priors_report.json",
            "cmb_priors_table": "reports/cmb_priors_table.csv",
            "numerics_invariants_report": "reports/numerics_invariants_report.json",
            "readme": "reports/README_REPORTS.md",
        }
        upload_portal_info["reports_staged"] = reports_staged

        final_payload = _build_report_payload(
            catalog_path=catalog_path,
            artifacts_dir=artifacts_dir,
            snapshot=_snapshot_with_integrity(entries, artifacts_dir, before_exists=before_exists),
            steps=steps,
            result="PASS",
            upload_portal=upload_portal_info,
            warnings=warnings,
            bundle_vs_repo_tex=bundle_vs_repo_tex,
            rc_check=rc_check_payload,
            cmb_reports=cmb_reports_payload,
        )
        portal_operator_report_path = Path(str(upload_portal_info["path"])) / "reports" / "operator_report.json"
        _write_report_text(portal_operator_report_path, final_payload)
        if report_path:
            _write_report_text(report_path, final_payload)

        upload_portal_info["checksums_file"] = _rewrite_portal_checksums(Path(str(upload_portal_info["path"])))
        if pending_upload_zip is not None:
            zrc, zinfo = _prepare_upload_zip_step(
                upload_portal=upload_portal_info,
                upload_zip=pending_upload_zip,
                steps=steps,
            )
            if zrc != 0:
                if report_path:
                    _write_report_text(
                        report_path,
                        _build_report_payload(
                            catalog_path=catalog_path,
                            artifacts_dir=artifacts_dir,
                            snapshot=_snapshot_with_integrity(entries, artifacts_dir, before_exists=before_exists),
                            steps=steps,
                            result="FAIL",
                            upload_portal=upload_portal_info,
                            warnings=warnings,
                            bundle_vs_repo_tex=bundle_vs_repo_tex,
                            rc_check=rc_check_payload,
                            cmb_reports=cmb_reports_payload,
                        ),
                    )
                print("RESULT: FAIL")
                return 2
            upload_portal_info["portal_zip"] = zinfo

    if report_path and upload_portal_info is None:
        payload = _build_report_payload(
            catalog_path=catalog_path,
            artifacts_dir=artifacts_dir,
            snapshot=_snapshot_with_integrity(entries, artifacts_dir, before_exists=before_exists),
            steps=steps,
            result="PASS",
            upload_portal=upload_portal_info,
            warnings=warnings,
            bundle_vs_repo_tex=bundle_vs_repo_tex,
            rc_check=rc_check_payload,
            cmb_reports=cmb_reports_payload,
        )
        _write_report_text(report_path, payload)

    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

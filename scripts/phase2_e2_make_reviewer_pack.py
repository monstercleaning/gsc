#!/usr/bin/env python3
"""Deterministic external-reviewer pack generator for Phase-2 E2 artifacts."""

from __future__ import annotations

import argparse
from datetime import datetime
import fnmatch
import hashlib
import json
import os
import re
import stat
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


TOOL_MARKER = "phase2_e2_reviewer_pack_v1"
FIXED_CREATED_UTC = "2000-01-01T00:00:00Z"
FIXED_ZIP_DT = (2000, 1, 1, 0, 0, 0)
ZIP_ROOT = "reviewer_pack"
PORTABLE_CONTENT_LINT_MARKER = "PORTABLE_CONTENT_LINT_FAILED"
REVIEWER_DOC_REL_PATHS: Tuple[str, ...] = (
    "v11.0.0/docs/project_status_and_roadmap.md",
    "v11.0.0/docs/external_reviewer_feedback.md",
    "v11.0.0/docs/early_time_e2_status.md",
    "v11.0.0/docs/structure_formation_status.md",
    "v11.0.0/docs/perturbations_and_dm_scope.md",
    "v11.0.0/docs/sigma_field_origin_status.md",
)

FORBIDDEN_SIMPLE_NAMES: Tuple[str, ...] = (
    ".git",
    ".venv",
    "__MACOSX",
    "site-packages",
)
FORBIDDEN_BASENAME_GLOBS: Tuple[str, ...] = (
    ".DS_Store",
    "error",
    "skipped_*",
    "submission_bundle*.zip",
    "referee_pack*.zip",
    "toe_bundle*.zip",
    "*PUBLICATION_BUNDLE*",
)
FORBIDDEN_PREFIXES: Tuple[str, ...] = (
    "v11.0.0/archive/packs/",
    "v11.0.0/B/",
)
_ABS_PATH_RE = re.compile(r"^(?:/|[A-Za-z]:[\\/]|\\\\)")


class ReviewerPackError(Exception):
    """Base error for reviewer-pack generation."""


class ReviewerPackUsageError(ReviewerPackError):
    """Raised when CLI arguments are invalid."""


class ReviewerPackSubtoolError(ReviewerPackError):
    """Raised when a composed subtool fails."""


@dataclass(frozen=True)
class ArtifactRow:
    path: str
    bytes: int
    sha256: str


@dataclass(frozen=True)
class CommandResult:
    command: List[str]
    returncode: int
    stdout: str
    stderr: str


def _sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_text_executable(path: Path, text: str) -> None:
    _write_text(path, text)
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _looks_like_absolute_path(text: str) -> bool:
    token = str(text).strip()
    if not token:
        return False
    if Path(token).is_absolute():
        return True
    return bool(_ABS_PATH_RE.match(token))


def _redact_path_token(text: str) -> str:
    token = str(text).strip()
    if not token:
        return token
    if _looks_like_absolute_path(token):
        name = Path(token).name
        return f"[abs]/{name}" if name else "[abs]"
    return token


def _redact_absolute_paths(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _redact_absolute_paths(value[k]) for k in sorted(value.keys(), key=lambda x: str(x))}
    if isinstance(value, list):
        return [_redact_absolute_paths(v) for v in value]
    if isinstance(value, tuple):
        return [_redact_absolute_paths(v) for v in value]
    if isinstance(value, str):
        return _redact_path_token(value)
    return value


def _rewrite_json_portable(path: Path) -> None:
    if not path.is_file():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    redacted = _redact_absolute_paths(payload)
    path.write_text(json.dumps(redacted, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _redact_json_tree_portable(root: Path) -> None:
    for path in sorted(root.rglob("*.json")):
        if not path.is_file():
            continue
        _rewrite_json_portable(path)


def _normalize_created_utc(value: str) -> str:
    text = str(value).strip()
    if not text:
        raise ReviewerPackUsageError("--created-utc must be non-empty")
    if not text.endswith("Z"):
        raise ReviewerPackUsageError("--created-utc must match YYYY-MM-DDTHH:MM:SSZ")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception as exc:
        raise ReviewerPackUsageError("--created-utc must match YYYY-MM-DDTHH:MM:SSZ") from exc
    normalized = parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(normalized)


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="phase2_e2_make_reviewer_pack",
        description="Build deterministic external-reviewer pack from an existing Phase-2 bundle.",
    )
    ap.add_argument("--bundle", required=True, help="Input Phase-2 bundle zip path.")
    ap.add_argument("--outdir", required=True, help="Output staging directory.")
    ap.add_argument("--zip-out", default=None, help="Optional final reviewer pack zip path.")
    ap.add_argument("--snapshot-profile", choices=("share", "slim"), default="share")
    ap.add_argument("--include-repo-snapshot", type=int, choices=(0, 1), default=1)
    ap.add_argument("--include-paper-assets", type=int, choices=(0, 1), default=1)
    ap.add_argument("--include-verify", type=int, choices=(0, 1), default=1)
    ap.add_argument(
        "--verify-strict",
        type=int,
        choices=(0, 1),
        default=1,
        help="When include-verify=1, run verify with schema + portable-content gates.",
    )
    ap.add_argument("--include-boltzmann-export", choices=("off", "on", "auto"), default="off")
    ap.add_argument("--boltzmann-rank-by", choices=("cmb", "rsd", "joint"), default="cmb")
    ap.add_argument("--boltzmann-eligible-status", choices=("ok_only", "any_eligible"), default="ok_only")
    ap.add_argument("--boltzmann-rsd-chi2-field", default=None)
    ap.add_argument("--boltzmann-max-zip-mb", type=float, default=50.0)
    ap.add_argument("--boltzmann-zip", action="store_true")
    ap.add_argument("--include-boltzmann-results", choices=("off", "on", "auto"), default="off")
    ap.add_argument("--boltzmann-run-dir", default=None, help="Optional external CLASS/CAMB run output directory.")
    ap.add_argument("--boltzmann-results-code", choices=("auto", "class", "camb"), default="auto")
    ap.add_argument("--boltzmann-results-max-zip-mb", type=float, default=50.0)
    ap.add_argument("--boltzmann-results-zip", action="store_true")
    ap.add_argument(
        "--skip-portable-content-lint",
        action="store_true",
        help="Skip JSON/JSONL machine-local path-content lint on staging output.",
    )
    ap.add_argument("--created-utc", default=FIXED_CREATED_UTC, help="Deterministic UTC timestamp (YYYY-MM-DDTHH:MM:SSZ).")
    ap.add_argument("--max-zip-mb", type=float, default=None)
    ap.add_argument("--format", choices=("text", "json"), default="text")
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--dry-run", action="store_true")
    return ap.parse_args(argv)


def _run_command(cmd: Sequence[str], *, cwd: Path) -> CommandResult:
    run = subprocess.run(
        [str(x) for x in cmd],
        cwd=str(cwd),
        text=True,
        capture_output=True,
    )
    return CommandResult(command=[str(x) for x in cmd], returncode=run.returncode, stdout=run.stdout or "", stderr=run.stderr or "")


def _format_command(cmd: Sequence[str]) -> str:
    return " ".join(cmd)


def _detect_bundle_root_from_extracted_tree(extract_root: Path) -> Path:
    manifest_paths = sorted(
        p for p in extract_root.rglob("manifest.json") if p.is_file()
    )
    if not manifest_paths:
        raise ReviewerPackSubtoolError("could not locate manifest.json in extracted bundle")
    for path in manifest_paths:
        parent = path.parent
        if parent == extract_root:
            return parent
    return manifest_paths[0].parent


def _ensure_empty_dir(path: Path) -> None:
    if path.exists():
        if not path.is_dir():
            raise ReviewerPackUsageError(f"outdir exists and is not a directory: {path}")
        if any(path.iterdir()):
            raise ReviewerPackUsageError(f"outdir must be empty: {path}")
    path.mkdir(parents=True, exist_ok=True)


def _is_symlink(path: Path) -> bool:
    try:
        return path.is_symlink()
    except OSError:
        return False


def _forbidden_reason(relpath: str) -> Optional[str]:
    rel = str(relpath).replace("\\", "/").strip("/")
    if not rel:
        return None
    lower = rel.lower()
    parts = rel.split("/")
    lower_parts = [p.lower() for p in parts]
    base = parts[-1]
    slash_wrapped = f"/{lower}/"

    for name in FORBIDDEN_SIMPLE_NAMES:
        if name.lower() in lower_parts:
            return f"contains forbidden path component '{name}'"

    for pref in FORBIDDEN_PREFIXES:
        pref_low = pref.lower()
        pref_clean = pref_low.rstrip("/")
        if lower == pref_clean or lower.startswith(pref_clean + "/"):
            return f"matches forbidden prefix '{pref}'"
        if f"/{pref_clean}/" in slash_wrapped:
            return f"contains forbidden subpath '{pref}'"

    for pattern in FORBIDDEN_BASENAME_GLOBS:
        if fnmatch.fnmatch(base.lower(), pattern.lower()):
            return f"matches forbidden basename pattern '{pattern}'"

    if "publication_bundle" in lower:
        return "matches forbidden token 'PUBLICATION_BUNDLE'"

    return None


def _scan_forbidden_paths(root: Path) -> None:
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if _forbidden_reason(rel) is not None:
            reason = _forbidden_reason(rel)
            raise ReviewerPackError(f"forbidden path in staging tree: {rel} ({reason})")


def _assert_no_symlinks(root: Path) -> None:
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        dir_path = Path(dirpath)
        for d in sorted(dirnames):
            candidate = dir_path / d
            if _is_symlink(candidate):
                rel = candidate.relative_to(root).as_posix()
                raise ReviewerPackError(f"symlink detected in staging tree: {rel}")
        for f in sorted(filenames):
            candidate = dir_path / f
            if _is_symlink(candidate):
                rel = candidate.relative_to(root).as_posix()
                raise ReviewerPackError(f"symlink detected in staging tree: {rel}")


def _assert_zip_internal_clean(path: Path) -> None:
    with zipfile.ZipFile(path, "r") as zf:
        for name in sorted(zf.namelist()):
            reason = _forbidden_reason(name)
            if reason is not None:
                raise ReviewerPackError(f"forbidden path inside zip '{path.name}': {name} ({reason})")


def _collect_artifacts(root: Path, *, exclude_relpaths: Iterable[str] = ()) -> List[ArtifactRow]:
    excluded = {x.strip("/") for x in exclude_relpaths}
    rows: List[ArtifactRow] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel in excluded:
            continue
        rows.append(ArtifactRow(path=rel, bytes=int(path.stat().st_size), sha256=_sha256_path(path)))
    return rows


def _write_sha_file(path: Path, *, sha256: str, label: str) -> None:
    _write_text(path, f"{sha256}  {label}\n")


def _render_readme(
    options: Mapping[str, Any],
    bundle_name: str,
    *,
    boltzmann_info: Mapping[str, Any],
    boltzmann_results_info: Mapping[str, Any],
) -> str:
    lines: List[str] = []
    lines.append("# External Reviewer Pack")
    lines.append("")
    lines.append(f"Tool marker: `{TOOL_MARKER}`")
    lines.append(f"Input bundle: `{bundle_name}`")
    lines.append("")
    lines.append("This pack is deterministic and reviewer-oriented. It is assembled from explicit artifacts")
    lines.append("instead of zipping a raw worktree.")
    lines.append("")
    lines.append("## Contents")
    lines.append("- `bundle/bundle.zip` + `bundle/bundle.sha256`")
    lines.append("- `bundle/LINEAGE.json` (Phase-2 provenance DAG)")
    lines.append("- `REVIEWER_GUIDE.md`")
    lines.append("- `docs/` reviewer-facing scope/status docs")
    if int(options.get("include_repo_snapshot", 0)) == 1:
        lines.append("- `repo_snapshot/repo_share.zip` + `repo_snapshot/repo_share.sha256`")
    if int(options.get("include_paper_assets", 0)) == 1:
        lines.append("- `paper_assets/` generated via `phase2_e2_make_paper_assets.py`")
    if int(options.get("include_verify", 0)) == 1:
        lines.append("- `verify/verify.txt` and `verify/verify.json`")
    lines.append("- `boltzmann_export.sh` (offline helper for perturbations export handoff)")
    lines.append("- `boltzmann_run_class.sh` (offline helper for external CLASS run harness)")
    lines.append("- `boltzmann_run_camb.sh` (offline helper for external CAMB run harness)")
    lines.append("- `boltzmann_results.sh` (offline helper for packaging external CLASS/CAMB outputs)")
    if bool(boltzmann_info.get("generated")):
        lines.append("- `boltzmann_export/` pre-generated export pack artifacts")
    if bool(boltzmann_info.get("zip_generated")):
        lines.append("- `boltzmann_export.zip` deterministic export zip")
    if bool(boltzmann_results_info.get("generated")):
        lines.append("- `boltzmann_results/` pre-generated results pack artifacts")
    if bool(boltzmann_results_info.get("zip_generated")):
        lines.append("- `boltzmann_results.zip` deterministic results zip")
    lines.append("- `manifest.json`")
    lines.append("")
    lines.append("## Reproduce / inspect")
    lines.append("1. Verify input bundle integrity:")
    if int(options.get("verify_strict", 1)) == 1:
        lines.append(
            "   `python3 v11.0.0/scripts/phase2_e2_verify_bundle.py "
            "--bundle bundle/bundle.zip --validate-schemas --lint-portable-content`"
        )
    else:
        lines.append("   `python3 v11.0.0/scripts/phase2_e2_verify_bundle.py --bundle bundle/bundle.zip`")
    lines.append("2. Read `REVIEWER_GUIDE.md` for reading order and verification notes.")
    lines.append("3. Inspect generated paper snippets and manifests under `paper_assets/`.")
    lines.append("4. Inspect provenance graph in `bundle/LINEAGE.json`.")
    lines.append("5. Run `./boltzmann_export.sh` (or inspect pre-generated `boltzmann_export/`).")
    lines.append("6. Optional: run external solver harness (`./boltzmann_run_class.sh` or `./boltzmann_run_camb.sh`).")
    lines.append("7. Inspect `boltzmann_results/RESULTS_SUMMARY.json` when results packaging is enabled.")
    lines.append("")
    lines.append("## Share hygiene")
    lines.append("Do not zip raw worktrees (`.git`, `.venv`, downloaded caches, `__MACOSX`, `.DS_Store`).")
    lines.append("Use deterministic snapshot tooling (`make_repo_snapshot.py --profile share`).")
    lines.append("")
    return "\n".join(lines)


def _render_reviewer_guide(
    bundle_name: str,
    *,
    created_utc: str,
    verify_strict: int,
    boltzmann_info: Mapping[str, Any],
    boltzmann_results_info: Mapping[str, Any],
) -> str:
    lines: List[str] = []
    lines.append("# Reviewer Guide")
    lines.append("")
    lines.append(f"Tool marker: `{TOOL_MARKER}`")
    lines.append(f"Selected bundle: `{bundle_name}`")
    lines.append(f"Deterministic created_utc: `{created_utc}`")
    lines.append("")
    lines.append("## What to read first")
    lines.append("1. `docs/project_status_and_roadmap.md`")
    lines.append("2. `docs/external_reviewer_feedback.md`")
    lines.append("3. `docs/early_time_e2_status.md`")
    lines.append("4. `docs/structure_formation_status.md`")
    lines.append("5. `docs/perturbations_and_dm_scope.md`")
    lines.append("6. `docs/sigma_field_origin_status.md`")
    lines.append("")
    lines.append("## How to reproduce / verify")
    lines.append("- Bundle used for this pack: `bundle/bundle.zip`")
    lines.append("- Bundle lineage DAG: `bundle/LINEAGE.json`")
    lines.append("- Precomputed verification outputs: `verify/verify.txt` and `verify/verify.json`")
    lines.append("- To re-run verification from a repo checkout:")
    if int(verify_strict) == 1:
        lines.append(
            "  `python3 v11.0.0/scripts/phase2_e2_verify_bundle.py "
            "--bundle bundle/bundle.zip --validate-schemas --lint-portable-content`"
        )
    else:
        lines.append("  `python3 v11.0.0/scripts/phase2_e2_verify_bundle.py --bundle bundle/bundle.zip`")
    lines.append("- Generated paper snippets/manifests are under `paper_assets/`.")
    lines.append("")
    lines.append("## Sharing / size hygiene")
    lines.append("- Do not zip a full worktree (`.git`, `.venv`, OS junk, downloaded caches).")
    lines.append("- Use deterministic snapshot tooling for code sharing:")
    lines.append("  `python3 v11.0.0/scripts/make_repo_snapshot.py --profile share --format zip --out GSC_share.zip`")
    lines.append("- If local ignored bloat accumulates, inspect/clean with:")
    lines.append("  `python3 v11.0.0/scripts/clean_ignored_bloat.py --root . --mode report`")
    lines.append("")
    lines.append("## Boltzmann export (perturbations)")
    lines.append("- This pack includes an offline helper that exports candidate metadata/templates.")
    lines.append("- Scope boundary: export-only bridge; no TT/TE/EE spectra are computed here.")
    lines.append("- Basic run:")
    lines.append("  `./boltzmann_export.sh`")
    lines.append("- Joint-ranking example (requires RSD chi2 fields in bundle records):")
    lines.append("  `GSC_RANK_BY=joint ./boltzmann_export.sh`")
    lines.append("- If `GSC_RANK_BY=joint|rsd` and RSD chi2 is missing, export can return exit code `2`.")
    lines.append("- Where to inspect outputs:")
    lines.append("  - `boltzmann_export/EXPORT_SUMMARY.json`")
    lines.append("  - `boltzmann_export/CANDIDATE_RECORD.json`")
    lines.append("  - CLASS/CAMB template `.ini` files under `boltzmann_export/`")
    if bool(boltzmann_info.get("generated")):
        lines.append("- Pre-generated export is included in this pack.")
    else:
        lines.append("- Pre-generated export is not included; run `./boltzmann_export.sh`.")
    if bool(boltzmann_info.get("note")):
        lines.append(f"- Generation note: {str(boltzmann_info.get('note'))}")
    lines.append("- External CLASS/CAMB binaries are not bundled; run them locally if needed.")
    lines.append("")
    lines.append("## How to run exporter directly")
    lines.append("- JSON summary mode:")
    lines.append(
        "  `python3 ./repo_snapshot/_repo_export/v11.0.0/scripts/phase2_pt_boltzmann_export_pack.py "
        "--bundle ./bundle/bundle.zip --rank-by cmb --eligible-status ok_only "
        f"--created-utc {created_utc} --outdir ./boltzmann_export --format json --json-out ./boltzmann_export/export_summary.json`"
    )
    lines.append("- If `repo_snapshot/` is not included, set `GSC_REPO_ROOT` and run `./boltzmann_export.sh`.")
    lines.append("")
    lines.append("## Boltzmann run harness (external execution)")
    lines.append("- Use helper scripts for one-command external solver runs:")
    lines.append("  `GSC_CLASS_BIN=/path/to/class ./boltzmann_run_class.sh`")
    lines.append("  `GSC_CAMB_BIN=/path/to/camb ./boltzmann_run_camb.sh`")
    lines.append("- Docker mode is optional:")
    lines.append("  `GSC_BOLTZMANN_RUNNER=docker GSC_CLASS_DOCKER_IMAGE=gsc-class:latest ./boltzmann_run_class.sh`")
    lines.append("- Harness outputs are written under `boltzmann_run_class/` or `boltzmann_run_camb/` by default.")
    lines.append("- Each run directory includes deterministic `RUN_METADATA.json` and `run.log`.")
    lines.append("")
    lines.append("## Boltzmann results (perturbations)")
    lines.append("- Optional: package external CLASS/CAMB outputs into a deterministic results artifact.")
    lines.append("- Scope boundary: this only packages external outputs/checksums and does not run a spectra solver.")
    lines.append("- Primary helper:")
    lines.append("  `GSC_BOLTZMANN_RUN_DIR=/path/to/external_run_outputs ./boltzmann_results.sh`")
    lines.append("- Require-TT example:")
    lines.append("  `GSC_BOLTZMANN_RESULTS_REQUIRE=tt_spectrum GSC_BOLTZMANN_RUN_DIR=/path/to/external_run_outputs ./boltzmann_results.sh`")
    if bool(boltzmann_results_info.get("generated")):
        lines.append("- Pre-generated results pack is included under `boltzmann_results/`.")
        lines.append("- Inspect:")
        lines.append("  - `boltzmann_results/RESULTS_SUMMARY.json`")
        lines.append("  - `boltzmann_results/README.md`")
        lines.append("  - `boltzmann_results/outputs/`")
    else:
        lines.append("- Results pack is not pre-generated in this reviewer pack; run `./boltzmann_results.sh`.")
    if bool(boltzmann_results_info.get("note")):
        lines.append(f"- Results note: {str(boltzmann_results_info.get('note'))}")
    lines.append("- To package results manually after running external CLASS/CAMB:")
    lines.append(
        "  `python3 ./repo_snapshot/_repo_export/v11.0.0/scripts/phase2_pt_boltzmann_results_pack.py "
        "--export-pack ./boltzmann_export --run-dir /path/to/external_run_outputs "
        f"--code auto --outdir ./boltzmann_results --created-utc {created_utc} --format json`"
    )
    lines.append("- Missing TT in `--require tt_spectrum` mode returns exit code `2` with a stable marker.")
    lines.append("")
    return "\n".join(lines)


def _render_boltzmann_export_script(*, created_utc: str) -> str:
    lines: List[str] = []
    lines.append("#!/usr/bin/env bash")
    lines.append("set -euo pipefail")
    lines.append("")
    lines.append('JOB_ROOT="$(cd "$(dirname "$0")" && pwd)"')
    lines.append('PY="${GSC_PYTHON:-python3}"')
    lines.append('CREATED_UTC_DEFAULT="' + str(created_utc) + '"')
    lines.append('CREATED_UTC="${GSC_BOLTZMANN_CREATED_UTC:-$CREATED_UTC_DEFAULT}"')
    lines.append('RANK_BY="${GSC_RANK_BY:-cmb}"')
    lines.append('ELIGIBLE_STATUS="${GSC_ELIGIBLE_STATUS:-ok_only}"')
    lines.append('RSD_CHI2_FIELD="${GSC_RSD_CHI2_FIELD:-}"')
    lines.append('OUTDIR_RAW="${GSC_BOLTZMANN_OUTDIR:-./boltzmann_export}"')
    lines.append('ZIP_OUT_RAW="${GSC_BOLTZMANN_ZIP_OUT:-}"')
    lines.append('MAX_ZIP_MB="${GSC_BOLTZMANN_MAX_ZIP_MB:-50}"')
    lines.append('REPO_ROOT_OVERRIDE="${GSC_REPO_ROOT:-}"')
    lines.append('SNAPSHOT_ZIP="$JOB_ROOT/repo_snapshot/repo_share.zip"')
    lines.append('SNAPSHOT_WORK="${GSC_BOLTZMANN_SNAPSHOT_WORK:-$JOB_ROOT/repo_snapshot/_repo_export}"')
    lines.append('EXPORT_SCRIPT=""')
    lines.append("")
    lines.append('if [[ "$OUTDIR_RAW" = /* ]]; then')
    lines.append('  OUTDIR="$OUTDIR_RAW"')
    lines.append("else")
    lines.append('  OUTDIR="$JOB_ROOT/$OUTDIR_RAW"')
    lines.append("fi")
    lines.append("")
    lines.append('ZIP_ARGS=()')
    lines.append('if [[ -n "$ZIP_OUT_RAW" ]]; then')
    lines.append('  if [[ "$ZIP_OUT_RAW" = /* ]]; then')
    lines.append('    ZIP_ARGS+=("--zip-out" "$ZIP_OUT_RAW")')
    lines.append("  else")
    lines.append('    ZIP_ARGS+=("--zip-out" "$JOB_ROOT/$ZIP_OUT_RAW")')
    lines.append("  fi")
    lines.append('  ZIP_ARGS+=("--max-zip-mb" "$MAX_ZIP_MB")')
    lines.append("fi")
    lines.append("")
    lines.append('if [[ -f "$SNAPSHOT_ZIP" ]]; then')
    lines.append('  mkdir -p "$SNAPSHOT_WORK"')
    lines.append('  if [[ ! -f "$SNAPSHOT_WORK/.extract_ok" ]]; then')
    lines.append('    rm -rf "$SNAPSHOT_WORK"')
    lines.append('    mkdir -p "$SNAPSHOT_WORK"')
    lines.append('    "$PY" - "$SNAPSHOT_ZIP" "$SNAPSHOT_WORK" <<\'PY_EXTRACT\'')
    lines.append("import shutil")
    lines.append("import sys")
    lines.append("from pathlib import Path")
    lines.append("import zipfile")
    lines.append("")
    lines.append("zip_path = Path(sys.argv[1]).resolve()")
    lines.append("work = Path(sys.argv[2]).resolve()")
    lines.append("tmp = work / '_tmp_extract'")
    lines.append("if tmp.exists():")
    lines.append("    shutil.rmtree(tmp)")
    lines.append("tmp.mkdir(parents=True, exist_ok=True)")
    lines.append("with zipfile.ZipFile(zip_path, 'r') as zf:")
    lines.append("    zf.extractall(tmp)")
    lines.append("candidates = sorted(tmp.rglob('phase2_pt_boltzmann_export_pack.py'))")
    lines.append("if not candidates:")
    lines.append("    raise SystemExit(2)")
    lines.append("repo_root = candidates[0].resolve().parents[2]")
    lines.append("dst = work / 'v11.0.0'")
    lines.append("if dst.exists():")
    lines.append("    shutil.rmtree(dst)")
    lines.append("dst.parent.mkdir(parents=True, exist_ok=True)")
    lines.append("shutil.move(str(repo_root / 'v11.0.0'), str(dst))")
    lines.append("shutil.rmtree(tmp)")
    lines.append("(work / '.extract_ok').write_text('ok\\n', encoding='utf-8')")
    lines.append("PY_EXTRACT")
    lines.append("  fi")
    lines.append('  if [[ -f "$SNAPSHOT_WORK/v11.0.0/scripts/phase2_pt_boltzmann_export_pack.py" ]]; then')
    lines.append('    EXPORT_SCRIPT="$SNAPSHOT_WORK/v11.0.0/scripts/phase2_pt_boltzmann_export_pack.py"')
    lines.append("  fi")
    lines.append("fi")
    lines.append("")
    lines.append('if [[ -z "$EXPORT_SCRIPT" ]]; then')
    lines.append('  if [[ -n "$REPO_ROOT_OVERRIDE" && -f "$REPO_ROOT_OVERRIDE/v11.0.0/scripts/phase2_pt_boltzmann_export_pack.py" ]]; then')
    lines.append('    EXPORT_SCRIPT="$REPO_ROOT_OVERRIDE/v11.0.0/scripts/phase2_pt_boltzmann_export_pack.py"')
    lines.append('  elif [[ -n "$REPO_ROOT_OVERRIDE" && -f "$REPO_ROOT_OVERRIDE/scripts/phase2_pt_boltzmann_export_pack.py" ]]; then')
    lines.append('    EXPORT_SCRIPT="$REPO_ROOT_OVERRIDE/scripts/phase2_pt_boltzmann_export_pack.py"')
    lines.append("  else")
    lines.append('    echo "Could not locate phase2_pt_boltzmann_export_pack.py (missing repo snapshot and GSC_REPO_ROOT fallback)." >&2')
    lines.append("    exit 2")
    lines.append("  fi")
    lines.append("fi")
    lines.append("")
    lines.append('INPUT_ARGS=()')
    lines.append('INPUT_SOURCE=""')
    lines.append('if [[ -f "$JOB_ROOT/bundle/bundle.zip" ]]; then')
    lines.append('  INPUT_ARGS+=("--bundle" "$JOB_ROOT/bundle/bundle.zip")')
    lines.append('  INPUT_SOURCE="bundle:$JOB_ROOT/bundle/bundle.zip"')
    lines.append('elif [[ -f "$JOB_ROOT/merged.jsonl.gz" ]]; then')
    lines.append('  INPUT_ARGS+=("--input" "$JOB_ROOT/merged.jsonl.gz")')
    lines.append('  INPUT_SOURCE="merged:$JOB_ROOT/merged.jsonl.gz"')
    lines.append('elif [[ -f "$JOB_ROOT/merged.jsonl" ]]; then')
    lines.append('  INPUT_ARGS+=("--input" "$JOB_ROOT/merged.jsonl")')
    lines.append('  INPUT_SOURCE="merged:$JOB_ROOT/merged.jsonl"')
    lines.append('elif [[ -d "$JOB_ROOT/shards" ]]; then')
    lines.append('  INPUT_ARGS+=("--input" "$JOB_ROOT/shards")')
    lines.append('  INPUT_SOURCE="shards:$JOB_ROOT/shards"')
    lines.append("else")
    lines.append('  echo "No bundle/merged/shards input found under reviewer pack root." >&2')
    lines.append("  exit 2")
    lines.append("fi")
    lines.append("")
    lines.append('if [[ -n "$RSD_CHI2_FIELD" ]]; then')
    lines.append('  FIELD_ARGS=("--rsd-chi2-field" "$RSD_CHI2_FIELD")')
    lines.append("else")
    lines.append('  FIELD_ARGS=()')
    lines.append("fi")
    lines.append("")
    lines.append('echo \"[info] boltzmann_export input=$INPUT_SOURCE rank_by=$RANK_BY eligible_status=$ELIGIBLE_STATUS outdir=$OUTDIR\"')
    lines.append("")
    lines.append('cmd=("$PY" "$EXPORT_SCRIPT")')
    lines.append('cmd+=("${INPUT_ARGS[@]}")')
    lines.append('cmd+=("--rank-by" "$RANK_BY" "--eligible-status" "$ELIGIBLE_STATUS")')
    lines.append('cmd+=("--created-utc" "$CREATED_UTC" "--outdir" "$OUTDIR" "--format" "text")')
    lines.append('if [[ "${#FIELD_ARGS[@]}" -gt 0 ]]; then')
    lines.append('  cmd+=("${FIELD_ARGS[@]}")')
    lines.append("fi")
    lines.append('if [[ "${#ZIP_ARGS[@]}" -gt 0 ]]; then')
    lines.append('  cmd+=("${ZIP_ARGS[@]}")')
    lines.append("fi")
    lines.append('if [[ "$#" -gt 0 ]]; then')
    lines.append('  cmd+=("$@")')
    lines.append("fi")
    lines.append("")
    lines.append('"${cmd[@]}"')
    lines.append('echo "[ok] boltzmann export -> $OUTDIR"')
    lines.append("")
    return "\n".join(lines)


def _render_boltzmann_results_script(*, created_utc: str) -> str:
    lines: List[str] = []
    lines.append("#!/usr/bin/env bash")
    lines.append("set -euo pipefail")
    lines.append("")
    lines.append('JOB_ROOT="$(cd "$(dirname "$0")" && pwd)"')
    lines.append('PY="${GSC_PYTHON:-python3}"')
    lines.append('CREATED_UTC_DEFAULT="' + str(created_utc) + '"')
    lines.append('CREATED_UTC="${GSC_BOLTZMANN_RESULTS_CREATED_UTC:-${GSC_BOLTZMANN_CREATED_UTC:-$CREATED_UTC_DEFAULT}}"')
    lines.append('CODE="${GSC_BOLTZMANN_RESULTS_CODE:-auto}"')
    lines.append('REQUIRE="${GSC_BOLTZMANN_RESULTS_REQUIRE:-none}"')
    lines.append('EXPORT_PACK_RAW="${GSC_BOLTZMANN_EXPORT_PACK:-${GSC_BOLTZMANN_OUTDIR:-./boltzmann_export}}"')
    lines.append('RUN_DIR_RAW="${GSC_BOLTZMANN_RUN_DIR:-${GSC_BOLTZMANN_RESULTS_RUN_DIR:-}}"')
    lines.append('OUTDIR_RAW="${GSC_BOLTZMANN_RESULTS_OUTDIR:-./boltzmann_results}"')
    lines.append('ZIP_OUT_RAW="${GSC_BOLTZMANN_RESULTS_ZIP_OUT:-}"')
    lines.append('MAX_ZIP_MB="${GSC_BOLTZMANN_RESULTS_MAX_ZIP_MB:-50}"')
    lines.append('REPO_ROOT_OVERRIDE="${GSC_REPO_ROOT:-}"')
    lines.append('SNAPSHOT_ZIP="$JOB_ROOT/repo_snapshot/repo_share.zip"')
    lines.append('SNAPSHOT_WORK="${GSC_BOLTZMANN_SNAPSHOT_WORK:-$JOB_ROOT/repo_snapshot/_repo_export}"')
    lines.append('RESULTS_SCRIPT=""')
    lines.append("")
    lines.append('case "$CODE" in')
    lines.append("  auto|class|camb) ;;")
    lines.append('  *) echo "Invalid GSC_BOLTZMANN_RESULTS_CODE=$CODE (allowed: auto|class|camb)" >&2; exit 2 ;;')
    lines.append("esac")
    lines.append('case "$REQUIRE" in')
    lines.append("  none|any_outputs|tt_spectrum) ;;")
    lines.append('  *) echo "Invalid GSC_BOLTZMANN_RESULTS_REQUIRE=$REQUIRE (allowed: none|any_outputs|tt_spectrum)" >&2; exit 2 ;;')
    lines.append("esac")
    lines.append("")
    lines.append('if [[ "$EXPORT_PACK_RAW" = /* ]]; then')
    lines.append('  EXPORT_PACK="$EXPORT_PACK_RAW"')
    lines.append("else")
    lines.append('  EXPORT_PACK="$JOB_ROOT/$EXPORT_PACK_RAW"')
    lines.append("fi")
    lines.append('if [[ -z "$RUN_DIR_RAW" ]]; then')
    lines.append('  echo "GSC_BOLTZMANN_RUN_DIR (or GSC_BOLTZMANN_RESULTS_RUN_DIR) is required for boltzmann_results.sh" >&2')
    lines.append("  exit 2")
    lines.append("fi")
    lines.append('if [[ "$RUN_DIR_RAW" = /* ]]; then')
    lines.append('  RUN_DIR="$RUN_DIR_RAW"')
    lines.append("else")
    lines.append('  RUN_DIR="$JOB_ROOT/$RUN_DIR_RAW"')
    lines.append("fi")
    lines.append('if [[ "$OUTDIR_RAW" = /* ]]; then')
    lines.append('  OUTDIR="$OUTDIR_RAW"')
    lines.append("else")
    lines.append('  OUTDIR="$JOB_ROOT/$OUTDIR_RAW"')
    lines.append("fi")
    lines.append("")
    lines.append('ZIP_ARGS=()')
    lines.append('if [[ -n "$ZIP_OUT_RAW" ]]; then')
    lines.append('  if [[ "$ZIP_OUT_RAW" = /* ]]; then')
    lines.append('    ZIP_ARGS+=("--zip-out" "$ZIP_OUT_RAW")')
    lines.append("  else")
    lines.append('    ZIP_ARGS+=("--zip-out" "$JOB_ROOT/$ZIP_OUT_RAW")')
    lines.append("  fi")
    lines.append('  ZIP_ARGS+=("--max-zip-mb" "$MAX_ZIP_MB")')
    lines.append("fi")
    lines.append("")
    lines.append('if [[ -f "$SNAPSHOT_ZIP" ]]; then')
    lines.append('  mkdir -p "$SNAPSHOT_WORK"')
    lines.append('  if [[ ! -f "$SNAPSHOT_WORK/.extract_ok" ]]; then')
    lines.append('    rm -rf "$SNAPSHOT_WORK"')
    lines.append('    mkdir -p "$SNAPSHOT_WORK"')
    lines.append('    "$PY" - "$SNAPSHOT_ZIP" "$SNAPSHOT_WORK" <<\'PY_EXTRACT\'')
    lines.append("import shutil")
    lines.append("import sys")
    lines.append("from pathlib import Path")
    lines.append("import zipfile")
    lines.append("")
    lines.append("zip_path = Path(sys.argv[1]).resolve()")
    lines.append("work = Path(sys.argv[2]).resolve()")
    lines.append("tmp = work / '_tmp_extract'")
    lines.append("if tmp.exists():")
    lines.append("    shutil.rmtree(tmp)")
    lines.append("tmp.mkdir(parents=True, exist_ok=True)")
    lines.append("with zipfile.ZipFile(zip_path, 'r') as zf:")
    lines.append("    zf.extractall(tmp)")
    lines.append("candidates = sorted(tmp.rglob('phase2_pt_boltzmann_results_pack.py'))")
    lines.append("if not candidates:")
    lines.append("    raise SystemExit(2)")
    lines.append("repo_root = candidates[0].resolve().parents[2]")
    lines.append("dst = work / 'v11.0.0'")
    lines.append("if dst.exists():")
    lines.append("    shutil.rmtree(dst)")
    lines.append("dst.parent.mkdir(parents=True, exist_ok=True)")
    lines.append("shutil.move(str(repo_root / 'v11.0.0'), str(dst))")
    lines.append("shutil.rmtree(tmp)")
    lines.append("(work / '.extract_ok').write_text('ok\\n', encoding='utf-8')")
    lines.append("PY_EXTRACT")
    lines.append("  fi")
    lines.append('  if [[ -f "$SNAPSHOT_WORK/v11.0.0/scripts/phase2_pt_boltzmann_results_pack.py" ]]; then')
    lines.append('    RESULTS_SCRIPT="$SNAPSHOT_WORK/v11.0.0/scripts/phase2_pt_boltzmann_results_pack.py"')
    lines.append("  fi")
    lines.append("fi")
    lines.append("")
    lines.append('if [[ -z "$RESULTS_SCRIPT" ]]; then')
    lines.append('  if [[ -n "$REPO_ROOT_OVERRIDE" && -f "$REPO_ROOT_OVERRIDE/v11.0.0/scripts/phase2_pt_boltzmann_results_pack.py" ]]; then')
    lines.append('    RESULTS_SCRIPT="$REPO_ROOT_OVERRIDE/v11.0.0/scripts/phase2_pt_boltzmann_results_pack.py"')
    lines.append('  elif [[ -n "$REPO_ROOT_OVERRIDE" && -f "$REPO_ROOT_OVERRIDE/scripts/phase2_pt_boltzmann_results_pack.py" ]]; then')
    lines.append('    RESULTS_SCRIPT="$REPO_ROOT_OVERRIDE/scripts/phase2_pt_boltzmann_results_pack.py"')
    lines.append("  else")
    lines.append('    echo "Could not locate phase2_pt_boltzmann_results_pack.py (missing repo snapshot and GSC_REPO_ROOT fallback)." >&2')
    lines.append("    exit 2")
    lines.append("  fi")
    lines.append("fi")
    lines.append("")
    lines.append('if [[ ! -d "$EXPORT_PACK" ]]; then')
    lines.append('  echo "Export pack directory not found: $EXPORT_PACK" >&2')
    lines.append("  exit 2")
    lines.append("fi")
    lines.append('if [[ ! -f "$EXPORT_PACK/EXPORT_SUMMARY.json" ]]; then')
    lines.append('  echo "Missing required export-pack file: $EXPORT_PACK/EXPORT_SUMMARY.json" >&2')
    lines.append("  exit 2")
    lines.append("fi")
    lines.append('if [[ ! -f "$EXPORT_PACK/CANDIDATE_RECORD.json" ]]; then')
    lines.append('  echo "Missing required export-pack file: $EXPORT_PACK/CANDIDATE_RECORD.json" >&2')
    lines.append("  exit 2")
    lines.append("fi")
    lines.append('if [[ ! -d "$RUN_DIR" ]]; then')
    lines.append('  echo "External Boltzmann run directory not found: $RUN_DIR" >&2')
    lines.append("  exit 2")
    lines.append("fi")
    lines.append("")
    lines.append('if [[ -n "$ZIP_OUT_RAW" ]]; then')
    lines.append('  ZIP_NOTE="$ZIP_OUT_RAW"')
    lines.append("else")
    lines.append('  ZIP_NOTE="<none>"')
    lines.append("fi")
    lines.append('echo "[info] boltzmann_results export_pack=$EXPORT_PACK run_dir=$RUN_DIR code=$CODE require=$REQUIRE outdir=$OUTDIR zip_out=$ZIP_NOTE"')
    lines.append("")
    lines.append('cmd=(')
    lines.append('  "$PY" "$RESULTS_SCRIPT"')
    lines.append('  "--export-pack" "$EXPORT_PACK"')
    lines.append('  "--run-dir" "$RUN_DIR"')
    lines.append('  "--code" "$CODE"')
    lines.append('  "--require" "$REQUIRE"')
    lines.append('  "--outdir" "$OUTDIR"')
    lines.append('  "--overwrite"')
    lines.append('  "--created-utc" "$CREATED_UTC"')
    lines.append('  "--format" "text"')
    lines.append(')')
    lines.append('if [[ "${#ZIP_ARGS[@]}" -gt 0 ]]; then')
    lines.append('  cmd+=("${ZIP_ARGS[@]}")')
    lines.append("fi")
    lines.append('if [[ "$#" -gt 0 ]]; then')
    lines.append('  cmd+=("$@")')
    lines.append("fi")
    lines.append("")
    lines.append('"${cmd[@]}"')
    lines.append('echo "[ok] boltzmann results -> $OUTDIR"')
    lines.append("")
    return "\n".join(lines)


def _render_boltzmann_run_script(*, created_utc: str, code: str) -> str:
    code_name = str(code)
    if code_name not in {"class", "camb"}:
        raise ReviewerPackUsageError(f"unsupported boltzmann run helper code: {code_name!r}")
    bin_env = "GSC_CLASS_BIN" if code_name == "class" else "GSC_CAMB_BIN"
    default_outdir = f"./boltzmann_run_{code_name}"
    template_name = (
        "BOLTZMANN_INPUT_TEMPLATE_CLASS.ini"
        if code_name == "class"
        else "BOLTZMANN_INPUT_TEMPLATE_CAMB.ini"
    )
    lines: List[str] = []
    lines.append("#!/usr/bin/env bash")
    lines.append("set -euo pipefail")
    lines.append("")
    lines.append('JOB_ROOT="$(cd "$(dirname "$0")" && pwd)"')
    lines.append('PY="${GSC_PYTHON:-python3}"')
    lines.append('CODE="' + code_name + '"')
    lines.append('CREATED_UTC_DEFAULT="' + str(created_utc) + '"')
    lines.append('CREATED_UTC="${GSC_BOLTZMANN_RESULTS_CREATED_UTC:-${GSC_BOLTZMANN_CREATED_UTC:-$CREATED_UTC_DEFAULT}}"')
    lines.append('RUNNER="${GSC_BOLTZMANN_RUNNER:-native}"')
    lines.append('EXPORT_PACK_RAW="${GSC_BOLTZMANN_EXPORT_PACK:-${GSC_BOLTZMANN_OUTDIR:-./boltzmann_export}}"')
    lines.append('RUN_DIR_RAW="${GSC_BOLTZMANN_RUN_OUTDIR:-' + default_outdir + '}"')
    lines.append(f'BIN_RAW="${{{bin_env}:-${{GSC_BOLTZMANN_BIN:-}}}}"')
    lines.append('REPO_ROOT_OVERRIDE="${GSC_REPO_ROOT:-}"')
    lines.append('SNAPSHOT_ZIP="$JOB_ROOT/repo_snapshot/repo_share.zip"')
    lines.append('SNAPSHOT_WORK="${GSC_BOLTZMANN_SNAPSHOT_WORK:-$JOB_ROOT/repo_snapshot/_repo_export}"')
    lines.append('RUN_SCRIPT=""')
    lines.append("")
    lines.append('case "$RUNNER" in')
    lines.append("  native|docker) ;;")
    lines.append('  *) echo "Invalid GSC_BOLTZMANN_RUNNER=$RUNNER (allowed: native|docker)" >&2; exit 2 ;;')
    lines.append("esac")
    lines.append("")
    lines.append('if [[ "$EXPORT_PACK_RAW" = /* ]]; then')
    lines.append('  EXPORT_PACK="$EXPORT_PACK_RAW"')
    lines.append("else")
    lines.append('  EXPORT_PACK="$JOB_ROOT/$EXPORT_PACK_RAW"')
    lines.append("fi")
    lines.append('if [[ "$RUN_DIR_RAW" = /* ]]; then')
    lines.append('  RUN_DIR="$RUN_DIR_RAW"')
    lines.append("else")
    lines.append('  RUN_DIR="$JOB_ROOT/$RUN_DIR_RAW"')
    lines.append("fi")
    lines.append("")
    lines.append('if [[ ! -d "$EXPORT_PACK" ]]; then')
    lines.append('  echo "Export pack directory not found: $EXPORT_PACK" >&2')
    lines.append("  exit 2")
    lines.append("fi")
    lines.append('if [[ ! -f "$EXPORT_PACK/EXPORT_SUMMARY.json" ]]; then')
    lines.append('  echo "Missing required export-pack file: $EXPORT_PACK/EXPORT_SUMMARY.json" >&2')
    lines.append("  exit 2")
    lines.append("fi")
    lines.append('if [[ ! -f "$EXPORT_PACK/CANDIDATE_RECORD.json" ]]; then')
    lines.append('  echo "Missing required export-pack file: $EXPORT_PACK/CANDIDATE_RECORD.json" >&2')
    lines.append("  exit 2")
    lines.append("fi")
    lines.append(f'if [[ ! -f "$EXPORT_PACK/{template_name}" ]]; then')
    lines.append(f'  echo "Missing required export-pack file: $EXPORT_PACK/{template_name}" >&2')
    lines.append("  exit 2")
    lines.append("fi")
    lines.append('if [[ "$RUNNER" == "native" && -z "$BIN_RAW" ]]; then')
    lines.append(f'  echo "{bin_env} (or GSC_BOLTZMANN_BIN) is required when GSC_BOLTZMANN_RUNNER=native" >&2')
    lines.append("  exit 2")
    lines.append("fi")
    lines.append('if [[ "$RUNNER" == "docker" ]]; then')
    lines.append('  if ! command -v docker >/dev/null 2>&1; then')
    lines.append('    echo "docker not found in PATH" >&2')
    lines.append("    exit 2")
    lines.append("  fi")
    lines.append("fi")
    lines.append("")
    lines.append('if [[ -f "$SNAPSHOT_ZIP" ]]; then')
    lines.append('  mkdir -p "$SNAPSHOT_WORK"')
    lines.append('  if [[ ! -f "$SNAPSHOT_WORK/.extract_ok" ]]; then')
    lines.append('    rm -rf "$SNAPSHOT_WORK"')
    lines.append('    mkdir -p "$SNAPSHOT_WORK"')
    lines.append('    "$PY" - "$SNAPSHOT_ZIP" "$SNAPSHOT_WORK" <<\'PY_EXTRACT\'')
    lines.append("import shutil")
    lines.append("import sys")
    lines.append("from pathlib import Path")
    lines.append("import zipfile")
    lines.append("")
    lines.append("zip_path = Path(sys.argv[1]).resolve()")
    lines.append("work = Path(sys.argv[2]).resolve()")
    lines.append("tmp = work / '_tmp_extract'")
    lines.append("if tmp.exists():")
    lines.append("    shutil.rmtree(tmp)")
    lines.append("tmp.mkdir(parents=True, exist_ok=True)")
    lines.append("with zipfile.ZipFile(zip_path, 'r') as zf:")
    lines.append("    zf.extractall(tmp)")
    lines.append("candidates = sorted(tmp.rglob('phase2_pt_boltzmann_run_harness.py'))")
    lines.append("if not candidates:")
    lines.append("    raise SystemExit(2)")
    lines.append("repo_root = candidates[0].resolve().parents[2]")
    lines.append("dst = work / 'v11.0.0'")
    lines.append("if dst.exists():")
    lines.append("    shutil.rmtree(dst)")
    lines.append("dst.parent.mkdir(parents=True, exist_ok=True)")
    lines.append("shutil.move(str(repo_root / 'v11.0.0'), str(dst))")
    lines.append("shutil.rmtree(tmp)")
    lines.append("(work / '.extract_ok').write_text('ok\\n', encoding='utf-8')")
    lines.append("PY_EXTRACT")
    lines.append("  fi")
    lines.append('  if [[ -f "$SNAPSHOT_WORK/v11.0.0/scripts/phase2_pt_boltzmann_run_harness.py" ]]; then')
    lines.append('    RUN_SCRIPT="$SNAPSHOT_WORK/v11.0.0/scripts/phase2_pt_boltzmann_run_harness.py"')
    lines.append("  fi")
    lines.append("fi")
    lines.append("")
    lines.append('if [[ -z "$RUN_SCRIPT" ]]; then')
    lines.append('  if [[ -n "$REPO_ROOT_OVERRIDE" && -f "$REPO_ROOT_OVERRIDE/v11.0.0/scripts/phase2_pt_boltzmann_run_harness.py" ]]; then')
    lines.append('    RUN_SCRIPT="$REPO_ROOT_OVERRIDE/v11.0.0/scripts/phase2_pt_boltzmann_run_harness.py"')
    lines.append('  elif [[ -n "$REPO_ROOT_OVERRIDE" && -f "$REPO_ROOT_OVERRIDE/scripts/phase2_pt_boltzmann_run_harness.py" ]]; then')
    lines.append('    RUN_SCRIPT="$REPO_ROOT_OVERRIDE/scripts/phase2_pt_boltzmann_run_harness.py"')
    lines.append("  else")
    lines.append('    echo "Could not locate phase2_pt_boltzmann_run_harness.py (missing repo snapshot and GSC_REPO_ROOT fallback)." >&2')
    lines.append("    exit 2")
    lines.append("  fi")
    lines.append("fi")
    lines.append("")
    lines.append('echo "[info] boltzmann_run code=$CODE runner=$RUNNER export_pack=$EXPORT_PACK run_dir=$RUN_DIR"')
    lines.append('cmd=(')
    lines.append('  "$PY" "$RUN_SCRIPT"')
    lines.append('  "--export-pack" "$EXPORT_PACK"')
    lines.append('  "--code" "$CODE"')
    lines.append('  "--runner" "$RUNNER"')
    lines.append('  "--run-dir" "$RUN_DIR"')
    lines.append('  "--overwrite"')
    lines.append('  "--created-utc" "$CREATED_UTC"')
    lines.append('  "--format" "text"')
    lines.append(')')
    lines.append('if [[ "$RUNNER" == "native" && -n "$BIN_RAW" ]]; then')
    lines.append('  cmd+=("--bin" "$BIN_RAW")')
    lines.append("fi")
    lines.append('if [[ "$#" -gt 0 ]]; then')
    lines.append('  cmd+=("$@")')
    lines.append("fi")
    lines.append("")
    lines.append('"${cmd[@]}"')
    lines.append('echo "[ok] boltzmann run metadata -> $RUN_DIR/RUN_METADATA.json"')
    lines.append("")
    return "\n".join(lines)


def _copy_reviewer_docs(*, repo_root: Path, outdir: Path) -> None:
    docs_dir = outdir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    for rel in REVIEWER_DOC_REL_PATHS:
        src = repo_root / rel
        if not src.is_file():
            raise ReviewerPackSubtoolError(f"required reviewer doc is missing: {rel}")
        dst = docs_dir / src.name
        shutil.copyfile(src, dst)


def _write_deterministic_zip(zip_out: Path, stage_root: Path) -> Tuple[str, int]:
    _assert_no_symlinks(stage_root)
    _scan_forbidden_paths(stage_root)

    entries: List[Tuple[str, Path, int]] = []
    for path in sorted(stage_root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(stage_root).as_posix()
        mode = 0o755 if os.access(path, os.X_OK) else 0o644
        entries.append((rel, path, mode))

    zip_out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_out, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel, path, mode in entries:
            info = zipfile.ZipInfo(filename=f"{ZIP_ROOT}/{rel}", date_time=FIXED_ZIP_DT)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = ((0o100000 | mode) & 0xFFFF) << 16
            zf.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)

    sha = _sha256_path(zip_out)
    size = int(zip_out.stat().st_size)
    return sha, size


def _build_boltzmann_export_cmd(
    *,
    exporter_script: Path,
    bundle_copy: Path,
    created_utc: str,
    outdir: Path,
    rank_by: str,
    eligible_status: str,
    rsd_chi2_field: Optional[str],
    zip_out: Optional[Path],
    max_zip_mb: float,
) -> List[str]:
    cmd: List[str] = [
        sys.executable,
        str(exporter_script),
        "--bundle",
        str(bundle_copy),
        "--rank-by",
        str(rank_by),
        "--eligible-status",
        str(eligible_status),
        "--created-utc",
        str(created_utc),
        "--outdir",
        str(outdir),
        "--format",
        "json",
    ]
    if isinstance(rsd_chi2_field, str) and rsd_chi2_field.strip():
        cmd.extend(["--rsd-chi2-field", str(rsd_chi2_field).strip()])
    if zip_out is not None:
        cmd.extend(["--zip-out", str(zip_out), "--max-zip-mb", str(float(max_zip_mb))])
    return cmd


def _build_boltzmann_results_cmd(
    *,
    results_script: Path,
    export_pack_dir: Path,
    run_dir: Path,
    code: str,
    outdir: Path,
    created_utc: str,
    zip_out: Optional[Path],
    max_zip_mb: float,
) -> List[str]:
    cmd: List[str] = [
        sys.executable,
        str(results_script),
        "--export-pack",
        str(export_pack_dir),
        "--run-dir",
        str(run_dir),
        "--code",
        str(code),
        "--outdir",
        str(outdir),
        "--overwrite",
        "--created-utc",
        str(created_utc),
        "--format",
        "json",
    ]
    if zip_out is not None:
        cmd.extend(["--zip-out", str(zip_out), "--max-zip-mb", str(float(max_zip_mb))])
    return cmd


def _run_portable_content_lint(*, script_root: Path, stage_root: Path) -> Dict[str, Any]:
    lint_script = script_root / "phase2_portable_content_lint.py"
    if not lint_script.is_file():
        raise ReviewerPackSubtoolError(
            f"{PORTABLE_CONTENT_LINT_MARKER}: missing tool {lint_script}; "
            "run with --skip-portable-content-lint to bypass temporarily."
        )
    cmd = [
        sys.executable,
        str(lint_script),
        "--path",
        str(stage_root),
        "--format",
        "json",
        "--include-glob",
        "*.json",
        "--include-glob",
        "*.jsonl",
    ]
    run = _run_command(cmd, cwd=script_root.parent)
    payload: Optional[Dict[str, Any]] = None
    if run.stdout.strip():
        try:
            decoded = json.loads(run.stdout)
            if isinstance(decoded, Mapping):
                payload = {str(k): decoded[k] for k in decoded.keys()}
        except Exception:
            payload = None

    if run.returncode == 0:
        return payload or {
            "status": "ok",
            "offending_file_count": 0,
            "marker": None,
        }
    if run.returncode == 2:
        marker = str((payload or {}).get("marker", "unknown"))
        offending = int((payload or {}).get("offending_file_count", -1))
        detail = (
            f"{PORTABLE_CONTENT_LINT_MARKER}: marker={marker} offending_file_count={offending} "
            "Use phase2_portable_content_lint.py directly for full details."
        )
        if run.stderr.strip():
            detail += f" stderr={run.stderr.strip()}"
        raise ReviewerPackSubtoolError(detail)

    detail = (
        f"{PORTABLE_CONTENT_LINT_MARKER}: lint tool execution failed (exit={run.returncode}); "
        "run with --skip-portable-content-lint to bypass temporarily."
    )
    if run.stderr.strip():
        detail += f" stderr={run.stderr.strip()}"
    if run.stdout.strip():
        detail += f" stdout={run.stdout.strip()}"
    raise ReviewerPackSubtoolError(detail)


def _make_pack(args: argparse.Namespace) -> Dict[str, Any]:
    this_script = Path(__file__).resolve()
    v101_root = this_script.parents[1]
    repo_root = this_script.parents[2]

    bundle_path = Path(str(args.bundle)).expanduser().resolve()
    if not bundle_path.is_file():
        raise ReviewerPackUsageError(f"--bundle must point to an existing file: {bundle_path}")
    if bundle_path.suffix.lower() != ".zip":
        raise ReviewerPackUsageError("--bundle must be a .zip file")

    outdir = Path(str(args.outdir)).expanduser().resolve()
    zip_out = Path(str(args.zip_out)).expanduser().resolve() if args.zip_out else None

    include_repo_snapshot = int(args.include_repo_snapshot)
    include_paper_assets = int(args.include_paper_assets)
    include_verify = int(args.include_verify)
    verify_strict = int(args.verify_strict)
    include_boltzmann_export = str(args.include_boltzmann_export)
    boltzmann_rank_by = str(args.boltzmann_rank_by)
    boltzmann_eligible_status = str(args.boltzmann_eligible_status)
    boltzmann_rsd_chi2_field = None if args.boltzmann_rsd_chi2_field is None else str(args.boltzmann_rsd_chi2_field)
    boltzmann_zip = bool(args.boltzmann_zip)
    boltzmann_max_zip_mb = float(args.boltzmann_max_zip_mb)
    include_boltzmann_results = str(args.include_boltzmann_results)
    boltzmann_run_dir = None if args.boltzmann_run_dir is None else str(args.boltzmann_run_dir)
    boltzmann_results_code = str(args.boltzmann_results_code)
    boltzmann_results_zip = bool(args.boltzmann_results_zip)
    boltzmann_results_max_zip_mb = float(args.boltzmann_results_max_zip_mb)
    skip_portable_content_lint = bool(args.skip_portable_content_lint)
    created_utc = _normalize_created_utc(str(args.created_utc))

    if args.max_zip_mb is not None and float(args.max_zip_mb) <= 0:
        raise ReviewerPackUsageError("--max-zip-mb must be positive when provided")
    if include_boltzmann_export not in {"off", "on", "auto"}:
        raise ReviewerPackUsageError("--include-boltzmann-export must be one of: off,on,auto")
    if include_boltzmann_results not in {"off", "on", "auto"}:
        raise ReviewerPackUsageError("--include-boltzmann-results must be one of: off,on,auto")
    if boltzmann_zip and boltzmann_max_zip_mb <= 0:
        raise ReviewerPackSubtoolError("--boltzmann-max-zip-mb must be > 0 when --boltzmann-zip is enabled")
    if boltzmann_results_zip and boltzmann_results_max_zip_mb <= 0:
        raise ReviewerPackSubtoolError("--boltzmann-results-max-zip-mb must be > 0 when --boltzmann-results-zip is enabled")

    bundle_sha = _sha256_path(bundle_path)
    bundle_size = int(bundle_path.stat().st_size)

    options: Dict[str, Any] = {
        "snapshot_profile": str(args.snapshot_profile),
        "include_repo_snapshot": include_repo_snapshot,
        "include_paper_assets": include_paper_assets,
        "include_verify": include_verify,
        "verify_strict": verify_strict,
        "include_boltzmann_export": include_boltzmann_export,
        "boltzmann_rank_by": boltzmann_rank_by,
        "boltzmann_eligible_status": boltzmann_eligible_status,
        "boltzmann_rsd_chi2_field": boltzmann_rsd_chi2_field,
        "boltzmann_zip": bool(boltzmann_zip),
        "boltzmann_max_zip_mb": float(boltzmann_max_zip_mb),
        "include_boltzmann_results": include_boltzmann_results,
        "boltzmann_run_dir": None if boltzmann_run_dir is None else _redact_path_token(boltzmann_run_dir),
        "boltzmann_results_code": boltzmann_results_code,
        "boltzmann_results_zip": bool(boltzmann_results_zip),
        "boltzmann_results_max_zip_mb": float(boltzmann_results_max_zip_mb),
        "skip_portable_content_lint": bool(skip_portable_content_lint),
        "created_utc": created_utc,
        "dry_run": bool(args.dry_run),
        "max_zip_mb": None if args.max_zip_mb is None else float(args.max_zip_mb),
    }

    plan = {
        "readme": "README.md",
        "reviewer_guide": "REVIEWER_GUIDE.md",
        "docs": [f"docs/{Path(rel).name}" for rel in REVIEWER_DOC_REL_PATHS],
        "manifest": "manifest.json",
        "bundle_zip": "bundle/bundle.zip",
        "bundle_sha256": "bundle/bundle.sha256",
        "bundle_lineage": "bundle/LINEAGE.json",
        "boltzmann_export_script": "boltzmann_export.sh",
        "boltzmann_run_class_script": "boltzmann_run_class.sh",
        "boltzmann_run_camb_script": "boltzmann_run_camb.sh",
        "boltzmann_results_script": "boltzmann_results.sh",
    }
    if include_repo_snapshot == 1:
        plan["repo_snapshot_zip"] = "repo_snapshot/repo_share.zip"
        plan["repo_snapshot_sha256"] = "repo_snapshot/repo_share.sha256"
        plan["repo_snapshot_manifest"] = "repo_snapshot/repo_snapshot_manifest.json"
    if include_paper_assets == 1:
        plan["paper_assets_root"] = "paper_assets/"
    if include_verify == 1:
        plan["verify_text"] = "verify/verify.txt"
        plan["verify_json"] = "verify/verify.json"
    if include_boltzmann_export in {"on", "auto"}:
        plan["boltzmann_export_root"] = "boltzmann_export/"
        if boltzmann_zip:
            plan["boltzmann_export_zip"] = "boltzmann_export.zip"
    if include_boltzmann_results in {"on", "auto"}:
        plan["boltzmann_results_root"] = "boltzmann_results/"
        if boltzmann_results_zip:
            plan["boltzmann_results_zip"] = "boltzmann_results.zip"

    boltzmann_info: Dict[str, Any] = {
        "mode": include_boltzmann_export,
        "generated": False,
        "zip_generated": False,
        "note": "",
    }
    boltzmann_results_info: Dict[str, Any] = {
        "mode": include_boltzmann_results,
        "generated": False,
        "zip_generated": False,
        "note": "",
        "run_dir": boltzmann_run_dir,
    }
    summary: Dict[str, Any] = {
        "tool_marker": TOOL_MARKER,
        "schema": "phase2_e2_reviewer_pack_summary_v1",
        "created_utc": created_utc,
        "bundle": {
            "basename": bundle_path.name,
            "bytes": bundle_size,
            "sha256": bundle_sha,
        },
        "options": options,
        "plan": plan,
        "boltzmann_export": boltzmann_info,
        "boltzmann_results": boltzmann_results_info,
        "artifacts": [],
        "subtools": [],
        "portable_content_lint": None,
        "pack_zip": None,
    }

    if args.dry_run:
        return summary

    _ensure_empty_dir(outdir)

    # Bundle copy.
    bundle_dir = outdir / "bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    bundle_copy = bundle_dir / "bundle.zip"
    bundle_lineage = bundle_dir / "LINEAGE.json"
    shutil.copyfile(bundle_path, bundle_copy)
    bundle_copy_sha = _sha256_path(bundle_copy)
    if bundle_copy_sha != bundle_sha:
        raise ReviewerPackSubtoolError(
            "bundle copy sha256 mismatch after copy\n"
            f"source_sha256={bundle_sha}\n"
            f"copied_sha256={bundle_copy_sha}\n"
            f"source={bundle_path}\n"
            f"copied={bundle_copy}"
        )
    _write_sha_file(bundle_dir / "bundle.sha256", sha256=bundle_sha, label="bundle.zip")
    _assert_zip_internal_clean(bundle_copy)

    # Include LINEAGE.json directly from bundle when present; otherwise generate
    # from extracted bundle contents to keep reviewer packs self-describing.
    lineage_copied = False
    with zipfile.ZipFile(bundle_copy, "r") as zf:
        names = sorted(str(n) for n in zf.namelist())
        lineage_candidates = [n for n in names if str(n).rstrip("/") and str(n).endswith("/LINEAGE.json")]
        if "LINEAGE.json" in names:
            lineage_candidates.insert(0, "LINEAGE.json")
        if lineage_candidates:
            chosen = lineage_candidates[0]
            bundle_lineage.write_bytes(zf.read(chosen))
            lineage_copied = True

    if not lineage_copied:
        with tempfile.TemporaryDirectory() as td:
            td_root = Path(td).resolve()
            with zipfile.ZipFile(bundle_copy, "r") as zf:
                zf.extractall(td_root)
            extracted_bundle_root = _detect_bundle_root_from_extracted_tree(td_root)
            lineage_cmd = [
                sys.executable,
                str(v101_root / "scripts" / "phase2_lineage_dag.py"),
                "--bundle-dir",
                str(extracted_bundle_root),
                "--out",
                str(bundle_lineage),
                "--created-utc",
                str(created_utc),
                "--format",
                "json",
            ]
            lineage_run = _run_command(lineage_cmd, cwd=repo_root)
            summary["subtools"].append(
                {
                    "name": "phase2_lineage_dag",
                    "command": lineage_run.command,
                    "returncode": lineage_run.returncode,
                }
            )
            if lineage_run.returncode != 0:
                raise ReviewerPackSubtoolError(
                    "phase2_lineage_dag failed while preparing bundle lineage\n"
                    f"cmd: {_format_command(lineage_run.command)}\n"
                    f"stdout:\n{lineage_run.stdout}\n"
                    f"stderr:\n{lineage_run.stderr}"
                )

    _copy_reviewer_docs(repo_root=repo_root, outdir=outdir)
    _write_text_executable(outdir / "boltzmann_export.sh", _render_boltzmann_export_script(created_utc=created_utc) + "\n")
    _write_text_executable(
        outdir / "boltzmann_run_class.sh",
        _render_boltzmann_run_script(created_utc=created_utc, code="class") + "\n",
    )
    _write_text_executable(
        outdir / "boltzmann_run_camb.sh",
        _render_boltzmann_run_script(created_utc=created_utc, code="camb") + "\n",
    )
    _write_text_executable(outdir / "boltzmann_results.sh", _render_boltzmann_results_script(created_utc=created_utc) + "\n")

    # Optional repo snapshot.
    if include_repo_snapshot == 1:
        snapshot_dir = outdir / "repo_snapshot"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot_zip = snapshot_dir / "repo_share.zip"
        snapshot_manifest = snapshot_dir / "repo_snapshot_manifest.json"
        snapshot_cmd = [
            sys.executable,
            str(v101_root / "scripts" / "make_repo_snapshot.py"),
            "--repo-root",
            str(repo_root),
            "--profile",
            str(args.snapshot_profile),
            "--snapshot-format",
            "zip",
            "--out",
            str(snapshot_zip),
            "--json-out",
            str(snapshot_manifest),
        ]
        snapshot_run = _run_command(snapshot_cmd, cwd=repo_root)
        summary["subtools"].append(
            {
                "name": "make_repo_snapshot",
                "command": snapshot_run.command,
                "returncode": snapshot_run.returncode,
            }
        )
        if snapshot_run.returncode != 0:
            raise ReviewerPackSubtoolError(
                "make_repo_snapshot failed\n"
                f"cmd: {_format_command(snapshot_run.command)}\n"
                f"stdout:\n{snapshot_run.stdout}\n"
                f"stderr:\n{snapshot_run.stderr}"
            )

        snap_sha = _sha256_path(snapshot_zip)
        _write_sha_file(snapshot_dir / "repo_share.sha256", sha256=snap_sha, label="repo_share.zip")
        _assert_zip_internal_clean(snapshot_zip)

    # Optional boltzmann export pre-generation.
    boltzmann_mode = include_boltzmann_export
    if include_boltzmann_results in {"on", "auto"} and boltzmann_mode == "off":
        # results-pack integration requires an export-pack input
        boltzmann_mode = "on" if include_boltzmann_results == "on" else "auto"
        boltzmann_info["note"] = "export auto-enabled for boltzmann results integration"
    if boltzmann_mode in {"on", "auto"}:
        export_dir = outdir / "boltzmann_export"
        export_zip = outdir / "boltzmann_export.zip" if boltzmann_zip else None
        export_cmd = _build_boltzmann_export_cmd(
            exporter_script=v101_root / "scripts" / "phase2_pt_boltzmann_export_pack.py",
            bundle_copy=bundle_copy,
            created_utc=created_utc,
            outdir=export_dir,
            rank_by=boltzmann_rank_by,
            eligible_status=boltzmann_eligible_status,
            rsd_chi2_field=boltzmann_rsd_chi2_field,
            zip_out=export_zip,
            max_zip_mb=boltzmann_max_zip_mb,
        )
        export_run = _run_command(export_cmd, cwd=repo_root)
        summary["subtools"].append(
            {
                "name": "phase2_pt_boltzmann_export_pack",
                "command": export_run.command,
                "returncode": export_run.returncode,
            }
        )
        if export_run.returncode == 0:
            boltzmann_info["generated"] = True
            if not boltzmann_info["note"]:
                boltzmann_info["note"] = "generated"
            if export_zip is not None and export_zip.is_file():
                boltzmann_info["zip_generated"] = True
        else:
            err_blob = "\n".join([export_run.stdout, export_run.stderr]).strip()
            marker_missing_rsd = "MISSING_RSD_CHI2_FIELD_FOR_BOLTZMANN_EXPORT" in err_blob
            if boltzmann_mode == "auto":
                if marker_missing_rsd:
                    boltzmann_info["note"] = "not generated (auto): missing RSD chi2 for requested rank mode"
                else:
                    boltzmann_info["note"] = "not generated (auto): exporter unavailable for current bundle/inputs"
            else:
                if marker_missing_rsd:
                    raise ReviewerPackSubtoolError(
                        "BOLTZMANN_EXPORT_FAILED_MISSING_RSD\n"
                        f"cmd: {_format_command(export_run.command)}\n"
                        f"stdout:\n{export_run.stdout}\n"
                        f"stderr:\n{export_run.stderr}"
                    )
                raise ReviewerPackSubtoolError(
                    "phase2_pt_boltzmann_export_pack failed\n"
                    f"cmd: {_format_command(export_run.command)}\n"
                    f"stdout:\n{export_run.stdout}\n"
                    f"stderr:\n{export_run.stderr}"
                )

    # Optional boltzmann results-pack generation.
    if include_boltzmann_results in {"on", "auto"}:
        marker_file = outdir / "BOLTZMANN_RESULTS_SKIPPED.txt"
        if marker_file.exists():
            marker_file.unlink()

        run_dir_resolved = Path(str(boltzmann_run_dir)).expanduser().resolve() if boltzmann_run_dir else None
        if run_dir_resolved is None:
            if include_boltzmann_results == "on":
                _write_text(marker_file, "BOLTZMANN_RESULTS_REQUIRED_BUT_MISSING: --boltzmann-run-dir not provided\n")
                raise ReviewerPackSubtoolError("BOLTZMANN_RESULTS_REQUIRED_BUT_MISSING")
            boltzmann_results_info["note"] = "not generated (auto): --boltzmann-run-dir not provided"
            _write_text(marker_file, "BOLTZMANN_RESULTS_SKIPPED: --boltzmann-run-dir not provided\n")
        else:
            export_dir = outdir / "boltzmann_export"
            if not export_dir.is_dir():
                if include_boltzmann_results == "on":
                    _write_text(marker_file, "BOLTZMANN_RESULTS_REQUIRED_BUT_MISSING: boltzmann export pack unavailable\n")
                    raise ReviewerPackSubtoolError("BOLTZMANN_RESULTS_REQUIRED_BUT_MISSING")
                boltzmann_results_info["note"] = "not generated (auto): boltzmann export pack unavailable"
                _write_text(marker_file, "BOLTZMANN_RESULTS_SKIPPED: boltzmann export pack unavailable\n")
            else:
                results_dir = outdir / "boltzmann_results"
                results_zip = outdir / "boltzmann_results.zip" if boltzmann_results_zip else None
                results_cmd = _build_boltzmann_results_cmd(
                    results_script=v101_root / "scripts" / "phase2_pt_boltzmann_results_pack.py",
                    export_pack_dir=export_dir,
                    run_dir=run_dir_resolved,
                    code=boltzmann_results_code,
                    outdir=results_dir,
                    created_utc=created_utc,
                    zip_out=results_zip,
                    max_zip_mb=boltzmann_results_max_zip_mb,
                )
                results_run = _run_command(results_cmd, cwd=repo_root)
                summary["subtools"].append(
                    {
                        "name": "phase2_pt_boltzmann_results_pack",
                        "command": results_run.command,
                        "returncode": results_run.returncode,
                    }
                )
                if results_run.returncode == 0:
                    boltzmann_results_info["generated"] = True
                    boltzmann_results_info["note"] = "generated"
                    if results_zip is not None and results_zip.is_file():
                        boltzmann_results_info["zip_generated"] = True
                elif results_run.returncode == 2:
                    err_blob = "\n".join([results_run.stdout, results_run.stderr]).strip()
                    if include_boltzmann_results == "on":
                        _write_text(
                            marker_file,
                            "BOLTZMANN_RESULTS_REQUIRED_BUT_MISSING\n"
                            f"cmd: {_format_command(results_run.command)}\n"
                            f"stdout:\n{results_run.stdout}\n"
                            f"stderr:\n{results_run.stderr}\n",
                        )
                        raise ReviewerPackSubtoolError("BOLTZMANN_RESULTS_REQUIRED_BUT_MISSING")
                    boltzmann_results_info["note"] = "not generated (auto): require/budget gate not satisfied"
                    _write_text(
                        marker_file,
                        "BOLTZMANN_RESULTS_SKIPPED\n"
                        f"cmd: {_format_command(results_run.command)}\n"
                        f"stdout:\n{results_run.stdout}\n"
                        f"stderr:\n{results_run.stderr}\n",
                    )
                    if "MISSING_TT_SPECTRUM_FOR_RESULTS_PACK" in err_blob:
                        boltzmann_results_info["note"] = "not generated (auto): missing TT spectrum for requested gate"
                else:
                    if include_boltzmann_results == "on":
                        raise ReviewerPackSubtoolError(
                            "phase2_pt_boltzmann_results_pack failed\n"
                            f"cmd: {_format_command(results_run.command)}\n"
                            f"stdout:\n{results_run.stdout}\n"
                            f"stderr:\n{results_run.stderr}"
                        )
                    raise ReviewerPackSubtoolError(
                        "phase2_pt_boltzmann_results_pack failed in auto mode (fatal IO/parse failure)\n"
                        f"cmd: {_format_command(results_run.command)}\n"
                        f"stdout:\n{results_run.stdout}\n"
                        f"stderr:\n{results_run.stderr}"
                    )

    # Optional paper assets.
    if include_paper_assets == 1:
        paper_dir = outdir / "paper_assets"
        paper_cmd = [
            sys.executable,
            str(v101_root / "scripts" / "phase2_e2_make_paper_assets.py"),
            "--bundle",
            str(bundle_copy),
            "--mode",
            "all",
            "--outdir",
            str(paper_dir),
            "--created-utc",
            created_utc,
        ]
        paper_run = _run_command(paper_cmd, cwd=repo_root)
        summary["subtools"].append(
            {
                "name": "phase2_e2_make_paper_assets",
                "command": paper_run.command,
                "returncode": paper_run.returncode,
            }
        )
        if paper_run.returncode != 0:
            raise ReviewerPackSubtoolError(
                "phase2_e2_make_paper_assets failed\n"
                f"cmd: {_format_command(paper_run.command)}\n"
                f"stdout:\n{paper_run.stdout}\n"
                f"stderr:\n{paper_run.stderr}"
            )

        manifest_path = paper_dir / "paper_assets_manifest.json"
        if not manifest_path.is_file():
            raise ReviewerPackSubtoolError("phase2_e2_make_paper_assets did not create paper_assets_manifest.json")

    # Optional verify.
    if include_verify == 1:
        verify_dir = outdir / "verify"
        verify_dir.mkdir(parents=True, exist_ok=True)
        verify_json = verify_dir / "verify.json"
        verify_txt = verify_dir / "verify.txt"
        verify_cmd = [
            sys.executable,
            str(v101_root / "scripts" / "phase2_e2_verify_bundle.py"),
            "--bundle",
            str(bundle_copy),
            "--paper-assets",
            "ignore",
        ]
        if verify_strict == 1:
            verify_cmd.extend(["--validate-schemas"])
            if not bool(skip_portable_content_lint):
                verify_cmd.extend(["--lint-portable-content"])
        verify_cmd.extend(["--json-out", str(verify_json)])
        verify_run = _run_command(verify_cmd, cwd=repo_root)
        summary["subtools"].append(
            {
                "name": "phase2_e2_verify_bundle",
                "command": verify_run.command,
                "returncode": verify_run.returncode,
            }
        )

        verify_text = "".join(
            [
                "# phase2_e2_verify_bundle stdout\n",
                verify_run.stdout,
                "\n# phase2_e2_verify_bundle stderr\n",
                verify_run.stderr,
            ]
        )
        _write_text(verify_txt, verify_text)

        if not verify_json.is_file():
            fallback = {
                "tool": "phase2_e2_verify_bundle",
                "ok": verify_run.returncode == 0,
                "exit_code": int(verify_run.returncode),
            }
            _write_json(verify_json, fallback)
        _rewrite_json_portable(verify_json)

        if verify_run.returncode != 0:
            raise ReviewerPackSubtoolError(
                "phase2_e2_verify_bundle failed\n"
                f"cmd: {_format_command(verify_run.command)}\n"
                f"stdout:\n{verify_run.stdout}\n"
                f"stderr:\n{verify_run.stderr}"
            )

    readme_text = _render_readme(
        options,
        bundle_path.name,
        boltzmann_info=boltzmann_info,
        boltzmann_results_info=boltzmann_results_info,
    )
    _write_text(outdir / "README.md", readme_text)
    guide_text = _render_reviewer_guide(
        bundle_path.name,
        created_utc=created_utc,
        verify_strict=verify_strict,
        boltzmann_info=boltzmann_info,
        boltzmann_results_info=boltzmann_results_info,
    )
    _write_text(outdir / "REVIEWER_GUIDE.md", guide_text)

    _redact_json_tree_portable(outdir)
    _assert_no_symlinks(outdir)
    _scan_forbidden_paths(outdir)

    artifacts = _collect_artifacts(outdir, exclude_relpaths=("manifest.json",))
    manifest_payload: Dict[str, Any] = {
        "tool_marker": TOOL_MARKER,
        "schema": "phase2_e2_reviewer_pack_manifest_v1",
        "created_utc": created_utc,
        "bundle": {
            "basename": bundle_path.name,
            "bytes": bundle_size,
            "sha256": bundle_sha,
        },
        "options": options,
        "boltzmann_export": boltzmann_info,
        "boltzmann_results": boltzmann_results_info,
        "artifacts": [
            {
                "path": row.path,
                "bytes": row.bytes,
                "sha256": row.sha256,
            }
            for row in artifacts
        ],
    }
    manifest_path = outdir / "manifest.json"
    _write_json(manifest_path, manifest_payload)
    _rewrite_json_portable(manifest_path)

    if not bool(skip_portable_content_lint):
        lint_payload = _run_portable_content_lint(script_root=v101_root / "scripts", stage_root=outdir)
        summary["portable_content_lint"] = lint_payload

    # Optional deterministic zip.
    pack_zip_meta: Optional[Dict[str, Any]] = None
    if zip_out is not None:
        pack_sha, pack_bytes = _write_deterministic_zip(zip_out, outdir)
        pack_zip_meta = {
            "path": zip_out.name,
            "bytes": int(pack_bytes),
            "sha256": pack_sha,
        }
        if args.max_zip_mb is not None:
            budget = int(float(args.max_zip_mb) * 1024 * 1024)
            if int(pack_bytes) > budget:
                raise ReviewerPackSubtoolError(
                    f"reviewer pack zip exceeds --max-zip-mb budget: bytes={pack_bytes} budget={budget}"
                )

    summary["artifacts"] = [
        {
            "path": row.path,
            "bytes": row.bytes,
            "sha256": row.sha256,
        }
        for row in _collect_artifacts(outdir)
    ]
    summary["pack_zip"] = pack_zip_meta
    return summary


def _summary_text(payload: Mapping[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"tool_marker={payload.get('tool_marker')}")
    bundle = payload.get("bundle") or {}
    lines.append(f"bundle={bundle.get('basename')}")
    lines.append(f"bundle_sha256={bundle.get('sha256')}")
    options = payload.get("options") or {}
    lines.append(
        "options="
        f"repo_snapshot={options.get('include_repo_snapshot')} "
        f"paper_assets={options.get('include_paper_assets')} "
        f"verify={options.get('include_verify')} "
        f"verify_strict={options.get('verify_strict')} "
        f"boltzmann={options.get('include_boltzmann_export')} "
        f"dry_run={options.get('dry_run')}"
    )
    boltz = payload.get("boltzmann_export") or {}
    lines.append(
        "boltzmann_export="
        f"generated={boltz.get('generated')} "
        f"zip_generated={boltz.get('zip_generated')} "
        f"note={boltz.get('note')}"
    )
    boltz_results = payload.get("boltzmann_results") or {}
    lines.append(
        "boltzmann_results="
        f"generated={boltz_results.get('generated')} "
        f"zip_generated={boltz_results.get('zip_generated')} "
        f"note={boltz_results.get('note')}"
    )
    lint_payload = payload.get("portable_content_lint") or {}
    if isinstance(lint_payload, Mapping):
        lines.append(
            "portable_content_lint="
            f"status={lint_payload.get('status', 'skipped')} "
            f"offending_file_count={lint_payload.get('offending_file_count', 0)}"
        )
    lines.append(f"n_artifacts={len(payload.get('artifacts') or [])}")
    pack_zip = payload.get("pack_zip")
    if isinstance(pack_zip, Mapping):
        lines.append(f"pack_zip={pack_zip.get('path')} bytes={pack_zip.get('bytes')} sha256={pack_zip.get('sha256')}")
    else:
        lines.append("pack_zip=none")
    return "\n".join(lines) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        summary = _make_pack(args)
    except ReviewerPackSubtoolError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except ReviewerPackUsageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except ReviewerPackError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.format == "json":
        sys.stdout.write(json.dumps(summary, sort_keys=True, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write(_summary_text(summary))

    if args.json_out:
        _write_json(Path(str(args.json_out)).expanduser().resolve(), summary)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

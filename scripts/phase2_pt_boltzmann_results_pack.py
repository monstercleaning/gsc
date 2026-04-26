#!/usr/bin/env python3
"""Deterministic packager for external Boltzmann (CLASS/CAMB) run outputs.

This tool ingests a previously generated Boltzmann export pack and a directory of
external solver outputs, then emits a small reproducible results pack for review.
It does not compute CMB spectra itself.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
import zipfile


TOOL_NAME = "phase2_pt_boltzmann_results_pack"
SCHEMA_NAME = "phase2_pt_boltzmann_results_pack_v1"
ZIP_ROOT = "boltzmann_results_pack"
FIXED_CREATED_UTC = "2000-01-01T00:00:00Z"

ALLOWLIST_EXTENSIONS: Tuple[str, ...] = (
    ".dat",
    ".txt",
    ".log",
    ".ini",
    ".json",
    ".yaml",
    ".yml",
    ".md",
)

REQUIRED_EXPORT_FILES: Tuple[str, ...] = (
    "EXPORT_SUMMARY.json",
    "CANDIDATE_RECORD.json",
)
OPTIONAL_EXPORT_FILES: Tuple[str, ...] = (
    "BOLTZMANN_INPUT_TEMPLATE_CLASS.ini",
    "BOLTZMANN_INPUT_TEMPLATE_CAMB.ini",
    "README.md",
)

MARKER_MISSING_ANY_OUTPUTS = "MISSING_ANY_OUTPUTS_FOR_RESULTS_PACK"
MARKER_MISSING_TT = "MISSING_TT_SPECTRUM_FOR_RESULTS_PACK"
MARKER_ZIP_BUDGET = "ZIP_BUDGET_EXCEEDED_FOR_RESULTS_PACK"

_CREATED_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_ABS_PATH_RE = re.compile(r"^(?:/|[A-Za-z]:[\\/]|\\\\)")
_PORTABLE_PATH_TOKENS: Tuple[str, ...] = (
    "/Users/",
    "/home/",
    "/var/folders/",
    "C:\\Users\\",
)


class ResultsPackError(Exception):
    """Base error."""


class ResultsPackUsageError(ResultsPackError):
    """Usage/parse/IO validation error."""


def _finite_float(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except Exception:
        return None
    if not math.isfinite(out):
        return None
    return float(out)


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _to_json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _to_json_safe(value[k]) for k in sorted(value.keys(), key=lambda x: str(x))}
    if isinstance(value, list):
        return [_to_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_to_json_safe(v) for v in value]
    if isinstance(value, (str, bool)) or value is None:
        return value
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return None if not math.isfinite(value) else float(value)
    return str(value)


def _looks_like_absolute_path(text: str) -> bool:
    token = str(text).strip()
    if not token:
        return False
    if Path(token).is_absolute():
        return True
    return bool(_ABS_PATH_RE.match(token))


def _contains_absolute_paths(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(_contains_absolute_paths(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_absolute_paths(v) for v in value)
    if isinstance(value, tuple):
        return any(_contains_absolute_paths(v) for v in value)
    if isinstance(value, str):
        if _looks_like_absolute_path(value):
            return True
        return any(token in value for token in _PORTABLE_PATH_TOKENS)
    return False


def _redact_absolute_paths(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _redact_absolute_paths(value[k]) for k in sorted(value.keys(), key=lambda x: str(x))}
    if isinstance(value, list):
        return [_redact_absolute_paths(v) for v in value]
    if isinstance(value, tuple):
        return [_redact_absolute_paths(v) for v in value]
    if isinstance(value, str):
        if _looks_like_absolute_path(value):
            name = Path(str(value)).name
            return f"[abs]/{name}" if name else "[abs]"
        return value
    return value


def _sanitize_portable_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _sanitize_portable_value(value[k]) for k in sorted(value.keys(), key=lambda x: str(x))}
    if isinstance(value, list):
        return [_sanitize_portable_value(v) for v in value]
    if isinstance(value, tuple):
        return [_sanitize_portable_value(v) for v in value]
    if isinstance(value, str):
        out = str(value)
        for token in _PORTABLE_PATH_TOKENS:
            replacement = "[abs]\\" if ("\\" in token and "/" not in token) else "[abs]/"
            out = out.replace(token, replacement)
        stripped = out.strip()
        if _looks_like_absolute_path(stripped):
            name = Path(stripped).name
            return f"[abs]/{name}" if name else "[abs]"
        return out
    return value


def _sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_to_json_safe(payload), sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _normalize_created_utc(value: Optional[str]) -> str:
    text = str(value if value is not None else FIXED_CREATED_UTC).strip()
    if not _CREATED_UTC_RE.match(text):
        raise ResultsPackUsageError("--created-utc must match YYYY-MM-DDTHH:MM:SSZ")
    try:
        parsed = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ResultsPackUsageError("--created-utc must match YYYY-MM-DDTHH:MM:SSZ") from exc
    if parsed.year < 1980:
        raise ResultsPackUsageError("--created-utc year must be >= 1980 for deterministic zip metadata")
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def _zip_dt(created_utc: str) -> Tuple[int, int, int, int, int, int]:
    parsed = datetime.strptime(created_utc, "%Y-%m-%dT%H:%M:%SZ")
    return (parsed.year, parsed.month, parsed.day, parsed.hour, parsed.minute, parsed.second)


def _safe_relative(path: Path) -> str:
    rel = path.as_posix().replace("\\", "/")
    if rel.startswith("/"):
        raise ResultsPackUsageError(f"unsafe absolute member path: {rel}")
    if ".." in Path(rel).parts:
        raise ResultsPackUsageError(f"unsafe parent traversal in path: {rel}")
    return rel


def _assert_tree_has_no_symlinks(root: Path, *, label: str) -> None:
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        dpath = Path(dirpath)
        for d in sorted(dirnames):
            candidate = dpath / d
            if candidate.is_symlink():
                rel = candidate.relative_to(root).as_posix()
                raise ResultsPackUsageError(f"symlink detected in {label}: {rel}")
        for f in sorted(filenames):
            candidate = dpath / f
            if candidate.is_symlink():
                rel = candidate.relative_to(root).as_posix()
                raise ResultsPackUsageError(f"symlink detected in {label}: {rel}")


def _read_json_file(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ResultsPackUsageError(f"invalid JSON file: {path}") from exc
    if not isinstance(payload, Mapping):
        raise ResultsPackUsageError(f"expected top-level JSON object: {path}")
    return {str(k): payload[k] for k in payload.keys()}


def _detect_code(run_dir: Path, *, declared: str) -> Dict[str, Any]:
    mode = str(declared)
    if mode in {"class", "camb"}:
        return {
            "name": mode,
            "mode": "explicit",
            "detected": True,
            "notes": f"code declared explicitly via --code {mode}",
        }

    class_score = 0
    camb_score = 0
    files = sorted([p for p in run_dir.rglob("*") if p.is_file()])

    for path in files:
        name = path.name.lower()
        if "class" in name:
            class_score += 4
        if "camb" in name:
            camb_score += 4
        if any(token in name for token in ("cltt", "clte", "clee", "pk", "matterpk")):
            class_score += 2
        if any(token in name for token in ("scalcls", "lensedcls", "totcls")):
            camb_score += 2

        if path.suffix.lower() in {".log", ".txt"}:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")[:8192].lower()
            except OSError:
                continue
            if "cosmic linear anisotropy" in text or "class v" in text:
                class_score += 3
            if "camb" in text:
                camb_score += 3

    if class_score == 0 and camb_score == 0:
        return {
            "name": "unknown",
            "mode": "auto",
            "detected": False,
            "notes": "auto-detection did not find CLASS/CAMB-specific markers",
        }

    if class_score >= camb_score:
        if class_score == camb_score:
            note = "auto-detected tie; selected class by deterministic tie-break"
        else:
            note = "auto-detected from filenames/log markers"
        return {
            "name": "class",
            "mode": "auto",
            "detected": True,
            "notes": note,
        }

    return {
        "name": "camb",
        "mode": "auto",
        "detected": True,
        "notes": "auto-detected from filenames/log markers",
    }


def _candidate_metadata(export_pack_payload: Mapping[str, Any], candidate_payload: Mapping[str, Any]) -> Dict[str, Any]:
    best = _as_mapping(candidate_payload.get("best"))
    record = _as_mapping(candidate_payload.get("record"))
    selection = _as_mapping(candidate_payload.get("selection"))

    def _pick_string(*values: Any) -> Optional[str]:
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return None

    return {
        "params_hash": _pick_string(best.get("best_params_hash"), record.get("params_hash")),
        "plan_point_id": _pick_string(best.get("best_plan_point_id"), record.get("plan_point_id")),
        "scan_config_sha256": _pick_string(record.get("scan_config_sha256")),
        "plan_source_sha256": _pick_string(record.get("plan_source_sha256")),
        "selection_rank_by": _pick_string(selection.get("rank_by"), export_pack_payload.get("selection", {}).get("rank_by")),
    }


def _parse_tt_rows(path: Path) -> Optional[Dict[str, Any]]:
    rows: List[Tuple[float, float]] = []
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None

    for raw in content.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#") or line.startswith("%") or line.startswith("//"):
            continue
        line = line.replace(",", " ").replace(";", " ")
        parts = [p for p in line.split() if p]
        if len(parts) < 2:
            continue
        ell = _finite_float(parts[0])
        val = _finite_float(parts[1])
        if ell is None or val is None:
            continue
        if ell <= 1.0:
            continue
        rows.append((float(ell), float(val)))

    if len(rows) < 5:
        return None

    rows.sort(key=lambda x: x[0])
    ell_min = int(round(rows[0][0]))
    ell_max = int(round(rows[-1][0]))

    peak_domain = [r for r in rows if 50.0 <= r[0] <= 4000.0 and math.isfinite(r[1])]
    if not peak_domain:
        peak_domain = rows
    peak_row = max(peak_domain, key=lambda x: x[1])

    return {
        "tt_ell_min": int(ell_min),
        "tt_ell_max": int(ell_max),
        "tt_peak1_ell": int(round(peak_row[0])),
    }


def _tt_name_score(relpath: str) -> int:
    name = relpath.lower()
    score = 0
    if "tt" in name:
        score += 12
    if "cltt" in name:
        score += 6
    if "totcls" in name or "scalcls" in name or "lensedcls" in name:
        score += 5
    if "cls" in name:
        score += 2
    if name.endswith(".dat"):
        score += 1
    return score


def _detect_tt(copied_output_paths: Sequence[Tuple[str, Path]]) -> Dict[str, Any]:
    candidates = sorted(
        copied_output_paths,
        key=lambda row: (-_tt_name_score(row[0]), row[0]),
    )
    notes: List[str] = []
    for rel, path in candidates:
        if _tt_name_score(rel) <= 0:
            continue
        parsed = _parse_tt_rows(path)
        if parsed is None:
            notes.append(f"unparseable_tt_candidate:{rel}")
            continue
        parsed.update({"has_tt": True, "tt_file": rel, "note": "parsed_tt_from_allowlisted_output"})
        return parsed

    return {
        "has_tt": False,
        "tt_file": None,
        "tt_ell_min": None,
        "tt_ell_max": None,
        "tt_peak1_ell": None,
        "note": "no parseable TT-like file in allowlisted outputs" if not notes else ",".join(notes[:3]),
    }


def _render_readme(*, created_utc: str, code_info: Mapping[str, Any], candidate: Mapping[str, Any], require_mode: str) -> str:
    lines: List[str] = []
    lines.append("# Boltzmann Results Pack")
    lines.append("")
    lines.append(f"Tool: `{TOOL_NAME}`")
    lines.append(f"Schema: `{SCHEMA_NAME}`")
    lines.append(f"Created UTC: `{created_utc}`")
    lines.append("")
    lines.append("## What this pack is")
    lines.append("- Deterministic package of externally generated CLASS/CAMB outputs.")
    lines.append("- Includes checksums, selected candidate metadata, and a minimal spectra summary.")
    lines.append("- Includes `RUN_METADATA.json` when present in the external run directory.")
    lines.append("- Adds `RUN_METADATA_REDACTED.json` when portable redaction is required.")
    lines.append("- Surfaces external solver provenance (`external_code`) from run metadata when available.")
    lines.append("- Redacts `run.log` path leaks by default; use `--include-unredacted-logs` to include unredacted copy explicitly.")
    lines.append("")
    lines.append("## What this pack is not")
    lines.append("- It does not run CLASS/CAMB by itself.")
    lines.append("- It does not claim a full Planck-likelihood fit or full in-repo perturbations closure.")
    lines.append("")
    lines.append("## Ingested sources")
    lines.append(f"- external_code: `{code_info.get('name')}` (mode=`{code_info.get('mode')}`, detected={bool(code_info.get('detected'))})")
    lines.append(f"- candidate params_hash: `{candidate.get('params_hash') or 'NA'}`")
    lines.append(f"- candidate plan_point_id: `{candidate.get('plan_point_id') or 'NA'}`")
    lines.append(f"- require gate mode: `{require_mode}`")
    lines.append("")
    lines.append("## Reviewer usage")
    lines.append("- Inspect `RESULTS_SUMMARY.json` and verify per-file SHA256.")
    lines.append("- Inspect `outputs/` for external spectra/log products.")
    lines.append("- Use scope docs for interpretation boundaries:")
    lines.append("  - `v11.0.0/docs/perturbations_and_dm_scope.md`")
    lines.append("  - `v11.0.0/docs/project_status_and_roadmap.md`")
    lines.append("")
    return "\n".join(lines)


def _collect_output_files(run_dir: Path) -> List[Tuple[str, Path]]:
    files: List[Tuple[str, Path]] = []
    for path in sorted(run_dir.rglob("*")):
        if path.is_dir():
            continue
        rel = _safe_relative(path.relative_to(run_dir))
        if rel == "RUN_METADATA.json":
            continue
        if rel.lower() == "run.log":
            continue
        ext = path.suffix.lower()
        if ext not in ALLOWLIST_EXTENSIONS:
            continue
        files.append((rel, path))
    return files


def _contains_run_log_markers(*, text: str, run_dir_abs: str) -> bool:
    hay = str(text or "")
    if run_dir_abs and run_dir_abs in hay:
        return True
    run_dir_posix = str(run_dir_abs).replace("\\", "/")
    if run_dir_posix and run_dir_posix in hay:
        return True
    for token in _PORTABLE_PATH_TOKENS:
        if token in hay:
            return True
    return False


def _redact_run_log_text(*, text: str, run_dir_abs: str) -> str:
    out = str(text or "")
    tokens: List[str] = []
    if run_dir_abs:
        tokens.append(str(run_dir_abs))
        run_dir_posix = str(run_dir_abs).replace("\\", "/")
        if run_dir_posix not in tokens:
            tokens.append(run_dir_posix)
        run_dir_win = str(run_dir_abs).replace("/", "\\")
        if run_dir_win not in tokens:
            tokens.append(run_dir_win)
    for token in sorted(tokens, key=len, reverse=True):
        if token:
            out = out.replace(token, ".")

    for token in _PORTABLE_PATH_TOKENS:
        replacement = "[abs]\\" if ("\\" in token and "/" not in token) else "[abs]/"
        out = out.replace(token, replacement)
    return out


def _write_deterministic_zip(*, zip_out: Path, outdir: Path, zip_dt: Tuple[int, int, int, int, int, int]) -> Tuple[str, int]:
    _assert_tree_has_no_symlinks(outdir, label="outdir")

    rows: List[Tuple[str, Path, int]] = []
    for path in sorted(outdir.rglob("*")):
        if not path.is_file():
            continue
        rel = _safe_relative(path.relative_to(outdir))
        mode = 0o755 if os.access(path, os.X_OK) else 0o644
        rows.append((rel, path, mode))

    zip_out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_out, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel, path, mode in rows:
            info = zipfile.ZipInfo(filename=f"{ZIP_ROOT}/{rel}", date_time=zip_dt)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = ((0o100000 | mode) & 0xFFFF) << 16
            zf.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)

    return _sha256_path(zip_out), int(zip_out.stat().st_size)


def _render_text_summary(payload: Mapping[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"tool={payload.get('tool')}")
    lines.append(f"schema={payload.get('schema')}")
    lines.append(f"created_utc={payload.get('created_utc')}")

    code = _as_mapping(payload.get("code"))
    lines.append(
        "code="
        f"name={code.get('name')} mode={code.get('mode')} detected={code.get('detected')}"
    )
    external_code = _as_mapping(payload.get("external_code"))
    if external_code:
        lines.append(f"external_code.runner={external_code.get('runner')}")

    counts = _as_mapping(payload.get("counts"))
    lines.append(
        "counts="
        f"n_files={counts.get('n_files_copied')} total_bytes={counts.get('total_bytes_copied')}"
    )

    spectra = _as_mapping(payload.get("spectra_detected"))
    lines.append(
        "spectra="
        f"has_tt={spectra.get('has_tt')} "
        f"ell_min={spectra.get('tt_ell_min')} "
        f"ell_max={spectra.get('tt_ell_max')} "
        f"peak1={spectra.get('tt_peak1_ell')}"
    )
    run_log = _as_mapping(payload.get("run_log"))
    lines.append(
        "run_log="
        f"path={run_log.get('path')} "
        f"paths_redacted={run_log.get('paths_redacted')} "
        f"note={run_log.get('note')}"
    )

    gates = _as_mapping(payload.get("gates"))
    lines.append(
        "gates="
        f"require={gates.get('require')} ok={gates.get('ok')} marker={gates.get('marker')}"
    )

    zip_meta = payload.get("zip")
    if isinstance(zip_meta, Mapping):
        lines.append(f"zip={zip_meta.get('path')} bytes={zip_meta.get('bytes')} sha256={zip_meta.get('sha256')}")
    else:
        lines.append("zip=none")
    return "\n".join(lines) + "\n"


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Deterministic packager for external CLASS/CAMB output artifacts.",
    )
    ap.add_argument("--export-pack", required=True, help="Directory generated by phase2_pt_boltzmann_export_pack.py")
    ap.add_argument("--run-dir", required=True, help="Directory containing external CLASS/CAMB outputs")
    ap.add_argument("--code", choices=("auto", "class", "camb"), default="auto")
    ap.add_argument("--outdir", required=True, help="Output directory for results pack")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--created-utc", default=FIXED_CREATED_UTC, help="Deterministic UTC timestamp (YYYY-MM-DDTHH:MM:SSZ)")
    ap.add_argument("--zip-out", default=None, help="Optional deterministic zip output path")
    ap.add_argument("--max-zip-mb", type=float, default=50.0, help="Zip-size budget when --zip-out is provided")
    ap.add_argument(
        "--include-unredacted-logs",
        action="store_true",
        help="Include run.log payload as outputs/run_UNREDACTED.log when redaction is required.",
    )
    ap.add_argument("--require", choices=("none", "any_outputs", "tt_spectrum"), default="none")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    return ap.parse_args(argv)


def _make_results(args: argparse.Namespace) -> Tuple[Dict[str, Any], Optional[str]]:
    export_pack = Path(str(args.export_pack)).expanduser().resolve()
    run_dir = Path(str(args.run_dir)).expanduser().resolve()
    outdir = Path(str(args.outdir)).expanduser().resolve()
    zip_out = Path(str(args.zip_out)).expanduser().resolve() if args.zip_out else None

    if not export_pack.is_dir():
        raise ResultsPackUsageError(f"--export-pack must be an existing directory: {export_pack}")
    if not run_dir.is_dir():
        raise ResultsPackUsageError(f"--run-dir must be an existing directory: {run_dir}")
    if args.max_zip_mb is not None and float(args.max_zip_mb) <= 0:
        raise ResultsPackUsageError("--max-zip-mb must be positive")

    created_utc = _normalize_created_utc(args.created_utc)
    zip_dt = _zip_dt(created_utc)

    required_paths = [export_pack / name for name in REQUIRED_EXPORT_FILES]
    for path in required_paths:
        if not path.is_file():
            raise ResultsPackUsageError(f"required export-pack file missing: {path.name}")

    _assert_tree_has_no_symlinks(export_pack, label="export-pack")
    _assert_tree_has_no_symlinks(run_dir, label="run-dir")

    export_summary = _read_json_file(export_pack / "EXPORT_SUMMARY.json")
    candidate_record = _read_json_file(export_pack / "CANDIDATE_RECORD.json")

    if outdir.exists():
        if not args.overwrite:
            raise ResultsPackUsageError(f"--outdir already exists (use --overwrite): {outdir}")
        if not outdir.is_dir():
            raise ResultsPackUsageError(f"--outdir exists and is not a directory: {outdir}")
        shutil.rmtree(outdir)
    outdir.mkdir(parents=True, exist_ok=False)

    code_info = _detect_code(run_dir, declared=str(args.code))
    candidate = _candidate_metadata(export_summary, candidate_record)

    export_copy_dir = outdir / "export_pack"
    export_copy_dir.mkdir(parents=True, exist_ok=True)
    for name in REQUIRED_EXPORT_FILES + OPTIONAL_EXPORT_FILES:
        src = export_pack / name
        if not src.is_file():
            continue
        shutil.copyfile(src, export_copy_dir / name)

    outputs_dir = outdir / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    copied_rows: List[Dict[str, Any]] = []
    copied_for_tt: List[Tuple[str, Path]] = []
    total_bytes = 0
    run_log_info: Dict[str, Any] = {
        "path": None,
        "paths_redacted": None,
        "note": "run.log not found",
    }

    for rel, src in _collect_output_files(run_dir):
        dst = outputs_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        size = int(dst.stat().st_size)
        sha = _sha256_path(dst)
        copied_rows.append({"relpath": rel, "bytes": size, "sha256": sha})
        copied_for_tt.append((rel, dst))
        total_bytes += size

    run_log_src = run_dir / "run.log"
    if run_log_src.is_file():
        run_log_text = run_log_src.read_text(encoding="utf-8", errors="replace")
        run_dir_abs = str(run_dir.resolve())
        needs_redaction = _contains_run_log_markers(text=run_log_text, run_dir_abs=run_dir_abs)
        if needs_redaction:
            redacted_text = _redact_run_log_text(text=run_log_text, run_dir_abs=run_dir_abs)
            redacted_rel = "run_REDACTED.log"
            redacted_dst = outputs_dir / redacted_rel
            _write_text(redacted_dst, redacted_text)
            redacted_size = int(redacted_dst.stat().st_size)
            copied_rows.append(
                {"relpath": redacted_rel, "bytes": redacted_size, "sha256": _sha256_path(redacted_dst)}
            )
            total_bytes += redacted_size
            run_log_info = {
                "path": f"outputs/{redacted_rel}",
                "paths_redacted": True,
                "note": "absolute host paths redacted from run.log",
            }

            if bool(args.include_unredacted_logs):
                unredacted_rel = "run_UNREDACTED.log"
                unredacted_dst = outputs_dir / unredacted_rel
                shutil.copyfile(run_log_src, unredacted_dst)
                unredacted_size = int(unredacted_dst.stat().st_size)
                copied_rows.append(
                    {"relpath": unredacted_rel, "bytes": unredacted_size, "sha256": _sha256_path(unredacted_dst)}
                )
                total_bytes += unredacted_size
                run_log_info["note"] = "redacted log included; unredacted log included by --include-unredacted-logs"
        else:
            run_log_rel = "run.log"
            run_log_dst = outputs_dir / run_log_rel
            shutil.copyfile(run_log_src, run_log_dst)
            run_log_size = int(run_log_dst.stat().st_size)
            copied_rows.append(
                {"relpath": run_log_rel, "bytes": run_log_size, "sha256": _sha256_path(run_log_dst)}
            )
            total_bytes += run_log_size
            run_log_info = {
                "path": f"outputs/{run_log_rel}",
                "paths_redacted": False,
                "note": "run.log included without path redaction",
            }

    copied_rows.sort(key=lambda row: str(row.get("relpath")))
    spectra = _detect_tt(copied_for_tt)

    run_metadata_row: Optional[Dict[str, Any]] = None
    run_metadata_summary_payload: Optional[Mapping[str, Any]] = None
    run_metadata_src = run_dir / "RUN_METADATA.json"
    if run_metadata_src.is_file():
        run_metadata_dst = outdir / "RUN_METADATA.json"
        shutil.copyfile(run_metadata_src, run_metadata_dst)
        run_metadata_row = {
            "path": "RUN_METADATA.json",
            "bytes": int(run_metadata_dst.stat().st_size),
            "sha256": _sha256_path(run_metadata_dst),
            "source": "RUN_METADATA.json",
            "summary_source": "RUN_METADATA.json",
        }
        try:
            run_metadata_payload = _read_json_file(run_metadata_src)
        except ResultsPackUsageError:
            run_metadata_payload = None
        if isinstance(run_metadata_payload, Mapping):
            run_metadata_summary_payload = run_metadata_payload
        if isinstance(run_metadata_payload, Mapping) and _contains_absolute_paths(run_metadata_payload):
            redacted_payload = _sanitize_portable_value(_redact_absolute_paths(run_metadata_payload))
            redacted_path = outdir / "RUN_METADATA_REDACTED.json"
            _write_json(redacted_path, redacted_payload)
            run_metadata_row["redacted_path"] = "RUN_METADATA_REDACTED.json"
            run_metadata_row["redacted_sha256"] = _sha256_path(redacted_path)
            run_metadata_row["redacted_bytes"] = int(redacted_path.stat().st_size)
            run_metadata_row["summary_source"] = "RUN_METADATA_REDACTED.json"
            run_metadata_summary_payload = redacted_payload

    external_code_summary: Optional[Mapping[str, Any]] = None
    if isinstance(run_metadata_summary_payload, Mapping):
        external_code_raw = run_metadata_summary_payload.get("external_code")
        if isinstance(external_code_raw, Mapping):
            external_code_summary = _sanitize_portable_value(external_code_raw)

    gates: Dict[str, Any] = {
        "require": str(args.require),
        "ok": True,
        "marker": None,
        "message": None,
    }
    gate_marker: Optional[str] = None

    if str(args.require) == "any_outputs" and len(copied_rows) == 0:
        gate_marker = MARKER_MISSING_ANY_OUTPUTS
        gates.update({"ok": False, "marker": gate_marker, "message": "no allowlisted output files were copied"})
    elif str(args.require) == "tt_spectrum" and not bool(spectra.get("has_tt")):
        gate_marker = MARKER_MISSING_TT
        gates.update({"ok": False, "marker": gate_marker, "message": "TT spectrum file could not be detected/parsed"})

    summary: Dict[str, Any] = {
        "tool": TOOL_NAME,
        "schema": SCHEMA_NAME,
        "created_utc": created_utc,
        "code": code_info,
        "candidate": candidate,
        "files": copied_rows,
        "counts": {
            "n_files_copied": len(copied_rows),
            "total_bytes_copied": int(total_bytes),
        },
        "spectra_detected": {
            "has_tt": bool(spectra.get("has_tt", False)),
            "tt_file": spectra.get("tt_file"),
            "tt_ell_min": spectra.get("tt_ell_min"),
            "tt_ell_max": spectra.get("tt_ell_max"),
            "tt_peak1_ell": spectra.get("tt_peak1_ell"),
            "note": spectra.get("note"),
        },
        "run_metadata": run_metadata_row,
        "external_code": external_code_summary,
        "run_log": run_log_info,
        "gates": gates,
        "notes": [
            "ingest/packaging tool for external Boltzmann outputs",
            "does not compute TT/TE/EE spectra in-repo",
            "claim-safe scope: descriptive packaging only, no full Planck-likelihood claim",
        ],
        "zip": None,
    }

    readme = _render_readme(
        created_utc=created_utc,
        code_info=code_info,
        candidate=candidate,
        require_mode=str(args.require),
    )

    _write_text(outdir / "README.md", readme)
    _write_json(outdir / "RESULTS_SUMMARY.json", summary)

    if zip_out is not None:
        zip_sha, zip_bytes = _write_deterministic_zip(zip_out=zip_out, outdir=outdir, zip_dt=zip_dt)
        summary["zip"] = {
            "path": zip_out.name,
            "bytes": int(zip_bytes),
            "sha256": zip_sha,
            "max_zip_mb": float(args.max_zip_mb),
        }
        budget_bytes = int(float(args.max_zip_mb) * 1024 * 1024)
        if int(zip_bytes) > budget_bytes:
            gate_marker = MARKER_ZIP_BUDGET
            summary["gates"] = {
                "require": str(args.require),
                "ok": False,
                "marker": gate_marker,
                "message": f"zip bytes exceed budget ({zip_bytes}>{budget_bytes})",
            }
        _write_json(outdir / "RESULTS_SUMMARY.json", summary)

    return summary, gate_marker


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)

    try:
        payload, gate_marker = _make_results(args)
    except ResultsPackUsageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.format == "json":
        sys.stdout.write(json.dumps(_to_json_safe(payload), sort_keys=True, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write(_render_text_summary(payload))

    if gate_marker is not None:
        print(str(gate_marker), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

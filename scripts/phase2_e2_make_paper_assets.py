#!/usr/bin/env python3
"""Generate deterministic Phase-2 E2 paper assets from scan JSONL/bundle inputs.

This tool is stdlib-only by default and focuses on post-processing:
- drift-constrained closure bound tables
- closure-to-physical-knobs tables

No physics model changes are performed; this is diagnostics/reporting only.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import shutil
import statistics
import subprocess
import sys
import tempfile
import tarfile
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
import zipfile

V101_DIR = Path(__file__).resolve().parents[1]
if str(V101_DIR) not in sys.path:
    sys.path.insert(0, str(V101_DIR))

from gsc.early_time.refine_plan_v1 import (  # noqa: E402
    get_plan_source_sha256,
    iter_plan_points,
    load_refine_plan_v1,
    validate_refine_plan_v1,
)
from phase2_e2_snippets_catalog import (  # noqa: E402
    PHASE2_E2_ALL_MARKER,
    PHASE2_E2_ALL_STEM,
    canonical_snippet_source_relpath,
    canonical_snippet_stems,
    iter_canonical_md_filenames,
    iter_canonical_tex_filenames,
)


SCHEMA_ID = "phase2_e2_paper_assets_v1"
PAPER_ASSETS_MANIFEST_SCHEMA_ID = "phase2_e2_paper_assets_manifest_v1"
DRIFT_DIR_NAME = "paper_assets_cmb_e2_drift_constrained_closure_bound"
KNOBS_DIR_NAME = "paper_assets_cmb_e2_closure_to_physical_knobs"
DEFAULT_CREATED_UTC = "1970-01-01T00:00:00Z"
SF_FSIGMA8_SNIPPET_MARKER = "phase2_sf_fsigma8_snippet_v1"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _normalize_created_utc(value: Optional[str]) -> str:
    text = str(value or "").strip()
    if not text:
        return DEFAULT_CREATED_UTC
    try:
        _ = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception as exc:
        raise SystemExit(f"Invalid --created-utc value: {value!r}") from exc
    return text


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


def _bool_like(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        fv = _finite_float(value)
        if fv is None:
            return None
        if fv == 1.0:
            return True
        if fv == 0.0:
            return False
        return fv > 0.0
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y", "ok"}:
        return True
    if text in {"0", "false", "f", "no", "n"}:
        return False
    return None


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(int(value))
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return f"{float(value):.15g}"
    return str(value)


def _sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _decode_jsonl_bytes(source: str, data: bytes) -> str:
    raw = bytes(data)
    if str(source).lower().endswith(".gz"):
        try:
            raw = gzip.decompress(raw)
        except OSError as exc:
            raise SystemExit(f"Invalid gzip JSONL payload: {source}") from exc
    return raw.decode("utf-8")


def _canonical_json(data: Mapping[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _safe_bundle_member_path(name: str) -> bool:
    posix = PurePosixPath(str(name))
    if posix.is_absolute():
        return False
    return ".." not in posix.parts


def _normalize_repo_root(path: Path) -> Tuple[Path, Path]:
    resolved = path.expanduser().resolve()
    if resolved.name == "v11.0.0":
        repo_root = resolved.parent
        v101 = resolved
    else:
        repo_root = resolved
        v101 = repo_root / "v11.0.0"
    if not v101.is_dir():
        raise SystemExit(f"Could not locate v11.0.0 under repo root: {repo_root}")
    return repo_root, v101


@dataclass(frozen=True)
class InputEntry:
    path: str
    sha256: str
    bytes: int


@dataclass(frozen=True)
class RawRecord:
    source: str
    line: int
    obj: Dict[str, Any]


@dataclass(frozen=True)
class E2Record:
    source: str
    line: int
    params_hash: str
    status: str
    status_ok: bool
    error_present: bool
    model: str
    chi2_cmb: Optional[float]
    chi2_total: Optional[float]
    drift_metric: Optional[float]
    drift_sign_ok: Optional[bool]
    drift_sign_z3: Optional[bool]
    plausible_ok: bool
    plausible_present: bool
    robustness_ok: bool
    robustness_present: bool
    microphysics_penalty: Optional[float]
    microphysics_max_rel_dev: Optional[float]
    params: Dict[str, float]
    cosmo_params: Dict[str, float]
    micro_knobs: Dict[str, float]


def _parse_jsonl_text(source: str, text: str) -> Tuple[List[RawRecord], Dict[str, int]]:
    records: List[RawRecord] = []
    stats = {
        "n_lines": 0,
        "n_blank": 0,
        "n_invalid_json": 0,
        "n_non_object": 0,
    }
    for idx, line in enumerate(text.splitlines(), start=1):
        stats["n_lines"] += 1
        stripped = line.strip()
        if not stripped:
            stats["n_blank"] += 1
            continue
        if stripped.startswith("#"):
            continue
        try:
            parsed = json.loads(stripped)
        except Exception:
            stats["n_invalid_json"] += 1
            continue
        if not isinstance(parsed, Mapping):
            stats["n_non_object"] += 1
            continue
        records.append(RawRecord(source=str(source), line=int(idx), obj={str(k): parsed[k] for k in parsed.keys()}))
    return records, stats


def _load_jsonl_path(path: Path) -> Tuple[List[RawRecord], InputEntry, Dict[str, int]]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise SystemExit(f"JSONL not found: {resolved}")
    data = resolved.read_bytes()
    text = _decode_jsonl_bytes(str(resolved), data)
    records, stats = _parse_jsonl_text(str(resolved), text)
    entry = InputEntry(
        path=str(resolved),
        sha256=_sha256_bytes(data),
        bytes=len(data),
    )
    return records, entry, stats


def _iter_bundle_jsonl_payloads(bundle_path: Path) -> List[Tuple[str, bytes]]:
    resolved = bundle_path.expanduser().resolve()
    if resolved.is_dir():
        payloads: List[Tuple[str, bytes]] = []
        for candidate in sorted(list(resolved.rglob("*.jsonl")) + list(resolved.rglob("*.jsonl.gz"))):
            if candidate.is_file():
                payloads.append((str(candidate.relative_to(resolved)), candidate.read_bytes()))
        return payloads

    suffix = resolved.suffix.lower()
    if suffix == ".zip":
        payloads = []
        with zipfile.ZipFile(resolved, "r") as zf:
            names = sorted(
                name
                for name in zf.namelist()
                if not name.endswith("/")
                and (name.lower().endswith(".jsonl") or name.lower().endswith(".jsonl.gz"))
            )
            for name in names:
                if not _safe_bundle_member_path(name):
                    raise SystemExit(f"Unsafe bundle member path: {name}")
                payloads.append((str(name), zf.read(name)))
        return payloads

    if suffix in {".tar", ".tgz", ".gz"} or str(resolved).lower().endswith(".tar.gz"):
        payloads = []
        with tarfile.open(resolved, "r:*") as tf:
            members = sorted((m for m in tf.getmembers() if m.isfile()), key=lambda m: str(m.name))
            for member in members:
                name = str(member.name)
                if not (name.lower().endswith(".jsonl") or name.lower().endswith(".jsonl.gz")):
                    continue
                if not _safe_bundle_member_path(name):
                    raise SystemExit(f"Unsafe bundle member path: {name}")
                fh = tf.extractfile(member)
                if fh is None:
                    continue
                payloads.append((name, fh.read()))
        return payloads

    raise SystemExit(f"Unsupported bundle path/type: {resolved}")


def _load_bundle(path: Path) -> Tuple[List[RawRecord], List[InputEntry], Dict[str, int]]:
    resolved = path.expanduser().resolve()
    payloads = _iter_bundle_jsonl_payloads(resolved)
    if not payloads:
        raise SystemExit(f"No *.jsonl records found in bundle: {resolved}")

    records: List[RawRecord] = []
    entries: List[InputEntry] = []
    stats = {
        "n_lines": 0,
        "n_blank": 0,
        "n_invalid_json": 0,
        "n_non_object": 0,
    }
    for member_name, data in payloads:
        text = _decode_jsonl_bytes(member_name, data)
        source = f"{resolved}!{member_name}"
        recs, rec_stats = _parse_jsonl_text(source, text)
        records.extend(recs)
        for key in stats.keys():
            stats[key] += int(rec_stats.get(key, 0))
        entries.append(
            InputEntry(
                path=source,
                sha256=_sha256_bytes(data),
                bytes=len(data),
            )
        )
    return records, entries, stats


def _sorted_counts(mapping: Mapping[str, int]) -> List[Tuple[str, int]]:
    return sorted(
        ((str(k), int(v)) for k, v in mapping.items()),
        key=lambda kv: (-int(kv[1]), str(kv[0])),
    )


def _extract_error_bucket(obj: Mapping[str, Any], *, status: str) -> Optional[str]:
    error_obj = obj.get("error")
    if isinstance(error_obj, Mapping):
        err_type = str(error_obj.get("type", "")).strip()
        if err_type:
            return err_type[:80]
        message = str(error_obj.get("message", "")).strip()
        if message:
            return message.splitlines()[0][:80]
    if isinstance(error_obj, str):
        text = error_obj.strip()
        if text:
            return text.splitlines()[0][:80]
    if status == "error":
        return "error"
    return None


def _record_status_for_audit(obj: Mapping[str, Any]) -> str:
    raw = obj.get("status")
    if raw is None:
        return "unknown"
    text = str(raw).strip().lower()
    return text if text else "unknown"


def _canonical_params_hash(params: Mapping[str, Any]) -> str:
    canonical = _extract_numeric_map(params)
    if not canonical:
        return ""
    return _sha256_bytes(_canonical_json(canonical).encode("utf-8"))


def _iter_bundle_plan_payloads(bundle_path: Path) -> List[Tuple[str, Dict[str, Any]]]:
    resolved = bundle_path.expanduser().resolve()
    payloads: List[Tuple[str, Dict[str, Any]]] = []
    candidate_names = {"plan.json", "refine_plan.json"}

    def _try_add(source: str, data: bytes) -> None:
        try:
            parsed = json.loads(data.decode("utf-8"))
        except Exception:
            return
        if not isinstance(parsed, Mapping):
            return
        try:
            normalized = validate_refine_plan_v1(parsed)
        except Exception:
            return
        payloads.append((str(source), normalized))

    if resolved.is_dir():
        candidates = sorted(
            p for p in resolved.rglob("*.json") if p.is_file() and p.name in candidate_names
        )
        for candidate in candidates:
            rel = candidate.relative_to(resolved).as_posix()
            _try_add(f"{resolved}!{rel}", candidate.read_bytes())
        return payloads

    suffix = resolved.suffix.lower()
    if suffix == ".zip":
        with zipfile.ZipFile(resolved, "r") as zf:
            names = sorted(
                name
                for name in zf.namelist()
                if not name.endswith("/") and PurePosixPath(name).name in candidate_names
            )
            for name in names:
                if not _safe_bundle_member_path(name):
                    raise SystemExit(f"Unsafe bundle member path: {name}")
                _try_add(f"{resolved}!{name}", zf.read(name))
        return payloads

    if suffix in {".tar", ".tgz", ".gz"} or str(resolved).lower().endswith(".tar.gz"):
        with tarfile.open(resolved, "r:*") as tf:
            members = sorted((m for m in tf.getmembers() if m.isfile()), key=lambda m: str(m.name))
            for member in members:
                name = str(member.name)
                if PurePosixPath(name).name not in candidate_names:
                    continue
                if not _safe_bundle_member_path(name):
                    raise SystemExit(f"Unsafe bundle member path: {name}")
                fh = tf.extractfile(member)
                if fh is None:
                    continue
                _try_add(f"{resolved}!{name}", fh.read())
        return payloads

    return payloads


def _resolve_scan_audit_plan(
    *,
    certificate_plan: Optional[Path],
    bundle_inputs: Sequence[Path],
) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]:
    if certificate_plan is not None:
        plan_path = Path(certificate_plan).expanduser().resolve()
        try:
            payload = load_refine_plan_v1(plan_path)
            return str(plan_path), payload, None
        except Exception as exc:
            return str(plan_path), None, f"failed to load --certificate-plan: {exc}"

    candidates: List[Tuple[str, Dict[str, Any]]] = []
    for bundle in sorted(bundle_inputs, key=lambda p: str(p)):
        candidates.extend(_iter_bundle_plan_payloads(bundle))
    if not candidates:
        return None, None, "no plan payload found in bundle inputs"
    source, payload = sorted(candidates, key=lambda item: str(item[0]))[0]
    return str(source), payload, None


def _build_scan_audit_summary(
    *,
    raw_records: Sequence[RawRecord],
    parse_stats: Mapping[str, int],
    inputs: Sequence[InputEntry],
    certificate_plan: Optional[Path],
    bundle_inputs: Sequence[Path],
) -> Dict[str, Any]:
    n_invalid_lines = int(parse_stats.get("n_invalid_json", 0)) + int(parse_stats.get("n_non_object", 0))
    n_records_parsed = int(len(raw_records))

    status_counts: Dict[str, int] = {}
    error_counts: Dict[str, int] = {}
    plan_source_seen: set[str] = set()
    config_sha_seen: set[str] = set()
    rows: List[Dict[str, Any]] = []

    for raw in raw_records:
        obj = raw.obj
        status = _record_status_for_audit(obj)
        status_counts[status] = int(status_counts.get(status, 0)) + 1

        bucket = _extract_error_bucket(obj, status=status)
        if bucket:
            error_counts[bucket] = int(error_counts.get(bucket, 0)) + 1

        plan_source = str(obj.get("plan_source_sha256", "")).strip()
        if plan_source:
            plan_source_seen.add(plan_source)
        config_sha = str(obj.get("scan_config_sha256", "")).strip()
        if config_sha:
            config_sha_seen.add(config_sha)

        chi2_total = _extract_chi2_total(obj)
        rows.append(
            {
                "status": status,
                "eligible_ok": bool(status == "ok" and chi2_total is not None),
                "eligible_any": bool(status != "error" and chi2_total is not None),
                "plan_point_id": str(obj.get("plan_point_id", "")).strip(),
                "plan_source_sha256": plan_source,
                "params_hash": _record_params_hash(obj),
            }
        )

    sorted_errors = _sorted_counts(error_counts)
    top_errors = sorted_errors[:10]
    other_error_count = int(sum(count for _, count in sorted_errors[10:]))

    plan_source, plan_payload, plan_note = _resolve_scan_audit_plan(
        certificate_plan=certificate_plan,
        bundle_inputs=bundle_inputs,
    )
    coverage: Dict[str, Any] = {
        "mode": "unknown",
        "eligible_policy": "ok_only",
        "plan_source": plan_source,
        "plan_points_total": None,
        "plan_points_seen_any": None,
        "plan_points_seen_eligible": None,
        "coverage_any": None,
        "coverage_eligible": None,
        "note": plan_note,
    }

    if plan_payload is not None:
        plan_source_expected = str(get_plan_source_sha256(plan_payload)).strip()
        plan_ids: set[str] = set()
        plan_hashes: set[str] = set()
        for point_id, point_obj, params in iter_plan_points(plan_payload):
            pid = str(point_id).strip()
            if pid:
                plan_ids.add(pid)
            hash_from_params = _canonical_params_hash(params)
            if hash_from_params:
                plan_hashes.add(hash_from_params)
            point_hash = str(point_obj.get("params_hash", "")).strip()
            if point_hash:
                plan_hashes.add(point_hash)

        has_record_point_ids = any(bool(row.get("plan_point_id")) for row in rows)
        seen_any: set[str] = set()
        seen_eligible: set[str] = set()
        foreign_records = 0

        if has_record_point_ids and plan_ids:
            coverage["mode"] = "plan_point_id"
            for row in rows:
                point_id = str(row.get("plan_point_id", "")).strip()
                if not point_id or point_id not in plan_ids:
                    continue
                row_source = str(row.get("plan_source_sha256", "")).strip()
                if row_source and plan_source_expected and row_source != plan_source_expected:
                    foreign_records += 1
                    continue
                seen_any.add(point_id)
                if bool(row.get("eligible_ok")):
                    seen_eligible.add(point_id)
            total = int(len(plan_ids))
        elif plan_hashes:
            coverage["mode"] = "params_hash"
            for row in rows:
                params_hash = str(row.get("params_hash", "")).strip()
                if not params_hash or params_hash not in plan_hashes:
                    continue
                seen_any.add(params_hash)
                if bool(row.get("eligible_ok")):
                    seen_eligible.add(params_hash)
            total = int(len(plan_hashes))
        else:
            total = 0
            coverage["note"] = "plan payload present but has no matching identifiers"

        if total > 0 and coverage["mode"] != "unknown":
            coverage.update(
                {
                    "plan_points_total": int(total),
                    "plan_points_seen_any": int(len(seen_any)),
                    "plan_points_seen_eligible": int(len(seen_eligible)),
                    "coverage_any": float(len(seen_any) / float(total)),
                    "coverage_eligible": float(len(seen_eligible) / float(total)),
                    "foreign_records": int(foreign_records),
                    "plan_source_sha256": plan_source_expected or None,
                }
            )
        else:
            coverage.update(
                {
                    "plan_points_total": int(total),
                    "plan_points_seen_any": 0,
                    "plan_points_seen_eligible": 0,
                    "coverage_any": None,
                    "coverage_eligible": None,
                    "foreign_records": int(foreign_records),
                    "plan_source_sha256": plan_source_expected or None,
                }
            )

    return {
        "schema": "phase2_e2_scan_audit_v1",
        "n_records_parsed": int(n_records_parsed),
        "n_invalid_lines": int(n_invalid_lines),
        "n_inputs_files": int(len(inputs)),
        "inputs_analyzed": [str(entry.path) for entry in sorted(inputs, key=lambda x: str(x.path))],
        "status_counts": [
            {"status": status, "count": int(count)}
            for status, count in _sorted_counts(status_counts)
        ],
        "error_counts": [
            {"error": key, "count": int(count)}
            for key, count in top_errors
        ],
        "error_other_count": int(other_error_count),
        "plan_source_sha256_values": sorted(plan_source_seen),
        "scan_config_sha256_values": sorted(config_sha_seen),
        "coverage": coverage,
        "note": "Counts/coverage are operational metrics; they do not imply physical viability.",
    }


def _render_scan_audit_snippets(summary: Mapping[str, Any]) -> Tuple[str, str]:
    status_rows = list(summary.get("status_counts") or [])
    error_rows = list(summary.get("error_counts") or [])
    coverage = _as_mapping(summary.get("coverage"))
    inputs_analyzed = list(summary.get("inputs_analyzed") or [])

    md_lines: List[str] = [
        "# Phase-2 E2 Scan Audit (Bundle)",
        "",
        "Operational scan-status and coverage summary for the analyzed Phase-2 E2 records.",
        "",
        "## Inputs/Provenance",
        f"- `n_inputs_files`: {int(summary.get('n_inputs_files', 0))}",
        f"- `n_records_parsed`: {int(summary.get('n_records_parsed', 0))}",
        f"- `n_invalid_lines`: {int(summary.get('n_invalid_lines', 0))}",
        "- `plan_source_sha256_values`: " + (
            ", ".join(str(v) for v in list(summary.get("plan_source_sha256_values") or []))
            if list(summary.get("plan_source_sha256_values") or [])
            else "none"
        ),
        "- `scan_config_sha256_values`: " + (
            ", ".join(str(v) for v in list(summary.get("scan_config_sha256_values") or []))
            if list(summary.get("scan_config_sha256_values") or [])
            else "none"
        ),
        "",
        "Analyzed JSONL sources:",
    ]
    if inputs_analyzed:
        for path in inputs_analyzed[:12]:
            md_lines.append(f"- `{path}`")
        if len(inputs_analyzed) > 12:
            md_lines.append(f"- ... (+{len(inputs_analyzed) - 12} more)")
    else:
        md_lines.append("- none")

    md_lines.extend(
        [
            "",
            "## Status counts",
            "| status | count |",
            "|---|---:|",
        ]
    )
    if status_rows:
        for row in status_rows:
            md_lines.append(f"| {row.get('status', '')} | {int(row.get('count', 0))} |")
    else:
        md_lines.append("| none | 0 |")

    md_lines.extend(["", "## Error summary"])
    if error_rows:
        md_lines.extend(["| error bucket | count |", "|---|---:|"])
        for row in error_rows:
            md_lines.append(f"| {row.get('error', '')} | {int(row.get('count', 0))} |")
        other_count = int(summary.get("error_other_count", 0))
        if other_count > 0:
            md_lines.append(f"| other | {other_count} |")
    else:
        md_lines.append("- no error field present")

    md_lines.extend(["", "## Plan coverage"])
    mode = str(coverage.get("mode", "unknown"))
    if mode == "unknown":
        note = str(coverage.get("note", "")).strip() or "no plan provided"
        md_lines.append(f"- coverage: unknown ({note})")
        md_lines.append("- eligible policy: ok_only")
    else:
        md_lines.append(f"- coverage mode: `{mode}`")
        md_lines.append("- eligible policy: `ok_only`")
        md_lines.append(f"- `plan_points_total`: {int(coverage.get('plan_points_total', 0))}")
        md_lines.append(f"- `plan_points_seen_any`: {int(coverage.get('plan_points_seen_any', 0))}")
        md_lines.append(f"- `plan_points_seen_eligible`: {int(coverage.get('plan_points_seen_eligible', 0))}")
        md_lines.append(f"- `coverage_any`: {_fmt_metric(_finite_float(coverage.get('coverage_any')))}")
        md_lines.append(f"- `coverage_eligible`: {_fmt_metric(_finite_float(coverage.get('coverage_eligible')))}")

    md_lines.extend(["", str(summary.get("note", ""))])

    def _tex_escape(text: str) -> str:
        return (
            str(text)
            .replace("\\", "\\textbackslash{}")
            .replace("&", "\\&")
            .replace("%", "\\%")
            .replace("$", "\\$")
            .replace("#", "\\#")
            .replace("_", "\\_")
            .replace("{", "\\{")
            .replace("}", "\\}")
            .replace("~", "\\textasciitilde{}")
            .replace("^", "\\textasciicircum{}")
        )

    tex_lines: List[str] = [
        "% Auto-generated Phase-2 E2 scan audit snippet",
        "\\paragraph{Phase-2 E2 Scan Audit (Bundle)}",
        "\\begin{itemize}",
        f"\\item n\\_inputs\\_files = {int(summary.get('n_inputs_files', 0))}",
        f"\\item n\\_records\\_parsed = {int(summary.get('n_records_parsed', 0))}",
        f"\\item n\\_invalid\\_lines = {int(summary.get('n_invalid_lines', 0))}",
        "\\item plan\\_source\\_sha256\\_values = "
        + _tex_escape(", ".join(str(v) for v in list(summary.get("plan_source_sha256_values") or [])) or "none"),
        "\\item scan\\_config\\_sha256\\_values = "
        + _tex_escape(", ".join(str(v) for v in list(summary.get("scan_config_sha256_values") or [])) or "none"),
        "\\end{itemize}",
        "",
        "\\textbf{Status counts}",
        "\\begin{tabular}{lr}",
        "\\hline",
        "status & count \\\\",
        "\\hline",
    ]
    if status_rows:
        for row in status_rows:
            tex_lines.append(f"{_tex_escape(str(row.get('status', '')))} & {int(row.get('count', 0))} \\\\")
    else:
        tex_lines.append("none & 0 \\\\")
    tex_lines.extend(["\\hline", "\\end{tabular}", "", "\\textbf{Error summary}"])
    if error_rows:
        tex_lines.extend(["\\begin{tabular}{lr}", "\\hline", "error bucket & count \\\\", "\\hline"])
        for row in error_rows:
            tex_lines.append(f"{_tex_escape(str(row.get('error', '')))} & {int(row.get('count', 0))} \\\\")
        other_count = int(summary.get("error_other_count", 0))
        if other_count > 0:
            tex_lines.append(f"other & {other_count} \\\\")
        tex_lines.extend(["\\hline", "\\end{tabular}"])
    else:
        tex_lines.append("No error field present.")

    tex_lines.extend(["", "\\textbf{Plan coverage}"])
    if mode == "unknown":
        note = str(coverage.get("note", "")).strip() or "no plan provided"
        tex_lines.append("Coverage: unknown (" + _tex_escape(note) + ").")
        tex_lines.append("Eligible policy: \\texttt{ok\\_only}.")
    else:
        tex_lines.append("Coverage mode: \\texttt{" + _tex_escape(mode) + "}.")
        tex_lines.append("Eligible policy: \\texttt{ok\\_only}.")
        tex_lines.append(f"plan\\_points\\_total = {int(coverage.get('plan_points_total', 0))}\\\\")
        tex_lines.append(f"plan\\_points\\_seen\\_any = {int(coverage.get('plan_points_seen_any', 0))}\\\\")
        tex_lines.append(
            f"plan\\_points\\_seen\\_eligible = {int(coverage.get('plan_points_seen_eligible', 0))}\\\\"
        )
        tex_lines.append(
            "coverage\\_any = " + _tex_escape(_fmt_metric(_finite_float(coverage.get("coverage_any")))) + "\\\\"
        )
        tex_lines.append(
            "coverage\\_eligible = "
            + _tex_escape(_fmt_metric(_finite_float(coverage.get("coverage_eligible"))))
            + "\\\\"
        )
    tex_lines.extend(["", _tex_escape(str(summary.get("note", "")))])
    return "\n".join(tex_lines), "\n".join(md_lines)


def _emit_scan_audit_assets(
    *,
    outdir: Path,
    raw_records: Sequence[RawRecord],
    parse_stats: Mapping[str, int],
    inputs: Sequence[InputEntry],
    args: argparse.Namespace,
    bundle_inputs: Sequence[Path],
) -> Tuple[List[Path], List[Path]]:
    summary = _build_scan_audit_summary(
        raw_records=raw_records,
        parse_stats=parse_stats,
        inputs=inputs,
        certificate_plan=args.certificate_plan,
        bundle_inputs=bundle_inputs,
    )
    summary_json_path = outdir / "phase2_e2_scan_audit.json"
    summary_md_path = outdir / "phase2_e2_scan_audit.md"
    summary_tex_path = outdir / "phase2_e2_scan_audit.tex"
    snippet_md_path = outdir / "snippets" / "phase2_e2_scan_audit.md"
    snippet_tex_path = outdir / "snippets" / "phase2_e2_scan_audit.tex"

    _write_text(summary_json_path, json.dumps(summary, indent=2, sort_keys=True))
    snippet_tex, snippet_md = _render_scan_audit_snippets(summary)
    _write_text(summary_md_path, snippet_md)
    _write_text(summary_tex_path, snippet_tex)
    _write_text(snippet_md_path, snippet_md)
    _write_text(snippet_tex_path, snippet_tex)

    return [summary_json_path, summary_md_path, summary_tex_path], [snippet_md_path, snippet_tex_path]


def _extract_numeric_map(value: Any) -> Dict[str, float]:
    mapping = _as_mapping(value)
    out: Dict[str, float] = {}
    for key in sorted(mapping.keys(), key=lambda x: str(x)):
        fv = _finite_float(mapping[key])
        if fv is not None:
            out[str(key)] = float(fv)
    return out


def _record_params_hash(obj: Mapping[str, Any]) -> str:
    raw = obj.get("params_hash")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()

    params = _extract_numeric_map(obj.get("params"))
    if params:
        return _sha256_bytes(_canonical_json(params).encode("utf-8"))

    return _sha256_bytes(_canonical_json({str(k): obj[k] for k in sorted(obj.keys())}).encode("utf-8"))


def _extract_chi2_component(value: Any) -> Optional[float]:
    if isinstance(value, Mapping):
        return _finite_float(value.get("chi2"))
    return _finite_float(value)


def _extract_chi2_cmb(obj: Mapping[str, Any]) -> Optional[float]:
    direct = _finite_float(obj.get("chi2_cmb"))
    if direct is not None:
        return direct

    parts = _as_mapping(obj.get("chi2_parts"))
    cmb_priors = _extract_chi2_component(parts.get("cmb_priors"))
    if cmb_priors is not None:
        return cmb_priors
    cmb = _extract_chi2_component(parts.get("cmb"))
    if cmb is not None:
        return cmb

    cmb_priors_block = _as_mapping(obj.get("cmb_priors"))
    nested = _finite_float(cmb_priors_block.get("chi2"))
    if nested is not None:
        return nested

    cmb_block = _as_mapping(obj.get("cmb"))
    nested = _finite_float(cmb_block.get("chi2"))
    if nested is not None:
        return nested

    return None


def _extract_chi2_total(obj: Mapping[str, Any]) -> Optional[float]:
    for key in ("chi2_total", "chi2", "chi2_tot"):
        value = _finite_float(obj.get(key))
        if value is not None:
            return value

    parts = _as_mapping(obj.get("chi2_parts"))
    values: List[float] = []
    for key in sorted(parts.keys(), key=lambda x: str(x)):
        v = _extract_chi2_component(parts[key])
        if v is not None:
            values.append(float(v))
    if values:
        return float(sum(values))
    return None


def _extract_nested_metric(obj: Mapping[str, Any], path: Sequence[str]) -> Optional[float]:
    cur: Any = obj
    for token in path:
        if not isinstance(cur, Mapping) or token not in cur:
            return None
        cur = cur[token]
    return _finite_float(cur)


def _extract_drift_metric(obj: Mapping[str, Any]) -> Optional[float]:
    direct = _finite_float(obj.get("drift_metric"))
    if direct is not None:
        return direct

    candidates = [
        ("drift_metrics", "metric"),
        ("drift", "metric"),
        ("drift_metrics", "min_zdot_z2_5"),
        ("drift", "min_z_dot"),
    ]
    for path in candidates:
        value = _extract_nested_metric(obj, path)
        if value is not None:
            return value
    return None


def _extract_drift_sign_ok(obj: Mapping[str, Any], *, drift_metric: Optional[float], drift_threshold: float) -> Optional[bool]:
    keys = [
        "drift_sign_z2_5",
        "drift_ok_z2_5",
        "drift_sign_ok",
    ]
    for key in keys:
        if key in obj:
            value = _bool_like(obj.get(key))
            if value is not None:
                return bool(value)

    nested_candidates = [
        ("drift_metrics", "sign_ok_z2_5"),
        ("drift_metrics", "ok_z2_5"),
        ("drift", "sign_ok_z2_5"),
    ]
    for path in nested_candidates:
        cur: Any = obj
        ok = True
        for token in path:
            if not isinstance(cur, Mapping) or token not in cur:
                ok = False
                break
            cur = cur[token]
        if ok:
            value = _bool_like(cur)
            if value is not None:
                return bool(value)

    if drift_metric is not None:
        return bool(float(drift_metric) >= float(drift_threshold))
    return None


def _extract_drift_sign_z3(obj: Mapping[str, Any]) -> Optional[bool]:
    keys = [
        "drift_sign_z3",
        "drift_ok_z3",
    ]
    for key in keys:
        if key in obj:
            value = _bool_like(obj.get(key))
            if value is not None:
                return bool(value)

    nested_bool_candidates = [
        ("drift_metrics", "sign_ok_z3"),
        ("drift_metrics", "ok_z3"),
        ("drift", "sign_ok_z3"),
    ]
    for path in nested_bool_candidates:
        cur: Any = obj
        ok = True
        for token in path:
            if not isinstance(cur, Mapping) or token not in cur:
                ok = False
                break
            cur = cur[token]
        if ok:
            value = _bool_like(cur)
            if value is not None:
                return bool(value)

    drift = _as_mapping(obj.get("drift"))
    z_list = drift.get("z_list")
    z_dot = drift.get("z_dot")
    if isinstance(z_list, Sequence) and isinstance(z_dot, Sequence):
        pairs = zip(z_list, z_dot)
        for z_value, zdot_value in pairs:
            zf = _finite_float(z_value)
            if zf is None:
                continue
            if abs(float(zf) - 3.0) > 1.0e-9:
                continue
            zdot = _finite_float(zdot_value)
            if zdot is None:
                return None
            return bool(float(zdot) > 0.0)
    return None


def _extract_plausibility(obj: Mapping[str, Any]) -> Tuple[bool, bool]:
    if "microphysics_plausible_ok" not in obj:
        return True, False
    value = _bool_like(obj.get("microphysics_plausible_ok"))
    return (True if value is None else bool(value)), True


def _extract_robustness(obj: Mapping[str, Any]) -> Tuple[bool, bool]:
    keys = ["robustness_ok", "robust_ok"]
    for key in keys:
        if key in obj:
            value = _bool_like(obj.get(key))
            return (True if value is None else bool(value)), True

    nested = _as_mapping(obj.get("robustness"))
    if "ok" in nested:
        value = _bool_like(nested.get("ok"))
        return (True if value is None else bool(value)), True

    nested = _as_mapping(obj.get("robustness_aggregate"))
    if "ok" in nested:
        value = _bool_like(nested.get("ok"))
        return (True if value is None else bool(value)), True

    return True, False


def _normalize_record(raw: RawRecord, *, drift_threshold: float) -> E2Record:
    obj = raw.obj
    status = str(obj.get("status", "ok")).strip().lower()
    status_ok = True if not status else status == "ok"
    error_present = "error" in obj and obj.get("error") is not None

    params_hash = _record_params_hash(obj)
    chi2_cmb = _extract_chi2_cmb(obj)
    chi2_total = _extract_chi2_total(obj)
    drift_metric = _extract_drift_metric(obj)
    drift_sign_ok = _extract_drift_sign_ok(obj, drift_metric=drift_metric, drift_threshold=drift_threshold)
    drift_sign_z3 = _extract_drift_sign_z3(obj)
    plausible_ok, plausible_present = _extract_plausibility(obj)
    robustness_ok, robustness_present = _extract_robustness(obj)

    params = _extract_numeric_map(obj.get("params"))
    cosmo_params = _extract_numeric_map(obj.get("cosmo_params"))

    micro_knobs = _extract_numeric_map(obj.get("microphysics_knobs"))
    if not micro_knobs:
        micro = _as_mapping(obj.get("microphysics"))
        for key in sorted(micro.keys(), key=lambda x: str(x)):
            if str(key).endswith("_scale"):
                fv = _finite_float(micro[key])
                if fv is not None:
                    micro_knobs[str(key)] = float(fv)

    penalty = _finite_float(obj.get("microphysics_penalty"))
    max_rel_dev = _finite_float(obj.get("microphysics_max_rel_dev"))

    return E2Record(
        source=str(raw.source),
        line=int(raw.line),
        params_hash=str(params_hash),
        status=str(status),
        status_ok=bool(status_ok),
        error_present=bool(error_present),
        model=str(obj.get("model", "")),
        chi2_cmb=chi2_cmb,
        chi2_total=chi2_total,
        drift_metric=drift_metric,
        drift_sign_ok=drift_sign_ok,
        drift_sign_z3=drift_sign_z3,
        plausible_ok=bool(plausible_ok),
        plausible_present=bool(plausible_present),
        robustness_ok=bool(robustness_ok),
        robustness_present=bool(robustness_present),
        microphysics_penalty=penalty,
        microphysics_max_rel_dev=max_rel_dev,
        params=params,
        cosmo_params=cosmo_params,
        micro_knobs=micro_knobs,
    )


def _dedupe_records(records: Sequence[E2Record]) -> List[E2Record]:
    def _status_rank(rec: E2Record) -> int:
        bucket = _status_bucket(rec)
        if bucket == "ok":
            return 0
        if bucket == "skipped":
            return 1
        return 2

    chosen: Dict[str, E2Record] = {}
    for rec in records:
        key = rec.params_hash
        existing = chosen.get(key)
        if existing is None:
            chosen[key] = rec
            continue
        score = (
            _status_rank(rec),
            rec.chi2_cmb if rec.chi2_cmb is not None else float("inf"),
            rec.chi2_total if rec.chi2_total is not None else float("inf"),
            rec.source,
            rec.line,
        )
        existing_score = (
            _status_rank(existing),
            existing.chi2_cmb if existing.chi2_cmb is not None else float("inf"),
            existing.chi2_total if existing.chi2_total is not None else float("inf"),
            existing.source,
            existing.line,
        )
        if score < existing_score:
            chosen[key] = rec
    return [chosen[k] for k in sorted(chosen.keys())]


def _filter_records(
    records: Sequence[E2Record],
    *,
    require_drift_metric: bool,
    plausibility: str,
    robustness: str,
    drift_constraint: str,
) -> Tuple[List[E2Record], Dict[str, int], Dict[str, int]]:
    counts = {
        "n_input": len(records),
        "n_status_skipped": 0,
        "n_missing_chi2_cmb": 0,
        "n_missing_drift_metric": 0,
        "n_plausibility_filtered": 0,
        "n_robustness_filtered": 0,
        "n_drift_filtered": 0,
        "n_output": 0,
    }
    notes = {
        "n_legacy_plausible": 0,
        "n_legacy_robust": 0,
    }

    out: List[E2Record] = []
    for rec in records:
        if not rec.status_ok:
            counts["n_status_skipped"] += 1
            continue
        if rec.chi2_cmb is None:
            counts["n_missing_chi2_cmb"] += 1
            continue
        if require_drift_metric and rec.drift_metric is None:
            counts["n_missing_drift_metric"] += 1
            continue

        if not rec.plausible_present:
            notes["n_legacy_plausible"] += 1
        if not rec.robustness_present:
            notes["n_legacy_robust"] += 1

        if plausibility == "plausible_only" and not rec.plausible_ok:
            counts["n_plausibility_filtered"] += 1
            continue

        if robustness == "robust_only" and not rec.robustness_ok:
            counts["n_robustness_filtered"] += 1
            continue

        if drift_constraint == "positive_only":
            if rec.drift_sign_ok is not True:
                counts["n_drift_filtered"] += 1
                continue

        out.append(rec)

    out_sorted = sorted(
        out,
        key=lambda r: (
            r.chi2_cmb if r.chi2_cmb is not None else float("inf"),
            r.chi2_total if r.chi2_total is not None else float("inf"),
            r.params_hash,
        ),
    )
    counts["n_output"] = len(out_sorted)
    return out_sorted, counts, notes


def _pareto_front(records: Sequence[E2Record]) -> List[E2Record]:
    sorted_points = sorted(
        records,
        key=lambda r: (
            r.chi2_cmb if r.chi2_cmb is not None else float("inf"),
            -(r.drift_metric if r.drift_metric is not None else float("inf")),
            r.params_hash,
        ),
    )
    best_drift = float("-inf")
    out: List[E2Record] = []
    for rec in sorted_points:
        drift = rec.drift_metric if rec.drift_metric is not None else float("-inf")
        if drift > best_drift + 1.0e-15:
            out.append(rec)
            best_drift = drift

    return sorted(
        out,
        key=lambda r: (
            -(r.drift_metric if r.drift_metric is not None else float("inf")),
            r.chi2_cmb if r.chi2_cmb is not None else float("inf"),
            r.params_hash,
        ),
    )


def _sample_thresholds(values: Sequence[float], max_points: int = 200) -> List[float]:
    unique = sorted(set(float(v) for v in values))
    if len(unique) <= int(max_points):
        return unique
    out: List[float] = []
    last_idx = len(unique) - 1
    for i in range(int(max_points)):
        idx = int(round((float(i) / float(max_points - 1)) * float(last_idx)))
        value = unique[idx]
        if not out or value > out[-1]:
            out.append(value)
    return out


def _build_closure_bound_curve(records: Sequence[E2Record]) -> List[Dict[str, Any]]:
    drift_values = [float(r.drift_metric) for r in records if r.drift_metric is not None]
    thresholds = _sample_thresholds(drift_values, max_points=200)
    rows: List[Dict[str, Any]] = []
    for threshold in thresholds:
        candidates = [r for r in records if r.drift_metric is not None and float(r.drift_metric) >= float(threshold)]
        if not candidates:
            continue
        best = min(
            candidates,
            key=lambda r: (
                r.chi2_cmb if r.chi2_cmb is not None else float("inf"),
                r.chi2_total if r.chi2_total is not None else float("inf"),
                r.params_hash,
            ),
        )
        rows.append(
            {
                "drift_threshold": float(threshold),
                "best_chi2_cmb": best.chi2_cmb,
                "best_params_hash": best.params_hash,
                "best_drift_metric": best.drift_metric,
                "best_chi2_total": best.chi2_total,
            }
        )
    return rows


def _pick_best(records: Sequence[E2Record], *, require_positive: bool, require_robust: bool = False) -> Optional[E2Record]:
    candidates = list(records)
    if require_positive:
        candidates = [r for r in candidates if r.drift_sign_ok is True]
    if require_robust:
        candidates = [r for r in candidates if r.robustness_ok]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda r: (
            r.chi2_cmb if r.chi2_cmb is not None else float("inf"),
            r.chi2_total if r.chi2_total is not None else float("inf"),
            r.params_hash,
        ),
    )


def _fmt_metric(value: Optional[float]) -> str:
    if value is None or not math.isfinite(float(value)):
        return "NA"
    return f"{float(value):.6g}"


def _fmt_bool(value: Optional[bool]) -> str:
    if value is None:
        return "NA"
    return "true" if bool(value) else "false"


def _drift_sign_z3_for_summary(rec: E2Record) -> Optional[bool]:
    if rec.drift_sign_z3 is not None:
        return bool(rec.drift_sign_z3)
    return rec.drift_sign_ok


def _status_bucket(rec: E2Record) -> str:
    if rec.error_present or rec.status == "error":
        return "error"
    if rec.status_ok:
        return "ok"
    return "skipped"


def _best_by_chi2_total(records: Sequence[E2Record]) -> Optional[E2Record]:
    candidates = [r for r in records if r.chi2_total is not None]
    if not candidates:
        return None
    return min(candidates, key=lambda r: (float(r.chi2_total or float("inf")), r.params_hash))


def _best_by_chi2_cmb(records: Sequence[E2Record]) -> Optional[E2Record]:
    candidates = [r for r in records if r.chi2_cmb is not None]
    if not candidates:
        return None
    return min(candidates, key=lambda r: (float(r.chi2_cmb or float("inf")), r.params_hash))


def _render_e2_summary_snippets(
    *,
    all_records: Sequence[E2Record],
    certificate_payload: Optional[Mapping[str, Any]] = None,
) -> Tuple[str, str]:
    n_total = len(all_records)
    n_ok = sum(1 for r in all_records if _status_bucket(r) == "ok")
    n_error = sum(1 for r in all_records if _status_bucket(r) == "error")
    n_skipped = n_total - n_ok - n_error

    plausible_present_any = any(r.plausible_present for r in all_records)
    n_plausible_ok = sum(1 for r in all_records if r.plausible_ok)
    fraction_plausible = (float(n_plausible_ok) / float(n_total)) if n_total > 0 else None

    deduped_ok = [r for r in _dedupe_records(all_records) if _status_bucket(r) == "ok"]
    best_overall_ok = _best_by_chi2_total(deduped_ok)
    best_cmb_ok = _best_by_chi2_cmb(deduped_ok)
    best_drift_positive_ok = _best_by_chi2_total(
        [r for r in deduped_ok if _drift_sign_z3_for_summary(r) is True]
    )

    summary_rows: List[Tuple[str, Optional[E2Record]]] = [
        ("best_overall_ok", best_overall_ok),
        ("best_cmb_ok", best_cmb_ok),
        ("best_drift_positive_ok", best_drift_positive_ok),
    ]
    best_joint = _as_mapping(certificate_payload.get("best_joint")) if isinstance(certificate_payload, Mapping) else {}
    best_joint_present = bool(best_joint) and _finite_float(best_joint.get("chi2_joint_total")) is not None

    md_lines = [
        "# Phase-2 E2 Summary (compressed-CMB diagnostics)",
        "",
        "This auto-generated summary is diagnostic-only (compressed priors), not a full CMB-likelihood fit.",
        "See `docs/early_time_e2_status.md` for interpretation guidance.",
        "",
        "## Counts",
        "",
        f"- `N_total`: {n_total}",
        f"- `N_ok`: {n_ok}",
        f"- `N_error`: {n_error}",
        f"- `N_skipped`: {n_skipped}",
    ]
    if plausible_present_any:
        md_lines.append(f"- `N_plausible_ok`: {n_plausible_ok}")
        md_lines.append(f"- `fraction_plausible_ok`: {_fmt_metric(fraction_plausible)}")
    else:
        md_lines.append("- `N_plausible_ok`: NA (legacy JSONL without `microphysics_plausible_ok`)")
        md_lines.append("- `fraction_plausible_ok`: NA")

    if n_total == 0:
        md_lines.extend(
            [
                "",
                "## Best points",
                "",
                "NO INPUT RESULTS FOUND",
            ]
        )
    else:
        md_lines.extend(
            [
                "",
                "## Best points",
                "",
                "| selection | params_hash | chi2_total | chi2_cmb | drift_sign_z3 | microphysics_plausible_ok | microphysics_penalty | microphysics_max_rel_dev |",
                "|---|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for label, rec in summary_rows:
            if rec is None:
                md_lines.append(f"| {label} | NA | NA | NA | NA | NA | NA | NA |")
                continue
            md_lines.append(
                "| "
                + label
                + " | "
                + str(rec.params_hash)
                + " | "
                + _fmt_metric(rec.chi2_total)
                + " | "
                + _fmt_metric(rec.chi2_cmb)
                + " | "
                + _fmt_bool(_drift_sign_z3_for_summary(rec))
                + " | "
                + _fmt_bool(rec.plausible_ok if rec.plausible_present else None)
                + " | "
                + _fmt_metric(rec.microphysics_penalty)
                + " | "
                + _fmt_metric(rec.microphysics_max_rel_dev)
                + " |"
            )
    md_lines.extend(
        [
            "",
            "Drift sign uses `z=3` when available from drift metrics; otherwise falls back to available drift sign fields.",
        ]
    )
    if best_joint_present:
        md_lines.extend(
            [
                "",
                "## JOINT objective summary",
                "",
                f"- `chi2_joint_total`: {_fmt_metric(_finite_float(best_joint.get('chi2_joint_total')))}",
                f"- `chi2_total`: {_fmt_metric(_finite_float(best_joint.get('chi2_total')))}",
                f"- `params_hash`: {best_joint.get('params_hash', '')}",
                f"- `rsd_chi2_field_used`: {best_joint.get('rsd_chi2_field_used', '')}",
                f"- `rsd_chi2_weight`: {_fmt_metric(_finite_float(best_joint.get('rsd_chi2_weight')))}",
            ]
        )

    def _tex_escape(text: str) -> str:
        return str(text).replace("_", "\\_")

    tex_lines = [
        "% Auto-generated Phase-2 E2 compressed-CMB diagnostics summary snippet",
        "\\paragraph{Phase-2 E2 compressed-CMB diagnostics summary}",
        "This auto-generated summary is diagnostic-only (compressed priors), not a full CMB-likelihood fit.",
        "See \\texttt{docs/early\\_time\\_e2\\_status.md} for interpretation guidance.",
        "",
        "\\begin{itemize}",
        f"\\item N\\_total = {n_total}",
        f"\\item N\\_ok = {n_ok}",
        f"\\item N\\_error = {n_error}",
        f"\\item N\\_skipped = {n_skipped}",
    ]
    if plausible_present_any:
        tex_lines.append(f"\\item N\\_plausible\\_ok = {n_plausible_ok}")
        tex_lines.append(f"\\item fraction\\_plausible\\_ok = {_fmt_metric(fraction_plausible)}")
    else:
        tex_lines.append("\\item N\\_plausible\\_ok = NA (legacy JSONL without \\texttt{microphysics\\_plausible\\_ok})")
        tex_lines.append("\\item fraction\\_plausible\\_ok = NA")
    tex_lines.append("\\end{itemize}")
    tex_lines.append("")

    if n_total == 0:
        tex_lines.append("\\textbf{NO INPUT RESULTS FOUND}.")
    else:
        tex_lines.extend(
            [
                "\\begingroup",
                "\\setlength{\\tabcolsep}{3pt}",
                "\\renewcommand{\\arraystretch}{1.05}",
                "\\small",
                "\\begin{tabular}{llllllll}",
                "\\hline",
                "selection & params\\_hash & chi2\\_total & chi2\\_cmb & drift\\_sign\\_z3 & plausible\\_ok & micro\\_penalty & micro\\_max\\_rel\\_dev \\\\",
                "\\hline",
            ]
        )
        for label, rec in summary_rows:
            if rec is None:
                tex_lines.append(_tex_escape(label) + " & NA & NA & NA & NA & NA & NA & NA \\\\")
                continue
            tex_lines.append(
                _tex_escape(label)
                + " & "
                + _tex_escape(str(rec.params_hash))
                + " & "
                + _fmt_metric(rec.chi2_total)
                + " & "
                + _fmt_metric(rec.chi2_cmb)
                + " & "
                + _fmt_bool(_drift_sign_z3_for_summary(rec))
                + " & "
                + _fmt_bool(rec.plausible_ok if rec.plausible_present else None)
                + " & "
                + _fmt_metric(rec.microphysics_penalty)
                + " & "
                + _fmt_metric(rec.microphysics_max_rel_dev)
                + " \\\\"
            )
        tex_lines.extend(["\\hline", "\\end{tabular}", "\\endgroup"])

    tex_lines.extend(
        [
            "",
            "Drift sign uses $z=3$ when available from drift metrics; otherwise it falls back to available drift sign fields.",
        ]
    )
    if best_joint_present:
        tex_lines.extend(
            [
                "",
                "\\paragraph{JOINT objective summary}",
                "\\begin{itemize}",
                "\\item chi2\\_joint\\_total = "
                + _fmt_metric(_finite_float(best_joint.get("chi2_joint_total"))),
                "\\item chi2\\_total = " + _fmt_metric(_finite_float(best_joint.get("chi2_total"))),
                "\\item params\\_hash = " + _tex_escape(str(best_joint.get("params_hash", ""))),
                "\\item rsd\\_chi2\\_field\\_used = " + _tex_escape(str(best_joint.get("rsd_chi2_field_used", ""))),
                "\\item rsd\\_chi2\\_weight = " + _fmt_metric(_finite_float(best_joint.get("rsd_chi2_weight"))),
                "\\end{itemize}",
            ]
        )

    return "\n".join(tex_lines), "\n".join(md_lines)


def _write_csv(path: Path, *, fieldnames: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=[str(x) for x in fieldnames], extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            out = {str(k): _csv_value(row.get(k)) for k in fieldnames}
            writer.writerow(out)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip("\n") + "\n", encoding="utf-8")


def _git_sha(repo_root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        out = str((proc.stdout or "").strip())
        return out if out else "UNKNOWN"
    except Exception:
        return "UNKNOWN"


def _write_manifest(
    *,
    outdir: Path,
    inputs: Sequence[InputEntry],
    outputs: Sequence[Path],
    config: Mapping[str, Any],
    created_utc: str,
    repo_root: Path,
) -> None:
    payload = {
        "schema": SCHEMA_ID,
        "git_sha": _git_sha(repo_root),
        "generated_utc": str(created_utc),
        "inputs": [
            {
                "path": str(entry.path),
                "sha256": str(entry.sha256),
                "bytes": int(entry.bytes),
            }
            for entry in sorted(inputs, key=lambda x: str(x.path))
        ],
        "outputs": [
            {
                "relpath": str(path.resolve().relative_to(outdir.resolve())),
                "sha256": _sha256_file(path),
                "bytes": int(path.stat().st_size),
            }
            for path in sorted([p.resolve() for p in outputs if p.is_file()], key=lambda x: str(x))
        ],
        "config": {str(k): config[k] for k in sorted(config.keys())},
    }
    _write_text(outdir / "manifest.json", json.dumps(payload, indent=2, sort_keys=True))


def _resolve_certificate_require_drift(args: argparse.Namespace) -> str:
    mode = str(getattr(args, "certificate_require_drift", "auto"))
    if mode == "auto":
        return "positive" if str(args.drift_constraint) == "positive_only" else "off"
    return "positive" if mode == "positive" else "off"


def _load_certificate_payload(path: Path) -> Optional[Dict[str, Any]]:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, Mapping):
        return None
    return {str(k): payload[k] for k in payload.keys()}


def _emit_certificate_assets(
    *,
    outdir: Path,
    jsonl_inputs: Sequence[Path],
    bundle_inputs: Sequence[Path],
    args: argparse.Namespace,
    created_utc: str,
    repo_root: Path,
) -> List[Path]:
    script = (repo_root / "v11.0.0" / "scripts" / "phase2_e2_certificate_report.py").resolve()
    if not script.is_file():
        raise SystemExit(f"Certificate script not found: {script}")

    cmd: List[str] = [
        str(sys.executable),
        str(script),
        "--outdir",
        str(outdir),
        "--status-filter",
        str(args.certificate_status_filter),
        "--plausibility",
        str(args.plausibility),
        "--cmb-chi2-threshold",
        str(float(args.certificate_cmb_chi2_threshold)),
        "--late-chi2-threshold",
        str(float(args.certificate_late_chi2_threshold)),
        "--require-drift",
        _resolve_certificate_require_drift(args),
        "--top-k",
        str(int(args.certificate_top_k)),
        "--require-plan-coverage",
        str(args.certificate_require_plan_coverage),
        "--created-utc",
        str(created_utc),
    ]
    if args.certificate_plan is not None:
        cmd.extend(["--plan", str(Path(args.certificate_plan).expanduser().resolve())])

    for path in sorted(jsonl_inputs, key=lambda p: str(p)):
        cmd.extend(["--jsonl", str(Path(path).expanduser().resolve())])
    for path in sorted(bundle_inputs, key=lambda p: str(p)):
        cmd.extend(["--bundle", str(Path(path).expanduser().resolve())])

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        output = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        raise SystemExit(f"Certificate generation failed for {outdir}: {output}")

    outputs: List[Path] = []
    for name in ("e2_certificate.json", "e2_certificate.md"):
        candidate = outdir / name
        if candidate.is_file():
            outputs.append(candidate)
    if not outputs:
        raise SystemExit(f"Certificate generation produced no outputs in: {outdir}")
    return outputs


def _emit_closure_bound_report_assets(
    *,
    outdir: Path,
    jsonl_inputs: Sequence[Path],
    bundle_inputs: Sequence[Path],
    args: argparse.Namespace,
    created_utc: str,
    repo_root: Path,
) -> List[Path]:
    script = (repo_root / "v11.0.0" / "scripts" / "phase2_e2_closure_bound_report.py").resolve()
    if not script.is_file():
        raise SystemExit(f"Closure-bound report script not found: {script}")

    drift_filter = "drift_positive_only" if str(args.drift_constraint) == "positive_only" else "any"
    cmd: List[str] = [
        str(sys.executable),
        str(script),
        "--out-dir",
        str(outdir),
        "--status-filter",
        str(args.certificate_status_filter),
        "--plausibility",
        str(args.plausibility),
        "--drift-filter",
        str(drift_filter),
        "--top-n",
        str(int(args.top_n)),
        "--created-utc",
        str(created_utc),
    ]
    for path in sorted(jsonl_inputs, key=lambda p: str(p)):
        cmd.extend(["--in-jsonl", str(Path(path).expanduser().resolve())])
    for path in sorted(bundle_inputs, key=lambda p: str(p)):
        cmd.extend(["--bundle", str(Path(path).expanduser().resolve())])

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        output = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        raise SystemExit(f"Closure-bound report generation failed for {outdir}: {output}")

    outputs: List[Path] = []
    for name in (
        "phase2_e2_closure_bound_report.json",
        "phase2_e2_closure_bound_report.md",
        "phase2_e2_closure_bound_report.tex",
        "phase2_e2_closure_bound_candidates.csv",
    ):
        candidate = outdir / name
        if candidate.is_file():
            outputs.append(candidate)
    if len(outputs) < 3:
        raise SystemExit(f"Closure-bound report outputs missing in: {outdir}")
    return outputs


def _emit_physical_knobs_report_assets(
    *,
    outdir: Path,
    jsonl_inputs: Sequence[Path],
    bundle_inputs: Sequence[Path],
    args: argparse.Namespace,
    created_utc: str,
    repo_root: Path,
) -> List[Path]:
    script = (repo_root / "v11.0.0" / "scripts" / "phase2_e2_physical_knobs_report.py").resolve()
    if not script.is_file():
        raise SystemExit(f"Physical-knobs report script not found: {script}")

    cmd: List[str] = [
        str(sys.executable),
        str(script),
        "--outdir",
        str(outdir),
        "--top-k",
        str(int(args.top_n)),
        "--status-filter",
        str(args.certificate_status_filter),
        "--plausibility",
        str(args.plausibility),
        "--selection",
        "best_plausible",
    ]
    if str(args.drift_constraint) == "positive_only":
        cmd.append("--require-drift-precheck")
    else:
        cmd.append("--no-require-drift-precheck")

    for path in sorted(jsonl_inputs, key=lambda p: str(p)):
        cmd.extend(["--input-jsonl", str(Path(path).expanduser().resolve())])
    for path in sorted(bundle_inputs, key=lambda p: str(p)):
        cmd.extend(["--bundle", str(Path(path).expanduser().resolve())])

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        output = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        raise SystemExit(f"Physical-knobs report generation failed for {outdir}: {output}")

    outputs: List[Path] = []
    for name in (
        "phase2_e2_physical_knobs_report.json",
        "phase2_e2_physical_knobs.md",
        "phase2_e2_physical_knobs.tex",
    ):
        candidate = outdir / name
        if candidate.is_file():
            outputs.append(candidate)
    if len(outputs) < 3:
        raise SystemExit(f"Physical-knobs report outputs missing in: {outdir}")
    return outputs


def _emit_best_candidates_report_assets(
    *,
    outdir: Path,
    jsonl_inputs: Sequence[Path],
    bundle_inputs: Sequence[Path],
    args: argparse.Namespace,
    repo_root: Path,
) -> List[Path]:
    script = (repo_root / "v11.0.0" / "scripts" / "phase2_e2_best_candidates_report.py").resolve()
    if not script.is_file():
        raise SystemExit(f"Best-candidates report script not found: {script}")

    json_out = outdir / "phase2_e2_best_candidates_report.json"
    md_out = outdir / "phase2_e2_best_candidates.md"
    tex_out = outdir / "phase2_e2_best_candidates.tex"
    sf_md_out = outdir / "phase2_sf_rsd_summary.md"
    sf_tex_out = outdir / "phase2_sf_rsd_summary.tex"

    cmd: List[str] = [
        str(sys.executable),
        str(script),
        "--status-filter",
        str(args.certificate_status_filter),
        "--plausibility",
        str(args.plausibility),
        "--top-n",
        str(int(args.top_n)),
        "--format",
        "text",
        "--json-out",
        str(json_out),
        "--md-out",
        str(md_out),
        "--tex-out",
        str(tex_out),
        "--sf-rsd",
        "--rsd-mode",
        "nuisance_sigma8",
        "--sf-snippet-md-out",
        str(sf_md_out),
        "--sf-snippet-tex-out",
        str(sf_tex_out),
        "--title",
        "Phase-2 E2 Best Candidates",
    ]
    for path in sorted(jsonl_inputs, key=lambda p: str(p)):
        cmd.extend(["--input", str(Path(path).expanduser().resolve())])
    for path in sorted(bundle_inputs, key=lambda p: str(p)):
        cmd.extend(["--input", str(Path(path).expanduser().resolve())])

    cmd_joint = [*cmd, "--rank-by", "joint"]
    proc = subprocess.run(cmd_joint, capture_output=True, text=True)
    if proc.returncode != 0:
        output = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        if proc.returncode == 2 and "missing required RSD fields for joint ranking" in output:
            cmd_cmb = [*cmd, "--rank-by", "cmb"]
            proc = subprocess.run(cmd_cmb, capture_output=True, text=True)
            if proc.returncode != 0:
                output = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
                raise SystemExit(f"Best-candidates report generation failed for {outdir}: {output}")
        else:
            raise SystemExit(f"Best-candidates report generation failed for {outdir}: {output}")

    outputs: List[Path] = []
    for path in (json_out, md_out, tex_out, sf_md_out, sf_tex_out):
        if path.is_file():
            outputs.append(path)
    if len(outputs) < 5:
        raise SystemExit(f"Best-candidates report outputs missing in: {outdir}")
    return outputs


def _emit_rg_sigma_origin_assets(
    *,
    outdir: Path,
    repo_root: Path,
) -> List[Path]:
    flow_script = (repo_root / "v11.0.0" / "scripts" / "phase2_rg_flow_table_report.py").resolve()
    pade_script = (repo_root / "v11.0.0" / "scripts" / "phase2_rg_pade_fit_report.py").resolve()
    if not flow_script.is_file():
        raise SystemExit(f"RG flow-table report script not found: {flow_script}")
    if not pade_script.is_file():
        raise SystemExit(f"RG Padé fit report script not found: {pade_script}")

    flow_json = outdir / "phase2_rg_flow_table_report.json"
    pade_json = outdir / "phase2_rg_pade_fit_report.json"
    cmd_flow: List[str] = [
        str(sys.executable),
        str(flow_script),
        "--format",
        "json",
        "--k-star-g-threshold",
        "1.0",
        "--json-out",
        str(flow_json),
        "--emit-snippets",
        str(outdir),
    ]
    cmd_pade: List[str] = [
        str(sys.executable),
        str(pade_script),
        "--format",
        "json",
        "--mode",
        "summary",
        "--json-out",
        str(pade_json),
        "--emit-snippets",
        str(outdir),
    ]

    proc_flow = subprocess.run(cmd_flow, capture_output=True, text=True)
    if proc_flow.returncode != 0:
        output = ((proc_flow.stdout or "") + "\n" + (proc_flow.stderr or "")).strip()
        raise SystemExit(f"RG flow-table snippet/report generation failed for {outdir}: {output}")
    proc_pade = subprocess.run(cmd_pade, capture_output=True, text=True)
    if proc_pade.returncode != 0:
        output = ((proc_pade.stdout or "") + "\n" + (proc_pade.stderr or "")).strip()
        raise SystemExit(f"RG Padé snippet/report generation failed for {outdir}: {output}")

    outputs: List[Path] = []
    for path in (
        flow_json,
        pade_json,
        outdir / "phase2_rg_flow_table.md",
        outdir / "phase2_rg_flow_table.tex",
        outdir / "phase2_rg_flow_table.json",
        outdir / "phase2_rg_pade_fit.md",
        outdir / "phase2_rg_pade_fit.tex",
        outdir / "phase2_rg_pade_fit.json",
    ):
        if path.is_file():
            outputs.append(path)
    required = [
        outdir / "phase2_rg_flow_table.md",
        outdir / "phase2_rg_flow_table.tex",
        outdir / "phase2_rg_pade_fit.md",
        outdir / "phase2_rg_pade_fit.tex",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("RG snippet outputs missing in " + str(outdir) + ": " + ", ".join(missing))
    return outputs


def _pick_sf_candidate_record(
    *,
    all_records: Sequence[E2Record],
    best_candidates_json: Path,
) -> Optional[E2Record]:
    deduped_ok = [rec for rec in _dedupe_records(all_records) if rec.status == "ok" and rec.chi2_total is not None]
    if not deduped_ok:
        return None

    target_hash: Optional[str] = None
    try:
        payload = json.loads(best_candidates_json.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    if isinstance(payload, Mapping):
        best_joint = _as_mapping(payload.get("best_by_joint"))
        best_cmb = _as_mapping(payload.get("best_by_cmb"))
        for row in (best_joint, best_cmb):
            cand = str(row.get("params_hash", "")).strip()
            if cand:
                target_hash = cand
                break

    if target_hash:
        matches = [rec for rec in deduped_ok if rec.params_hash == target_hash]
        if matches:
            return sorted(matches, key=lambda rec: (float(rec.chi2_total or float("inf")), rec.params_hash))[0]
    return sorted(deduped_ok, key=lambda rec: (float(rec.chi2_total or float("inf")), rec.params_hash))[0]


def _render_sf_unavailable_snippets(*, reason: str) -> Tuple[str, str, Dict[str, Any]]:
    md = "\n".join(
        [
            f"<!-- {SF_FSIGMA8_SNIPPET_MARKER} -->",
            "## Structure formation diagnostics (`fσ8` / RSD)",
            "",
            "- status: `unavailable`",
            f"- reason: `{reason}`",
            "",
            "Scope boundary: linear-theory growth with approximate transfer functions; not a full nonlinear LSS treatment.",
            "",
        ]
    )
    tex = "\n".join(
        [
            f"% {SF_FSIGMA8_SNIPPET_MARKER}",
            "\\paragraph{Structure formation diagnostics ($f\\sigma_8$/RSD).}",
            "Status: unavailable ("
            + str(reason).replace("_", "\\_")
            + ").",
            "\\noindent\\textit{Scope boundary: linear-theory growth with approximate transfer functions; not a full nonlinear LSS treatment.}",
            "",
        ]
    )
    payload = {
        "marker": SF_FSIGMA8_SNIPPET_MARKER,
        "schema": "phase2_sf_fsigma8_snippet_v1",
        "status": "unavailable",
        "reason": str(reason),
    }
    return tex, md, payload


def _emit_sf_fsigma8_assets(
    *,
    outdir: Path,
    all_records: Sequence[E2Record],
    repo_root: Path,
) -> List[Path]:
    script = (repo_root / "v11.0.0" / "scripts" / "phase2_sf_fsigma8_report.py").resolve()
    best_json = outdir / "phase2_e2_best_candidates_report.json"
    sf_json = outdir / "phase2_sf_fsigma8_report.json"
    sf_md = outdir / "phase2_sf_fsigma8.md"
    sf_tex = outdir / "phase2_sf_fsigma8.tex"
    sf_snippet_json = outdir / "phase2_sf_fsigma8.json"

    if not script.is_file():
        tex_text, md_text, payload = _render_sf_unavailable_snippets(reason="missing_phase2_sf_fsigma8_report_script")
        _write_text(sf_tex, tex_text)
        _write_text(sf_md, md_text)
        _write_text(sf_snippet_json, json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2))
        return [sf_md, sf_tex, sf_snippet_json]

    candidate = _pick_sf_candidate_record(all_records=all_records, best_candidates_json=best_json)
    if candidate is None:
        tex_text, md_text, payload = _render_sf_unavailable_snippets(reason="no_ok_candidate_with_chi2_total")
        _write_text(sf_tex, tex_text)
        _write_text(sf_md, md_text)
        _write_text(sf_snippet_json, json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2))
        return [sf_md, sf_tex, sf_snippet_json]

    model = str(candidate.model or "lcdm").strip().lower()
    if model not in {"lcdm", "gsc_transition"}:
        model = "lcdm"

    h0 = _lookup_param(candidate, ["H0", "h0", "h0_km_s_mpc"])
    little_h = _lookup_param(candidate, ["h"])
    if h0 is None and little_h is not None:
        h0 = float(100.0 * little_h)
    omega_m = _lookup_param(candidate, ["Omega_m", "omega_m", "omega_m0", "omegam", "om0"])
    omega_lambda = _lookup_param(candidate, ["Omega_Lambda", "omega_lambda", "omega_l", "omega_de", "omega_l0"])
    omega_b0 = _lookup_param(candidate, ["Omega_b0", "omega_b", "omega_b0", "Omega_b"])
    ns = _lookup_param(candidate, ["n_s", "ns", "rsd_primordial_ns"])
    k_pivot = _lookup_param(candidate, ["k_pivot_mpc", "k0_mpc", "rsd_primordial_k_pivot_mpc"])

    if h0 is None or omega_m is None:
        tex_text, md_text, payload = _render_sf_unavailable_snippets(reason="missing_background_parameters_for_sf_snippet")
        _write_text(sf_tex, tex_text)
        _write_text(sf_md, md_text)
        _write_text(sf_snippet_json, json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2))
        return [sf_md, sf_tex, sf_snippet_json]

    cmd: List[str] = [
        str(sys.executable),
        str(script),
        "--history",
        str(model),
        "--H0",
        f"{float(h0):.12g}",
        "--Omega-m",
        f"{float(omega_m):.12g}",
        "--sigma8-mode",
        "nuisance",
        "--transfer-model",
        "bbks",
        "--ns",
        f"{float(ns if ns is not None else 1.0):.12g}",
        "--k-pivot",
        f"{float(k_pivot if k_pivot is not None else 0.05):.12g}",
        "--rsd",
        "--format",
        "json",
        "--json-out",
        str(sf_json),
        "--emit-snippets",
        str(outdir),
    ]
    if omega_lambda is not None:
        cmd.extend(["--Omega-lambda", f"{float(omega_lambda):.12g}"])
    if omega_b0 is not None:
        cmd.extend(["--Omega-b0", f"{float(omega_b0):.12g}"])
    if model == "gsc_transition":
        p_val = _lookup_param(candidate, ["p"])
        zt_val = _lookup_param(candidate, ["z_transition", "z_t", "zt"])
        if p_val is None or zt_val is None:
            tex_text, md_text, payload = _render_sf_unavailable_snippets(reason="missing_gsc_transition_parameters_for_sf_snippet")
            _write_text(sf_tex, tex_text)
            _write_text(sf_md, md_text)
            _write_text(sf_snippet_json, json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2))
            return [sf_md, sf_tex, sf_snippet_json]
        cmd.extend(["--p", f"{float(p_val):.12g}", "--z-transition", f"{float(zt_val):.12g}"])

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        reason = "sf_fsigma8_report_failed"
        output = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        if output:
            reason = f"{reason}:{output.splitlines()[-1][:120]}"
        tex_text, md_text, payload = _render_sf_unavailable_snippets(reason=reason)
        _write_text(sf_tex, tex_text)
        _write_text(sf_md, md_text)
        _write_text(sf_snippet_json, json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2))
        return [sf_md, sf_tex, sf_snippet_json]

    outputs: List[Path] = []
    for candidate_path in (sf_json, sf_md, sf_tex, sf_snippet_json):
        if candidate_path.is_file():
            outputs.append(candidate_path)

    if not sf_md.is_file() or not sf_tex.is_file():
        tex_text, md_text, payload = _render_sf_unavailable_snippets(reason="sf_snippet_files_missing_after_report_run")
        _write_text(sf_tex, tex_text)
        _write_text(sf_md, md_text)
        _write_text(sf_snippet_json, json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2))
        outputs = [sf_md, sf_tex, sf_snippet_json] + ([sf_json] if sf_json.is_file() else [])
    return outputs


def _emit_consistency_report_assets(
    *,
    outdir: Path,
    created_utc: str,
    repo_root: Path,
) -> List[Path]:
    script = (repo_root / "v11.0.0" / "scripts" / "phase2_consistency_check.py").resolve()
    if not script.is_file():
        raise SystemExit(f"Consistency check script not found: {script}")

    report_dir = outdir / "consistency"
    cmd: List[str] = [
        str(sys.executable),
        str(script),
        "--bundle-dir",
        str(outdir),
        "--outdir",
        str(report_dir),
        "--created-utc",
        str(created_utc),
        "--format",
        "json",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        output = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        raise SystemExit(f"Consistency report generation failed for {outdir}: {output}")

    outputs: List[Path] = []
    for name in ("CONSISTENCY_REPORT.json", "CONSISTENCY_REPORT.md"):
        candidate = report_dir / name
        if candidate.is_file():
            outputs.append(candidate)
    if len(outputs) < 2:
        raise SystemExit(f"Consistency report outputs missing in: {report_dir}")
    return outputs


def _emit_rs_zstar_reference_audit_assets(
    *,
    outdir: Path,
    repo_root: Path,
    created_utc: str,
    run_dir: Optional[Path],
    strict: bool,
) -> List[Path]:
    script = (repo_root / "v11.0.0" / "scripts" / "phase2_cmb_rs_zstar_reference_audit.py").resolve()
    if not script.is_file():
        raise SystemExit(f"RS/Z* reference audit script not found: {script}")
    report_json = outdir / "RS_ZSTAR_REFERENCE_AUDIT.json"
    report_txt = outdir / "RS_ZSTAR_REFERENCE_AUDIT.txt"
    cmd: List[str] = [
        str(sys.executable),
        str(script),
        "--bundle-dir",
        str(outdir),
        "--created-utc",
        str(created_utc),
        "--out",
        str(report_json),
        "--summary-out",
        str(report_txt),
        "--format",
        "json",
    ]
    if run_dir is not None:
        cmd.extend(["--run-dir", str(run_dir.expanduser().resolve())])
    if strict:
        cmd.append("--strict")

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        output = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        raise SystemExit(f"RS/Z* reference audit generation failed for {outdir}: {output}")

    outputs: List[Path] = []
    for path in (report_json, report_txt):
        if path.is_file():
            outputs.append(path)
    return outputs


def _emit_drift_table_report_assets(
    *,
    outdir: Path,
    jsonl_inputs: Sequence[Path],
    bundle_inputs: Sequence[Path],
    args: argparse.Namespace,
    repo_root: Path,
) -> List[Path]:
    script = (repo_root / "v11.0.0" / "scripts" / "phase2_e2_drift_table_report.py").resolve()
    if not script.is_file():
        raise SystemExit(f"Drift-table report script not found: {script}")

    json_out = outdir / "phase2_e2_drift_table_report.json"
    md_out = outdir / "phase2_e2_drift_table.md"
    tex_out = outdir / "phase2_e2_drift_table.tex"

    plausibility_mode = (
        "plausible_only"
        if str(args.plausibility) == "plausible_only"
        else "also_report_best_plausible"
    )

    cmd: List[str] = [
        str(sys.executable),
        str(script),
        "--format",
        "text",
        "--eligible-status",
        str(args.certificate_status_filter),
        "--plausibility-mode",
        str(plausibility_mode),
        "--years",
        "10.0",
        "--json-out",
        str(json_out),
        "--emit-md",
        str(md_out),
        "--emit-tex",
        str(tex_out),
    ]
    for z in ("2", "3", "4", "5"):
        cmd.extend(["--z", z])
    for path in sorted(jsonl_inputs, key=lambda p: str(p)):
        cmd.extend(["--input", str(Path(path).expanduser().resolve())])
    for path in sorted(bundle_inputs, key=lambda p: str(p)):
        cmd.extend(["--bundle", str(Path(path).expanduser().resolve())])

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        output = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        raise SystemExit(f"Drift-table report generation failed for {outdir}: {output}")

    outputs: List[Path] = []
    for path in (json_out, md_out, tex_out):
        if path.is_file():
            outputs.append(path)
    if len(outputs) < 3:
        raise SystemExit(f"Drift-table report outputs missing in: {outdir}")
    return outputs


def _emit_cmb_tension_report_assets(
    *,
    outdir: Path,
    jsonl_inputs: Sequence[Path],
    bundle_inputs: Sequence[Path],
    raw_records: Sequence[RawRecord],
    args: argparse.Namespace,
    created_utc: str,
    repo_root: Path,
) -> List[Path]:
    script = (repo_root / "v11.0.0" / "scripts" / "phase2_e2_cmb_tension_report.py").resolve()
    if not script.is_file():
        raise SystemExit(f"CMB tension report script not found: {script}")

    cmd: List[str] = [
        str(sys.executable),
        str(script),
        "--outdir",
        str(outdir),
        "--top-k",
        str(int(args.top_n)),
        "--sort-by",
        "chi2_total",
        "--emit-snippets",
        "--snippets-outdir",
        str(outdir),
        "--created-utc",
        str(created_utc),
    ]
    if str(args.drift_constraint) == "positive_only":
        cmd.extend(["--require-drift-sign", "positive"])
    else:
        cmd.extend(["--require-drift-sign", "any"])

    if str(args.certificate_status_filter) == "ok_only":
        cmd.append("--require-ok")
    else:
        cmd.append("--no-require-ok")

    temp_input: Optional[Path] = None
    for path in sorted(jsonl_inputs, key=lambda p: str(p)):
        cmd.extend(["--in-jsonl", str(Path(path).expanduser().resolve())])
    for path in sorted(bundle_inputs, key=lambda p: str(p)):
        candidate = Path(path).expanduser().resolve()
        if candidate.is_dir():
            cmd.extend(["--indir", str(candidate)])

    if not any(flag in cmd for flag in ("--in-jsonl", "--indir")):
        merged_lines = [
            json.dumps(rec.obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            for rec in sorted(raw_records, key=lambda r: (str(r.source), int(r.line)))
        ]
        digest = _sha256_bytes("\n".join(merged_lines).encode("utf-8"))
        temp_input = Path(tempfile.gettempdir()) / f"phase2_e2_cmb_tension_{digest}.jsonl"
        _write_text(temp_input, "\n".join(merged_lines))
        cmd.extend(["--in-jsonl", str(temp_input)])

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            output = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
            raise SystemExit(f"CMB tension report generation failed for {outdir}: {output}")
    finally:
        if temp_input is not None and temp_input.is_file():
            temp_input.unlink()

    outputs: List[Path] = []
    for path in (
        outdir / "cmb_tension_summary.json",
        outdir / "cmb_tension_summary.md",
        outdir / "cmb_tension_topk.csv",
        outdir / "phase2_e2_cmb_tension.md",
        outdir / "phase2_e2_cmb_tension.tex",
    ):
        if path.is_file():
            outputs.append(path)
    required = [outdir / "phase2_e2_cmb_tension.md", outdir / "phase2_e2_cmb_tension.tex"]
    if not all(path.is_file() for path in required):
        raise SystemExit(f"CMB tension snippet outputs missing in: {outdir}")
    return outputs


def _inputs_digest(entries: Sequence[InputEntry]) -> str:
    payload = [
        {
            "bytes": int(entry.bytes),
            "path": str(entry.path),
            "sha256": str(entry.sha256),
        }
        for entry in sorted(entries, key=lambda x: str(x.path))
    ]
    return _sha256_bytes(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8"))


def _paper_manifest_entries(paths: Sequence[Path], *, rel_base: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for path in sorted({p.resolve() for p in paths if p.is_file()}, key=lambda p: str(p)):
        rows.append(
            {
                "relpath": str(path.relative_to(rel_base.resolve())),
                "sha256": _sha256_file(path),
                "bytes": int(path.stat().st_size),
            }
        )
    return rows


def _write_paper_assets_manifest(
    *,
    manifest_path: Path,
    inputs: Sequence[InputEntry],
    output_files: Sequence[Path],
    snippet_files: Sequence[Path],
    repo_root: Path,
    created_utc: str,
    source_bundle_sha256: Optional[str],
    config: Mapping[str, Any],
) -> Path:
    manifest_dir = manifest_path.parent.resolve()
    files = _paper_manifest_entries(output_files, rel_base=manifest_dir)
    snippets = _paper_manifest_entries(snippet_files, rel_base=manifest_dir)

    payload: Dict[str, Any] = {
        "schema": PAPER_ASSETS_MANIFEST_SCHEMA_ID,
        "created_utc": str(created_utc),
        "gsc_git_sha": _git_sha(repo_root),
        "inputs": [
            {
                "path": str(entry.path),
                "sha256": str(entry.sha256),
                "bytes": int(entry.bytes),
            }
            for entry in sorted(inputs, key=lambda x: str(x.path))
        ],
        "source_inputs_sha256": _inputs_digest(inputs),
        "files": files,
        "snippets": snippets,
        "config": {str(k): config[k] for k in sorted(config.keys())},
    }
    if source_bundle_sha256:
        payload["source_bundle_sha256"] = str(source_bundle_sha256)
    _write_text(manifest_path, json.dumps(payload, indent=2, sort_keys=True))
    return manifest_path


def _prepare_outdir(path: Path, *, overwrite: bool) -> None:
    resolved = path.expanduser().resolve()
    if resolved.exists():
        existing = [p for p in resolved.iterdir()]
        if existing and not overwrite:
            raise SystemExit(f"Output directory exists and is not empty (use --overwrite): {resolved}")
        if existing and overwrite:
            shutil.rmtree(resolved)
    resolved.mkdir(parents=True, exist_ok=True)


def _lookup_param(rec: E2Record, keys: Sequence[str]) -> Optional[float]:
    for key in keys:
        if key in rec.params:
            return rec.params[key]
        if key in rec.cosmo_params:
            return rec.cosmo_params[key]
    return None


def _closure_to_knobs_columns(records: Sequence[E2Record]) -> List[str]:
    knob_keys: List[str] = []
    seen: set[str] = set()
    for rec in records:
        for key in sorted(rec.micro_knobs.keys()):
            col = f"knob_{key}"
            if col not in seen:
                seen.add(col)
                knob_keys.append(col)
    return sorted(knob_keys)


def _make_drift_assets(
    *,
    outdir: Path,
    raw_records: Sequence[RawRecord],
    records: Sequence[E2Record],
    all_records: Sequence[E2Record],
    parse_stats: Mapping[str, int],
    filter_counts: Mapping[str, int],
    filter_notes: Mapping[str, int],
    inputs: Sequence[InputEntry],
    jsonl_inputs: Sequence[Path],
    bundle_inputs: Sequence[Path],
    args: argparse.Namespace,
    created_utc: str,
    repo_root: Path,
) -> Dict[str, List[Path]]:
    deduped = _dedupe_records(records)

    pareto = _pareto_front(deduped)
    curve = _build_closure_bound_curve(deduped)

    table_rows: List[Dict[str, Any]] = []
    for rec in pareto:
        table_rows.append(
            {
                "params_hash": rec.params_hash,
                "chi2_cmb": rec.chi2_cmb,
                "chi2_total": rec.chi2_total,
                "drift_metric": rec.drift_metric,
                "drift_sign_ok": rec.drift_sign_ok,
                "microphysics_plausible_ok": rec.plausible_ok,
                "microphysics_penalty": rec.microphysics_penalty,
                "microphysics_max_rel_dev": rec.microphysics_max_rel_dev,
                "robustness_ok": rec.robustness_ok,
            }
        )

    best_overall = _pick_best(deduped, require_positive=False)
    best_positive = _pick_best(deduped, require_positive=True)
    best_positive_robust = _pick_best(deduped, require_positive=True, require_robust=True)

    summary_rows: List[Dict[str, Any]] = []
    for label, rec in [
        ("best_overall", best_overall),
        ("best_drift_positive", best_positive),
        ("best_drift_positive_robust", best_positive_robust),
    ]:
        if rec is None:
            continue
        summary_rows.append(
            {
                "label": label,
                "params_hash": rec.params_hash,
                "chi2_cmb": rec.chi2_cmb,
                "chi2_total": rec.chi2_total,
                "drift_metric": rec.drift_metric,
                "drift_sign_ok": rec.drift_sign_ok,
                "microphysics_max_rel_dev": rec.microphysics_max_rel_dev,
                "microphysics_penalty": rec.microphysics_penalty,
            }
        )

    tables_dir = outdir / "tables"
    _write_csv(
        tables_dir / "pareto_front.csv",
        fieldnames=[
            "params_hash",
            "chi2_cmb",
            "chi2_total",
            "drift_metric",
            "drift_sign_ok",
            "microphysics_plausible_ok",
            "microphysics_penalty",
            "microphysics_max_rel_dev",
            "robustness_ok",
        ],
        rows=table_rows,
    )
    _write_csv(
        tables_dir / "closure_bound_curve.csv",
        fieldnames=[
            "drift_threshold",
            "best_chi2_cmb",
            "best_params_hash",
            "best_drift_metric",
            "best_chi2_total",
        ],
        rows=curve,
    )
    _write_csv(
        tables_dir / "best_points_summary.csv",
        fieldnames=[
            "label",
            "params_hash",
            "chi2_cmb",
            "chi2_total",
            "drift_metric",
            "drift_sign_ok",
            "microphysics_max_rel_dev",
            "microphysics_penalty",
        ],
        rows=summary_rows,
    )

    figures: List[Path] = []
    if bool(args.emit_plots):
        try:
            import matplotlib.pyplot as plt  # type: ignore
        except Exception as exc:
            raise SystemExit(f"--emit-plots requested but matplotlib is unavailable: {exc}") from exc

        fig_dir = outdir / "figures"
        fig_dir.mkdir(parents=True, exist_ok=True)

        xs = [float(r.drift_metric) for r in deduped if r.drift_metric is not None and r.chi2_cmb is not None]
        ys = [float(r.chi2_cmb) for r in deduped if r.drift_metric is not None and r.chi2_cmb is not None]
        p_x = [float(r.drift_metric) for r in pareto if r.drift_metric is not None and r.chi2_cmb is not None]
        p_y = [float(r.chi2_cmb) for r in pareto if r.drift_metric is not None and r.chi2_cmb is not None]

        plt.figure(figsize=(6.0, 4.0), dpi=150)
        plt.scatter(xs, ys, s=14, alpha=0.6, label="filtered points")
        plt.scatter(p_x, p_y, s=26, alpha=0.9, label="pareto front")
        plt.xlabel("drift_metric")
        plt.ylabel("chi2_cmb")
        plt.legend(loc="best")
        plt.tight_layout()
        p1 = fig_dir / "chi2_cmb_vs_drift_metric.png"
        plt.savefig(p1)
        plt.close()
        figures.append(p1)

        plt.figure(figsize=(6.0, 4.0), dpi=150)
        cx = [float(r["drift_threshold"]) for r in curve]
        cy = [float(r["best_chi2_cmb"]) for r in curve]
        plt.step(cx, cy, where="post")
        plt.xlabel("drift_threshold")
        plt.ylabel("best chi2_cmb at/above threshold")
        plt.tight_layout()
        p2 = fig_dir / "closure_bound_curve.png"
        plt.savefig(p2)
        plt.close()
        figures.append(p2)

    all_aggregator_lines = ""
    if str(args.mode) == "all":
        all_aggregator_lines = "- `snippets/phase2_e2_all.tex`\n- `snippets/phase2_e2_all.md`\n"

    readme = f"""# E2 Drift-Constrained Closure Bound Assets

This directory is generated by `v11.0.0/scripts/phase2_e2_make_paper_assets.py`
in `drift_closure_bound` mode. It summarizes the empirical trade-off between
drift metric constraints and compressed-CMB closure (`chi2_cmb`) for filtered
E2 scan records.

## Filters

- plausibility: `{args.plausibility}`
- robustness: `{args.robustness}`
- drift_constraint: `{args.drift_constraint}`
- drift_threshold: `{args.drift_threshold}`

## Counts

- input records: {filter_counts.get('n_input', 0)}
- status-skipped: {filter_counts.get('n_status_skipped', 0)}
- missing chi2_cmb: {filter_counts.get('n_missing_chi2_cmb', 0)}
- missing drift_metric: {filter_counts.get('n_missing_drift_metric', 0)}
- plausibility filtered: {filter_counts.get('n_plausibility_filtered', 0)}
- robustness filtered: {filter_counts.get('n_robustness_filtered', 0)}
- drift filtered: {filter_counts.get('n_drift_filtered', 0)}
- records used (pre-dedupe): {filter_counts.get('n_output', 0)}
- records used (deduped): {len(deduped)}
- pareto points: {len(pareto)}

## Legacy defaults

- records without `microphysics_plausible_ok` treated as plausible: {filter_notes.get('n_legacy_plausible', 0)}
- records without robustness flags treated as robust: {filter_notes.get('n_legacy_robust', 0)}

## Tables

- `tables/pareto_front.csv`
- `tables/closure_bound_curve.csv`
- `tables/best_points_summary.csv`
- `phase2_e2_closure_bound_candidates.csv`

## Closure bound report

- `phase2_e2_closure_bound_report.json`
- `phase2_e2_closure_bound_report.md`
- `phase2_e2_closure_bound_report.tex`

## Drift comparison report (M68)

- `phase2_e2_drift_table_report.json`
- `phase2_e2_drift_table.md`
- `phase2_e2_drift_table.tex`

## CMB tension snippet report (M69)

- `cmb_tension_summary.json`
- `cmb_tension_summary.md`
- `cmb_tension_topk.csv`
- `phase2_e2_cmb_tension.md`
- `phase2_e2_cmb_tension.tex`

## Scan audit report (M67)

- `phase2_e2_scan_audit.json`
- `phase2_e2_scan_audit.md`
- `phase2_e2_scan_audit.tex`

## Certificate

- `e2_certificate.json`
- `e2_certificate.md`

## Canonical snippet includes

- `snippets/phase2_e2_appendix.tex`
- `snippets/phase2_e2_appendix.md`
- `snippets/phase2_e2_closure_bound.tex`
- `snippets/phase2_e2_closure_bound.md`
- `snippets/phase2_e2_summary.tex`
- `snippets/phase2_e2_summary.md`
- `snippets/phase2_e2_drift_table.tex`
- `snippets/phase2_e2_drift_table.md`
- `snippets/phase2_e2_cmb_tension.tex`
- `snippets/phase2_e2_cmb_tension.md`
- `snippets/phase2_e2_scan_audit.tex`
- `snippets/phase2_e2_scan_audit.md`
{all_aggregator_lines}

These assets are diagnostics of closure-vs-drift trade-offs under explicit
filters; they do not introduce new physical claims.
"""
    _write_text(outdir / "README.md", readme)

    outputs = [
        outdir / "README.md",
        tables_dir / "pareto_front.csv",
        tables_dir / "closure_bound_curve.csv",
        tables_dir / "best_points_summary.csv",
    ] + figures

    outputs.extend(
        _emit_closure_bound_report_assets(
            outdir=outdir,
            jsonl_inputs=jsonl_inputs,
            bundle_inputs=bundle_inputs,
            args=args,
            created_utc=created_utc,
            repo_root=repo_root,
        )
    )
    outputs.extend(
        _emit_drift_table_report_assets(
            outdir=outdir,
            jsonl_inputs=jsonl_inputs,
            bundle_inputs=bundle_inputs,
            args=args,
            repo_root=repo_root,
        )
    )
    outputs.extend(
        _emit_cmb_tension_report_assets(
            outdir=outdir,
            jsonl_inputs=jsonl_inputs,
            bundle_inputs=bundle_inputs,
            raw_records=raw_records,
            args=args,
            created_utc=created_utc,
            repo_root=repo_root,
        )
    )
    scan_audit_outputs, scan_audit_snippets = _emit_scan_audit_assets(
        outdir=outdir,
        raw_records=raw_records,
        parse_stats=parse_stats,
        inputs=inputs,
        args=args,
        bundle_inputs=bundle_inputs,
    )
    outputs.extend(scan_audit_outputs)

    snippet_rows = table_rows[: min(len(table_rows), 5)]
    snippets_dir = outdir / "snippets"
    snippets: List[Path] = []

    canonical_md_lines = [
        "# Phase-2 E2 Drift Appendix Snippet",
        "",
        "| params_hash | chi2_cmb | drift_metric |",
        "|---|---:|---:|",
    ]
    for row in snippet_rows:
        canonical_md_lines.append(
            "| "
            + str(row.get("params_hash", ""))
            + " | "
            + _csv_value(row.get("chi2_cmb"))
            + " | "
            + _csv_value(row.get("drift_metric"))
            + " |"
        )
    canonical_md_path = snippets_dir / "phase2_e2_appendix.md"
    _write_text(canonical_md_path, "\n".join(canonical_md_lines))
    snippets.append(canonical_md_path)

    canonical_tex_lines = [
        "% Auto-generated Phase-2 E2 drift appendix snippet",
        "\\begin{tabular}{lll}",
        "\\hline",
        "params\\_hash & chi2\\_cmb & drift\\_metric \\\\",
        "\\hline",
    ]
    for row in snippet_rows:
        canonical_tex_lines.append(
            str(row.get("params_hash", "")).replace("_", "\\_")
            + " & "
            + _csv_value(row.get("chi2_cmb"))
            + " & "
            + _csv_value(row.get("drift_metric"))
            + " \\\\"
        )
    canonical_tex_lines.extend(["\\hline", "\\end{tabular}"])
    canonical_tex_path = snippets_dir / "phase2_e2_appendix.tex"
    _write_text(canonical_tex_path, "\n".join(canonical_tex_lines))
    snippets.append(canonical_tex_path)

    closure_md_src = outdir / "phase2_e2_closure_bound_report.md"
    closure_tex_src = outdir / "phase2_e2_closure_bound_report.tex"
    closure_md_snippet = snippets_dir / "phase2_e2_closure_bound.md"
    closure_tex_snippet = snippets_dir / "phase2_e2_closure_bound.tex"
    if closure_md_src.is_file():
        _write_text(closure_md_snippet, closure_md_src.read_text(encoding="utf-8"))
        snippets.append(closure_md_snippet)
    if closure_tex_src.is_file():
        _write_text(closure_tex_snippet, closure_tex_src.read_text(encoding="utf-8"))
        snippets.append(closure_tex_snippet)

    certificate_outputs: List[Path] = []
    certificate_payload: Optional[Dict[str, Any]] = None
    if bool(args.emit_certificate):
        certificate_outputs = _emit_certificate_assets(
            outdir=outdir,
            jsonl_inputs=jsonl_inputs,
            bundle_inputs=bundle_inputs,
            args=args,
            created_utc=created_utc,
            repo_root=repo_root,
        )
        certificate_payload = _load_certificate_payload(outdir / "e2_certificate.json")

    summary_tex, summary_md = _render_e2_summary_snippets(
        all_records=all_records,
        certificate_payload=certificate_payload,
    )
    summary_tex_path = snippets_dir / "phase2_e2_summary.tex"
    summary_md_path = snippets_dir / "phase2_e2_summary.md"
    _write_text(summary_tex_path, summary_tex)
    _write_text(summary_md_path, summary_md)
    snippets.append(summary_tex_path)
    snippets.append(summary_md_path)

    drift_table_md_src = outdir / "phase2_e2_drift_table.md"
    drift_table_tex_src = outdir / "phase2_e2_drift_table.tex"
    drift_table_md_snippet = snippets_dir / "phase2_e2_drift_table.md"
    drift_table_tex_snippet = snippets_dir / "phase2_e2_drift_table.tex"
    if drift_table_md_src.is_file():
        _write_text(drift_table_md_snippet, drift_table_md_src.read_text(encoding="utf-8"))
        snippets.append(drift_table_md_snippet)
    if drift_table_tex_src.is_file():
        _write_text(drift_table_tex_snippet, drift_table_tex_src.read_text(encoding="utf-8"))
        snippets.append(drift_table_tex_snippet)

    cmb_tension_md_src = outdir / "phase2_e2_cmb_tension.md"
    cmb_tension_tex_src = outdir / "phase2_e2_cmb_tension.tex"
    cmb_tension_md_snippet = snippets_dir / "phase2_e2_cmb_tension.md"
    cmb_tension_tex_snippet = snippets_dir / "phase2_e2_cmb_tension.tex"
    if cmb_tension_md_src.is_file():
        _write_text(cmb_tension_md_snippet, cmb_tension_md_src.read_text(encoding="utf-8"))
        snippets.append(cmb_tension_md_snippet)
    if cmb_tension_tex_src.is_file():
        _write_text(cmb_tension_tex_snippet, cmb_tension_tex_src.read_text(encoding="utf-8"))
        snippets.append(cmb_tension_tex_snippet)

    snippets.extend(scan_audit_snippets)

    if bool(args.emit_snippets):
        if str(args.snippets_format) in {"md", "both"}:
            md_lines = [
                "# Drift Closure Snippet",
                "",
                "| params_hash | chi2_cmb | drift_metric |",
                "|---|---:|---:|",
            ]
            for row in snippet_rows:
                md_lines.append(
                    "| "
                    + str(row.get("params_hash", ""))
                    + " | "
                    + _csv_value(row.get("chi2_cmb"))
                    + " | "
                    + _csv_value(row.get("drift_metric"))
                    + " |"
                )
            md_path = snippets_dir / "drift_closure_bound.md"
            _write_text(md_path, "\n".join(md_lines))
            snippets.append(md_path)
        if str(args.snippets_format) in {"tex", "both"}:
            tex_lines = [
                "% Auto-generated drift closure snippet",
                "\\begin{tabular}{lll}",
                "\\hline",
                "params\\_hash & chi2\\_cmb & drift\\_metric \\\\",
                "\\hline",
            ]
            for row in snippet_rows:
                tex_lines.append(
                    str(row.get("params_hash", "")).replace("_", "\\_")
                    + " & "
                    + _csv_value(row.get("chi2_cmb"))
                    + " & "
                    + _csv_value(row.get("drift_metric"))
                    + " \\\\"
                )
            tex_lines.extend(["\\hline", "\\end{tabular}"])
            tex_path = snippets_dir / "drift_closure_bound.tex"
            _write_text(tex_path, "\n".join(tex_lines))
            snippets.append(tex_path)
    outputs.extend(snippets)
    outputs.extend(certificate_outputs)

    _write_manifest(
        outdir=outdir,
        inputs=inputs,
        outputs=outputs,
        config={
            "mode": "drift_closure_bound",
            "plausibility": args.plausibility,
            "robustness": args.robustness,
            "drift_constraint": args.drift_constraint,
            "drift_threshold": float(args.drift_threshold),
            "closure_cut": float(args.closure_cut),
            "top_n": int(args.top_n),
            "emit_plots": bool(args.emit_plots),
            "emit_snippets": bool(args.emit_snippets),
            "snippets_format": str(args.snippets_format),
            "emit_certificate": bool(args.emit_certificate),
            "certificate_status_filter": str(args.certificate_status_filter),
            "certificate_require_drift": _resolve_certificate_require_drift(args),
            "certificate_cmb_chi2_threshold": float(args.certificate_cmb_chi2_threshold),
            "certificate_late_chi2_threshold": float(args.certificate_late_chi2_threshold),
            "certificate_top_k": int(args.certificate_top_k),
            "certificate_require_plan_coverage": str(args.certificate_require_plan_coverage),
        },
        created_utc=created_utc,
        repo_root=repo_root,
    )
    return {"outputs": outputs, "snippets": snippets}


def _make_knobs_assets(
    *,
    outdir: Path,
    records: Sequence[E2Record],
    filter_counts: Mapping[str, int],
    filter_notes: Mapping[str, int],
    inputs: Sequence[InputEntry],
    jsonl_inputs: Sequence[Path],
    bundle_inputs: Sequence[Path],
    args: argparse.Namespace,
    created_utc: str,
    repo_root: Path,
) -> Dict[str, List[Path]]:
    deduped = _dedupe_records(records)

    sorted_by_chi2 = sorted(
        deduped,
        key=lambda r: (
            r.chi2_cmb if r.chi2_cmb is not None else float("inf"),
            r.chi2_total if r.chi2_total is not None else float("inf"),
            r.params_hash,
        ),
    )

    top_n = max(int(args.top_n), 1)
    top_models = sorted_by_chi2[:top_n]
    closure_region_raw = [r for r in sorted_by_chi2 if r.chi2_cmb is not None and float(r.chi2_cmb) <= float(args.closure_cut)]
    closure_region = closure_region_raw if closure_region_raw else list(top_models)

    knob_columns = _closure_to_knobs_columns(closure_region or top_models)

    def _knob_row(rec: E2Record, *, rank: Optional[int]) -> Dict[str, Any]:
        row: Dict[str, Any] = {
            "rank": rank,
            "params_hash": rec.params_hash,
            "chi2_cmb": rec.chi2_cmb,
            "chi2_total": rec.chi2_total,
            "drift_metric": rec.drift_metric,
            "drift_sign_ok": rec.drift_sign_ok,
            "omega_b_h2": _lookup_param(rec, ["omega_b_h2"]),
            "omega_c_h2": _lookup_param(rec, ["omega_c_h2"]),
            "N_eff": _lookup_param(rec, ["N_eff", "Neff"]),
            "Y_p": _lookup_param(rec, ["Y_p", "Yp"]),
            "h": _lookup_param(rec, ["h"]),
            "microphysics_penalty": rec.microphysics_penalty,
            "microphysics_max_rel_dev": rec.microphysics_max_rel_dev,
        }
        if row["h"] is None:
            h0 = _lookup_param(rec, ["H0"])
            if h0 is not None:
                row["h"] = float(h0) / 100.0
        for col in knob_columns:
            key = col[len("knob_") :]
            row[col] = rec.micro_knobs.get(key)
        return row

    top_rows = [_knob_row(rec, rank=idx) for idx, rec in enumerate(top_models, start=1)]
    stats_source_rows = [_knob_row(rec, rank=None) for rec in closure_region]

    stats_rows: List[Dict[str, Any]] = []
    numeric_keys: List[str] = ["omega_b_h2", "omega_c_h2", "N_eff", "Y_p", "h"] + knob_columns
    for key in numeric_keys:
        values = [float(v) for v in (_finite_float(row.get(key)) for row in stats_source_rows) if v is not None]
        if not values:
            continue
        stats_rows.append(
            {
                "name": key,
                "min": min(values),
                "max": max(values),
                "mean": statistics.fmean(values),
                "n": len(values),
            }
        )

    stats_rows = sorted(stats_rows, key=lambda r: str(r["name"]))

    tables_dir = outdir / "tables"
    top_fieldnames = [
        "rank",
        "params_hash",
        "chi2_cmb",
        "chi2_total",
        "drift_metric",
        "drift_sign_ok",
        "omega_b_h2",
        "omega_c_h2",
        "N_eff",
        "Y_p",
        "h",
        "microphysics_penalty",
        "microphysics_max_rel_dev",
    ] + knob_columns

    _write_csv(
        tables_dir / "top_models_knobs.csv",
        fieldnames=top_fieldnames,
        rows=top_rows,
    )
    _write_csv(
        tables_dir / "knobs_summary_stats.csv",
        fieldnames=["name", "min", "max", "mean", "n"],
        rows=stats_rows,
    )

    # Build concise TeX table with core + selected knobs.
    selected_knobs: List[str] = []
    if knob_columns:
        knob_scores: List[Tuple[float, str]] = []
        for col in knob_columns:
            vals = [_finite_float(row.get(col)) for row in top_rows]
            numeric = [float(v) for v in vals if v is not None]
            if not numeric:
                continue
            score = max(abs(v - 1.0) for v in numeric)
            knob_scores.append((float(score), col))
        knob_scores.sort(key=lambda kv: (-kv[0], kv[1]))
        selected_knobs = [col for _, col in knob_scores[:8]]

    tex_cols = ["rank", "params_hash", "chi2_cmb", "drift_metric", "omega_b_h2", "omega_c_h2", "N_eff", "Y_p", "h"] + selected_knobs

    def _tex_escape(text: str) -> str:
        return str(text).replace("_", "\\_")

    tex_lines = [
        "% Auto-generated by phase2_e2_make_paper_assets.py",
        "\\begin{tabular}{" + "l" * len(tex_cols) + "}",
        "\\hline",
        " & ".join(_tex_escape(col) for col in tex_cols) + " \\\\",
        "\\hline",
    ]
    for row in top_rows:
        tex_lines.append(
            " & ".join(_tex_escape(_csv_value(row.get(col))) for col in tex_cols) + " \\\\",
        )
    tex_lines.extend(["\\hline", "\\end{tabular}"])
    _write_text(tables_dir / "knobs_table.tex", "\n".join(tex_lines))

    figures: List[Path] = []
    if bool(args.emit_plots):
        try:
            import matplotlib.pyplot as plt  # type: ignore
        except Exception as exc:
            raise SystemExit(f"--emit-plots requested but matplotlib is unavailable: {exc}") from exc

        fig_dir = outdir / "figures"
        fig_dir.mkdir(parents=True, exist_ok=True)

        xs = [int(row["rank"]) for row in top_rows]
        ys = [float(row["chi2_cmb"]) for row in top_rows if row.get("chi2_cmb") is not None]
        plt.figure(figsize=(6.0, 4.0), dpi=150)
        plt.plot(xs[: len(ys)], ys, marker="o")
        plt.xlabel("rank")
        plt.ylabel("chi2_cmb")
        plt.tight_layout()
        p = fig_dir / "top_models_chi2_by_rank.png"
        plt.savefig(p)
        plt.close()
        figures.append(p)

    readme = f"""# E2 Closure-to-Physical-Knobs Assets

This directory is generated by `v11.0.0/scripts/phase2_e2_make_paper_assets.py`
in `closure_to_knobs` mode. It maps best closure candidates to inferred
parameter/knob values under explicit filters.

## Filters

- plausibility: `{args.plausibility}`
- robustness: `{args.robustness}`
- drift_constraint: `{args.drift_constraint}`
- drift_threshold: `{args.drift_threshold}`
- closure_cut: `{args.closure_cut}`
- top_n: `{args.top_n}`

## Counts

- input records: {filter_counts.get('n_input', 0)}
- status-skipped: {filter_counts.get('n_status_skipped', 0)}
- missing chi2_cmb: {filter_counts.get('n_missing_chi2_cmb', 0)}
- plausibility filtered: {filter_counts.get('n_plausibility_filtered', 0)}
- robustness filtered: {filter_counts.get('n_robustness_filtered', 0)}
- drift filtered: {filter_counts.get('n_drift_filtered', 0)}
- records used (pre-dedupe): {filter_counts.get('n_output', 0)}
- records used (deduped): {len(deduped)}
- closure region size (chi2_cmb <= cut): {len([r for r in deduped if r.chi2_cmb is not None and r.chi2_cmb <= float(args.closure_cut)])}

## Legacy defaults

- records without `microphysics_plausible_ok` treated as plausible: {filter_notes.get('n_legacy_plausible', 0)}
- records without robustness flags treated as robust: {filter_notes.get('n_legacy_robust', 0)}

## Tables

- `tables/top_models_knobs.csv`
- `tables/knobs_summary_stats.csv`
- `tables/knobs_table.tex`

## Physical knobs report (M53)

- `phase2_e2_physical_knobs_report.json`
- `phase2_e2_physical_knobs.md`
- `phase2_e2_physical_knobs.tex`

## Best candidates report (M65)

- `phase2_e2_best_candidates_report.json`
- `phase2_e2_best_candidates.md`
- `phase2_e2_best_candidates.tex`
- `phase2_sf_rsd_summary.md`
- `phase2_sf_rsd_summary.tex`
- `phase2_sf_fsigma8_report.json`
- `phase2_sf_fsigma8.md`
- `phase2_sf_fsigma8.tex`

## Sigma-origin RG diagnostics (M98)

- `phase2_rg_flow_table_report.json`
- `phase2_rg_flow_table.md`
- `phase2_rg_flow_table.tex`
- `phase2_rg_pade_fit_report.json`
- `phase2_rg_pade_fit.md`
- `phase2_rg_pade_fit.tex`

## Consistency checkpoint (M111)

- `consistency/CONSISTENCY_REPORT.json`
- `consistency/CONSISTENCY_REPORT.md`

## Optional rs/z* reference audit (M112)

Enabled with `--emit-rs-zstar-reference-audit`.

- `RS_ZSTAR_REFERENCE_AUDIT.json`
- `RS_ZSTAR_REFERENCE_AUDIT.txt`

## Certificate

- `e2_certificate.json`
- `e2_certificate.md`

## Canonical snippet includes

- `snippets/phase2_e2_appendix.tex`
- `snippets/phase2_e2_appendix.md`
- `snippets/phase2_e2_physical_knobs.tex`
- `snippets/phase2_e2_physical_knobs.md`
- `snippets/phase2_e2_best_candidates.tex`
- `snippets/phase2_e2_best_candidates.md`
- `snippets/phase2_sf_rsd_summary.tex`
- `snippets/phase2_sf_rsd_summary.md`
- `snippets/phase2_sf_fsigma8.tex`
- `snippets/phase2_sf_fsigma8.md`
- `snippets/phase2_rg_flow_table.tex`
- `snippets/phase2_rg_flow_table.md`
- `snippets/phase2_rg_pade_fit.tex`
- `snippets/phase2_rg_pade_fit.md`

When both modes are generated together (`--mode all`), these snippets are also
mirrored into `../paper_assets_cmb_e2_drift_constrained_closure_bound/snippets/`
for `phase2_e2_all.{{tex,md}}` single-file paper aggregation.

If closure region is empty under the current cut, summary stats fall back to top-N rows.
These assets are diagnostics and do not add new physical claims.
"""
    _write_text(outdir / "README.md", readme)

    outputs = [
        outdir / "README.md",
        tables_dir / "top_models_knobs.csv",
        tables_dir / "knobs_summary_stats.csv",
        tables_dir / "knobs_table.tex",
    ] + figures

    outputs.extend(
        _emit_physical_knobs_report_assets(
            outdir=outdir,
            jsonl_inputs=jsonl_inputs,
            bundle_inputs=bundle_inputs,
            args=args,
            created_utc=created_utc,
            repo_root=repo_root,
        )
    )
    outputs.extend(
        _emit_best_candidates_report_assets(
            outdir=outdir,
            jsonl_inputs=jsonl_inputs,
            bundle_inputs=bundle_inputs,
            args=args,
            repo_root=repo_root,
        )
    )
    outputs.extend(
        _emit_rg_sigma_origin_assets(
            outdir=outdir,
            repo_root=repo_root,
        )
    )
    outputs.extend(
        _emit_sf_fsigma8_assets(
            outdir=outdir,
            all_records=records,
            repo_root=repo_root,
        )
    )
    outputs.extend(
        _emit_consistency_report_assets(
            outdir=outdir,
            created_utc=created_utc,
            repo_root=repo_root,
        )
    )
    if bool(args.emit_rs_zstar_reference_audit):
        outputs.extend(
            _emit_rs_zstar_reference_audit_assets(
                outdir=outdir,
                repo_root=repo_root,
                created_utc=created_utc,
                run_dir=args.reference_audit_run_dir,
                strict=bool(args.reference_audit_strict),
            )
        )

    snippet_top = top_rows[: min(len(top_rows), 5)]
    snippets_dir = outdir / "snippets"
    snippets: List[Path] = []

    canonical_md_lines = [
        "# Phase-2 E2 Closure-to-Knobs Appendix Snippet",
        "",
        "| rank | params_hash | chi2_cmb | drift_metric |",
        "|---:|---|---:|---:|",
    ]
    for row in snippet_top:
        canonical_md_lines.append(
            "| "
            + _csv_value(row.get("rank"))
            + " | "
            + str(row.get("params_hash", ""))
            + " | "
            + _csv_value(row.get("chi2_cmb"))
            + " | "
            + _csv_value(row.get("drift_metric"))
            + " |"
        )
    canonical_md_path = snippets_dir / "phase2_e2_appendix.md"
    _write_text(canonical_md_path, "\n".join(canonical_md_lines))
    snippets.append(canonical_md_path)

    canonical_tex_lines = [
        "% Auto-generated Phase-2 E2 closure-to-knobs appendix snippet",
        "\\begin{tabular}{llll}",
        "\\hline",
        "rank & params\\_hash & chi2\\_cmb & drift\\_metric \\\\",
        "\\hline",
    ]
    for row in snippet_top:
        canonical_tex_lines.append(
            _csv_value(row.get("rank"))
            + " & "
            + str(row.get("params_hash", "")).replace("_", "\\_")
            + " & "
            + _csv_value(row.get("chi2_cmb"))
            + " & "
            + _csv_value(row.get("drift_metric"))
            + " \\\\"
        )
    canonical_tex_lines.extend(["\\hline", "\\end{tabular}"])
    canonical_tex_path = snippets_dir / "phase2_e2_appendix.tex"
    _write_text(canonical_tex_path, "\n".join(canonical_tex_lines))
    snippets.append(canonical_tex_path)

    physical_knobs_md_src = outdir / "phase2_e2_physical_knobs.md"
    physical_knobs_tex_src = outdir / "phase2_e2_physical_knobs.tex"
    physical_knobs_md_snippet = snippets_dir / "phase2_e2_physical_knobs.md"
    physical_knobs_tex_snippet = snippets_dir / "phase2_e2_physical_knobs.tex"
    if physical_knobs_md_src.is_file():
        _write_text(physical_knobs_md_snippet, physical_knobs_md_src.read_text(encoding="utf-8"))
        snippets.append(physical_knobs_md_snippet)
    if physical_knobs_tex_src.is_file():
        _write_text(physical_knobs_tex_snippet, physical_knobs_tex_src.read_text(encoding="utf-8"))
        snippets.append(physical_knobs_tex_snippet)

    best_candidates_md_src = outdir / "phase2_e2_best_candidates.md"
    best_candidates_tex_src = outdir / "phase2_e2_best_candidates.tex"
    best_candidates_md_snippet = snippets_dir / "phase2_e2_best_candidates.md"
    best_candidates_tex_snippet = snippets_dir / "phase2_e2_best_candidates.tex"
    if best_candidates_md_src.is_file():
        _write_text(best_candidates_md_snippet, best_candidates_md_src.read_text(encoding="utf-8"))
        snippets.append(best_candidates_md_snippet)
    if best_candidates_tex_src.is_file():
        _write_text(best_candidates_tex_snippet, best_candidates_tex_src.read_text(encoding="utf-8"))
        snippets.append(best_candidates_tex_snippet)

    sf_rsd_md_src = outdir / "phase2_sf_rsd_summary.md"
    sf_rsd_tex_src = outdir / "phase2_sf_rsd_summary.tex"
    sf_rsd_md_snippet = snippets_dir / "phase2_sf_rsd_summary.md"
    sf_rsd_tex_snippet = snippets_dir / "phase2_sf_rsd_summary.tex"
    if sf_rsd_md_src.is_file():
        _write_text(sf_rsd_md_snippet, sf_rsd_md_src.read_text(encoding="utf-8"))
        snippets.append(sf_rsd_md_snippet)
    if sf_rsd_tex_src.is_file():
        _write_text(sf_rsd_tex_snippet, sf_rsd_tex_src.read_text(encoding="utf-8"))
        snippets.append(sf_rsd_tex_snippet)

    sf_fsigma8_md_src = outdir / "phase2_sf_fsigma8.md"
    sf_fsigma8_tex_src = outdir / "phase2_sf_fsigma8.tex"
    sf_fsigma8_md_snippet = snippets_dir / "phase2_sf_fsigma8.md"
    sf_fsigma8_tex_snippet = snippets_dir / "phase2_sf_fsigma8.tex"
    if sf_fsigma8_md_src.is_file():
        _write_text(sf_fsigma8_md_snippet, sf_fsigma8_md_src.read_text(encoding="utf-8"))
        snippets.append(sf_fsigma8_md_snippet)
    if sf_fsigma8_tex_src.is_file():
        _write_text(sf_fsigma8_tex_snippet, sf_fsigma8_tex_src.read_text(encoding="utf-8"))
        snippets.append(sf_fsigma8_tex_snippet)

    rg_flow_md_src = outdir / "phase2_rg_flow_table.md"
    rg_flow_tex_src = outdir / "phase2_rg_flow_table.tex"
    rg_flow_md_snippet = snippets_dir / "phase2_rg_flow_table.md"
    rg_flow_tex_snippet = snippets_dir / "phase2_rg_flow_table.tex"
    if rg_flow_md_src.is_file():
        _write_text(rg_flow_md_snippet, rg_flow_md_src.read_text(encoding="utf-8"))
        snippets.append(rg_flow_md_snippet)
    if rg_flow_tex_src.is_file():
        _write_text(rg_flow_tex_snippet, rg_flow_tex_src.read_text(encoding="utf-8"))
        snippets.append(rg_flow_tex_snippet)

    rg_pade_md_src = outdir / "phase2_rg_pade_fit.md"
    rg_pade_tex_src = outdir / "phase2_rg_pade_fit.tex"
    rg_pade_md_snippet = snippets_dir / "phase2_rg_pade_fit.md"
    rg_pade_tex_snippet = snippets_dir / "phase2_rg_pade_fit.tex"
    if rg_pade_md_src.is_file():
        _write_text(rg_pade_md_snippet, rg_pade_md_src.read_text(encoding="utf-8"))
        snippets.append(rg_pade_md_snippet)
    if rg_pade_tex_src.is_file():
        _write_text(rg_pade_tex_snippet, rg_pade_tex_src.read_text(encoding="utf-8"))
        snippets.append(rg_pade_tex_snippet)

    if bool(args.emit_snippets):
        if str(args.snippets_format) in {"md", "both"}:
            md_lines = [
                "# Closure-to-Knobs Snippet",
                "",
                "| rank | params_hash | chi2_cmb | drift_metric |",
                "|---:|---|---:|---:|",
            ]
            for row in snippet_top:
                md_lines.append(
                    "| "
                    + _csv_value(row.get("rank"))
                    + " | "
                    + str(row.get("params_hash", ""))
                    + " | "
                    + _csv_value(row.get("chi2_cmb"))
                    + " | "
                    + _csv_value(row.get("drift_metric"))
                    + " |"
                )
            md_path = snippets_dir / "closure_to_knobs.md"
            _write_text(md_path, "\n".join(md_lines))
            snippets.append(md_path)
        if str(args.snippets_format) in {"tex", "both"}:
            tex_lines = [
                "% Auto-generated closure-to-knobs snippet",
                "\\begin{tabular}{llll}",
                "\\hline",
                "rank & params\\_hash & chi2\\_cmb & drift\\_metric \\\\",
                "\\hline",
            ]
            for row in snippet_top:
                tex_lines.append(
                    _csv_value(row.get("rank"))
                    + " & "
                    + str(row.get("params_hash", "")).replace("_", "\\_")
                    + " & "
                    + _csv_value(row.get("chi2_cmb"))
                    + " & "
                    + _csv_value(row.get("drift_metric"))
                    + " \\\\"
                )
            tex_lines.extend(["\\hline", "\\end{tabular}"])
            tex_path = snippets_dir / "closure_to_knobs.tex"
            _write_text(tex_path, "\n".join(tex_lines))
            snippets.append(tex_path)
    outputs.extend(snippets)

    if bool(args.emit_certificate):
        outputs.extend(
            _emit_certificate_assets(
                outdir=outdir,
                jsonl_inputs=jsonl_inputs,
                bundle_inputs=bundle_inputs,
                args=args,
                created_utc=created_utc,
                repo_root=repo_root,
            )
        )

    _write_manifest(
        outdir=outdir,
        inputs=inputs,
        outputs=outputs,
        config={
            "mode": "closure_to_knobs",
            "plausibility": args.plausibility,
            "robustness": args.robustness,
            "drift_constraint": args.drift_constraint,
            "drift_threshold": float(args.drift_threshold),
            "closure_cut": float(args.closure_cut),
            "top_n": int(args.top_n),
            "emit_plots": bool(args.emit_plots),
            "emit_snippets": bool(args.emit_snippets),
            "snippets_format": str(args.snippets_format),
            "emit_certificate": bool(args.emit_certificate),
            "certificate_status_filter": str(args.certificate_status_filter),
            "certificate_require_drift": _resolve_certificate_require_drift(args),
            "certificate_cmb_chi2_threshold": float(args.certificate_cmb_chi2_threshold),
            "certificate_late_chi2_threshold": float(args.certificate_late_chi2_threshold),
            "certificate_top_k": int(args.certificate_top_k),
            "certificate_require_plan_coverage": str(args.certificate_require_plan_coverage),
        },
        created_utc=created_utc,
        repo_root=repo_root,
    )
    return {"outputs": outputs, "snippets": snippets}


def _collect_outputs_under(path: Path) -> List[Path]:
    out: List[Path] = []
    for candidate in sorted(path.rglob("*")):
        if candidate.is_file() and candidate.name != "manifest.json":
            out.append(candidate)
    return out


def _emit_phase2_all_aggregator(*, common_root: Path) -> Tuple[List[Path], List[Path]]:
    root = common_root.expanduser().resolve()
    snippets_dir = (root / DRIFT_DIR_NAME / "snippets").resolve()
    snippets_dir.mkdir(parents=True, exist_ok=True)

    materialized: List[Path] = []
    for stem in canonical_snippet_stems():
        for ext in ("tex", "md"):
            source_rel = canonical_snippet_source_relpath(stem, ext)
            source_path = (root / source_rel).resolve()
            if not source_path.is_file():
                raise SystemExit(
                    "Missing required Phase-2 snippet for phase2_e2_all aggregation: "
                    + source_rel
                )
            target_path = (snippets_dir / f"{stem}.{ext}").resolve()
            _write_text(target_path, source_path.read_text(encoding="utf-8"))
            materialized.append(target_path)

    tex_filenames = list(iter_canonical_tex_filenames())
    md_filenames = list(iter_canonical_md_filenames())

    all_tex_path = (snippets_dir / f"{PHASE2_E2_ALL_STEM}.tex").resolve()
    all_tex_lines = [f"% {PHASE2_E2_ALL_MARKER}", "% included_snippets:"]
    all_tex_lines.extend(f"% - {name}" for name in tex_filenames)
    all_tex_lines.append("")
    all_tex_lines.extend(f"\\input{{{name}}}" for name in tex_filenames)
    _write_text(all_tex_path, "\n".join(all_tex_lines))

    all_md_path = (snippets_dir / f"{PHASE2_E2_ALL_STEM}.md").resolve()
    md_chunks: List[str] = [f"<!-- {PHASE2_E2_ALL_MARKER} -->\n"]
    for name in md_filenames:
        md_chunks.append(f"<!-- include: {name} -->\n")
    md_chunks.append("\n")
    for index, name in enumerate(md_filenames):
        src = (snippets_dir / name).resolve()
        if not src.is_file():
            raise SystemExit(f"Missing required markdown snippet for phase2_e2_all: {src}")
        md_chunks.append(f"<!-- BEGIN {name} -->\n")
        body = src.read_text(encoding="utf-8")
        md_chunks.append(body.rstrip("\n"))
        md_chunks.append("\n")
        md_chunks.append(f"<!-- END {name} -->\n")
        if index != len(md_filenames) - 1:
            md_chunks.append("\n---\n\n")
    _write_text(all_md_path, "".join(md_chunks))

    snippet_paths = sorted({*materialized, all_tex_path, all_md_path}, key=lambda p: str(p))
    return snippet_paths, snippet_paths


def _resolve_output_dirs(*, repo_root: Path, mode: str, outdir: Optional[Path]) -> Dict[str, Path]:
    defaults = {
        "drift_closure_bound": (repo_root / "v11.0.0" / DRIFT_DIR_NAME).resolve(),
        "closure_to_knobs": (repo_root / "v11.0.0" / KNOBS_DIR_NAME).resolve(),
    }
    if mode == "all":
        if outdir is None:
            return defaults
        base = outdir.expanduser().resolve()
        return {
            "drift_closure_bound": (base / DRIFT_DIR_NAME).resolve(),
            "closure_to_knobs": (base / KNOBS_DIR_NAME).resolve(),
        }

    assert mode in {"drift_closure_bound", "closure_to_knobs"}
    if outdir is None:
        return {mode: defaults[mode]}
    return {mode: outdir.expanduser().resolve()}


def _load_inputs(
    jsonl_paths: Sequence[Path],
    bundle_paths: Sequence[Path],
) -> Tuple[List[RawRecord], List[E2Record], List[InputEntry], Dict[str, int]]:
    raw_records: List[RawRecord] = []
    inputs: List[InputEntry] = []
    stats = {
        "n_lines": 0,
        "n_blank": 0,
        "n_invalid_json": 0,
        "n_non_object": 0,
    }

    for jsonl_path in sorted(jsonl_paths, key=lambda p: str(p)):
        recs, entry, local = _load_jsonl_path(jsonl_path)
        raw_records.extend(recs)
        inputs.append(entry)
        for key in stats.keys():
            stats[key] += int(local.get(key, 0))

    for bundle_path in sorted(bundle_paths, key=lambda p: str(p)):
        recs, entries, local = _load_bundle(bundle_path)
        raw_records.extend(recs)
        inputs.extend(entries)
        for key in stats.keys():
            stats[key] += int(local.get(key, 0))

    records = [_normalize_record(rec, drift_threshold=0.0) for rec in raw_records]
    return raw_records, records, sorted(inputs, key=lambda x: str(x.path)), stats


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="phase2_e2_make_paper_assets",
        description="Generate deterministic E2 paper-asset tables from scan JSONL or bundles (stdlib-only).",
    )
    ap.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root (or v11.0.0 directory).",
    )
    ap.add_argument("--jsonl", action="append", type=Path, default=[], help="Input JSONL path (repeatable).")
    ap.add_argument("--bundle", action="append", type=Path, default=[], help="Input bundle path (dir/zip/tar/tgz; repeatable).")
    ap.add_argument("--outdir", type=Path, default=None, help="Output directory. In --mode all this acts as parent root.")
    ap.add_argument("--mode", choices=["drift_closure_bound", "closure_to_knobs", "all"], default="all")
    ap.add_argument("--plausibility", choices=["any", "plausible_only"], default="plausible_only")
    ap.add_argument("--robustness", choices=["any", "robust_only"], default="any")
    ap.add_argument("--drift-constraint", choices=["any", "positive_only"], default="positive_only")
    ap.add_argument("--drift-threshold", type=float, default=0.0)
    ap.add_argument("--closure-cut", type=float, default=3.0)
    ap.add_argument("--top-n", type=int, default=10)
    ap.add_argument("--emit-plots", action="store_true")
    ap.add_argument("--emit-snippets", action="store_true")
    ap.add_argument("--snippets-format", choices=["tex", "md", "both"], default="both")
    ap.add_argument(
        "--emit-rs-zstar-reference-audit",
        action="store_true",
        help="Emit optional rs/z* reference audit artifact (diagnostic only).",
    )
    ap.add_argument(
        "--reference-audit-run-dir",
        type=Path,
        default=None,
        help="Optional external CLASS/CAMB run directory used by rs/z* reference audit.",
    )
    ap.add_argument(
        "--reference-audit-strict",
        action="store_true",
        help="Fail rs/z* reference audit when reference values are unavailable.",
    )
    ap.add_argument("--emit-certificate", dest="emit_certificate", action="store_true", default=True)
    ap.add_argument("--no-emit-certificate", dest="emit_certificate", action="store_false")
    ap.add_argument("--certificate-plan", type=Path, default=None, help="Optional refine plan for certificate coverage.")
    ap.add_argument("--certificate-status-filter", choices=["ok_only", "any_eligible"], default="ok_only")
    ap.add_argument("--certificate-require-drift", choices=["auto", "off", "positive"], default="auto")
    ap.add_argument("--certificate-cmb-chi2-threshold", type=float, default=4.0)
    ap.add_argument("--certificate-late-chi2-threshold", type=float, default=10.0)
    ap.add_argument("--certificate-top-k", type=int, default=10)
    ap.add_argument("--certificate-require-plan-coverage", choices=["off", "complete"], default="off")
    ap.add_argument(
        "--created-utc",
        type=str,
        default=DEFAULT_CREATED_UTC,
        help="Deterministic timestamp value embedded in paper_assets_manifest.json (default fixed).",
    )
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args(argv)

    if not args.jsonl and not args.bundle:
        raise SystemExit("Provide at least one input via --jsonl and/or --bundle")

    if int(args.top_n) <= 0:
        raise SystemExit("--top-n must be > 0")
    if int(args.certificate_top_k) <= 0:
        raise SystemExit("--certificate-top-k must be > 0")
    if not math.isfinite(float(args.drift_threshold)):
        raise SystemExit("--drift-threshold must be finite")
    if not math.isfinite(float(args.closure_cut)):
        raise SystemExit("--closure-cut must be finite")
    if not math.isfinite(float(args.certificate_cmb_chi2_threshold)):
        raise SystemExit("--certificate-cmb-chi2-threshold must be finite")
    if not math.isfinite(float(args.certificate_late_chi2_threshold)):
        raise SystemExit("--certificate-late-chi2-threshold must be finite")
    created_utc = _normalize_created_utc(args.created_utc)

    repo_root, _ = _normalize_repo_root(Path(args.repo_root))

    raw_records, records, inputs, parse_stats = _load_inputs(list(args.jsonl), list(args.bundle))

    for rec in records:
        # Recompute drift-sign fallback with the actual threshold.
        if rec.drift_sign_ok is None and rec.drift_metric is not None:
            pass

    # Re-normalize drift sign fallback with threshold (without mutating dataclass).
    adjusted: List[E2Record] = []
    for rec in records:
        drift_sign_ok = rec.drift_sign_ok
        if drift_sign_ok is None and rec.drift_metric is not None:
            drift_sign_ok = bool(float(rec.drift_metric) >= float(args.drift_threshold))
        adjusted.append(
            E2Record(
                source=rec.source,
                line=rec.line,
                params_hash=rec.params_hash,
                status=rec.status,
                status_ok=rec.status_ok,
                error_present=rec.error_present,
                model=rec.model,
                chi2_cmb=rec.chi2_cmb,
                chi2_total=rec.chi2_total,
                drift_metric=rec.drift_metric,
                drift_sign_ok=drift_sign_ok,
                drift_sign_z3=rec.drift_sign_z3,
                plausible_ok=rec.plausible_ok,
                plausible_present=rec.plausible_present,
                robustness_ok=rec.robustness_ok,
                robustness_present=rec.robustness_present,
                microphysics_penalty=rec.microphysics_penalty,
                microphysics_max_rel_dev=rec.microphysics_max_rel_dev,
                params=rec.params,
                cosmo_params=rec.cosmo_params,
                micro_knobs=rec.micro_knobs,
            )
        )

    outdirs = _resolve_output_dirs(repo_root=repo_root, mode=args.mode, outdir=args.outdir)
    for key in sorted(outdirs.keys()):
        _prepare_outdir(outdirs[key], overwrite=bool(args.overwrite))

    # Common filtered views per mode.
    built_outputs: Dict[str, List[Path]] = {}
    built_snippets: Dict[str, List[Path]] = {}

    if "drift_closure_bound" in outdirs:
        drift_filtered, drift_counts, drift_notes = _filter_records(
            adjusted,
            require_drift_metric=True,
            plausibility=args.plausibility,
            robustness=args.robustness,
            drift_constraint=args.drift_constraint,
        )
        drift_result = _make_drift_assets(
            outdir=outdirs["drift_closure_bound"],
            raw_records=raw_records,
            records=drift_filtered,
            all_records=adjusted,
            parse_stats=parse_stats,
            filter_counts=drift_counts,
            filter_notes=drift_notes,
            inputs=inputs,
            jsonl_inputs=list(args.jsonl),
            bundle_inputs=list(args.bundle),
            args=args,
            created_utc=created_utc,
            repo_root=repo_root,
        )
        built_outputs["drift_closure_bound"] = list(drift_result.get("outputs", []))
        built_snippets["drift_closure_bound"] = list(drift_result.get("snippets", []))

    if "closure_to_knobs" in outdirs:
        knobs_filtered, knobs_counts, knobs_notes = _filter_records(
            adjusted,
            require_drift_metric=False,
            plausibility=args.plausibility,
            robustness=args.robustness,
            drift_constraint=args.drift_constraint,
        )
        knobs_result = _make_knobs_assets(
            outdir=outdirs["closure_to_knobs"],
            records=knobs_filtered,
            filter_counts=knobs_counts,
            filter_notes=knobs_notes,
            inputs=inputs,
            jsonl_inputs=list(args.jsonl),
            bundle_inputs=list(args.bundle),
            args=args,
            created_utc=created_utc,
            repo_root=repo_root,
        )
        built_outputs["closure_to_knobs"] = list(knobs_result.get("outputs", []))
        built_snippets["closure_to_knobs"] = list(knobs_result.get("snippets", []))

    if str(args.mode) == "all":
        if args.outdir is None:
            common_root = (repo_root / "v11.0.0").resolve()
        else:
            common_root = Path(args.outdir).expanduser().resolve()
        agg_outputs, agg_snippets = _emit_phase2_all_aggregator(common_root=common_root)
        built_outputs.setdefault("drift_closure_bound", []).extend(agg_outputs)
        built_snippets.setdefault("drift_closure_bound", []).extend(agg_snippets)

    source_bundle_sha256: Optional[str] = None
    bundle_paths = [Path(p).expanduser().resolve() for p in list(args.bundle)]
    if len(bundle_paths) == 1 and bundle_paths[0].is_file():
        source_bundle_sha256 = _sha256_file(bundle_paths[0])

    # Emit top-level paper-assets manifest. Keep default outputs under ignored paper-assets dirs.
    if args.outdir is not None:
        common_root = Path(args.outdir).expanduser().resolve()
        all_outputs: List[Path] = []
        all_snippets: List[Path] = []
        for mode_key in sorted(outdirs.keys()):
            all_outputs.extend(built_outputs.get(mode_key, []))
            all_snippets.extend(built_snippets.get(mode_key, []))
        manifest_path = common_root / "paper_assets_manifest.json"
        _write_paper_assets_manifest(
            manifest_path=manifest_path,
            inputs=inputs,
            output_files=all_outputs,
            snippet_files=all_snippets,
            repo_root=repo_root,
            created_utc=created_utc,
            source_bundle_sha256=source_bundle_sha256,
            config={
                "mode": str(args.mode),
                "plausibility": str(args.plausibility),
                "robustness": str(args.robustness),
                "drift_constraint": str(args.drift_constraint),
                "drift_threshold": float(args.drift_threshold),
                "closure_cut": float(args.closure_cut),
                "top_n": int(args.top_n),
                "emit_plots": bool(args.emit_plots),
                "emit_snippets": bool(args.emit_snippets),
                "snippets_format": str(args.snippets_format),
                "emit_certificate": bool(args.emit_certificate),
                "certificate_status_filter": str(args.certificate_status_filter),
                "certificate_require_drift": _resolve_certificate_require_drift(args),
                "certificate_cmb_chi2_threshold": float(args.certificate_cmb_chi2_threshold),
                "certificate_late_chi2_threshold": float(args.certificate_late_chi2_threshold),
                "certificate_top_k": int(args.certificate_top_k),
                "certificate_require_plan_coverage": str(args.certificate_require_plan_coverage),
            },
        )
    else:
        for mode_key in sorted(outdirs.keys()):
            mode_root = outdirs[mode_key]
            manifest_path = mode_root / "paper_assets_manifest.json"
            _write_paper_assets_manifest(
                manifest_path=manifest_path,
                inputs=inputs,
                output_files=built_outputs.get(mode_key, []),
                snippet_files=built_snippets.get(mode_key, []),
                repo_root=repo_root,
                created_utc=created_utc,
                source_bundle_sha256=source_bundle_sha256,
                config={
                    "mode": str(mode_key),
                    "plausibility": str(args.plausibility),
                    "robustness": str(args.robustness),
                    "drift_constraint": str(args.drift_constraint),
                    "drift_threshold": float(args.drift_threshold),
                    "closure_cut": float(args.closure_cut),
                    "top_n": int(args.top_n),
                    "emit_plots": bool(args.emit_plots),
                    "emit_snippets": bool(args.emit_snippets),
                    "snippets_format": str(args.snippets_format),
                    "emit_certificate": bool(args.emit_certificate),
                    "certificate_status_filter": str(args.certificate_status_filter),
                    "certificate_require_drift": _resolve_certificate_require_drift(args),
                    "certificate_cmb_chi2_threshold": float(args.certificate_cmb_chi2_threshold),
                    "certificate_late_chi2_threshold": float(args.certificate_late_chi2_threshold),
                    "certificate_top_k": int(args.certificate_top_k),
                    "certificate_require_plan_coverage": str(args.certificate_require_plan_coverage),
                },
            )

    summary = {
        "schema": SCHEMA_ID,
        "mode": args.mode,
        "parse_stats": {str(k): int(parse_stats[k]) for k in sorted(parse_stats.keys())},
        "outdirs": {str(k): str(v) for k, v in sorted(outdirs.items())},
        "inputs": len(inputs),
        "emit_snippets": bool(args.emit_snippets),
        "emit_certificate": bool(args.emit_certificate),
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

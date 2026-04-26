#!/usr/bin/env python3
"""Offline integrity verifier for Phase-2 E2 bundles (stdlib-only).

Supports:
- unpacked bundle directories
- .zip archives
- .tar / .tar.gz / .tgz archives

Verification is based on manifest file hashes (SHA256) with deterministic output.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import shutil
import stat
import sys
import tarfile
import tempfile
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
import zipfile

from phase2_e2_plan_coverage import analyze_plan_coverage, load_jsonl_records
from phase2_e2_snippets_catalog import (
    PHASE2_E2_ALL_MARKER,
    canonical_all_md_begin_markers,
    canonical_all_tex_inputs,
    canonical_required_snippet_relpaths,
)


DEFAULT_MANIFEST_CANDIDATES: Tuple[str, ...] = (
    "manifest.json",
    "phase2_e2_manifest.json",
    "phase2_e2_manifest_v1.json",
)
LINEAGE_FILE_NAME = "LINEAGE.json"
PAPER_ASSETS_MANIFEST_NAME = "paper_assets_manifest.json"
PAPER_ASSETS_SCHEMA_ID = "phase2_e2_paper_assets_manifest_v1"
REQUIRED_PAPER_SNIPPETS: Tuple[str, ...] = canonical_required_snippet_relpaths(include_aggregator=True)
BEST_CANDIDATES_SNIPPET_MARKER = "phase2_e2_best_candidates_snippet_v2"
SF_RSD_SNIPPET_MARKER = "phase2_sf_rsd_summary_snippet_v1"
SF_FSIGMA8_SNIPPET_MARKER = "phase2_sf_fsigma8_snippet_v1"
RG_FLOW_SNIPPET_MARKER = "phase2_rg_flow_table_snippet_v1"
RG_PADE_SNIPPET_MARKER = "phase2_rg_pade_fit_snippet_v1"
CONSISTENCY_REPORT_JSON = "CONSISTENCY_REPORT.json"
CONSISTENCY_REPORT_MD = "CONSISTENCY_REPORT.md"
SCHEMA_VALIDATE_FAILED_MARKER = "SCHEMA_VALIDATION_FAILED"
PORTABLE_CONTENT_LINT_FAILED_MARKER = "PORTABLE_CONTENT_LINT_FAILED"
DEFAULT_EXTRACT_PREFIXES: Tuple[str, ...] = (
    "v11.0.0/paper_assets_cmb_e2_closure_to_physical_knobs/",
    "v11.0.0/paper_assets_cmb_e2_drift_constrained_closure_bound/",
)
MAX_PRINT_ERRORS = 20
MAX_JSON_ERRORS = 50


class VerificationFailure(Exception):
    """Bundle verification failure (exit code 2)."""

    def __init__(self, message: str, *, errors: Optional[List[Dict[str, str]]] = None) -> None:
        super().__init__(str(message))
        self.errors: List[Dict[str, str]] = list(errors or [])


def _scripts_dir() -> Path:
    return Path(__file__).resolve().parent


def _schema_dir() -> Path:
    return _scripts_dir().parent / "schemas"


def _run_subprocess_json(cmd: Sequence[str], *, cwd: Path) -> Tuple[int, str, str, Optional[Dict[str, Any]]]:
    run = subprocess.run(
        [str(x) for x in cmd],
        cwd=str(cwd),
        text=True,
        capture_output=True,
    )
    stdout = str(run.stdout or "")
    stderr = str(run.stderr or "")
    payload: Optional[Dict[str, Any]] = None
    if stdout.strip():
        try:
            decoded = json.loads(stdout)
            if isinstance(decoded, Mapping):
                payload = {str(k): decoded[k] for k in decoded.keys()}
        except Exception:
            payload = None
    return int(run.returncode), stdout, stderr, payload


def _to_json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Mapping):
        return {str(k): _to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_json_safe(v) for v in value]
    return str(value)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_stream(stream: io.BufferedIOBase) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    digest = hashlib.sha256()
    digest.update(data)
    return digest.hexdigest()


def _normalize_relpath(text: str) -> str:
    raw = str(text or "").strip().replace("\\", "/")
    if not raw:
        raise VerificationFailure("empty manifest path entry")
    if raw.startswith("/"):
        raise VerificationFailure(f"absolute manifest path not allowed: {raw}")
    if len(raw) >= 2 and raw[1] == ":" and raw[0].isalpha():
        raise VerificationFailure(f"absolute drive path not allowed: {raw}")
    parts = PurePosixPath(raw).parts
    if any(part == ".." for part in parts):
        raise VerificationFailure(f"path traversal not allowed in manifest path: {raw}")
    norm = str(PurePosixPath(*parts))
    if norm in ("", "."):
        raise VerificationFailure(f"invalid manifest path entry: {raw}")
    return norm


def _is_hex_sha256(value: str) -> bool:
    text = str(value or "").strip().lower()
    if len(text) != 64:
        return False
    return all(ch in "0123456789abcdef" for ch in text)


def _adapter_entries(manifest: Mapping[str, Any]) -> List[Tuple[str, str]]:
    entries: List[Tuple[str, str]] = []

    artifacts = manifest.get("artifacts")
    if isinstance(artifacts, list):
        for item in artifacts:
            if not isinstance(item, Mapping):
                continue
            path = item.get("path")
            sha = item.get("sha256")
            if path is None or sha is None:
                continue
            relpath = _normalize_relpath(str(path))
            sha_text = str(sha).strip().lower()
            if not _is_hex_sha256(sha_text):
                raise VerificationFailure(f"invalid sha256 for {relpath}")
            entries.append((relpath, sha_text))
        if entries:
            return sorted(entries, key=lambda t: t[0])

    files = manifest.get("files")
    if isinstance(files, list):
        for item in files:
            if not isinstance(item, Mapping):
                continue
            path = item.get("path", item.get("relpath", item.get("file")))
            sha = item.get("sha256", item.get("sha", item.get("digest")))
            if path is None or sha is None:
                continue
            relpath = _normalize_relpath(str(path))
            sha_text = str(sha).strip().lower()
            if not _is_hex_sha256(sha_text):
                raise VerificationFailure(f"invalid sha256 for {relpath}")
            entries.append((relpath, sha_text))
        if entries:
            return sorted(entries, key=lambda t: t[0])

    for map_key in ("artifacts_sha256", "files_sha256"):
        mapping = manifest.get(map_key)
        if isinstance(mapping, Mapping):
            local: List[Tuple[str, str]] = []
            for key in sorted(str(k) for k in mapping.keys()):
                relpath = _normalize_relpath(key)
                sha_text = str(mapping[key]).strip().lower()
                if not _is_hex_sha256(sha_text):
                    raise VerificationFailure(f"invalid sha256 for {relpath}")
                local.append((relpath, sha_text))
            if local:
                return local

    raise VerificationFailure("manifest does not contain a supported file/hash list")


def _adapter_relpaths(manifest: Mapping[str, Any]) -> List[str]:
    return [rel for rel, _ in _adapter_entries(manifest)]


def _paper_assets_entries(manifest: Mapping[str, Any]) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
    schema = str(manifest.get("schema", "")).strip()
    if schema != PAPER_ASSETS_SCHEMA_ID:
        raise VerificationFailure(
            f"invalid paper assets manifest schema: expected {PAPER_ASSETS_SCHEMA_ID}, got {schema or 'UNKNOWN'}"
        )

    def _parse_entries(value: Any, *, field_name: str) -> List[Tuple[str, str]]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise VerificationFailure(f"paper assets manifest field '{field_name}' must be a list")
        rows: List[Tuple[str, str]] = []
        for item in value:
            if not isinstance(item, Mapping):
                continue
            rel = item.get("relpath", item.get("path"))
            sha = item.get("sha256")
            if rel is None or sha is None:
                continue
            relpath = _normalize_relpath(str(rel))
            sha_text = str(sha).strip().lower()
            if not _is_hex_sha256(sha_text):
                raise VerificationFailure(f"invalid sha256 for paper asset '{relpath}'")
            rows.append((relpath, sha_text))
        return sorted(rows, key=lambda t: t[0])

    files = _parse_entries(manifest.get("files"), field_name="files")
    snippets = _parse_entries(manifest.get("snippets"), field_name="snippets")
    if not files:
        raise VerificationFailure("paper assets manifest does not list any files")
    snippet_set = {rel for rel, _ in snippets}
    have_all_tex = any(PurePosixPath(rel).name == "phase2_e2_all.tex" for rel in snippet_set)
    have_all_md = any(PurePosixPath(rel).name == "phase2_e2_all.md" for rel in snippet_set)
    if not (have_all_tex and have_all_md):
        raise VerificationFailure(
            "bundle missing phase2_e2_all.*; regenerate paper assets with v10.1.1-phase2-m70+"
        )
    missing_required = [rel for rel in REQUIRED_PAPER_SNIPPETS if rel not in snippet_set]
    if missing_required:
        missing_text = ", ".join(sorted(missing_required))
        raise VerificationFailure(
            "paper assets manifest missing required snippets: "
            + missing_text
        )
    return files, snippets


def _decode_utf8_snippet(data: bytes, *, label: str) -> str:
    try:
        return data.decode("utf-8")
    except Exception as exc:
        raise VerificationFailure(f"failed to decode snippet as UTF-8: {label}") from exc


def _validate_phase2_all_aggregator(*, snippet_payloads: Mapping[str, bytes]) -> None:
    tex_candidates = sorted(rel for rel in snippet_payloads if PurePosixPath(rel).name == "phase2_e2_all.tex")
    md_candidates = sorted(rel for rel in snippet_payloads if PurePosixPath(rel).name == "phase2_e2_all.md")
    if not tex_candidates or not md_candidates:
        raise VerificationFailure(
            "bundle missing phase2_e2_all.*; regenerate paper assets with v10.1.1-phase2-m70+"
        )
    if len(tex_candidates) != 1 or len(md_candidates) != 1:
        raise VerificationFailure("multiple phase2_e2_all snippets found; cannot validate aggregator consistency")

    tex_label = tex_candidates[0]
    md_label = md_candidates[0]
    tex_text = _decode_utf8_snippet(snippet_payloads[tex_label], label=tex_label)
    md_text = _decode_utf8_snippet(snippet_payloads[md_label], label=md_label)
    if PHASE2_E2_ALL_MARKER not in tex_text:
        raise VerificationFailure(f"phase2_e2_all tex marker missing in {tex_label}")
    if PHASE2_E2_ALL_MARKER not in md_text:
        raise VerificationFailure(f"phase2_e2_all md marker missing in {md_label}")
    for needle in canonical_all_tex_inputs():
        if needle not in tex_text:
            raise VerificationFailure(f"phase2_e2_all tex missing include: {needle}")
    for marker in canonical_all_md_begin_markers():
        if marker not in md_text:
            raise VerificationFailure(f"phase2_e2_all md missing marker: {marker}")


def _validate_phase2_sf_rsd_summary_marker(*, snippet_payloads: Mapping[str, bytes]) -> None:
    tex_candidates = sorted(rel for rel in snippet_payloads if PurePosixPath(rel).name == "phase2_sf_rsd_summary.tex")
    md_candidates = sorted(rel for rel in snippet_payloads if PurePosixPath(rel).name == "phase2_sf_rsd_summary.md")
    if not tex_candidates or not md_candidates:
        raise VerificationFailure("bundle missing Phase-2 SF RSD snippet; re-run make_paper_assets")

    tex_text = _decode_utf8_snippet(snippet_payloads[tex_candidates[0]], label=tex_candidates[0])
    md_text = _decode_utf8_snippet(snippet_payloads[md_candidates[0]], label=md_candidates[0])
    if SF_RSD_SNIPPET_MARKER not in tex_text:
        raise VerificationFailure(f"phase2_sf_rsd_summary marker missing in {tex_candidates[0]}")
    if SF_RSD_SNIPPET_MARKER not in md_text:
        raise VerificationFailure(f"phase2_sf_rsd_summary marker missing in {md_candidates[0]}")


def _validate_phase2_sf_fsigma8_marker(*, snippet_payloads: Mapping[str, bytes]) -> None:
    tex_candidates = sorted(rel for rel in snippet_payloads if PurePosixPath(rel).name == "phase2_sf_fsigma8.tex")
    md_candidates = sorted(rel for rel in snippet_payloads if PurePosixPath(rel).name == "phase2_sf_fsigma8.md")
    if not tex_candidates or not md_candidates:
        raise VerificationFailure("bundle missing Phase-2 SF fσ8 snippet; re-run make_paper_assets")

    tex_text = _decode_utf8_snippet(snippet_payloads[tex_candidates[0]], label=tex_candidates[0])
    md_text = _decode_utf8_snippet(snippet_payloads[md_candidates[0]], label=md_candidates[0])
    if SF_FSIGMA8_SNIPPET_MARKER not in tex_text:
        raise VerificationFailure(f"phase2_sf_fsigma8 marker missing in {tex_candidates[0]}")
    if SF_FSIGMA8_SNIPPET_MARKER not in md_text:
        raise VerificationFailure(f"phase2_sf_fsigma8 marker missing in {md_candidates[0]}")


def _validate_phase2_best_candidates_marker(*, snippet_payloads: Mapping[str, bytes]) -> None:
    tex_candidates = sorted(rel for rel in snippet_payloads if PurePosixPath(rel).name == "phase2_e2_best_candidates.tex")
    md_candidates = sorted(rel for rel in snippet_payloads if PurePosixPath(rel).name == "phase2_e2_best_candidates.md")
    if not tex_candidates or not md_candidates:
        raise VerificationFailure("bundle missing Phase-2 best-candidates snippet; re-run make_paper_assets")

    tex_text = _decode_utf8_snippet(snippet_payloads[tex_candidates[0]], label=tex_candidates[0])
    md_text = _decode_utf8_snippet(snippet_payloads[md_candidates[0]], label=md_candidates[0])
    if BEST_CANDIDATES_SNIPPET_MARKER not in tex_text:
        raise VerificationFailure(f"phase2_e2_best_candidates marker missing in {tex_candidates[0]}")
    if BEST_CANDIDATES_SNIPPET_MARKER not in md_text:
        raise VerificationFailure(f"phase2_e2_best_candidates marker missing in {md_candidates[0]}")


def _validate_phase2_rg_markers(*, snippet_payloads: Mapping[str, bytes]) -> None:
    flow_tex_candidates = sorted(rel for rel in snippet_payloads if PurePosixPath(rel).name == "phase2_rg_flow_table.tex")
    flow_md_candidates = sorted(rel for rel in snippet_payloads if PurePosixPath(rel).name == "phase2_rg_flow_table.md")
    pade_tex_candidates = sorted(rel for rel in snippet_payloads if PurePosixPath(rel).name == "phase2_rg_pade_fit.tex")
    pade_md_candidates = sorted(rel for rel in snippet_payloads if PurePosixPath(rel).name == "phase2_rg_pade_fit.md")

    if not flow_tex_candidates or not flow_md_candidates:
        raise VerificationFailure("bundle missing Phase-2 RG flow-table snippet; re-run make_paper_assets")
    if not pade_tex_candidates or not pade_md_candidates:
        raise VerificationFailure("bundle missing Phase-2 RG Padé snippet; re-run make_paper_assets")

    flow_tex = _decode_utf8_snippet(snippet_payloads[flow_tex_candidates[0]], label=flow_tex_candidates[0])
    flow_md = _decode_utf8_snippet(snippet_payloads[flow_md_candidates[0]], label=flow_md_candidates[0])
    pade_tex = _decode_utf8_snippet(snippet_payloads[pade_tex_candidates[0]], label=pade_tex_candidates[0])
    pade_md = _decode_utf8_snippet(snippet_payloads[pade_md_candidates[0]], label=pade_md_candidates[0])
    if RG_FLOW_SNIPPET_MARKER not in flow_tex:
        raise VerificationFailure(f"phase2_rg_flow_table marker missing in {flow_tex_candidates[0]}")
    if RG_FLOW_SNIPPET_MARKER not in flow_md:
        raise VerificationFailure(f"phase2_rg_flow_table marker missing in {flow_md_candidates[0]}")
    if RG_PADE_SNIPPET_MARKER not in pade_tex:
        raise VerificationFailure(f"phase2_rg_pade_fit marker missing in {pade_tex_candidates[0]}")
    if RG_PADE_SNIPPET_MARKER not in pade_md:
        raise VerificationFailure(f"phase2_rg_pade_fit marker missing in {pade_md_candidates[0]}")


def _validate_consistency_report_presence(*, files: Sequence[Tuple[str, str]]) -> None:
    basenames = {PurePosixPath(rel).name for rel, _ in files}
    missing: List[str] = []
    if CONSISTENCY_REPORT_JSON not in basenames:
        missing.append(CONSISTENCY_REPORT_JSON)
    if CONSISTENCY_REPORT_MD not in basenames:
        missing.append(CONSISTENCY_REPORT_MD)
    if missing:
        raise VerificationFailure(
            "bundle missing Phase-2 consistency report; re-run make_paper_assets "
            f"(missing: {', '.join(sorted(missing))})"
        )


def _detect_paper_assets_manifest_relpath_dir(bundle_dir: Path) -> str:
    preferred = [
        PAPER_ASSETS_MANIFEST_NAME,
        f"paper_assets/{PAPER_ASSETS_MANIFEST_NAME}",
    ]
    for candidate in preferred:
        path = bundle_dir / candidate
        if path.is_file():
            return _normalize_relpath(candidate)

    matches = sorted(
        _normalize_relpath(str(p.relative_to(bundle_dir)).replace(os.sep, "/"))
        for p in bundle_dir.rglob(PAPER_ASSETS_MANIFEST_NAME)
        if p.is_file()
    )
    if not matches:
        raise VerificationFailure(f"{PAPER_ASSETS_MANIFEST_NAME} missing")
    if len(matches) == 1:
        return matches[0]
    raise VerificationFailure(f"multiple {PAPER_ASSETS_MANIFEST_NAME} files found; cannot auto-select")


def _detect_paper_assets_manifest_relpath_archive(names: Sequence[str]) -> str:
    normalized = sorted(_normalize_relpath(str(name)) for name in names)
    preferred = [
        PAPER_ASSETS_MANIFEST_NAME,
        f"paper_assets/{PAPER_ASSETS_MANIFEST_NAME}",
    ]
    for candidate in preferred:
        matches = [n for n in normalized if n == candidate or n.endswith("/" + candidate)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            exact = [m for m in matches if m == candidate]
            if len(exact) == 1:
                return exact[0]
            raise VerificationFailure(f"multiple {PAPER_ASSETS_MANIFEST_NAME} files found; cannot auto-select")

    wildcard = [n for n in normalized if PurePosixPath(n).name == PAPER_ASSETS_MANIFEST_NAME]
    if len(wildcard) == 1:
        return wildcard[0]
    if not wildcard:
        raise VerificationFailure(f"{PAPER_ASSETS_MANIFEST_NAME} missing")
    raise VerificationFailure(f"multiple {PAPER_ASSETS_MANIFEST_NAME} files found; cannot auto-select")


def _parse_jsonl_records_bytes(data: bytes, *, source_label: str) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    try:
        text = data.decode("utf-8")
    except Exception as exc:
        raise VerificationFailure(f"failed to decode JSONL from {source_label}: {exc}") from exc
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except Exception as exc:
            raise VerificationFailure(f"failed to parse JSONL from {source_label} line {line_no}") from exc
        if not isinstance(payload, Mapping):
            continue
        records.append({str(k): payload[k] for k in payload.keys()})
    return records


def _parse_jsonl_records_bytes_runtime(data: bytes, *, source_label: str) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    try:
        text = data.decode("utf-8")
    except Exception as exc:
        raise ValueError(f"failed to decode JSONL from {source_label}: {exc}") from exc
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except Exception as exc:
            raise ValueError(f"failed to parse JSONL from {source_label} line {line_no}") from exc
        if not isinstance(payload, Mapping):
            continue
        records.append({str(k): payload[k] for k in payload.keys()})
    return records


def _collect_plan_source_seen(records: Iterable[Mapping[str, Any]]) -> List[str]:
    seen: set[str] = set()
    for record in records:
        raw = record.get("plan_source_sha256")
        if not isinstance(raw, str):
            continue
        text = raw.strip()
        if text:
            seen.add(text)
    return sorted(seen)


def _scan_config_bucket(record: Mapping[str, Any]) -> str:
    raw = record.get("scan_config_sha256")
    if not isinstance(raw, str):
        return "__MISSING__"
    text = raw.strip()
    return text if text else "__MISSING__"


def _is_scan_data_record(record: Mapping[str, Any]) -> bool:
    probe_keys = ("params_hash", "params", "status", "chi2_total", "chi2", "plan_point_id", "model")
    return any(key in record for key in probe_keys)


def _collect_scan_config_counts(
    records: Iterable[Mapping[str, Any]],
    *,
    source_label: str,
) -> Tuple[Dict[str, int], Dict[str, str]]:
    counts: Dict[str, int] = {}
    examples: Dict[str, str] = {}
    for idx, record in enumerate(records, start=1):
        if not _is_scan_data_record(record):
            continue
        bucket = _scan_config_bucket(record)
        counts[bucket] = int(counts.get(bucket, 0) + 1)
        if bucket not in examples:
            examples[bucket] = f"{source_label}:{idx}"
    return counts, examples


def _accumulate_scan_config_counts(
    target_counts: Dict[str, int],
    target_examples: Dict[str, str],
    *,
    add_counts: Mapping[str, int],
    add_examples: Mapping[str, str],
) -> None:
    for key, value in add_counts.items():
        target_counts[str(key)] = int(target_counts.get(str(key), 0) + int(value))
    for key, value in add_examples.items():
        skey = str(key)
        if skey not in target_examples:
            target_examples[skey] = str(value)


def _extract_declared_plan_source_sha(payload: Mapping[str, Any]) -> Optional[str]:
    source = payload.get("source")
    if isinstance(source, Mapping):
        for key in ("jsonl_sha256", "source_sha256"):
            raw = source.get(key)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
    for key in ("plan_source_sha256", "source_jsonl_sha256", "jsonl_sha256"):
        raw = payload.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return None


def _select_plan_and_jsonl_relpaths(
    *,
    relpaths: Sequence[str],
    read_bytes,
) -> Tuple[str, str]:
    plan_candidates: List[str] = []
    for relpath in sorted(set(str(p) for p in relpaths)):
        if not relpath.lower().endswith(".json"):
            continue
        try:
            payload = _parse_manifest_bytes(read_bytes(relpath))
        except Exception:
            continue
        if str(payload.get("plan_version", "")).strip() == "phase2_e2_refine_plan_v1" and isinstance(
            payload.get("points"), list
        ):
            plan_candidates.append(relpath)
    if not plan_candidates:
        raise ValueError("bundle does not contain a refine plan (phase2_e2_refine_plan_v1)")
    plan_relpath = sorted(plan_candidates)[0]

    jsonl_candidates = sorted(p for p in set(str(p) for p in relpaths) if str(p).lower().endswith(".jsonl"))
    if not jsonl_candidates:
        raise ValueError("bundle does not contain JSONL scan results")

    mapped_candidate: Optional[str] = None
    for relpath in jsonl_candidates:
        try:
            records = _parse_jsonl_records_bytes(read_bytes(relpath), source_label=relpath)
        except Exception:
            continue
        has_plan_id = any(bool(str(rec.get("plan_point_id", "")).strip()) for rec in records if isinstance(rec, Mapping))
        if has_plan_id:
            mapped_candidate = relpath
            break
    jsonl_relpath = mapped_candidate if mapped_candidate is not None else jsonl_candidates[0]
    return plan_relpath, jsonl_relpath


def _parse_manifest_bytes(data: bytes) -> Mapping[str, Any]:
    try:
        payload = json.loads(data.decode("utf-8"))
    except Exception as exc:
        raise VerificationFailure(f"failed to parse manifest JSON: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise VerificationFailure("manifest root must be a JSON object")
    return payload


def _parse_lineage_nodes(data: bytes, *, label: str) -> List[Tuple[str, str, Optional[int]]]:
    try:
        payload = json.loads(data.decode("utf-8"))
    except Exception as exc:
        raise VerificationFailure(f"failed to parse lineage JSON ({label}): {exc}") from exc
    if not isinstance(payload, Mapping):
        raise VerificationFailure(f"lineage payload must be a JSON object ({label})")
    nodes = payload.get("nodes")
    if not isinstance(nodes, list):
        raise VerificationFailure(f"lineage payload missing 'nodes' list ({label})")

    parsed: List[Tuple[str, str, Optional[int]]] = []
    seen: set[str] = set()
    for item in nodes:
        if not isinstance(item, Mapping):
            continue
        rel_raw = item.get("path")
        sha_raw = item.get("sha256")
        if rel_raw is None or sha_raw is None:
            continue
        rel = _normalize_relpath(str(rel_raw))
        if rel == LINEAGE_FILE_NAME:
            # Self-hash cannot be stable for the lineage file itself; skip if present.
            continue
        sha = str(sha_raw).strip().lower()
        if not _is_hex_sha256(sha):
            raise VerificationFailure(f"invalid lineage sha256 for {rel} ({label})")
        if rel in seen:
            continue
        seen.add(rel)
        size_val = item.get("bytes")
        size: Optional[int]
        if size_val is None:
            size = None
        else:
            try:
                size = int(size_val)
            except Exception as exc:
                raise VerificationFailure(f"invalid lineage bytes value for {rel} ({label})") from exc
            if size < 0:
                raise VerificationFailure(f"invalid lineage bytes value for {rel} ({label})")
        parsed.append((rel, sha, size))
    return sorted(parsed, key=lambda t: t[0])


def _validate_lineage_nodes_dir(
    *,
    bundle_dir: Path,
    lineage_relpath: str,
    lineage_nodes: Sequence[Tuple[str, str, Optional[int]]],
) -> List[Dict[str, str]]:
    errors: List[Dict[str, str]] = []
    for rel, expected_sha, expected_bytes in lineage_nodes:
        target = bundle_dir / rel
        if not target.exists():
            errors.append({"kind": "missing", "path": rel, "detail": f"LINEAGE_MISSING_TARGET referenced_by={lineage_relpath}"})
            continue
        if target.is_symlink():
            errors.append({"kind": "security", "path": rel, "detail": f"LINEAGE_SECURITY_SYMLINK referenced_by={lineage_relpath}"})
            continue
        if not target.is_file():
            errors.append({"kind": "missing", "path": rel, "detail": f"LINEAGE_MISSING_TARGET_NOT_FILE referenced_by={lineage_relpath}"})
            continue
        got_sha = _sha256_file(target).lower()
        if got_sha != expected_sha:
            errors.append(
                {
                    "kind": "mismatch",
                    "path": rel,
                    "detail": f"LINEAGE_HASH_MISMATCH expected={expected_sha} got={got_sha}",
                }
            )
            continue
        if expected_bytes is not None:
            got_bytes = int(target.stat().st_size)
            if got_bytes != int(expected_bytes):
                errors.append(
                    {
                        "kind": "mismatch",
                        "path": rel,
                        "detail": f"LINEAGE_SIZE_MISMATCH expected={expected_bytes} got={got_bytes}",
                    }
                )
    return errors


def _detect_manifest_for_dir(bundle_dir: Path, requested: Optional[str]) -> str:
    if requested is not None:
        rel = _normalize_relpath(requested)
        target = bundle_dir / rel
        if not target.is_file():
            raise VerificationFailure(f"manifest not found at requested path: {rel}")
        return rel

    for candidate in DEFAULT_MANIFEST_CANDIDATES:
        if (bundle_dir / candidate).is_file():
            return candidate

    wildcard = sorted(p.name for p in bundle_dir.glob("*manifest*.json") if p.is_file())
    if len(wildcard) == 1:
        return wildcard[0]
    raise VerificationFailure("manifest not found (auto-detect failed)")


def _archive_regular_member_names_zip(zf: zipfile.ZipFile) -> List[str]:
    names: List[str] = []
    for info in zf.infolist():
        name = info.filename or ""
        if not name or name.endswith("/"):
            continue
        norm = _normalize_relpath(name)
        mode = (int(info.external_attr) >> 16) & 0xFFFF
        if mode and stat.S_ISLNK(mode):
            raise VerificationFailure(f"symlink entry not allowed in archive: {norm}")
        names.append(norm)
    return sorted(names)


def _archive_regular_member_names_tar(tf: tarfile.TarFile) -> List[str]:
    names: List[str] = []
    for info in tf.getmembers():
        name = str(info.name or "").strip()
        if not name:
            continue
        norm = _normalize_relpath(name)
        if info.issym() or info.islnk():
            raise VerificationFailure(f"symlink/hardlink entry not allowed in archive: {norm}")
        if info.isfile():
            names.append(norm)
    return sorted(names)


def _detect_manifest_for_archive(names: Sequence[str], requested: Optional[str]) -> str:
    name_list = list(names)
    if requested is not None:
        rel = _normalize_relpath(requested)
        matches = [n for n in name_list if n == rel or n.endswith("/" + rel)]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise VerificationFailure(f"manifest not found at requested path: {rel}")
        raise VerificationFailure(f"manifest path is ambiguous in archive: {rel}")

    for candidate in DEFAULT_MANIFEST_CANDIDATES:
        rel = _normalize_relpath(candidate)
        matches = [n for n in name_list if n == rel or n.endswith("/" + rel)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            exact = [m for m in matches if m == rel]
            if len(exact) == 1:
                return exact[0]
            raise VerificationFailure(f"manifest auto-detect ambiguous for {candidate}")

    wildcard = [n for n in name_list if PurePosixPath(n).name.endswith(".json") and "manifest" in PurePosixPath(n).name]
    if len(wildcard) == 1:
        return wildcard[0]
    raise VerificationFailure("manifest not found in archive (auto-detect failed)")


def _join_archive_prefix(prefix: str, relpath: str) -> str:
    if not prefix:
        return relpath
    return str(PurePosixPath(prefix) / relpath)


def _normalize_extract_prefixes(raw_prefixes: Sequence[str]) -> List[Tuple[str, Tuple[str, ...]]]:
    prefixes = list(raw_prefixes) if raw_prefixes else list(DEFAULT_EXTRACT_PREFIXES)
    out: List[Tuple[str, Tuple[str, ...]]] = []
    seen: set[str] = set()
    for raw in prefixes:
        text = str(raw or "").strip()
        if not text:
            continue
        norm = _normalize_relpath(text.rstrip("/"))
        if norm in seen:
            continue
        seen.add(norm)
        parts = tuple(PurePosixPath(norm).parts)
        if not parts:
            continue
        out.append((norm, parts))
    if not out:
        raise VerificationFailure("no valid extract prefixes configured")
    return sorted(out, key=lambda item: item[0])


def _starts_with_parts(parts: Sequence[str], prefix_parts: Sequence[str]) -> bool:
    if len(prefix_parts) > len(parts):
        return False
    return tuple(parts[: len(prefix_parts)]) == tuple(prefix_parts)


def _strip_optional_prefix_wrappers(parts: Sequence[str]) -> Tuple[str, ...]:
    out = tuple(parts)
    while out and out[0] in {"v11.0.0", "paper_assets"}:
        out = out[1:]
    return out


def _match_extract_prefix(
    *,
    source_relpath: str,
    prefixes: Sequence[Tuple[str, Tuple[str, ...]]],
) -> Optional[Dict[str, str]]:
    source_norm = _normalize_relpath(source_relpath)
    source_parts = tuple(PurePosixPath(source_norm).parts)
    source_core = _strip_optional_prefix_wrappers(source_parts)
    best: Optional[Dict[str, str]] = None
    best_score: Optional[Tuple[int, str, str]] = None

    for prefix_norm, prefix_parts in prefixes:
        prefix_core = _strip_optional_prefix_wrappers(prefix_parts)
        if not prefix_core:
            continue
        if not _starts_with_parts(source_core, prefix_core):
            continue

        remainder = tuple(source_core[len(prefix_core) :])
        output_prefix_parts = prefix_parts

        output_prefix = _normalize_relpath(str(PurePosixPath(*output_prefix_parts)))
        output_relpath = _normalize_relpath(str(PurePosixPath(*(output_prefix_parts + remainder))))
        score = (len(prefix_parts), output_prefix, output_relpath)
        if best is None or best_score is None or score > best_score:
            best = {
                "source_relpath": source_norm,
                "output_relpath": output_relpath,
                "output_prefix": output_prefix,
                "matched_prefix": prefix_norm,
            }
            best_score = score
    return best


def _build_extract_plan(
    *,
    entries: Mapping[str, str],
    prefixes: Sequence[Tuple[str, Tuple[str, ...]]],
) -> Tuple[List[Dict[str, str]], List[str]]:
    selected: Dict[str, Dict[str, str]] = {}
    cleanup_prefixes: set[str] = set()
    for source_relpath in sorted(entries.keys()):
        match = _match_extract_prefix(source_relpath=source_relpath, prefixes=prefixes)
        if match is None:
            continue
        payload = {
            "source_relpath": str(match["source_relpath"]),
            "output_relpath": str(match["output_relpath"]),
            "output_prefix": str(match["output_prefix"]),
            "matched_prefix": str(match["matched_prefix"]),
            "expected_sha256": str(entries[source_relpath]).lower(),
        }
        existing = selected.get(payload["output_relpath"])
        if existing is None or payload["source_relpath"] < str(existing.get("source_relpath", "")):
            selected[payload["output_relpath"]] = payload
        cleanup_prefixes.add(payload["output_prefix"])
    if not selected:
        requested = ", ".join(prefix for prefix, _ in prefixes)
        raise VerificationFailure(f"no files matched extract prefixes: {requested}")
    plan = [selected[key] for key in sorted(selected.keys())]
    return plan, sorted(cleanup_prefixes)


def _ensure_within_root(root: Path, relpath: str) -> Path:
    root_resolved = root.resolve()
    target = (root_resolved / relpath).resolve()
    try:
        target.relative_to(root_resolved)
    except ValueError as exc:
        raise VerificationFailure(f"refusing to write outside extract root: {relpath}") from exc
    return target


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp_verify_extract")
    tmp.write_bytes(data)
    tmp.replace(path)


def _apply_extract_plan(
    *,
    extract_root: Path,
    extract_mode: str,
    cleanup_prefixes: Sequence[str],
    payloads: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    root = extract_root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    if extract_mode == "clean_overwrite":
        for prefix in sorted(set(str(p) for p in cleanup_prefixes)):
            target = _ensure_within_root(root, prefix)
            if not target.exists():
                continue
            if target.is_symlink():
                raise VerificationFailure(f"refusing to remove symlink target during clean_overwrite: {prefix}")
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
    elif extract_mode != "overwrite":
        raise VerificationFailure(f"unsupported extract mode: {extract_mode}")

    written: List[str] = []
    for payload in payloads:
        relpath = str(payload["output_relpath"])
        data = bytes(payload["data"])
        destination = _ensure_within_root(root, relpath)
        _atomic_write_bytes(destination, data)
        written.append(relpath)

    return {
        "extract_root": str(root),
        "extract_mode": str(extract_mode),
        "prefixes": sorted(set(str(p) for p in cleanup_prefixes)),
        "n_extracted": len(written),
        "paths_sample": written[:50],
    }


def _verify_dir(
    bundle_dir: Path,
    *,
    manifest_relpath_arg: Optional[str],
    strict_extras: bool,
    verbose: bool,
) -> Dict[str, Any]:
    manifest_relpath = _detect_manifest_for_dir(bundle_dir, manifest_relpath_arg)
    manifest_path = bundle_dir / manifest_relpath
    manifest = _parse_manifest_bytes(manifest_path.read_bytes())
    schema_id = str(manifest.get("schema", "UNKNOWN"))
    entries = _adapter_entries(manifest)

    errors: List[Dict[str, str]] = []
    n_verified = 0
    for relpath, sha_expected in entries:
        target = bundle_dir / relpath
        if not target.exists():
            errors.append({"kind": "missing", "path": relpath, "detail": "file not found"})
            if len(errors) >= MAX_JSON_ERRORS:
                break
            continue
        if target.is_symlink():
            errors.append({"kind": "security", "path": relpath, "detail": "symlink not allowed"})
            if len(errors) >= MAX_JSON_ERRORS:
                break
            continue
        if not target.is_file():
            errors.append({"kind": "missing", "path": relpath, "detail": "not a regular file"})
            if len(errors) >= MAX_JSON_ERRORS:
                break
            continue
        got = _sha256_file(target).lower()
        if got != sha_expected:
            errors.append(
                {
                    "kind": "mismatch",
                    "path": relpath,
                    "detail": f"expected={sha_expected} got={got}",
                }
            )
            if len(errors) >= MAX_JSON_ERRORS:
                break
            continue
        n_verified += 1
        if verbose:
            print(f"OK: {relpath}")

    lineage_relpath = LINEAGE_FILE_NAME
    lineage_path = bundle_dir / lineage_relpath
    if not lineage_path.is_file():
        errors.append({"kind": "missing", "path": lineage_relpath, "detail": "LINEAGE_MISSING"})
    else:
        lineage_nodes = _parse_lineage_nodes(lineage_path.read_bytes(), label=lineage_relpath)
        errors.extend(
            _validate_lineage_nodes_dir(
                bundle_dir=bundle_dir,
                lineage_relpath=lineage_relpath,
                lineage_nodes=lineage_nodes,
            )
        )

    expected_files = set(rel for rel, _ in entries)
    expected_files.add(_normalize_relpath(manifest_relpath))
    if lineage_path.is_file():
        expected_files.add(_normalize_relpath(lineage_relpath))
    extras: List[str] = []
    for root, _, files in os.walk(bundle_dir):
        for filename in sorted(files):
            abs_path = Path(root) / filename
            rel = _normalize_relpath(str(abs_path.relative_to(bundle_dir)).replace(os.sep, "/"))
            if abs_path.is_symlink():
                errors.append({"kind": "security", "path": rel, "detail": "symlink not allowed"})
                if len(errors) >= MAX_JSON_ERRORS:
                    break
                continue
            if rel not in expected_files:
                extras.append(rel)
        if len(errors) >= MAX_JSON_ERRORS:
            break

    if strict_extras and extras:
        for rel in extras[:MAX_JSON_ERRORS - len(errors)]:
            errors.append({"kind": "extra", "path": rel, "detail": "extra file not listed in manifest"})

    return {
        "ok": len(errors) == 0,
        "bundle_kind": "dir",
        "manifest_relpath": manifest_relpath,
        "schema_id": schema_id,
        "n_files_manifest": len(entries),
        "n_verified": n_verified,
        "n_missing": sum(1 for e in errors if e.get("kind") == "missing"),
        "n_mismatch": sum(1 for e in errors if e.get("kind") == "mismatch"),
        "n_extras": len(extras),
        "errors": errors[:MAX_JSON_ERRORS],
    }


def _verify_zip(
    bundle_path: Path,
    *,
    manifest_relpath_arg: Optional[str],
    strict_extras: bool,
    verbose: bool,
) -> Dict[str, Any]:
    with zipfile.ZipFile(bundle_path, "r") as zf:
        names = _archive_regular_member_names_zip(zf)
        manifest_member = _detect_manifest_for_archive(names, manifest_relpath_arg)
        manifest = _parse_manifest_bytes(zf.read(manifest_member))
        schema_id = str(manifest.get("schema", "UNKNOWN"))
        entries = _adapter_entries(manifest)

        root_prefix = str(PurePosixPath(manifest_member).parent)
        if root_prefix == ".":
            root_prefix = ""

        index: Dict[str, zipfile.ZipInfo] = {}
        for info in zf.infolist():
            name = info.filename or ""
            if not name or name.endswith("/"):
                continue
            norm = _normalize_relpath(name)
            if norm not in index:
                index[norm] = info

        errors: List[Dict[str, str]] = []
        n_verified = 0
        for relpath, sha_expected in entries:
            member_name = _join_archive_prefix(root_prefix, relpath)
            info = index.get(member_name)
            if info is None:
                errors.append({"kind": "missing", "path": relpath, "detail": "archive member not found"})
                if len(errors) >= MAX_JSON_ERRORS:
                    break
                continue
            with zf.open(info, "r") as fh:
                got = _sha256_stream(fh).lower()
            if got != sha_expected:
                errors.append(
                    {
                        "kind": "mismatch",
                        "path": relpath,
                        "detail": f"expected={sha_expected} got={got}",
                    }
                )
                if len(errors) >= MAX_JSON_ERRORS:
                    break
                continue
            n_verified += 1
            if verbose:
                print(f"OK: {relpath}")

        lineage_member = _join_archive_prefix(root_prefix, LINEAGE_FILE_NAME)
        lineage_info = index.get(lineage_member)
        if lineage_info is None:
            errors.append({"kind": "missing", "path": LINEAGE_FILE_NAME, "detail": "LINEAGE_MISSING"})
        else:
            lineage_nodes = _parse_lineage_nodes(zf.read(lineage_info), label=lineage_member)
            for rel, expected_sha, expected_bytes in lineage_nodes:
                member_name = _join_archive_prefix(root_prefix, rel)
                info = index.get(member_name)
                if info is None:
                    errors.append(
                        {
                            "kind": "missing",
                            "path": rel,
                            "detail": f"LINEAGE_MISSING_TARGET referenced_by={lineage_member}",
                        }
                    )
                    continue
                with zf.open(info, "r") as fh:
                    data = fh.read()
                got_sha = _sha256_bytes(data).lower()
                if got_sha != expected_sha:
                    errors.append(
                        {
                            "kind": "mismatch",
                            "path": rel,
                            "detail": f"LINEAGE_HASH_MISMATCH expected={expected_sha} got={got_sha}",
                        }
                    )
                    continue
                if expected_bytes is not None and int(len(data)) != int(expected_bytes):
                    errors.append(
                        {
                            "kind": "mismatch",
                            "path": rel,
                            "detail": f"LINEAGE_SIZE_MISMATCH expected={expected_bytes} got={len(data)}",
                        }
                    )

        expected_members = {_join_archive_prefix(root_prefix, rel) for rel, _ in entries}
        expected_members.add(manifest_member)
        if lineage_info is not None:
            expected_members.add(lineage_member)
        extras = sorted(n for n in names if n not in expected_members)
        if strict_extras and extras:
            for rel in extras[:MAX_JSON_ERRORS - len(errors)]:
                errors.append({"kind": "extra", "path": rel, "detail": "extra archive member not listed in manifest"})

        return {
            "ok": len(errors) == 0,
            "bundle_kind": "zip",
            "manifest_relpath": manifest_member,
            "schema_id": schema_id,
            "n_files_manifest": len(entries),
            "n_verified": n_verified,
            "n_missing": sum(1 for e in errors if e.get("kind") == "missing"),
            "n_mismatch": sum(1 for e in errors if e.get("kind") == "mismatch"),
            "n_extras": len(extras),
            "errors": errors[:MAX_JSON_ERRORS],
        }


def _verify_tar(
    bundle_path: Path,
    *,
    manifest_relpath_arg: Optional[str],
    strict_extras: bool,
    verbose: bool,
) -> Dict[str, Any]:
    with tarfile.open(bundle_path, "r:*") as tf:
        names = _archive_regular_member_names_tar(tf)
        manifest_member = _detect_manifest_for_archive(names, manifest_relpath_arg)
        manifest_data = tf.extractfile(manifest_member)
        if manifest_data is None:
            raise VerificationFailure(f"failed to read manifest member: {manifest_member}")
        manifest = _parse_manifest_bytes(manifest_data.read())
        schema_id = str(manifest.get("schema", "UNKNOWN"))
        entries = _adapter_entries(manifest)

        root_prefix = str(PurePosixPath(manifest_member).parent)
        if root_prefix == ".":
            root_prefix = ""

        members: Dict[str, tarfile.TarInfo] = {}
        for info in tf.getmembers():
            name = str(info.name or "").strip()
            if not name:
                continue
            norm = _normalize_relpath(name)
            if info.issym() or info.islnk():
                raise VerificationFailure(f"symlink/hardlink entry not allowed in archive: {norm}")
            if info.isfile() and norm not in members:
                members[norm] = info

        errors: List[Dict[str, str]] = []
        n_verified = 0
        for relpath, sha_expected in entries:
            member_name = _join_archive_prefix(root_prefix, relpath)
            info = members.get(member_name)
            if info is None:
                errors.append({"kind": "missing", "path": relpath, "detail": "archive member not found"})
                if len(errors) >= MAX_JSON_ERRORS:
                    break
                continue
            fh = tf.extractfile(info)
            if fh is None:
                errors.append({"kind": "missing", "path": relpath, "detail": "failed to read member bytes"})
                if len(errors) >= MAX_JSON_ERRORS:
                    break
                continue
            with fh:
                got = _sha256_stream(fh).lower()
            if got != sha_expected:
                errors.append(
                    {
                        "kind": "mismatch",
                        "path": relpath,
                        "detail": f"expected={sha_expected} got={got}",
                    }
                )
                if len(errors) >= MAX_JSON_ERRORS:
                    break
                continue
            n_verified += 1
            if verbose:
                print(f"OK: {relpath}")

        lineage_member = _join_archive_prefix(root_prefix, LINEAGE_FILE_NAME)
        lineage_info = members.get(lineage_member)
        if lineage_info is None:
            errors.append({"kind": "missing", "path": LINEAGE_FILE_NAME, "detail": "LINEAGE_MISSING"})
        else:
            lineage_fh = tf.extractfile(lineage_info)
            if lineage_fh is None:
                errors.append({"kind": "missing", "path": LINEAGE_FILE_NAME, "detail": "LINEAGE_MISSING"})
            else:
                with lineage_fh:
                    lineage_bytes = lineage_fh.read()
                lineage_nodes = _parse_lineage_nodes(lineage_bytes, label=lineage_member)
                for rel, expected_sha, expected_bytes in lineage_nodes:
                    member_name = _join_archive_prefix(root_prefix, rel)
                    info = members.get(member_name)
                    if info is None:
                        errors.append(
                            {
                                "kind": "missing",
                                "path": rel,
                                "detail": f"LINEAGE_MISSING_TARGET referenced_by={lineage_member}",
                            }
                        )
                        continue
                    fh = tf.extractfile(info)
                    if fh is None:
                        errors.append(
                            {
                                "kind": "missing",
                                "path": rel,
                                "detail": f"LINEAGE_MISSING_TARGET referenced_by={lineage_member}",
                            }
                        )
                        continue
                    with fh:
                        data = fh.read()
                    got_sha = _sha256_bytes(data).lower()
                    if got_sha != expected_sha:
                        errors.append(
                            {
                                "kind": "mismatch",
                                "path": rel,
                                "detail": f"LINEAGE_HASH_MISMATCH expected={expected_sha} got={got_sha}",
                            }
                        )
                        continue
                    if expected_bytes is not None and int(len(data)) != int(expected_bytes):
                        errors.append(
                            {
                                "kind": "mismatch",
                                "path": rel,
                                "detail": f"LINEAGE_SIZE_MISMATCH expected={expected_bytes} got={len(data)}",
                            }
                        )

        expected_members = {_join_archive_prefix(root_prefix, rel) for rel, _ in entries}
        expected_members.add(manifest_member)
        if lineage_info is not None:
            expected_members.add(lineage_member)
        extras = sorted(n for n in names if n not in expected_members)
        if strict_extras and extras:
            for rel in extras[:MAX_JSON_ERRORS - len(errors)]:
                errors.append({"kind": "extra", "path": rel, "detail": "extra archive member not listed in manifest"})

        return {
            "ok": len(errors) == 0,
            "bundle_kind": "tar",
            "manifest_relpath": manifest_member,
            "schema_id": schema_id,
            "n_files_manifest": len(entries),
            "n_verified": n_verified,
            "n_missing": sum(1 for e in errors if e.get("kind") == "missing"),
            "n_mismatch": sum(1 for e in errors if e.get("kind") == "mismatch"),
            "n_extras": len(extras),
            "errors": errors[:MAX_JSON_ERRORS],
        }


def _verify_bundle(
    bundle: Path,
    *,
    manifest_relpath: Optional[str],
    strict_extras: bool,
    verbose: bool,
) -> Dict[str, Any]:
    if bundle.is_dir():
        report = _verify_dir(
            bundle,
            manifest_relpath_arg=manifest_relpath,
            strict_extras=strict_extras,
            verbose=verbose,
        )
        return report

    if not bundle.is_file():
        raise VerificationFailure(f"bundle path does not exist: {bundle}")

    lower = bundle.name.lower()
    if lower.endswith(".zip"):
        return _verify_zip(
            bundle,
            manifest_relpath_arg=manifest_relpath,
            strict_extras=strict_extras,
            verbose=verbose,
        )
    if lower.endswith(".tar") or lower.endswith(".tar.gz") or lower.endswith(".tgz"):
        return _verify_tar(
            bundle,
            manifest_relpath_arg=manifest_relpath,
            strict_extras=strict_extras,
            verbose=verbose,
        )
    raise VerificationFailure(f"unsupported bundle format: {bundle.suffix or bundle.name}")


def _schema_targets_from_dir(*, bundle_dir: Path, manifest_relpath: str) -> List[Tuple[str, bytes]]:
    targets: List[Tuple[str, bytes]] = []
    manifest_norm = _normalize_relpath(manifest_relpath)
    manifest_path = bundle_dir / manifest_norm
    if not manifest_path.is_file():
        raise VerificationFailure(f"manifest not found for schema validation: {manifest_norm}")
    targets.append((manifest_norm, manifest_path.read_bytes()))

    lineage_path = bundle_dir / LINEAGE_FILE_NAME
    if lineage_path.is_file():
        targets.append((LINEAGE_FILE_NAME, lineage_path.read_bytes()))

    consistency_paths = sorted(
        p for p in bundle_dir.rglob(CONSISTENCY_REPORT_JSON) if p.is_file()
    )
    for path in consistency_paths:
        rel = _normalize_relpath(path.relative_to(bundle_dir).as_posix())
        targets.append((rel, path.read_bytes()))

    dedup: Dict[str, bytes] = {}
    for rel, data in targets:
        if rel not in dedup:
            dedup[rel] = data
    return [(rel, dedup[rel]) for rel in sorted(dedup.keys())]


def _schema_targets_from_zip(*, bundle_path: Path, manifest_relpath: str) -> List[Tuple[str, bytes]]:
    targets: List[Tuple[str, bytes]] = []
    manifest_member = _normalize_relpath(manifest_relpath)
    with zipfile.ZipFile(bundle_path, "r") as zf:
        names = _archive_regular_member_names_zip(zf)
        name_set = set(names)
        if manifest_member not in name_set:
            raise VerificationFailure(f"manifest not found for schema validation: {manifest_member}")
        targets.append((manifest_member, zf.read(manifest_member)))

        root_prefix = str(PurePosixPath(manifest_member).parent)
        if root_prefix == ".":
            root_prefix = ""
        lineage_member = _join_archive_prefix(root_prefix, LINEAGE_FILE_NAME)
        if lineage_member in name_set:
            targets.append((lineage_member, zf.read(lineage_member)))

        for name in sorted(names):
            if PurePosixPath(name).name != CONSISTENCY_REPORT_JSON:
                continue
            targets.append((name, zf.read(name)))

    dedup: Dict[str, bytes] = {}
    for rel, data in targets:
        if rel not in dedup:
            dedup[rel] = data
    return [(rel, dedup[rel]) for rel in sorted(dedup.keys())]


def _schema_targets_from_tar(*, bundle_path: Path, manifest_relpath: str) -> List[Tuple[str, bytes]]:
    targets: List[Tuple[str, bytes]] = []
    manifest_member = _normalize_relpath(manifest_relpath)
    with tarfile.open(bundle_path, "r:*") as tf:
        names = _archive_regular_member_names_tar(tf)
        name_set = set(names)
        if manifest_member not in name_set:
            raise VerificationFailure(f"manifest not found for schema validation: {manifest_member}")
        manifest_fh = tf.extractfile(manifest_member)
        if manifest_fh is None:
            raise VerificationFailure(f"failed to read manifest for schema validation: {manifest_member}")
        with manifest_fh:
            targets.append((manifest_member, manifest_fh.read()))

        root_prefix = str(PurePosixPath(manifest_member).parent)
        if root_prefix == ".":
            root_prefix = ""
        lineage_member = _join_archive_prefix(root_prefix, LINEAGE_FILE_NAME)
        if lineage_member in name_set:
            lineage_fh = tf.extractfile(lineage_member)
            if lineage_fh is not None:
                with lineage_fh:
                    targets.append((lineage_member, lineage_fh.read()))

        for name in sorted(names):
            if PurePosixPath(name).name != CONSISTENCY_REPORT_JSON:
                continue
            fh = tf.extractfile(name)
            if fh is None:
                continue
            with fh:
                targets.append((name, fh.read()))

    dedup: Dict[str, bytes] = {}
    for rel, data in targets:
        if rel not in dedup:
            dedup[rel] = data
    return [(rel, dedup[rel]) for rel in sorted(dedup.keys())]


def _schema_targets_for_bundle(
    *,
    bundle: Path,
    bundle_kind: str,
    manifest_relpath: str,
) -> List[Tuple[str, bytes]]:
    if bundle_kind == "dir":
        return _schema_targets_from_dir(bundle_dir=bundle, manifest_relpath=manifest_relpath)
    if bundle_kind == "zip":
        return _schema_targets_from_zip(bundle_path=bundle, manifest_relpath=manifest_relpath)
    if bundle_kind == "tar":
        return _schema_targets_from_tar(bundle_path=bundle, manifest_relpath=manifest_relpath)
    raise VerificationFailure(f"unsupported bundle kind for schema validation: {bundle_kind}")


def _validate_bundle_schemas(
    *,
    bundle: Path,
    bundle_kind: str,
    manifest_relpath: str,
) -> Dict[str, Any]:
    targets = _schema_targets_for_bundle(
        bundle=bundle,
        bundle_kind=bundle_kind,
        manifest_relpath=manifest_relpath,
    )
    validator = _scripts_dir() / "phase2_schema_validate.py"
    schema_dir = _schema_dir()
    if not validator.is_file():
        raise VerificationFailure(f"{SCHEMA_VALIDATE_FAILED_MARKER}: validator script missing: {validator}")
    if not schema_dir.is_dir():
        raise VerificationFailure(f"{SCHEMA_VALIDATE_FAILED_MARKER}: schema dir missing: {schema_dir}")

    rows: List[Dict[str, Any]] = []
    for relpath, data in targets:
        with tempfile.TemporaryDirectory() as td:
            td_root = Path(td).resolve()
            payload_path = td_root / PurePosixPath(relpath).name
            payload_path.write_bytes(data)
            cmd = [
                sys.executable,
                str(validator),
                "--auto",
                "--schema-dir",
                str(schema_dir),
                "--json",
                str(payload_path),
                "--format",
                "json",
            ]
            rc, stdout, stderr, payload = _run_subprocess_json(cmd, cwd=_scripts_dir().parent)
        if rc != 0:
            detail = f"{SCHEMA_VALIDATE_FAILED_MARKER}: path={relpath}"
            if isinstance(payload, Mapping) and payload.get("n_errors") is not None:
                detail += f" n_errors={payload.get('n_errors')}"
            if stderr.strip():
                detail += f" stderr={stderr.strip()}"
            if stdout.strip() and payload is None:
                detail += f" stdout={stdout.strip()}"
            raise VerificationFailure(
                detail,
                errors=[{"kind": "schema", "path": relpath, "detail": detail}],
            )
        if not isinstance(payload, Mapping):
            detail = f"{SCHEMA_VALIDATE_FAILED_MARKER}: non-JSON validator output for path={relpath}"
            raise VerificationFailure(
                detail,
                errors=[{"kind": "schema", "path": relpath, "detail": detail}],
            )
        rows.append(
            {
                "path": relpath,
                "ok": bool(payload.get("ok", False)),
                "schema": str(payload.get("schema", "")),
                "schema_selected_by": str(payload.get("schema_selected_by", "")),
                "engine": str(payload.get("engine", "")),
                "n_errors": int(payload.get("n_errors", 0)),
            }
        )

    rows.sort(key=lambda row: str(row.get("path", "")))
    return {
        "ok": True,
        "n_checked": len(rows),
        "files": rows,
    }


def _lint_portable_content(*, bundle: Path) -> Dict[str, Any]:
    lint_script = _scripts_dir() / "phase2_portable_content_lint.py"
    if not lint_script.is_file():
        raise VerificationFailure(
            f"{PORTABLE_CONTENT_LINT_FAILED_MARKER}: lint script missing: {lint_script}"
        )
    cmd = [
        sys.executable,
        str(lint_script),
        "--path",
        str(bundle),
        "--format",
        "json",
        "--include-glob",
        "*.json",
        "--include-glob",
        "*.jsonl",
    ]
    rc, stdout, stderr, payload = _run_subprocess_json(cmd, cwd=_scripts_dir().parent)
    if rc == 0:
        if not isinstance(payload, Mapping):
            detail = "portable-content lint returned non-JSON payload"
            raise VerificationFailure(
                f"{PORTABLE_CONTENT_LINT_FAILED_MARKER}: {detail}",
                errors=[{"kind": "portable", "path": "", "detail": detail}],
            )
        return {
            "ok": True,
            "offending_file_count": int(payload.get("offending_file_count", 0)),
            "marker": payload.get("marker"),
            "payload": payload,
        }
    if rc == 2:
        marker = "unknown"
        offending = None
        if isinstance(payload, Mapping):
            marker = str(payload.get("marker", "unknown"))
            offending = payload.get("offending_file_count")
        detail = (
            f"{PORTABLE_CONTENT_LINT_FAILED_MARKER}: marker={marker} "
            f"offending_file_count={offending if offending is not None else 'unknown'}"
        )
        if stderr.strip():
            detail += f" stderr={stderr.strip()}"
        raise VerificationFailure(
            detail,
            errors=[{"kind": "portable", "path": "", "detail": detail}],
        )
    detail = f"portable-content lint failed to execute (exit={rc})"
    if stderr.strip():
        detail += f" stderr={stderr.strip()}"
    if stdout.strip():
        detail += f" stdout={stdout.strip()}"
    raise ValueError(detail)


def _verify_paper_assets_dir(*, bundle_dir: Path) -> Dict[str, Any]:
    manifest_relpath = _detect_paper_assets_manifest_relpath_dir(bundle_dir)
    manifest_path = bundle_dir / manifest_relpath
    payload = _parse_manifest_bytes(manifest_path.read_bytes())
    files, snippets = _paper_assets_entries(payload)
    manifest_parent = manifest_path.parent
    snippet_relpaths = {rel for rel, _ in snippets}

    errors: List[Dict[str, str]] = []
    verified = 0
    snippet_payloads: Dict[str, bytes] = {}
    for relpath, expected_sha in sorted(set(files + snippets), key=lambda t: t[0]):
        target = manifest_parent / relpath
        if not target.exists():
            errors.append({"kind": "missing", "path": relpath, "detail": "paper asset file not found"})
            continue
        if target.is_symlink():
            errors.append({"kind": "security", "path": relpath, "detail": "symlink not allowed"})
            continue
        if not target.is_file():
            errors.append({"kind": "missing", "path": relpath, "detail": "not a regular file"})
            continue
        data = target.read_bytes()
        got_sha = _sha256_bytes(data).lower()
        if got_sha != expected_sha:
            errors.append({"kind": "mismatch", "path": relpath, "detail": f"expected={expected_sha} got={got_sha}"})
            continue
        if relpath in snippet_relpaths:
            snippet_payloads[relpath] = data
        verified += 1

    if errors:
        raise VerificationFailure(
            f"paper assets verification failed ({len(errors)} errors)",
            errors=errors[:MAX_JSON_ERRORS],
        )
    _validate_phase2_all_aggregator(snippet_payloads=snippet_payloads)
    _validate_phase2_best_candidates_marker(snippet_payloads=snippet_payloads)
    _validate_phase2_sf_rsd_summary_marker(snippet_payloads=snippet_payloads)
    _validate_phase2_sf_fsigma8_marker(snippet_payloads=snippet_payloads)
    _validate_phase2_rg_markers(snippet_payloads=snippet_payloads)
    _validate_consistency_report_presence(files=files)
    return {
        "manifest_relpath": manifest_relpath,
        "schema_id": PAPER_ASSETS_SCHEMA_ID,
        "n_files": len(files),
        "n_snippets": len(snippets),
        "n_verified": verified,
    }


def _verify_paper_assets_zip(*, bundle_path: Path) -> Dict[str, Any]:
    with zipfile.ZipFile(bundle_path, "r") as zf:
        names = _archive_regular_member_names_zip(zf)
        manifest_member = _detect_paper_assets_manifest_relpath_archive(names)
        payload = _parse_manifest_bytes(zf.read(manifest_member))
        files, snippets = _paper_assets_entries(payload)
        snippet_relpaths = {rel for rel, _ in snippets}
        root_prefix = str(PurePosixPath(manifest_member).parent)
        if root_prefix == ".":
            root_prefix = ""

        index: Dict[str, zipfile.ZipInfo] = {}
        for info in zf.infolist():
            name = info.filename or ""
            if not name or name.endswith("/"):
                continue
            norm = _normalize_relpath(name)
            if norm not in index:
                index[norm] = info

        errors: List[Dict[str, str]] = []
        verified = 0
        snippet_payloads: Dict[str, bytes] = {}
        for relpath, expected_sha in sorted(set(files + snippets), key=lambda t: t[0]):
            member_name = _join_archive_prefix(root_prefix, relpath)
            info = index.get(member_name)
            if info is None:
                errors.append({"kind": "missing", "path": relpath, "detail": "paper asset archive member not found"})
                continue
            with zf.open(info, "r") as fh:
                data = fh.read()
            got_sha = _sha256_bytes(data).lower()
            if got_sha != expected_sha:
                errors.append({"kind": "mismatch", "path": relpath, "detail": f"expected={expected_sha} got={got_sha}"})
                continue
            if relpath in snippet_relpaths:
                snippet_payloads[relpath] = data
            verified += 1

        if errors:
            raise VerificationFailure(
                f"paper assets verification failed ({len(errors)} errors)",
                errors=errors[:MAX_JSON_ERRORS],
            )
        _validate_phase2_all_aggregator(snippet_payloads=snippet_payloads)
        _validate_phase2_best_candidates_marker(snippet_payloads=snippet_payloads)
        _validate_phase2_sf_rsd_summary_marker(snippet_payloads=snippet_payloads)
        _validate_phase2_sf_fsigma8_marker(snippet_payloads=snippet_payloads)
        _validate_phase2_rg_markers(snippet_payloads=snippet_payloads)
        _validate_consistency_report_presence(files=files)
        return {
            "manifest_relpath": manifest_member,
            "schema_id": PAPER_ASSETS_SCHEMA_ID,
            "n_files": len(files),
            "n_snippets": len(snippets),
            "n_verified": verified,
        }


def _verify_paper_assets_tar(*, bundle_path: Path) -> Dict[str, Any]:
    with tarfile.open(bundle_path, "r:*") as tf:
        names = _archive_regular_member_names_tar(tf)
        manifest_member = _detect_paper_assets_manifest_relpath_archive(names)
        manifest_fh = tf.extractfile(manifest_member)
        if manifest_fh is None:
            raise VerificationFailure(f"failed to read {PAPER_ASSETS_MANIFEST_NAME} from archive")
        with manifest_fh:
            payload = _parse_manifest_bytes(manifest_fh.read())
        files, snippets = _paper_assets_entries(payload)
        snippet_relpaths = {rel for rel, _ in snippets}
        root_prefix = str(PurePosixPath(manifest_member).parent)
        if root_prefix == ".":
            root_prefix = ""

        members: Dict[str, tarfile.TarInfo] = {}
        for info in tf.getmembers():
            name = str(info.name or "").strip()
            if not name:
                continue
            norm = _normalize_relpath(name)
            if info.issym() or info.islnk():
                raise VerificationFailure(f"symlink/hardlink entry not allowed in archive: {norm}")
            if info.isfile() and norm not in members:
                members[norm] = info

        errors: List[Dict[str, str]] = []
        verified = 0
        snippet_payloads: Dict[str, bytes] = {}
        for relpath, expected_sha in sorted(set(files + snippets), key=lambda t: t[0]):
            member_name = _join_archive_prefix(root_prefix, relpath)
            info = members.get(member_name)
            if info is None:
                errors.append({"kind": "missing", "path": relpath, "detail": "paper asset archive member not found"})
                continue
            fh = tf.extractfile(info)
            if fh is None:
                errors.append({"kind": "missing", "path": relpath, "detail": "failed to read paper asset member"})
                continue
            with fh:
                data = fh.read()
            got_sha = _sha256_bytes(data).lower()
            if got_sha != expected_sha:
                errors.append({"kind": "mismatch", "path": relpath, "detail": f"expected={expected_sha} got={got_sha}"})
                continue
            if relpath in snippet_relpaths:
                snippet_payloads[relpath] = data
            verified += 1

        if errors:
            raise VerificationFailure(
                f"paper assets verification failed ({len(errors)} errors)",
                errors=errors[:MAX_JSON_ERRORS],
            )
        _validate_phase2_all_aggregator(snippet_payloads=snippet_payloads)
        _validate_phase2_best_candidates_marker(snippet_payloads=snippet_payloads)
        _validate_phase2_sf_rsd_summary_marker(snippet_payloads=snippet_payloads)
        _validate_phase2_sf_fsigma8_marker(snippet_payloads=snippet_payloads)
        _validate_phase2_rg_markers(snippet_payloads=snippet_payloads)
        _validate_consistency_report_presence(files=files)
        return {
            "manifest_relpath": manifest_member,
            "schema_id": PAPER_ASSETS_SCHEMA_ID,
            "n_files": len(files),
            "n_snippets": len(snippets),
            "n_verified": verified,
        }


def _enforce_paper_assets(
    *,
    bundle: Path,
    bundle_kind: str,
    mode: str,
) -> Dict[str, Any]:
    if mode == "ignore":
        return {}
    if mode != "require":
        raise ValueError(f"unsupported --paper-assets mode: {mode!r}")

    if bundle_kind == "dir":
        return _verify_paper_assets_dir(bundle_dir=bundle)
    if bundle_kind == "zip":
        return _verify_paper_assets_zip(bundle_path=bundle)
    if bundle_kind == "tar":
        return _verify_paper_assets_tar(bundle_path=bundle)
    raise ValueError(f"unsupported bundle kind for paper assets: {bundle_kind!r}")


def _extract_paper_assets_from_dir(
    *,
    bundle_dir: Path,
    manifest_relpath: str,
    extract_root: Path,
    extract_prefixes: Sequence[Tuple[str, Tuple[str, ...]]],
    extract_mode: str,
) -> Dict[str, Any]:
    manifest_path = bundle_dir / _normalize_relpath(manifest_relpath)
    if not manifest_path.is_file():
        raise VerificationFailure(f"manifest not found for extraction: {manifest_relpath}")
    manifest = _parse_manifest_bytes(manifest_path.read_bytes())
    entries = {rel: sha for rel, sha in _adapter_entries(manifest)}
    plan, cleanup_prefixes = _build_extract_plan(entries=entries, prefixes=extract_prefixes)

    payloads: List[Dict[str, Any]] = []
    for item in plan:
        source_rel = str(item["source_relpath"])
        source_path = bundle_dir / source_rel
        if not source_path.exists():
            raise VerificationFailure(f"paper asset source missing in bundle directory: {source_rel}")
        if source_path.is_symlink():
            raise VerificationFailure(f"symlink source not allowed for extraction: {source_rel}")
        if not source_path.is_file():
            raise VerificationFailure(f"paper asset source is not a regular file: {source_rel}")
        data = source_path.read_bytes()
        got = _sha256_bytes(data).lower()
        expected = str(item["expected_sha256"]).lower()
        if got != expected:
            raise VerificationFailure(f"paper asset hash mismatch before extract: {source_rel}")
        payloads.append(
            {
                "output_relpath": str(item["output_relpath"]),
                "data": data,
            }
        )
    return _apply_extract_plan(
        extract_root=extract_root,
        extract_mode=extract_mode,
        cleanup_prefixes=cleanup_prefixes,
        payloads=payloads,
    )


def _extract_paper_assets_from_zip(
    *,
    bundle_path: Path,
    manifest_relpath: str,
    extract_root: Path,
    extract_prefixes: Sequence[Tuple[str, Tuple[str, ...]]],
    extract_mode: str,
) -> Dict[str, Any]:
    with zipfile.ZipFile(bundle_path, "r") as zf:
        _archive_regular_member_names_zip(zf)
        manifest_member = _normalize_relpath(manifest_relpath)
        manifest = _parse_manifest_bytes(zf.read(manifest_member))
        entries = {rel: sha for rel, sha in _adapter_entries(manifest)}
        plan, cleanup_prefixes = _build_extract_plan(entries=entries, prefixes=extract_prefixes)
        root_prefix = str(PurePosixPath(manifest_member).parent)
        if root_prefix == ".":
            root_prefix = ""

        index: Dict[str, zipfile.ZipInfo] = {}
        for info in zf.infolist():
            name = info.filename or ""
            if not name or name.endswith("/"):
                continue
            norm = _normalize_relpath(name)
            if norm not in index:
                index[norm] = info

        payloads: List[Dict[str, Any]] = []
        for item in plan:
            source_rel = str(item["source_relpath"])
            member_name = _join_archive_prefix(root_prefix, source_rel)
            info = index.get(member_name)
            if info is None:
                raise VerificationFailure(f"paper asset source missing in archive: {source_rel}")
            with zf.open(info, "r") as fh:
                data = fh.read()
            got = _sha256_bytes(data).lower()
            expected = str(item["expected_sha256"]).lower()
            if got != expected:
                raise VerificationFailure(f"paper asset hash mismatch before extract: {source_rel}")
            payloads.append(
                {
                    "output_relpath": str(item["output_relpath"]),
                    "data": data,
                }
            )
    return _apply_extract_plan(
        extract_root=extract_root,
        extract_mode=extract_mode,
        cleanup_prefixes=cleanup_prefixes,
        payloads=payloads,
    )


def _extract_paper_assets_from_tar(
    *,
    bundle_path: Path,
    manifest_relpath: str,
    extract_root: Path,
    extract_prefixes: Sequence[Tuple[str, Tuple[str, ...]]],
    extract_mode: str,
) -> Dict[str, Any]:
    with tarfile.open(bundle_path, "r:*") as tf:
        _archive_regular_member_names_tar(tf)
        manifest_member = _normalize_relpath(manifest_relpath)
        manifest_fh = tf.extractfile(manifest_member)
        if manifest_fh is None:
            raise VerificationFailure(f"failed to read manifest member for extraction: {manifest_member}")
        with manifest_fh:
            manifest = _parse_manifest_bytes(manifest_fh.read())
        entries = {rel: sha for rel, sha in _adapter_entries(manifest)}
        plan, cleanup_prefixes = _build_extract_plan(entries=entries, prefixes=extract_prefixes)
        root_prefix = str(PurePosixPath(manifest_member).parent)
        if root_prefix == ".":
            root_prefix = ""

        members: Dict[str, tarfile.TarInfo] = {}
        for info in tf.getmembers():
            name = str(info.name or "").strip()
            if not name:
                continue
            norm = _normalize_relpath(name)
            if info.issym() or info.islnk():
                raise VerificationFailure(f"symlink/hardlink entry not allowed in archive: {norm}")
            if info.isfile() and norm not in members:
                members[norm] = info

        payloads: List[Dict[str, Any]] = []
        for item in plan:
            source_rel = str(item["source_relpath"])
            member_name = _join_archive_prefix(root_prefix, source_rel)
            info = members.get(member_name)
            if info is None:
                raise VerificationFailure(f"paper asset source missing in archive: {source_rel}")
            fh = tf.extractfile(info)
            if fh is None:
                raise VerificationFailure(f"failed to read archive member for extraction: {source_rel}")
            with fh:
                data = fh.read()
            got = _sha256_bytes(data).lower()
            expected = str(item["expected_sha256"]).lower()
            if got != expected:
                raise VerificationFailure(f"paper asset hash mismatch before extract: {source_rel}")
            payloads.append(
                {
                    "output_relpath": str(item["output_relpath"]),
                    "data": data,
                }
            )
    return _apply_extract_plan(
        extract_root=extract_root,
        extract_mode=extract_mode,
        cleanup_prefixes=cleanup_prefixes,
        payloads=payloads,
    )


def _extract_paper_assets(
    *,
    bundle: Path,
    bundle_kind: str,
    manifest_relpath: str,
    extract_root: Path,
    extract_prefixes: Sequence[str],
    extract_mode: str,
) -> Dict[str, Any]:
    prefixes = _normalize_extract_prefixes(extract_prefixes)
    if bundle_kind == "dir":
        return _extract_paper_assets_from_dir(
            bundle_dir=bundle,
            manifest_relpath=manifest_relpath,
            extract_root=extract_root,
            extract_prefixes=prefixes,
            extract_mode=extract_mode,
        )
    if bundle_kind == "zip":
        return _extract_paper_assets_from_zip(
            bundle_path=bundle,
            manifest_relpath=manifest_relpath,
            extract_root=extract_root,
            extract_prefixes=prefixes,
            extract_mode=extract_mode,
        )
    if bundle_kind == "tar":
        return _extract_paper_assets_from_tar(
            bundle_path=bundle,
            manifest_relpath=manifest_relpath,
            extract_root=extract_root,
            extract_prefixes=prefixes,
            extract_mode=extract_mode,
        )
    raise VerificationFailure(f"unsupported bundle kind for extraction: {bundle_kind}")


def _coverage_from_dir(
    *,
    bundle_dir: Path,
    manifest_relpath: str,
) -> Dict[str, Any]:
    manifest_path = bundle_dir / _normalize_relpath(manifest_relpath)
    if not manifest_path.is_file():
        raise ValueError(f"manifest not found for coverage check: {manifest_relpath}")
    manifest = _parse_manifest_bytes(manifest_path.read_bytes())
    relpaths = _adapter_relpaths(manifest)

    def _read_bytes(relpath: str) -> bytes:
        target = bundle_dir / _normalize_relpath(relpath)
        if not target.is_file():
            raise VerificationFailure(f"missing file required for coverage: {relpath}")
        if target.is_symlink():
            raise VerificationFailure(f"symlink not allowed for coverage: {relpath}")
        return target.read_bytes()

    plan_relpath, jsonl_relpath = _select_plan_and_jsonl_relpaths(relpaths=relpaths, read_bytes=_read_bytes)
    plan_payload = _parse_manifest_bytes(_read_bytes(plan_relpath))
    records = load_jsonl_records(bundle_dir / _normalize_relpath(jsonl_relpath))
    coverage, _, _, _ = analyze_plan_coverage(
        plan_payload=plan_payload,
        records=records,
        plan_path=plan_relpath,
        jsonl_path=jsonl_relpath,
        max_id_list=50,
    )
    return coverage


def _coverage_from_zip(
    *,
    bundle_path: Path,
    manifest_member: str,
) -> Dict[str, Any]:
    with zipfile.ZipFile(bundle_path, "r") as zf:
        names = _archive_regular_member_names_zip(zf)
        manifest_norm = _normalize_relpath(manifest_member)
        manifest_data = zf.read(manifest_norm)
        manifest = _parse_manifest_bytes(manifest_data)
        relpaths = _adapter_relpaths(manifest)
        root_prefix = str(PurePosixPath(manifest_norm).parent)
        if root_prefix == ".":
            root_prefix = ""

        index: Dict[str, zipfile.ZipInfo] = {}
        for info in zf.infolist():
            name = info.filename or ""
            if not name or name.endswith("/"):
                continue
            norm = _normalize_relpath(name)
            if norm not in index:
                index[norm] = info

        def _read_bytes(relpath: str) -> bytes:
            member_name = _join_archive_prefix(root_prefix, _normalize_relpath(relpath))
            info = index.get(member_name)
            if info is None:
                raise VerificationFailure(f"missing archive member required for coverage: {relpath}")
            with zf.open(info, "r") as fh:
                return fh.read()

        plan_relpath, jsonl_relpath = _select_plan_and_jsonl_relpaths(relpaths=relpaths, read_bytes=_read_bytes)
        plan_payload = _parse_manifest_bytes(_read_bytes(plan_relpath))
        records = _parse_jsonl_records_bytes(_read_bytes(jsonl_relpath), source_label=jsonl_relpath)
        coverage, _, _, _ = analyze_plan_coverage(
            plan_payload=plan_payload,
            records=records,
            plan_path=plan_relpath,
            jsonl_path=jsonl_relpath,
            max_id_list=50,
        )
        return coverage


def _coverage_from_tar(
    *,
    bundle_path: Path,
    manifest_member: str,
) -> Dict[str, Any]:
    with tarfile.open(bundle_path, "r:*") as tf:
        _archive_regular_member_names_tar(tf)
        manifest_norm = _normalize_relpath(manifest_member)
        manifest_fh = tf.extractfile(manifest_norm)
        if manifest_fh is None:
            raise VerificationFailure(f"failed to read manifest member for coverage: {manifest_norm}")
        with manifest_fh:
            manifest = _parse_manifest_bytes(manifest_fh.read())
        relpaths = _adapter_relpaths(manifest)
        root_prefix = str(PurePosixPath(manifest_norm).parent)
        if root_prefix == ".":
            root_prefix = ""

        members: Dict[str, tarfile.TarInfo] = {}
        for info in tf.getmembers():
            name = str(info.name or "").strip()
            if not name:
                continue
            norm = _normalize_relpath(name)
            if info.issym() or info.islnk():
                raise VerificationFailure(f"symlink/hardlink entry not allowed in archive: {norm}")
            if info.isfile() and norm not in members:
                members[norm] = info

        def _read_bytes(relpath: str) -> bytes:
            member_name = _join_archive_prefix(root_prefix, _normalize_relpath(relpath))
            info = members.get(member_name)
            if info is None:
                raise VerificationFailure(f"missing archive member required for coverage: {relpath}")
            fh = tf.extractfile(info)
            if fh is None:
                raise VerificationFailure(f"failed to read archive member required for coverage: {relpath}")
            with fh:
                return fh.read()

        plan_relpath, jsonl_relpath = _select_plan_and_jsonl_relpaths(relpaths=relpaths, read_bytes=_read_bytes)
        plan_payload = _parse_manifest_bytes(_read_bytes(plan_relpath))
        records = _parse_jsonl_records_bytes(_read_bytes(jsonl_relpath), source_label=jsonl_relpath)
        coverage, _, _, _ = analyze_plan_coverage(
            plan_payload=plan_payload,
            records=records,
            plan_path=plan_relpath,
            jsonl_path=jsonl_relpath,
            max_id_list=50,
        )
        return coverage


def _plan_source_context_from_dir(
    *,
    bundle_dir: Path,
    manifest_relpath: str,
) -> Dict[str, Any]:
    manifest_path = bundle_dir / _normalize_relpath(manifest_relpath)
    if not manifest_path.is_file():
        raise ValueError(f"manifest not found for plan-source check: {manifest_relpath}")
    manifest = _parse_manifest_bytes(manifest_path.read_bytes())
    relpaths = _adapter_relpaths(manifest)

    plan_relpath: Optional[str] = None
    plan_sha_expected: Optional[str] = None
    plan_source_declared: Optional[str] = None
    for relpath in sorted(relpaths):
        if not relpath.lower().endswith(".json"):
            continue
        target = bundle_dir / _normalize_relpath(relpath)
        if not target.is_file():
            continue
        try:
            payload = _parse_manifest_bytes(target.read_bytes())
        except Exception:
            continue
        if str(payload.get("plan_version", "")).strip() == "phase2_e2_refine_plan_v1" and isinstance(
            payload.get("points"), list
        ):
            plan_relpath = relpath
            plan_sha_expected = _sha256_file(target).lower()
            plan_source_declared = _extract_declared_plan_source_sha(payload)
            break

    seen_set: set[str] = set()
    scan_config_counts: Dict[str, int] = {}
    scan_config_examples: Dict[str, str] = {}
    for relpath in sorted(relpaths):
        if not relpath.lower().endswith(".jsonl"):
            continue
        target = bundle_dir / _normalize_relpath(relpath)
        if not target.is_file():
            raise ValueError(f"missing JSONL required for plan-source check: {relpath}")
        records = load_jsonl_records(target)
        for value in _collect_plan_source_seen(records):
            seen_set.add(value)
        counts, examples = _collect_scan_config_counts(records, source_label=relpath)
        _accumulate_scan_config_counts(
            scan_config_counts,
            scan_config_examples,
            add_counts=counts,
            add_examples=examples,
        )

    return {
        "plan_relpath": plan_relpath,
        "plan_sha256_expected": plan_sha_expected,
        "plan_source_sha256_declared": plan_source_declared,
        "plan_source_sha256_seen_set": sorted(seen_set),
        "scan_config_sha256_counts": {
            str(k): int(v)
            for k, v in sorted(scan_config_counts.items(), key=lambda kv: str(kv[0]))
        },
        "scan_config_sha256_examples": {
            str(k): str(v)
            for k, v in sorted(scan_config_examples.items(), key=lambda kv: str(kv[0]))
        },
    }


def _plan_source_context_from_zip(
    *,
    bundle_path: Path,
    manifest_member: str,
) -> Dict[str, Any]:
    with zipfile.ZipFile(bundle_path, "r") as zf:
        names = _archive_regular_member_names_zip(zf)
        manifest_norm = _normalize_relpath(manifest_member)
        if manifest_norm not in names:
            raise ValueError(f"manifest not found for plan-source check: {manifest_norm}")
        manifest = _parse_manifest_bytes(zf.read(manifest_norm))
        relpaths = _adapter_relpaths(manifest)
        root_prefix = str(PurePosixPath(manifest_norm).parent)
        if root_prefix == ".":
            root_prefix = ""

        index: Dict[str, zipfile.ZipInfo] = {}
        for info in zf.infolist():
            name = info.filename or ""
            if not name or name.endswith("/"):
                continue
            norm = _normalize_relpath(name)
            if norm not in index:
                index[norm] = info

        def _read_bytes(relpath: str) -> bytes:
            member_name = _join_archive_prefix(root_prefix, _normalize_relpath(relpath))
            info = index.get(member_name)
            if info is None:
                raise ValueError(f"missing archive member required for plan-source check: {relpath}")
            with zf.open(info, "r") as fh:
                return fh.read()

        plan_relpath: Optional[str] = None
        plan_sha_expected: Optional[str] = None
        plan_source_declared: Optional[str] = None
        for relpath in sorted(relpaths):
            if not relpath.lower().endswith(".json"):
                continue
            try:
                payload_bytes = _read_bytes(relpath)
                payload = _parse_manifest_bytes(payload_bytes)
            except Exception:
                continue
            if str(payload.get("plan_version", "")).strip() == "phase2_e2_refine_plan_v1" and isinstance(
                payload.get("points"), list
            ):
                plan_relpath = relpath
                plan_sha_expected = _sha256_bytes(payload_bytes).lower()
                plan_source_declared = _extract_declared_plan_source_sha(payload)
                break

        seen_set: set[str] = set()
        scan_config_counts: Dict[str, int] = {}
        scan_config_examples: Dict[str, str] = {}
        for relpath in sorted(relpaths):
            if not relpath.lower().endswith(".jsonl"):
                continue
            records = _parse_jsonl_records_bytes_runtime(_read_bytes(relpath), source_label=relpath)
            for value in _collect_plan_source_seen(records):
                seen_set.add(value)
            counts, examples = _collect_scan_config_counts(records, source_label=relpath)
            _accumulate_scan_config_counts(
                scan_config_counts,
                scan_config_examples,
                add_counts=counts,
                add_examples=examples,
            )

        return {
            "plan_relpath": plan_relpath,
            "plan_sha256_expected": plan_sha_expected,
            "plan_source_sha256_declared": plan_source_declared,
            "plan_source_sha256_seen_set": sorted(seen_set),
            "scan_config_sha256_counts": {
                str(k): int(v)
                for k, v in sorted(scan_config_counts.items(), key=lambda kv: str(kv[0]))
            },
            "scan_config_sha256_examples": {
                str(k): str(v)
                for k, v in sorted(scan_config_examples.items(), key=lambda kv: str(kv[0]))
            },
        }


def _plan_source_context_from_tar(
    *,
    bundle_path: Path,
    manifest_member: str,
) -> Dict[str, Any]:
    with tarfile.open(bundle_path, "r:*") as tf:
        _archive_regular_member_names_tar(tf)
        manifest_norm = _normalize_relpath(manifest_member)
        manifest_fh = tf.extractfile(manifest_norm)
        if manifest_fh is None:
            raise ValueError(f"failed to read manifest for plan-source check: {manifest_norm}")
        with manifest_fh:
            manifest = _parse_manifest_bytes(manifest_fh.read())
        relpaths = _adapter_relpaths(manifest)
        root_prefix = str(PurePosixPath(manifest_norm).parent)
        if root_prefix == ".":
            root_prefix = ""

        members: Dict[str, tarfile.TarInfo] = {}
        for info in tf.getmembers():
            name = str(info.name or "").strip()
            if not name:
                continue
            norm = _normalize_relpath(name)
            if info.issym() or info.islnk():
                raise VerificationFailure(f"symlink/hardlink entry not allowed in archive: {norm}")
            if info.isfile() and norm not in members:
                members[norm] = info

        def _read_bytes(relpath: str) -> bytes:
            member_name = _join_archive_prefix(root_prefix, _normalize_relpath(relpath))
            info = members.get(member_name)
            if info is None:
                raise ValueError(f"missing archive member required for plan-source check: {relpath}")
            fh = tf.extractfile(info)
            if fh is None:
                raise ValueError(f"failed to read archive member required for plan-source check: {relpath}")
            with fh:
                return fh.read()

        plan_relpath: Optional[str] = None
        plan_sha_expected: Optional[str] = None
        plan_source_declared: Optional[str] = None
        for relpath in sorted(relpaths):
            if not relpath.lower().endswith(".json"):
                continue
            try:
                payload_bytes = _read_bytes(relpath)
                payload = _parse_manifest_bytes(payload_bytes)
            except Exception:
                continue
            if str(payload.get("plan_version", "")).strip() == "phase2_e2_refine_plan_v1" and isinstance(
                payload.get("points"), list
            ):
                plan_relpath = relpath
                plan_sha_expected = _sha256_bytes(payload_bytes).lower()
                plan_source_declared = _extract_declared_plan_source_sha(payload)
                break

        seen_set: set[str] = set()
        scan_config_counts: Dict[str, int] = {}
        scan_config_examples: Dict[str, str] = {}
        for relpath in sorted(relpaths):
            if not relpath.lower().endswith(".jsonl"):
                continue
            records = _parse_jsonl_records_bytes_runtime(_read_bytes(relpath), source_label=relpath)
            for value in _collect_plan_source_seen(records):
                seen_set.add(value)
            counts, examples = _collect_scan_config_counts(records, source_label=relpath)
            _accumulate_scan_config_counts(
                scan_config_counts,
                scan_config_examples,
                add_counts=counts,
                add_examples=examples,
            )

        return {
            "plan_relpath": plan_relpath,
            "plan_sha256_expected": plan_sha_expected,
            "plan_source_sha256_declared": plan_source_declared,
            "plan_source_sha256_seen_set": sorted(seen_set),
            "scan_config_sha256_counts": {
                str(k): int(v)
                for k, v in sorted(scan_config_counts.items(), key=lambda kv: str(kv[0]))
            },
            "scan_config_sha256_examples": {
                str(k): str(v)
                for k, v in sorted(scan_config_examples.items(), key=lambda kv: str(kv[0]))
            },
        }


def _enforce_plan_source_integrity(
    *,
    bundle: Path,
    bundle_kind: str,
    manifest_relpath: str,
    mode: str,
) -> Dict[str, Any]:
    if bundle_kind == "dir":
        context = _plan_source_context_from_dir(bundle_dir=bundle, manifest_relpath=manifest_relpath)
    elif bundle_kind == "zip":
        context = _plan_source_context_from_zip(bundle_path=bundle, manifest_member=manifest_relpath)
    elif bundle_kind == "tar":
        context = _plan_source_context_from_tar(bundle_path=bundle, manifest_member=manifest_relpath)
    else:
        raise ValueError(f"unsupported bundle kind for plan-source check: {bundle_kind!r}")

    requested = str(mode)
    seen_set = sorted(set(str(x) for x in list(context.get("plan_source_sha256_seen_set", [])) if str(x).strip()))
    expected = (
        str(context.get("plan_sha256_expected")).lower()
        if isinstance(context.get("plan_sha256_expected"), str) and str(context.get("plan_sha256_expected")).strip()
        else None
    )
    declared = (
        str(context.get("plan_source_sha256_declared"))
        if isinstance(context.get("plan_source_sha256_declared"), str)
        and str(context.get("plan_source_sha256_declared")).strip()
        else None
    )
    match_values: List[str] = []
    if expected:
        match_values.append(expected)
    if declared and declared not in match_values:
        match_values.append(declared)
    has_plan = bool(context.get("plan_relpath"))

    if requested == "off":
        applied = "off"
    elif requested == "consistent":
        applied = "consistent"
    elif requested == "match_plan":
        applied = "match_plan"
    elif requested == "auto":
        if has_plan and len(seen_set) > 0:
            applied = "match_plan"
        else:
            applied = "consistent"
    else:
        raise ValueError(f"unsupported --require-plan-source mode: {requested!r}")

    if applied == "consistent":
        if len(seen_set) > 1:
            raise VerificationFailure(
                "mixed plan_source_sha256 values detected",
                errors=[
                    {
                        "kind": "plan_source",
                        "path": str(manifest_relpath),
                        "detail": "mixed plan_source_sha256: " + ",".join(seen_set),
                    }
                ],
            )
    elif applied == "match_plan":
        if not has_plan:
            raise ValueError("--require-plan-source match_plan requires bundle to contain plan.json")
        if expected is None:
            raise VerificationFailure(
                "cannot verify match_plan: missing expected plan SHA256",
                errors=[
                    {
                        "kind": "plan_source",
                        "path": str(manifest_relpath),
                        "detail": "cannot verify match_plan without plan SHA256",
                    }
                ],
            )
        if len(seen_set) == 0:
            raise VerificationFailure(
                "cannot verify match_plan: no non-empty plan_source_sha256 values found",
                errors=[
                    {
                        "kind": "plan_source",
                        "path": str(manifest_relpath),
                        "detail": "no non-empty plan_source_sha256 values found",
                    }
                ],
            )
        if len(seen_set) > 1:
            raise VerificationFailure(
                "mixed plan_source_sha256 values detected",
                errors=[
                    {
                        "kind": "plan_source",
                        "path": str(manifest_relpath),
                        "detail": "mixed plan_source_sha256: " + ",".join(seen_set),
                    }
                ],
            )
        if seen_set[0] not in set(match_values):
            raise VerificationFailure(
                "plan_source_sha256 does not match plan.json SHA256",
                errors=[
                    {
                        "kind": "plan_source",
                        "path": str(manifest_relpath),
                        "detail": f"seen={seen_set[0]} expected_any={','.join(match_values)}",
                    }
                ],
            )
    elif applied != "off":
        raise ValueError(f"unsupported applied plan-source mode: {applied!r}")

    return {
        "policy_requested": requested,
        "policy_applied": applied,
        "plan_relpath": str(context.get("plan_relpath")) if context.get("plan_relpath") else None,
        "plan_sha256_expected": expected,
        "plan_source_sha256_declared": declared,
        "plan_source_sha256_match_values": match_values,
        "plan_source_sha256_seen_set": seen_set,
        "plan_source_sha256_chosen": seen_set[0] if len(seen_set) == 1 else "unknown",
    }


def _enforce_scan_config_integrity(
    *,
    bundle: Path,
    bundle_kind: str,
    manifest_relpath: str,
    require_present: bool,
) -> Dict[str, Any]:
    if bundle_kind == "dir":
        context = _plan_source_context_from_dir(bundle_dir=bundle, manifest_relpath=manifest_relpath)
    elif bundle_kind == "zip":
        context = _plan_source_context_from_zip(bundle_path=bundle, manifest_member=manifest_relpath)
    elif bundle_kind == "tar":
        context = _plan_source_context_from_tar(bundle_path=bundle, manifest_member=manifest_relpath)
    else:
        raise ValueError(f"unsupported bundle kind for scan-config check: {bundle_kind!r}")

    counts = {
        str(k): int(v)
        for k, v in dict(context.get("scan_config_sha256_counts", {})).items()
    }
    examples = {
        str(k): str(v)
        for k, v in dict(context.get("scan_config_sha256_examples", {})).items()
    }
    missing_count = int(counts.get("__MISSING__", 0))
    seen_set = sorted(str(k) for k in counts.keys() if str(k) != "__MISSING__" and str(k).strip())

    counts_text = ",".join(
        f"{('MISSING' if str(k) == '__MISSING__' else str(k))}:{int(v)}"
        for k, v in sorted(counts.items(), key=lambda kv: str(kv[0]))
        if int(v) > 0
    )
    examples_text = ",".join(
        f"{('MISSING' if str(k) == '__MISSING__' else str(k))}@{str(v)}"
        for k, v in sorted(examples.items(), key=lambda kv: str(kv[0]))
    )

    if len(seen_set) > 1:
        raise VerificationFailure(
            "mixed scan_config_sha256 values detected",
            errors=[
                {
                    "kind": "scan_config",
                    "path": str(manifest_relpath),
                    "detail": f"mixed scan_config_sha256: {','.join(seen_set)} counts={counts_text} examples={examples_text}",
                }
            ],
        )
    if len(seen_set) == 1 and missing_count > 0:
        raise VerificationFailure(
            "mixed scan_config_sha256 presence detected (some records missing field)",
            errors=[
                {
                    "kind": "scan_config",
                    "path": str(manifest_relpath),
                    "detail": f"scan_config_sha256 missing in subset; counts={counts_text} examples={examples_text}",
                }
            ],
        )
    if require_present and len(seen_set) == 0:
        raise VerificationFailure(
            "scan_config_sha256 missing in bundle JSONL records",
            errors=[
                {
                    "kind": "scan_config",
                    "path": str(manifest_relpath),
                    "detail": f"require-scan-config-sha=1 but no non-empty scan_config_sha256 found; counts={counts_text} examples={examples_text}",
                }
            ],
        )

    return {
        "required": bool(require_present),
        "scan_config_sha256_seen_set": seen_set,
        "scan_config_sha256_chosen": seen_set[0] if len(seen_set) == 1 else "unknown",
        "scan_config_sha256_missing_count": int(missing_count),
        "scan_config_sha256_counts": {
            str(k): int(v) for k, v in sorted(counts.items(), key=lambda kv: str(kv[0]))
        },
        "scan_config_sha256_examples": {
            str(k): str(v) for k, v in sorted(examples.items(), key=lambda kv: str(kv[0]))
        },
        "scan_config_sha256_mixed": bool(len(seen_set) > 1 or (len(seen_set) == 1 and missing_count > 0)),
        "scan_config_sha256_present": bool(len(seen_set) > 0),
    }


def _enforce_plan_coverage(
    *,
    bundle: Path,
    bundle_kind: str,
    manifest_relpath: str,
    mode: str,
) -> Dict[str, Any]:
    if mode == "none":
        return {}

    if bundle_kind == "dir":
        coverage = _coverage_from_dir(bundle_dir=bundle, manifest_relpath=manifest_relpath)
    elif bundle_kind == "zip":
        coverage = _coverage_from_zip(bundle_path=bundle, manifest_member=manifest_relpath)
    elif bundle_kind == "tar":
        coverage = _coverage_from_tar(bundle_path=bundle, manifest_member=manifest_relpath)
    else:
        raise ValueError(f"unsupported bundle kind for plan coverage: {bundle_kind!r}")

    counts = coverage.get("counts", {})
    n_missing = int(counts.get("n_missing", 0))
    n_failed = int(counts.get("n_failed", 0))
    if mode == "complete":
        if n_missing > 0:
            raise VerificationFailure(
                f"plan coverage incomplete: missing={n_missing}, failed={n_failed}",
                errors=[
                    {
                        "kind": "coverage",
                        "path": str(coverage.get("jsonl_path", "")),
                        "detail": f"complete requires no missing points (missing={n_missing}, failed={n_failed})",
                    }
                ],
            )
    elif mode == "ok":
        if n_missing > 0 or n_failed > 0:
            raise VerificationFailure(
                f"plan coverage requires ok results: missing={n_missing}, failed={n_failed}",
                errors=[
                    {
                        "kind": "coverage",
                        "path": str(coverage.get("jsonl_path", "")),
                        "detail": f"ok requires no missing/failed points (missing={n_missing}, failed={n_failed})",
                    }
                ],
            )
    else:
        raise ValueError(f"unsupported --plan-coverage mode: {mode!r}")

    return coverage


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _print_failure(errors: Sequence[Mapping[str, Any]]) -> None:
    if not errors:
        return
    for err in list(errors)[:MAX_PRINT_ERRORS]:
        kind = str(err.get("kind", "error"))
        path = str(err.get("path", ""))
        detail = str(err.get("detail", ""))
        if path:
            print(f"FAIL: {kind}: {path} ({detail})")
        else:
            print(f"FAIL: {kind}: {detail}")
    if len(errors) > MAX_PRINT_ERRORS:
        print(f"FAIL: ... {len(errors) - MAX_PRINT_ERRORS} more errors omitted ...")


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="phase2_e2_verify_bundle",
        description="Offline integrity verifier for Phase-2 E2 bundles (manifest + SHA256).",
    )
    ap.add_argument("--bundle", required=True, type=Path, help="Bundle archive (.zip/.tar/.tar.gz/.tgz) or unpacked bundle directory.")
    ap.add_argument("--manifest-relpath", type=str, default="", help="Optional manifest relative path inside bundle.")
    ap.add_argument(
        "--strict-extras",
        type=int,
        choices=[0, 1],
        default=0,
        help="If 1, fail when bundle contains files not listed in manifest (default: 0).",
    )
    ap.add_argument(
        "--plan-coverage",
        choices=["none", "complete", "ok"],
        default="none",
        help="Optional plan coverage enforcement for bundles containing refine plan + JSONL results.",
    )
    ap.add_argument(
        "--require-plan-source",
        choices=["auto", "off", "consistent", "match_plan"],
        default="auto",
        help=(
            "Optional plan_source_sha256 integrity enforcement. "
            "auto: match_plan when plan+source are present, else consistent."
        ),
    )
    ap.add_argument(
        "--require-scan-config-sha",
        type=int,
        choices=[0, 1],
        default=0,
        help=(
            "If 1, fail when bundle JSONL records do not contain a non-empty "
            "single scan_config_sha256 value."
        ),
    )
    ap.add_argument(
        "--paper-assets",
        choices=["ignore", "require"],
        default="ignore",
        help="Optional paper-assets verification using paper_assets_manifest.json.",
    )
    ap.add_argument(
        "--validate-schemas",
        action="store_true",
        help="Validate key JSON artifacts using phase2_schema_validate.py --auto.",
    )
    ap.add_argument(
        "--lint-portable-content",
        action="store_true",
        help="Run content-level absolute-path lint on JSON/JSONL artifacts.",
    )
    ap.add_argument(
        "--extract-paper-assets",
        action="store_true",
        help="Extract paper-assets directories from bundle after successful verification.",
    )
    ap.add_argument(
        "--extract-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Destination root used with --extract-paper-assets (default: repo root).",
    )
    ap.add_argument(
        "--extract-prefix",
        action="append",
        default=[],
        help=(
            "Allowed relative prefix for extraction (repeatable). "
            "Default allowlist is the two Phase-2 paper_assets_cmb_e2_* directories."
        ),
    )
    ap.add_argument(
        "--extract-mode",
        choices=["overwrite", "clean_overwrite"],
        default="clean_overwrite",
        help="Extraction behavior when --extract-paper-assets is enabled (default: clean_overwrite).",
    )
    ap.add_argument("--json-out", type=Path, default=None, help="Optional JSON verify report output path.")
    ap.add_argument("--verbose", action="store_true", help="Print per-file verification lines.")

    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 1

    bundle = args.bundle.expanduser().resolve()
    manifest_relpath = str(args.manifest_relpath or "").strip() or None
    strict_extras = bool(int(args.strict_extras))
    extract_root = args.extract_root.expanduser().resolve()

    try:
        report = _verify_bundle(
            bundle,
            manifest_relpath=manifest_relpath,
            strict_extras=strict_extras,
            verbose=bool(args.verbose),
        )
        if bool(report.get("ok", False)):
            plan_source_integrity = _enforce_plan_source_integrity(
                bundle=bundle,
                bundle_kind=str(report.get("bundle_kind", "unknown")),
                manifest_relpath=str(report.get("manifest_relpath", "")),
                mode=str(args.require_plan_source),
            )
            report["plan_source_integrity"] = plan_source_integrity
        if bool(report.get("ok", False)):
            scan_config_integrity = _enforce_scan_config_integrity(
                bundle=bundle,
                bundle_kind=str(report.get("bundle_kind", "unknown")),
                manifest_relpath=str(report.get("manifest_relpath", "")),
                require_present=bool(int(args.require_scan_config_sha)),
            )
            report["scan_config_integrity"] = scan_config_integrity
        if bool(report.get("ok", False)) and str(args.paper_assets) != "ignore":
            paper_assets = _enforce_paper_assets(
                bundle=bundle,
                bundle_kind=str(report.get("bundle_kind", "unknown")),
                mode=str(args.paper_assets),
            )
            report["paper_assets"] = paper_assets
        if bool(report.get("ok", False)) and bool(args.validate_schemas):
            schema_validation = _validate_bundle_schemas(
                bundle=bundle,
                bundle_kind=str(report.get("bundle_kind", "unknown")),
                manifest_relpath=str(report.get("manifest_relpath", "")),
            )
            report["schema_validation"] = schema_validation
        if bool(report.get("ok", False)) and bool(args.lint_portable_content):
            portable_content = _lint_portable_content(bundle=bundle)
            report["portable_content_lint"] = portable_content
        if bool(report.get("ok", False)) and str(args.plan_coverage) != "none":
            coverage = _enforce_plan_coverage(
                bundle=bundle,
                bundle_kind=str(report.get("bundle_kind", "unknown")),
                manifest_relpath=str(report.get("manifest_relpath", "")),
                mode=str(args.plan_coverage),
            )
            report["plan_coverage"] = coverage
        if bool(report.get("ok", False)) and bool(args.extract_paper_assets):
            extract_result = _extract_paper_assets(
                bundle=bundle,
                bundle_kind=str(report.get("bundle_kind", "unknown")),
                manifest_relpath=str(report.get("manifest_relpath", "")),
                extract_root=extract_root,
                extract_prefixes=[str(x) for x in list(args.extract_prefix)],
                extract_mode=str(args.extract_mode),
            )
            report["paper_assets_extract"] = extract_result
        report = {
            "ok": bool(report.get("ok", False)),
            "bundle": str(bundle),
            "bundle_kind": str(report.get("bundle_kind", "unknown")),
            "manifest_relpath": str(report.get("manifest_relpath", "")),
            "schema_id": str(report.get("schema_id", "UNKNOWN")),
            "n_files_manifest": int(report.get("n_files_manifest", 0)),
            "n_verified": int(report.get("n_verified", 0)),
            "n_missing": int(report.get("n_missing", 0)),
            "n_mismatch": int(report.get("n_mismatch", 0)),
            "n_extras": int(report.get("n_extras", 0)),
            "errors": list(report.get("errors", []))[:MAX_JSON_ERRORS],
            "plan_source_policy_requested": str(args.require_plan_source),
            "plan_source_policy_applied": str(
                _to_json_safe((report.get("plan_source_integrity") or {}).get("policy_applied", "off"))
            ),
            "plan_sha256_expected": _to_json_safe(
                (report.get("plan_source_integrity") or {}).get("plan_sha256_expected")
            ),
            "plan_source_sha256_declared": _to_json_safe(
                (report.get("plan_source_integrity") or {}).get("plan_source_sha256_declared")
            ),
            "plan_source_sha256_match_values": _to_json_safe(
                (report.get("plan_source_integrity") or {}).get("plan_source_sha256_match_values", [])
            ),
            "plan_source_sha256_seen_set": _to_json_safe(
                (report.get("plan_source_integrity") or {}).get("plan_source_sha256_seen_set", [])
            ),
            "plan_source_sha256_chosen": _to_json_safe(
                (report.get("plan_source_integrity") or {}).get("plan_source_sha256_chosen", "unknown")
            ),
            "require_scan_config_sha": bool(int(args.require_scan_config_sha)),
            "scan_config_sha256_seen_set": _to_json_safe(
                (report.get("scan_config_integrity") or {}).get("scan_config_sha256_seen_set", [])
            ),
            "scan_config_sha256_chosen": _to_json_safe(
                (report.get("scan_config_integrity") or {}).get("scan_config_sha256_chosen", "unknown")
            ),
            "scan_config_sha256_missing_count": int(
                (report.get("scan_config_integrity") or {}).get("scan_config_sha256_missing_count", 0)
            ),
            "scan_config_sha256_counts": _to_json_safe(
                (report.get("scan_config_integrity") or {}).get("scan_config_sha256_counts", {})
            ),
            "scan_config_sha256_examples": _to_json_safe(
                (report.get("scan_config_integrity") or {}).get("scan_config_sha256_examples", {})
            ),
            "scan_config_sha256_mixed": bool(
                (report.get("scan_config_integrity") or {}).get("scan_config_sha256_mixed", False)
            ),
            "scan_config_sha256_present": bool(
                (report.get("scan_config_integrity") or {}).get("scan_config_sha256_present", False)
            ),
            "scan_config_integrity": _to_json_safe(report.get("scan_config_integrity")),
            "plan_source_integrity": _to_json_safe(report.get("plan_source_integrity")),
            "plan_coverage_mode": str(args.plan_coverage),
            "plan_coverage": _to_json_safe(report.get("plan_coverage")),
            "paper_assets_mode": str(args.paper_assets),
            "paper_assets": _to_json_safe(report.get("paper_assets")),
            "validate_schemas": bool(args.validate_schemas),
            "schema_validation": _to_json_safe(report.get("schema_validation")),
            "lint_portable_content": bool(args.lint_portable_content),
            "portable_content_lint": _to_json_safe(report.get("portable_content_lint")),
            "extract_paper_assets": bool(args.extract_paper_assets),
            "extract_root": str(extract_root),
            "extract_mode": str(args.extract_mode),
            "extract_prefixes": [str(x) for x in (list(args.extract_prefix) or list(DEFAULT_EXTRACT_PREFIXES))],
            "paper_assets_extract": _to_json_safe(report.get("paper_assets_extract")),
        }
    except ValueError as exc:
        report = {
            "ok": False,
            "bundle": str(bundle),
            "bundle_kind": "unknown",
            "manifest_relpath": "",
            "schema_id": "UNKNOWN",
            "n_files_manifest": 0,
            "n_verified": 0,
            "n_missing": 0,
            "n_mismatch": 0,
            "n_extras": 0,
            "errors": [{"kind": "runtime", "path": "", "detail": str(exc)}],
            "plan_source_policy_requested": str(args.require_plan_source),
            "plan_source_policy_applied": "off",
            "plan_sha256_expected": None,
            "plan_source_sha256_declared": None,
            "plan_source_sha256_match_values": [],
            "plan_source_sha256_seen_set": [],
            "plan_source_sha256_chosen": "unknown",
            "require_scan_config_sha": bool(int(args.require_scan_config_sha)),
            "scan_config_sha256_seen_set": [],
            "scan_config_sha256_chosen": "unknown",
            "scan_config_sha256_missing_count": 0,
            "scan_config_sha256_counts": {},
            "scan_config_sha256_examples": {},
            "scan_config_sha256_mixed": False,
            "scan_config_sha256_present": False,
            "scan_config_integrity": None,
            "plan_source_integrity": None,
            "plan_coverage_mode": str(args.plan_coverage),
            "plan_coverage": None,
            "paper_assets_mode": str(args.paper_assets),
            "paper_assets": None,
            "validate_schemas": bool(args.validate_schemas),
            "schema_validation": None,
            "lint_portable_content": bool(args.lint_portable_content),
            "portable_content_lint": None,
            "extract_paper_assets": bool(args.extract_paper_assets),
            "extract_root": str(extract_root),
            "extract_mode": str(args.extract_mode),
            "extract_prefixes": [str(x) for x in (list(args.extract_prefix) or list(DEFAULT_EXTRACT_PREFIXES))],
            "paper_assets_extract": None,
        }
        if args.json_out is not None:
            _write_json(args.json_out.expanduser().resolve(), report)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except VerificationFailure as exc:
        report = {
            "ok": False,
            "bundle": str(bundle),
            "bundle_kind": "unknown",
            "manifest_relpath": "",
            "schema_id": "UNKNOWN",
            "n_files_manifest": 0,
            "n_verified": 0,
            "n_missing": 0,
            "n_mismatch": 0,
            "n_extras": 0,
            "errors": [{"kind": "schema", "path": "", "detail": str(exc)}],
            "plan_source_policy_requested": str(args.require_plan_source),
            "plan_source_policy_applied": "off",
            "plan_sha256_expected": None,
            "plan_source_sha256_declared": None,
            "plan_source_sha256_match_values": [],
            "plan_source_sha256_seen_set": [],
            "plan_source_sha256_chosen": "unknown",
            "require_scan_config_sha": bool(int(args.require_scan_config_sha)),
            "scan_config_sha256_seen_set": [],
            "scan_config_sha256_chosen": "unknown",
            "scan_config_sha256_missing_count": 0,
            "scan_config_sha256_counts": {},
            "scan_config_sha256_examples": {},
            "scan_config_sha256_mixed": False,
            "scan_config_sha256_present": False,
            "scan_config_integrity": None,
            "plan_source_integrity": None,
            "plan_coverage_mode": str(args.plan_coverage),
            "plan_coverage": None,
            "paper_assets_mode": str(args.paper_assets),
            "paper_assets": None,
            "validate_schemas": bool(args.validate_schemas),
            "schema_validation": None,
            "lint_portable_content": bool(args.lint_portable_content),
            "portable_content_lint": None,
            "extract_paper_assets": bool(args.extract_paper_assets),
            "extract_root": str(extract_root),
            "extract_mode": str(args.extract_mode),
            "extract_prefixes": [str(x) for x in (list(args.extract_prefix) or list(DEFAULT_EXTRACT_PREFIXES))],
            "paper_assets_extract": None,
        }
        if exc.errors:
            report["errors"] = [dict(e) for e in exc.errors][:MAX_JSON_ERRORS]
    except Exception as exc:
        report = {
            "ok": False,
            "bundle": str(bundle),
            "bundle_kind": "unknown",
            "manifest_relpath": "",
            "schema_id": "UNKNOWN",
            "n_files_manifest": 0,
            "n_verified": 0,
            "n_missing": 0,
            "n_mismatch": 0,
            "n_extras": 0,
            "errors": [{"kind": "runtime", "path": "", "detail": str(exc)}],
            "plan_source_policy_requested": str(args.require_plan_source),
            "plan_source_policy_applied": "off",
            "plan_sha256_expected": None,
            "plan_source_sha256_declared": None,
            "plan_source_sha256_match_values": [],
            "plan_source_sha256_seen_set": [],
            "plan_source_sha256_chosen": "unknown",
            "require_scan_config_sha": bool(int(args.require_scan_config_sha)),
            "scan_config_sha256_seen_set": [],
            "scan_config_sha256_chosen": "unknown",
            "scan_config_sha256_missing_count": 0,
            "scan_config_sha256_counts": {},
            "scan_config_sha256_examples": {},
            "scan_config_sha256_mixed": False,
            "scan_config_sha256_present": False,
            "scan_config_integrity": None,
            "plan_source_integrity": None,
            "plan_coverage_mode": str(args.plan_coverage),
            "plan_coverage": None,
            "paper_assets_mode": str(args.paper_assets),
            "paper_assets": None,
            "validate_schemas": bool(args.validate_schemas),
            "schema_validation": None,
            "lint_portable_content": bool(args.lint_portable_content),
            "portable_content_lint": None,
            "extract_paper_assets": bool(args.extract_paper_assets),
            "extract_root": str(extract_root),
            "extract_mode": str(args.extract_mode),
            "extract_prefixes": [str(x) for x in (list(args.extract_prefix) or list(DEFAULT_EXTRACT_PREFIXES))],
            "paper_assets_extract": None,
        }
        if args.json_out is not None:
            _write_json(args.json_out.expanduser().resolve(), report)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json_out is not None:
        _write_json(args.json_out.expanduser().resolve(), report)

    if report["ok"]:
        extras_mode = "strict" if strict_extras else "ignored"
        print(
            f"OK: verified {report['n_verified']} files "
            f"(schema={report['schema_id']}, extras={extras_mode})"
        )
        print(
            "OK: plan source integrity "
            f"(requested={report.get('plan_source_policy_requested', 'auto')}, "
            f"applied={report.get('plan_source_policy_applied', 'off')}, "
            f"seen={report.get('plan_source_sha256_seen_set', [])}, "
            f"expected={report.get('plan_sha256_expected', None)})"
        )
        print(
            "OK: scan config integrity "
            f"(required={bool(report.get('require_scan_config_sha', False))}, "
            f"seen={report.get('scan_config_sha256_seen_set', [])}, "
            f"missing={int(report.get('scan_config_sha256_missing_count', 0))}, "
            f"mixed={bool(report.get('scan_config_sha256_mixed', False))})"
        )
        if str(args.paper_assets) != "ignore":
            pa = report.get("paper_assets") or {}
            if isinstance(pa, Mapping):
                print(
                    "OK: paper assets "
                    f"(files={int(pa.get('n_files', 0))}, snippets={int(pa.get('n_snippets', 0))})"
                )
        if str(args.plan_coverage) != "none":
            cov = report.get("plan_coverage") or {}
            counts = cov.get("counts") if isinstance(cov, Mapping) else {}
            if isinstance(counts, Mapping):
                print(
                    "OK: plan coverage "
                    f"(missing={int(counts.get('n_missing', 0))}, failed={int(counts.get('n_failed', 0))})"
                )
        if bool(args.validate_schemas):
            schema_validation = report.get("schema_validation") or {}
            if isinstance(schema_validation, Mapping):
                print(
                    "OK: schema validation "
                    f"(n_checked={int(schema_validation.get('n_checked', 0))})"
                )
        if bool(args.lint_portable_content):
            portable = report.get("portable_content_lint") or {}
            if isinstance(portable, Mapping):
                print(
                    "OK: portable-content lint "
                    f"(offending={int(portable.get('offending_file_count', 0))})"
                )
        if bool(args.extract_paper_assets):
            extract = report.get("paper_assets_extract") or {}
            if isinstance(extract, Mapping):
                print(
                    "OK: extracted paper assets "
                    f"(files={int(extract.get('n_extracted', 0))}, root={extract.get('extract_root', '')})"
                )
        return 0

    _print_failure(report.get("errors", []))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

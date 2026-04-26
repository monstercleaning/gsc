#!/usr/bin/env python3
"""Deterministic merge for Phase-2 E2 scan JSONL shards (stdlib-only)."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import glob
import heapq
import hashlib
import json
import math
import shutil
from pathlib import Path
import sys
import tempfile
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple


V101_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V101_DIR))

from gsc.jsonl_io import open_text_auto  # noqa: E402


class PlanSourcePolicyFailure(Exception):
    """Raised for plan-source policy violations (exit code 2)."""

    def __init__(self, message: str) -> None:
        super().__init__(str(message))


class ScanConfigPolicyFailure(Exception):
    """Raised for scan-config policy violations (exit code 2)."""

    def __init__(self, message: str) -> None:
        super().__init__(str(message))


def _finite_float(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except Exception:
        return None
    if not math.isfinite(out):
        return None
    return float(out)


def _canonical_json_text(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _list_jsonl_files_in_dir(path: Path) -> List[Path]:
    files: List[Path] = []
    seen: Set[Path] = set()
    for candidate in list(path.glob("*.jsonl")) + list(path.glob("*.jsonl.gz")):
        resolved = candidate.resolve()
        if resolved in seen or not resolved.is_file():
            continue
        seen.add(resolved)
        files.append(resolved)
    return sorted(files, key=lambda p: str(p))


def _resolve_input_paths(tokens: Sequence[str]) -> List[Path]:
    resolved: List[Path] = []
    seen: Set[Path] = set()

    def _add_path(path: Path, *, dedupe: bool) -> None:
        rp = path.expanduser().resolve()
        if not rp.exists():
            raise SystemExit(f"Input JSONL path not found: {path}")
        if rp.is_file():
            if bool(dedupe):
                if rp in seen:
                    return
                seen.add(rp)
            resolved.append(rp)
            return
        if rp.is_dir():
            for file_path in _list_jsonl_files_in_dir(rp):
                if bool(dedupe):
                    if file_path in seen:
                        continue
                    seen.add(file_path)
                resolved.append(file_path)
            return
        raise SystemExit(f"Input path must be a file, directory, or glob: {path}")

    for raw in tokens:
        token = str(raw).strip()
        if not token:
            continue
        if any(ch in token for ch in "*?["):
            matches = sorted(glob.glob(token))
            if not matches:
                raise SystemExit(f"Input glob did not match any paths: {token}")
            for match in matches:
                _add_path(Path(match), dedupe=True)
            continue
        explicit_path = Path(token).expanduser().resolve()
        _add_path(Path(token), dedupe=bool(explicit_path.exists() and explicit_path.is_dir()))
    return resolved


def _extract_declared_plan_source_sha256(plan_path: Path) -> Optional[str]:
    try:
        payload = json.loads(plan_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, Mapping):
        return None
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


def _canonical_params(params: Mapping[str, Any]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for key in sorted(str(k) for k in params.keys()):
        fv = _finite_float(params.get(key))
        if fv is not None:
            out[str(key)] = float(fv)
    return out


def _hash_from_params(params: Mapping[str, Any]) -> Optional[str]:
    canonical = _canonical_params(params)
    if not canonical:
        return None
    return _sha256_text(_canonical_json_text(canonical))


def _is_data_record(payload: Mapping[str, Any]) -> bool:
    probe_keys = {
        "params_hash",
        "params",
        "status",
        "chi2_total",
        "chi2",
        "plan_point_id",
        "model",
    }
    return any(k in payload for k in probe_keys)


def _strip_execution_fields(payload: Mapping[str, Any], *, canonicalize: bool) -> Dict[str, Any]:
    out = {str(k): payload[k] for k in payload.keys()}
    if canonicalize:
        out.pop("plan_slice_i", None)
        out.pop("plan_slice_n", None)
    return out


def _plan_identity(payload: Mapping[str, Any]) -> Optional[Tuple[str, str]]:
    point_id = payload.get("plan_point_id")
    source_sha = payload.get("plan_source_sha256")
    if not isinstance(point_id, str) or not point_id.strip():
        return None
    if not isinstance(source_sha, str) or not source_sha.strip():
        return None
    return (source_sha.strip(), point_id.strip())


def _record_plan_source_sha(payload: Mapping[str, Any]) -> Optional[str]:
    raw = payload.get("plan_source_sha256")
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    return text if text else None


def _record_scan_config_sha(payload: Mapping[str, Any]) -> Optional[str]:
    raw = payload.get("scan_config_sha256")
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    return text if text else None


def _scan_config_key(value: Optional[str]) -> str:
    return value if isinstance(value, str) and value.strip() else "__MISSING__"


def _format_scan_config_counts(counts: Mapping[str, int]) -> str:
    ordered = sorted(
        ((str(k), int(v)) for k, v in counts.items() if int(v) > 0),
        key=lambda kv: (str(kv[0]) != "__MISSING__", str(kv[0])),
    )
    parts: List[str] = []
    for key, value in ordered:
        label = "MISSING" if key == "__MISSING__" else key
        parts.append(f"{label}:{int(value)}")
    return ",".join(parts)


def _format_scan_config_examples(examples: Mapping[str, str]) -> str:
    ordered = sorted((str(k), str(v)) for k, v in examples.items())
    parts: List[str] = []
    for key, value in ordered:
        label = "MISSING" if key == "__MISSING__" else key
        parts.append(f"{label}@{value}")
    return ",".join(parts)


def _enforce_scan_config_policy(
    *,
    policy: str,
    counts: Mapping[str, int],
    examples: Mapping[str, str],
) -> Dict[str, Any]:
    missing_count = int(counts.get("__MISSING__", 0))
    seen_set = sorted(str(k) for k in counts.keys() if str(k) != "__MISSING__" and str(k).strip())
    chosen = seen_set[0] if len(seen_set) == 1 else "unknown"
    counts_text = _format_scan_config_counts(counts)
    examples_text = _format_scan_config_examples(examples)

    if policy == "ignore":
        return {
            "policy": policy,
            "seen_set": seen_set,
            "chosen": chosen if chosen != "unknown" else None,
            "missing_count": int(missing_count),
            "counts": {str(k): int(v) for k, v in sorted(counts.items(), key=lambda kv: str(kv[0]))},
            "examples": {str(k): str(v) for k, v in sorted(examples.items(), key=lambda kv: str(kv[0]))},
        }

    if policy == "auto":
        if len(seen_set) == 0 and missing_count > 0:
            return {
                "policy": policy,
                "seen_set": seen_set,
                "chosen": None,
                "missing_count": int(missing_count),
                "counts": {str(k): int(v) for k, v in sorted(counts.items(), key=lambda kv: str(kv[0]))},
                "examples": {str(k): str(v) for k, v in sorted(examples.items(), key=lambda kv: str(kv[0]))},
            }
        if len(seen_set) > 1:
            raise ScanConfigPolicyFailure(
                "ERROR: mixed scan_config_sha256 (policy=auto): "
                + ",".join(seen_set)
                + f" counts={counts_text} examples={examples_text}"
            )
        if len(seen_set) == 1 and missing_count > 0:
            raise ScanConfigPolicyFailure(
                "ERROR: mixed scan_config_sha256 presence (policy=auto): "
                f"counts={counts_text} examples={examples_text}"
            )
        return {
            "policy": policy,
            "seen_set": seen_set,
            "chosen": seen_set[0] if len(seen_set) == 1 else None,
            "missing_count": int(missing_count),
            "counts": {str(k): int(v) for k, v in sorted(counts.items(), key=lambda kv: str(kv[0]))},
            "examples": {str(k): str(v) for k, v in sorted(examples.items(), key=lambda kv: str(kv[0]))},
        }

    if policy == "require":
        if len(seen_set) == 0:
            raise ScanConfigPolicyFailure(
                "ERROR: scan_config_sha256 missing in all records (policy=require): "
                f"counts={counts_text} examples={examples_text}"
            )
        if len(seen_set) > 1:
            raise ScanConfigPolicyFailure(
                "ERROR: mixed scan_config_sha256 (policy=require): "
                + ",".join(seen_set)
                + f" counts={counts_text} examples={examples_text}"
            )
        if missing_count > 0:
            raise ScanConfigPolicyFailure(
                "ERROR: missing scan_config_sha256 in subset of records (policy=require): "
                f"counts={counts_text} examples={examples_text}"
            )
        return {
            "policy": policy,
            "seen_set": seen_set,
            "chosen": seen_set[0],
            "missing_count": int(missing_count),
            "counts": {str(k): int(v) for k, v in sorted(counts.items(), key=lambda kv: str(kv[0]))},
            "examples": {str(k): str(v) for k, v in sorted(examples.items(), key=lambda kv: str(kv[0]))},
        }

    raise ValueError(f"unsupported --scan-config-sha-policy mode: {policy!r}")


def _enforce_plan_source_policy(
    *,
    policy: str,
    seen_set: Set[str],
    plan_sha256_expected: Optional[str],
    plan_source_declared: Optional[str],
) -> Dict[str, Any]:
    seen_sorted = sorted(str(x) for x in seen_set if str(x).strip())
    chosen = seen_sorted[0] if len(seen_sorted) == 1 else "unknown"
    expected = str(plan_sha256_expected) if plan_sha256_expected else None
    declared = str(plan_source_declared) if plan_source_declared else None
    match_values: List[str] = []
    if expected:
        match_values.append(expected)
    if declared and declared not in match_values:
        match_values.append(declared)

    if policy == "ignore":
        return {
            "policy": policy,
            "seen_set": seen_sorted,
            "chosen": chosen if chosen != "unknown" else None,
            "expected": expected,
            "declared": declared,
            "match_values": match_values,
        }

    if policy == "consistent":
        if len(seen_sorted) > 1:
            raise PlanSourcePolicyFailure(
                "ERROR: mixed plan_source_sha256 (policy=consistent): "
                + ",".join(seen_sorted)
            )
        return {
            "policy": policy,
            "seen_set": seen_sorted,
            "chosen": chosen if chosen != "unknown" else None,
            "expected": expected,
            "declared": declared,
            "match_values": match_values,
        }

    if policy == "match_plan":
        if expected is None:
            raise ValueError("--plan-source-policy match_plan requires --plan")
        if len(seen_sorted) == 0:
            raise PlanSourcePolicyFailure(
                "ERROR: cannot verify match_plan: no non-empty plan_source_sha256 values found"
            )
        if len(seen_sorted) > 1:
            raise PlanSourcePolicyFailure(
                "ERROR: mixed plan_source_sha256 (policy=match_plan): "
                + ",".join(seen_sorted)
            )
        if seen_sorted[0] not in set(match_values):
            raise PlanSourcePolicyFailure(
                "ERROR: plan_source_sha256 does not match --plan SHA256: "
                f"seen={seen_sorted[0]} expected_any={','.join(match_values)}"
            )
        return {
            "policy": policy,
            "seen_set": seen_sorted,
            "chosen": seen_sorted[0],
            "expected": expected,
            "declared": declared,
            "match_values": match_values,
        }

    raise ValueError(f"unsupported --plan-source-policy mode: {policy!r}")


def _params_hash(payload: Mapping[str, Any]) -> Tuple[str, str]:
    raw = payload.get("params_hash")
    if isinstance(raw, str) and raw.strip():
        return raw.strip(), "record"
    params = payload.get("params")
    if isinstance(params, Mapping):
        from_params = _hash_from_params(params)
        if from_params:
            return from_params, "params"
    return _sha256_text(_canonical_json_text(payload)), "record_fallback"


def _status_rank(payload: Mapping[str, Any]) -> int:
    status = str(payload.get("status", "ok")).strip().lower()
    if status in {"", "ok"}:
        return 0
    if status == "skipped_drift":
        return 1
    if status == "error":
        return 3
    return 2


def _chi2_value(payload: Mapping[str, Any]) -> float:
    chi2 = _finite_float(payload.get("chi2_total"))
    if chi2 is None:
        chi2 = _finite_float(payload.get("chi2"))
    if chi2 is None:
        return float("inf")
    return float(chi2)


def _selection_score(
    payload: Mapping[str, Any],
    *,
    prefer: str,
    source_rank: int,
    source_line: int,
) -> Tuple[Any, ...]:
    canonical = _canonical_json_text(payload)
    if prefer == "first":
        return (int(source_rank), int(source_line), canonical)
    if prefer == "ok_then_first":
        return (_status_rank(payload), int(source_rank), int(source_line), canonical)
    if prefer == "ok_then_lowest_chi2":
        return (
            _status_rank(payload),
            _chi2_value(payload),
            canonical,
            int(source_rank),
            int(source_line),
        )
    raise ValueError(f"unsupported --prefer policy: {prefer}")


def _record_key(
    *,
    payload: Mapping[str, Any],
    dedupe_key: str,
) -> Tuple[Tuple[str, ...], str]:
    plan_identity = _plan_identity(payload)
    if dedupe_key == "plan_point_id":
        if plan_identity is None:
            raise ValueError(
                "merge dedupe-key=plan_point_id requires plan_point_id and plan_source_sha256 in all records"
            )
        source_sha, point_id = plan_identity
        return ("plan", source_sha, point_id), "record"
    if dedupe_key == "params_hash":
        params_hash, hash_source = _params_hash(payload)
        return ("params", params_hash), hash_source
    if dedupe_key == "auto":
        if plan_identity is not None:
            source_sha, point_id = plan_identity
            return ("plan", source_sha, point_id), "record"
        params_hash, hash_source = _params_hash(payload)
        return ("params", params_hash), hash_source
    raise ValueError(f"unsupported --dedupe-key mode: {dedupe_key!r}")


def _serialize_key_tuple(key: Tuple[str, ...]) -> str:
    return json.dumps([str(part) for part in key], sort_keys=False, separators=(",", ":"), ensure_ascii=True)


def _parse_key_tuple(text: str) -> Tuple[str, ...]:
    parsed = json.loads(text)
    if not isinstance(parsed, list):
        raise ValueError("invalid external-sort key payload (expected JSON list)")
    out: List[str] = []
    for item in parsed:
        out.append(str(item))
    return tuple(out)


def _flush_external_chunk(
    *,
    entries: Sequence[Tuple[Tuple[str, ...], int, int, str]],
    chunk_dir: Path,
    chunk_index: int,
) -> Path:
    ordered = sorted(
        entries,
        key=lambda item: (
            tuple(str(part) for part in item[0]),
            int(item[1]),
            int(item[2]),
            str(item[3]),
        ),
    )
    path = chunk_dir / f"chunk_{int(chunk_index):06d}.tsv"
    with path.open("w", encoding="utf-8") as fh:
        for record_key, source_rank, source_line, canonical in ordered:
            fh.write(
                _serialize_key_tuple(tuple(str(part) for part in record_key))
                + "\t"
                + str(int(source_rank))
                + "\t"
                + str(int(source_line))
                + "\t"
                + str(canonical)
                + "\n"
            )
    return path


def _read_external_chunk_row(line: str) -> Tuple[Tuple[str, ...], int, int, str, Dict[str, Any]]:
    parts = line.rstrip("\n").split("\t", 3)
    if len(parts) != 4:
        raise ValueError("invalid external-sort chunk row format")
    record_key = _parse_key_tuple(parts[0])
    source_rank = int(parts[1])
    source_line = int(parts[2])
    canonical = str(parts[3])
    payload = json.loads(canonical)
    if not isinstance(payload, Mapping):
        raise ValueError("invalid external-sort chunk row payload (expected JSON object)")
    return record_key, int(source_rank), int(source_line), canonical, dict(payload)


def _build_external_chunks(
    *,
    inputs: Sequence[Path],
    prefer: str,
    canonicalize: bool,
    dedupe_key: str,
    chunk_records: int,
    chunk_dir: Path,
    progress_every: int,
) -> Tuple[List[Path], Dict[str, Any]]:
    del prefer  # selection is applied in the k-way merge stage
    chunk_limit = max(1, int(chunk_records))
    chunk_dir.mkdir(parents=True, exist_ok=True)

    chunk_entries: List[Tuple[Tuple[str, ...], int, int, str]] = []
    chunk_paths: List[Path] = []

    plan_source_by_id: Dict[str, str] = {}
    plan_source_sha_seen: Set[str] = set()
    scan_config_counts: Dict[str, int] = {}
    scan_config_examples: Dict[str, str] = {}

    n_lines_read_total = 0
    n_skipped_blank = 0
    n_skipped_comment = 0
    n_skipped_invalid_json = 0
    n_skipped_non_object = 0
    n_skipped_header_like = 0
    n_fallback_hash = 0
    n_plan_source_conflicts = 0
    n_valid_records = 0

    for source_rank, path in enumerate(inputs):
        with open_text_auto(path, "r") as fh:
            for line_idx, line in enumerate(fh, start=1):
                n_lines_read_total += 1
                text = line.strip()
                if not text:
                    n_skipped_blank += 1
                    continue
                if text.startswith("#"):
                    n_skipped_comment += 1
                    continue
                try:
                    parsed = json.loads(text)
                except Exception:
                    n_skipped_invalid_json += 1
                    continue
                if not isinstance(parsed, Mapping):
                    n_skipped_non_object += 1
                    continue
                if not _is_data_record(parsed):
                    n_skipped_header_like += 1
                    continue

                payload = _strip_execution_fields(parsed, canonicalize=canonicalize)
                row_source_sha = _record_plan_source_sha(payload)
                if row_source_sha is not None:
                    plan_source_sha_seen.add(row_source_sha)
                row_scan_config_sha = _record_scan_config_sha(payload)
                scan_config_key = _scan_config_key(row_scan_config_sha)
                scan_config_counts[scan_config_key] = int(scan_config_counts.get(scan_config_key, 0) + 1)
                if scan_config_key not in scan_config_examples:
                    scan_config_examples[scan_config_key] = f"{path}:{line_idx}"
                plan_identity = _plan_identity(payload)
                if plan_identity is not None:
                    source_sha, point_id = plan_identity
                    known_source = plan_source_by_id.get(point_id)
                    if known_source is None:
                        plan_source_by_id[point_id] = source_sha
                    elif known_source != source_sha:
                        n_plan_source_conflicts += 1
                        raise ValueError(
                            "plan_point_id conflict with mismatched plan_source_sha256: "
                            f"point_id={point_id!r}, sources={known_source!r} vs {source_sha!r}"
                        )

                record_key, hash_source = _record_key(payload=payload, dedupe_key=dedupe_key)
                if hash_source != "record":
                    n_fallback_hash += 1
                if record_key and record_key[0] == "params":
                    payload["params_hash"] = record_key[1]
                elif isinstance(payload.get("params_hash"), str) and payload.get("params_hash"):
                    payload["params_hash"] = str(payload.get("params_hash"))
                else:
                    params_hash, _ = _params_hash(payload)
                    payload["params_hash"] = params_hash

                canonical = _canonical_json_text(payload)
                chunk_entries.append(
                    (
                        tuple(str(part) for part in record_key),
                        int(source_rank),
                        int(line_idx),
                        canonical,
                    )
                )
                n_valid_records += 1
                if progress_every > 0 and int(n_valid_records) % int(progress_every) == 0:
                    print(
                        f"[merge-external] parsed_valid_records={int(n_valid_records)}",
                        file=sys.stderr,
                    )
                if len(chunk_entries) >= chunk_limit:
                    chunk_paths.append(
                        _flush_external_chunk(
                            entries=chunk_entries,
                            chunk_dir=chunk_dir,
                            chunk_index=len(chunk_paths),
                        )
                    )
                    chunk_entries = []

    if chunk_entries:
        chunk_paths.append(
            _flush_external_chunk(
                entries=chunk_entries,
                chunk_dir=chunk_dir,
                chunk_index=len(chunk_paths),
            )
        )

    stats = {
        "n_lines_read_total": int(n_lines_read_total),
        "n_skipped_blank": int(n_skipped_blank),
        "n_skipped_comment": int(n_skipped_comment),
        "n_skipped_invalid_json": int(n_skipped_invalid_json),
        "n_skipped_non_object": int(n_skipped_non_object),
        "n_skipped_header_like": int(n_skipped_header_like),
        "n_duplicates": 0,
        "n_conflicts": 0,
        "n_fallback_hash": int(n_fallback_hash),
        "n_plan_source_conflicts": int(n_plan_source_conflicts),
        "plan_source_sha256_seen_set": sorted(str(x) for x in plan_source_sha_seen),
        "scan_config_sha256_counts": {
            str(k): int(v)
            for k, v in sorted(scan_config_counts.items(), key=lambda kv: str(kv[0]))
        },
        "scan_config_sha256_examples": {
            str(k): str(v)
            for k, v in sorted(scan_config_examples.items(), key=lambda kv: str(kv[0]))
        },
        "external_chunks": int(len(chunk_paths)),
        "external_valid_records": int(n_valid_records),
    }
    return chunk_paths, stats


def _dedupe_external_chunks(
    *,
    chunk_paths: Sequence[Path],
    prefer: str,
    selected_raw_path: Path,
    progress_every: int,
) -> Tuple[Dict[str, int], bool, bool]:
    selected_raw_path.parent.mkdir(parents=True, exist_ok=True)

    readers = [path.open("r", encoding="utf-8") for path in chunk_paths]
    heap: List[Tuple[Tuple[str, ...], int, int, str, int, Dict[str, Any]]] = []

    def _push_next(reader_index: int) -> None:
        line = readers[reader_index].readline()
        if not line:
            return
        record_key, source_rank, source_line, canonical, payload = _read_external_chunk_row(line)
        heapq.heappush(
            heap,
            (
                tuple(str(part) for part in record_key),
                int(source_rank),
                int(source_line),
                str(canonical),
                int(reader_index),
                payload,
            ),
        )

    try:
        for idx in range(len(readers)):
            _push_next(idx)

        n_duplicates = 0
        n_conflicts = 0
        n_records_out = 0
        all_plan = True
        all_plan_has_index = True

        with selected_raw_path.open("w", encoding="utf-8") as out_fh:
            while heap:
                key, source_rank, source_line, canonical, reader_idx, payload = heapq.heappop(heap)
                score = _selection_score(
                    payload,
                    prefer=prefer,
                    source_rank=int(source_rank),
                    source_line=int(source_line),
                )
                selected_key = tuple(str(part) for part in key)
                selected_payload = payload
                selected_canonical = str(canonical)
                selected_score = score

                _push_next(reader_idx)

                while heap and tuple(str(part) for part in heap[0][0]) == selected_key:
                    key2, source_rank2, source_line2, canonical2, reader_idx2, payload2 = heapq.heappop(heap)
                    n_duplicates += 1
                    canonical2_text = str(canonical2)
                    if selected_canonical != canonical2_text:
                        n_conflicts += 1
                    score2 = _selection_score(
                        payload2,
                        prefer=prefer,
                        source_rank=int(source_rank2),
                        source_line=int(source_line2),
                    )
                    if score2 < selected_score:
                        selected_payload = payload2
                        selected_canonical = canonical2_text
                        selected_score = score2
                    _push_next(reader_idx2)

                if not (selected_key and selected_key[0] == "plan"):
                    all_plan = False
                elif all_plan_has_index:
                    if _finite_float(selected_payload.get("plan_point_index")) is None:
                        all_plan_has_index = False

                out_fh.write(_serialize_key_tuple(selected_key) + "\t" + selected_canonical + "\n")
                n_records_out += 1
                if progress_every > 0 and int(n_records_out) % int(progress_every) == 0:
                    print(
                        f"[merge-external] deduped_keys={int(n_records_out)}",
                        file=sys.stderr,
                    )

        stats = {
            "n_duplicates": int(n_duplicates),
            "n_conflicts": int(n_conflicts),
            "n_records_out": int(n_records_out),
            "n_unique_hashes": int(n_records_out),
        }
        return stats, bool(all_plan), bool(all_plan_has_index)
    finally:
        for fh in readers:
            try:
                fh.close()
            except Exception:
                pass


def _selected_sort_key(
    *,
    mode: str,
    record_key: Tuple[str, ...],
    payload: Mapping[str, Any],
) -> Tuple[Any, ...]:
    if mode == "plan_index":
        index_raw = payload.get("plan_point_index")
        index_val = _finite_float(index_raw)
        if index_val is None:
            raise ValueError("missing numeric plan_point_index while sorting external merged output")
        point_id = str(payload.get("plan_point_id", ""))
        source_sha = str(record_key[1]) if len(record_key) > 1 else ""
        return (int(float(index_val)), point_id, source_sha)
    if mode == "plan_point_id":
        point_id = str(record_key[2]) if len(record_key) > 2 else str(payload.get("plan_point_id", ""))
        source_sha = str(record_key[1]) if len(record_key) > 1 else ""
        return (point_id, source_sha)
    if mode == "generic":
        return (
            str(record_key[0]) if len(record_key) > 0 else "",
            str(record_key[1]) if len(record_key) > 1 else "",
            str(record_key[2]) if len(record_key) > 2 else "",
        )
    raise ValueError(f"unsupported external output sort mode: {mode!r}")


def _flush_selected_sort_chunk(
    *,
    entries: Sequence[Tuple[Tuple[Any, ...], str]],
    chunk_dir: Path,
    chunk_index: int,
) -> Path:
    ordered = sorted(entries, key=lambda item: (tuple(item[0]), str(item[1])))
    path = chunk_dir / f"selected_sort_{int(chunk_index):06d}.tsv"
    with path.open("w", encoding="utf-8") as fh:
        for sort_key, canonical in ordered:
            fh.write(
                json.dumps(list(sort_key), sort_keys=False, separators=(",", ":"), ensure_ascii=True)
                + "\t"
                + str(canonical)
                + "\n"
            )
    return path


def _read_selected_sort_row(line: str) -> Tuple[Tuple[Any, ...], str]:
    parts = line.rstrip("\n").split("\t", 1)
    if len(parts) != 2:
        raise ValueError("invalid selected-sort chunk row format")
    sort_key_raw = json.loads(parts[0])
    if not isinstance(sort_key_raw, list):
        raise ValueError("invalid selected-sort key payload (expected JSON list)")
    sort_key = tuple(sort_key_raw)
    canonical = str(parts[1])
    return sort_key, canonical


def _write_output_from_selected_raw(
    *,
    selected_raw_path: Path,
    out_path: Path,
    mode: str,
    chunk_records: int,
    chunk_dir: Path,
    progress_every: int,
) -> None:
    chunk_limit = max(1, int(chunk_records))
    chunk_dir.mkdir(parents=True, exist_ok=True)
    temp_chunks: List[Path] = []
    buffer: List[Tuple[Tuple[Any, ...], str]] = []
    n_selected_read = 0

    with selected_raw_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            text = line.rstrip("\n")
            if not text:
                continue
            parts = text.split("\t", 1)
            if len(parts) != 2:
                raise ValueError("invalid selected raw row format")
            record_key = _parse_key_tuple(parts[0])
            canonical = str(parts[1])
            payload = json.loads(canonical)
            if not isinstance(payload, Mapping):
                raise ValueError("invalid selected payload while writing output")
            sort_key = _selected_sort_key(mode=mode, record_key=record_key, payload=payload)
            buffer.append((sort_key, canonical))
            n_selected_read += 1
            if progress_every > 0 and int(n_selected_read) % int(progress_every) == 0:
                print(
                    f"[merge-external] output_sort_records={int(n_selected_read)}",
                    file=sys.stderr,
                )
            if len(buffer) >= chunk_limit:
                temp_chunks.append(
                    _flush_selected_sort_chunk(
                        entries=buffer,
                        chunk_dir=chunk_dir,
                        chunk_index=len(temp_chunks),
                    )
                )
                buffer = []
    if buffer:
        temp_chunks.append(
            _flush_selected_sort_chunk(
                entries=buffer,
                chunk_dir=chunk_dir,
                chunk_index=len(temp_chunks),
            )
        )

    readers = [path.open("r", encoding="utf-8") for path in temp_chunks]
    heap: List[Tuple[Tuple[Any, ...], str, int]] = []

    def _push_selected(reader_index: int) -> None:
        line = readers[reader_index].readline()
        if not line:
            return
        sort_key, canonical = _read_selected_sort_row(line)
        heapq.heappush(heap, (tuple(sort_key), str(canonical), int(reader_index)))

    try:
        for idx in range(len(readers)):
            _push_selected(idx)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open_text_auto(out_path, "w") as out_fh:
            while heap:
                sort_key, canonical, reader_idx = heapq.heappop(heap)
                del sort_key
                out_fh.write(str(canonical) + "\n")
                _push_selected(reader_idx)
    finally:
        for fh in readers:
            try:
                fh.close()
            except Exception:
                pass


def _external_sort_merge_to_output(
    *,
    chunk_paths: Sequence[Path],
    prefer: str,
    out_path: Path,
    chunk_records: int,
    work_dir: Path,
    progress_every: int,
) -> Dict[str, Any]:
    selected_raw_path = work_dir / "selected_raw.tsv"
    dedupe_stats, all_plan, all_plan_has_index = _dedupe_external_chunks(
        chunk_paths=chunk_paths,
        prefer=prefer,
        selected_raw_path=selected_raw_path,
        progress_every=progress_every,
    )
    if bool(all_plan):
        output_mode = "plan_index" if bool(all_plan_has_index) else "plan_point_id"
    else:
        output_mode = "generic"
    _write_output_from_selected_raw(
        selected_raw_path=selected_raw_path,
        out_path=out_path,
        mode=output_mode,
        chunk_records=chunk_records,
        chunk_dir=work_dir / "selected_sort_chunks",
        progress_every=progress_every,
    )
    dedupe_stats = dict(dedupe_stats)
    dedupe_stats["external_output_mode"] = str(output_mode)
    return {str(k): v for k, v in dedupe_stats.items()}


def _read_and_select(
    *,
    inputs: Sequence[Path],
    prefer: str,
    canonicalize: bool,
    dedupe_key: str,
) -> Tuple[Dict[Tuple[str, ...], Dict[str, Any]], Dict[str, Any]]:
    selected: Dict[Tuple[str, ...], Dict[str, Any]] = {}
    plan_source_by_id: Dict[str, str] = {}
    plan_source_sha_seen: Set[str] = set()
    scan_config_counts: Dict[str, int] = {}
    scan_config_examples: Dict[str, str] = {}

    n_lines_read_total = 0
    n_skipped_blank = 0
    n_skipped_comment = 0
    n_skipped_invalid_json = 0
    n_skipped_non_object = 0
    n_skipped_header_like = 0
    n_duplicates = 0
    n_conflicts = 0
    n_fallback_hash = 0
    n_plan_source_conflicts = 0

    for source_rank, path in enumerate(inputs):
        with open_text_auto(path, "r") as fh:
            for line_idx, line in enumerate(fh, start=1):
                n_lines_read_total += 1
                text = line.strip()
                if not text:
                    n_skipped_blank += 1
                    continue
                if text.startswith("#"):
                    n_skipped_comment += 1
                    continue
                try:
                    parsed = json.loads(text)
                except Exception:
                    n_skipped_invalid_json += 1
                    continue
                if not isinstance(parsed, Mapping):
                    n_skipped_non_object += 1
                    continue
                if not _is_data_record(parsed):
                    n_skipped_header_like += 1
                    continue

                payload = _strip_execution_fields(parsed, canonicalize=canonicalize)
                row_source_sha = _record_plan_source_sha(payload)
                if row_source_sha is not None:
                    plan_source_sha_seen.add(row_source_sha)
                row_scan_config_sha = _record_scan_config_sha(payload)
                scan_config_key = _scan_config_key(row_scan_config_sha)
                scan_config_counts[scan_config_key] = int(scan_config_counts.get(scan_config_key, 0) + 1)
                if scan_config_key not in scan_config_examples:
                    scan_config_examples[scan_config_key] = f"{path}:{line_idx}"
                plan_identity = _plan_identity(payload)
                if plan_identity is not None:
                    source_sha, point_id = plan_identity
                    known_source = plan_source_by_id.get(point_id)
                    if known_source is None:
                        plan_source_by_id[point_id] = source_sha
                    elif known_source != source_sha:
                        n_plan_source_conflicts += 1
                        raise ValueError(
                            "plan_point_id conflict with mismatched plan_source_sha256: "
                            f"point_id={point_id!r}, sources={known_source!r} vs {source_sha!r}"
                        )

                record_key, hash_source = _record_key(payload=payload, dedupe_key=dedupe_key)
                if hash_source != "record":
                    n_fallback_hash += 1
                if record_key and record_key[0] == "params":
                    payload["params_hash"] = record_key[1]
                elif isinstance(payload.get("params_hash"), str) and payload.get("params_hash"):
                    payload["params_hash"] = str(payload.get("params_hash"))
                else:
                    params_hash, _ = _params_hash(payload)
                    payload["params_hash"] = params_hash

                score = _selection_score(
                    payload,
                    prefer=prefer,
                    source_rank=int(source_rank),
                    source_line=int(line_idx),
                )
                existing = selected.get(record_key)
                if existing is None:
                    selected[record_key] = {
                        "record": payload,
                        "score": score,
                        "canonical": _canonical_json_text(payload),
                    }
                    continue

                n_duplicates += 1
                if existing["canonical"] != _canonical_json_text(payload):
                    n_conflicts += 1
                if score < existing["score"]:
                    selected[record_key] = {
                        "record": payload,
                        "score": score,
                        "canonical": _canonical_json_text(payload),
                    }

    stats = {
        "n_lines_read_total": int(n_lines_read_total),
        "n_skipped_blank": int(n_skipped_blank),
        "n_skipped_comment": int(n_skipped_comment),
        "n_skipped_invalid_json": int(n_skipped_invalid_json),
        "n_skipped_non_object": int(n_skipped_non_object),
        "n_skipped_header_like": int(n_skipped_header_like),
        "n_duplicates": int(n_duplicates),
        "n_conflicts": int(n_conflicts),
        "n_fallback_hash": int(n_fallback_hash),
        "n_plan_source_conflicts": int(n_plan_source_conflicts),
        "plan_source_sha256_seen_set": sorted(str(x) for x in plan_source_sha_seen),
        "scan_config_sha256_counts": {
            str(k): int(v)
            for k, v in sorted(scan_config_counts.items(), key=lambda kv: str(kv[0]))
        },
        "scan_config_sha256_examples": {
            str(k): str(v)
            for k, v in sorted(scan_config_examples.items(), key=lambda kv: str(kv[0]))
        },
    }
    return selected, stats


def _sorted_selected_items(
    selected: Mapping[Tuple[str, ...], Mapping[str, Any]],
) -> List[Tuple[Tuple[str, ...], Mapping[str, Any]]]:
    items = list(selected.items())
    if not items:
        return []

    all_plan = all(key and key[0] == "plan" for key, _ in items)
    if all_plan:
        has_index = all(
            _finite_float(_to_sort_payload(entry).get("plan_point_index")) is not None
            for _, entry in items
        )
        if has_index:
            return sorted(
                items,
                key=lambda kv: (
                    int(float(_to_sort_payload(kv[1]).get("plan_point_index"))),
                    str(_to_sort_payload(kv[1]).get("plan_point_id", "")),
                    str(kv[0][1]),
                ),
            )
        return sorted(items, key=lambda kv: (str(kv[0][2]), str(kv[0][1])))

    return sorted(
        items,
        key=lambda kv: (
            str(kv[0][0]),
            str(kv[0][1]) if len(kv[0]) > 1 else "",
            str(kv[0][2]) if len(kv[0]) > 2 else "",
        ),
    )


def _to_sort_payload(entry: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = entry.get("record")
    if isinstance(payload, Mapping):
        return payload
    return {}


def _write_output(path: Path, selected: Mapping[Tuple[str, ...], Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open_text_auto(path, "w") as fh:
        for _, selected_entry in _sorted_selected_items(selected):
            payload = selected_entry["record"]
            fh.write(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")


def _write_report(
    *,
    path: Path,
    inputs: Sequence[Path],
    out: Path,
    prefer: str,
    canonicalize: bool,
    dedupe_key: str,
    external_sort: bool,
    chunk_records: int,
    external_output_mode: Optional[str],
    stats: Mapping[str, Any],
    plan_source_policy: str,
    plan_sha256_expected: Optional[str],
    plan_source_sha256_declared: Optional[str],
    plan_source_seen_set: Sequence[str],
    plan_source_chosen: Optional[str],
    plan_source_match_values: Sequence[str],
    scan_config_policy: str,
    scan_config_seen_set: Sequence[str],
    scan_config_chosen: Optional[str],
    scan_config_missing_count: int,
    scan_config_counts: Mapping[str, int],
    scan_config_examples: Mapping[str, str],
) -> None:
    payload = {
        "n_inputs": int(len(inputs)),
        "inputs": [str(p.name) for p in inputs],
        "n_lines_read_total": int(stats.get("n_lines_read_total", 0)),
        "n_unique_hashes": int(stats.get("n_unique_hashes", 0)),
        "n_records_out": int(stats.get("n_records_out", 0)),
        "n_duplicates": int(stats.get("n_duplicates", 0)),
        "n_conflicts": int(stats.get("n_conflicts", 0)),
        "n_fallback_hash": int(stats.get("n_fallback_hash", 0)),
        "n_plan_source_conflicts": int(stats.get("n_plan_source_conflicts", 0)),
        "n_skipped_invalid_json": int(stats.get("n_skipped_invalid_json", 0)),
        "n_skipped_non_object": int(stats.get("n_skipped_non_object", 0)),
        "n_skipped_header_like": int(stats.get("n_skipped_header_like", 0)),
        "policy_prefer": str(prefer),
        "dedupe_key": str(dedupe_key),
        "canonicalize": bool(canonicalize),
        "external_sort": bool(external_sort),
        "chunk_records": int(chunk_records),
        "external_output_mode": str(external_output_mode) if external_output_mode else None,
        "plan_source_sha256_policy": str(plan_source_policy),
        "plan_sha256_expected": str(plan_sha256_expected) if plan_sha256_expected else None,
        "plan_source_sha256_declared": str(plan_source_sha256_declared) if plan_source_sha256_declared else None,
        "plan_source_sha256_match_values": [
            str(x) for x in sorted(str(v) for v in plan_source_match_values)
        ],
        "plan_source_sha256_seen_set": [str(x) for x in sorted(str(v) for v in plan_source_seen_set)],
        "plan_source_sha256_chosen": str(plan_source_chosen) if plan_source_chosen else "unknown",
        "scan_config_sha256_policy": str(scan_config_policy),
        "scan_config_sha256_seen_set": [str(x) for x in sorted(str(v) for v in scan_config_seen_set)],
        "scan_config_sha256_chosen": str(scan_config_chosen) if scan_config_chosen else "unknown",
        "scan_config_sha256_missing_count": int(scan_config_missing_count),
        "scan_config_sha256_counts": {
            str(k): int(v)
            for k, v in sorted(((str(x), int(y)) for x, y in scan_config_counts.items()), key=lambda kv: str(kv[0]))
        },
        "scan_config_sha256_examples": {
            str(k): str(v)
            for k, v in sorted(((str(x), str(y)) for x, y in scan_config_examples.items()), key=lambda kv: str(kv[0]))
        },
        "sha256_out": _sha256_file(out),
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Deterministically merge Phase-2 E2 scan JSONL files "
            "with auto dedupe by plan_point_id or params_hash."
        ),
    )
    ap.add_argument("inputs", nargs="+", type=str, help="Input JSONL files/directories/globs (1+ files after expansion)")
    ap.add_argument("--out", required=True, type=Path, help="Output merged JSONL path")
    ap.add_argument("--report-out", type=Path, default=None, help="Optional JSON merge summary path")
    ap.add_argument("--plan", type=Path, default=None, help="Optional plan JSON used for plan-source integrity checks.")
    ap.add_argument(
        "--plan-source-policy",
        choices=["ignore", "consistent", "match_plan"],
        default="consistent",
        help=(
            "Plan-source integrity policy: ignore, enforce consistent non-empty "
            "plan_source_sha256, or require match to --plan SHA256."
        ),
    )
    ap.add_argument(
        "--scan-config-sha-policy",
        choices=["auto", "ignore", "require"],
        default="auto",
        help=(
            "scan_config_sha256 integrity policy. auto: allow legacy all-missing, "
            "but fail on mixed/multiple values; require: enforce one non-empty shared value."
        ),
    )
    ap.add_argument(
        "--prefer",
        choices=["ok_then_lowest_chi2", "ok_then_first", "first"],
        default="ok_then_lowest_chi2",
        help="Conflict policy for duplicate params_hash records.",
    )
    ap.add_argument(
        "--dedupe-key",
        choices=["auto", "plan_point_id", "params_hash"],
        default="auto",
        help=(
            "Dedupe identity key (default auto): prefer plan_point_id+plan_source_sha256 when available; "
            "fallback to params_hash."
        ),
    )
    ap.add_argument("--canonicalize", dest="canonicalize", action="store_true", default=True)
    ap.add_argument("--no-canonicalize", dest="canonicalize", action="store_false")
    ap.add_argument(
        "--external-sort",
        action="store_true",
        help=(
            "Use memory-bounded external sorting (chunk sort + k-way merge) before deterministic dedupe. "
            "Keeps merge semantics unchanged."
        ),
    )
    ap.add_argument(
        "--chunk-records",
        type=int,
        default=200000,
        help="Valid records per external-sort chunk when --external-sort is enabled (default: 200000).",
    )
    ap.add_argument(
        "--tmpdir",
        type=Path,
        default=None,
        help="Optional temp directory root for external-sort chunks (default: system temp).",
    )
    ap.add_argument(
        "--keep-tmp",
        action="store_true",
        help="Keep external-sort temporary files for debugging.",
    )
    ap.add_argument(
        "--progress-every",
        type=int,
        default=0,
        help="Emit stderr progress every N parsed/deduped records in external-sort mode (default: off).",
    )
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        code = int(exc.code) if isinstance(exc.code, int) else 1
        return 1 if code != 0 else 0

    try:
        inputs = _resolve_input_paths([str(p) for p in args.inputs])
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if len(inputs) < 1:
        print("phase2_e2_merge_jsonl.py requires at least one input JSONL file", file=sys.stderr)
        return 1

    expected_plan_sha: Optional[str] = None
    declared_plan_source_sha: Optional[str] = None
    if args.plan is not None:
        plan_path = Path(args.plan).expanduser().resolve()
        if not plan_path.is_file():
            print(f"--plan file not found: {plan_path}", file=sys.stderr)
            return 1
        expected_plan_sha = _sha256_file(plan_path)
        declared_plan_source_sha = _extract_declared_plan_source_sha256(plan_path)

    out = Path(args.out).expanduser().resolve()
    if int(args.chunk_records) < 1:
        print("--chunk-records must be >= 1", file=sys.stderr)
        return 1
    if int(args.progress_every) < 0:
        print("--progress-every must be >= 0", file=sys.stderr)
        return 1

    selected: Dict[Tuple[str, ...], Dict[str, Any]] = {}
    stats: Dict[str, Any]
    plan_source: Dict[str, Any]
    scan_config: Dict[str, Any]
    external_tmp_workdir: Optional[Path] = None
    external_output_mode: Optional[str] = None

    try:
        if bool(args.external_sort):
            tmp_root = None if args.tmpdir is None else Path(args.tmpdir).expanduser().resolve()
            if tmp_root is not None:
                tmp_root.mkdir(parents=True, exist_ok=True)
            external_tmp_workdir = Path(
                tempfile.mkdtemp(
                    prefix="phase2_e2_merge_ext_",
                    dir=(str(tmp_root) if tmp_root is not None else None),
                )
            ).resolve()

            chunk_paths, stats = _build_external_chunks(
                inputs=inputs,
                prefer=str(args.prefer),
                canonicalize=bool(args.canonicalize),
                dedupe_key=str(args.dedupe_key),
                chunk_records=int(args.chunk_records),
                chunk_dir=external_tmp_workdir / "chunks",
                progress_every=int(args.progress_every),
            )
            plan_source = _enforce_plan_source_policy(
                policy=str(args.plan_source_policy),
                seen_set=set(str(x) for x in list(stats.get("plan_source_sha256_seen_set", []))),
                plan_sha256_expected=expected_plan_sha,
                plan_source_declared=declared_plan_source_sha,
            )
            scan_config = _enforce_scan_config_policy(
                policy=str(args.scan_config_sha_policy),
                counts={str(k): int(v) for k, v in dict(stats.get("scan_config_sha256_counts", {})).items()},
                examples={str(k): str(v) for k, v in dict(stats.get("scan_config_sha256_examples", {})).items()},
            )
            dedupe_stats = _external_sort_merge_to_output(
                chunk_paths=chunk_paths,
                prefer=str(args.prefer),
                out_path=out,
                chunk_records=int(args.chunk_records),
                work_dir=external_tmp_workdir,
                progress_every=int(args.progress_every),
            )
            stats = dict(stats)
            stats.update(dedupe_stats)
            external_output_mode = (
                str(dedupe_stats.get("external_output_mode"))
                if isinstance(dedupe_stats.get("external_output_mode"), str)
                else None
            )
            if external_tmp_workdir is not None and bool(args.keep_tmp):
                print(
                    f"[merge-external] keep tmp: {external_tmp_workdir}",
                    file=sys.stderr,
                )
        else:
            selected, stats = _read_and_select(
                inputs=inputs,
                prefer=str(args.prefer),
                canonicalize=bool(args.canonicalize),
                dedupe_key=str(args.dedupe_key),
            )
            plan_source = _enforce_plan_source_policy(
                policy=str(args.plan_source_policy),
                seen_set=set(str(x) for x in list(stats.get("plan_source_sha256_seen_set", []))),
                plan_sha256_expected=expected_plan_sha,
                plan_source_declared=declared_plan_source_sha,
            )
            scan_config = _enforce_scan_config_policy(
                policy=str(args.scan_config_sha_policy),
                counts={str(k): int(v) for k, v in dict(stats.get("scan_config_sha256_counts", {})).items()},
                examples={str(k): str(v) for k, v in dict(stats.get("scan_config_sha256_examples", {})).items()},
            )
            _write_output(out, selected)
            stats = dict(stats)
            stats["n_unique_hashes"] = int(len(selected))
            stats["n_records_out"] = int(len(selected))
    except PlanSourcePolicyFailure as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except ScanConfigPolicyFailure as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        if external_tmp_workdir is not None and not bool(args.keep_tmp):
            try:
                shutil.rmtree(external_tmp_workdir)
            except Exception:
                pass

    report_out = None if args.report_out is None else Path(args.report_out).expanduser().resolve()
    if report_out is not None:
        _write_report(
            path=report_out,
            inputs=inputs,
            out=out,
            prefer=str(args.prefer),
            canonicalize=bool(args.canonicalize),
            dedupe_key=str(args.dedupe_key),
            external_sort=bool(args.external_sort),
            chunk_records=int(args.chunk_records),
            external_output_mode=external_output_mode,
            stats=stats,
            plan_source_policy=str(plan_source.get("policy", args.plan_source_policy)),
            plan_sha256_expected=expected_plan_sha,
            plan_source_sha256_declared=declared_plan_source_sha,
            plan_source_seen_set=[str(x) for x in list(plan_source.get("seen_set", []))],
            plan_source_chosen=(
                str(plan_source.get("chosen")) if isinstance(plan_source.get("chosen"), str) else None
            ),
            plan_source_match_values=[str(x) for x in list(plan_source.get("match_values", []))],
            scan_config_policy=str(scan_config.get("policy", args.scan_config_sha_policy)),
            scan_config_seen_set=[str(x) for x in list(scan_config.get("seen_set", []))],
            scan_config_chosen=(
                str(scan_config.get("chosen")) if isinstance(scan_config.get("chosen"), str) else None
            ),
            scan_config_missing_count=int(scan_config.get("missing_count", 0)),
            scan_config_counts={
                str(k): int(v)
                for k, v in dict(scan_config.get("counts", {})).items()
            },
            scan_config_examples={
                str(k): str(v)
                for k, v in dict(scan_config.get("examples", {})).items()
            },
        )

    print(
        json.dumps(
            {
                "out": str(out),
                "n_inputs": int(len(inputs)),
                "n_lines_read_total": int(stats["n_lines_read_total"]),
                "n_records_out": int(stats["n_records_out"]),
                "n_duplicates": int(stats["n_duplicates"]),
                "n_conflicts": int(stats["n_conflicts"]),
                "n_plan_source_conflicts": int(stats.get("n_plan_source_conflicts", 0)),
                "policy_prefer": str(args.prefer),
                "dedupe_key": str(args.dedupe_key),
                "canonicalize": bool(args.canonicalize),
                "external_sort": bool(args.external_sort),
                "chunk_records": int(args.chunk_records),
                "external_output_mode": str(external_output_mode) if external_output_mode else "none",
                "plan_source_sha256_policy": str(plan_source.get("policy", args.plan_source_policy)),
                "plan_sha256_expected": str(expected_plan_sha) if expected_plan_sha else "none",
                "plan_source_sha256_declared": str(declared_plan_source_sha) if declared_plan_source_sha else "none",
                "plan_source_sha256_match_values": sorted(
                    str(x) for x in list(plan_source.get("match_values", []))
                ),
                "plan_source_sha256_seen_set": sorted(
                    str(x) for x in list(plan_source.get("seen_set", []))
                ),
                "plan_source_sha256_chosen": (
                    str(plan_source.get("chosen"))
                    if isinstance(plan_source.get("chosen"), str)
                    else "unknown"
                ),
                "scan_config_sha256_policy": str(scan_config.get("policy", args.scan_config_sha_policy)),
                "scan_config_sha256_seen_set": sorted(
                    str(x) for x in list(scan_config.get("seen_set", []))
                ),
                "scan_config_sha256_chosen": (
                    str(scan_config.get("chosen"))
                    if isinstance(scan_config.get("chosen"), str)
                    else "unknown"
                ),
                "scan_config_sha256_missing_count": int(scan_config.get("missing_count", 0)),
                "scan_config_sha256_counts": {
                    str(k): int(v)
                    for k, v in sorted(
                        ((str(x), int(y)) for x, y in dict(scan_config.get("counts", {})).items()),
                        key=lambda kv: str(kv[0]),
                    )
                },
                "scan_config_sha256_examples": {
                    str(k): str(v)
                    for k, v in sorted(
                        ((str(x), str(y)) for x, y in dict(scan_config.get("examples", {})).items()),
                        key=lambda kv: str(kv[0]),
                    )
                },
                "sha256_out": _sha256_file(out),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

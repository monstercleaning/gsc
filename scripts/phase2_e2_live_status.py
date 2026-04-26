#!/usr/bin/env python3
"""Live/instant status monitor for Phase-2 E2 JSONL scans (stdlib-only)."""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


V101_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V101_DIR))

from gsc.early_time.refine_plan_v1 import (  # noqa: E402
    get_plan_source_sha256,
    iter_plan_points,
    load_refine_plan_v1,
)
from gsc.jsonl_io import open_text_auto  # noqa: E402


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


def _canonical_params(params: Mapping[str, Any]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for key in sorted(str(k) for k in params.keys()):
        value = _finite_float(params.get(key))
        if value is not None:
            out[str(key)] = float(value)
    return out


def _canonical_hash_payload(payload: Mapping[str, Any]) -> str:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _params_hash(record: Mapping[str, Any], *, line_text: Optional[str] = None) -> str:
    raw = record.get("params_hash")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    params = record.get("params")
    if isinstance(params, Mapping):
        canonical = _canonical_params(params)
        if canonical:
            return _canonical_hash_payload(canonical)
    if line_text is not None:
        return hashlib.sha256(line_text.encode("utf-8")).hexdigest()
    return _canonical_hash_payload({str(k): record[k] for k in sorted(record.keys())})


def _normalize_status(record: Mapping[str, Any]) -> str:
    raw = record.get("status")
    if raw is None:
        return "unknown"
    text = str(raw).strip().lower()
    return text if text else "unknown"


def _extract_chi2_total(record: Mapping[str, Any]) -> Optional[float]:
    direct = _finite_float(record.get("chi2_total"))
    if direct is not None:
        return direct
    direct = _finite_float(record.get("chi2"))
    if direct is not None:
        return direct
    parts = _as_mapping(record.get("chi2_parts"))
    if not parts:
        return None
    total = 0.0
    used = False
    for value in parts.values():
        if isinstance(value, Mapping):
            sub = _finite_float(value.get("chi2"))
        else:
            sub = _finite_float(value)
        if sub is None:
            continue
        total += float(sub)
        used = True
    return float(total) if used else None


def _extract_chi2_cmb(record: Mapping[str, Any]) -> Optional[float]:
    direct = _finite_float(record.get("chi2_cmb"))
    if direct is not None:
        return direct
    parts = _as_mapping(record.get("chi2_parts"))
    cmb = _as_mapping(parts.get("cmb"))
    direct = _finite_float(cmb.get("chi2"))
    if direct is not None:
        return direct
    return _finite_float(parts.get("cmb"))


def _extract_error_key(record: Mapping[str, Any], *, status: str) -> Optional[str]:
    err = record.get("error")
    if isinstance(err, Mapping):
        et = str(err.get("type", "")).strip()
        if et:
            return et
        msg = str(err.get("message", "")).strip()
        if msg:
            return msg.split()[0][:80]
    if isinstance(err, str) and err.strip():
        return err.strip().split()[0][:80]
    if status == "error":
        return "error"
    return None


def _collect_drift_fields(record: Mapping[str, Any]) -> Set[str]:
    out: Set[str] = set()
    for key in record.keys():
        text = str(key)
        if text.startswith("drift_"):
            out.add(text)
    drift_obj = _as_mapping(record.get("drift"))
    for key in drift_obj.keys():
        out.add(f"drift.{str(key)}")
    return out


def _scan_config_bucket(record: Mapping[str, Any]) -> str:
    raw = record.get("scan_config_sha256")
    if not isinstance(raw, str):
        return "__MISSING__"
    text = raw.strip()
    return text if text else "__MISSING__"


def _parse_slice_key(record: Mapping[str, Any]) -> Optional[Tuple[int, int]]:
    raw_i = record.get("plan_slice_i")
    raw_n = record.get("plan_slice_n")
    value_i = _finite_float(raw_i)
    value_n = _finite_float(raw_n)
    if value_i is None or value_n is None:
        return None
    slice_i = int(value_i)
    slice_n = int(value_n)
    if float(slice_i) != float(value_i):
        return None
    if float(slice_n) != float(value_n):
        return None
    if slice_n < 1:
        return None
    if slice_i < 0 or slice_i >= slice_n:
        return None
    return (int(slice_i), int(slice_n))


def _is_plausible(record: Mapping[str, Any]) -> bool:
    raw = record.get("microphysics_plausible_ok")
    if raw is None:
        return True
    return bool(raw)


def _is_eligible(record: Mapping[str, Any], *, status: str, status_filter: str) -> bool:
    chi2_total = _extract_chi2_total(record)
    if chi2_total is None:
        return False
    if status_filter == "ok_only":
        return status == "ok"
    if status_filter == "any_eligible":
        return status != "error"
    return False


def _resolve_inputs(tokens: Sequence[str]) -> List[Path]:
    resolved: List[Path] = []
    seen: Set[Path] = set()

    def _iter_dir_jsonl_files(path: Path) -> List[Path]:
        files: List[Path] = []
        local_seen: Set[Path] = set()
        for candidate in list(path.glob("*.jsonl")) + list(path.glob("*.jsonl.gz")):
            rp = candidate.resolve()
            if rp in local_seen or not rp.is_file():
                continue
            local_seen.add(rp)
            files.append(rp)
        return sorted(files, key=lambda p: str(p))

    for raw in tokens:
        token = str(raw).strip()
        if not token:
            continue
        expanded_any = False
        if any(ch in token for ch in "*?["):
            matches = sorted(glob.glob(token))
            for match in matches:
                path = Path(match).expanduser().resolve()
                if path in seen:
                    continue
                seen.add(path)
                if path.is_file():
                    resolved.append(path)
                elif path.is_dir():
                    for rp in _iter_dir_jsonl_files(path):
                        if rp in seen:
                            continue
                        seen.add(rp)
                        resolved.append(rp)
                expanded_any = True
            if expanded_any:
                continue

        path = Path(token).expanduser().resolve()
        if not path.exists():
            raise SystemExit(f"--input path not found: {token}")
        if path.is_file():
            if path not in seen:
                seen.add(path)
                resolved.append(path)
            continue
        if path.is_dir():
            files = _iter_dir_jsonl_files(path)
            if not files:
                continue
            for rp in files:
                if rp in seen:
                    continue
                seen.add(rp)
                resolved.append(rp)
            continue
        raise SystemExit(f"--input must be a file, directory, or glob pattern: {token}")
    return sorted(resolved, key=lambda p: str(p))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _short_best_record(record: Mapping[str, Any], *, params_hash: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "params_hash": str(params_hash),
        "status": _normalize_status(record),
        "chi2_total": _extract_chi2_total(record),
        "chi2_cmb": _extract_chi2_cmb(record),
        "plan_point_id": (
            str(record.get("plan_point_id")).strip() if record.get("plan_point_id") is not None else None
        ),
        "microphysics_plausible_ok": bool(record.get("microphysics_plausible_ok", True)),
        "microphysics_penalty": _finite_float(record.get("microphysics_penalty")),
        "microphysics_max_rel_dev": _finite_float(record.get("microphysics_max_rel_dev")),
    }
    drift_precheck_ok = record.get("drift_precheck_ok")
    if drift_precheck_ok is not None:
        out["drift_precheck_ok"] = bool(drift_precheck_ok)
    return out


def _line_sort(items: Mapping[str, int]) -> List[Tuple[str, int]]:
    return sorted(((str(k), int(v)) for k, v in items.items()), key=lambda kv: (-int(kv[1]), str(kv[0])))


def _format_float(value: Optional[float]) -> str:
    if value is None:
        return "NA"
    return f"{float(value):.6g}"


def _analyze(
    *,
    input_paths: Sequence[Path],
    status_filter: str,
    mode: str,
    plan_path: Optional[Path],
    tail_safe: bool,
    include_slice_summary: bool,
) -> Dict[str, Any]:
    total_records = 0
    invalid_lines = 0
    partial_tail_lines_skipped = 0
    status_counts: Dict[str, int] = {}
    error_counts: Dict[str, int] = {}
    drift_fields_present: Set[str] = set()
    unique_hashes: Set[str] = set()
    scan_config_counts: Dict[str, int] = {}
    rsd_overlay_present_records = 0
    rsd_overlay_ok_records = 0
    rsd_transfer_model_counts: Dict[str, int] = {}

    best_overall: Optional[Tuple[float, str, Dict[str, Any]]] = None
    best_plausible: Optional[Tuple[float, str, Dict[str, Any]]] = None
    best_joint_overall: Optional[Tuple[float, str, Dict[str, Any]]] = None
    best_rsd_overlay: Optional[Tuple[float, str, Dict[str, Any]]] = None

    by_file_stats: List[Dict[str, Any]] = []
    records_for_coverage: List[Dict[str, Any]] = []
    per_slice_stats: Dict[Tuple[int, int], Dict[str, Any]] = {}

    for path in input_paths:
        file_total = 0
        file_invalid = 0
        file_partial = 0
        file_status: Dict[str, int] = {}
        file_scan_config: Dict[str, int] = {}
        with open_text_auto(path, "r") as fh:
            deferred_line: Optional[str] = None

            def consume_line(raw_line: str, *, is_last: bool) -> None:
                nonlocal total_records
                nonlocal invalid_lines
                nonlocal partial_tail_lines_skipped
                nonlocal file_total
                nonlocal file_invalid
                nonlocal file_partial
                nonlocal best_overall
                nonlocal best_plausible
                nonlocal best_joint_overall
                nonlocal rsd_overlay_present_records
                nonlocal rsd_overlay_ok_records
                nonlocal best_rsd_overlay
                nonlocal rsd_transfer_model_counts
                text = str(raw_line).strip()
                if not text:
                    return
                file_total += 1
                total_records += 1
                try:
                    payload = json.loads(text)
                except Exception:
                    if bool(tail_safe) and bool(is_last) and not str(raw_line).endswith("\n"):
                        partial_tail_lines_skipped += 1
                        file_partial += 1
                        return
                    invalid_lines += 1
                    file_invalid += 1
                    return
                if not isinstance(payload, Mapping):
                    invalid_lines += 1
                    file_invalid += 1
                    return
                record = {str(k): payload[k] for k in payload.keys()}
                status = _normalize_status(record)
                status_counts[status] = int(status_counts.get(status, 0)) + 1
                file_status[status] = int(file_status.get(status, 0)) + 1
                err_key = _extract_error_key(record, status=status)
                if err_key is not None:
                    error_counts[err_key] = int(error_counts.get(err_key, 0)) + 1

                params_hash = _params_hash(record, line_text=text)
                unique_hashes.add(params_hash)
                drift_fields_present.update(_collect_drift_fields(record))
                bucket = _scan_config_bucket(record)
                scan_config_counts[bucket] = int(scan_config_counts.get(bucket, 0)) + 1
                file_scan_config[bucket] = int(file_scan_config.get(bucket, 0)) + 1
                has_rsd_overlay = any(
                    key in record for key in ("rsd_overlay_ok", "rsd_chi2", "rsd_sigma8_0_best", "rsd_n")
                )
                if has_rsd_overlay:
                    rsd_overlay_present_records += 1

                eligible = _is_eligible(record, status=status, status_filter=status_filter)
                chi2_total = _extract_chi2_total(record)
                if bool(eligible):
                    transfer_model = record.get("rsd_transfer_model")
                    if isinstance(transfer_model, str) and transfer_model.strip():
                        model_key = transfer_model.strip().lower()
                        rsd_transfer_model_counts[model_key] = int(
                            rsd_transfer_model_counts.get(model_key, 0)
                        ) + 1
                if eligible and chi2_total is not None:
                    candidate = (float(chi2_total), str(params_hash), record)
                    if best_overall is None or candidate[:2] < best_overall[:2]:
                        best_overall = candidate
                    if _is_plausible(record):
                        if best_plausible is None or candidate[:2] < best_plausible[:2]:
                            best_plausible = candidate
                if eligible:
                    chi2_joint_total = _finite_float(record.get("chi2_joint_total"))
                    if chi2_joint_total is not None:
                        candidate_joint = (float(chi2_joint_total), str(params_hash), record)
                        if best_joint_overall is None or candidate_joint[:2] < best_joint_overall[:2]:
                            best_joint_overall = candidate_joint
                if has_rsd_overlay and bool(record.get("rsd_overlay_ok")):
                    rsd_overlay_ok_records += 1
                    chi2_rsd = _finite_float(record.get("rsd_chi2"))
                    if status == "ok" and bool(eligible) and chi2_rsd is not None:
                        candidate_rsd = (float(chi2_rsd), str(params_hash), record)
                        if best_rsd_overlay is None or candidate_rsd[:2] < best_rsd_overlay[:2]:
                            best_rsd_overlay = candidate_rsd

                slice_key = _parse_slice_key(record) if bool(include_slice_summary) else None
                if slice_key is not None:
                    slice_row = per_slice_stats.setdefault(
                        slice_key,
                        {
                            "slice_i": int(slice_key[0]),
                            "slice_n": int(slice_key[1]),
                            "n_records": 0,
                            "status_counts": {},
                            "eligible_count": 0,
                            "best_candidate": None,
                        },
                    )
                    slice_row["n_records"] = int(slice_row.get("n_records", 0)) + 1
                    status_map = _as_mapping(slice_row.get("status_counts"))
                    mutable_status = {str(k): int(v) for k, v in status_map.items()}
                    mutable_status[status] = int(mutable_status.get(status, 0)) + 1
                    slice_row["status_counts"] = mutable_status
                    if bool(eligible):
                        slice_row["eligible_count"] = int(slice_row.get("eligible_count", 0)) + 1
                        if chi2_total is not None:
                            best_candidate = slice_row.get("best_candidate")
                            candidate = (
                                float(chi2_total),
                                str(params_hash),
                                str(record.get("plan_point_id", "")).strip(),
                            )
                            if best_candidate is None or candidate[:2] < tuple(best_candidate)[:2]:
                                slice_row["best_candidate"] = candidate

                records_for_coverage.append(
                    {
                        "status": status,
                        "params_hash": params_hash,
                        "eligible": bool(eligible),
                        "plan_point_id": (
                            str(record.get("plan_point_id")).strip()
                            if record.get("plan_point_id") is not None
                            else ""
                        ),
                        "plan_source_sha256": (
                            str(record.get("plan_source_sha256")).strip()
                            if record.get("plan_source_sha256") is not None
                            else ""
                        ),
                        "slice_i": int(slice_key[0]) if slice_key is not None else None,
                        "slice_n": int(slice_key[1]) if slice_key is not None else None,
                    }
                )

            for raw_line in fh:
                if deferred_line is None:
                    deferred_line = raw_line
                    continue
                consume_line(deferred_line, is_last=False)
                deferred_line = raw_line
            if deferred_line is not None:
                consume_line(deferred_line, is_last=True)
        by_file_stats.append(
            {
                "path": str(path),
                "sha256": _sha256_file(path),
                "bytes": int(path.stat().st_size),
                "n_records_parsed": int(file_total - file_invalid - file_partial),
                "n_invalid_lines": int(file_invalid),
                "status_counts": {k: int(v) for k, v in _line_sort(file_status)},
                "scan_config_sha256_counts": {
                    k: int(v) for k, v in sorted(file_scan_config.items(), key=lambda kv: str(kv[0]))
                },
                **(
                    {"n_partial_tail_lines_skipped": int(file_partial)}
                    if bool(tail_safe)
                    else {}
                ),
            }
        )

    plan_summary: Optional[Dict[str, Any]] = None
    plan_payload: Optional[Mapping[str, Any]] = None
    plan_point_order_ids: List[str] = []
    if plan_path is not None:
        try:
            plan_payload = load_refine_plan_v1(plan_path)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        plan_source = str(get_plan_source_sha256(plan_payload)).strip()
        plan_ids: Set[str] = set()
        plan_hashes: Set[str] = set()
        for point_id, point_obj, params in iter_plan_points(plan_payload):
            normalized_point_id = str(point_id)
            plan_ids.add(normalized_point_id)
            plan_point_order_ids.append(normalized_point_id)
            plan_hashes.add(_canonical_hash_payload(_canonical_params(params)))
            # keep compatibility if plan stores params_hash in point metadata
            raw_ph = point_obj.get("params_hash")
            if isinstance(raw_ph, str) and raw_ph.strip():
                plan_hashes.add(raw_ph.strip())

        has_any_point_ids = any(bool(item.get("plan_point_id")) for item in records_for_coverage)
        has_any_hashes = any(bool(item.get("params_hash")) for item in records_for_coverage)
        strategy = "unknown"
        seen_any: Set[str] = set()
        seen_eligible: Set[str] = set()
        foreign_records = 0

        if has_any_point_ids:
            strategy = "plan_point_id"
            for item in records_for_coverage:
                point_id = str(item.get("plan_point_id", "")).strip()
                if not point_id:
                    continue
                if point_id not in plan_ids:
                    continue
                row_source = str(item.get("plan_source_sha256", "")).strip()
                if row_source and plan_source and row_source != plan_source:
                    foreign_records += 1
                    continue
                seen_any.add(point_id)
                if bool(item.get("eligible")):
                    seen_eligible.add(point_id)
        elif has_any_hashes and plan_hashes:
            strategy = "params_hash"
            for item in records_for_coverage:
                ph = str(item.get("params_hash", "")).strip()
                if not ph or ph not in plan_hashes:
                    continue
                seen_any.add(ph)
                if bool(item.get("eligible")):
                    seen_eligible.add(ph)
        plan_total = int(len(plan_ids))
        if strategy == "params_hash":
            plan_total = int(len(plan_hashes))

        if strategy == "unknown" or plan_total <= 0:
            plan_summary = {
                "known": False,
                "strategy": "unknown",
                "plan_points_total": int(plan_total),
                "plan_points_seen_any": 0,
                "plan_points_seen_eligible": 0,
                "coverage_any": None,
                "coverage_eligible": None,
                "foreign_records": int(foreign_records),
                "plan_source_sha256": plan_source or None,
            }
        else:
            plan_summary = {
                "known": True,
                "strategy": strategy,
                "plan_points_total": int(plan_total),
                "plan_points_seen_any": int(len(seen_any)),
                "plan_points_seen_eligible": int(len(seen_eligible)),
                "coverage_any": float(len(seen_any) / float(plan_total)),
                "coverage_eligible": float(len(seen_eligible) / float(plan_total)),
                "foreign_records": int(foreign_records),
                "plan_source_sha256": plan_source or None,
            }

    scan_config_values = sorted(str(k) for k in scan_config_counts.keys() if str(k) != "__MISSING__" and str(k).strip())
    scan_config_missing_count = int(scan_config_counts.get("__MISSING__", 0))
    scan_config_mixed = bool(len(scan_config_values) > 1 or (len(scan_config_values) == 1 and scan_config_missing_count > 0))
    scan_config_chosen = scan_config_values[0] if len(scan_config_values) == 1 and scan_config_missing_count == 0 else "unknown"

    summary: Dict[str, Any] = {
        "schema": "phase2_e2_live_status_v1",
        "mode": str(mode),
        "status_filter": str(status_filter),
        "n_inputs": int(len(input_paths)),
        "n_files_expanded": int(len(input_paths)),
        "n_records_total": int(total_records),
        "n_records_parsed": int(total_records - invalid_lines - partial_tail_lines_skipped),
        "n_invalid_lines": int(invalid_lines),
        "n_unique_params_hash": int(len(unique_hashes)),
        "status_counts": {k: int(v) for k, v in _line_sort(status_counts)},
        "error_counts": {k: int(v) for k, v in _line_sort(error_counts)},
        "drift_fields_present": sorted(drift_fields_present),
        "scan_config_sha256_values": [str(v) for v in scan_config_values],
        "scan_config_sha256_counts": {
            str(k): int(v)
            for k, v in sorted(scan_config_counts.items(), key=lambda kv: str(kv[0]))
        },
        "scan_config_sha256_missing_count": int(scan_config_missing_count),
        "scan_config_sha256_mixed": bool(scan_config_mixed),
        "scan_config_sha256_chosen": str(scan_config_chosen),
        "best": {
            "overall": None
            if best_overall is None
            else _short_best_record(best_overall[2], params_hash=str(best_overall[1])),
            "plausible": None
            if best_plausible is None
            else _short_best_record(best_plausible[2], params_hash=str(best_plausible[1])),
            "joint": (
                None
                if best_joint_overall is None
                else {
                    **_short_best_record(best_joint_overall[2], params_hash=str(best_joint_overall[1])),
                    "chi2_joint_total": _finite_float(best_joint_overall[2].get("chi2_joint_total")),
                    "rsd_chi2_field_used": (
                        str(best_joint_overall[2].get("rsd_chi2_field_used")).strip()
                        if best_joint_overall[2].get("rsd_chi2_field_used") is not None
                        else None
                    ),
                    "rsd_chi2_weight": _finite_float(best_joint_overall[2].get("rsd_chi2_weight")),
                }
            ),
        },
        "rsd_overlay": {
            "present_records": int(rsd_overlay_present_records),
            "ok_records": int(rsd_overlay_ok_records),
            "best_chi2": (
                None if best_rsd_overlay is None else float(best_rsd_overlay[0])
            ),
            "best_params_hash": (
                None if best_rsd_overlay is None else str(best_rsd_overlay[1])
            ),
            "best_plan_point_id": (
                None
                if best_rsd_overlay is None
                else (
                    str(best_rsd_overlay[2].get("plan_point_id")).strip()
                    if best_rsd_overlay[2].get("plan_point_id") is not None
                    else None
                )
            ),
            "best_chi2_total": (
                None if best_rsd_overlay is None else _extract_chi2_total(best_rsd_overlay[2])
            ),
            "best_transfer_model": (
                None
                if best_rsd_overlay is None
                else (
                    str(best_rsd_overlay[2].get("rsd_transfer_model")).strip()
                    if best_rsd_overlay[2].get("rsd_transfer_model") is not None
                    else None
                )
            ),
            "best_primordial_ns": (
                None
                if best_rsd_overlay is None
                else _finite_float(best_rsd_overlay[2].get("rsd_primordial_ns"))
            ),
            "best_primordial_k_pivot_mpc": (
                None
                if best_rsd_overlay is None
                else _finite_float(best_rsd_overlay[2].get("rsd_primordial_k_pivot_mpc"))
            ),
            "best_joint_chi2_total": (
                None
                if best_joint_overall is None
                else _finite_float(best_joint_overall[2].get("chi2_joint_total"))
            ),
            "best_joint_params_hash": (
                None if best_joint_overall is None else str(best_joint_overall[1])
            ),
            "best_joint_plan_point_id": (
                None
                if best_joint_overall is None
                else (
                    str(best_joint_overall[2].get("plan_point_id")).strip()
                    if best_joint_overall[2].get("plan_point_id") is not None
                    else None
                )
            ),
            "best_joint_rsd_chi2_field_used": (
                None
                if best_joint_overall is None
                else (
                    str(best_joint_overall[2].get("rsd_chi2_field_used")).strip()
                    if best_joint_overall[2].get("rsd_chi2_field_used") is not None
                    else None
                )
            ),
            "best_joint_rsd_chi2_weight": (
                None
                if best_joint_overall is None
                else _finite_float(best_joint_overall[2].get("rsd_chi2_weight"))
            ),
            "transfer_model_counts": {
                k: int(v) for k, v in _line_sort(rsd_transfer_model_counts)
            },
        },
        "plan_coverage": plan_summary,
        "by_file": sorted(by_file_stats, key=lambda row: str(row.get("path", ""))),
    }
    if bool(tail_safe):
        summary["n_partial_tail_lines_skipped"] = int(partial_tail_lines_skipped)
    if bool(include_slice_summary) and bool(per_slice_stats):
        slice_output: List[Dict[str, Any]] = []
        plan_ids_by_slice: Dict[Tuple[int, int], Set[str]] = {}
        seen_any_by_slice: Dict[Tuple[int, int], Set[str]] = {}
        seen_eligible_by_slice: Dict[Tuple[int, int], Set[str]] = {}
        plan_known_for_slice = bool(
            plan_summary
            and bool(plan_summary.get("known", False))
            and str(plan_summary.get("strategy", "unknown")) == "plan_point_id"
        )
        if plan_known_for_slice and plan_point_order_ids:
            all_slice_n = sorted({int(key[1]) for key in per_slice_stats.keys()})
            for slice_n in all_slice_n:
                for idx, point_id in enumerate(plan_point_order_ids):
                    slice_i = int(idx % int(slice_n))
                    key = (slice_i, int(slice_n))
                    bucket = plan_ids_by_slice.setdefault(key, set())
                    bucket.add(str(point_id))
            plan_source = str(plan_summary.get("plan_source_sha256") or "").strip()
            for row in records_for_coverage:
                slice_i = row.get("slice_i")
                slice_n = row.get("slice_n")
                if not isinstance(slice_i, int) or not isinstance(slice_n, int):
                    continue
                key = (int(slice_i), int(slice_n))
                plan_bucket = plan_ids_by_slice.get(key)
                if not plan_bucket:
                    continue
                point_id = str(row.get("plan_point_id", "")).strip()
                if not point_id or point_id not in plan_bucket:
                    continue
                row_source = str(row.get("plan_source_sha256", "")).strip()
                if row_source and plan_source and row_source != plan_source:
                    continue
                seen_any_by_slice.setdefault(key, set()).add(point_id)
                if bool(row.get("eligible")):
                    seen_eligible_by_slice.setdefault(key, set()).add(point_id)

        for key in sorted(per_slice_stats.keys(), key=lambda item: (int(item[1]), int(item[0]))):
            row = per_slice_stats[key]
            status_map = _as_mapping(row.get("status_counts"))
            best_candidate = row.get("best_candidate")
            out_row: Dict[str, Any] = {
                "slice_i": int(row.get("slice_i", key[0])),
                "slice_n": int(row.get("slice_n", key[1])),
                "n_records": int(row.get("n_records", 0)),
                "status_counts": {k: int(v) for k, v in _line_sort(status_map)},
                "eligible_count": int(row.get("eligible_count", 0)),
                "best_chi2_total_eligible": (
                    float(best_candidate[0]) if isinstance(best_candidate, tuple) and len(best_candidate) >= 1 else None
                ),
                "best_plan_point_id": (
                    str(best_candidate[2]) if isinstance(best_candidate, tuple) and len(best_candidate) >= 3 else None
                ),
                "best_params_hash": (
                    str(best_candidate[1]) if isinstance(best_candidate, tuple) and len(best_candidate) >= 2 else None
                ),
            }
            if plan_known_for_slice:
                plan_total = int(len(plan_ids_by_slice.get(key, set())))
                seen_any = int(len(seen_any_by_slice.get(key, set())))
                seen_eligible = int(len(seen_eligible_by_slice.get(key, set())))
                out_row["plan_points_total_in_slice"] = int(plan_total)
                out_row["plan_points_seen_any_in_slice"] = int(seen_any)
                out_row["plan_points_seen_eligible_in_slice"] = int(seen_eligible)
                if plan_total > 0:
                    out_row["coverage_any_in_slice"] = float(seen_any / float(plan_total))
                    out_row["coverage_eligible_in_slice"] = float(seen_eligible / float(plan_total))
                else:
                    out_row["coverage_any_in_slice"] = None
                    out_row["coverage_eligible_in_slice"] = None
            slice_output.append(out_row)
        if slice_output:
            summary["slice_summary"] = slice_output
    return summary


def _format_text(summary: Mapping[str, Any], *, show_by_file: bool) -> str:
    lines: List[str] = []
    lines.append("Phase-2 E2 Live Status")
    lines.append(f"n_inputs={int(summary.get('n_inputs', 0))}")
    lines.append(f"n_files_expanded={int(summary.get('n_files_expanded', 0))}")
    lines.append(f"n_records_total={int(summary.get('n_records_total', 0))}")
    lines.append(f"n_records_parsed={int(summary.get('n_records_parsed', 0))}")
    lines.append(f"n_invalid_lines={int(summary.get('n_invalid_lines', 0))}")
    if "n_partial_tail_lines_skipped" in summary:
        lines.append(
            f"partial_tail_lines_skipped={int(summary.get('n_partial_tail_lines_skipped', 0))}"
        )
    lines.append(f"n_unique_params_hash={int(summary.get('n_unique_params_hash', 0))}")
    lines.append("")

    lines.append("Scan Config")
    lines.append(f"scan_config_sha256={str(summary.get('scan_config_sha256_chosen', 'unknown'))}")
    lines.append(f"scan_config_sha256_missing_count={int(summary.get('scan_config_sha256_missing_count', 0))}")
    scan_config_counts = _as_mapping(summary.get("scan_config_sha256_counts"))
    if scan_config_counts:
        parts: List[str] = []
        for key, count in sorted(((str(k), int(v)) for k, v in scan_config_counts.items()), key=lambda kv: str(kv[0])):
            label = "MISSING" if key == "__MISSING__" else key
            parts.append(f"{label}:{int(count)}")
        lines.append("scan_config_sha256_counts=" + ",".join(parts))
    else:
        lines.append("scan_config_sha256_counts=none")
    if bool(summary.get("scan_config_sha256_mixed", False)):
        lines.append("MIXED_SCAN_CONFIG_SHA256")
    lines.append("")

    lines.append("Status Counts")
    status_counts = _as_mapping(summary.get("status_counts"))
    for status, count in status_counts.items():
        lines.append(f"status={status} count={int(count)}")
    if not status_counts:
        lines.append("status=none count=0")
    lines.append("")

    lines.append("Error Summary")
    error_counts = _as_mapping(summary.get("error_counts"))
    if error_counts:
        for key, count in error_counts.items():
            lines.append(f"error={key} count={int(count)}")
    else:
        lines.append("error=none count=0")
    lines.append("")

    lines.append("Best Records (eligible)")
    best = _as_mapping(summary.get("best"))
    for label in ("overall", "plausible"):
        item = _as_mapping(best.get(label))
        if not item:
            lines.append(f"best_{label}=NA")
            continue
        lines.append(
            "best_{label}=params_hash:{params_hash} chi2_total:{chi2_total} chi2_cmb:{chi2_cmb} "
            "plan_point_id:{plan_point_id}".format(
                label=label,
                params_hash=str(item.get("params_hash", "")),
                chi2_total=_format_float(_finite_float(item.get("chi2_total"))),
                chi2_cmb=_format_float(_finite_float(item.get("chi2_cmb"))),
                plan_point_id=str(item.get("plan_point_id", "NA")),
            )
        )
    joint_item = _as_mapping(best.get("joint"))
    best_joint_value = _finite_float(joint_item.get("chi2_joint_total"))
    if best_joint_value is not None:
        lines.append(
            "best_joint=params_hash:{params_hash} chi2_joint_total:{chi2_joint_total} chi2_total:{chi2_total} "
            "chi2_cmb:{chi2_cmb} plan_point_id:{plan_point_id}".format(
                params_hash=str(joint_item.get("params_hash", "")),
                chi2_joint_total=_format_float(best_joint_value),
                chi2_total=_format_float(_finite_float(joint_item.get("chi2_total"))),
                chi2_cmb=_format_float(_finite_float(joint_item.get("chi2_cmb"))),
                plan_point_id=str(joint_item.get("plan_point_id", "NA")),
            )
        )
        lines.append(
            f"best_joint_rsd_chi2_field_used={str(joint_item.get('rsd_chi2_field_used') or 'NA')}"
        )
        lines.append(
            f"best_joint_rsd_chi2_weight={_format_float(_finite_float(joint_item.get('rsd_chi2_weight')))}"
        )
    lines.append("")

    lines.append("RSD overlay")
    rsd_overlay = _as_mapping(summary.get("rsd_overlay"))
    lines.append(f"rsd_overlay_present_records={int(rsd_overlay.get('present_records', 0))}")
    lines.append(f"rsd_overlay_ok_records={int(rsd_overlay.get('ok_records', 0))}")
    best_rsd_chi2 = _finite_float(rsd_overlay.get("best_chi2"))
    if best_rsd_chi2 is None:
        lines.append("best_rsd_chi2=n/a")
        lines.append("best_rsd_chi2_total=n/a")
        lines.append("best_rsd_params_hash=NA")
        lines.append("best_rsd_plan_point_id=NA")
        lines.append("best_rsd_transfer_model=NA")
        lines.append("best_rsd_primordial_ns=NA")
        lines.append("best_rsd_primordial_k_pivot_mpc=NA")
    else:
        lines.append(f"best_rsd_chi2={_format_float(best_rsd_chi2)}")
        lines.append(f"best_rsd_chi2_total={_format_float(_finite_float(rsd_overlay.get('best_chi2_total')))}")
        lines.append(f"best_rsd_params_hash={str(rsd_overlay.get('best_params_hash', 'NA'))}")
        lines.append(f"best_rsd_plan_point_id={str(rsd_overlay.get('best_plan_point_id', 'NA'))}")
        lines.append(f"best_rsd_transfer_model={str(rsd_overlay.get('best_transfer_model', 'NA'))}")
        lines.append(
            f"best_rsd_primordial_ns={_format_float(_finite_float(rsd_overlay.get('best_primordial_ns')))}"
        )
        lines.append(
            "best_rsd_primordial_k_pivot_mpc="
            f"{_format_float(_finite_float(rsd_overlay.get('best_primordial_k_pivot_mpc')))}"
        )
    transfer_counts = _as_mapping(rsd_overlay.get("transfer_model_counts"))
    if transfer_counts:
        parts = [
            f"{str(model)}:{int(count)}"
            for model, count in sorted(
                ((str(k), int(v)) for k, v in transfer_counts.items()),
                key=lambda kv: (-int(kv[1]), str(kv[0])),
            )
        ]
        lines.append("rsd_transfer_model_counts=" + ",".join(parts))
    else:
        lines.append("rsd_transfer_model_counts=none")

    drift_fields = list(summary.get("drift_fields_present") or [])
    if drift_fields:
        lines.append("drift_fields_present=" + ",".join(str(v) for v in drift_fields[:5]))
    else:
        lines.append("drift_fields_present=none")
    lines.append("")

    lines.append("Plan Coverage")
    plan_cov = _as_mapping(summary.get("plan_coverage"))
    if not plan_cov:
        lines.append("plan_coverage=not_requested")
    elif not bool(plan_cov.get("known", False)):
        lines.append("plan_coverage=unknown")
        lines.append(f"plan_strategy={str(plan_cov.get('strategy', 'unknown'))}")
    else:
        lines.append(f"plan_strategy={str(plan_cov.get('strategy', 'unknown'))}")
        lines.append(f"plan_points_total={int(plan_cov.get('plan_points_total', 0))}")
        lines.append(f"plan_points_seen_any={int(plan_cov.get('plan_points_seen_any', 0))}")
        lines.append(f"plan_points_seen_eligible={int(plan_cov.get('plan_points_seen_eligible', 0))}")
        lines.append(f"coverage_any={_format_float(_finite_float(plan_cov.get('coverage_any')))}")
        lines.append(f"coverage_eligible={_format_float(_finite_float(plan_cov.get('coverage_eligible')))}")
        lines.append(f"foreign_records={int(plan_cov.get('foreign_records', 0))}")
    lines.append("")

    if show_by_file:
        lines.append("By File")
        for row in list(summary.get("by_file") or []):
            data = _as_mapping(row)
            lines.append(
                "file={path} parsed={parsed} invalid={invalid}".format(
                    path=str(data.get("path", "")),
                    parsed=int(data.get("n_records_parsed", 0)),
                    invalid=int(data.get("n_invalid_lines", 0)),
                )
            )
            if "n_partial_tail_lines_skipped" in data:
                lines.append(
                    "  partial_tail_lines_skipped={value}".format(
                        value=int(data.get("n_partial_tail_lines_skipped", 0))
                    )
                )
            status_map = _as_mapping(data.get("status_counts"))
            for status, count in status_map.items():
                lines.append(f"  status={status} count={int(count)}")
            scan_map = _as_mapping(data.get("scan_config_sha256_counts"))
            if scan_map:
                parts: List[str] = []
                for key, count in sorted(((str(k), int(v)) for k, v in scan_map.items()), key=lambda kv: str(kv[0])):
                    label = "MISSING" if key == "__MISSING__" else key
                    parts.append(f"{label}:{int(count)}")
                lines.append(f"  scan_config_sha256_counts={','.join(parts)}")
        lines.append("")

    slice_summary = list(summary.get("slice_summary") or [])
    if slice_summary:
        lines.append("Slice summary")
        for item in slice_summary:
            row = _as_mapping(item)
            status_map = _as_mapping(row.get("status_counts"))
            ok_count = int(status_map.get("ok", 0))
            err_count = int(status_map.get("error", 0))
            line = (
                "slice={slice_i}/{slice_n} records={records} ok={ok} error={error} eligible={eligible} "
                "best_chi2={best_chi2}".format(
                    slice_i=int(row.get("slice_i", 0)),
                    slice_n=int(row.get("slice_n", 0)),
                    records=int(row.get("n_records", 0)),
                    ok=ok_count,
                    error=err_count,
                    eligible=int(row.get("eligible_count", 0)),
                    best_chi2=_format_float(_finite_float(row.get("best_chi2_total_eligible"))),
                )
            )
            if "coverage_any_in_slice" in row:
                line += " cov_any={cov_any} cov_elig={cov_elig}".format(
                    cov_any=_format_float(_finite_float(row.get("coverage_any_in_slice"))),
                    cov_elig=_format_float(_finite_float(row.get("coverage_eligible_in_slice"))),
                )
            lines.append(line)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    out = path.expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="phase2_e2_live_status",
        description="Instant/live status monitor for Phase-2 E2 JSONL scans and shard directories.",
    )
    ap.add_argument("--input", action="append", required=True, help="Input JSONL file, directory, or glob pattern (repeatable).")
    ap.add_argument("--plan", type=Path, default=None, help="Optional refine plan JSON for coverage accounting.")
    ap.add_argument("--mode", choices=["summary", "by_file"], default="summary")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--json-out", type=Path, default=None, help="Optional path to write JSON output.")
    ap.add_argument(
        "--require-plan-coverage",
        choices=["none", "any", "complete"],
        default="none",
        help="Optional plan coverage gate for exit code.",
    )
    ap.add_argument(
        "--eligible-status",
        choices=["ok_only", "any_eligible"],
        default="ok_only",
        help="Eligibility policy for best-record selection.",
    )
    ap.add_argument(
        "--tail-safe",
        action="store_true",
        help="Ignore a single invalid trailing line when file does not end with newline (active write safety).",
    )
    ap.add_argument(
        "--include-slice-summary",
        action="store_true",
        help="Emit per-slice progress summary when records carry plan_slice_i/plan_slice_n fields.",
    )
    args = ap.parse_args(argv)

    input_paths = _resolve_inputs([str(item) for item in (args.input or [])])
    if not input_paths:
        raise SystemExit("no JSONL inputs resolved from --input")

    plan_path = None if args.plan is None else args.plan.expanduser().resolve()
    if str(args.require_plan_coverage) != "none" and plan_path is None:
        raise SystemExit("--require-plan-coverage requires --plan")

    summary = _analyze(
        input_paths=input_paths,
        status_filter=str(args.eligible_status),
        mode=str(args.mode),
        plan_path=plan_path,
        tail_safe=bool(args.tail_safe),
        include_slice_summary=bool(args.include_slice_summary),
    )

    if args.json_out is not None:
        _write_json(args.json_out, summary)

    if str(args.format) == "json":
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(_format_text(summary, show_by_file=bool(str(args.mode) == "by_file")), end="")

    gate = str(args.require_plan_coverage)
    if gate == "none":
        return 0
    plan_cov = _as_mapping(summary.get("plan_coverage"))
    if not plan_cov or not bool(plan_cov.get("known", False)):
        return 2

    coverage_any = _finite_float(plan_cov.get("coverage_any"))
    if coverage_any is None:
        return 2
    if gate == "any":
        return 0 if float(coverage_any) > 0.0 else 2
    if gate == "complete":
        return 0 if float(coverage_any) >= 1.0 else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

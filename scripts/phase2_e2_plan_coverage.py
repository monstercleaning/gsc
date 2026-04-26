#!/usr/bin/env python3
"""Plan coverage accounting for ``phase2_e2_refine_plan_v1`` runs (stdlib-only)."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

V101_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V101_DIR))

from gsc.early_time.refine_plan_v1 import (  # noqa: E402
    get_plan_source_sha256,
    iter_plan_points,
    load_refine_plan_v1,
    write_refine_plan_v1,
)
from gsc.jsonl_io import open_text_read  # noqa: E402


def _to_json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Mapping):
        return {str(k): _to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_json_safe(v) for v in value]
    return str(value)


def _norm_status(value: Any) -> str:
    text = str(value).strip().lower()
    return text if text else "ok"


def _status_counts_as_success(status: str) -> bool:
    value = str(status).strip().lower()
    return value in {"ok", "skipped_drift"}


def _point_id_from_record(record: Mapping[str, Any]) -> str:
    raw = record.get("plan_point_id")
    if raw is None:
        return ""
    text = str(raw).strip()
    return text


def _source_sha_from_record(record: Mapping[str, Any]) -> str:
    raw = record.get("plan_source_sha256")
    if raw is None:
        return ""
    text = str(raw).strip()
    return text


def load_jsonl_records(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    with open_text_read(path) as fh:
        for line_no, line in enumerate(fh, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except Exception as exc:
                raise ValueError(f"invalid JSON at line {line_no} in {path}") from exc
            if not isinstance(payload, Mapping):
                continue
            records.append({str(k): _to_json_safe(v) for k, v in payload.items()})
    return records


def _plan_point_index(plan: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for point_id, point_obj, _ in iter_plan_points(plan):
        obj = copy.deepcopy(point_obj)
        obj["point_id"] = str(point_id)
        out[str(point_id)] = obj
    return out


def analyze_plan_coverage(
    *,
    plan_payload: Mapping[str, Any],
    records: Iterable[Mapping[str, Any]],
    plan_path: str,
    jsonl_path: str,
    max_id_list: int = 50,
) -> Tuple[Dict[str, Any], List[str], List[str], Dict[str, Dict[str, Any]]]:
    points_by_id = _plan_point_index(plan_payload)
    plan_ids = sorted(points_by_id.keys())
    plan_source_sha = str(get_plan_source_sha256(plan_payload))

    status_counts: Dict[str, int] = {}
    matched_ok_by_id: Dict[str, bool] = {}
    matched_seen_by_id: Dict[str, int] = {}
    n_records_total = 0
    n_matching = 0
    n_foreign = 0
    n_unmapped = 0

    for record in records:
        n_records_total += 1
        point_id = _point_id_from_record(record)
        source_sha = _source_sha_from_record(record)
        is_foreign = bool(source_sha and plan_source_sha and source_sha != plan_source_sha)
        if is_foreign:
            n_foreign += 1
        if not point_id:
            n_unmapped += 1
            continue
        if point_id not in points_by_id:
            continue
        if is_foreign:
            continue

        n_matching += 1
        status = _norm_status(record.get("status"))
        status_counts[status] = int(status_counts.get(status, 0)) + 1
        matched_seen_by_id[point_id] = int(matched_seen_by_id.get(point_id, 0)) + 1
        if _status_counts_as_success(status):
            matched_ok_by_id[point_id] = True

    missing_ids = sorted(pid for pid in plan_ids if pid not in matched_seen_by_id)
    failed_ids = sorted(pid for pid in plan_ids if pid in matched_seen_by_id and not matched_ok_by_id.get(pid, False))
    max_ids = max(0, int(max_id_list))

    coverage = {
        "schema": "phase2_e2_plan_coverage_v1",
        "plan_path": str(plan_path),
        "jsonl_path": str(jsonl_path),
        "plan_source_sha256": str(plan_source_sha),
        "counts": {
            "n_plan_points": int(len(plan_ids)),
            "n_records_total": int(n_records_total),
            "n_records_matching_plan": int(n_matching),
            "n_records_foreign": int(n_foreign),
            "n_records_unmapped": int(n_unmapped),
            "n_unique_point_ids_matching_plan": int(len(matched_seen_by_id)),
            "n_missing": int(len(missing_ids)),
            "n_failed": int(len(failed_ids)),
            "status_counts_matching_plan": {
                key: int(status_counts[key]) for key in sorted(status_counts.keys())
            },
        },
        "missing_plan_point_ids": list(missing_ids[:max_ids]),
        "failed_plan_point_ids": list(failed_ids[:max_ids]),
    }
    return coverage, missing_ids, failed_ids, points_by_id


def build_rerun_plan(
    *,
    parent_plan: Mapping[str, Any],
    selected_point_ids: Sequence[str],
    points_by_id: Mapping[str, Mapping[str, Any]],
    reason: str,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = copy.deepcopy(dict(parent_plan))
    selected: List[Dict[str, Any]] = []
    for point_id in sorted(str(pid) for pid in selected_point_ids):
        raw = points_by_id.get(point_id)
        if raw is None:
            continue
        point_obj = copy.deepcopy(dict(raw))
        point_obj["point_id"] = str(point_id)
        selected.append(point_obj)
    payload["points"] = selected
    payload["derived_from_plan_source_sha256"] = str(get_plan_source_sha256(parent_plan))
    payload["derived_reason"] = str(reason)
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    out = path.expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="phase2_e2_plan_coverage",
        description="Compute coverage of phase2_e2_refine_plan_v1 points against scan JSONL results.",
    )
    ap.add_argument("--plan", required=True, type=Path, help="Refine plan JSON (phase2_e2_refine_plan_v1).")
    ap.add_argument("--jsonl", required=True, type=Path, help="Scan JSONL results file.")
    ap.add_argument("--out", type=Path, default=None, help="Optional path to write coverage JSON.")
    ap.add_argument("--strict", action="store_true", help="Exit non-zero when missing/failed points are present.")
    ap.add_argument("--emit-missing-plan", type=Path, default=None, help="Optional rerun plan path for missing points.")
    ap.add_argument("--emit-failed-plan", type=Path, default=None, help="Optional rerun plan path for failed points.")
    ap.add_argument("--max-id-list", type=int, default=50, help="Maximum number of IDs included in output lists.")
    args = ap.parse_args(argv)

    plan_path = args.plan.expanduser().resolve()
    jsonl_path = args.jsonl.expanduser().resolve()

    try:
        plan_payload = load_refine_plan_v1(plan_path)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if not jsonl_path.is_file():
        print(f"scan JSONL file not found: {jsonl_path}", file=sys.stderr)
        return 1
    try:
        records = load_jsonl_records(jsonl_path)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    coverage, missing_ids, failed_ids, points_by_id = analyze_plan_coverage(
        plan_payload=plan_payload,
        records=records,
        plan_path=str(plan_path),
        jsonl_path=str(jsonl_path),
        max_id_list=int(args.max_id_list),
    )

    if args.out is not None:
        _write_json(args.out, coverage)
    print(json.dumps(coverage, indent=2, sort_keys=True))

    if args.emit_missing_plan is not None:
        missing_plan = build_rerun_plan(
            parent_plan=plan_payload,
            selected_point_ids=missing_ids,
            points_by_id=points_by_id,
            reason="missing",
        )
        write_refine_plan_v1(args.emit_missing_plan, missing_plan)
    if args.emit_failed_plan is not None:
        failed_plan = build_rerun_plan(
            parent_plan=plan_payload,
            selected_point_ids=failed_ids,
            points_by_id=points_by_id,
            reason="failed",
        )
        write_refine_plan_v1(args.emit_failed_plan, failed_plan)

    if not bool(args.strict):
        return 0
    if int(coverage["counts"]["n_missing"]) > 0:
        return 2
    if int(coverage["counts"]["n_failed"]) > 0:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

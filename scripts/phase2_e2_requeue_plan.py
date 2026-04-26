#!/usr/bin/env python3
"""Generate deterministic requeue refine plans from Phase-2 E2 JSONL results.

This tool is stdlib-only and additive. It reads a source refine plan and one or
more result JSONL inputs (files/directories/globs), classifies each plan point,
and emits a reduced refine plan for missing/unresolved/errors-only reruns.
"""

from __future__ import annotations

import argparse
import copy
import glob
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


V101_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V101_DIR))

from gsc.early_time.refine_plan_v1 import (  # noqa: E402
    iter_plan_points,
    load_refine_plan_v1,
    write_refine_plan_v1,
)
from gsc.jsonl_io import open_text_read  # noqa: E402


SCHEMA_ID = "phase2_e2_requeue_plan_v1"


def _json_dump(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_float_params(params: Mapping[str, Any]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for key in sorted(str(k) for k in params.keys()):
        value = params.get(key)
        try:
            out[str(key)] = float(value)
        except Exception:
            continue
    return out


def _fallback_params_hash(params: Mapping[str, Any]) -> str:
    payload = _canonical_float_params(params)
    return _sha256_text(_json_dump(payload))


def _norm_status(value: Any) -> str:
    if value is None:
        return "unknown"
    text = str(value).strip().lower()
    return text if text else "unknown"


def _nonempty_error_field(record: Mapping[str, Any]) -> bool:
    value = record.get("error")
    if value is None:
        return False
    if isinstance(value, Mapping):
        return any(str(v).strip() for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(str(v).strip() for v in value)
    return bool(str(value).strip())


def _resolve_inputs(tokens: Sequence[str]) -> List[Path]:
    resolved: List[Path] = []
    seen: Set[Path] = set()

    def _iter_jsonl_files(path: Path) -> List[Path]:
        files: List[Path] = []
        local_seen: Set[Path] = set()
        for jsonl in sorted(list(path.glob("*.jsonl")) + list(path.glob("*.jsonl.gz"))):
            rp = jsonl.resolve()
            if rp in local_seen or not rp.is_file():
                continue
            local_seen.add(rp)
            files.append(rp)
        return files

    for raw in tokens:
        token = str(raw).strip()
        if not token:
            continue
        if any(ch in token for ch in "*?["):
            matches = sorted(Path(p).expanduser().resolve() for p in glob.glob(token))
            if not matches:
                raise ValueError(f"glob input matched no files: {token}")
            for path in matches:
                if path in seen:
                    continue
                seen.add(path)
                if path.is_file():
                    resolved.append(path)
                    continue
                if path.is_dir():
                    for rp in _iter_jsonl_files(path):
                        if rp in seen:
                            continue
                        seen.add(rp)
                        resolved.append(rp)
                    continue
                raise ValueError(f"input path is neither file nor directory: {path}")
            continue

        path = Path(token).expanduser().resolve()
        if not path.exists():
            raise ValueError(f"input path not found: {token}")
        if path in seen:
            continue
        seen.add(path)
        if path.is_file():
            resolved.append(path)
            continue
        if path.is_dir():
            for rp in _iter_jsonl_files(path):
                if rp in seen:
                    continue
                seen.add(rp)
                resolved.append(rp)
            continue
        raise ValueError(f"input path is neither file nor directory: {token}")

    resolved_sorted = sorted(resolved, key=lambda p: str(p))
    return resolved_sorted


def _plan_point_key(point_obj: Mapping[str, Any], params: Mapping[str, Any], idx: int) -> str:
    for field in ("plan_point_id", "point_id"):
        raw = point_obj.get(field)
        if raw is None:
            continue
        text = str(raw).strip()
        if text:
            return text
    raw_hash = point_obj.get("params_hash")
    if isinstance(raw_hash, str) and raw_hash.strip():
        return raw_hash.strip()
    return _fallback_params_hash(params)


def _record_key(record: Mapping[str, Any], *, line_text: str) -> Tuple[str, str]:
    raw = record.get("plan_point_id")
    if raw is not None:
        text = str(raw).strip()
        if text:
            return text, "plan_point_id"
    raw_hash = record.get("params_hash")
    if isinstance(raw_hash, str) and raw_hash.strip():
        return raw_hash.strip(), "params_hash"
    return _sha256_text(line_text), "fallback_line_hash"


def _build_requeue_plan(
    *,
    parent_plan: Mapping[str, Any],
    selected_point_objs: Sequence[Mapping[str, Any]],
    source_plan_sha256: str,
    select_mode: str,
    final_status: Sequence[str],
    final_prefixes: Sequence[str],
    error_status: Sequence[str],
    input_descriptor_sha256: str,
) -> Dict[str, Any]:
    out = copy.deepcopy(dict(parent_plan))
    out["points"] = [copy.deepcopy(dict(point)) for point in selected_point_objs]
    out["requeue_source_plan_sha256"] = str(source_plan_sha256)
    out["requeue_select"] = str(select_mode)
    out["requeue_final_status"] = [str(s) for s in final_status]
    out["requeue_final_status_prefix"] = [str(s) for s in final_prefixes]
    out["requeue_error_status"] = [str(s) for s in error_status]
    out["requeue_inputs_sha256"] = str(input_descriptor_sha256)
    return out


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    out = path.expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _format_text(summary: Mapping[str, Any]) -> str:
    lines: List[str] = []
    lines.append("== Inputs ==")
    lines.append(f"n_inputs={int(summary.get('n_inputs', 0))}")
    lines.append(f"n_files_expanded={int(summary.get('n_files_expanded', 0))}")
    lines.append(f"n_records_parsed={int(summary.get('n_records_parsed', 0))}")
    lines.append(f"n_invalid_lines={int(summary.get('n_invalid_lines', 0))}")
    lines.append(f"n_unmatched_records={int(summary.get('n_unmatched_records', 0))}")
    lines.append("")

    lines.append("== Plan ==")
    lines.append(f"plan_points_total={int(summary.get('plan_points_total', 0))}")
    lines.append("")

    lines.append("== Classification ==")
    lines.append(f"seen_any={int(summary.get('seen_any', 0))}")
    lines.append(f"seen_final={int(summary.get('seen_final', 0))}")
    lines.append(f"missing={int(summary.get('missing', 0))}")
    lines.append(f"unresolved={int(summary.get('unresolved', 0))}")
    lines.append(f"errors_only={int(summary.get('errors_only', 0))}")
    lines.append("")

    lines.append("== Selection ==")
    lines.append(f"select={str(summary.get('select', 'unresolved'))}")
    lines.append(f"selected={int(summary.get('selected', 0))}")
    lines.append(f"limit={summary.get('limit') if summary.get('limit') is not None else 'none'}")
    lines.append(f"output_plan={str(summary.get('output_plan', ''))}")
    return "\n".join(lines) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="phase2_e2_requeue_plan",
        description="Generate requeue refine plans from existing Phase-2 E2 JSONL results.",
    )
    ap.add_argument("--plan", required=True, type=Path, help="Input refine plan JSON.")
    ap.add_argument(
        "--input",
        action="append",
        required=True,
        help="Input JSONL file, directory, or glob pattern (repeatable).",
    )
    ap.add_argument(
        "--select",
        choices=["missing", "unresolved", "errors"],
        default="unresolved",
        help="Selection mode for output plan points.",
    )
    ap.add_argument(
        "--final-status",
        action="append",
        default=[],
        help="Status values considered final (repeatable, additive).",
    )
    ap.add_argument(
        "--final-status-prefix",
        action="append",
        default=[],
        help="Status prefixes considered final (repeatable, additive).",
    )
    ap.add_argument(
        "--error-status",
        action="append",
        default=[],
        help="Status values considered error (repeatable, additive).",
    )
    ap.add_argument(
        "--error-if-has-error-field",
        action="store_true",
        dest="error_if_has_error_field",
        default=True,
        help="Treat non-empty error field as error-ish (default: on).",
    )
    ap.add_argument(
        "--no-error-if-has-error-field",
        action="store_false",
        dest="error_if_has_error_field",
        help="Ignore non-empty error field for error-ish classification.",
    )
    ap.add_argument("--limit", type=int, default=None, help="Optional max selected points (plan order).")
    ap.add_argument("--output-plan", required=True, type=Path, help="Path to output requeue plan JSON.")
    ap.add_argument("--format", choices=["text", "json"], default="text", help="Stdout format.")
    ap.add_argument("--json-out", type=Path, default=None, help="Optional JSON summary output path.")
    args = ap.parse_args(argv)

    if args.limit is not None and int(args.limit) < 0:
        print("--limit must be >= 0", file=sys.stderr)
        return 1

    final_status = ["ok"] + [str(x).strip().lower() for x in list(args.final_status or []) if str(x).strip()]
    final_status_set = set(final_status)
    final_prefixes = ["skipped_"] + [str(x).strip().lower() for x in list(args.final_status_prefix or []) if str(x).strip()]
    error_status = ["error"] + [str(x).strip().lower() for x in list(args.error_status or []) if str(x).strip()]
    error_status_set = set(error_status)

    try:
        input_files = _resolve_inputs([str(x) for x in list(args.input or [])])
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if not input_files:
        print("no JSONL files resolved from --input", file=sys.stderr)
        return 1

    plan_path = args.plan.expanduser().resolve()
    try:
        plan_payload = load_refine_plan_v1(plan_path)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    plan_source_sha256 = _sha256_file(plan_path)

    plan_order: List[str] = []
    plan_key_to_point: Dict[str, Dict[str, Any]] = {}
    plan_hash_to_key: Dict[str, str] = {}
    ambiguous_plan_hashes: Set[str] = set()
    for idx, (_, point_obj, params) in enumerate(iter_plan_points(plan_payload)):
        key = _plan_point_key(point_obj, params, idx)
        if key in plan_key_to_point:
            print(f"duplicate plan key detected: {key}", file=sys.stderr)
            return 1
        plan_order.append(key)
        plan_key_to_point[key] = copy.deepcopy(dict(point_obj))
        params_hash = point_obj.get("params_hash")
        if isinstance(params_hash, str) and params_hash.strip():
            point_hash = params_hash.strip()
        else:
            point_hash = _fallback_params_hash(params)
        if point_hash in ambiguous_plan_hashes:
            continue
        prior = plan_hash_to_key.get(point_hash)
        if prior is None:
            plan_hash_to_key[point_hash] = key
        elif prior != key:
            ambiguous_plan_hashes.add(point_hash)
            del plan_hash_to_key[point_hash]

    # Per-plan-point flags
    seen_any: Set[str] = set()
    seen_final: Set[str] = set()
    seen_ok: Set[str] = set()
    seen_error: Set[str] = set()

    n_records_parsed = 0
    n_invalid_lines = 0
    n_unmatched_records = 0

    file_descriptors: List[Dict[str, Any]] = []

    for path in input_files:
        file_descriptors.append(
            {
                "path": str(path),
                "sha256": _sha256_file(path),
                "bytes": int(path.stat().st_size),
            }
        )
        with open_text_read(path) as fh:
            for line in fh:
                text = line.strip()
                if not text:
                    continue
                try:
                    payload = json.loads(text)
                except Exception:
                    n_invalid_lines += 1
                    continue
                if not isinstance(payload, Mapping):
                    n_invalid_lines += 1
                    continue
                record = {str(k): payload[k] for k in payload.keys()}
                n_records_parsed += 1
                key, key_kind = _record_key(record, line_text=text)
                matched_key = key
                if matched_key not in plan_key_to_point and key_kind == "params_hash":
                    mapped = plan_hash_to_key.get(key)
                    if mapped is not None:
                        matched_key = mapped
                if matched_key not in plan_key_to_point:
                    n_unmatched_records += 1
                    continue

                status = _norm_status(record.get("status"))
                seen_any.add(matched_key)

                is_final = status in final_status_set or any(
                    status.startswith(prefix) for prefix in final_prefixes
                )
                if is_final:
                    seen_final.add(matched_key)

                if status == "ok":
                    seen_ok.add(matched_key)

                is_error = status in error_status_set
                if not is_error and bool(args.error_if_has_error_field):
                    is_error = _nonempty_error_field(record)
                if is_error:
                    seen_error.add(matched_key)

    missing_keys = [key for key in plan_order if key not in seen_any]
    unresolved_keys = [key for key in plan_order if key not in seen_final]
    errors_only_keys = [key for key in plan_order if key in seen_error and key not in seen_ok]

    select_mode = str(args.select)
    if select_mode == "missing":
        selected_keys = list(missing_keys)
    elif select_mode == "errors":
        selected_keys = list(errors_only_keys)
    else:
        selected_keys = list(unresolved_keys)

    if args.limit is not None:
        selected_keys = selected_keys[: int(args.limit)]

    selected_points = [plan_key_to_point[key] for key in selected_keys]

    descriptor_payload = {
        "files": sorted(file_descriptors, key=lambda item: str(item["path"])),
        "n_files": int(len(input_files)),
    }
    requeue_inputs_sha256 = _sha256_text(_json_dump(descriptor_payload))

    requeue_plan = _build_requeue_plan(
        parent_plan=plan_payload,
        selected_point_objs=selected_points,
        source_plan_sha256=plan_source_sha256,
        select_mode=select_mode,
        final_status=final_status,
        final_prefixes=final_prefixes,
        error_status=error_status,
        input_descriptor_sha256=requeue_inputs_sha256,
    )
    write_refine_plan_v1(args.output_plan, requeue_plan)

    summary: Dict[str, Any] = {
        "schema": SCHEMA_ID,
        "plan_path": str(plan_path),
        "output_plan": str(args.output_plan.expanduser().resolve()),
        "select": select_mode,
        "limit": None if args.limit is None else int(args.limit),
        "n_inputs": int(len(args.input or [])),
        "n_files_expanded": int(len(input_files)),
        "n_records_parsed": int(n_records_parsed),
        "n_invalid_lines": int(n_invalid_lines),
        "n_unmatched_records": int(n_unmatched_records),
        "plan_points_total": int(len(plan_order)),
        "seen_any": int(len(seen_any)),
        "seen_final": int(len(seen_final)),
        "missing": int(len(missing_keys)),
        "unresolved": int(len(unresolved_keys)),
        "errors_only": int(len(errors_only_keys)),
        "selected": int(len(selected_keys)),
        "selected_plan_point_ids": [str(k) for k in selected_keys],
        "inputs_expanded": [str(p) for p in input_files],
    }

    if args.json_out is not None:
        _write_json(args.json_out, summary)

    if str(args.format) == "json":
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(_format_text(summary), end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

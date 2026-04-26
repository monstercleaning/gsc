#!/usr/bin/env python3
"""Compare two Phase-2 E2 scan JSONL outputs on identical points.

This tool is stdlib-only and designed for numerics/recombination robustness
cross-checks where two runs share the same plan points (`plan_point_id`) or
parameter hashes (`params_hash`).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import re
import sys
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

V101_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V101_DIR))

from gsc.jsonl_io import open_text_read  # noqa: E402


_HEADER_HINT_KEYS: Tuple[str, ...] = ("status", "params_hash", "plan_point_id")
_NUMERIC_SORT_RE = re.compile(r"^-?\d+$")


def _finite_float(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if not isinstance(value, (int, float)):
        return None
    out = float(value)
    if not math.isfinite(out):
        return None
    return out


def _format_value(value: Any, *, float_format: str) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(int(value))
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return str(float_format.format(value))
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if isinstance(value, (list, tuple)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def _get_path(obj: Mapping[str, Any], path: str) -> Any:
    cur: Any = obj
    for part in str(path).split("."):
        if not isinstance(cur, Mapping):
            return None
        if part not in cur:
            return None
        cur = cur[part]
    return cur


def _iter_scalar_paths(obj: Any, *, prefix: str = "") -> Iterable[str]:
    if isinstance(obj, Mapping):
        for key in sorted(str(k) for k in obj.keys()):
            child = f"{prefix}.{key}" if prefix else key
            yield from _iter_scalar_paths(obj[key], prefix=child)
        return
    if isinstance(obj, (list, tuple)):
        return
    if prefix:
        yield prefix


def _looks_like_data_record(obj: Mapping[str, Any]) -> bool:
    return any(key in obj for key in _HEADER_HINT_KEYS)


def _extract_match_value(
    *,
    obj: Mapping[str, Any],
    match_key: str,
    source: Path,
    line_no: int,
) -> str:
    raw = obj.get(match_key)
    if raw is None:
        if match_key == "plan_point_id":
            raise SystemExit(
                f"{source}:{line_no}: missing plan_point_id required by --match-key=plan_point_id. "
                "Run scans with --plan to emit plan_point_id."
            )
        raise SystemExit(f"{source}:{line_no}: missing {match_key!r} required by --match-key={match_key}.")
    text = str(raw).strip()
    if not text:
        raise SystemExit(f"{source}:{line_no}: empty {match_key!r} is not valid for matching.")
    return text


def _load_index(
    *,
    path: Path,
    match_key: str,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, int]]:
    stats = {
        "n_lines_total": 0,
        "n_parsed": 0,
        "n_data_records": 0,
        "n_skipped_invalid_json": 0,
        "n_skipped_non_object": 0,
        "n_skipped_non_data": 0,
    }
    index: Dict[str, Dict[str, Any]] = {}
    rp = path.expanduser().resolve()
    if not rp.is_file():
        raise SystemExit(f"Input JSONL not found: {rp}")

    with open_text_read(rp) as fh:
        for line_no, line in enumerate(fh, start=1):
            stats["n_lines_total"] += 1
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            try:
                payload = json.loads(text)
            except Exception:
                stats["n_skipped_invalid_json"] += 1
                continue
            stats["n_parsed"] += 1
            if not isinstance(payload, Mapping):
                stats["n_skipped_non_object"] += 1
                continue
            obj = {str(k): v for k, v in payload.items()}
            if not _looks_like_data_record(obj):
                stats["n_skipped_non_data"] += 1
                continue

            key = _extract_match_value(obj=obj, match_key=match_key, source=rp, line_no=line_no)
            if key in index:
                prev = index[key]
                raise SystemExit(
                    f"Duplicate match key {match_key}={key!r} in {rp}: lines "
                    f"{prev.get('_line_no')} and {line_no}."
                )

            obj["_source_file"] = str(rp)
            obj["_line_no"] = int(line_no)
            index[key] = obj
            stats["n_data_records"] += 1

    return index, stats


def _status_is_ok(obj: Mapping[str, Any]) -> bool:
    raw = obj.get("status", "ok")
    return str(raw).strip().lower() == "ok"


def _any_path_present(records: Sequence[Mapping[str, Any]], path: str) -> bool:
    for rec in records:
        if _get_path(rec, path) is not None:
            return True
    return False


def _discover_drift_paths(records: Sequence[Mapping[str, Any]]) -> List[str]:
    preferred = [
        "drift_pass",
        "drift_required_pass",
        "drift_margin",
        "drift.min_z_dot",
        "drift_sign_z2_5",
        "min_zdot_si",
        "chi2_parts.drift.min_zdot_si",
        "chi2_parts.drift.penalty",
    ]
    all_scalar_paths: set[str] = set()
    for rec in records:
        all_scalar_paths.update(_iter_scalar_paths(rec))

    out: List[str] = []
    for path in preferred:
        if path in all_scalar_paths:
            out.append(path)

    extras = sorted(p for p in all_scalar_paths if "drift" in p.lower() and p not in out)
    out.extend(extras)
    return out


def _unique_preserve_order(items: Sequence[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for item in items:
        key = str(item).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _build_preset_fields(*, preset: str, records: Sequence[Mapping[str, Any]]) -> List[str]:
    core_candidates = [
        "chi2_total",
        "chi2_parts.cmb.chi2",
        "chi2_parts.late_time.chi2",
        "microphysics_plausible_ok",
        "microphysics_penalty",
        "microphysics_max_rel_dev",
        "rd_early",
        "r_d",
        "rd_Mpc",
        "recombination_method",
        "drag_method",
        "cmb_num_method",
        "cmb_num_n_eval_dm",
        "cmb_num_err_dm",
        "cmb_num_n_eval_rs",
        "cmb_num_err_rs",
        "cmb_num_n_eval_rs_drag",
        "cmb_num_err_rs_drag",
        "cmb_num_rtol",
        "cmb_num_atol",
        "numerics.method",
        "numerics.n_eval",
        "numerics.err_est",
        "numerics.rtol",
        "numerics.atol",
        "robustness.recombination.method",
        "robustness.drag.method",
    ]
    extended_candidates = [
        "cmb_pred.R",
        "cmb_pred.lA",
        "cmb_pred.omega_b_h2",
        "cmb_pred.z_star",
        "cmb_pred.z_drag",
        "cmb_pred.D_M_Mpc",
        "cmb_pred.r_s_Mpc",
        "R",
        "lA",
        "theta_star",
        "z_star",
        "z_drag",
        "bridge_H_ratio",
    ]

    drift_fields = _discover_drift_paths(records)
    fields: List[str] = [p for p in core_candidates if _any_path_present(records, p)]
    fields.extend(drift_fields)
    if str(preset) == "extended":
        fields.extend([p for p in extended_candidates if _any_path_present(records, p)])
    return _unique_preserve_order(fields)


def _parse_fields_arg(value: str) -> List[str]:
    parts = [p.strip() for p in str(value).split(",")]
    return _unique_preserve_order(parts)


def _parse_fail_thresholds(raw_values: Sequence[str]) -> List[Tuple[str, float]]:
    out: List[Tuple[str, float]] = []
    for raw in raw_values:
        text = str(raw).strip()
        if not text:
            continue
        if ":" not in text:
            raise SystemExit(f"Invalid --fail-on-max-abs {text!r}; expected FIELD:THRESH")
        field, raw_thresh = text.split(":", 1)
        field = field.strip()
        if not field:
            raise SystemExit(f"Invalid --fail-on-max-abs {text!r}; empty FIELD")
        try:
            thresh = float(raw_thresh.strip())
        except Exception as exc:
            raise SystemExit(f"Invalid --fail-on-max-abs {text!r}; THRESH must be float") from exc
        if not (math.isfinite(thresh) and thresh >= 0.0):
            raise SystemExit(f"Invalid --fail-on-max-abs {text!r}; THRESH must be finite and >= 0")
        out.append((field, float(thresh)))
    return out


def _median(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    arr = sorted(float(v) for v in values)
    n = len(arr)
    m = n // 2
    if n % 2 == 1:
        return float(arr[m])
    return float((arr[m - 1] + arr[m]) * 0.5)


def _sort_keys(keys: Sequence[str], *, match_key: str) -> List[str]:
    if str(match_key) == "plan_point_id" and all(_NUMERIC_SORT_RE.match(k or "") for k in keys):
        return sorted(keys, key=lambda x: int(x))
    return sorted(keys)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Compare two E2 scan JSONL outputs.")
    ap.add_argument("--jsonl-a", type=Path, required=True)
    ap.add_argument("--jsonl-b", type=Path, required=True)
    ap.add_argument("--out-tsv", type=Path, required=True)
    ap.add_argument("--match-key", choices=["plan_point_id", "params_hash"], default="plan_point_id")
    ap.add_argument(
        "--require-status-ok",
        dest="require_status_ok",
        action="store_true",
        default=True,
        help="Only compare points where both status fields are 'ok' (default).",
    )
    ap.add_argument(
        "--no-require-status-ok",
        dest="require_status_ok",
        action="store_false",
        help="Compare matched points regardless of status fields.",
    )
    ap.add_argument(
        "--fields",
        type=str,
        default="",
        help="Comma-separated dotted field paths to compare.",
    )
    ap.add_argument("--preset", choices=["core", "extended"], default="core")
    ap.add_argument(
        "--fail-on-max-abs",
        action="append",
        default=[],
        metavar="FIELD:THRESH",
        help="Fail with non-zero exit if max(abs(delta)) for FIELD exceeds THRESH.",
    )
    ap.add_argument(
        "--float-format",
        type=str,
        default="{:.8g}",
        help="Python format string used for finite float rendering.",
    )
    args = ap.parse_args(argv)

    try:
        _ = args.float_format.format(1.2345)
    except Exception as exc:
        raise SystemExit(f"Invalid --float-format {args.float_format!r}") from exc

    fail_thresholds = _parse_fail_thresholds(args.fail_on_max_abs)
    index_a, stats_a = _load_index(path=args.jsonl_a, match_key=str(args.match_key))
    index_b, stats_b = _load_index(path=args.jsonl_b, match_key=str(args.match_key))

    only_a = _sort_keys(sorted(set(index_a.keys()) - set(index_b.keys())), match_key=str(args.match_key))
    only_b = _sort_keys(sorted(set(index_b.keys()) - set(index_a.keys())), match_key=str(args.match_key))
    matched_all = _sort_keys(sorted(set(index_a.keys()) & set(index_b.keys())), match_key=str(args.match_key))

    if args.require_status_ok:
        matched = [k for k in matched_all if _status_is_ok(index_a[k]) and _status_is_ok(index_b[k])]
    else:
        matched = list(matched_all)

    records_for_discovery: List[Mapping[str, Any]] = [index_a[k] for k in matched] + [index_b[k] for k in matched]
    if args.fields.strip():
        fields = _parse_fields_arg(args.fields)
    else:
        fields = _build_preset_fields(preset=str(args.preset), records=records_for_discovery)

    header: List[str] = [
        str(args.match_key),
        "plan_point_id",
        "params_hash_a",
        "params_hash_b",
        "status_a",
        "status_b",
    ]
    for field in fields:
        header.extend([f"{field}_a", f"{field}_b", f"d_{field}"])

    deltas_by_field: Dict[str, List[float]] = {field: [] for field in fields}
    rows: List[List[str]] = []
    for key in matched:
        rec_a = index_a[key]
        rec_b = index_b[key]
        plan_point_id = rec_a.get("plan_point_id", rec_b.get("plan_point_id"))
        base = [
            str(key),
            _format_value(plan_point_id, float_format=args.float_format),
            _format_value(rec_a.get("params_hash"), float_format=args.float_format),
            _format_value(rec_b.get("params_hash"), float_format=args.float_format),
            _format_value(rec_a.get("status", "ok"), float_format=args.float_format),
            _format_value(rec_b.get("status", "ok"), float_format=args.float_format),
        ]
        for field in fields:
            va = _get_path(rec_a, field)
            vb = _get_path(rec_b, field)
            fa = _finite_float(va)
            fb = _finite_float(vb)
            if fa is not None and fb is not None:
                delta = float(fb - fa)
                deltas_by_field[field].append(abs(delta))
                fd = _format_value(delta, float_format=args.float_format)
            else:
                fd = ""
            base.extend(
                [
                    _format_value(va, float_format=args.float_format),
                    _format_value(vb, float_format=args.float_format),
                    fd,
                ]
            )
        rows.append(base)

    out_path = args.out_tsv.expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t", lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)

    print(f"N_a_total: {len(index_a)}")
    print(f"N_b_total: {len(index_b)}")
    print(f"N_matched: {len(matched_all)}")
    print(f"N_compared: {len(matched)}")
    print(f"N_only_a: {len(only_a)}")
    print(f"N_only_b: {len(only_b)}")
    print(f"status_filter: {'ok_only' if args.require_status_ok else 'any'}")
    print(f"fields_compared: {len(fields)}")
    print(f"out_tsv: {out_path}")
    print(
        "A_stats: "
        f"lines={stats_a['n_lines_total']} parsed={stats_a['n_parsed']} "
        f"data={stats_a['n_data_records']} skip_json={stats_a['n_skipped_invalid_json']} "
        f"skip_obj={stats_a['n_skipped_non_object']} skip_non_data={stats_a['n_skipped_non_data']}"
    )
    print(
        "B_stats: "
        f"lines={stats_b['n_lines_total']} parsed={stats_b['n_parsed']} "
        f"data={stats_b['n_data_records']} skip_json={stats_b['n_skipped_invalid_json']} "
        f"skip_obj={stats_b['n_skipped_non_object']} skip_non_data={stats_b['n_skipped_non_data']}"
    )

    field_stats: Dict[str, Dict[str, float]] = {}
    for field in fields:
        values = deltas_by_field.get(field) or []
        if not values:
            continue
        mean_abs = float(sum(values) / len(values))
        median_abs = _median(values)
        max_abs = float(max(values))
        field_stats[field] = {
            "max_abs_delta": max_abs,
            "mean_abs_delta": mean_abs,
            "median_abs_delta": 0.0 if median_abs is None else float(median_abs),
            "n_numeric": float(len(values)),
        }
        print(
            f"FIELD {field}: "
            f"n={len(values)} "
            f"max_abs={args.float_format.format(max_abs)} "
            f"mean_abs={args.float_format.format(mean_abs)} "
            f"median_abs={args.float_format.format(field_stats[field]['median_abs_delta'])}"
        )

    failures: List[str] = []
    for field, threshold in fail_thresholds:
        stats = field_stats.get(field)
        if stats is None:
            failures.append(f"{field}: no numeric deltas available (threshold={threshold})")
            continue
        max_abs = float(stats["max_abs_delta"])
        if max_abs > float(threshold):
            failures.append(
                f"{field}: max_abs_delta={args.float_format.format(max_abs)} exceeds {args.float_format.format(threshold)}"
            )

    if failures:
        for line in failures:
            print(f"FAIL threshold: {line}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

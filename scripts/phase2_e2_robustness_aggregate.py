#!/usr/bin/env python3
"""Aggregate robustness metrics across multiple E2 scan JSONL outputs.

Stdlib-only tool for multi-run robustness checks over shared `params_hash` points.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

V101_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V101_DIR))

from gsc.jsonl_io import open_text_read  # noqa: E402


SCRIPT_VERSION = "M30"
_META_SCHEMA = "phase2_e2_robustness_aggregate_v1"
_REFINE_PLAN_SCHEMA = "phase2_e2_refine_plan_v1"

_CHI2_TOTAL_KEYS: Tuple[str, ...] = (
    "chi2_total",
    "chi2",
    "chi2_tot",
    "result.chi2_total",
    "result.chi2",
    "metrics.chi2_total",
    "metrics.chi2",
)

_CHI2_CMB_KEYS: Tuple[str, ...] = (
    "chi2_cmb",
    "chi2_parts.cmb.chi2",
    "chi2_parts.cmb",
    "result.chi2_cmb",
    "metrics.chi2_cmb",
)

_DRIFT_FLOAT_KEYS: Tuple[str, ...] = (
    "drift.min_z_dot",
    "drift_margin",
    "drift.min_zdot_si",
    "min_zdot_si",
    "chi2_parts.drift.min_zdot_si",
)

_DRIFT_SIGN_KEYS: Tuple[str, ...] = (
    "drift_sign_z2_5",
    "drift.sign",
)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _finite_float(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if not isinstance(value, (int, float)):
        return None
    out = float(value)
    if not math.isfinite(out):
        return None
    return out


def _fmt_float(value: Optional[float]) -> str:
    if value is None:
        return ""
    if not math.isfinite(float(value)):
        return ""
    return f"{float(value):.12g}"


def _fmt_bool(value: Optional[bool]) -> str:
    if value is None:
        return ""
    return "true" if bool(value) else "false"


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _get_path(obj: Mapping[str, Any], path: str) -> Any:
    cur: Any = obj
    for token in str(path).split("."):
        if not isinstance(cur, Mapping):
            return None
        if token not in cur:
            return None
        cur = cur[token]
    return cur


def _first_numeric(obj: Mapping[str, Any], keys: Sequence[str]) -> Optional[float]:
    for key in keys:
        fv = _finite_float(_get_path(obj, key))
        if fv is not None:
            return float(fv)
    return None


def _parse_status_ok(obj: Mapping[str, Any]) -> bool:
    raw = obj.get("status")
    if raw is None:
        return True
    return str(raw).strip().lower() == "ok"


def _extract_drift_sign(obj: Mapping[str, Any], drift_value: Optional[float]) -> Optional[int]:
    for key in _DRIFT_SIGN_KEYS:
        val = _get_path(obj, key)
        fv = _finite_float(val)
        if fv is not None:
            if fv > 0:
                return 1
            if fv < 0:
                return -1
            return 0

    for key in ("drift_pass", "drift_required_pass"):
        raw = _get_path(obj, key)
        if isinstance(raw, bool):
            return 1 if raw else -1

    if drift_value is not None:
        if drift_value > 0:
            return 1
        if drift_value < 0:
            return -1
        return 0
    return None


def _extract_params(obj: Mapping[str, Any]) -> Dict[str, float]:
    raw = _as_mapping(obj.get("params"))
    out: Dict[str, float] = {}
    for key in sorted(str(k) for k in raw.keys()):
        fv = _finite_float(raw.get(key))
        if fv is not None:
            out[key] = float(fv)
    return out


def _extract_microphysics_plausible(obj: Mapping[str, Any]) -> Tuple[Optional[bool], bool]:
    if "microphysics_plausible_ok" not in obj:
        return None, False
    return bool(obj.get("microphysics_plausible_ok")), True


@dataclass(frozen=True)
class Candidate:
    params_hash: str
    status: str
    status_ok: bool
    chi2_total: Optional[float]
    chi2_cmb: Optional[float]
    drift_value: Optional[float]
    drift_sign: Optional[int]
    microphysics_plausible_ok: Optional[bool]
    microphysics_penalty: Optional[float]
    microphysics_max_rel_dev: Optional[float]
    params: Dict[str, float]
    line_no: int


@dataclass(frozen=True)
class InputStats:
    path: str
    label: str
    sha256: str
    n_lines: int
    n_parsed_obj: int
    n_skipped_invalid_json: int
    n_skipped_non_object: int
    n_skipped_missing_hash: int
    n_dupe_hash: int
    n_selected: int
    n_ok_used: int
    n_skipped_no_ok: int


@dataclass(frozen=True)
class AggregateRow:
    params_hash: str
    n_present: int
    in_all_inputs: bool
    params: Dict[str, float]
    chi2_cmb_min: Optional[float]
    chi2_cmb_max: Optional[float]
    chi2_cmb_span: Optional[float]
    chi2_total_min: Optional[float]
    chi2_total_max: Optional[float]
    chi2_total_span: Optional[float]
    drift_metric_min: Optional[float]
    drift_metric_max: Optional[float]
    drift_metric_span: Optional[float]
    drift_sign_consensus: Optional[bool]
    microphysics_plausible_all: Optional[bool]
    microphysics_penalty_min: Optional[float]
    microphysics_penalty_max: Optional[float]
    microphysics_penalty_span: Optional[float]
    microphysics_max_rel_dev_max: Optional[float]
    robust_ok: bool
    by_label: Dict[str, Optional[Candidate]]


def _span(values: Sequence[float]) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    if not values:
        return None, None, None
    lo = float(min(values))
    hi = float(max(values))
    return lo, hi, float(hi - lo)


def _candidate_rank(candidate: Candidate) -> Tuple[int, float, float, int]:
    status_rank = 0 if candidate.status_ok else 1
    chi2_total = candidate.chi2_total if candidate.chi2_total is not None else float("inf")
    chi2_cmb = candidate.chi2_cmb if candidate.chi2_cmb is not None else float("inf")
    return (
        int(status_rank),
        float(chi2_total),
        float(chi2_cmb),
        -int(candidate.line_no),
    )


def _choose_candidate(candidates: Sequence[Candidate], *, only_status_ok: bool) -> Tuple[Optional[Candidate], bool]:
    if not candidates:
        return None, False
    pool: Sequence[Candidate] = candidates
    if only_status_ok:
        ok_pool = [c for c in candidates if c.status_ok]
        if not ok_pool:
            return None, True
        pool = ok_pool
    chosen = min(pool, key=_candidate_rank)
    return chosen, False


def _load_index_for_input(
    *,
    path: Path,
    label: str,
    only_status_ok: bool,
) -> Tuple[Dict[str, Candidate], InputStats]:
    rp = path.expanduser().resolve()
    if not rp.is_file():
        raise SystemExit(f"Input JSONL not found: {rp}")

    grouped: Dict[str, List[Candidate]] = {}
    n_lines = 0
    n_parsed_obj = 0
    n_invalid_json = 0
    n_non_object = 0
    n_missing_hash = 0

    with open_text_read(rp) as fh:
        for line_no, line in enumerate(fh, start=1):
            n_lines += 1
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            try:
                payload = json.loads(text)
            except Exception:
                n_invalid_json += 1
                continue
            if not isinstance(payload, Mapping):
                n_non_object += 1
                continue
            n_parsed_obj += 1

            obj = {str(k): v for k, v in payload.items()}
            raw_hash = obj.get("params_hash")
            params_hash = str(raw_hash).strip() if raw_hash is not None else ""
            if not params_hash:
                n_missing_hash += 1
                continue

            chi2_total = _first_numeric(obj, _CHI2_TOTAL_KEYS)
            chi2_cmb = _first_numeric(obj, _CHI2_CMB_KEYS)
            drift_value = _first_numeric(obj, _DRIFT_FLOAT_KEYS)
            drift_sign = _extract_drift_sign(obj, drift_value)
            micro_plaus, _ = _extract_microphysics_plausible(obj)

            candidate = Candidate(
                params_hash=params_hash,
                status=str(obj.get("status", "ok")),
                status_ok=_parse_status_ok(obj),
                chi2_total=chi2_total,
                chi2_cmb=chi2_cmb,
                drift_value=drift_value,
                drift_sign=drift_sign,
                microphysics_plausible_ok=micro_plaus,
                microphysics_penalty=_finite_float(obj.get("microphysics_penalty")),
                microphysics_max_rel_dev=_finite_float(obj.get("microphysics_max_rel_dev")),
                params=_extract_params(obj),
                line_no=int(line_no),
            )
            grouped.setdefault(params_hash, []).append(candidate)

    selected: Dict[str, Candidate] = {}
    n_dupe_hash = 0
    n_ok_used = 0
    n_skipped_no_ok = 0
    for params_hash in sorted(grouped.keys()):
        candidates = grouped[params_hash]
        if len(candidates) > 1:
            n_dupe_hash += 1
        chosen, skipped_no_ok = _choose_candidate(candidates, only_status_ok=only_status_ok)
        if skipped_no_ok:
            n_skipped_no_ok += 1
            continue
        if chosen is None:
            continue
        selected[params_hash] = chosen
        if chosen.status_ok:
            n_ok_used += 1

    stats = InputStats(
        path=str(rp),
        label=str(label),
        sha256=_sha256_file(rp),
        n_lines=int(n_lines),
        n_parsed_obj=int(n_parsed_obj),
        n_skipped_invalid_json=int(n_invalid_json),
        n_skipped_non_object=int(n_non_object),
        n_skipped_missing_hash=int(n_missing_hash),
        n_dupe_hash=int(n_dupe_hash),
        n_selected=int(len(selected)),
        n_ok_used=int(n_ok_used),
        n_skipped_no_ok=int(n_skipped_no_ok),
    )
    return selected, stats


def _sanitize_label(label: str, index: int) -> str:
    raw = str(label).strip()
    if not raw:
        raw = f"input_{index+1}"
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw)
    cleaned = cleaned.strip("_")
    if not cleaned:
        cleaned = f"input_{index+1}"
    return cleaned


def _resolve_labels(paths: Sequence[Path], labels: Sequence[str]) -> List[str]:
    if labels and len(labels) != len(paths):
        raise SystemExit("--label must be provided either zero times or exactly once per --jsonl")

    base = list(labels) if labels else [p.name for p in paths]
    normalized = [_sanitize_label(name, i) for i, name in enumerate(base)]
    seen: Dict[str, int] = {}
    out: List[str] = []
    for label in normalized:
        count = seen.get(label, 0) + 1
        seen[label] = count
        if count == 1:
            out.append(label)
        else:
            out.append(f"{label}__{count}")
    return out


def _robust_sort_value(row: AggregateRow, key: str) -> float:
    if str(key) == "chi2_total_worst":
        return float(row.chi2_total_max) if row.chi2_total_max is not None else float("inf")
    return float(row.chi2_cmb_max) if row.chi2_cmb_max is not None else float("inf")


def _aggregate_rows(
    *,
    labels: Sequence[str],
    indices: Sequence[Dict[str, Candidate]],
    selected_hashes: Sequence[str],
    max_span_chi2_cmb: float,
    max_span_chi2_total: float,
    require_drift_sign_consensus: bool,
) -> Tuple[List[AggregateRow], Dict[str, bool]]:
    drift_seen_global = any(
        candidate.drift_sign is not None
        for index in indices
        for candidate in index.values()
    )
    plausibility_seen_global = any(
        candidate.microphysics_plausible_ok is not None
        for index in indices
        for candidate in index.values()
    )

    out: List[AggregateRow] = []
    n_inputs = len(indices)

    for params_hash in selected_hashes:
        by_label: Dict[str, Optional[Candidate]] = {
            label: indices[i].get(params_hash)
            for i, label in enumerate(labels)
        }
        present = [c for c in by_label.values() if c is not None]
        n_present = int(len(present))
        in_all_inputs = bool(n_present == n_inputs)

        params: Dict[str, float] = {}
        for candidate in present:
            if candidate.params:
                params = {k: float(v) for k, v in sorted(candidate.params.items())}
                break

        chi2_cmb_vals = [float(c.chi2_cmb) for c in present if c.chi2_cmb is not None]
        chi2_total_vals = [float(c.chi2_total) for c in present if c.chi2_total is not None]
        drift_vals = [float(c.drift_value) for c in present if c.drift_value is not None]
        drift_sign_vals = [int(c.drift_sign) for c in present if c.drift_sign is not None]

        plaus_vals = [bool(c.microphysics_plausible_ok) for c in present if c.microphysics_plausible_ok is not None]
        micro_penalty_vals = [float(c.microphysics_penalty) for c in present if c.microphysics_penalty is not None]
        micro_max_rel_vals = [float(c.microphysics_max_rel_dev) for c in present if c.microphysics_max_rel_dev is not None]

        chi2_cmb_min, chi2_cmb_max, chi2_cmb_span = _span(chi2_cmb_vals)
        chi2_total_min, chi2_total_max, chi2_total_span = _span(chi2_total_vals)
        drift_min, drift_max, drift_span = _span(drift_vals)
        penalty_min, penalty_max, penalty_span = _span(micro_penalty_vals)

        drift_sign_consensus: Optional[bool]
        if not drift_sign_vals:
            drift_sign_consensus = None
        else:
            first = drift_sign_vals[0]
            drift_sign_consensus = bool(all(v == first for v in drift_sign_vals))

        microphysics_plausible_all: Optional[bool]
        if not plaus_vals:
            microphysics_plausible_all = None
        else:
            microphysics_plausible_all = bool(all(plaus_vals))

        robust_ok = True
        if n_present < 2:
            robust_ok = False
        if chi2_cmb_span is not None and float(chi2_cmb_span) > float(max_span_chi2_cmb):
            robust_ok = False
        if chi2_total_span is not None and float(chi2_total_span) > float(max_span_chi2_total):
            robust_ok = False
        if require_drift_sign_consensus and drift_seen_global and drift_sign_consensus is False:
            robust_ok = False
        if plausibility_seen_global and microphysics_plausible_all is False:
            robust_ok = False
        if chi2_cmb_span is None and chi2_total_span is None:
            robust_ok = False

        out.append(
            AggregateRow(
                params_hash=str(params_hash),
                n_present=int(n_present),
                in_all_inputs=bool(in_all_inputs),
                params=params,
                chi2_cmb_min=chi2_cmb_min,
                chi2_cmb_max=chi2_cmb_max,
                chi2_cmb_span=chi2_cmb_span,
                chi2_total_min=chi2_total_min,
                chi2_total_max=chi2_total_max,
                chi2_total_span=chi2_total_span,
                drift_metric_min=drift_min,
                drift_metric_max=drift_max,
                drift_metric_span=drift_span,
                drift_sign_consensus=drift_sign_consensus,
                microphysics_plausible_all=microphysics_plausible_all,
                microphysics_penalty_min=penalty_min,
                microphysics_penalty_max=penalty_max,
                microphysics_penalty_span=penalty_span,
                microphysics_max_rel_dev_max=max(micro_max_rel_vals) if micro_max_rel_vals else None,
                robust_ok=bool(robust_ok),
                by_label=by_label,
            )
        )

    flags = {
        "drift_sign_seen_global": bool(drift_seen_global),
        "plausibility_seen_global": bool(plausibility_seen_global),
    }
    return out, flags


def _csv_headers(labels: Sequence[str]) -> List[str]:
    base = [
        "params_hash",
        "n_present",
        "in_all_inputs",
        "chi2_cmb_min",
        "chi2_cmb_max",
        "chi2_cmb_span",
        "chi2_total_min",
        "chi2_total_max",
        "chi2_total_span",
        "drift_metric_min",
        "drift_metric_max",
        "drift_metric_span",
        "drift_sign_consensus",
        "microphysics_plausible_all",
        "microphysics_penalty_min",
        "microphysics_penalty_max",
        "microphysics_penalty_span",
        "microphysics_max_rel_dev_max",
        "robust_ok",
        "params_json",
    ]
    per_run: List[str] = []
    for label in labels:
        per_run.extend(
            [
                f"status__{label}",
                f"chi2_total__{label}",
                f"chi2_cmb__{label}",
                f"drift_metric__{label}",
                f"drift_sign__{label}",
                f"microphysics_plausible_ok__{label}",
                f"microphysics_penalty__{label}",
                f"microphysics_max_rel_dev__{label}",
            ]
        )
    return base + per_run


def _row_to_csv_dict(row: AggregateRow, labels: Sequence[str]) -> Dict[str, str]:
    out: Dict[str, str] = {
        "params_hash": str(row.params_hash),
        "n_present": str(int(row.n_present)),
        "in_all_inputs": _fmt_bool(bool(row.in_all_inputs)),
        "chi2_cmb_min": _fmt_float(row.chi2_cmb_min),
        "chi2_cmb_max": _fmt_float(row.chi2_cmb_max),
        "chi2_cmb_span": _fmt_float(row.chi2_cmb_span),
        "chi2_total_min": _fmt_float(row.chi2_total_min),
        "chi2_total_max": _fmt_float(row.chi2_total_max),
        "chi2_total_span": _fmt_float(row.chi2_total_span),
        "drift_metric_min": _fmt_float(row.drift_metric_min),
        "drift_metric_max": _fmt_float(row.drift_metric_max),
        "drift_metric_span": _fmt_float(row.drift_metric_span),
        "drift_sign_consensus": _fmt_bool(row.drift_sign_consensus),
        "microphysics_plausible_all": _fmt_bool(row.microphysics_plausible_all),
        "microphysics_penalty_min": _fmt_float(row.microphysics_penalty_min),
        "microphysics_penalty_max": _fmt_float(row.microphysics_penalty_max),
        "microphysics_penalty_span": _fmt_float(row.microphysics_penalty_span),
        "microphysics_max_rel_dev_max": _fmt_float(row.microphysics_max_rel_dev_max),
        "robust_ok": _fmt_bool(bool(row.robust_ok)),
        "params_json": json.dumps({k: float(v) for k, v in sorted(row.params.items())}, sort_keys=True, separators=(",", ":")),
    }

    for label in labels:
        candidate = row.by_label.get(label)
        out[f"status__{label}"] = ""
        out[f"chi2_total__{label}"] = ""
        out[f"chi2_cmb__{label}"] = ""
        out[f"drift_metric__{label}"] = ""
        out[f"drift_sign__{label}"] = ""
        out[f"microphysics_plausible_ok__{label}"] = ""
        out[f"microphysics_penalty__{label}"] = ""
        out[f"microphysics_max_rel_dev__{label}"] = ""
        if candidate is None:
            continue
        out[f"status__{label}"] = str(candidate.status)
        out[f"chi2_total__{label}"] = _fmt_float(candidate.chi2_total)
        out[f"chi2_cmb__{label}"] = _fmt_float(candidate.chi2_cmb)
        out[f"drift_metric__{label}"] = _fmt_float(candidate.drift_value)
        out[f"drift_sign__{label}"] = "" if candidate.drift_sign is None else str(int(candidate.drift_sign))
        out[f"microphysics_plausible_ok__{label}"] = _fmt_bool(candidate.microphysics_plausible_ok)
        out[f"microphysics_penalty__{label}"] = _fmt_float(candidate.microphysics_penalty)
        out[f"microphysics_max_rel_dev__{label}"] = _fmt_float(candidate.microphysics_max_rel_dev)
    return out


def _summarize_input_stats(stats: Sequence[InputStats]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for entry in stats:
        out.append(
            {
                "path": str(entry.path),
                "label": str(entry.label),
                "sha256": str(entry.sha256),
                "n_lines": int(entry.n_lines),
                "n_parsed_obj": int(entry.n_parsed_obj),
                "n_skipped_invalid_json": int(entry.n_skipped_invalid_json),
                "n_skipped_non_object": int(entry.n_skipped_non_object),
                "n_skipped_missing_hash": int(entry.n_skipped_missing_hash),
                "n_dupe_hash": int(entry.n_dupe_hash),
                "n_selected": int(entry.n_selected),
                "n_ok_used": int(entry.n_ok_used),
                "n_skipped_no_ok": int(entry.n_skipped_no_ok),
            }
        )
    return out


def _write_markdown(
    *,
    out_path: Path,
    labels: Sequence[str],
    input_stats: Sequence[InputStats],
    rows_sorted: Sequence[AggregateRow],
    robust_rows: Sequence[AggregateRow],
    unstable_rows: Sequence[AggregateRow],
    top_n: int,
    require_common: bool,
    robust_sort_key: str,
    counts: Mapping[str, Any],
) -> None:
    lines: List[str] = []
    lines.append("# Phase-2 E2 Robustness Aggregate (M30)")
    lines.append("")
    lines.append(f"- Generated (UTC): `{_now_utc()}`")
    lines.append(f"- Script version: `{SCRIPT_VERSION}`")
    lines.append(f"- Inputs: `{len(labels)}`")
    lines.append(f"- Selection: `{'intersection' if require_common else 'union'}`")
    lines.append(f"- Sort key: `{robust_sort_key}`")
    lines.append("")
    lines.append("## Inputs")
    lines.append("")
    lines.append("| label | path | sha256 | selected | dup_hash | skipped_missing_hash |")
    lines.append("|---|---|---|---:|---:|---:|")
    for st in input_stats:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(st.label),
                    str(st.path),
                    str(st.sha256),
                    str(int(st.n_selected)),
                    str(int(st.n_dupe_hash)),
                    str(int(st.n_skipped_missing_hash)),
                ]
            )
            + " |"
        )

    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Union hashes: `{int(counts['n_union'])}`")
    lines.append(f"- Intersection hashes: `{int(counts['n_intersection'])}`")
    lines.append(f"- Aggregated rows: `{int(counts['n_rows'])}`")
    lines.append(f"- Robust OK rows: `{int(counts['n_robust_ok'])}`")
    lines.append(f"- Drift-sign present globally: `{bool(counts['drift_sign_seen_global'])}`")
    lines.append(f"- Plausibility present globally: `{bool(counts['plausibility_seen_global'])}`")

    lines.append("")
    lines.append("## Top robust candidates")
    lines.append("")
    lines.append("| rank | params_hash | n_present | chi2_cmb_worst | chi2_total_worst | chi2_cmb_span | chi2_total_span | drift_consensus | plausible_all |")
    lines.append("|---:|---|---:|---:|---:|---:|---:|---|---|")
    for idx, row in enumerate(list(robust_rows)[: int(top_n)], start=1):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(idx),
                    str(row.params_hash),
                    str(int(row.n_present)),
                    _fmt_float(row.chi2_cmb_max) or "NA",
                    _fmt_float(row.chi2_total_max) or "NA",
                    _fmt_float(row.chi2_cmb_span) or "NA",
                    _fmt_float(row.chi2_total_span) or "NA",
                    _fmt_bool(row.drift_sign_consensus) or "NA",
                    _fmt_bool(row.microphysics_plausible_all) or "NA",
                ]
            )
            + " |"
        )

    lines.append("")
    lines.append("## Worst unstable examples")
    lines.append("")
    lines.append("| rank | params_hash | n_present | chi2_cmb_span | chi2_total_span | chi2_cmb_worst | chi2_total_worst | robust_ok |")
    lines.append("|---:|---|---:|---:|---:|---:|---:|---|")
    for idx, row in enumerate(list(unstable_rows)[: int(top_n)], start=1):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(idx),
                    str(row.params_hash),
                    str(int(row.n_present)),
                    _fmt_float(row.chi2_cmb_span) or "NA",
                    _fmt_float(row.chi2_total_span) or "NA",
                    _fmt_float(row.chi2_cmb_max) or "NA",
                    _fmt_float(row.chi2_total_max) or "NA",
                    _fmt_bool(bool(row.robust_ok)),
                ]
            )
            + " |"
        )

    lines.append("")
    lines.append("## How to use")
    lines.append("")
    lines.append("1. Run the same plan with different numerics/recombination settings.")
    lines.append("2. Aggregate with `--require-common` for strict point-to-point comparison.")
    lines.append("3. Use robust candidates for focused follow-up scans.")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _infer_global_bounds(rows: Sequence[AggregateRow]) -> Dict[str, Tuple[float, float]]:
    bounds: Dict[str, Tuple[float, float]] = {}
    keys = sorted({k for row in rows for k in row.params.keys()})
    for key in keys:
        values = [float(row.params[key]) for row in rows if key in row.params]
        if not values:
            continue
        lo = float(min(values))
        hi = float(max(values))
        if not (math.isfinite(lo) and math.isfinite(hi)):
            continue
        if hi <= lo:
            eps = max(abs(lo) * 1e-6, 1e-6)
            lo -= eps
            hi += eps
        bounds[str(key)] = (float(lo), float(hi))
    return bounds


def _emit_refine_plan(
    *,
    out_path: Path,
    candidates: Sequence[AggregateRow],
    input_stats: Sequence[InputStats],
    robust_sort_key: str,
    require_drift_sign_consensus: bool,
    aggregate_meta_path: Path,
) -> Optional[Path]:
    chosen = [row for row in candidates if row.robust_ok and row.params]
    if not chosen:
        return None

    sorted_candidates = sorted(
        chosen,
        key=lambda row: (
            _robust_sort_value(row, robust_sort_key),
            str(row.params_hash),
        ),
    )

    global_bounds = _infer_global_bounds(sorted_candidates)

    points: List[Dict[str, Any]] = []
    for idx, row in enumerate(sorted_candidates):
        points.append(
            {
                "point_id": f"robust_p{int(idx):06d}",
                "seed_rank": int(idx),
                "seed_params_hash": str(row.params_hash),
                "params": {k: float(v) for k, v in sorted(row.params.items())},
            }
        )

    first_input = input_stats[0]
    aggregate_meta_sha = _sha256_file(aggregate_meta_path)
    payload = {
        "plan_version": _REFINE_PLAN_SCHEMA,
        "generated_utc": _now_utc(),
        "source": {
            "jsonl_path": str(first_input.path),
            "jsonl_sha256": str(first_input.sha256),
            "aggregate_meta_path": str(aggregate_meta_path),
            "aggregate_meta_sha256": str(aggregate_meta_sha),
            "jsonl_inputs": [
                {
                    "path": str(item.path),
                    "label": str(item.label),
                    "sha256": str(item.sha256),
                }
                for item in input_stats
            ],
        },
        "selection": {
            "top_k": int(len(points)),
            "plausibility": "robust_ok_only",
            "require_drift_sign": "consensus_required" if bool(require_drift_sign_consensus) else "any",
            "ranking": f"{str(robust_sort_key)}_then_params_hash",
            "note": "M30 robust aggregation plan from multi-run intersection/union candidates",
        },
        "refine": {
            "n_per_seed": 1,
            "radius_rel": 0.0,
            "sampler": "explicit",
            "seed": 0,
        },
        "global_bounds": {
            key: [float(value[0]), float(value[1])]
            for key, value in sorted(global_bounds.items())
        },
        "points": points,
    }
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out_path


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Aggregate robustness metrics across multiple E2 scan JSONL files.")
    ap.add_argument("--jsonl", type=Path, action="append", required=True, help="Input scan JSONL (repeatable, min 2).")
    ap.add_argument("--label", type=str, action="append", default=[], help="Optional label per --jsonl input.")
    ap.add_argument("--outdir", type=Path, required=True, help="Output directory (required).")
    ap.add_argument("--require-common", action="store_true", help="Use intersection of params_hash across all inputs.")
    ap.add_argument(
        "--only-status-ok",
        dest="only_status_ok",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use only status==ok records when status exists (default: true).",
    )
    ap.add_argument("--max-span-chi2-cmb", type=float, default=1.0)
    ap.add_argument("--max-span-chi2-total", type=float, default=1.0)
    ap.add_argument(
        "--require-drift-sign-consensus",
        dest="require_drift_sign_consensus",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Require drift sign consensus for robust_ok when drift sign exists (default: true).",
    )
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument(
        "--robust-sort-key",
        choices=["chi2_cmb_worst", "chi2_total_worst"],
        default="chi2_cmb_worst",
    )
    ap.add_argument("--emit-refine-plan", type=Path, default=None, help="Optional path for phase2_e2_refine_plan_v1 JSON.")
    args = ap.parse_args(argv)

    if len(args.jsonl) < 2:
        raise SystemExit("Provide at least two --jsonl inputs for robustness aggregation.")
    if not (math.isfinite(float(args.max_span_chi2_cmb)) and float(args.max_span_chi2_cmb) >= 0.0):
        raise SystemExit("--max-span-chi2-cmb must be finite and >= 0")
    if not (math.isfinite(float(args.max_span_chi2_total)) and float(args.max_span_chi2_total) >= 0.0):
        raise SystemExit("--max-span-chi2-total must be finite and >= 0")
    if int(args.top_n) <= 0:
        raise SystemExit("--top-n must be > 0")

    input_paths = [p.expanduser().resolve() for p in args.jsonl]
    labels = _resolve_labels(input_paths, args.label)

    indices: List[Dict[str, Candidate]] = []
    stats: List[InputStats] = []
    for path, label in zip(input_paths, labels):
        index, stat = _load_index_for_input(path=path, label=label, only_status_ok=bool(args.only_status_ok))
        indices.append(index)
        stats.append(stat)

    key_sets = [set(index.keys()) for index in indices]
    union_hashes = sorted(set().union(*key_sets)) if key_sets else []
    intersection_hashes = sorted(set.intersection(*key_sets)) if key_sets else []
    selected_hashes = intersection_hashes if bool(args.require_common) else union_hashes

    rows, flags = _aggregate_rows(
        labels=labels,
        indices=indices,
        selected_hashes=selected_hashes,
        max_span_chi2_cmb=float(args.max_span_chi2_cmb),
        max_span_chi2_total=float(args.max_span_chi2_total),
        require_drift_sign_consensus=bool(args.require_drift_sign_consensus),
    )

    rows_sorted = sorted(
        rows,
        key=lambda row: (
            _robust_sort_value(row, str(args.robust_sort_key)),
            str(row.params_hash),
        ),
    )
    robust_rows = [row for row in rows_sorted if row.robust_ok]

    unstable_span_key = "chi2_total_span" if str(args.robust_sort_key) == "chi2_total_worst" else "chi2_cmb_span"
    unstable_rows = sorted(
        [row for row in rows_sorted if not row.robust_ok],
        key=lambda row: (
            -float(row.chi2_total_span if unstable_span_key == "chi2_total_span" and row.chi2_total_span is not None else 0.0)
            if unstable_span_key == "chi2_total_span"
            else -float(row.chi2_cmb_span if row.chi2_cmb_span is not None else 0.0),
            str(row.params_hash),
        ),
    )

    outdir = args.outdir.expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    out_csv = outdir / "robustness_aggregate.csv"
    out_md = outdir / "robustness_aggregate.md"
    out_meta = outdir / "robustness_aggregate_meta.json"

    headers = _csv_headers(labels)
    with out_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers)
        writer.writeheader()
        for row in rows_sorted:
            writer.writerow(_row_to_csv_dict(row, labels))

    counts = {
        "n_union": int(len(union_hashes)),
        "n_intersection": int(len(intersection_hashes)),
        "n_rows": int(len(rows_sorted)),
        "n_robust_ok": int(len(robust_rows)),
        "n_unstable": int(len(unstable_rows)),
        "drift_sign_seen_global": bool(flags["drift_sign_seen_global"]),
        "plausibility_seen_global": bool(flags["plausibility_seen_global"]),
    }

    _write_markdown(
        out_path=out_md,
        labels=labels,
        input_stats=stats,
        rows_sorted=rows_sorted,
        robust_rows=robust_rows,
        unstable_rows=unstable_rows,
        top_n=int(args.top_n),
        require_common=bool(args.require_common),
        robust_sort_key=str(args.robust_sort_key),
        counts=counts,
    )

    meta_payload = {
        "schema": _META_SCHEMA,
        "script_version": SCRIPT_VERSION,
        "generated_utc": _now_utc(),
        "config": {
            "jsonl": [str(p) for p in input_paths],
            "labels": list(labels),
            "require_common": bool(args.require_common),
            "only_status_ok": bool(args.only_status_ok),
            "max_span_chi2_cmb": float(args.max_span_chi2_cmb),
            "max_span_chi2_total": float(args.max_span_chi2_total),
            "require_drift_sign_consensus": bool(args.require_drift_sign_consensus),
            "top_n": int(args.top_n),
            "robust_sort_key": str(args.robust_sort_key),
            "emit_refine_plan": None if args.emit_refine_plan is None else str(args.emit_refine_plan),
        },
        "inputs": _summarize_input_stats(stats),
        "counts": counts,
        "outputs": {
            "csv": str(out_csv),
            "markdown": str(out_md),
            "meta_json": str(out_meta),
        },
    }
    out_meta.write_text(json.dumps(meta_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    refine_written: Optional[Path] = None
    if args.emit_refine_plan is not None:
        plan_path = args.emit_refine_plan
        if not plan_path.is_absolute():
            plan_path = outdir / plan_path
        plan_path = plan_path.expanduser().resolve()
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        refine_written = _emit_refine_plan(
            out_path=plan_path,
            candidates=rows_sorted,
            input_stats=stats,
            robust_sort_key=str(args.robust_sort_key),
            require_drift_sign_consensus=bool(args.require_drift_sign_consensus),
            aggregate_meta_path=out_meta,
        )

    print(f"[ok] wrote {out_csv}")
    print(f"[ok] wrote {out_md}")
    print(f"[ok] wrote {out_meta}")
    if refine_written is not None:
        print(f"[ok] wrote {refine_written}")
    elif args.emit_refine_plan is not None:
        print("[warn] no robust candidates with params; refine plan not written")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Phase-2 E2 sensitivity/correlation report (stdlib-only).

This tool analyzes one or many JSONL outputs from `phase2_e2_scan.py` and
produces deterministic correlation summaries between parameter knobs and
scan metrics (chi2 / drift / plausibility diagnostics).
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

V101_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V101_DIR))

from gsc.jsonl_io import open_text_read  # noqa: E402


SCRIPT_VERSION = "phase2.m32.e2_sensitivity_report.v1"


@dataclass
class Counters:
    n_total_lines: int = 0
    n_parsed: int = 0
    n_used: int = 0
    n_skipped_bad_json: int = 0
    n_skipped_non_object: int = 0
    n_skipped_status: int = 0
    n_skipped_plausibility: int = 0
    n_skipped_missing_drift_metric: int = 0
    n_skipped_non_positive_drift_metric: int = 0
    n_skipped_no_numeric_params: int = 0
    n_skipped_no_numeric_metrics: int = 0

    def as_dict(self) -> Dict[str, int]:
        return {
            "n_total_lines": int(self.n_total_lines),
            "n_parsed": int(self.n_parsed),
            "n_used": int(self.n_used),
            "n_skipped_bad_json": int(self.n_skipped_bad_json),
            "n_skipped_non_object": int(self.n_skipped_non_object),
            "n_skipped_status": int(self.n_skipped_status),
            "n_skipped_plausibility": int(self.n_skipped_plausibility),
            "n_skipped_missing_drift_metric": int(self.n_skipped_missing_drift_metric),
            "n_skipped_non_positive_drift_metric": int(self.n_skipped_non_positive_drift_metric),
            "n_skipped_no_numeric_params": int(self.n_skipped_no_numeric_params),
            "n_skipped_no_numeric_metrics": int(self.n_skipped_no_numeric_metrics),
        }


@dataclass
class Row:
    source: str
    line: int
    params: Dict[str, float]
    metrics: Dict[str, float]


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _to_float(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except Exception:
        return None
    if not math.isfinite(out):
        return None
    return float(out)


def _format_float(value: Optional[float], fmt: str) -> str:
    if value is None:
        return "NA"
    try:
        return str(fmt.format(float(value)))
    except Exception:
        return f"{float(value):.8g}"


def _split_csv_values(raw: str) -> List[str]:
    out: List[str] = []
    for token in str(raw).split(","):
        key = token.strip()
        if key and key not in out:
            out.append(key)
    return out


def _iter_unique_inputs(positional: Sequence[Path], repeatable: Sequence[Path]) -> List[Path]:
    out: List[Path] = []
    seen: set[Path] = set()
    for raw in list(positional) + list(repeatable):
        rp = raw.expanduser().resolve()
        if rp in seen:
            continue
        seen.add(rp)
        out.append(rp)
    return sorted(out)


def _flatten_numeric(mapping: Mapping[str, Any], *, prefix: str = "") -> Dict[str, float]:
    out: Dict[str, float] = {}
    for key in sorted(mapping.keys(), key=lambda x: str(x)):
        skey = str(key)
        value = mapping[key]
        full_key = f"{prefix}.{skey}" if prefix else skey
        if isinstance(value, Mapping):
            out.update(_flatten_numeric(_as_mapping(value), prefix=full_key))
            continue
        if isinstance(value, (list, tuple)):
            continue
        fv = _to_float(value)
        if fv is not None:
            out[full_key] = float(fv)
    return out


def _insert_param(out: Dict[str, float], key: str, value: float) -> None:
    if key not in out:
        out[key] = float(value)
        return
    suffix = 2
    while f"{key}__{suffix}" in out:
        suffix += 1
    out[f"{key}__{suffix}"] = float(value)


def _extract_params(obj: Mapping[str, Any]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    base = _flatten_numeric(_as_mapping(obj.get("params")))
    for key in sorted(base.keys()):
        _insert_param(out, key, base[key])

    cosmo = _flatten_numeric(_as_mapping(obj.get("cosmo_params")), prefix="cosmo")
    for key in sorted(cosmo.keys()):
        _insert_param(out, key, cosmo[key])

    micro = _flatten_numeric(_as_mapping(obj.get("microphysics_knobs")), prefix="micro")
    for key in sorted(micro.keys()):
        _insert_param(out, key, micro[key])

    return out


def _extract_chi2_parts_metrics(obj: Mapping[str, Any]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    root = _as_mapping(obj.get("chi2_parts"))
    for key in sorted(root.keys(), key=lambda x: str(x)):
        skey = str(key)
        value = root[key]
        metric_key = f"chi2_parts.{skey}"
        if isinstance(value, Mapping):
            chi2 = _to_float(_as_mapping(value).get("chi2"))
            if chi2 is not None:
                out[metric_key] = float(chi2)
                continue
            nested = _flatten_numeric(_as_mapping(value), prefix=metric_key)
            for nested_key in sorted(nested.keys()):
                out[nested_key] = float(nested[nested_key])
            continue
        fv = _to_float(value)
        if fv is not None:
            out[metric_key] = float(fv)
    return out


def _get_path(obj: Mapping[str, Any], dotted: str) -> Any:
    current: Any = obj
    for token in str(dotted).split("."):
        if not isinstance(current, Mapping) or token not in current:
            return None
        current = current[token]
    return current


def _metric_value_from_path(obj: Mapping[str, Any], key: str) -> Optional[float]:
    if not key:
        return None
    if key in obj:
        direct = _to_float(obj[key])
        if direct is not None:
            return float(direct)
    value = _get_path(obj, key)
    if isinstance(value, Mapping):
        chi2 = _to_float(_as_mapping(value).get("chi2"))
        if chi2 is not None:
            return float(chi2)
        return None
    return _to_float(value)


def _detect_metrics(obj: Mapping[str, Any]) -> Dict[str, float]:
    out: Dict[str, float] = {}

    for key in ("chi2_total", "chi2", "chi2_tot"):
        fv = _to_float(obj.get(key))
        if fv is not None:
            out[key] = float(fv)

    out.update(_extract_chi2_parts_metrics(obj))

    for key in sorted(obj.keys(), key=lambda x: str(x)):
        skey = str(key)
        if skey.startswith("drift_"):
            fv = _to_float(obj[key])
            if fv is not None:
                out[skey] = float(fv)

    drift = _flatten_numeric(_as_mapping(obj.get("drift")), prefix="drift")
    for key in sorted(drift.keys()):
        out[key] = float(drift[key])

    for key in ("microphysics_penalty", "microphysics_max_rel_dev"):
        fv = _to_float(obj.get(key))
        if fv is not None:
            out[key] = float(fv)

    return out


def _rankdata_average(values: Sequence[float]) -> List[float]:
    n = len(values)
    if n == 0:
        return []
    indexed = sorted(enumerate(values), key=lambda kv: (float(kv[1]), int(kv[0])))
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i + 1
        while j < n and float(indexed[j][1]) == float(indexed[i][1]):
            j += 1
        avg_rank = (float(i + 1) + float(j)) / 2.0
        for k in range(i, j):
            ranks[indexed[k][0]] = avg_rank
        i = j
    return ranks


def _pearson(x: Sequence[float], y: Sequence[float]) -> Optional[float]:
    if len(x) != len(y) or len(x) < 2:
        return None
    n = float(len(x))
    mx = sum(float(v) for v in x) / n
    my = sum(float(v) for v in y) / n
    sxx = 0.0
    syy = 0.0
    sxy = 0.0
    for xv, yv in zip(x, y):
        dx = float(xv) - mx
        dy = float(yv) - my
        sxx += dx * dx
        syy += dy * dy
        sxy += dx * dy
    if sxx <= 0.0 or syy <= 0.0:
        return None
    return float(sxy / math.sqrt(sxx * syy))


def _spearman(x: Sequence[float], y: Sequence[float]) -> Optional[float]:
    if len(x) != len(y) or len(x) < 2:
        return None
    rx = _rankdata_average([float(v) for v in x])
    ry = _rankdata_average([float(v) for v in y])
    return _pearson(rx, ry)


def _parse_rows(
    *,
    paths: Sequence[Path],
    status_ok_only: bool,
    plausibility: str,
    require_drift_positive: Optional[str],
    metrics_override: Optional[Sequence[str]],
) -> Tuple[List[Row], Counters, Dict[str, Dict[str, str]], List[str], List[str]]:
    counters = Counters()
    rows: List[Row] = []
    inputs_meta: Dict[str, Dict[str, str]] = {}
    metric_keys_seen: set[str] = set()
    param_keys_seen: set[str] = set()
    override = [str(k) for k in metrics_override] if metrics_override else []

    for path in paths:
        if not path.is_file():
            raise SystemExit(f"Input JSONL not found: {path}")
        inputs_meta[str(path)] = {"sha256": _sha256_file(path)}
        with open_text_read(path) as fh:
            for idx, raw_line in enumerate(fh, start=1):
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                counters.n_total_lines += 1
                try:
                    payload = json.loads(line)
                except Exception:
                    counters.n_skipped_bad_json += 1
                    continue
                if not isinstance(payload, Mapping):
                    counters.n_skipped_non_object += 1
                    continue
                counters.n_parsed += 1
                obj = {str(k): v for k, v in payload.items()}

                if status_ok_only and "status" in obj:
                    status = str(obj.get("status", "")).strip().lower()
                    if status != "ok":
                        counters.n_skipped_status += 1
                        continue

                if plausibility == "plausible_only":
                    plausible = obj.get("microphysics_plausible_ok")
                    if plausible is not None and bool(plausible) is not True:
                        counters.n_skipped_plausibility += 1
                        continue

                if require_drift_positive:
                    drift_val = _metric_value_from_path(obj, require_drift_positive)
                    if drift_val is None:
                        counters.n_skipped_missing_drift_metric += 1
                        continue
                    if float(drift_val) <= 0.0:
                        counters.n_skipped_non_positive_drift_metric += 1
                        continue

                params = _extract_params(obj)
                if not params:
                    counters.n_skipped_no_numeric_params += 1
                    continue
                for key in params.keys():
                    param_keys_seen.add(str(key))

                metrics: Dict[str, float] = {}
                if override:
                    for key in override:
                        fv = _metric_value_from_path(obj, key)
                        if fv is not None:
                            metrics[key] = float(fv)
                else:
                    metrics = _detect_metrics(obj)

                if not metrics:
                    counters.n_skipped_no_numeric_metrics += 1
                    continue
                for key in metrics.keys():
                    metric_keys_seen.add(str(key))

                rows.append(
                    Row(
                        source=str(path),
                        line=int(idx),
                        params={str(k): float(v) for k, v in sorted(params.items())},
                        metrics={str(k): float(v) for k, v in sorted(metrics.items())},
                    )
                )
                counters.n_used += 1

    metric_keys = list(override) if override else sorted(metric_keys_seen)
    param_keys = sorted(param_keys_seen)
    return rows, counters, inputs_meta, metric_keys, param_keys


def _compute_correlations(
    *,
    rows: Sequence[Row],
    metric_keys: Sequence[str],
    param_keys: Sequence[str],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for metric_key in metric_keys:
        for param_key in param_keys:
            xs: List[float] = []
            ys: List[float] = []
            for row in rows:
                x = row.params.get(param_key)
                y = row.metrics.get(metric_key)
                if x is None or y is None:
                    continue
                xs.append(float(x))
                ys.append(float(y))
            n = len(xs)
            pearson = _pearson(xs, ys) if n >= 2 else None
            spearman = _spearman(xs, ys) if n >= 2 else None
            out.append(
                {
                    "param_key": str(param_key),
                    "metric_key": str(metric_key),
                    "n": int(n),
                    "pearson_r": pearson,
                    "spearman_r": spearman,
                }
            )
    return out


def _safe_abs(value: Optional[float]) -> float:
    if value is None or not math.isfinite(float(value)):
        return -1.0
    return abs(float(value))


def _top_correlations(
    corr_rows: Sequence[Mapping[str, Any]],
    *,
    metric_key: str,
    top_k: int,
) -> List[Mapping[str, Any]]:
    rows = [row for row in corr_rows if str(row.get("metric_key")) == str(metric_key)]
    rows = sorted(
        rows,
        key=lambda r: (
            -_safe_abs(_to_float(r.get("spearman_r"))),
            str(r.get("param_key", "")),
        ),
    )
    return rows[: max(1, int(top_k))]


def _median(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    return float(statistics.median([float(v) for v in values]))


def _quantile_sections(
    *,
    rows: Sequence[Row],
    corr_rows: Sequence[Mapping[str, Any]],
    metric_key: str,
    quantiles: int,
    max_params: int,
) -> List[Dict[str, Any]]:
    quant = max(2, int(quantiles))
    ranked = _top_correlations(corr_rows, metric_key=metric_key, top_k=max_params)
    out: List[Dict[str, Any]] = []
    for entry in ranked:
        param_key = str(entry.get("param_key"))
        pairs: List[Tuple[float, float]] = []
        for row in rows:
            x = row.params.get(param_key)
            y = row.metrics.get(metric_key)
            if x is None or y is None:
                continue
            pairs.append((float(x), float(y)))
        if len(pairs) < quant:
            continue
        pairs.sort(key=lambda xy: xy[0])
        bins: List[Dict[str, Any]] = []
        n = len(pairs)
        for q_idx in range(quant):
            start = (q_idx * n) // quant
            end = ((q_idx + 1) * n) // quant
            if end <= start:
                continue
            chunk = pairs[start:end]
            xs = [c[0] for c in chunk]
            ys = [c[1] for c in chunk]
            bins.append(
                {
                    "q_index": int(q_idx + 1),
                    "param_min": float(min(xs)),
                    "param_max": float(max(xs)),
                    "n": int(len(chunk)),
                    "metric_median": _median(ys),
                }
            )
        if bins:
            out.append(
                {
                    "param_key": param_key,
                    "n_pairs": int(len(pairs)),
                    "bins": bins,
                }
            )
    return out


def _write_csv(path: Path, corr_rows: Sequence[Mapping[str, Any]]) -> None:
    fieldnames = ["param_key", "metric_key", "n", "pearson_r", "spearman_r"]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in corr_rows:
            writer.writerow(
                {
                    "param_key": str(row.get("param_key", "")),
                    "metric_key": str(row.get("metric_key", "")),
                    "n": int(row.get("n", 0)),
                    "pearson_r": row.get("pearson_r"),
                    "spearman_r": row.get("spearman_r"),
                }
            )


def _write_markdown(
    *,
    path: Path,
    inputs: Mapping[str, Mapping[str, str]],
    counters: Counters,
    metric_keys: Sequence[str],
    param_keys: Sequence[str],
    corr_rows: Sequence[Mapping[str, Any]],
    top_k: int,
    float_format: str,
    quantile_metric: Optional[str],
    quantile_sections: Sequence[Mapping[str, Any]],
) -> None:
    lines: List[str] = []
    lines.append("# Phase-2 E2 Sensitivity Report")
    lines.append("")
    lines.append(f"- Script version: `{SCRIPT_VERSION}`")
    lines.append("")
    lines.append("## Input Summary")
    for source in sorted(inputs.keys()):
        sha = str(inputs[source].get("sha256", ""))
        lines.append(f"- `{source}` (sha256: `{sha}`)")
    lines.append("")
    counts = counters.as_dict()
    lines.append(f"- N_total_lines: `{counts['n_total_lines']}`")
    lines.append(f"- N_parsed: `{counts['n_parsed']}`")
    lines.append(f"- N_used: `{counts['n_used']}`")
    lines.append("- N_skipped breakdown:")
    lines.append(f"  - bad_json: `{counts['n_skipped_bad_json']}`")
    lines.append(f"  - non_object: `{counts['n_skipped_non_object']}`")
    lines.append(f"  - status_filter: `{counts['n_skipped_status']}`")
    lines.append(f"  - plausibility_filter: `{counts['n_skipped_plausibility']}`")
    lines.append(f"  - missing_drift_filter_metric: `{counts['n_skipped_missing_drift_metric']}`")
    lines.append(f"  - non_positive_drift_metric: `{counts['n_skipped_non_positive_drift_metric']}`")
    lines.append(f"  - no_numeric_params: `{counts['n_skipped_no_numeric_params']}`")
    lines.append(f"  - no_numeric_metrics: `{counts['n_skipped_no_numeric_metrics']}`")
    lines.append("")
    lines.append("## Metrics Analyzed")
    for metric_key in metric_keys:
        lines.append(f"- `{metric_key}`")
    lines.append("")
    lines.append("## Parameter Space Summary")
    lines.append(f"- N_params: `{len(param_keys)}`")
    lines.append("")

    all_pairs = sorted(
        corr_rows,
        key=lambda r: (
            -_safe_abs(_to_float(r.get("spearman_r"))),
            str(r.get("metric_key", "")),
            str(r.get("param_key", "")),
        ),
    )
    lines.append("## Top Absolute Correlations (Global)")
    lines.append("")
    lines.append("| rank | metric | param | spearman_r | pearson_r | n_pairs |")
    lines.append("|---:|---|---|---:|---:|---:|")
    for idx, row in enumerate(all_pairs[: max(1, int(top_k))], start=1):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(idx),
                    f"`{row.get('metric_key', '')}`",
                    f"`{row.get('param_key', '')}`",
                    _format_float(_to_float(row.get("spearman_r")), float_format),
                    _format_float(_to_float(row.get("pearson_r")), float_format),
                    str(int(row.get("n", 0))),
                ]
            )
            + " |"
        )
    lines.append("")

    for metric_key in metric_keys:
        lines.append(f"## Metric: `{metric_key}`")
        lines.append("")
        lines.append("| rank | param | spearman_r | pearson_r | n_pairs |")
        lines.append("|---:|---|---:|---:|---:|")
        top_rows = _top_correlations(corr_rows, metric_key=metric_key, top_k=top_k)
        for idx, row in enumerate(top_rows, start=1):
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(idx),
                        f"`{row.get('param_key', '')}`",
                        _format_float(_to_float(row.get("spearman_r")), float_format),
                        _format_float(_to_float(row.get("pearson_r")), float_format),
                        str(int(row.get("n", 0))),
                    ]
                )
                + " |"
            )
        lines.append("")

    if quantile_metric:
        lines.append(f"## Quantile Trends: `{quantile_metric}`")
        lines.append("")
        if not quantile_sections:
            lines.append("No quantile sections available for the selected metric.")
            lines.append("")
        for section in quantile_sections:
            param_key = str(section.get("param_key", ""))
            lines.append(f"### Param `{param_key}`")
            lines.append("")
            lines.append("| q_index | param_range | n | metric_median |")
            lines.append("|---:|---|---:|---:|")
            for q in section.get("bins", []):
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            str(int(q.get("q_index", 0))),
                            f"[{_format_float(_to_float(q.get('param_min')), float_format)}, {_format_float(_to_float(q.get('param_max')), float_format)}]",
                            str(int(q.get("n", 0))),
                            _format_float(_to_float(q.get("metric_median")), float_format),
                        ]
                    )
                    + " |"
                )
            lines.append("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_json(
    path: Path,
    *,
    inputs: Mapping[str, Mapping[str, str]],
    counters: Counters,
    metric_keys: Sequence[str],
    param_keys: Sequence[str],
    corr_rows: Sequence[Mapping[str, Any]],
    quantile_metric: Optional[str],
    quantile_sections: Sequence[Mapping[str, Any]],
) -> None:
    payload = {
        "schema_version": SCRIPT_VERSION,
        "inputs": [
            {"path": source, "sha256": inputs[source].get("sha256", "")}
            for source in sorted(inputs.keys())
        ],
        "counts": counters.as_dict(),
        "metric_keys": [str(m) for m in metric_keys],
        "param_keys": [str(p) for p in param_keys],
        "correlations": [
            {
                "param_key": str(row.get("param_key", "")),
                "metric_key": str(row.get("metric_key", "")),
                "n": int(row.get("n", 0)),
                "pearson_r": _to_float(row.get("pearson_r")),
                "spearman_r": _to_float(row.get("spearman_r")),
            }
            for row in corr_rows
        ],
        "quantile_metric": quantile_metric,
        "quantile_sections": quantile_sections,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="phase2_e2_sensitivity_report",
        description="Stdlib-only parameter/metric sensitivity report for E2 scan JSONL artifacts.",
    )
    ap.add_argument("inputs", nargs="*", type=Path, help="Input JSONL files (positional alternative to --in-jsonl).")
    ap.add_argument("--in-jsonl", action="append", default=[], type=Path, help="Input JSONL file (repeatable).")
    ap.add_argument("--out-md", type=Path, required=True, help="Output Markdown report path.")
    ap.add_argument("--out-csv", type=Path, default=None, help="Optional CSV output for pairwise correlations.")
    ap.add_argument("--out-json", type=Path, default=None, help="Optional JSON output with full computed stats.")
    ap.add_argument(
        "--status-ok-only",
        type=int,
        choices=[0, 1],
        default=1,
        help="If 1 (default), keep only rows with status=='ok' when status field exists.",
    )
    ap.add_argument(
        "--plausibility",
        choices=["any", "plausible_only"],
        default="any",
        help=(
            "If plausible_only, keep only rows with microphysics_plausible_ok==True when field exists. "
            "Rows missing the field are treated as plausible for backward compatibility."
        ),
    )
    ap.add_argument(
        "--require-drift-positive",
        type=str,
        default=None,
        help="Optional metric key that must be > 0 for row inclusion (e.g. drift_z_min).",
    )
    ap.add_argument(
        "--metrics",
        type=str,
        default="",
        help="Comma-separated metric keys. If omitted, metrics are auto-detected.",
    )
    ap.add_argument("--top-k", type=int, default=15, help="Top-K correlations shown per metric in Markdown.")
    ap.add_argument("--quantiles", type=int, default=5, help="Number of bins for optional quantile trend tables.")
    ap.add_argument(
        "--quantile-metric",
        type=str,
        default=None,
        help="If set, add quantile trend sections for top parameters against this metric.",
    )
    ap.add_argument(
        "--float-format",
        type=str,
        default="{:.8g}",
        help="Format string for floating-point rendering in Markdown tables.",
    )
    args = ap.parse_args(argv)

    paths = _iter_unique_inputs(args.inputs, args.in_jsonl)
    if not paths:
        raise SystemExit("Provide at least one input JSONL via positional args or --in-jsonl.")
    metrics_override = _split_csv_values(args.metrics)

    rows, counters, inputs_meta, metric_keys, param_keys = _parse_rows(
        paths=paths,
        status_ok_only=bool(int(args.status_ok_only)),
        plausibility=str(args.plausibility),
        require_drift_positive=args.require_drift_positive,
        metrics_override=metrics_override if metrics_override else None,
    )
    if not rows:
        raise SystemExit("No usable rows after filtering; adjust filters or input files.")
    if not metric_keys:
        raise SystemExit("No numeric metrics found after filtering.")
    if not param_keys:
        raise SystemExit("No numeric parameters found after filtering.")

    corr_rows = _compute_correlations(rows=rows, metric_keys=metric_keys, param_keys=param_keys)

    quantile_metric = str(args.quantile_metric).strip() if args.quantile_metric else None
    quant_sections: List[Dict[str, Any]] = []
    if quantile_metric:
        if quantile_metric not in metric_keys:
            raise SystemExit(f"--quantile-metric not found in analyzed metrics: {quantile_metric}")
        quant_sections = _quantile_sections(
            rows=rows,
            corr_rows=corr_rows,
            metric_key=quantile_metric,
            quantiles=int(args.quantiles),
            max_params=min(max(1, int(args.top_k)), 10),
        )

    out_md = args.out_md.expanduser().resolve()
    out_md.parent.mkdir(parents=True, exist_ok=True)
    _write_markdown(
        path=out_md,
        inputs=inputs_meta,
        counters=counters,
        metric_keys=metric_keys,
        param_keys=param_keys,
        corr_rows=corr_rows,
        top_k=int(args.top_k),
        float_format=str(args.float_format),
        quantile_metric=quantile_metric,
        quantile_sections=quant_sections,
    )

    if args.out_csv is not None:
        out_csv = args.out_csv.expanduser().resolve()
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        _write_csv(out_csv, corr_rows)

    if args.out_json is not None:
        out_json = args.out_json.expanduser().resolve()
        out_json.parent.mkdir(parents=True, exist_ok=True)
        _write_json(
            out_json,
            inputs=inputs_meta,
            counters=counters,
            metric_keys=metric_keys,
            param_keys=param_keys,
            corr_rows=corr_rows,
            quantile_metric=quantile_metric,
            quantile_sections=quant_sections,
        )

    print(f"[ok] wrote {out_md}")
    if args.out_csv is not None:
        print(f"[ok] wrote {args.out_csv.expanduser().resolve()}")
    if args.out_json is not None:
        print(f"[ok] wrote {args.out_json.expanduser().resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

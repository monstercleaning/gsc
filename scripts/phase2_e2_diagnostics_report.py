#!/usr/bin/env python3
"""Phase-2 E2 diagnostics/sensitivity reporting from scan JSONL artifacts.

Stdlib-only post-processing:
- reads one or many JSONL inputs
- summarizes chi2/drift tradeoffs and envelope diagnostics
- extracts dominant chi2_parts, top candidates, and Spearman correlations
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
import statistics
import sys
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

V101_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V101_DIR))

from gsc.jsonl_io import open_text_read  # noqa: E402


SCRIPT_VERSION = "M19"
KNOWN_PARAM_KEYS = (
    "H0",
    "Omega_m",
    "Omega_Lambda",
    "p",
    "z_transition",
    "omega_b_h2",
    "omega_c_h2",
    "N_eff",
    "Y_p",
    "Tcmb_K",
)

AUTO_CHI2_KEYS = (
    "chi2_total",
    "chi2",
    "chi2_tot",
    "result.chi2_total",
    "result.chi2",
    "metrics.chi2_total",
    "metrics.chi2",
)

AUTO_DRIFT_PRIMARY_KEYS = (
    "drift_sign_z2_5",
    "metrics.drift_sign_z2_5",
    "result.drift_sign_z2_5",
)


@dataclass(frozen=True)
class Record:
    source: str
    line: int
    model: str
    chi2: float
    drift: Optional[float]
    params: Dict[str, float]
    microphysics: Dict[str, Any]
    microphysics_plausible_ok: bool
    microphysics_penalty: float
    microphysics_max_rel_dev: float
    microphysics_notes: List[str]
    chi2_parts: Dict[str, float]
    scalar_metrics: Dict[str, float]
    raw: Dict[str, Any]


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _to_float(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except Exception:
        return None
    if not math.isfinite(out):
        return None
    return float(out)


def _fmt(value: Optional[float], digits: int) -> str:
    if value is None:
        return "NA"
    if not math.isfinite(float(value)):
        return "NA"
    return f"{float(value):.{int(digits)}g}"


def _flatten_numeric(value: Any, prefix: str = "") -> Dict[str, float]:
    out: Dict[str, float] = {}
    if isinstance(value, Mapping):
        for key in sorted(value.keys(), key=lambda x: str(x)):
            sk = str(key)
            next_prefix = f"{prefix}.{sk}" if prefix else sk
            out.update(_flatten_numeric(value[key], prefix=next_prefix))
        return out
    if isinstance(value, (list, tuple)):
        return out
    fv = _to_float(value)
    if fv is not None and prefix:
        out[prefix] = float(fv)
    return out


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _get_nested(obj: Mapping[str, Any], dotted_key: str) -> Any:
    current: Any = obj
    for token in str(dotted_key).split("."):
        if not isinstance(current, Mapping) or token not in current:
            return None
        current = current[token]
    return current


def _get_numeric(obj: Mapping[str, Any], flat: Mapping[str, float], key: str) -> Optional[float]:
    key_s = str(key).strip()
    if not key_s:
        return None
    if key_s in flat:
        return float(flat[key_s])
    val = _get_nested(obj, key_s)
    return _to_float(val)


def _iter_jsonl_inputs(files: Sequence[Path], dirs: Sequence[Path]) -> List[Path]:
    out: List[Path] = []
    seen: set[Path] = set()

    def _add(path: Path) -> None:
        rp = path.expanduser().resolve()
        if rp in seen:
            return
        seen.add(rp)
        out.append(rp)

    for path in files:
        _add(path)
    for directory in dirs:
        root = directory.expanduser().resolve()
        if not root.is_dir():
            raise SystemExit(f"--jsonl-dir is not a directory: {root}")
        for candidate in sorted(list(root.rglob("*.jsonl")) + list(root.rglob("*.jsonl.gz"))):
            _add(candidate)
    return sorted(out)


def _extract_model(obj: Mapping[str, Any]) -> str:
    for key in ("model", "model_id", "family"):
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _extract_params(obj: Mapping[str, Any]) -> Dict[str, float]:
    params: Dict[str, float] = {}
    params_obj = _as_mapping(obj.get("params"))
    if params_obj:
        for key in sorted(params_obj.keys(), key=lambda x: str(x)):
            fv = _to_float(params_obj[key])
            if fv is not None:
                params[str(key)] = float(fv)
    else:
        for key in KNOWN_PARAM_KEYS:
            fv = _to_float(obj.get(key))
            if fv is not None:
                params[str(key)] = float(fv)
    return params


def _extract_microphysics(obj: Mapping[str, Any]) -> Dict[str, Any]:
    raw = _as_mapping(obj.get("microphysics"))
    mode = str(raw.get("mode", "none"))
    z_star_scale = _to_float(raw.get("z_star_scale"))
    r_s_scale = _to_float(raw.get("r_s_scale"))
    r_d_scale = _to_float(raw.get("r_d_scale"))
    return {
        "mode": mode if mode in {"none", "knobs"} else "none",
        "z_star_scale": 1.0 if z_star_scale is None else float(z_star_scale),
        "r_s_scale": 1.0 if r_s_scale is None else float(r_s_scale),
        "r_d_scale": 1.0 if r_d_scale is None else float(r_d_scale),
    }


def _extract_microphysics_audit(obj: Mapping[str, Any]) -> Tuple[bool, float, float, List[str]]:
    raw_plausible = obj.get("microphysics_plausible_ok")
    plausible_ok = True if raw_plausible is None else bool(raw_plausible)
    penalty = _to_float(obj.get("microphysics_penalty"))
    max_rel_dev = _to_float(obj.get("microphysics_max_rel_dev"))
    raw_notes = obj.get("microphysics_notes")
    notes: List[str] = []
    if isinstance(raw_notes, list):
        for entry in raw_notes:
            txt = str(entry).strip()
            if txt:
                notes.append(txt)
    return (
        bool(plausible_ok),
        0.0 if penalty is None else float(penalty),
        0.0 if max_rel_dev is None else float(max_rel_dev),
        notes,
    )


def _extract_chi2_parts(obj: Mapping[str, Any]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    root = _as_mapping(obj.get("chi2_parts"))
    for key in sorted(root.keys(), key=lambda x: str(x)):
        skey = str(key)
        value = root[key]
        if isinstance(value, Mapping):
            fv = _to_float(value.get("chi2"))
            if fv is not None:
                out[skey] = float(fv)
        else:
            fv = _to_float(value)
            if fv is not None:
                out[skey] = float(fv)
    return out


def _detect_chi2(
    obj: Mapping[str, Any],
    flat: Mapping[str, float],
    *,
    chi2_key: str,
) -> Tuple[Optional[float], Optional[str]]:
    if chi2_key != "auto":
        val = _get_numeric(obj, flat, chi2_key)
        return (val, chi2_key if val is not None else None)
    for key in AUTO_CHI2_KEYS:
        val = _get_numeric(obj, flat, key)
        if val is not None:
            return val, key
    return None, None


def _detect_drift(
    obj: Mapping[str, Any],
    flat: Mapping[str, float],
    *,
    drift_key: str,
) -> Tuple[Optional[float], Optional[str]]:
    if drift_key != "auto":
        val = _get_numeric(obj, flat, drift_key)
        return (val, drift_key if val is not None else None)

    for key in AUTO_DRIFT_PRIMARY_KEYS:
        val = _get_numeric(obj, flat, key)
        if val is not None:
            return val, key

    keys = sorted(flat.keys())
    for key in keys:
        low = key.lower()
        if ("dzdt" in low) and ("z3" in low):
            return float(flat[key]), key
    for key in keys:
        low = key.lower()
        if ("dv" in low) and ("z3" in low):
            return float(flat[key]), key
    for key in keys:
        if key.lower().startswith("drift_"):
            return float(flat[key]), key

    return None, None


def _rank(values: Sequence[float]) -> List[float]:
    indexed = sorted(enumerate(values), key=lambda kv: kv[1])
    out = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i + 1
        while j < len(indexed) and indexed[j][1] == indexed[i][1]:
            j += 1
        avg_rank = (float(i + 1) + float(j)) / 2.0
        for k in range(i, j):
            out[indexed[k][0]] = float(avg_rank)
        i = j
    return out


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mx = statistics.fmean(xs)
    my = statistics.fmean(ys)
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx <= 0.0 or vy <= 0.0:
        return None
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return float(cov / math.sqrt(vx * vy))


def _spearman(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    rx = _rank(xs)
    ry = _rank(ys)
    return _pearson(rx, ry)


def _parse_thresholds(spec: str) -> List[float]:
    out: List[float] = []
    for token in str(spec).split(","):
        txt = token.strip()
        if not txt:
            continue
        fv = _to_float(txt)
        if fv is None:
            raise SystemExit(f"Invalid threshold value: {txt!r}")
        out.append(float(fv))
    if not out:
        raise SystemExit("Threshold list must contain at least one value")
    # preserve first-seen order while deduplicating
    dedup: List[float] = []
    seen: set[float] = set()
    for v in out:
        if v in seen:
            continue
        seen.add(v)
        dedup.append(v)
    return dedup


def _median(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    return float(statistics.median(values))


def _percentile(sorted_values: Sequence[float], q: float) -> Optional[float]:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    q_clamped = min(max(float(q), 0.0), 1.0)
    pos = q_clamped * (len(sorted_values) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(sorted_values[lo])
    w = pos - lo
    return float(sorted_values[lo] * (1.0 - w) + sorted_values[hi] * w)


def _pareto_points(records: Sequence[Record]) -> List[Record]:
    candidates = [r for r in records if r.drift is not None and math.isfinite(r.chi2)]
    candidates.sort(key=lambda r: (float(r.chi2), str(r.source), int(r.line)))
    pareto: List[Record] = []
    max_drift = float("-inf")
    for r in candidates:
        assert r.drift is not None
        if float(r.drift) > max_drift:
            pareto.append(r)
            max_drift = float(r.drift)
    return pareto


def _stable_sort(records: Sequence[Record], *, key_fn) -> List[Record]:
    return sorted(records, key=lambda r: (*key_fn(r), str(r.source), int(r.line)))


def _write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="phase2_e2_diagnostics_report",
        description="Deterministic stdlib-only diagnostics report from phase2_e2_scan JSONL outputs.",
    )
    ap.add_argument("--jsonl", action="append", default=[], type=Path, help="Input JSONL file (repeatable).")
    ap.add_argument(
        "--jsonl-dir",
        action="append",
        default=[],
        type=Path,
        help="Directory scanned recursively for *.jsonl and *.jsonl.gz",
    )
    ap.add_argument("--outdir", type=Path, required=True, help="Output directory (required).")
    ap.add_argument("--top", type=int, default=25, help="Top-N rows per ranking block.")
    ap.add_argument("--chi2-key", type=str, default="auto", help="chi2 key/path or 'auto'.")
    ap.add_argument("--drift-key", type=str, default="auto", help="drift key/path or 'auto'.")
    ap.add_argument("--require-ok", dest="require_ok", action="store_true", default=True)
    ap.add_argument("--no-require-ok", dest="require_ok", action="store_false")
    ap.add_argument("--model-filter", type=str, default="", help="Optional regex for model/model_id/family.")
    ap.add_argument("--chi2-thresholds", type=str, default="1,4,9,25")
    ap.add_argument("--drift-thresholds", type=str, default="0")
    ap.add_argument("--float-digits", type=int, default=6)
    args = ap.parse_args(argv)

    if int(args.top) <= 0:
        raise SystemExit("--top must be > 0")
    if int(args.float_digits) <= 0:
        raise SystemExit("--float-digits must be > 0")

    model_re = re.compile(args.model_filter) if str(args.model_filter).strip() else None
    chi2_thresholds = _parse_thresholds(args.chi2_thresholds)
    drift_thresholds = _parse_thresholds(args.drift_thresholds)

    inputs = _iter_jsonl_inputs(files=args.jsonl, dirs=args.jsonl_dir)
    if not inputs:
        raise SystemExit("No inputs: provide --jsonl and/or --jsonl-dir")

    outdir = args.outdir.expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    summary_md = outdir / "e2_diagnostics_summary.md"
    best_csv = outdir / "e2_best_points.csv"
    envelope_csv = outdir / "e2_tradeoff_envelope.csv"
    corr_csv = outdir / "e2_param_correlations.csv"

    stats: Dict[str, int] = {
        "n_total_lines": 0,
        "n_parsed": 0,
        "n_used": 0,
        "n_skipped_err": 0,
        "n_skipped_model_filter": 0,
        "n_skipped_ok_false": 0,
        "n_skipped_missing_chi2": 0,
    }
    error_counts: Dict[str, int] = {}
    used: List[Record] = []
    detected_chi2_key: Optional[str] = None
    detected_drift_key: Optional[str] = None

    for path in inputs:
        with open_text_read(path) as fh:
            for line_no, raw_line in enumerate(fh, start=1):
                txt = raw_line.strip()
                if not txt:
                    continue
                stats["n_total_lines"] += 1
                try:
                    obj_any = json.loads(txt)
                except Exception:
                    stats["n_skipped_err"] += 1
                    error_counts["invalid_json"] = error_counts.get("invalid_json", 0) + 1
                    continue
                if not isinstance(obj_any, Mapping):
                    stats["n_skipped_err"] += 1
                    error_counts["non_object_json"] = error_counts.get("non_object_json", 0) + 1
                    continue
                obj = dict(obj_any)
                stats["n_parsed"] += 1

                err_text = obj.get("error", obj.get("err"))
                if isinstance(err_text, str) and err_text.strip():
                    key = f"error:{err_text.strip()[:120]}"
                    error_counts[key] = error_counts.get(key, 0) + 1

                model = _extract_model(obj)
                if model_re is not None and not model_re.search(model):
                    stats["n_skipped_model_filter"] += 1
                    continue

                if args.require_ok:
                    status_text = str(obj.get("status", "")).strip().lower()
                    if status_text and status_text != "ok":
                        stats["n_skipped_ok_false"] += 1
                        continue
                    if not status_text:
                        ok_val = obj.get("ok")
                        if ok_val is not None and not bool(ok_val):
                            stats["n_skipped_ok_false"] += 1
                            continue

                flat = _flatten_numeric(obj)
                chi2_val, used_chi2_key = _detect_chi2(obj, flat, chi2_key=str(args.chi2_key))
                if chi2_val is None:
                    stats["n_skipped_missing_chi2"] += 1
                    continue

                drift_val, used_drift_key = _detect_drift(obj, flat, drift_key=str(args.drift_key))
                if detected_chi2_key is None and used_chi2_key is not None:
                    detected_chi2_key = str(used_chi2_key)
                if detected_drift_key is None and used_drift_key is not None:
                    detected_drift_key = str(used_drift_key)

                params = _extract_params(obj)
                chi2_parts = _extract_chi2_parts(obj)
                scalar_metrics = dict(flat)
                for pkey in params.keys():
                    scalar_metrics.pop(pkey, None)
                microphysics_plausible_ok, microphysics_penalty, microphysics_max_rel_dev, microphysics_notes = (
                    _extract_microphysics_audit(obj)
                )
                rec = Record(
                    source=str(path),
                    line=int(line_no),
                    model=str(model),
                    chi2=float(chi2_val),
                    drift=None if drift_val is None else float(drift_val),
                    params=params,
                    microphysics=_extract_microphysics(obj),
                    microphysics_plausible_ok=bool(microphysics_plausible_ok),
                    microphysics_penalty=float(microphysics_penalty),
                    microphysics_max_rel_dev=float(microphysics_max_rel_dev),
                    microphysics_notes=list(microphysics_notes),
                    chi2_parts=chi2_parts,
                    scalar_metrics=scalar_metrics,
                    raw=obj,
                )
                used.append(rec)
                stats["n_used"] += 1

    if not used:
        raise SystemExit("No usable rows after filtering/parsing")

    chi2_vals = sorted(float(r.chi2) for r in used if math.isfinite(float(r.chi2)))
    drift_vals = sorted(float(r.drift) for r in used if r.drift is not None and math.isfinite(float(r.drift)))

    top_by_chi2 = _stable_sort(used, key_fn=lambda r: (float(r.chi2),))[: int(args.top)]
    top_by_drift = _stable_sort(
        [r for r in used if r.drift is not None],
        key_fn=lambda r: (-float(r.drift), float(r.chi2)),
    )[: int(args.top)]
    pareto = _pareto_points(used)
    top_pareto = _stable_sort(pareto, key_fn=lambda r: (float(r.chi2), -float(r.drift or float("-inf"))))[: int(args.top)]
    plausible_rows = [r for r in used if r.microphysics_plausible_ok]
    best_overall = min(used, key=lambda r: (float(r.chi2), str(r.source), int(r.line)))
    best_plausible = (
        min(plausible_rows, key=lambda r: (float(r.chi2), str(r.source), int(r.line)))
        if plausible_rows
        else None
    )
    recombination_methods_seen = sorted(
        {
            str(
                r.raw.get(
                    "recombination_method",
                    _as_mapping(r.raw.get("predicted")).get("recombination_method", ""),
                )
            ).strip()
            for r in used
        }
        - {""}
    )

    def _collect_metric_values(keys: Sequence[str]) -> List[float]:
        vals: List[float] = []
        for rec in used:
            found: Optional[float] = None
            for key in keys:
                value = rec.scalar_metrics.get(str(key))
                if value is None:
                    continue
                if math.isfinite(float(value)):
                    found = float(value)
                    break
            if found is not None:
                vals.append(float(found))
        return vals

    cmb_num_err_dm_vals = sorted(_collect_metric_values(("cmb_num_err_dm", "predicted.cmb_num_err_dm")))
    cmb_num_err_rs_vals = sorted(_collect_metric_values(("cmb_num_err_rs", "predicted.cmb_num_err_rs")))
    cmb_num_err_rs_drag_vals = sorted(
        _collect_metric_values(("cmb_num_err_rs_drag", "predicted.cmb_num_err_rs_drag"))
    )

    # Envelope rows
    envelope_rows: List[Dict[str, Any]] = []
    for thr in drift_thresholds:
        subset = [r for r in used if r.drift is not None and float(r.drift) >= float(thr)]
        if subset:
            by_chi2 = min(subset, key=lambda r: (float(r.chi2), str(r.source), int(r.line)))
            by_drift = max(subset, key=lambda r: (float(r.drift or float("-inf")), -float(r.chi2)))
            row = {
                "mode": "require_drift",
                "threshold": _fmt(thr, args.float_digits),
                "value": f"drift>={_fmt(thr, args.float_digits)}",
                "chi2_min": _fmt(by_chi2.chi2, args.float_digits),
                "drift_at_chi2_min": _fmt(by_chi2.drift, args.float_digits),
                "drift_max": _fmt(by_drift.drift, args.float_digits),
                "chi2_at_drift_max": _fmt(by_drift.chi2, args.float_digits),
                "n_points": int(len(subset)),
            }
        else:
            row = {
                "mode": "require_drift",
                "threshold": _fmt(thr, args.float_digits),
                "value": f"drift>={_fmt(thr, args.float_digits)}",
                "chi2_min": "NA",
                "drift_at_chi2_min": "NA",
                "drift_max": "NA",
                "chi2_at_drift_max": "NA",
                "n_points": 0,
            }
        envelope_rows.append(row)

    for thr in chi2_thresholds:
        subset = [r for r in used if float(r.chi2) <= float(thr) and r.drift is not None]
        if subset:
            by_chi2 = min(subset, key=lambda r: (float(r.chi2), str(r.source), int(r.line)))
            by_drift = max(subset, key=lambda r: (float(r.drift or float("-inf")), -float(r.chi2)))
            row = {
                "mode": "require_chi2",
                "threshold": _fmt(thr, args.float_digits),
                "value": f"chi2<={_fmt(thr, args.float_digits)}",
                "chi2_min": _fmt(by_chi2.chi2, args.float_digits),
                "drift_at_chi2_min": _fmt(by_chi2.drift, args.float_digits),
                "drift_max": _fmt(by_drift.drift, args.float_digits),
                "chi2_at_drift_max": _fmt(by_drift.chi2, args.float_digits),
                "n_points": int(len(subset)),
            }
        else:
            row = {
                "mode": "require_chi2",
                "threshold": _fmt(thr, args.float_digits),
                "value": f"chi2<={_fmt(thr, args.float_digits)}",
                "chi2_min": "NA",
                "drift_at_chi2_min": "NA",
                "drift_max": "NA",
                "chi2_at_drift_max": "NA",
                "n_points": 0,
            }
        envelope_rows.append(row)

    # Correlations
    param_keys = sorted({k for r in used for k in r.params.keys()})
    corr_rows: List[Dict[str, Any]] = []
    for key in param_keys:
        xs_chi2: List[float] = []
        ys_chi2: List[float] = []
        xs_drift: List[float] = []
        ys_drift: List[float] = []
        for r in used:
            if key not in r.params:
                continue
            px = float(r.params[key])
            xs_chi2.append(px)
            ys_chi2.append(float(r.chi2))
            if r.drift is not None:
                xs_drift.append(px)
                ys_drift.append(float(r.drift))
        rho_chi2 = _spearman(xs_chi2, ys_chi2) if len(xs_chi2) >= 2 else None
        rho_drift = _spearman(xs_drift, ys_drift) if len(xs_drift) >= 2 else None
        corr_rows.append(
            {
                "param": key,
                "spearman_rho_chi2": _fmt(rho_chi2, args.float_digits),
                "spearman_rho_drift": _fmt(rho_drift, args.float_digits),
                "n": max(len(xs_chi2), len(xs_drift)),
            }
        )

    # Dominant chi2_parts
    chi2_part_keys = sorted({k for r in used for k in r.chi2_parts.keys()})
    chi2_part_summary: List[Tuple[str, float, float, float]] = []
    for key in chi2_part_keys:
        vals = [float(r.chi2_parts[key]) for r in used if key in r.chi2_parts]
        if not vals:
            continue
        chi2_part_summary.append((key, float(statistics.fmean(vals)), float(statistics.median(vals)), float(max(vals))))
    chi2_part_summary.sort(key=lambda t: t[1], reverse=True)

    # Best points csv
    selected_blocks = [("chi2", top_by_chi2), ("drift", top_by_drift), ("pareto", top_pareto)]
    selected_records: List[Tuple[str, int, Record]] = []
    for criterion, block in selected_blocks:
        for idx, rec in enumerate(block, start=1):
            selected_records.append((criterion, idx, rec))
    selected_param_keys = sorted({k for _, _, r in selected_records for k in r.params.keys()})
    selected_metric_keys = sorted(
        {
            k
            for _, _, r in selected_records
            for k in r.scalar_metrics.keys()
            if k not in ("chi2", "chi2_total", "chi2_tot")
            and not k.endswith(".chi2")
            and not k.startswith("params.")
        }
    )

    best_fieldnames = [
        "rank",
        "criterion",
        "chi2",
        "drift",
        "model",
        "micro_mode",
        "z_star_scale",
        "r_s_scale",
        "r_d_scale",
        "microphysics_plausible_ok",
        "microphysics_penalty",
        "microphysics_max_rel_dev",
    ] + selected_param_keys + selected_metric_keys
    best_rows: List[Dict[str, Any]] = []
    for criterion, rank, rec in selected_records:
        row: Dict[str, Any] = {
            "rank": int(rank),
            "criterion": criterion,
            "chi2": _fmt(rec.chi2, args.float_digits),
            "drift": _fmt(rec.drift, args.float_digits),
            "model": rec.model,
            "micro_mode": str(rec.microphysics.get("mode", "none")),
            "z_star_scale": _fmt(_to_float(rec.microphysics.get("z_star_scale")), args.float_digits),
            "r_s_scale": _fmt(_to_float(rec.microphysics.get("r_s_scale")), args.float_digits),
            "r_d_scale": _fmt(_to_float(rec.microphysics.get("r_d_scale")), args.float_digits),
            "microphysics_plausible_ok": bool(rec.microphysics_plausible_ok),
            "microphysics_penalty": _fmt(rec.microphysics_penalty, args.float_digits),
            "microphysics_max_rel_dev": _fmt(rec.microphysics_max_rel_dev, args.float_digits),
        }
        for key in selected_param_keys:
            row[key] = _fmt(rec.params.get(key), args.float_digits) if key in rec.params else "NA"
        for key in selected_metric_keys:
            row[key] = _fmt(rec.scalar_metrics.get(key), args.float_digits) if key in rec.scalar_metrics else "NA"
        best_rows.append(row)

    _write_csv(best_csv, fieldnames=best_fieldnames, rows=best_rows)
    _write_csv(
        envelope_csv,
        fieldnames=(
            "mode",
            "threshold",
            "value",
            "chi2_min",
            "drift_at_chi2_min",
            "drift_max",
            "chi2_at_drift_max",
            "n_points",
        ),
        rows=envelope_rows,
    )
    _write_csv(
        corr_csv,
        fieldnames=("param", "spearman_rho_chi2", "spearman_rho_drift", "n"),
        rows=corr_rows,
    )

    # Summary markdown
    input_rows = [(str(p), _sha256_file(p)) for p in inputs]
    best_drift_positive = [r for r in used if r.drift is not None and float(r.drift) > 0.0]
    best_drift_positive_min_chi2 = (
        min(best_drift_positive, key=lambda r: (float(r.chi2), str(r.source), int(r.line)))
        if best_drift_positive
        else None
    )
    lines: List[str] = []
    lines.append("# Phase-2 E2 Diagnostics/Sensitivity Report")
    lines.append("")
    lines.append(f"- Version: `{SCRIPT_VERSION}`")
    lines.append(f"- Generated (UTC): `{_now_utc()}`")
    lines.append("")
    lines.append("## Inputs")
    lines.append(f"- Files: `{len(inputs)}`")
    lines.append("### Input SHA256")
    for path_str, digest in input_rows:
        lines.append(f"- `{path_str}`  sha256=`{digest}`")
    lines.append("")
    lines.append("## Parse/Filter Stats")
    lines.append(f"- N_total_lines: `{stats['n_total_lines']}`")
    lines.append(f"- N_parsed: `{stats['n_parsed']}`")
    lines.append(f"- N_used: `{stats['n_used']}`")
    lines.append(f"- N_skipped_err: `{stats['n_skipped_err']}`")
    lines.append(f"- N_skipped_model_filter: `{stats['n_skipped_model_filter']}`")
    lines.append(f"- N_skipped_ok_false: `{stats['n_skipped_ok_false']}`")
    lines.append(f"- N_skipped_missing_chi2: `{stats['n_skipped_missing_chi2']}`")
    if error_counts:
        lines.append("")
        lines.append("### Error Counters")
        for key in sorted(error_counts.keys()):
            lines.append(f"- `{key}`: `{error_counts[key]}`")
    lines.append("")
    lines.append("## Key Summary")
    lines.append(f"- chi2 key: `{detected_chi2_key or args.chi2_key}`")
    lines.append(f"- drift key: `{detected_drift_key or args.drift_key}`")
    lines.append(f"- chi2 min/median/p90: `{_fmt(min(chi2_vals), args.float_digits)}` / `{_fmt(_median(chi2_vals), args.float_digits)}` / `{_fmt(_percentile(chi2_vals, 0.9), args.float_digits)}`")
    if drift_vals:
        lines.append(
            f"- drift min/median/p90: `{_fmt(min(drift_vals), args.float_digits)}` / `{_fmt(_median(drift_vals), args.float_digits)}` / `{_fmt(_percentile(drift_vals, 0.9), args.float_digits)}`"
        )
    else:
        lines.append("- drift min/median/p90: `NA / NA / NA`")
    lines.append("")
    lines.append("## Tradeoff / No-Go Envelope")
    if best_drift_positive_min_chi2 is None:
        lines.append("- min chi2 among drift>0: `NA` (no drift-positive points)")
    else:
        lines.append(
            f"- min chi2 among drift>0: `{_fmt(best_drift_positive_min_chi2.chi2, args.float_digits)}` (drift=`{_fmt(best_drift_positive_min_chi2.drift, args.float_digits)}`)"
        )
    for row in envelope_rows:
        lines.append(
            f"- {row['mode']} {row['value']}: n={row['n_points']}, chi2_min={row['chi2_min']}, drift_max={row['drift_max']}"
        )
    lines.append("")
    lines.append("## Microphysics Knobs")
    n_total = int(len(used))
    n_plausible = int(len(plausible_rows))
    frac_plausible = (float(n_plausible) / float(n_total)) if n_total > 0 else 0.0
    lines.append(f"- N_total: `{n_total}`")
    lines.append(f"- N_plausible: `{n_plausible}`")
    lines.append(f"- fraction_plausible: `{_fmt(frac_plausible, args.float_digits)}`")
    lines.append(f"- best_overall_chi2: `{_fmt(best_overall.chi2, args.float_digits)}`")
    if best_plausible is None:
        lines.append("- best_plausible_chi2: `NA` (no plausible rows)")
    else:
        lines.append(f"- best_plausible_chi2: `{_fmt(best_plausible.chi2, args.float_digits)}`")
    if not best_overall.microphysics_plausible_ok:
        lines.append(
            f"- best_overall_non_plausible_penalty: `{_fmt(best_overall.microphysics_penalty, args.float_digits)}`"
        )
        notes = best_overall.microphysics_notes if best_overall.microphysics_notes else ["none"]
        lines.append(f"- best_overall_non_plausible_notes: `{'; '.join(notes)}`")
    lines.append("")
    knobs = [r for r in used if str(r.microphysics.get("mode", "none")) == "knobs"]
    lines.append(f"- Knobs mode rows: `{len(knobs)}`")
    if knobs:
        for key in ("z_star_scale", "r_s_scale", "r_d_scale"):
            values = [
                float(r.microphysics[key])
                for r in knobs
                if _to_float(r.microphysics.get(key)) is not None
            ]
            if values:
                lines.append(
                    f"- {key}: min={_fmt(min(values), args.float_digits)}, "
                    f"mean={_fmt(statistics.fmean(values), args.float_digits)}, "
                    f"max={_fmt(max(values), args.float_digits)}"
                )
            else:
                lines.append(f"- {key}: NA")
    lines.append("")
    lines.append("## Numerics Robustness")
    if recombination_methods_seen:
        lines.append(f"- recombination_methods_seen: `{', '.join(recombination_methods_seen)}`")
    else:
        lines.append("- recombination_methods_seen: `NA`")

    def _stats_line(name: str, values: Sequence[float]) -> None:
        if not values:
            lines.append(f"- {name} min/median/max: `NA / NA / NA`")
            return
        lines.append(
            f"- {name} min/median/max: "
            f"`{_fmt(min(values), args.float_digits)} / "
            f"{_fmt(_median(values), args.float_digits)} / "
            f"{_fmt(max(values), args.float_digits)}`"
        )

    _stats_line("cmb_num_err_dm", cmb_num_err_dm_vals)
    _stats_line("cmb_num_err_rs", cmb_num_err_rs_vals)
    _stats_line("cmb_num_err_rs_drag", cmb_num_err_rs_drag_vals)
    lines.append("")
    lines.append("## Dominant chi2_parts")
    if not chi2_part_summary:
        lines.append("- none")
    else:
        for key, mean_v, med_v, max_v in chi2_part_summary:
            lines.append(
                f"- `{key}`: mean={_fmt(mean_v, args.float_digits)}, median={_fmt(med_v, args.float_digits)}, max={_fmt(max_v, args.float_digits)}"
            )
        best_chi2 = min(used, key=lambda r: (float(r.chi2), str(r.source), int(r.line)))
        if best_chi2.chi2_parts:
            lines.append("- best-by-chi2 top chi2_parts:")
            top_parts = sorted(best_chi2.chi2_parts.items(), key=lambda kv: kv[1], reverse=True)[:5]
            for key, val in top_parts:
                lines.append(f"  - `{key}` = `{_fmt(val, args.float_digits)}`")
    lines.append("")
    lines.append("## Top Candidates")
    lines.append(f"- top by chi2: `{len(top_by_chi2)}`")
    lines.append(f"- top by drift: `{len(top_by_drift)}`")
    lines.append(f"- top Pareto: `{len(top_pareto)}`")
    lines.append("")
    lines.append("## Correlations (Spearman)")
    sortable_corr: List[Tuple[str, Optional[float], Optional[float], int]] = []
    for row in corr_rows:
        rho_chi2 = _to_float(row["spearman_rho_chi2"])
        rho_drift = _to_float(row["spearman_rho_drift"])
        sortable_corr.append((str(row["param"]), rho_chi2, rho_drift, int(row["n"])))
    top_corr_chi2 = sorted(sortable_corr, key=lambda t: abs(t[1]) if t[1] is not None else -1.0, reverse=True)[:10]
    top_corr_drift = sorted(sortable_corr, key=lambda t: abs(t[2]) if t[2] is not None else -1.0, reverse=True)[:10]
    lines.append("- Top |rho| vs chi2:")
    for p, rc, _, n in top_corr_chi2:
        lines.append(f"  - `{p}`: rho={_fmt(rc, args.float_digits)} (n={n})")
    lines.append("- Top |rho| vs drift:")
    for p, _, rd, n in top_corr_drift:
        lines.append(f"  - `{p}`: rho={_fmt(rd, args.float_digits)} (n={n})")
    lines.append("")
    lines.append("## Outputs")
    lines.append(f"- `{best_csv}`")
    lines.append(f"- `{envelope_csv}`")
    lines.append(f"- `{corr_csv}`")

    summary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[ok] wrote {summary_md}")
    print(f"[ok] wrote {best_csv}")
    print(f"[ok] wrote {envelope_csv}")
    print(f"[ok] wrote {corr_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

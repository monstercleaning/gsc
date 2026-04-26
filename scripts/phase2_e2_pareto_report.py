#!/usr/bin/env python3
"""Build Phase-2 E2 tradeoff diagnostics from JSONL scan outputs.

This is a stdlib-only post-processing tool for `phase2_e2_scan.py` JSONL files.
It summarizes best achievable CMB chi2 under drift conditions and extracts a
Pareto frontier in (chi2_cmb, drift_margin=min_z_dot).
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Set, Tuple

from _outdir import resolve_outdir, resolve_path_under_outdir

V101_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V101_DIR))

from gsc.early_time.refine_plan_v1 import write_refine_plan_v1  # noqa: E402
from gsc.jsonl_io import open_text_read  # noqa: E402
from gsc.search_sampling import iter_halton_points, iter_lhs_points, iter_random_points  # noqa: E402
from gsc.structure.rsd_overlay import rsd_overlay_for_e2_record  # noqa: E402


DEFAULT_RSD_DATA_PATH = V101_DIR / "data" / "structure" / "fsigma8_gold2017_plus_zhao2018.csv"
RSD_CHI2_FIELD_PRIORITY: Tuple[str, ...] = (
    "rsd_chi2_total",
    "rsd_chi2",
    "rsd_chi2_min",
)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _finite_float(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except Exception:
        return None
    if not math.isfinite(out):
        return None
    return out


def _to_json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Mapping):
        return {str(k): _to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_json_safe(v) for v in value]
    try:
        out = float(value)
    except Exception:
        return str(value)
    return out if math.isfinite(out) else None


def _parse_bool_like(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if not math.isfinite(float(value)):
            return None
        if float(value) == 1.0:
            return True
        if float(value) == 0.0:
            return False
        return None
    text = str(value).strip().lower()
    if text in {"true", "t", "yes", "y", "1"}:
        return True
    if text in {"false", "f", "no", "n", "0"}:
        return False
    return None


def _mean(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    total = 0.0
    for value in values:
        total += float(value)
    return float(total / float(len(values)))


@dataclass(frozen=True)
class RobustAggregate:
    params_hash: str
    n_runs: int
    chi2_cmb_min: Optional[float]
    chi2_cmb_mean: Optional[float]
    chi2_cmb_max: Optional[float]
    chi2_total_min: Optional[float]
    chi2_total_mean: Optional[float]
    chi2_total_max: Optional[float]
    drift_metric_min: Optional[float]
    drift_metric_mean: Optional[float]
    drift_metric_max: Optional[float]
    drift_consistent: Optional[bool]
    plausible_ok: Optional[bool]
    raw: Dict[str, Any]

@dataclass(frozen=True)
class Point:
    source_jsonl: str
    line: int
    model: str
    params_hash: str
    chi2_cmb: Optional[float]
    chi2_total: Optional[float]
    drift_margin: Optional[float]
    all_positive: bool
    invariants_ok: bool
    params: Dict[str, float]
    params_all: Dict[str, Any]
    microphysics: Dict[str, Any]
    microphysics_plausible_ok: bool
    microphysics_penalty: float
    microphysics_max_rel_dev: float
    microphysics_notes: List[str]
    chi2_parts: Dict[str, Any]
    raw: Dict[str, Any]
    robust_n_runs: Optional[int] = None
    robust_chi2_cmb_min: Optional[float] = None
    robust_chi2_cmb_mean: Optional[float] = None
    robust_chi2_cmb_max: Optional[float] = None
    robust_chi2_total_min: Optional[float] = None
    robust_chi2_total_mean: Optional[float] = None
    robust_chi2_total_max: Optional[float] = None
    robust_drift_metric_min: Optional[float] = None
    robust_drift_metric_mean: Optional[float] = None
    robust_drift_metric_max: Optional[float] = None
    robust_drift_consistent: Optional[bool] = None
    robust_microphysics_plausible_ok: Optional[bool] = None


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _extract_microphysics(obj: Mapping[str, Any]) -> Dict[str, Any]:
    raw = _as_mapping(obj.get("microphysics"))
    mode = str(raw.get("mode", "none"))
    z_star_scale = _finite_float(raw.get("z_star_scale"))
    r_s_scale = _finite_float(raw.get("r_s_scale"))
    r_d_scale = _finite_float(raw.get("r_d_scale"))
    return {
        "mode": mode if mode in {"none", "knobs"} else "none",
        "z_star_scale": 1.0 if z_star_scale is None else float(z_star_scale),
        "r_s_scale": 1.0 if r_s_scale is None else float(r_s_scale),
        "r_d_scale": 1.0 if r_d_scale is None else float(r_d_scale),
    }


def _extract_point(obj: Mapping[str, Any], *, source_jsonl: str, line: int) -> Point:
    chi2_parts = dict(_as_mapping(obj.get("chi2_parts")))
    cmb = _as_mapping(chi2_parts.get("cmb"))
    drift_parts = _as_mapping(chi2_parts.get("drift"))
    drift = _as_mapping(obj.get("drift"))
    invariants = _as_mapping(chi2_parts.get("invariants"))

    chi2_cmb = _finite_float(cmb.get("chi2"))
    if chi2_cmb is None:
        chi2_cmb = _finite_float(obj.get("chi2_cmb"))

    chi2_total = _finite_float(obj.get("chi2_total"))
    if chi2_total is None:
        chi2_total = _finite_float(obj.get("chi2"))

    drift_margin = _finite_float(drift.get("min_z_dot"))
    if drift_margin is None:
        drift_margin = _finite_float(drift_parts.get("min_zdot_si"))
    if drift_margin is None:
        drift_margin = _finite_float(obj.get("min_zdot_si"))

    if "all_positive" in drift:
        all_positive = bool(drift.get("all_positive"))
    elif "drift_pass" in obj:
        all_positive = bool(obj.get("drift_pass"))
    else:
        all_positive = bool(drift_parts.get("sign_ok"))

    if "invariants_ok" in obj:
        invariants_ok = bool(obj.get("invariants_ok"))
    else:
        invariants_ok = bool(invariants.get("ok"))

    params_hash_raw = obj.get("params_hash")
    params_hash = str(params_hash_raw).strip() if params_hash_raw is not None else ""

    params_raw = _as_mapping(obj.get("params"))
    params: Dict[str, float] = {}
    for key in sorted(params_raw.keys()):
        val = _finite_float(params_raw[key])
        if val is not None:
            params[str(key)] = float(val)
    params_all: Dict[str, Any] = {
        str(key): _to_json_safe(params_raw[key]) for key in sorted(params_raw.keys())
    }

    raw_plausible = obj.get("microphysics_plausible_ok")
    microphysics_plausible_ok = True if raw_plausible is None else bool(raw_plausible)
    microphysics_penalty = _finite_float(obj.get("microphysics_penalty"))
    microphysics_max_rel_dev = _finite_float(obj.get("microphysics_max_rel_dev"))
    raw_notes = obj.get("microphysics_notes")
    microphysics_notes: List[str] = []
    if isinstance(raw_notes, Sequence) and not isinstance(raw_notes, (str, bytes)):
        for entry in raw_notes:
            text = str(entry).strip()
            if text:
                microphysics_notes.append(text)

    return Point(
        source_jsonl=str(source_jsonl),
        line=int(line),
        model=str(obj.get("model", "")),
        params_hash=str(params_hash),
        chi2_cmb=chi2_cmb,
        chi2_total=chi2_total,
        drift_margin=drift_margin,
        all_positive=bool(all_positive),
        invariants_ok=bool(invariants_ok),
        params=params,
        params_all=params_all,
        microphysics=_extract_microphysics(obj),
        microphysics_plausible_ok=bool(microphysics_plausible_ok),
        microphysics_penalty=0.0 if microphysics_penalty is None else float(microphysics_penalty),
        microphysics_max_rel_dev=0.0 if microphysics_max_rel_dev is None else float(microphysics_max_rel_dev),
        microphysics_notes=list(microphysics_notes),
        chi2_parts={str(k): _to_json_safe(v) for k, v in chi2_parts.items()},
        raw={str(k): _to_json_safe(v) for k, v in obj.items()},
    )


def _iter_jsonl_paths(*, files: Sequence[Path], dirs: Sequence[Path]) -> List[Path]:
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


def _load_points(paths: Sequence[Path]) -> Tuple[List[Point], Dict[str, int]]:
    stats = {
        "n_total_lines": 0,
        "n_invalid_json": 0,
        "n_invalid_shape": 0,
    }
    out: List[Point] = []
    for path in paths:
        if not path.is_file():
            raise SystemExit(f"Input JSONL not found: {path}")
        with open_text_read(path) as fh:
            for idx, line in enumerate(fh, start=1):
                text = line.strip()
                if not text:
                    continue
                stats["n_total_lines"] += 1
                try:
                    obj = json.loads(text)
                except Exception:
                    stats["n_invalid_json"] += 1
                    continue
                if not isinstance(obj, Mapping):
                    stats["n_invalid_shape"] += 1
                    continue
                out.append(_extract_point(obj, source_jsonl=str(path), line=idx))
    return out, stats


def _point_sort_key(point: Point) -> Tuple[float, float, str, int]:
    chi2 = point.chi2_cmb if point.chi2_cmb is not None else float("inf")
    margin = point.drift_margin if point.drift_margin is not None else float("-inf")
    return (float(chi2), -float(margin), str(point.source_jsonl), int(point.line))


def _point_to_dict(point: Point) -> Dict[str, Any]:
    return {
        "source_jsonl": str(point.source_jsonl),
        "line": int(point.line),
        "model": str(point.model),
        "params_hash": str(point.params_hash),
        "chi2_cmb": point.chi2_cmb,
        "chi2_total": point.chi2_total,
        "drift_margin": point.drift_margin,
        "all_positive": bool(point.all_positive),
        "invariants_ok": bool(point.invariants_ok),
        "params": {k: float(v) for k, v in sorted(point.params.items())},
        "microphysics": _to_json_safe(point.microphysics),
        "microphysics_plausible_ok": bool(point.microphysics_plausible_ok),
        "microphysics_penalty": float(point.microphysics_penalty),
        "microphysics_max_rel_dev": float(point.microphysics_max_rel_dev),
        "microphysics_notes": list(point.microphysics_notes),
        "robust_n_runs": point.robust_n_runs,
        "robust_chi2_cmb_min": point.robust_chi2_cmb_min,
        "robust_chi2_cmb_mean": point.robust_chi2_cmb_mean,
        "robust_chi2_cmb_max": point.robust_chi2_cmb_max,
        "robust_chi2_total_min": point.robust_chi2_total_min,
        "robust_chi2_total_mean": point.robust_chi2_total_mean,
        "robust_chi2_total_max": point.robust_chi2_total_max,
        "robust_drift_metric_min": point.robust_drift_metric_min,
        "robust_drift_metric_mean": point.robust_drift_metric_mean,
        "robust_drift_metric_max": point.robust_drift_metric_max,
        "robust_drift_consistent": point.robust_drift_consistent,
        "robust_microphysics_plausible_ok": point.robust_microphysics_plausible_ok,
        "chi2_parts": _to_json_safe(point.chi2_parts),
    }


def _params_signature(params: Mapping[str, float]) -> Tuple[Tuple[str, float], ...]:
    return tuple(sorted((str(k), float(v)) for k, v in params.items()))


def _params_hash(params: Mapping[str, float]) -> str:
    canonical = json.dumps(
        {str(k): float(v) for k, v in sorted(params.items())},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _point_status_ok(point: Point) -> bool:
    status = str(point.raw.get("status", "")).strip().lower()
    if not status:
        return True
    return status == "ok"


def _point_status_label(point: Point) -> str:
    status = str(point.raw.get("status", "")).strip().lower()
    if not status:
        return "ok_legacy"
    return status


def _point_is_drift_skipped(point: Point) -> bool:
    status = _point_status_label(point)
    return status == "skipped_drift" or status.startswith("skipped_drift")


def _point_has_required_metrics(point: Point) -> bool:
    return (
        point.chi2_cmb is not None
        and math.isfinite(float(point.chi2_cmb))
        and point.drift_margin is not None
        and math.isfinite(float(point.drift_margin))
    )


def _point_is_eligible_for_pareto(point: Point, *, status_filter: str) -> bool:
    if not _point_has_required_metrics(point):
        return False
    if not bool(point.invariants_ok):
        return False
    return _point_status_allowed(point, status_filter=status_filter)


def _point_status_allowed(point: Point, *, status_filter: str) -> bool:
    if str(status_filter) == "ok_only":
        return _point_status_ok(point)
    return True


def _get_dotted_path(payload: Mapping[str, Any], dotted_path: str) -> Any:
    if not dotted_path:
        return None
    cur: Any = payload
    for token in str(dotted_path).split("."):
        if not isinstance(cur, Mapping):
            return None
        if token not in cur:
            return None
        cur = cur[token]
    return cur


def _extract_metric_value(point: Point, metric_key: str) -> Optional[float]:
    key = str(metric_key).strip()
    if not key:
        return None
    if key == "chi2_cmb":
        return point.chi2_cmb
    if key == "chi2_total":
        return point.chi2_total
    if key == "chi2":
        return _finite_float(point.raw.get("chi2"))
    return _finite_float(_get_dotted_path(point.raw, key))


def _resolve_refine_target_metric(points: Sequence[Point], requested: str) -> str:
    raw = str(requested).strip()
    if raw:
        found = any(_extract_metric_value(point, raw) is not None for point in points)
        if not found:
            raise SystemExit(
                f"--refine-target-metric '{raw}' not found in input points with finite values"
            )
        return raw

    for candidate in ("chi2_cmb", "chi2_total", "chi2"):
        if any(_extract_metric_value(point, candidate) is not None for point in points):
            return candidate
    raise SystemExit(
        "Unable to auto-detect refine target metric; pass --refine-target-metric explicitly "
        "(tried chi2_cmb, chi2_total, chi2)."
    )


def _extract_nonnumeric_params(point: Point) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key in sorted(point.params_all.keys()):
        value = point.params_all[key]
        if _finite_float(value) is not None:
            continue
        out[str(key)] = value
    return out


def _infer_integer_param_keys(points: Sequence[Point]) -> Set[str]:
    observed: Dict[str, List[float]] = {}
    for point in points:
        raw_params = _as_mapping(point.raw.get("params"))
        for key in sorted(raw_params.keys()):
            value = _finite_float(raw_params[key])
            if value is None:
                continue
            observed.setdefault(str(key), []).append(float(value))

    integer_keys: Set[str] = set()
    for key, values in observed.items():
        if not values:
            continue
        all_integral = True
        for value in values:
            if not math.isclose(value, round(value), rel_tol=0.0, abs_tol=1e-12):
                all_integral = False
                break
        if all_integral:
            integer_keys.add(str(key))
    return integer_keys


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _point_key(point: Point) -> Tuple[str, int]:
    return (str(point.source_jsonl), int(point.line))


def _rank_tiebreak_token(point: Point) -> str:
    params_hash = str(point.params_hash).strip()
    if params_hash:
        return params_hash
    fallback = f"{str(point.source_jsonl)}:{int(point.line)}"
    return hashlib.sha256(fallback.encode("utf-8")).hexdigest()


def _extract_point_rsd_chi2(
    point: Point,
    *,
    field: str,
    overlay_by_key: Optional[Mapping[Tuple[str, int], Mapping[str, Any]]] = None,
) -> Optional[float]:
    key = str(field).strip()
    if not key:
        return None
    val = _finite_float(_get_dotted_path(point.raw, key))
    if val is not None:
        return float(val)
    if overlay_by_key is None:
        return None
    overlay = _as_mapping(overlay_by_key.get(_point_key(point), {}))
    if key in {"rsd_chi2_total", "rsd_chi2", "rsd_chi2_min"}:
        val = _finite_float(overlay.get("chi2_rsd_min"))
        if val is not None:
            return float(val)
    val = _finite_float(overlay.get(key))
    if val is not None:
        return float(val)
    return None


def _resolve_rsd_chi2_field(
    *,
    points: Sequence[Point],
    requested_field: str,
    overlay_by_key: Optional[Mapping[Tuple[str, int], Mapping[str, Any]]] = None,
) -> Optional[str]:
    requested = str(requested_field).strip()
    if requested:
        has_values = any(
            _extract_point_rsd_chi2(point, field=requested, overlay_by_key=overlay_by_key) is not None
            for point in points
        )
        return requested if has_values else None

    for candidate in RSD_CHI2_FIELD_PRIORITY:
        has_values = any(
            _extract_point_rsd_chi2(point, field=candidate, overlay_by_key=overlay_by_key) is not None
            for point in points
        )
        if has_values:
            return str(candidate)
    return None


def _rank_components_for_point(
    point: Point,
    *,
    rank_by: str,
    rsd_chi2_field: Optional[str],
    overlay_by_key: Optional[Mapping[Tuple[str, int], Mapping[str, Any]]] = None,
) -> Optional[Dict[str, Optional[float]]]:
    mode = str(rank_by)
    chi2_total = _finite_float(point.chi2_total)
    precomputed_joint = _finite_float(point.raw.get("chi2_joint_total")) if mode == "joint" else None
    rsd_chi2: Optional[float] = None
    rsd_weight_used = _finite_float(point.raw.get("rsd_chi2_weight"))
    if rsd_weight_used is None:
        rsd_weight_used = 1.0
    if mode in {"rsd", "joint"}:
        if not rsd_chi2_field:
            if mode == "joint" and precomputed_joint is not None:
                rsd_chi2 = None
            else:
                return None
        else:
            rsd_chi2 = _extract_point_rsd_chi2(
                point,
                field=str(rsd_chi2_field),
                overlay_by_key=overlay_by_key,
            )
    if mode == "rsd":
        if rsd_chi2 is None:
            return None
        rank_metric = float(rsd_chi2)
    elif mode == "cmb":
        if chi2_total is None:
            return None
        rank_metric = float(chi2_total)
    elif mode == "joint":
        if precomputed_joint is not None:
            rank_metric = float(precomputed_joint)
            if rsd_chi2 is None and chi2_total is not None and abs(float(rsd_weight_used)) > 0.0:
                rsd_chi2 = float((float(rank_metric) - float(chi2_total)) / float(rsd_weight_used))
        else:
            if chi2_total is None or rsd_chi2 is None:
                return None
            rank_metric = float(chi2_total + float(rsd_weight_used) * float(rsd_chi2))
    else:
        return None

    return {
        "rank_metric": float(rank_metric),
        "chi2_total": None if chi2_total is None else float(chi2_total),
        "rsd_chi2": None if rsd_chi2 is None else float(rsd_chi2),
        "rsd_chi2_weight": float(rsd_weight_used),
    }


def _rank_points_by_mode(
    points: Sequence[Point],
    *,
    rank_by: str,
    rsd_chi2_field: Optional[str],
    overlay_by_key: Optional[Mapping[Tuple[str, int], Mapping[str, Any]]] = None,
) -> Tuple[List[Point], Dict[Tuple[str, int], Dict[str, Optional[float]]]]:
    ranked_rows: List[Tuple[Tuple[Any, ...], Point, Dict[str, Optional[float]]]] = []
    components_by_key: Dict[Tuple[str, int], Dict[str, Optional[float]]] = {}

    for point in points:
        comps = _rank_components_for_point(
            point,
            rank_by=str(rank_by),
            rsd_chi2_field=rsd_chi2_field,
            overlay_by_key=overlay_by_key,
        )
        if comps is None:
            continue
        rank_metric = float(comps.get("rank_metric") or float("inf"))
        chi2_total = _finite_float(comps.get("chi2_total"))
        sort_key = (
            float(rank_metric),
            float(chi2_total) if chi2_total is not None else float("inf"),
            _rank_tiebreak_token(point),
            str(point.source_jsonl),
            int(point.line),
        )
        ranked_rows.append((sort_key, point, comps))

    ranked_rows.sort(key=lambda item: item[0])
    ordered_points: List[Point] = []
    for _, point, comps in ranked_rows:
        key = _point_key(point)
        components_by_key[key] = dict(comps)
        ordered_points.append(point)
    return ordered_points, components_by_key


def _missing_data_overlay(*, ap_correction: bool, data_sha256: Optional[str]) -> Dict[str, Any]:
    return {
        "rsd_overlay_status": "skipped_missing_data",
        "chi2_rsd_min": None,
        "rsd_sigma8_0_best": None,
        "chi2_combined": None,
        "rsd_n": 0,
        "rsd_data_sha256": data_sha256,
        "rsd_ap_correction": bool(ap_correction),
    }


def _precomputed_rsd_overlay(
    *,
    point: Point,
    rsd_weight: float,
    data_sha256: Optional[str],
) -> Optional[Dict[str, Any]]:
    raw = _as_mapping(point.raw)
    chi2_rsd = _finite_float(raw.get("rsd_chi2"))
    sigma8_best = _finite_float(raw.get("rsd_sigma8_0_best"))
    overlay_ok = bool(raw.get("rsd_overlay_ok"))
    if not overlay_ok or chi2_rsd is None:
        return None

    chi2_total = _finite_float(point.chi2_total)
    if chi2_total is not None:
        chi2_combined = float(chi2_total + float(rsd_weight) * float(chi2_rsd))
    else:
        chi2_combined = None

    ap_raw = raw.get("rsd_ap_correction")
    ap_text = str(ap_raw).strip().lower()
    ap_bool = ap_text in {"on", "true", "1", "yes", "approx"}
    rsd_data_sha = str(raw.get("rsd_dataset_sha256") or data_sha256 or "").strip() or None
    rsd_n = int(_finite_float(raw.get("rsd_n")) or 0)

    return {
        "rsd_overlay_status": "ok",
        "chi2_rsd_min": float(chi2_rsd),
        "rsd_sigma8_0_best": sigma8_best,
        "chi2_combined": chi2_combined,
        "rsd_n": int(rsd_n),
        "rsd_data_sha256": rsd_data_sha,
        "rsd_ap_correction": bool(ap_bool),
    }


def _as_numeric_bounds(raw: Any) -> Optional[Tuple[float, float]]:
    lo: Optional[float] = None
    hi: Optional[float] = None
    if isinstance(raw, Mapping):
        lo = _finite_float(raw.get("min"))
        hi = _finite_float(raw.get("max"))
    elif isinstance(raw, (list, tuple)) and len(raw) == 2:
        lo = _finite_float(raw[0])
        hi = _finite_float(raw[1])
    if lo is None or hi is None:
        return None
    if not (math.isfinite(lo) and math.isfinite(hi) and hi > lo):
        return None
    return float(lo), float(hi)


def _extract_global_bounds_from_points(points: Sequence[Point]) -> Tuple[Dict[str, Tuple[float, float]], str]:
    # Preferred source: explicit per-record bounds metadata if present.
    for point in points:
        sampler = _as_mapping(point.raw.get("sampler"))
        detail = _as_mapping(sampler.get("detail"))
        candidate = detail.get("bounds")
        if isinstance(candidate, Mapping):
            parsed: Dict[str, Tuple[float, float]] = {}
            for key in sorted(str(k) for k in candidate.keys()):
                bounds = _as_numeric_bounds(candidate[key])
                if bounds is None:
                    parsed = {}
                    break
                parsed[str(key)] = bounds
            if parsed:
                return parsed, "sampler_detail_bounds"

    # Fallback: infer from observed parameter values.
    inferred: Dict[str, Tuple[float, float]] = {}
    keys = sorted({k for point in points for k in point.params.keys()})
    for key in keys:
        values = [float(point.params[key]) for point in points if key in point.params]
        if not values:
            continue
        lo = float(min(values))
        hi = float(max(values))
        if hi <= lo:
            eps = max(abs(lo) * 1e-6, 1e-6)
            lo -= eps
            hi += eps
        inferred[str(key)] = (float(lo), float(hi))
    return inferred, "inferred_from_points"


def _refine_local_bounds_for_seed(
    *,
    seed: Mapping[str, float],
    global_bounds: Mapping[str, Tuple[float, float]],
    radius_rel: float,
) -> Dict[str, Tuple[float, float]]:
    out: Dict[str, Tuple[float, float]] = {}
    for key in sorted(seed.keys()):
        x = float(seed[key])
        if key in global_bounds:
            g_lo, g_hi = global_bounds[key]
        else:
            g_lo, g_hi = (x - 1.0, x + 1.0)
        span = float(g_hi - g_lo)
        if abs(x) > 0.0:
            lo = float(x * (1.0 - float(radius_rel)))
            hi = float(x * (1.0 + float(radius_rel)))
            lo, hi = (lo, hi) if lo <= hi else (hi, lo)
        else:
            r0 = float(radius_rel) * span if span > 0.0 else max(float(radius_rel), 1e-3)
            lo = float(-r0)
            hi = float(r0)
        lo = max(float(lo), float(g_lo))
        hi = min(float(hi), float(g_hi))
        if hi <= lo:
            eps = max(abs(x) * 1e-6, 1e-9)
            lo = max(float(g_lo), float(x - eps))
            hi = min(float(g_hi), float(x + eps))
        if hi <= lo:
            hi = float(lo + max(1e-12, abs(lo) * 1e-12))
        out[str(key)] = (float(lo), float(hi))
    return out


def _iter_refine_points(
    *,
    local_bounds: Mapping[str, Tuple[float, float]],
    sampler: str,
    n_points: int,
    seed: int,
) -> Iterator[Dict[str, float]]:
    if sampler == "lhs":
        return iter_lhs_points(local_bounds, n=int(n_points), seed=int(seed))
    if sampler == "halton":
        return iter_halton_points(local_bounds, n=int(n_points), seed=int(seed), scramble=False, skip=0)
    if sampler == "random":
        return iter_random_points(local_bounds, n=int(n_points), seed=int(seed))
    raise ValueError(f"Unsupported refine sampler: {sampler}")


def _generate_local_rows(
    *,
    seed_params: Mapping[str, float],
    local_bounds: Mapping[str, Tuple[float, float]],
    sampler: str,
    n_points: int,
    seed: int,
) -> List[Dict[str, float]]:
    seed_signature = _params_signature(seed_params)
    local_iter = _iter_refine_points(
        local_bounds=local_bounds,
        sampler=str(sampler),
        n_points=int(n_points),
        seed=int(seed),
    )
    local_rows: List[Dict[str, float]] = []
    seen_local: set[Tuple[Tuple[str, float], ...]] = set()
    for candidate in local_iter:
        params = {k: float(v) for k, v in sorted(candidate.items())}
        sig = _params_signature(params)
        if sig == seed_signature or sig in seen_local:
            continue
        seen_local.add(sig)
        local_rows.append(params)
        if len(local_rows) >= int(n_points):
            break
    if len(local_rows) < int(n_points):
        topup_iter = iter_random_points(
            local_bounds,
            n=max(1, int(n_points) * 2),
            seed=int(seed) + 7919,
        )
        for candidate in topup_iter:
            params = {k: float(v) for k, v in sorted(candidate.items())}
            sig = _params_signature(params)
            if sig == seed_signature or sig in seen_local:
                continue
            seen_local.add(sig)
            local_rows.append(params)
            if len(local_rows) >= int(n_points):
                break
    return local_rows


def _clamp_value(value: float, lo: float, hi: float) -> float:
    return float(min(max(float(value), float(lo)), float(hi)))


def _build_sensitivity_rows_for_seed(
    *,
    seed_point: Point,
    neighbor_pool: Sequence[Point],
    global_bounds: Mapping[str, Tuple[float, float]],
    metric_key: str,
    n_neighbors: int,
    n_per_seed: int,
    top_params: int,
    step_frac: float,
    direction_mode: str,
    hold_fixed_nonnumeric: bool,
    integer_params: Set[str],
    fallback_sampler: str,
    fallback_seed: int,
    radius_rel: float,
) -> Tuple[List[Dict[str, float]], Optional[str]]:
    seed_params = {k: float(v) for k, v in sorted(seed_point.params.items())}
    if not seed_params:
        return [], "no numeric seed params"

    anchor_metric = _extract_metric_value(seed_point, metric_key)
    if anchor_metric is None:
        return [], f"missing anchor metric: {metric_key}"

    local_bounds = _refine_local_bounds_for_seed(
        seed=seed_params,
        global_bounds=global_bounds,
        radius_rel=float(radius_rel),
    )
    min_neighbors = max(8, int(n_neighbors) // 4)
    anchor_nonnumeric = _extract_nonnumeric_params(seed_point) if hold_fixed_nonnumeric else {}

    neighbor_rows: List[Tuple[float, str, int, Optional[float], Dict[str, float]]] = []
    for candidate in neighbor_pool:
        if candidate is seed_point:
            continue
        if str(candidate.source_jsonl) == str(seed_point.source_jsonl) and int(candidate.line) == int(seed_point.line):
            continue
        if not _point_status_ok(candidate):
            continue
        if hold_fixed_nonnumeric and anchor_nonnumeric:
            candidate_nonnumeric = _extract_nonnumeric_params(candidate)
            matched = True
            for key, expected in anchor_nonnumeric.items():
                if candidate_nonnumeric.get(key) != expected:
                    matched = False
                    break
            if not matched:
                continue

        missing_key = False
        dist_sq = 0.0
        for key, seed_value in seed_params.items():
            if key not in candidate.params:
                missing_key = True
                break
            bounds = global_bounds.get(key)
            if bounds is None:
                span = 1.0
            else:
                span = max(float(bounds[1] - bounds[0]), 1e-12)
            dx = (float(candidate.params[key]) - float(seed_value)) / span
            dist_sq += float(dx * dx)
        if missing_key:
            continue
        candidate_metric = _extract_metric_value(candidate, metric_key)
        if candidate_metric is None:
            continue
        neighbor_rows.append(
            (
                float(math.sqrt(dist_sq)),
                str(candidate.source_jsonl),
                int(candidate.line),
                float(candidate_metric),
                {k: float(v) for k, v in sorted(candidate.params.items()) if k in seed_params},
            )
        )

    neighbor_rows = sorted(
        neighbor_rows,
        key=lambda item: (float(item[0]), str(item[1]), int(item[2])),
    )[: int(n_neighbors)]
    if len(neighbor_rows) < int(min_neighbors):
        fallback_rows = _generate_local_rows(
            seed_params=seed_params,
            local_bounds=local_bounds,
            sampler=fallback_sampler,
            n_points=n_per_seed,
            seed=fallback_seed,
        )
        return fallback_rows, f"insufficient neighbors ({len(neighbor_rows)})"

    slopes: Dict[str, float] = {}
    for key in sorted(seed_params.keys()):
        numer = 0.0
        denom = 0.0
        for dist, _, _, metric_value, candidate_params in neighbor_rows:
            candidate_value = candidate_params.get(key)
            if candidate_value is None:
                continue
            delta_p = float(candidate_value) - float(seed_params[key])
            if abs(delta_p) <= 1e-15:
                continue
            delta_m = float(metric_value) - float(anchor_metric)
            weight = 1.0 / (1e-12 + float(dist))
            numer += weight * delta_p * delta_m
            denom += weight * delta_p * delta_p
        if denom <= 1e-18:
            slopes[key] = 0.0
        else:
            slopes[key] = float(numer / denom)

    ranked_params = sorted(
        [key for key, slope in slopes.items() if abs(float(slope)) > 1e-18],
        key=lambda key: (-abs(float(slopes[key])), str(key)),
    )[: int(top_params)]

    if not ranked_params:
        fallback_rows = _generate_local_rows(
            seed_params=seed_params,
            local_bounds=local_bounds,
            sampler=fallback_sampler,
            n_points=n_per_seed,
            seed=fallback_seed,
        )
        return fallback_rows, "zero local slopes"

    directions: List[int] = [1]
    if str(direction_mode) == "both":
        directions = [1, -1]

    sensitivity_rows: List[Dict[str, float]] = []
    seen: Set[Tuple[Tuple[str, float], ...]] = set()
    seed_sig = _params_signature(seed_params)

    def _push(candidate_params: Mapping[str, float]) -> None:
        params = {k: float(v) for k, v in sorted(candidate_params.items())}
        sig = _params_signature(params)
        if sig == seed_sig or sig in seen:
            return
        seen.add(sig)
        sensitivity_rows.append(params)

    for key in ranked_params:
        slope = float(slopes[key])
        downhill_sign = -1.0 if slope > 0.0 else 1.0
        bounds = global_bounds.get(key, local_bounds.get(key))
        if bounds is None:
            continue
        lo, hi = float(bounds[0]), float(bounds[1])
        span = float(max(hi - lo, 1e-12))
        step = float(step_frac) * span
        if key in integer_params:
            step = float(max(1.0, round(step)))
        if step <= 0.0:
            continue

        for direction in directions:
            effective_sign = downhill_sign * float(direction)
            raw_value = float(seed_params[key]) + effective_sign * step
            new_value = _clamp_value(raw_value, lo=lo, hi=hi)
            if key in integer_params:
                new_value = float(int(round(new_value)))
                new_value = _clamp_value(new_value, lo=lo, hi=hi)
            candidate = dict(seed_params)
            candidate[key] = float(new_value)
            _push(candidate)

    for direction in directions:
        combined = dict(seed_params)
        changed = False
        for key in ranked_params:
            slope = float(slopes[key])
            downhill_sign = -1.0 if slope > 0.0 else 1.0
            bounds = global_bounds.get(key, local_bounds.get(key))
            if bounds is None:
                continue
            lo, hi = float(bounds[0]), float(bounds[1])
            span = float(max(hi - lo, 1e-12))
            step = float(step_frac) * span
            if key in integer_params:
                step = float(max(1.0, round(step)))
            if step <= 0.0:
                continue
            effective_sign = downhill_sign * float(direction)
            raw_value = float(seed_params[key]) + effective_sign * step
            new_value = _clamp_value(raw_value, lo=lo, hi=hi)
            if key in integer_params:
                new_value = float(int(round(new_value)))
                new_value = _clamp_value(new_value, lo=lo, hi=hi)
            if not math.isclose(new_value, float(seed_params[key]), rel_tol=0.0, abs_tol=1e-15):
                changed = True
            combined[key] = float(new_value)
        if changed:
            _push(combined)

    if len(sensitivity_rows) < int(n_per_seed):
        fallback_rows = _generate_local_rows(
            seed_params=seed_params,
            local_bounds=local_bounds,
            sampler=fallback_sampler,
            n_points=n_per_seed,
            seed=fallback_seed + 4049,
        )
        for row in fallback_rows:
            _push(row)
            if len(sensitivity_rows) >= int(n_per_seed):
                break

    if not sensitivity_rows:
        return [], "no sensitivity rows generated"
    return sensitivity_rows[: int(n_per_seed)], None


def _refine_score_key(
    point: Point,
    *,
    score_mode: str,
    frontier_keys: Mapping[Tuple[str, int], bool],
    overlay_by_key: Optional[Mapping[Tuple[str, int], Mapping[str, Any]]] = None,
    rsd_weight: float = 1.0,
) -> Tuple[Any, ...]:
    key = (str(point.source_jsonl), int(point.line))
    chi2 = point.chi2_cmb if point.chi2_cmb is not None else float("inf")
    chi2_total = point.chi2_total if point.chi2_total is not None else float("inf")
    margin = point.drift_margin if point.drift_margin is not None else float("-inf")
    drift_rank = 0 if point.all_positive else 1
    mode = str(score_mode)
    if mode == "chi2_total":
        return (float(chi2_total), -float(margin), str(point.source_jsonl), int(point.line))
    if mode == "chi2_combined":
        overlay = (overlay_by_key or {}).get(key, {})
        chi2_rsd = _finite_float(overlay.get("chi2_rsd_min"))
        if chi2_rsd is None:
            return (1, float("inf"), float(chi2_total), -float(margin), str(point.source_jsonl), int(point.line))
        combined = float(chi2_total) + float(rsd_weight) * float(chi2_rsd)
        return (0, float(combined), float(chi2_total), -float(margin), str(point.source_jsonl), int(point.line))
    if score_mode == "pareto":
        pareto_rank = 0 if frontier_keys.get(key, False) else 1
        return (pareto_rank, drift_rank, float(chi2), -float(margin), str(point.source_jsonl), int(point.line))
    return (drift_rank, float(chi2), -float(margin), str(point.source_jsonl), int(point.line))


def _is_dominated(a: Point, b: Point) -> bool:
    if a.chi2_cmb is None or a.drift_margin is None or b.chi2_cmb is None or b.drift_margin is None:
        return False
    better_or_equal = (b.chi2_cmb <= a.chi2_cmb) and (b.drift_margin >= a.drift_margin)
    strictly_better = (b.chi2_cmb < a.chi2_cmb) or (b.drift_margin > a.drift_margin)
    return bool(better_or_equal and strictly_better)


def _pareto_frontier(points: Sequence[Point]) -> List[Point]:
    candidates = [
        p
        for p in points
        if p.invariants_ok and p.chi2_cmb is not None and p.drift_margin is not None
    ]
    candidates = sorted(candidates, key=_point_sort_key)
    frontier: List[Point] = []
    for point in candidates:
        dominated = False
        for other in candidates:
            if other is point:
                continue
            if _is_dominated(point, other):
                dominated = True
                break
        if not dominated:
            frontier.append(point)
    return sorted(frontier, key=_point_sort_key)


def _write_csv(
    path: Path,
    *,
    points: Sequence[Point],
    include_chi2_parts_json: bool,
    show_params: Optional[Sequence[str]] = None,
    include_rsd_overlay: bool = False,
    overlay_by_key: Optional[Mapping[Tuple[str, int], Mapping[str, Any]]] = None,
) -> None:
    discovered = sorted({k for p in points for k in p.params.keys()})
    if show_params:
        ordered: List[str] = []
        seen: set[str] = set()
        for key in show_params:
            k = str(key)
            if not k or k in seen:
                continue
            ordered.append(k)
            seen.add(k)
        for key in discovered:
            if key not in seen:
                ordered.append(key)
        param_keys = ordered
    else:
        param_keys = discovered
    fieldnames: List[str] = [
        "source_jsonl",
        "line",
        "model",
        "params_hash",
        "chi2_cmb",
        "chi2_total",
        "drift_margin",
        "all_positive",
        "invariants_ok",
        "micro_mode",
        "z_star_scale",
        "r_s_scale",
        "r_d_scale",
        "microphysics_plausible_ok",
        "microphysics_penalty",
        "microphysics_max_rel_dev",
        "recombination_method",
        "recomb_converged",
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
        "robust_n_runs",
        "robust_chi2_cmb_min",
        "robust_chi2_cmb_mean",
        "robust_chi2_cmb_max",
        "robust_chi2_total_min",
        "robust_chi2_total_mean",
        "robust_chi2_total_max",
        "robust_drift_metric_min",
        "robust_drift_metric_mean",
        "robust_drift_metric_max",
        "robust_drift_consistent",
        "robust_microphysics_plausible_ok",
    ]
    fieldnames.extend(param_keys)
    if bool(include_rsd_overlay):
        fieldnames.extend(
            [
                "chi2_rsd_min",
                "rsd_sigma8_0_best",
                "rsd_n",
                "chi2_combined",
                "rsd_overlay_status",
            ]
        )
    if include_chi2_parts_json:
        fieldnames.append("chi2_parts_json")

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for p in points:
            predicted = _as_mapping(p.raw.get("predicted"))
            row: Dict[str, Any] = {
                "source_jsonl": str(p.source_jsonl),
                "line": int(p.line),
                "model": str(p.model),
                "params_hash": str(p.params_hash),
                "chi2_cmb": p.chi2_cmb,
                "chi2_total": p.chi2_total,
                "drift_margin": p.drift_margin,
                "all_positive": bool(p.all_positive),
                "invariants_ok": bool(p.invariants_ok),
                "micro_mode": str(p.microphysics.get("mode", "none")),
                "z_star_scale": _finite_float(p.microphysics.get("z_star_scale")),
                "r_s_scale": _finite_float(p.microphysics.get("r_s_scale")),
                "r_d_scale": _finite_float(p.microphysics.get("r_d_scale")),
                "microphysics_plausible_ok": bool(p.microphysics_plausible_ok),
                "microphysics_penalty": float(p.microphysics_penalty),
                "microphysics_max_rel_dev": float(p.microphysics_max_rel_dev),
                "recombination_method": str(
                    p.raw.get("recombination_method", predicted.get("recombination_method", "fit"))
                ),
                "recomb_converged": bool(
                    p.raw.get("recomb_converged", predicted.get("recomb_converged", True))
                ),
                "drag_method": str(p.raw.get("drag_method", predicted.get("drag_method", "eh98"))),
                "cmb_num_method": str(
                    p.raw.get("cmb_num_method", predicted.get("cmb_num_method", ""))
                ),
                "cmb_num_n_eval_dm": int(
                    _finite_float(p.raw.get("cmb_num_n_eval_dm", predicted.get("cmb_num_n_eval_dm"))) or 0
                ),
                "cmb_num_err_dm": _finite_float(
                    p.raw.get("cmb_num_err_dm", predicted.get("cmb_num_err_dm"))
                ),
                "cmb_num_n_eval_rs": int(
                    _finite_float(p.raw.get("cmb_num_n_eval_rs", predicted.get("cmb_num_n_eval_rs"))) or 0
                ),
                "cmb_num_err_rs": _finite_float(
                    p.raw.get("cmb_num_err_rs", predicted.get("cmb_num_err_rs"))
                ),
                "cmb_num_n_eval_rs_drag": int(
                    _finite_float(
                        p.raw.get("cmb_num_n_eval_rs_drag", predicted.get("cmb_num_n_eval_rs_drag"))
                    )
                    or 0
                ),
                "cmb_num_err_rs_drag": _finite_float(
                    p.raw.get("cmb_num_err_rs_drag", predicted.get("cmb_num_err_rs_drag"))
                ),
                "cmb_num_rtol": _finite_float(
                    p.raw.get("cmb_num_rtol", predicted.get("cmb_num_rtol"))
                ),
                "cmb_num_atol": _finite_float(
                    p.raw.get("cmb_num_atol", predicted.get("cmb_num_atol"))
                ),
                "robust_n_runs": p.robust_n_runs,
                "robust_chi2_cmb_min": p.robust_chi2_cmb_min,
                "robust_chi2_cmb_mean": p.robust_chi2_cmb_mean,
                "robust_chi2_cmb_max": p.robust_chi2_cmb_max,
                "robust_chi2_total_min": p.robust_chi2_total_min,
                "robust_chi2_total_mean": p.robust_chi2_total_mean,
                "robust_chi2_total_max": p.robust_chi2_total_max,
                "robust_drift_metric_min": p.robust_drift_metric_min,
                "robust_drift_metric_mean": p.robust_drift_metric_mean,
                "robust_drift_metric_max": p.robust_drift_metric_max,
                "robust_drift_consistent": p.robust_drift_consistent,
                "robust_microphysics_plausible_ok": p.robust_microphysics_plausible_ok,
            }
            for key in param_keys:
                row[key] = p.params.get(key)
            if bool(include_rsd_overlay):
                overlay = (overlay_by_key or {}).get(_point_key(p), {})
                row["chi2_rsd_min"] = _finite_float(overlay.get("chi2_rsd_min"))
                row["rsd_sigma8_0_best"] = _finite_float(overlay.get("rsd_sigma8_0_best"))
                row["rsd_n"] = int(_finite_float(overlay.get("rsd_n")) or 0)
                row["chi2_combined"] = _finite_float(overlay.get("chi2_combined"))
                row["rsd_overlay_status"] = str(overlay.get("rsd_overlay_status", "unknown"))
            if include_chi2_parts_json:
                row["chi2_parts_json"] = json.dumps(_to_json_safe(p.chi2_parts), sort_keys=True)
            writer.writerow(row)


def _parse_show_params(raw: str) -> List[str]:
    out: List[str] = []
    for token in str(raw).split(","):
        key = token.strip()
        if not key:
            continue
        if key not in out:
            out.append(key)
    return out


def _flag_explicit(argv: Sequence[str], flag: str) -> bool:
    token = str(flag)
    for raw in argv:
        text = str(raw)
        if text == token or text.startswith(token + "="):
            return True
    return False


def _load_robustness_from_csv(path: Path) -> Dict[str, RobustAggregate]:
    out: Dict[str, RobustAggregate] = {}
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        chi2_cmb_by_run = [name for name in fieldnames if name.startswith("chi2_cmb__")]
        chi2_total_by_run = [name for name in fieldnames if name.startswith("chi2_total__")]
        drift_by_run = [name for name in fieldnames if name.startswith("drift_metric__")]
        for row in reader:
            params_hash = str((row.get("params_hash") or "")).strip()
            if not params_hash:
                continue
            n_runs = int(_finite_float(row.get("n_present")) or _finite_float(row.get("n_runs")) or 0)
            chi2_cmb_min = _finite_float(row.get("chi2_cmb_min"))
            chi2_cmb_max = _finite_float(row.get("chi2_cmb_max"))
            chi2_cmb_samples = [_finite_float(row.get(key)) for key in chi2_cmb_by_run]
            chi2_cmb_vals = [float(v) for v in chi2_cmb_samples if v is not None]
            chi2_cmb_mean = _finite_float(row.get("chi2_cmb_mean"))
            if chi2_cmb_mean is None:
                chi2_cmb_mean = _mean(chi2_cmb_vals)

            chi2_total_min = _finite_float(row.get("chi2_total_min"))
            chi2_total_max = _finite_float(row.get("chi2_total_max"))
            chi2_total_samples = [_finite_float(row.get(key)) for key in chi2_total_by_run]
            chi2_total_vals = [float(v) for v in chi2_total_samples if v is not None]
            chi2_total_mean = _finite_float(row.get("chi2_total_mean"))
            if chi2_total_mean is None:
                chi2_total_mean = _mean(chi2_total_vals)

            drift_metric_min = _finite_float(row.get("drift_metric_min"))
            drift_metric_max = _finite_float(row.get("drift_metric_max"))
            drift_samples = [_finite_float(row.get(key)) for key in drift_by_run]
            drift_vals = [float(v) for v in drift_samples if v is not None]
            drift_metric_mean = _finite_float(row.get("drift_metric_mean"))
            if drift_metric_mean is None:
                drift_metric_mean = _mean(drift_vals)

            drift_consistent = _parse_bool_like(
                row.get("drift_sign_consensus", row.get("drift_consistent"))
            )
            plausible_ok = _parse_bool_like(
                row.get("microphysics_plausible_all", row.get("microphysics_plausible_ok"))
            )

            out[params_hash] = RobustAggregate(
                params_hash=params_hash,
                n_runs=max(0, int(n_runs)),
                chi2_cmb_min=chi2_cmb_min,
                chi2_cmb_mean=chi2_cmb_mean,
                chi2_cmb_max=chi2_cmb_max,
                chi2_total_min=chi2_total_min,
                chi2_total_mean=chi2_total_mean,
                chi2_total_max=chi2_total_max,
                drift_metric_min=drift_metric_min,
                drift_metric_mean=drift_metric_mean,
                drift_metric_max=drift_metric_max,
                drift_consistent=drift_consistent,
                plausible_ok=plausible_ok,
                raw={str(k): _to_json_safe(v) for k, v in row.items()},
            )
    return out


def _load_robustness_from_jsonl(path: Path) -> Dict[str, RobustAggregate]:
    out: Dict[str, RobustAggregate] = {}
    with open_text_read(path) as fh:
        for line in fh:
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            try:
                payload = json.loads(text)
            except Exception:
                continue
            if not isinstance(payload, Mapping):
                continue
            row = {str(k): v for k, v in payload.items()}
            params_hash = str((row.get("params_hash") or "")).strip()
            if not params_hash:
                continue

            n_runs = int(_finite_float(row.get("n_present")) or _finite_float(row.get("n_runs")) or 0)
            chi2_cmb_min = _finite_float(row.get("chi2_cmb_min"))
            chi2_cmb_mean = _finite_float(row.get("chi2_cmb_mean"))
            chi2_cmb_max = _finite_float(row.get("chi2_cmb_max"))
            chi2_total_min = _finite_float(row.get("chi2_total_min"))
            chi2_total_mean = _finite_float(row.get("chi2_total_mean"))
            chi2_total_max = _finite_float(row.get("chi2_total_max"))
            drift_metric_min = _finite_float(row.get("drift_metric_min"))
            drift_metric_mean = _finite_float(row.get("drift_metric_mean"))
            drift_metric_max = _finite_float(row.get("drift_metric_max"))
            drift_consistent = _parse_bool_like(
                row.get("drift_sign_consensus", row.get("drift_consistent"))
            )
            plausible_ok = _parse_bool_like(
                row.get("microphysics_plausible_all", row.get("microphysics_plausible_ok"))
            )

            out[params_hash] = RobustAggregate(
                params_hash=params_hash,
                n_runs=max(0, int(n_runs)),
                chi2_cmb_min=chi2_cmb_min,
                chi2_cmb_mean=chi2_cmb_mean,
                chi2_cmb_max=chi2_cmb_max,
                chi2_total_min=chi2_total_min,
                chi2_total_mean=chi2_total_mean,
                chi2_total_max=chi2_total_max,
                drift_metric_min=drift_metric_min,
                drift_metric_mean=drift_metric_mean,
                drift_metric_max=drift_metric_max,
                drift_consistent=drift_consistent,
                plausible_ok=plausible_ok,
                raw={str(k): _to_json_safe(v) for k, v in row.items()},
            )
    return out


def _load_robustness_aggregate(path: Path) -> Dict[str, RobustAggregate]:
    rp = path.expanduser().resolve()
    if not rp.is_file():
        raise SystemExit(f"Robustness aggregate file not found: {rp}")

    suffix = rp.suffix.lower()
    if suffix == ".csv":
        return _load_robustness_from_csv(rp)
    lower_name = rp.name.lower()
    if suffix in {".jsonl", ".ndjson"} or lower_name.endswith(".jsonl.gz") or lower_name.endswith(".ndjson.gz"):
        return _load_robustness_from_jsonl(rp)

    with open_text_read(rp) as fh:
        for line in fh:
            text = line.strip()
            if not text:
                continue
            if text.startswith("{"):
                return _load_robustness_from_jsonl(rp)
            return _load_robustness_from_csv(rp)
    return {}


def _apply_robustness_objective(
    *,
    points: Sequence[Point],
    robustness: Mapping[str, RobustAggregate],
    objective: str,
    min_runs: int,
    require_drift_consistency: bool,
    require_plausible: bool,
) -> Tuple[List[Point], Dict[str, int]]:
    missing_params_hash = [p for p in points if not str(p.params_hash).strip()]
    if missing_params_hash:
        raise SystemExit(
            "Robustness mode requires params_hash in scan JSONL rows; "
            "missing params_hash detected."
        )

    representative: Dict[str, Point] = {}
    for point in points:
        params_hash = str(point.params_hash).strip()
        if params_hash not in representative:
            representative[params_hash] = point

    selected: List[Point] = []
    n_missing_aggregate = 0
    n_filtered_min_runs = 0
    n_filtered_drift = 0
    n_filtered_plausibility = 0

    for params_hash in sorted(representative.keys()):
        base = representative[params_hash]
        agg = robustness.get(params_hash)
        if agg is None:
            n_missing_aggregate += 1
            continue
        if int(agg.n_runs) < int(min_runs):
            n_filtered_min_runs += 1
            continue
        if require_drift_consistency and agg.drift_consistent is not True:
            n_filtered_drift += 1
            continue
        if require_plausible and agg.plausible_ok is not True:
            n_filtered_plausibility += 1
            continue

        if objective == "worst":
            mapped_chi2_cmb = agg.chi2_cmb_max if agg.chi2_cmb_max is not None else base.chi2_cmb
            mapped_chi2_total = agg.chi2_total_max if agg.chi2_total_max is not None else base.chi2_total
            mapped_drift = agg.drift_metric_min if agg.drift_metric_min is not None else base.drift_margin
        elif objective == "mean":
            mapped_chi2_cmb = agg.chi2_cmb_mean if agg.chi2_cmb_mean is not None else base.chi2_cmb
            mapped_chi2_total = agg.chi2_total_mean if agg.chi2_total_mean is not None else base.chi2_total
            mapped_drift = agg.drift_metric_mean if agg.drift_metric_mean is not None else base.drift_margin
        else:
            mapped_chi2_cmb = base.chi2_cmb
            mapped_chi2_total = base.chi2_total
            mapped_drift = base.drift_margin

        robust_all_positive = base.all_positive
        if mapped_drift is not None:
            robust_all_positive = bool(float(mapped_drift) > 0.0)

        selected.append(
            replace(
                base,
                chi2_cmb=mapped_chi2_cmb,
                chi2_total=mapped_chi2_total,
                drift_margin=mapped_drift,
                all_positive=robust_all_positive,
                robust_n_runs=int(agg.n_runs),
                robust_chi2_cmb_min=agg.chi2_cmb_min,
                robust_chi2_cmb_mean=agg.chi2_cmb_mean,
                robust_chi2_cmb_max=agg.chi2_cmb_max,
                robust_chi2_total_min=agg.chi2_total_min,
                robust_chi2_total_mean=agg.chi2_total_mean,
                robust_chi2_total_max=agg.chi2_total_max,
                robust_drift_metric_min=agg.drift_metric_min,
                robust_drift_metric_mean=agg.drift_metric_mean,
                robust_drift_metric_max=agg.drift_metric_max,
                robust_drift_consistent=agg.drift_consistent,
                robust_microphysics_plausible_ok=agg.plausible_ok,
            )
        )

    stats = {
        "n_repr_hashes": int(len(representative)),
        "n_missing_aggregate": int(n_missing_aggregate),
        "n_filtered_min_runs": int(n_filtered_min_runs),
        "n_filtered_drift_consistency": int(n_filtered_drift),
        "n_filtered_plausibility": int(n_filtered_plausibility),
        "n_selected": int(len(selected)),
    }
    return selected, stats


def _write_report_md(
    path: Path,
    *,
    summary: Mapping[str, Any],
    frontier: Sequence[Point],
    top_positive: Sequence[Point],
    rsd_overlay_summary: Optional[Mapping[str, Any]] = None,
) -> None:
    lines: List[str] = []
    lines.append("# Phase 2 E2 Pareto/Tradeoff Report")
    lines.append("")
    lines.append("Diagnostic-only summary under the tested families/ranges; this is not a full CMB likelihood.")
    lines.append("")
    lines.append("## Counts")
    lines.append(f"- Plausibility mode: `{str(summary.get('plausibility_mode', 'any'))}`")
    lines.append(f"- Total parsed points: `{int(summary.get('n_total', 0))}`")
    lines.append(f"- Raw parsed points: `{int(summary.get('n_total_raw', 0))}`")
    lines.append(f"- Plausible points (raw): `{int(summary.get('n_plausible_raw', 0))}`")
    lines.append(f"- Invariants OK: `{int(summary.get('n_with_invariants_ok', 0))}`")
    lines.append(f"- With finite CMB chi2: `{int(summary.get('n_with_cmb', 0))}`")
    lines.append(f"- With drift metrics: `{int(summary.get('n_with_drift_metrics', 0))}`")
    lines.append(f"- All-positive drift: `{int(summary.get('n_all_positive', 0))}`")
    lines.append(f"- CMB chi2 <= threshold: `{int(summary.get('n_cmb_below_threshold', 0))}`")
    lines.append(f"- Joint feasible (drift-positive & chi2<=threshold): `{int(summary.get('n_joint_positive_and_cmb_ok', 0))}`")
    robustness_summary = summary.get("robustness") if isinstance(summary.get("robustness"), Mapping) else None
    if isinstance(robustness_summary, Mapping):
        objective = str(robustness_summary.get("objective", "none"))
        lines.append(f"- Robustness objective: `{objective}`")
        if objective != "none":
            lines.append(f"- Robustness aggregate rows: `{int(robustness_summary.get('aggregate_rows', 0))}`")
            sel = robustness_summary.get("selection_stats")
            if isinstance(sel, Mapping):
                lines.append(f"- Robust selected rows: `{int(sel.get('n_selected', 0))}`")
                lines.append(f"- Missing aggregate rows: `{int(sel.get('n_missing_aggregate', 0))}`")
    lines.append("")
    lines.append("## Best Points")
    best_overall = summary.get("best_overall")
    best_positive = summary.get("best_positive")
    lines.append(f"- Best overall: `{json.dumps(best_overall, sort_keys=True) if best_overall else 'null'}`")
    lines.append(f"- Best all-positive: `{json.dumps(best_positive, sort_keys=True) if best_positive else 'null'}`")
    lines.append("")
    lines.append("## Frontier")
    lines.append(f"- Pareto frontier size: `{len(frontier)}`")
    lines.append(f"- Top-positive list size: `{len(top_positive)}`")
    lines.append("")
    if isinstance(rsd_overlay_summary, Mapping):
        lines.append("## RSD Overlay (optional)")
        lines.append(
            "- claim-safe note: linear-GR growth sanity overlay (not a full perturbation/LSS likelihood)."
        )
        lines.append(f"- enabled: `{bool(rsd_overlay_summary.get('enabled', False))}`")
        lines.append(f"- rsd_data_sha256: `{str(rsd_overlay_summary.get('rsd_data_sha256', ''))}`")
        lines.append(f"- rsd_weight: `{_to_json_safe(rsd_overlay_summary.get('rsd_weight'))}`")
        lines.append(f"- ap_correction: `{_to_json_safe(rsd_overlay_summary.get('rsd_ap_correction'))}`")
        lines.append(
            f"- best_by_chi2_total: `{json.dumps(_to_json_safe(rsd_overlay_summary.get('best_by_chi2_total')), sort_keys=True)}`"
        )
        lines.append(
            f"- best_by_chi2_combined: `{json.dumps(_to_json_safe(rsd_overlay_summary.get('best_by_chi2_combined')), sort_keys=True)}`"
        )
        lines.append("")
    lines.append("## Interpretation")
    lines.append("- Lower `chi2_cmb` and higher `drift_margin` are jointly preferred.")
    lines.append("- Frontier points are non-dominated in `(chi2_cmb, drift_margin)` space.")
    lines.append("- Conclusions are conditional on tested model families, scan ranges, and compressed-priors setup.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv_list = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(
        prog="phase2_e2_pareto_report",
        description="Summarize E2 scan JSONL outputs with Pareto/tradeoff diagnostics.",
    )
    ap.add_argument("--jsonl", action="append", default=[], type=Path, help="Input JSONL file (repeatable).")
    ap.add_argument("--jsonl-dir", action="append", default=[], type=Path, help="Directory containing JSONL files.")
    ap.add_argument("--top-k", type=int, default=10, help="Top-K all-positive points by chi2_cmb.")
    ap.add_argument(
        "--status-filter",
        choices=["ok_only", "any_eligible"],
        default="ok_only",
        help=(
            "Eligibility mode for Pareto/refine inputs. "
            "'ok_only' (default) uses status==ok (or legacy rows without status) and required metrics; "
            "'any_eligible' ignores status but still requires complete finite metrics."
        ),
    )
    ap.add_argument(
        "--rsd-overlay",
        choices=["off", "on"],
        default="off",
        help="Optional additive RSD fσ8 overlay for Pareto/refine candidate diagnostics.",
    )
    ap.add_argument(
        "--rsd-data",
        type=Path,
        default=DEFAULT_RSD_DATA_PATH,
        help="RSD CSV (z,fsigma8,sigma,omega_m_ref,ref_key). Used only when --rsd-overlay on.",
    )
    ap.add_argument(
        "--rsd-ap-correction",
        choices=["off", "on"],
        default="off",
        help="Optional AP-like correction mode for RSD overlay (diagnostic only).",
    )
    ap.add_argument(
        "--rsd-mode",
        choices=["nuisance_sigma8", "derived_As"],
        default="nuisance_sigma8",
        help="RSD overlay amplitude mode.",
    )
    ap.add_argument(
        "--rsd-weight",
        type=float,
        default=1.0,
        help="Weight for combined score: chi2_total + rsd_weight * chi2_rsd_min.",
    )
    ap.add_argument(
        "--plausibility",
        choices=["any", "plausible_only"],
        default="any",
        help=(
            "Filter by per-sample microphysics plausibility flag. "
            "For legacy JSONL without this field, rows are treated as plausible."
        ),
    )
    ap.add_argument(
        "--robustness-aggregate",
        type=Path,
        default=None,
        help="Path to robustness aggregate output (M30 CSV/JSONL).",
    )
    ap.add_argument(
        "--robustness-objective",
        choices=["none", "worst", "mean"],
        default="none",
        help="Use robustness aggregate metrics in Pareto objective (default: none).",
    )
    ap.add_argument(
        "--robustness-min-runs",
        type=int,
        default=1,
        help="Require at least this many runs in robustness aggregate for each selected params_hash.",
    )
    ap.add_argument(
        "--robustness-require-drift-consistency",
        choices=[0, 1],
        type=int,
        default=0,
        help="If 1, require drift consistency flag from robustness aggregate.",
    )
    ap.add_argument(
        "--robustness-require-plausible",
        choices=[0, 1],
        type=int,
        default=0,
        help="If 1, require robustness plausibility flag from robustness aggregate.",
    )
    ap.add_argument(
        "--chi2-cmb-threshold",
        type=float,
        default=9.0,
        help="Feasibility threshold for CMB chi2 in summary counters.",
    )
    ap.add_argument(
        "--json-summary",
        type=Path,
        default=None,
        help="Optional alias output path for machine-readable summary JSON.",
    )
    ap.add_argument(
        "--emit-refine-plan",
        type=Path,
        default=None,
        help="Write explicit refine plan JSON (phase2_e2_refine_plan_v1).",
    )
    ap.add_argument("--emit-refine-bounds", type=Path, default=None, help="Write narrowed bounds JSON for next-pass scans.")
    ap.add_argument("--emit-seed-points", type=Path, default=None, help="Write top-ranked seed points JSONL for next-pass scans.")
    ap.add_argument("--refine-top-k", type=int, default=25, help="Number of ranked points used to derive refine outputs.")
    ap.add_argument("--refine-n-per-seed", type=int, default=20, help="Number of local refine points generated per selected seed.")
    ap.add_argument("--refine-radius-rel", type=float, default=0.05, help="Relative local hyper-rectangle radius around each seed.")
    ap.add_argument("--refine-seed", type=int, default=0, help="Seed used for deterministic refine-plan point generation.")
    ap.add_argument(
        "--refine-strategy",
        choices=["grid", "sensitivity"],
        default="grid",
        help="Refine-point generation strategy (default: grid, backward-compatible).",
    )
    ap.add_argument(
        "--refine-target-metric",
        type=str,
        default="",
        help=(
            "Target metric for sensitivity-guided refine. "
            "Default auto-detect order: chi2_cmb -> chi2_total -> chi2."
        ),
    )
    ap.add_argument("--refine-neighbors", type=int, default=64, help="Nearest neighbors used for local sensitivity estimation.")
    ap.add_argument("--refine-top-params", type=int, default=3, help="Top parameters (by |local slope|) to perturb per anchor.")
    ap.add_argument("--refine-step-frac", type=float, default=0.05, help="Relative perturbation step as a fraction of parameter range.")
    ap.add_argument(
        "--refine-direction",
        choices=["downhill_only", "both"],
        default="both",
        help="Sensitivity perturbation direction mode.",
    )
    ap.add_argument(
        "--refine-anchor-filter",
        choices=["any", "plausible_only"],
        default="any",
        help="Anchor filter for sensitivity strategy (legacy rows without field are treated as plausible).",
    )
    ap.add_argument(
        "--refine-hold-fixed-nonnumeric",
        choices=[0, 1],
        type=int,
        default=1,
        help="If 1, sensitivity neighbors must match anchor non-numeric params exactly.",
    )
    ap.add_argument(
        "--refine-sampler",
        choices=["lhs", "halton", "random"],
        default="lhs",
        help="Sampler used for local refine-plan points.",
    )
    ap.add_argument(
        "--refine-plausibility",
        choices=["any", "plausible_only"],
        default="plausible_only",
        help="Seed selection filter for refine plan based on microphysics plausibility flag.",
    )
    ap.add_argument(
        "--refine-require-drift-sign",
        choices=["any", "positive_only", "negative_only"],
        default="any",
        help="Optional drift-sign filter for refine-plan seed selection.",
    )
    ap.add_argument(
        "--refine-score",
        choices=["drift_then_chi2", "pareto", "chi2_total", "chi2_combined"],
        default="drift_then_chi2",
        help=(
            "Ranking mode for refine-top-k selection. "
            "'chi2_total'/'chi2_combined' are additive options; "
            "legacy default remains drift_then_chi2 for backward compatibility."
        ),
    )
    ap.add_argument(
        "--rank-by",
        choices=["cmb", "rsd", "joint"],
        default="cmb",
        help=(
            "Optional ranking metric for refine-plan seed ordering. "
            "Used only when this flag (or --rsd-chi2-field) is passed explicitly."
        ),
    )
    ap.add_argument(
        "--rsd-chi2-field",
        type=str,
        default="",
        help=(
            "Optional RSD chi2 field for --rank-by rsd/joint. "
            "If omitted, auto-detect order is rsd_chi2_total -> rsd_chi2 -> rsd_chi2_min."
        ),
    )
    ap.add_argument(
        "--refine-margin-frac",
        type=float,
        default=0.10,
        help="Expand selected min/max bounds by this fractional margin.",
    )
    ap.add_argument(
        "--show-params",
        type=str,
        default="",
        help="Comma-separated parameter keys to force-show in CSV outputs (missing values rendered as NA/empty).",
    )
    ap.add_argument(
        "--out-dir",
        "--outdir",
        dest="outdir",
        type=Path,
        default=None,
        help="Output root (CLI > GSC_OUTDIR > v11.0.0/artifacts/release).",
    )
    ap.add_argument("--out-summary", type=Path, default=Path("pareto_summary.json"))
    ap.add_argument("--out-frontier", type=Path, default=Path("pareto_frontier.csv"))
    ap.add_argument("--out-top-positive", type=Path, default=Path("pareto_top_positive.csv"))
    ap.add_argument("--out-report-md", type=Path, default=Path("pareto_report.md"))
    args = ap.parse_args(argv_list)
    rank_by_explicit = _flag_explicit(argv_list, "--rank-by")
    rsd_chi2_field_explicit = _flag_explicit(argv_list, "--rsd-chi2-field")
    rank_mode_explicit = bool(rank_by_explicit or rsd_chi2_field_explicit)

    if int(args.top_k) <= 0:
        raise SystemExit("--top-k must be > 0")
    if int(args.refine_top_k) <= 0:
        raise SystemExit("--refine-top-k must be > 0")
    if int(args.refine_n_per_seed) <= 0:
        raise SystemExit("--refine-n-per-seed must be > 0")
    if not (math.isfinite(float(args.refine_radius_rel)) and float(args.refine_radius_rel) > 0.0):
        raise SystemExit("--refine-radius-rel must be finite and > 0")
    if not math.isfinite(float(args.chi2_cmb_threshold)):
        raise SystemExit("--chi2-cmb-threshold must be finite")
    if not (math.isfinite(float(args.refine_margin_frac)) and float(args.refine_margin_frac) >= 0.0):
        raise SystemExit("--refine-margin-frac must be finite and >= 0")
    if int(args.refine_neighbors) <= 0:
        raise SystemExit("--refine-neighbors must be > 0")
    if int(args.refine_top_params) <= 0:
        raise SystemExit("--refine-top-params must be > 0")
    if not (math.isfinite(float(args.refine_step_frac)) and float(args.refine_step_frac) > 0.0):
        raise SystemExit("--refine-step-frac must be finite and > 0")
    if int(args.robustness_min_runs) <= 0:
        raise SystemExit("--robustness-min-runs must be > 0")
    if not (math.isfinite(float(args.rsd_weight)) and float(args.rsd_weight) >= 0.0):
        raise SystemExit("--rsd-weight must be finite and >= 0")
    if str(args.refine_score) == "chi2_combined" and str(args.rsd_overlay) != "on":
        raise SystemExit("--refine-score chi2_combined requires --rsd-overlay on")
    show_params = _parse_show_params(args.show_params)

    jsonl_paths = _iter_jsonl_paths(files=args.jsonl, dirs=args.jsonl_dir)
    if not jsonl_paths:
        raise SystemExit("No inputs provided; pass --jsonl and/or --jsonl-dir")

    points, parse_stats = _load_points(jsonl_paths)
    if not points:
        raise SystemExit("No valid JSONL point records found")
    all_points = list(points)
    raw_total_parsed = int(len(all_points))
    status_counts: Dict[str, int] = {}
    n_incomplete_metrics = 0
    n_invariants_filtered = 0
    n_legacy_status = 0
    for point in all_points:
        label = _point_status_label(point)
        status_counts[label] = int(status_counts.get(label, 0) + 1)
        if label == "ok_legacy":
            n_legacy_status += 1
        if not _point_has_required_metrics(point):
            n_incomplete_metrics += 1
        elif not bool(point.invariants_ok):
            n_invariants_filtered += 1
    n_skipped_drift = int(
        sum(count for label, count in status_counts.items() if str(label).startswith("skipped_drift"))
    )
    n_error_status = int(status_counts.get("error", 0))

    points = list(all_points)

    robustness_map: Dict[str, RobustAggregate] = {}
    robustness_stats: Dict[str, int] = {}
    robustness_aggregate_sha256: Optional[str] = None
    robustness_aggregate_path: Optional[str] = None
    if str(args.robustness_objective) != "none" and args.robustness_aggregate is None:
        raise SystemExit("--robustness-aggregate is required when --robustness-objective is not none")
    if args.robustness_aggregate is not None:
        resolved_aggregate = args.robustness_aggregate.expanduser().resolve()
        robustness_aggregate_path = str(resolved_aggregate)
        robustness_aggregate_sha256 = _sha256_file(resolved_aggregate)
        robustness_map = _load_robustness_aggregate(resolved_aggregate)
        if str(args.robustness_objective) != "none":
            points, robustness_stats = _apply_robustness_objective(
                points=points,
                robustness=robustness_map,
                objective=str(args.robustness_objective),
                min_runs=int(args.robustness_min_runs),
                require_drift_consistency=bool(int(args.robustness_require_drift_consistency)),
                require_plausible=bool(int(args.robustness_require_plausible)),
            )
            if not points:
                raise SystemExit(
                    "No points left after robustness filters/objective; "
                    "check robustness aggregate and thresholds."
                )

    raw_total = int(len(points))
    raw_plausible = int(sum(1 for p in points if p.microphysics_plausible_ok))
    if str(args.plausibility) == "plausible_only":
        points = [p for p in points if p.microphysics_plausible_ok]
        if not points:
            raise SystemExit("No points left after --plausibility plausible_only filtering")
    analysis_points = list(points)
    pareto_points = [
        point
        for point in analysis_points
        if _point_is_eligible_for_pareto(point, status_filter=str(args.status_filter))
    ]

    out_root = resolve_outdir(args.outdir, v101_dir=V101_DIR)
    out_root.mkdir(parents=True, exist_ok=True)
    summary_target = args.json_summary if args.json_summary is not None else args.out_summary
    out_summary = resolve_path_under_outdir(summary_target, out_root=out_root)
    out_frontier = resolve_path_under_outdir(args.out_frontier, out_root=out_root)
    out_top_positive = resolve_path_under_outdir(args.out_top_positive, out_root=out_root)
    out_report_md = resolve_path_under_outdir(args.out_report_md, out_root=out_root)
    out_refine_bounds = (
        resolve_path_under_outdir(args.emit_refine_bounds, out_root=out_root)
        if args.emit_refine_bounds is not None
        else None
    )
    out_refine_plan = (
        resolve_path_under_outdir(args.emit_refine_plan, out_root=out_root)
        if args.emit_refine_plan is not None
        else None
    )
    out_seed_points = (
        resolve_path_under_outdir(args.emit_seed_points, out_root=out_root)
        if args.emit_seed_points is not None
        else None
    )
    if out_summary is None or out_frontier is None or out_top_positive is None or out_report_md is None:
        raise SystemExit("Failed to resolve output paths")

    with_invariants_ok = [p for p in analysis_points if p.invariants_ok]
    with_cmb = [p for p in analysis_points if p.chi2_cmb is not None]
    with_drift_metrics = [p for p in analysis_points if p.drift_margin is not None]
    all_positive = [p for p in analysis_points if p.all_positive]
    with_cmb_ok = [
        p
        for p in with_invariants_ok
        if p.chi2_cmb is not None and float(p.chi2_cmb) <= float(args.chi2_cmb_threshold)
    ]
    with_joint_ok = [p for p in with_cmb_ok if p.all_positive]

    best_overall_candidates = [
        p
        for p in with_invariants_ok
        if p.chi2_cmb is not None and _point_status_allowed(p, status_filter=str(args.status_filter))
    ]
    best_positive_candidates = [p for p in best_overall_candidates if p.all_positive]
    best_overall = min(best_overall_candidates, key=_point_sort_key) if best_overall_candidates else None
    best_positive = min(best_positive_candidates, key=_point_sort_key) if best_positive_candidates else None

    frontier = _pareto_frontier(pareto_points)
    top_positive = sorted(best_positive_candidates, key=_point_sort_key)[: int(args.top_k)]

    rsd_overlay_enabled = str(args.rsd_overlay) == "on"
    rsd_ap_correction = str(args.rsd_ap_correction) == "on"
    rsd_overlay_by_key: Dict[Tuple[str, int], Dict[str, Any]] = {}
    rsd_data_sha256: Optional[str] = None
    rsd_data_path_resolved: Optional[str] = None
    rank_by_mode = str(args.rank_by)
    rank_requires_rsd = bool(rank_mode_explicit and rank_by_mode in {"rsd", "joint"})
    rsd_chi2_field_requested = str(args.rsd_chi2_field).strip()
    rsd_chi2_field_used: Optional[str] = None
    best_rank_metric: Optional[float] = None
    best_rank_metric_components: Optional[Dict[str, Optional[float]]] = None

    overlay_candidates: Dict[Tuple[str, int], Point] = {}
    for point in frontier:
        overlay_candidates[_point_key(point)] = point
    for point in top_positive:
        overlay_candidates[_point_key(point)] = point

    frontier_keys = {(str(p.source_jsonl), int(p.line)): True for p in frontier}
    refine_rank_pool = [p for p in pareto_points if _point_status_ok(p) and p.chi2_cmb is not None]
    if rsd_overlay_enabled and str(args.refine_score) == "chi2_combined":
        for point in refine_rank_pool:
            overlay_candidates[_point_key(point)] = point
    if rsd_overlay_enabled and rank_requires_rsd:
        for point in pareto_points:
            overlay_candidates[_point_key(point)] = point

    if rsd_overlay_enabled:
        rsd_path = Path(args.rsd_data).expanduser().resolve()
        rsd_data_path_resolved = str(rsd_path)
        rsd_data_exists = rsd_path.is_file()
        if rsd_data_exists:
            rsd_data_sha256 = _sha256_file(rsd_path)
        warned_missing_data = False
        for point in sorted(overlay_candidates.values(), key=_point_sort_key):
            precomputed = _precomputed_rsd_overlay(
                point=point,
                rsd_weight=float(args.rsd_weight),
                data_sha256=rsd_data_sha256,
            )
            if precomputed is not None:
                rsd_overlay_by_key[_point_key(point)] = precomputed
                continue
            if rsd_data_exists:
                overlay = rsd_overlay_for_e2_record(
                    point.raw,
                    rsd_csv_path=str(rsd_path),
                    ap_correction=bool(rsd_ap_correction),
                    status_filter=str(args.status_filter),
                    rsd_mode=str(args.rsd_mode),
                )
                chi2_rsd = _finite_float(overlay.get("chi2_rsd_min"))
                chi2_total = _finite_float(point.chi2_total)
                if chi2_rsd is not None and chi2_total is not None:
                    overlay["chi2_combined"] = float(chi2_total + float(args.rsd_weight) * float(chi2_rsd))
                else:
                    overlay["chi2_combined"] = None
                if overlay.get("rsd_data_sha256") is None:
                    overlay["rsd_data_sha256"] = rsd_data_sha256
                rsd_overlay_by_key[_point_key(point)] = dict(overlay)
            else:
                if not warned_missing_data:
                    print(
                        f"[warn] --rsd-overlay on but --rsd-data not found: {rsd_path}; "
                        "overlay marked as skipped_missing_data where precomputed rsd_* fields are absent",
                        file=sys.stderr,
                    )
                    warned_missing_data = True
                rsd_overlay_by_key[_point_key(point)] = _missing_data_overlay(
                    ap_correction=bool(rsd_ap_correction),
                    data_sha256=None,
                )

    allow_joint_precomputed = bool(
        rank_mode_explicit
        and rank_by_mode == "joint"
        and not rsd_chi2_field_requested
        and any(_finite_float(point.raw.get("chi2_joint_total")) is not None for point in pareto_points)
    )

    if rank_mode_explicit and rank_requires_rsd and not allow_joint_precomputed:
        rsd_chi2_field_used = _resolve_rsd_chi2_field(
            points=pareto_points,
            requested_field=rsd_chi2_field_requested,
            overlay_by_key=rsd_overlay_by_key if rsd_overlay_enabled else None,
        )
        if rsd_chi2_field_used is None:
            requested_hint = rsd_chi2_field_requested or "<auto>"
            print(
                "MISSING_RSD_CHI2_FIELD: no finite RSD chi2 values found in eligible rows; "
                f"requested={requested_hint}. Hint: run scan with --rsd-overlay or pass --rsd-chi2-field.",
                file=sys.stderr,
            )
            return 2

    if rank_mode_explicit:
        ranked_candidates, rank_components_all = _rank_points_by_mode(
            pareto_points,
            rank_by=rank_by_mode,
            rsd_chi2_field=rsd_chi2_field_used,
            overlay_by_key=rsd_overlay_by_key if rsd_overlay_enabled else None,
        )
        refine_selected = ranked_candidates[: int(args.refine_top_k)]
    else:
        ranked_candidates = sorted(
            refine_rank_pool,
            key=lambda p: _refine_score_key(
                p,
                score_mode=str(args.refine_score),
                frontier_keys=frontier_keys,
                overlay_by_key=rsd_overlay_by_key if rsd_overlay_enabled else None,
                rsd_weight=float(args.rsd_weight),
            ),
        )
        rank_components_all = {}
        refine_selected = ranked_candidates[: int(args.refine_top_k)]

    if rank_mode_explicit and ranked_candidates:
        best_comps = rank_components_all.get(_point_key(ranked_candidates[0]), {})
        best_rank_metric = _finite_float(best_comps.get("rank_metric"))
        best_rank_metric_components = {
            "chi2_total": _finite_float(best_comps.get("chi2_total")),
            "rsd_chi2": _finite_float(best_comps.get("rsd_chi2")),
        }

    refine_seed_candidates = [p for p in (pareto_points if rank_mode_explicit else refine_rank_pool)]
    refine_strategy = str(args.refine_strategy)
    if refine_strategy == "sensitivity":
        if str(args.refine_anchor_filter) == "plausible_only":
            refine_seed_candidates = [p for p in refine_seed_candidates if p.microphysics_plausible_ok]
    elif str(args.refine_plausibility) == "plausible_only":
        refine_seed_candidates = [p for p in refine_seed_candidates if p.microphysics_plausible_ok]
    if str(args.refine_require_drift_sign) == "positive_only":
        refine_seed_candidates = [p for p in refine_seed_candidates if p.all_positive]
    elif str(args.refine_require_drift_sign) == "negative_only":
        refine_seed_candidates = [p for p in refine_seed_candidates if not p.all_positive]

    refine_seed_frontier = _pareto_frontier(refine_seed_candidates)
    refine_seed_frontier_keys = {(str(p.source_jsonl), int(p.line)): True for p in refine_seed_frontier}
    if rank_mode_explicit:
        refine_seed_ranked, _ = _rank_points_by_mode(
            refine_seed_candidates,
            rank_by=rank_by_mode,
            rsd_chi2_field=rsd_chi2_field_used,
            overlay_by_key=rsd_overlay_by_key if rsd_overlay_enabled else None,
        )
    else:
        if str(args.refine_score) in {"chi2_total", "chi2_combined"}:
            refine_seed_ranked = sorted(
                refine_seed_candidates,
                key=lambda p: _refine_score_key(
                    p,
                    score_mode=str(args.refine_score),
                    frontier_keys=refine_seed_frontier_keys,
                    overlay_by_key=rsd_overlay_by_key if rsd_overlay_enabled else None,
                    rsd_weight=float(args.rsd_weight),
                ),
            )
        else:
            refine_seed_ranked = sorted(
                refine_seed_candidates,
                key=lambda p: (
                    0 if refine_seed_frontier_keys.get((str(p.source_jsonl), int(p.line)), False) else 1,
                    float(p.chi2_total) if p.chi2_total is not None else float("inf"),
                    float(p.chi2_cmb) if p.chi2_cmb is not None else float("inf"),
                    -(float(p.drift_margin) if p.drift_margin is not None else float("-inf")),
                    str(p.source_jsonl),
                    int(p.line),
                ),
            )
    refine_plan_seeds = refine_seed_ranked[: int(args.refine_top_k)]
    refine_target_metric = ""
    if refine_strategy == "sensitivity":
        if not pareto_points:
            raise SystemExit(
                "No eligible Pareto points for sensitivity refine plan; "
                "check --status-filter and input completeness."
            )
        refine_target_metric = _resolve_refine_target_metric(pareto_points, str(args.refine_target_metric))

    refine_bounds: Dict[str, Dict[str, float]] = {}
    margin_frac = float(args.refine_margin_frac)
    for key in sorted({k for p in refine_selected for k in p.params.keys()}):
        values = [float(p.params[key]) for p in refine_selected if key in p.params]
        if not values:
            continue
        lo = min(values)
        hi = max(values)
        span = float(hi - lo)
        if span > 0.0:
            expand = margin_frac * span
        else:
            mid = 0.5 * (float(lo) + float(hi))
            expand = margin_frac * max(abs(mid), 1.0)
        out_lo = float(lo - expand)
        out_hi = float(hi + expand)
        if out_hi <= out_lo:
            out_hi = float(out_lo + 1e-12)
        refine_bounds[str(key)] = {"min": float(out_lo), "max": float(out_hi)}

    seed_points_payload: List[Dict[str, Any]] = []
    seen_seed: set[Tuple[Tuple[str, float], ...]] = set()
    for point in refine_selected:
        sig = _params_signature(point.params)
        if sig in seen_seed:
            continue
        seen_seed.add(sig)
        seed_points_payload.append(
            {
                "sample_id": f"{Path(point.source_jsonl).name}:{int(point.line)}",
                "source_jsonl": str(point.source_jsonl),
                "line": int(point.line),
                "model": str(point.model),
                "params": {k: float(v) for k, v in sorted(point.params.items())},
                "chi2_cmb": point.chi2_cmb,
                "chi2_total": point.chi2_total,
                "drift": {
                    "all_positive": bool(point.all_positive),
                    "drift_margin": point.drift_margin,
                },
                "microphysics": _to_json_safe(point.microphysics),
                "chi2_parts": _to_json_safe(point.chi2_parts),
            }
        )

    refine_plan_payload: Optional[Dict[str, Any]] = None
    if out_refine_plan is not None:
        if len(jsonl_paths) != 1:
            raise SystemExit("--emit-refine-plan currently requires exactly one --jsonl input")
        source_jsonl = jsonl_paths[0]
        source_sha256 = _sha256_file(source_jsonl)
        global_bounds, bounds_source = _extract_global_bounds_from_points(pareto_points)
        selection_note = None
        if bounds_source == "inferred_from_points":
            selection_note = "global_bounds inferred from observed JSONL params"

        plan_points: List[Dict[str, Any]] = []
        sensitivity_notes: List[str] = []
        neighbor_pool = [point for point in pareto_points if _point_status_ok(point)]
        integer_param_keys = _infer_integer_param_keys(neighbor_pool)
        for seed_rank, seed_point in enumerate(refine_plan_seeds):
            seed_params = {k: float(v) for k, v in sorted(seed_point.params.items())}
            if not seed_params:
                continue
            seed_sampler_seed = int(args.refine_seed) + 1009 * int(seed_rank)
            if refine_strategy == "sensitivity":
                local_rows, sensitivity_reason = _build_sensitivity_rows_for_seed(
                    seed_point=seed_point,
                    neighbor_pool=neighbor_pool,
                    global_bounds=global_bounds,
                    metric_key=str(refine_target_metric),
                    n_neighbors=int(args.refine_neighbors),
                    n_per_seed=int(args.refine_n_per_seed),
                    top_params=int(args.refine_top_params),
                    step_frac=float(args.refine_step_frac),
                    direction_mode=str(args.refine_direction),
                    hold_fixed_nonnumeric=bool(int(args.refine_hold_fixed_nonnumeric)),
                    integer_params=integer_param_keys,
                    fallback_sampler=str(args.refine_sampler),
                    fallback_seed=seed_sampler_seed,
                    radius_rel=float(args.refine_radius_rel),
                )
                if sensitivity_reason:
                    sensitivity_notes.append(
                        f"seed_rank={int(seed_rank)} source={Path(seed_point.source_jsonl).name}:{int(seed_point.line)} "
                        f"reason={sensitivity_reason}"
                    )
            else:
                local_bounds = _refine_local_bounds_for_seed(
                    seed=seed_params,
                    global_bounds=global_bounds,
                    radius_rel=float(args.refine_radius_rel),
                )
                local_rows = _generate_local_rows(
                    seed_params=seed_params,
                    local_bounds=local_bounds,
                    sampler=str(args.refine_sampler),
                    n_points=int(args.refine_n_per_seed),
                    seed=seed_sampler_seed,
                )

            for local_idx, params in enumerate(local_rows):
                plan_points.append(
                    {
                        "point_id": f"refine_s{int(seed_rank):02d}_p{int(local_idx):03d}",
                        "seed_rank": int(seed_rank),
                        "seed_params_hash": _params_hash(seed_params),
                        "params": params,
                    }
                )

        if not plan_points:
            raise SystemExit("No refine plan points generated")

        refine_plan_payload = {
            "plan_version": "phase2_e2_refine_plan_v1",
            "source": {
                "jsonl_path": str(source_jsonl),
                "jsonl_sha256": str(source_sha256),
            },
            "selection": {
                "top_k": int(args.refine_top_k),
                "plausibility": (
                    str(args.refine_anchor_filter)
                    if refine_strategy == "sensitivity"
                else str(args.refine_plausibility)
                ),
                "require_drift_sign": str(args.refine_require_drift_sign),
                "ranking": (
                    str(args.refine_score)
                    if str(args.refine_score) in {"chi2_total", "chi2_combined"}
                    else "pareto_then_chi2_total"
                ),
                "refine_score": str(args.refine_score),
                "note": selection_note,
                "robustness_objective": (
                    None if str(args.robustness_objective) == "none" else str(args.robustness_objective)
                ),
                "robustness_min_runs": int(args.robustness_min_runs),
                "robustness_aggregate_basename": (
                    None
                    if args.robustness_aggregate is None
                    else str(args.robustness_aggregate.expanduser().resolve().name)
                ),
                "robustness_aggregate_sha256": robustness_aggregate_sha256,
                "rsd_overlay_enabled": bool(rsd_overlay_enabled),
                "rsd_weight": float(args.rsd_weight),
                "rsd_ap_correction": bool(rsd_ap_correction),
                "rsd_mode": str(args.rsd_mode),
                "rsd_data_sha256": rsd_data_sha256,
            },
            "refine": {
                "n_per_seed": int(args.refine_n_per_seed),
                "radius_rel": float(args.refine_radius_rel),
                "sampler": str(args.refine_sampler),
                "seed": int(args.refine_seed),
            },
            "global_bounds": {
                k: [float(v[0]), float(v[1])]
                for k, v in sorted(global_bounds.items())
            },
            "points": plan_points,
        }
        if rank_mode_explicit:
            selection_block = refine_plan_payload.get("selection")
            if isinstance(selection_block, dict):
                selection_block["rank_by"] = str(rank_by_mode)
                selection_block["rsd_chi2_field_used"] = (
                    str(rsd_chi2_field_used) if rsd_chi2_field_used is not None else None
                )
        if refine_strategy == "sensitivity":
            selection_block = refine_plan_payload.get("selection")
            if isinstance(selection_block, dict):
                selection_block["anchor_filter"] = str(args.refine_anchor_filter)
                selection_block["hold_fixed_nonnumeric"] = bool(int(args.refine_hold_fixed_nonnumeric))
                selection_block["sensitivity_notes"] = sorted(
                    set(str(note) for note in sensitivity_notes if str(note).strip())
                )
            refine_block = refine_plan_payload.get("refine")
            if isinstance(refine_block, dict):
                refine_block["strategy"] = "sensitivity"
                refine_block["target_metric"] = str(refine_target_metric)
                refine_block["neighbors"] = int(args.refine_neighbors)
                refine_block["top_params"] = int(args.refine_top_params)
                refine_block["step_frac"] = float(args.refine_step_frac)
                refine_block["direction"] = str(args.refine_direction)
        else:
            refine_block = refine_plan_payload.get("refine")
            if isinstance(refine_block, dict):
                refine_block["strategy"] = "grid"
        if refine_strategy != "sensitivity":
            refine_plan_payload["generated_utc"] = _now_utc()

    rsd_overlay_summary: Optional[Dict[str, Any]] = None
    if rsd_overlay_enabled:
        n_ok = 0
        n_skipped = 0
        n_error = 0
        best_total_overlay: Optional[Dict[str, Any]] = None
        best_combined_overlay: Optional[Dict[str, Any]] = None
        for point in sorted(overlay_candidates.values(), key=_point_sort_key):
            overlay = rsd_overlay_by_key.get(_point_key(point), {})
            status = str(overlay.get("rsd_overlay_status", "unknown"))
            if status == "ok":
                n_ok += 1
            elif status.startswith("skipped"):
                n_skipped += 1
            elif status == "error":
                n_error += 1

            chi2_total = _finite_float(point.chi2_total)
            chi2_rsd = _finite_float(overlay.get("chi2_rsd_min"))
            combined = _finite_float(overlay.get("chi2_combined"))
            row_payload = {
                "params_hash": str(point.params_hash),
                "source_jsonl": str(point.source_jsonl),
                "line": int(point.line),
                "chi2_total": chi2_total,
                "chi2_rsd_min": chi2_rsd,
                "chi2_combined": combined,
                "rsd_sigma8_0_best": _finite_float(overlay.get("rsd_sigma8_0_best")),
                "rsd_overlay_status": status,
                "rsd_n": int(_finite_float(overlay.get("rsd_n")) or 0),
            }
            if chi2_total is not None:
                if best_total_overlay is None:
                    best_total_overlay = row_payload
                else:
                    cur = (
                        float(best_total_overlay.get("chi2_total") or float("inf")),
                        str(best_total_overlay.get("params_hash", "")),
                    )
                    nxt = (float(chi2_total), str(point.params_hash))
                    if nxt < cur:
                        best_total_overlay = row_payload
            if combined is not None:
                if best_combined_overlay is None:
                    best_combined_overlay = row_payload
                else:
                    cur = (
                        float(best_combined_overlay.get("chi2_combined") or float("inf")),
                        str(best_combined_overlay.get("params_hash", "")),
                    )
                    nxt = (float(combined), str(point.params_hash))
                    if nxt < cur:
                        best_combined_overlay = row_payload

        rsd_overlay_summary = {
            "enabled": True,
            "rsd_data_path": rsd_data_path_resolved,
            "rsd_data_sha256": rsd_data_sha256,
            "rsd_ap_correction": bool(rsd_ap_correction),
            "rsd_mode": str(args.rsd_mode),
            "rsd_weight": float(args.rsd_weight),
            "n_overlay_candidates": int(len(overlay_candidates)),
            "n_overlay_ok": int(n_ok),
            "n_overlay_skipped": int(n_skipped),
            "n_overlay_error": int(n_error),
            "best_by_chi2_total": _to_json_safe(best_total_overlay),
            "best_by_chi2_combined": _to_json_safe(best_combined_overlay),
            "claim_safe_note": (
                "RSD fσ8 overlay is a preliminary linear-GR sanity check; "
                "not a full perturbation/LSS likelihood."
            ),
        }

    summary: Dict[str, Any] = {
        "status_filter": str(args.status_filter),
        "plausibility_mode": str(args.plausibility),
        "n_total": int(len(analysis_points)),
        "n_total_raw": int(raw_total),
        "n_total_parsed": int(raw_total_parsed),
        "n_total_read": int(len(all_points)),
        "n_eligible_for_pareto": int(len(pareto_points)),
        "n_plausible_raw": int(raw_plausible),
        "n_with_invariants_ok": int(len(with_invariants_ok)),
        "n_with_cmb": int(len(with_cmb)),
        "n_with_drift_metrics": int(len(with_drift_metrics)),
        "n_all_positive": int(len(all_positive)),
        "n_cmb_below_threshold": int(len(with_cmb_ok)),
        "n_joint_positive_and_cmb_ok": int(len(with_joint_ok)),
        "chi2_cmb_threshold": float(args.chi2_cmb_threshold),
        "n_invalid_json": int(parse_stats["n_invalid_json"]),
        "n_invalid_shape": int(parse_stats["n_invalid_shape"]),
        "status_counts_read": {k: int(status_counts[k]) for k in sorted(status_counts.keys())},
        "n_status_legacy_missing": int(n_legacy_status),
        "n_skipped_drift": int(n_skipped_drift),
        "n_error_status": int(n_error_status),
        "n_incomplete_missing_metrics": int(n_incomplete_metrics),
        "n_filtered_invariants": int(n_invariants_filtered),
        "robustness": {
            "objective": str(args.robustness_objective),
            "aggregate_path": robustness_aggregate_path,
            "aggregate_sha256": robustness_aggregate_sha256,
            "min_runs": int(args.robustness_min_runs),
            "require_drift_consistency": bool(int(args.robustness_require_drift_consistency)),
            "require_plausible": bool(int(args.robustness_require_plausible)),
            "aggregate_rows": int(len(robustness_map)),
            "selection_stats": dict(robustness_stats),
        },
        "best_overall": _point_to_dict(best_overall) if best_overall is not None else None,
        "best_positive": _point_to_dict(best_positive) if best_positive is not None else None,
        "frontier_size": int(len(frontier)),
        "top_positive_size": int(len(top_positive)),
        "refine_selected_size": int(len(refine_selected)),
        "refine_plan_seed_size": int(len(refine_plan_seeds)),
        "refine_plan_point_size": int(len((refine_plan_payload or {}).get("points") or [])),
        "config": {
            "jsonl_inputs": [str(p) for p in jsonl_paths],
            "top_k": int(args.top_k),
            "refine_top_k": int(args.refine_top_k),
            "refine_score": str(args.refine_score),
            "refine_margin_frac": float(args.refine_margin_frac),
            "refine_sampler": str(args.refine_sampler),
            "refine_seed": int(args.refine_seed),
            "refine_n_per_seed": int(args.refine_n_per_seed),
            "refine_radius_rel": float(args.refine_radius_rel),
            "refine_strategy": str(refine_strategy),
            "refine_target_metric": str(refine_target_metric),
            "refine_neighbors": int(args.refine_neighbors),
            "refine_top_params": int(args.refine_top_params),
            "refine_step_frac": float(args.refine_step_frac),
            "refine_direction": str(args.refine_direction),
            "refine_anchor_filter": str(args.refine_anchor_filter),
            "refine_hold_fixed_nonnumeric": bool(int(args.refine_hold_fixed_nonnumeric)),
            "refine_plausibility": str(args.refine_plausibility),
            "refine_require_drift_sign": str(args.refine_require_drift_sign),
            "robustness_objective": str(args.robustness_objective),
            "robustness_min_runs": int(args.robustness_min_runs),
            "robustness_require_drift_consistency": bool(int(args.robustness_require_drift_consistency)),
            "robustness_require_plausible": bool(int(args.robustness_require_plausible)),
            "robustness_aggregate_path": robustness_aggregate_path,
            "robustness_aggregate_sha256": robustness_aggregate_sha256,
            "status_filter": str(args.status_filter),
            "show_params": list(show_params),
            "generated_utc": _now_utc(),
            "outputs": {
                "pareto_summary_json": str(out_summary),
                "pareto_frontier_csv": str(out_frontier),
                "pareto_top_positive_csv": str(out_top_positive),
                "pareto_report_md": str(out_report_md),
                "refine_bounds_json": None if out_refine_bounds is None else str(out_refine_bounds),
                "refine_plan_json": None if out_refine_plan is None else str(out_refine_plan),
                "seed_points_jsonl": None if out_seed_points is None else str(out_seed_points),
            },
        },
    }
    if rank_mode_explicit:
        summary["rank_by"] = str(rank_by_mode)
        summary["rsd_chi2_field_used"] = (
            str(rsd_chi2_field_used) if rsd_chi2_field_used is not None else None
        )
        summary["best_rank_metric"] = _finite_float(best_rank_metric)
        summary["best_rank_metric_components"] = _to_json_safe(best_rank_metric_components)
        cfg = summary.get("config")
        if isinstance(cfg, dict):
            cfg["rank_by"] = str(rank_by_mode)
            cfg["rsd_chi2_field_used"] = (
                str(rsd_chi2_field_used) if rsd_chi2_field_used is not None else None
            )
    if rsd_overlay_summary is not None:
        summary["rsd_overlay"] = _to_json_safe(rsd_overlay_summary)
        cfg = summary.get("config")
        if isinstance(cfg, dict):
            cfg["rsd_overlay"] = {
                "enabled": True,
                "data_path": rsd_data_path_resolved,
                "data_sha256": rsd_data_sha256,
                "ap_correction": bool(rsd_ap_correction),
                "mode": str(args.rsd_mode),
                "weight": float(args.rsd_weight),
            }

    out_summary.write_text(json.dumps(_to_json_safe(summary), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_csv(
        out_frontier,
        points=frontier,
        include_chi2_parts_json=False,
        show_params=show_params,
        include_rsd_overlay=bool(rsd_overlay_enabled),
        overlay_by_key=rsd_overlay_by_key,
    )
    _write_csv(
        out_top_positive,
        points=top_positive,
        include_chi2_parts_json=True,
        show_params=show_params,
        include_rsd_overlay=bool(rsd_overlay_enabled),
        overlay_by_key=rsd_overlay_by_key,
    )
    _write_report_md(
        out_report_md,
        summary=summary,
        frontier=frontier,
        top_positive=top_positive,
        rsd_overlay_summary=rsd_overlay_summary,
    )
    if out_refine_bounds is not None:
        refine_payload = {
            "schema": "gsc.phase2.e2.refine_bounds.v1",
            "source_jsonl": [str(p) for p in jsonl_paths],
            "generated_utc": _now_utc(),
            "top_k": int(args.refine_top_k),
            "score": str(args.refine_score),
            "margin_frac": float(args.refine_margin_frac),
            "bounds": _to_json_safe(refine_bounds),
        }
        out_refine_bounds.write_text(json.dumps(refine_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if out_refine_plan is not None:
        assert refine_plan_payload is not None
        write_refine_plan_v1(out_refine_plan, _to_json_safe(refine_plan_payload))
    if out_seed_points is not None:
        with out_seed_points.open("w", encoding="utf-8") as fh:
            for row in seed_points_payload:
                fh.write(json.dumps(_to_json_safe(row), sort_keys=True) + "\n")

    print(
        "[stats] "
        f"total_read={int(len(all_points))} "
        f"eligible_used={int(len(pareto_points))} "
        f"skipped_drift={int(n_skipped_drift)} "
        f"errored={int(n_error_status)} "
        f"incomplete_missing_metrics={int(n_incomplete_metrics)} "
        f"filtered_invariants={int(n_invariants_filtered)}"
    )
    for label in sorted(status_counts.keys()):
        print(f"[stats] status[{label}]={int(status_counts[label])}")
    if rank_mode_explicit:
        print(
            "[ranking] "
            f"rank_by={str(rank_by_mode)} "
            f"rsd_chi2_field={str(rsd_chi2_field_used) if rsd_chi2_field_used is not None else 'null'}"
        )
        if best_rank_metric is not None:
            comps = best_rank_metric_components or {}
            print(
                "[ranking] best "
                f"metric={float(best_rank_metric):.12g} "
                f"chi2_total={_finite_float(comps.get('chi2_total'))} "
                f"rsd_chi2={_finite_float(comps.get('rsd_chi2'))}"
            )
    if rsd_overlay_summary is not None:
        print(
            "[stats] rsd_overlay "
            f"enabled=1 candidates={int(rsd_overlay_summary.get('n_overlay_candidates', 0))} "
            f"ok={int(rsd_overlay_summary.get('n_overlay_ok', 0))} "
            f"skipped={int(rsd_overlay_summary.get('n_overlay_skipped', 0))} "
            f"error={int(rsd_overlay_summary.get('n_overlay_error', 0))}"
        )
    print(f"[ok] wrote {out_summary}")
    print(f"[ok] wrote {out_frontier}")
    print(f"[ok] wrote {out_top_positive}")
    print(f"[ok] wrote {out_report_md}")
    if out_refine_bounds is not None:
        print(f"[ok] wrote {out_refine_bounds}")
    if out_refine_plan is not None:
        print(f"[ok] wrote {out_refine_plan}")
    if out_seed_points is not None:
        print(f"[ok] wrote {out_seed_points}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

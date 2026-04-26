"""Shared helpers for ``phase2_e2_refine_plan_v1`` I/O.

This module is stdlib-only and keeps refine-plan parsing/writing deterministic.
"""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterator, Mapping, Tuple


PLAN_VERSION_V1 = "phase2_e2_refine_plan_v1"


def _finite_float(value: Any) -> float:
    try:
        out = float(value)
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError(f"non-numeric parameter value: {value!r}") from exc
    if not math.isfinite(out):
        raise ValueError(f"non-finite parameter value: {value!r}")
    return float(out)


def _canonical_params(raw_params: Mapping[str, Any], *, point_index: int) -> Dict[str, float]:
    params: Dict[str, float] = {}
    for key in sorted(str(k) for k in raw_params.keys()):
        params[str(key)] = _finite_float(raw_params[key])
    if not params:
        raise ValueError(f"plan point #{point_index} has no numeric params")
    return params


def validate_refine_plan_v1(payload: Any) -> Dict[str, Any]:
    """Validate and normalize a refine plan payload (schema v1)."""
    if not isinstance(payload, Mapping):
        raise ValueError("refine plan must be a JSON object")
    version = str(payload.get("plan_version", "")).strip()
    if version != PLAN_VERSION_V1:
        raise ValueError(
            f"unsupported refine plan version: {version!r} (expected {PLAN_VERSION_V1!r})"
        )
    raw_points = payload.get("points")
    if not isinstance(raw_points, list):
        raise ValueError("refine plan must contain list field 'points'")

    normalized = copy.deepcopy(dict(payload))
    points_out: list[Dict[str, Any]] = []
    for idx, raw_point in enumerate(raw_points):
        if not isinstance(raw_point, Mapping):
            raise ValueError(f"plan point #{idx} must be a JSON object")
        params_raw = raw_point.get("params")
        if not isinstance(params_raw, Mapping):
            raise ValueError(f"plan point #{idx} missing object field 'params'")
        point_obj = copy.deepcopy(dict(raw_point))
        if "point_id" not in point_obj and "plan_point_id" not in point_obj:
            point_obj["point_id"] = f"plan_p{idx:06d}"
        point_obj["params"] = _canonical_params(params_raw, point_index=idx)
        points_out.append(point_obj)
    normalized["points"] = points_out
    return normalized


def load_refine_plan_v1(path: Path) -> Dict[str, Any]:
    """Load and validate a ``phase2_e2_refine_plan_v1`` file."""
    plan_path = Path(path).expanduser().resolve()
    if not plan_path.is_file():
        raise ValueError(f"refine plan file not found: {plan_path}")
    try:
        payload = json.loads(plan_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"failed to parse refine plan JSON: {plan_path}") from exc
    return validate_refine_plan_v1(payload)


def write_refine_plan_v1(path: Path, plan_dict: Mapping[str, Any]) -> None:
    """Write a validated refine plan JSON in deterministic canonical form."""
    output_path = Path(path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    normalized = validate_refine_plan_v1(plan_dict)
    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(normalized, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(output_path)


def iter_plan_points(plan_dict: Mapping[str, Any]) -> Iterator[Tuple[str, Dict[str, Any], Dict[str, float]]]:
    """Yield ``(plan_point_id, point_obj, params_obj)`` for each plan point."""
    normalized = validate_refine_plan_v1(plan_dict)
    raw_points = normalized.get("points", [])
    for idx, raw_point in enumerate(raw_points):
        point_obj = copy.deepcopy(dict(raw_point))
        raw_id = point_obj.get("point_id", point_obj.get("plan_point_id", f"plan_p{idx:06d}"))
        point_id = str(raw_id).strip() or f"plan_p{idx:06d}"
        point_obj["point_id"] = point_id
        params = _canonical_params(point_obj.get("params", {}), point_index=idx)
        yield point_id, point_obj, params


def get_plan_source_sha256(plan_dict: Mapping[str, Any]) -> str:
    """Best-effort extraction of the source JSONL SHA256 from a plan payload."""
    source = plan_dict.get("source")
    if isinstance(source, Mapping):
        for key in ("jsonl_sha256", "source_sha256"):
            raw = source.get(key)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
    for key in ("plan_source_sha256", "source_jsonl_sha256", "jsonl_sha256"):
        raw = plan_dict.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return ""


__all__ = [
    "PLAN_VERSION_V1",
    "get_plan_source_sha256",
    "iter_plan_points",
    "load_refine_plan_v1",
    "validate_refine_plan_v1",
    "write_refine_plan_v1",
]

#!/usr/bin/env python3
"""Deterministic E2 certificate report from scan JSONL/bundle inputs (stdlib-only)."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple
import zipfile

V101_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V101_DIR))

from gsc.early_time.refine_plan_v1 import (  # noqa: E402
    get_plan_source_sha256,
    iter_plan_points,
    load_refine_plan_v1,
)

SCHEMA_ID = "phase2_e2_certificate_v1"
TOOL_NAME = "phase2_e2_certificate_report.py"
TOOL_VERSION = "v1"
DEFAULT_CREATED_UTC = "1970-01-01T00:00:00Z"


@dataclass(frozen=True)
class InputEntry:
    path: str
    sha256: str
    bytes: int
    n_lines: int
    n_invalid_json: int
    n_non_object: int


@dataclass(frozen=True)
class RawRecord:
    source: str
    line: int
    obj: Dict[str, Any]


@dataclass(frozen=True)
class E2Record:
    source: str
    line: int
    params_hash: str
    params_hash_source: str
    status: str
    status_missing: bool
    chi2_total: Optional[float]
    chi2_total_source: Optional[str]
    chi2_cmb: Optional[float]
    chi2_cmb_source: Optional[str]
    chi2_late: Optional[float]
    chi2_late_source: Optional[str]
    chi2_joint_total: Optional[float]
    chi2_joint_total_source: Optional[str]
    drift_metric: Optional[float]
    drift_metric_source: Optional[str]
    drift_ok: Optional[bool]
    drift_ok_source: Optional[str]
    plausible_ok: bool
    plausible_present: bool
    microphysics_penalty: Optional[float]
    microphysics_max_rel_dev: Optional[float]
    params: Dict[str, Any]
    plan_point_id: str
    plan_source_sha256: str
    rsd_chi2_field_used: Optional[str]
    rsd_chi2_weight: Optional[float]
    rsd_transfer_model: Optional[str]
    rsd_primordial_ns: Optional[float]
    rsd_primordial_k_pivot_mpc: Optional[float]
    rsd_dataset_sha256: Optional[str]
    error_bucket: Optional[str]
    marker_buckets: Tuple[str, ...]


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


def _bool_like(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        fv = _finite_float(value)
        if fv is None:
            return None
        if fv == 1.0:
            return True
        if fv == 0.0:
            return False
        return fv > 0.0
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y", "ok"}:
        return True
    if text in {"0", "false", "f", "no", "n"}:
        return False
    return None


def _to_json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Mapping):
        return {str(k): _to_json_safe(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_to_json_safe(v) for v in value]
    try:
        out = float(value)
    except Exception:
        return str(value)
    return out if math.isfinite(out) else None


def _sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _normalize_created_utc(value: Optional[str]) -> str:
    text = str(value or "").strip()
    if not text:
        return DEFAULT_CREATED_UTC
    try:
        _ = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception as exc:
        raise SystemExit(f"Invalid --created-utc value: {value!r}") from exc
    return text


def _safe_bundle_member_path(name: str) -> bool:
    posix = PurePosixPath(str(name))
    if posix.is_absolute():
        return False
    return ".." not in posix.parts


def _iter_bundle_jsonl_payloads(bundle_path: Path) -> List[Tuple[str, bytes]]:
    resolved = bundle_path.expanduser().resolve()
    if resolved.is_dir():
        payloads: List[Tuple[str, bytes]] = []
        for candidate in sorted(resolved.rglob("*.jsonl")):
            if candidate.is_file():
                payloads.append((str(candidate.relative_to(resolved)), candidate.read_bytes()))
        return payloads

    suffix = resolved.suffix.lower()
    if suffix == ".zip":
        payloads = []
        with zipfile.ZipFile(resolved, "r") as zf:
            names = sorted(name for name in zf.namelist() if name.lower().endswith(".jsonl") and not name.endswith("/"))
            for name in names:
                if not _safe_bundle_member_path(name):
                    raise SystemExit(f"Unsafe bundle member path: {name}")
                payloads.append((str(name), zf.read(name)))
        return payloads

    if suffix in {".tar", ".tgz", ".gz"} or str(resolved).lower().endswith(".tar.gz"):
        payloads = []
        with tarfile.open(resolved, "r:*") as tf:
            members = sorted((m for m in tf.getmembers() if m.isfile()), key=lambda m: str(m.name))
            for member in members:
                name = str(member.name)
                if not name.lower().endswith(".jsonl"):
                    continue
                if not _safe_bundle_member_path(name):
                    raise SystemExit(f"Unsafe bundle member path: {name}")
                fh = tf.extractfile(member)
                if fh is None:
                    continue
                payloads.append((name, fh.read()))
        return payloads

    raise SystemExit(f"Unsupported bundle path/type: {resolved}")


def _parse_jsonl_text(source: str, text: str) -> Tuple[List[RawRecord], Dict[str, int]]:
    records: List[RawRecord] = []
    stats = {
        "n_lines": 0,
        "n_blank": 0,
        "n_invalid_json": 0,
        "n_non_object": 0,
    }
    for idx, line in enumerate(text.splitlines(), start=1):
        stats["n_lines"] += 1
        stripped = line.strip()
        if not stripped:
            stats["n_blank"] += 1
            continue
        if stripped.startswith("#"):
            continue
        try:
            parsed = json.loads(stripped)
        except Exception:
            stats["n_invalid_json"] += 1
            continue
        if not isinstance(parsed, Mapping):
            stats["n_non_object"] += 1
            continue
        records.append(
            RawRecord(
                source=str(source),
                line=int(idx),
                obj={str(k): parsed[k] for k in parsed.keys()},
            )
        )
    return records, stats


def _load_jsonl_path(path: Path) -> Tuple[List[RawRecord], InputEntry, Dict[str, int]]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise SystemExit(f"JSONL not found: {resolved}")
    data = resolved.read_bytes()
    records, stats = _parse_jsonl_text(str(resolved), data.decode("utf-8"))
    entry = InputEntry(
        path=str(resolved),
        sha256=_sha256_bytes(data),
        bytes=len(data),
        n_lines=int(stats.get("n_lines", 0)),
        n_invalid_json=int(stats.get("n_invalid_json", 0)),
        n_non_object=int(stats.get("n_non_object", 0)),
    )
    return records, entry, stats


def _load_bundle_path(path: Path) -> Tuple[List[RawRecord], List[InputEntry], Dict[str, int]]:
    resolved = path.expanduser().resolve()
    payloads = _iter_bundle_jsonl_payloads(resolved)
    if not payloads:
        raise SystemExit(f"No *.jsonl payloads found in bundle: {resolved}")
    records: List[RawRecord] = []
    entries: List[InputEntry] = []
    stats = {
        "n_lines": 0,
        "n_blank": 0,
        "n_invalid_json": 0,
        "n_non_object": 0,
    }
    for member_name, data in payloads:
        source = f"{resolved}!{member_name}"
        parsed, local_stats = _parse_jsonl_text(source, data.decode("utf-8"))
        records.extend(parsed)
        for key in stats.keys():
            stats[key] += int(local_stats.get(key, 0))
        entries.append(
            InputEntry(
                path=source,
                sha256=_sha256_bytes(data),
                bytes=len(data),
                n_lines=int(local_stats.get("n_lines", 0)),
                n_invalid_json=int(local_stats.get("n_invalid_json", 0)),
                n_non_object=int(local_stats.get("n_non_object", 0)),
            )
        )
    return records, entries, stats


def _extract_chi2_component(value: Any) -> Optional[float]:
    if isinstance(value, Mapping):
        return _finite_float(value.get("chi2"))
    return _finite_float(value)


def _extract_chi2_total(obj: Mapping[str, Any]) -> Tuple[Optional[float], Optional[str]]:
    direct_keys = [
        "chi2_total",
        "chi2",
        "chi2_tot",
        "result.chi2_total",
        "metrics.chi2_total",
    ]
    for key in direct_keys:
        if "." in key:
            current: Any = obj
            ok = True
            for token in key.split("."):
                if not isinstance(current, Mapping) or token not in current:
                    ok = False
                    break
                current = current[token]
            if not ok:
                continue
            value = _finite_float(current)
        else:
            value = _finite_float(obj.get(key))
        if value is not None:
            return value, key

    parts = _as_mapping(obj.get("chi2_parts"))
    values: List[float] = []
    for key in sorted(parts.keys(), key=lambda x: str(x)):
        comp = _extract_chi2_component(parts[key])
        if comp is not None:
            values.append(float(comp))
    if values:
        return float(sum(values)), "chi2_parts_sum"
    return None, None


def _extract_chi2_cmb(obj: Mapping[str, Any]) -> Tuple[Optional[float], Optional[str]]:
    direct = _finite_float(obj.get("chi2_cmb"))
    if direct is not None:
        return direct, "chi2_cmb"

    parts = _as_mapping(obj.get("chi2_parts"))
    cmb_priors = _extract_chi2_component(parts.get("cmb_priors"))
    if cmb_priors is not None:
        return cmb_priors, "chi2_parts.cmb_priors"
    cmb = _extract_chi2_component(parts.get("cmb"))
    if cmb is not None:
        return cmb, "chi2_parts.cmb"

    cmb_priors_block = _as_mapping(obj.get("cmb_priors"))
    nested = _finite_float(cmb_priors_block.get("chi2"))
    if nested is not None:
        return nested, "cmb_priors.chi2"

    cmb_block = _as_mapping(obj.get("cmb"))
    nested = _finite_float(cmb_block.get("chi2"))
    if nested is not None:
        return nested, "cmb.chi2"

    return None, None


def _extract_chi2_late(
    obj: Mapping[str, Any],
    *,
    chi2_total: Optional[float],
    chi2_cmb: Optional[float],
) -> Tuple[Optional[float], Optional[str]]:
    direct = _finite_float(obj.get("chi2_late"))
    if direct is not None:
        return direct, "chi2_late"

    parts = _as_mapping(obj.get("chi2_parts"))
    for key in ("late", "late_time", "late_total"):
        value = _extract_chi2_component(parts.get(key))
        if value is not None:
            return value, f"chi2_parts.{key}"

    if chi2_total is not None and chi2_cmb is not None:
        late = float(chi2_total) - float(chi2_cmb)
        if math.isfinite(late):
            return late, "chi2_total-chi2_cmb"

    return None, None


def _extract_chi2_joint_total(obj: Mapping[str, Any]) -> Tuple[Optional[float], Optional[str]]:
    for key in ("chi2_joint_total", "chi2_total_plus_rsd", "chi2_joint"):
        value = _finite_float(obj.get(key))
        if value is not None:
            return value, key
    return None, None


def _optional_text(value: Any, *, max_len: int = 256) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[: max(1, int(max_len))]


def _extract_error_bucket(obj: Mapping[str, Any], *, status: str) -> Optional[str]:
    error_obj = obj.get("error")
    if isinstance(error_obj, Mapping):
        err_type = _optional_text(error_obj.get("type"), max_len=120)
        if err_type is not None:
            return err_type
        message = _optional_text(error_obj.get("message"), max_len=120)
        if message is not None:
            return message.splitlines()[0][:120]
    if isinstance(error_obj, str):
        text = _optional_text(error_obj, max_len=120)
        if text is not None:
            return text.splitlines()[0][:120]
    if str(status).strip().lower() == "error":
        return "error"
    return None


def _extract_marker_buckets(obj: Mapping[str, Any], *, error_bucket: Optional[str]) -> Tuple[str, ...]:
    values: List[str] = []
    for key in ("error_marker", "rsd_overlay_skip_reason", "skip_reason"):
        text = _optional_text(obj.get(key), max_len=120)
        if text is not None:
            values.append(text)
    if error_bucket is not None:
        values.append(str(error_bucket))
    if isinstance(obj.get("error"), Mapping):
        text = _optional_text(_as_mapping(obj.get("error")).get("marker"), max_len=120)
        if text is not None:
            values.append(text)
    out: List[str] = []
    for raw in values:
        normalized = str(raw).strip()
        if not normalized:
            continue
        marker = None
        for token in normalized.replace(",", " ").replace(":", " ").split():
            cleaned = token.strip("[](){}<>\"'`.;")
            if cleaned.startswith("MISSING_") or cleaned.startswith("SCAN_CONFIG_"):
                marker = cleaned
                break
        if marker is None and (
            normalized.startswith("MISSING_")
            or normalized.startswith("SCAN_CONFIG_")
            or normalized.startswith("PLAN_")
            or normalized.startswith("RSD_")
        ):
            marker = normalized
        if marker is not None and marker not in out:
            out.append(marker[:120])
    return tuple(sorted(out))


def _extract_drift_metric(obj: Mapping[str, Any]) -> Tuple[Optional[float], Optional[str]]:
    direct = _finite_float(obj.get("drift_metric"))
    if direct is not None:
        return direct, "drift_metric"

    candidates = [
        ("drift_metrics", "metric"),
        ("drift", "metric"),
        ("drift", "min_z_dot"),
        ("drift_metrics", "min_zdot_z2_5"),
        ("chi2_parts", "drift", "min_zdot_si"),
    ]
    for path in candidates:
        cur: Any = obj
        ok = True
        for token in path:
            if not isinstance(cur, Mapping) or token not in cur:
                ok = False
                break
            cur = cur[token]
        if not ok:
            continue
        value = _finite_float(cur)
        if value is not None:
            return value, ".".join(path)
    return None, None


def _extract_drift_ok(
    obj: Mapping[str, Any],
    *,
    drift_metric: Optional[float],
) -> Tuple[Optional[bool], Optional[str]]:
    direct_keys = [
        "drift_precheck_ok",
        "drift_sign_z2_5",
        "drift_ok_z2_5",
        "drift_sign_ok",
        "drift_pass",
    ]
    for key in direct_keys:
        if key not in obj:
            continue
        value = _bool_like(obj.get(key))
        if value is not None:
            return bool(value), key

    nested_candidates = [
        ("drift", "all_positive"),
        ("drift_metrics", "sign_ok_z2_5"),
        ("drift_metrics", "ok_z2_5"),
        ("chi2_parts", "drift", "sign_ok"),
    ]
    for path in nested_candidates:
        cur: Any = obj
        ok = True
        for token in path:
            if not isinstance(cur, Mapping) or token not in cur:
                ok = False
                break
            cur = cur[token]
        if not ok:
            continue
        value = _bool_like(cur)
        if value is not None:
            return bool(value), ".".join(path)

    if drift_metric is not None:
        return bool(float(drift_metric) > 0.0), "drift_metric>0"
    return None, None


def _extract_params(obj: Mapping[str, Any]) -> Dict[str, Any]:
    params_raw = _as_mapping(obj.get("params"))
    return {str(k): _to_json_safe(params_raw[k]) for k in sorted(params_raw.keys(), key=lambda x: str(x))}


def _fallback_params_hash(params: Mapping[str, Any], obj: Mapping[str, Any]) -> str:
    if params:
        payload = _canonical_json({str(k): _to_json_safe(params[k]) for k in sorted(params.keys())})
        return _sha256_bytes(payload.encode("utf-8"))
    payload = _canonical_json({str(k): _to_json_safe(obj[k]) for k in sorted(obj.keys())})
    return _sha256_bytes(payload.encode("utf-8"))


def _normalize_record(raw: RawRecord) -> E2Record:
    obj = raw.obj
    raw_status = obj.get("status")
    status_missing = raw_status is None
    if raw_status is None:
        status = "unknown"
    else:
        status_text = str(raw_status).strip().lower()
        status = status_text if status_text else "unknown"

    params = _extract_params(obj)
    params_hash_raw = obj.get("params_hash")
    if isinstance(params_hash_raw, str) and params_hash_raw.strip():
        params_hash = params_hash_raw.strip()
        params_hash_source = "params_hash"
    else:
        params_hash = _fallback_params_hash(params, obj)
        params_hash_source = "fallback"

    chi2_total, chi2_total_source = _extract_chi2_total(obj)
    chi2_cmb, chi2_cmb_source = _extract_chi2_cmb(obj)
    chi2_late, chi2_late_source = _extract_chi2_late(obj, chi2_total=chi2_total, chi2_cmb=chi2_cmb)
    chi2_joint_total, chi2_joint_total_source = _extract_chi2_joint_total(obj)
    drift_metric, drift_metric_source = _extract_drift_metric(obj)
    drift_ok, drift_ok_source = _extract_drift_ok(obj, drift_metric=drift_metric)

    plausible_present = "microphysics_plausible_ok" in obj
    plausible = _bool_like(obj.get("microphysics_plausible_ok"))
    plausible_ok = True if plausible is None else bool(plausible)

    error_bucket = _extract_error_bucket(obj, status=status)
    marker_buckets = _extract_marker_buckets(obj, error_bucket=error_bucket)

    return E2Record(
        source=str(raw.source),
        line=int(raw.line),
        params_hash=str(params_hash),
        params_hash_source=str(params_hash_source),
        status=str(status),
        status_missing=bool(status_missing),
        chi2_total=chi2_total,
        chi2_total_source=chi2_total_source,
        chi2_cmb=chi2_cmb,
        chi2_cmb_source=chi2_cmb_source,
        chi2_late=chi2_late,
        chi2_late_source=chi2_late_source,
        chi2_joint_total=chi2_joint_total,
        chi2_joint_total_source=chi2_joint_total_source,
        drift_metric=drift_metric,
        drift_metric_source=drift_metric_source,
        drift_ok=drift_ok,
        drift_ok_source=drift_ok_source,
        plausible_ok=bool(plausible_ok),
        plausible_present=bool(plausible_present),
        microphysics_penalty=_finite_float(obj.get("microphysics_penalty")),
        microphysics_max_rel_dev=_finite_float(obj.get("microphysics_max_rel_dev")),
        params=params,
        plan_point_id=str(obj.get("plan_point_id", "")).strip(),
        plan_source_sha256=str(obj.get("plan_source_sha256", "")).strip(),
        rsd_chi2_field_used=_optional_text(obj.get("rsd_chi2_field_used"), max_len=80),
        rsd_chi2_weight=_finite_float(obj.get("rsd_chi2_weight")),
        rsd_transfer_model=_optional_text(obj.get("rsd_transfer_model"), max_len=80),
        rsd_primordial_ns=_finite_float(obj.get("rsd_primordial_ns")),
        rsd_primordial_k_pivot_mpc=_finite_float(obj.get("rsd_primordial_k_pivot_mpc")),
        rsd_dataset_sha256=_optional_text(obj.get("rsd_dataset_sha256"), max_len=64),
        error_bucket=error_bucket,
        marker_buckets=marker_buckets,
    )


def _fmt(value: Any) -> str:
    fv = _finite_float(value)
    if fv is None:
        return "NA"
    return f"{float(fv):.6g}"


def _is_status_ok(status: str) -> bool:
    return str(status).strip().lower() == "ok"


def _is_eligible(record: E2Record, *, status_filter: str) -> bool:
    if str(status_filter) == "ok_only" and not _is_status_ok(record.status):
        return False
    return record.chi2_total is not None and record.chi2_cmb is not None


def _is_eligible_status_only(record: E2Record, *, status_filter: str) -> bool:
    mode = str(status_filter)
    if mode == "ok_only":
        return _is_status_ok(record.status)
    return str(record.status).strip().lower() != "error"


def _record_summary(record: E2Record, *, outdir: Path) -> Dict[str, Any]:
    return {
        "source": _normalize_outdir_path(str(record.source), outdir=outdir),
        "line": int(record.line),
        "params_hash": str(record.params_hash),
        "params_hash_source": str(record.params_hash_source),
        "plan_point_id": str(record.plan_point_id),
        "status": str(record.status),
        "chi2_total": record.chi2_total,
        "chi2_joint_total": record.chi2_joint_total,
        "chi2_cmb": record.chi2_cmb,
        "chi2_late": record.chi2_late,
        "drift_ok": record.drift_ok,
        "drift_metric": record.drift_metric,
        "drift_metric_name": record.drift_metric_source,
        "microphysics_plausible_ok": bool(record.plausible_ok),
        "microphysics_penalty": record.microphysics_penalty,
        "microphysics_max_rel_dev": record.microphysics_max_rel_dev,
        "rsd_chi2_field_used": record.rsd_chi2_field_used,
        "rsd_chi2_weight": record.rsd_chi2_weight,
        "rsd_transfer_model": record.rsd_transfer_model,
        "rsd_primordial_ns": record.rsd_primordial_ns,
        "rsd_primordial_k_pivot_mpc": record.rsd_primordial_k_pivot_mpc,
        "rsd_dataset_sha256": record.rsd_dataset_sha256,
        "params": {str(k): _to_json_safe(v) for k, v in sorted(record.params.items())},
    }


def _better_record(a: E2Record, b: E2Record) -> bool:
    a_key = (
        float(a.chi2_total) if a.chi2_total is not None else float("inf"),
        str(a.params_hash),
        str(a.source),
        int(a.line),
    )
    b_key = (
        float(b.chi2_total) if b.chi2_total is not None else float("inf"),
        str(b.params_hash),
        str(b.source),
        int(b.line),
    )
    return a_key < b_key


def _update_best(best: Optional[E2Record], candidate: E2Record) -> E2Record:
    if best is None:
        return candidate
    if _better_record(candidate, best):
        return candidate
    return best


def _topk_push(container: List[E2Record], candidate: E2Record, *, top_k: int) -> None:
    container.append(candidate)
    container.sort(
        key=lambda r: (
            float(r.chi2_total) if r.chi2_total is not None else float("inf"),
            str(r.params_hash),
            str(r.source),
            int(r.line),
        )
    )
    if len(container) > int(top_k):
        del container[int(top_k) :]


def _git_sha(repo_root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        out = str((proc.stdout or "").strip())
        return out if out else "UNKNOWN"
    except Exception:
        return "UNKNOWN"


def _norm_path(path: Path) -> str:
    return str(path.expanduser().resolve())


def _normalize_outdir_path(text: str, *, outdir: Path) -> str:
    raw = str(text)
    outdir_resolved = str(outdir.expanduser().resolve())
    if raw == outdir_resolved:
        return "<OUTDIR>"
    prefix = outdir_resolved + "/"
    if raw.startswith(prefix):
        return "<OUTDIR>/" + raw[len(prefix) :]
    return raw


def _load_inputs(
    *,
    jsonl_paths: Sequence[Path],
    bundle_paths: Sequence[Path],
) -> Tuple[List[RawRecord], List[InputEntry], Dict[str, int]]:
    records: List[RawRecord] = []
    entries: List[InputEntry] = []
    parse_stats = {
        "n_lines": 0,
        "n_blank": 0,
        "n_invalid_json": 0,
        "n_non_object": 0,
    }

    for path in sorted(jsonl_paths, key=lambda p: str(p)):
        recs, entry, local_stats = _load_jsonl_path(path)
        records.extend(recs)
        entries.append(entry)
        for key in parse_stats.keys():
            parse_stats[key] += int(local_stats.get(key, 0))

    for path in sorted(bundle_paths, key=lambda p: str(p)):
        recs, loaded_entries, local_stats = _load_bundle_path(path)
        records.extend(recs)
        entries.extend(loaded_entries)
        for key in parse_stats.keys():
            parse_stats[key] += int(local_stats.get(key, 0))

    return records, sorted(entries, key=lambda x: str(x.path)), parse_stats


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip("\n") + "\n", encoding="utf-8")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    _write_text(path, json.dumps(payload, indent=2, sort_keys=True))


def _build_markdown(payload: Mapping[str, Any]) -> str:
    counts = _as_mapping(payload.get("counts"))
    input_summary = _as_mapping(payload.get("input_summary"))
    options = _as_mapping(payload.get("options"))
    coverage = payload.get("coverage")
    best = _as_mapping(payload.get("best"))
    best_cmb = _as_mapping(payload.get("best_cmb"))
    best_joint = _as_mapping(payload.get("best_joint"))
    topk = _as_mapping(payload.get("top_k"))

    lines: List[str] = []
    lines.append("# E2 Certificate")
    lines.append("")
    lines.append(f"- schema: `{payload.get('schema', '')}`")
    lines.append(f"- status_filter: `{options.get('status_filter', '')}`")
    lines.append(f"- plausibility: `{options.get('plausibility', '')}`")
    lines.append(f"- require_drift: `{options.get('require_drift', '')}`")
    lines.append(f"- cmb_chi2_threshold: `{_fmt(options.get('cmb_chi2_threshold'))}`")
    lines.append(f"- late_chi2_threshold: `{_fmt(options.get('late_chi2_threshold'))}`")
    lines.append("")
    lines.append("## Counts")
    lines.append("")
    for key in (
        "n_total_records",
        "n_records_invalid_json",
        "n_ok",
        "n_eligible",
        "n_plausible",
        "n_drift_ok",
        "n_cmb_ok",
        "n_joint_ok",
        "n_incomplete",
    ):
        if key in counts:
            lines.append(f"- {key}: `{counts.get(key)}`")
    if input_summary:
        lines.append(f"- eligible_status_filter: `{input_summary.get('eligible_status_filter', options.get('status_filter', ''))}`")
    lines.append("")

    lines.append("## Coverage")
    lines.append("")
    if coverage is None:
        lines.append("- coverage: `missing` (no plan provided)")
    else:
        cov = _as_mapping(coverage)
        lines.append(f"- mode: `{cov.get('mode', '')}`")
        lines.append(f"- n_plan_points: `{cov.get('n_plan_points', 0)}`")
        lines.append(f"- n_seen_plan_point_ids: `{cov.get('n_seen_plan_point_ids', 0)}`")
        lines.append(f"- fraction: `{_fmt(cov.get('fraction'))}`")
    lines.append("")

    lines.append("## Best")
    lines.append("")
    for key in ("best_overall", "best_plausible", "best_drift_ok", "best_cmb_ok", "best_joint_ok"):
        item = best.get(key)
        if not isinstance(item, Mapping):
            lines.append(f"- {key}: `NA`")
            continue
        lines.append(
            f"- {key}: params_hash=`{item.get('params_hash', '')}` chi2_total=`{_fmt(item.get('chi2_total'))}` chi2_cmb=`{_fmt(item.get('chi2_cmb'))}` drift=`{_fmt(item.get('drift_metric'))}`"
        )
    lines.append("")

    if best_cmb:
        lines.append("## Best CMB (eligible)")
        lines.append("")
        lines.append(
            "- params_hash=`{params_hash}` chi2_total=`{chi2_total}` plan_point_id=`{plan_point_id}` microphysics_plausible_ok=`{plausible}`".format(
                params_hash=best_cmb.get("params_hash", ""),
                chi2_total=_fmt(best_cmb.get("chi2_total")),
                plan_point_id=best_cmb.get("plan_point_id", ""),
                plausible=str(best_cmb.get("microphysics_plausible_ok", "")),
            )
        )
        lines.append("")

    if best_joint:
        lines.append("## Best JOINT (eligible)")
        lines.append("")
        lines.append(
            "- params_hash=`{params_hash}` chi2_joint_total=`{chi2_joint}` chi2_total=`{chi2_total}` plan_point_id=`{plan_point_id}`".format(
                params_hash=best_joint.get("params_hash", ""),
                chi2_joint=_fmt(best_joint.get("chi2_joint_total")),
                chi2_total=_fmt(best_joint.get("chi2_total")),
                plan_point_id=best_joint.get("plan_point_id", ""),
            )
        )
        lines.append(
            "- rsd_chi2_field_used=`{field}` rsd_chi2_weight=`{weight}` rsd_transfer_model=`{model}`".format(
                field=best_joint.get("rsd_chi2_field_used", ""),
                weight=_fmt(best_joint.get("rsd_chi2_weight")),
                model=best_joint.get("rsd_transfer_model", ""),
            )
        )
        lines.append("")

    joint_rows = topk.get("joint_ok")
    lines.append("## Top Joint")
    lines.append("")
    lines.append("| rank | params_hash | chi2_total | chi2_cmb | chi2_late | drift_metric |")
    lines.append("|---:|---|---:|---:|---:|---:|")
    if isinstance(joint_rows, Sequence):
        for idx, row in enumerate(joint_rows, start=1):
            if not isinstance(row, Mapping):
                continue
            lines.append(
                "| "
                + str(idx)
                + " | "
                + str(row.get("params_hash", ""))
                + " | "
                + _fmt(row.get("chi2_total"))
                + " | "
                + _fmt(row.get("chi2_cmb"))
                + " | "
                + _fmt(row.get("chi2_late"))
                + " | "
                + _fmt(row.get("drift_metric"))
                + " |"
            )
    lines.append("")

    warnings = payload.get("warnings")
    if isinstance(warnings, Sequence):
        lines.append("## Warnings")
        lines.append("")
        for warning in warnings:
            lines.append(f"- {warning}")

    return "\n".join(lines)


def _build_certificate(
    *,
    records: Sequence[E2Record],
    input_entries: Sequence[InputEntry],
    parse_stats: Mapping[str, int],
    jsonl_paths: Sequence[Path],
    bundle_paths: Sequence[Path],
    plan_payload: Optional[Mapping[str, Any]],
    plan_path: Optional[Path],
    require_plan_coverage: str,
    status_filter: str,
    plausibility_mode: str,
    cmb_chi2_threshold: float,
    late_chi2_threshold: float,
    require_drift: str,
    top_k: int,
    max_id_list: int,
    created_utc: str,
    repo_root: Path,
    outdir: Path,
) -> Tuple[Dict[str, Any], int]:
    warnings: List[str] = []

    n_total = len(records)
    n_ok = 0
    n_eligible = 0
    n_incomplete = 0
    n_plausible = 0
    n_drift_ok = 0
    n_cmb_ok = 0
    n_late_ok = 0
    n_joint_ok = 0

    n_missing_status = 0
    n_legacy_plausible = 0
    n_missing_late_treated_pass = 0

    best_overall: Optional[E2Record] = None
    best_plausible: Optional[E2Record] = None
    best_drift_ok: Optional[E2Record] = None
    best_cmb_ok: Optional[E2Record] = None
    best_joint_ok: Optional[E2Record] = None

    top_overall: List[E2Record] = []
    top_joint: List[E2Record] = []

    status_counts: Dict[str, int] = {}
    error_counts: Dict[str, int] = {}
    marker_counts: Dict[str, int] = {}

    best_cmb: Optional[E2Record] = None
    best_cmb_plausible: Optional[E2Record] = None
    best_joint: Optional[E2Record] = None
    best_joint_plausible: Optional[E2Record] = None

    # Coverage accounting
    plan_point_ids: List[str] = []
    plan_point_set: set[str] = set()
    plan_source_sha = ""
    seen_plan_ids: set[str] = set()
    n_records_matching_plan = 0
    n_records_foreign = 0
    n_records_unmapped = 0

    if plan_payload is not None:
        for point_id, _, _ in iter_plan_points(plan_payload):
            pid = str(point_id)
            plan_point_ids.append(pid)
            plan_point_set.add(pid)
        plan_point_ids = sorted(plan_point_ids)
        plan_source_sha = str(get_plan_source_sha256(plan_payload))

    for rec in records:
        status_counts[rec.status] = int(status_counts.get(rec.status, 0)) + 1
        if rec.error_bucket is not None:
            error_counts[str(rec.error_bucket)] = int(error_counts.get(str(rec.error_bucket), 0)) + 1
        for marker in rec.marker_buckets:
            marker_counts[str(marker)] = int(marker_counts.get(str(marker), 0)) + 1
        if rec.status_missing:
            n_missing_status += 1
        if _is_status_ok(rec.status):
            n_ok += 1
        if not rec.plausible_present:
            n_legacy_plausible += 1

        if plan_payload is not None:
            point_id = str(rec.plan_point_id)
            if not point_id:
                n_records_unmapped += 1
            else:
                foreign = bool(
                    point_id in plan_point_set
                    and plan_source_sha
                    and rec.plan_source_sha256
                    and str(rec.plan_source_sha256) != str(plan_source_sha)
                )
                if foreign:
                    n_records_foreign += 1
                elif point_id in plan_point_set:
                    n_records_matching_plan += 1
                    seen_plan_ids.add(point_id)

        status_eligible = _is_eligible_status_only(rec, status_filter=status_filter)
        if status_eligible:
            if rec.chi2_total is not None:
                best_cmb = _update_best(best_cmb, rec)
                if rec.plausible_ok:
                    best_cmb_plausible = _update_best(best_cmb_plausible, rec)
            if rec.chi2_joint_total is not None:
                if best_joint is None:
                    best_joint = rec
                else:
                    key_a = (
                        float(rec.chi2_joint_total),
                        str(rec.plan_point_id or ""),
                        str(rec.params_hash),
                    )
                    key_b = (
                        float(best_joint.chi2_joint_total) if best_joint.chi2_joint_total is not None else float("inf"),
                        str(best_joint.plan_point_id or ""),
                        str(best_joint.params_hash),
                    )
                    if key_a < key_b:
                        best_joint = rec
                if rec.plausible_ok:
                    if best_joint_plausible is None:
                        best_joint_plausible = rec
                    else:
                        key_a = (
                            float(rec.chi2_joint_total),
                            str(rec.plan_point_id or ""),
                            str(rec.params_hash),
                        )
                        key_b = (
                            float(best_joint_plausible.chi2_joint_total)
                            if best_joint_plausible.chi2_joint_total is not None
                            else float("inf"),
                            str(best_joint_plausible.plan_point_id or ""),
                            str(best_joint_plausible.params_hash),
                        )
                        if key_a < key_b:
                            best_joint_plausible = rec

        eligible = _is_eligible(rec, status_filter=status_filter)
        if not eligible:
            n_incomplete += 1
            continue

        n_eligible += 1
        _topk_push(top_overall, rec, top_k=top_k)
        best_overall = _update_best(best_overall, rec)

        plausible_gate = True if plausibility_mode == "any" else bool(rec.plausible_ok)
        if rec.plausible_ok:
            n_plausible += 1
            best_plausible = _update_best(best_plausible, rec)

        drift_ok = rec.drift_ok is True
        if drift_ok:
            n_drift_ok += 1
            best_drift_ok = _update_best(best_drift_ok, rec)

        cmb_ok = rec.chi2_cmb is not None and float(rec.chi2_cmb) <= float(cmb_chi2_threshold)
        if cmb_ok:
            n_cmb_ok += 1

        if rec.chi2_late is None:
            late_ok = True
            n_missing_late_treated_pass += 1
        else:
            late_ok = float(rec.chi2_late) <= float(late_chi2_threshold)

        if late_ok:
            n_late_ok += 1

        if cmb_ok and late_ok:
            best_cmb_ok = _update_best(best_cmb_ok, rec)

        drift_gate = True
        if require_drift == "positive":
            drift_gate = drift_ok

        joint_ok = bool(plausible_gate and drift_gate and cmb_ok and late_ok)
        if joint_ok:
            n_joint_ok += 1
            best_joint_ok = _update_best(best_joint_ok, rec)
            _topk_push(top_joint, rec, top_k=top_k)

    if n_missing_status > 0:
        warnings.append(f"{n_missing_status} record(s) missing status treated as unknown")
    if n_legacy_plausible > 0:
        warnings.append(
            f"{n_legacy_plausible} record(s) missing microphysics_plausible_ok treated as plausible (legacy back-compat)"
        )
    if n_missing_late_treated_pass > 0:
        warnings.append(
            f"{n_missing_late_treated_pass} eligible record(s) missing chi2_late treated as late-pass for joint gating"
        )

    coverage: Optional[Dict[str, Any]] = None
    if plan_payload is not None:
        missing_ids = sorted(pid for pid in plan_point_ids if pid not in seen_plan_ids)
        coverage = {
            "mode": str(require_plan_coverage),
            "n_plan_points": int(len(plan_point_ids)),
            "n_seen_plan_point_ids": int(len(seen_plan_ids)),
            "fraction": (
                float(len(seen_plan_ids)) / float(len(plan_point_ids)) if plan_point_ids else 1.0
            ),
            "n_records_matching_plan": int(n_records_matching_plan),
            "n_records_foreign": int(n_records_foreign),
            "n_records_unmapped": int(n_records_unmapped),
            "missing_plan_point_ids_sample": list(missing_ids[: max(0, int(max_id_list))]),
        }
    else:
        if require_plan_coverage == "complete":
            warnings.append("coverage requested but no --plan provided")

    jsonl_entries_payload = [
        {
            "path": _normalize_outdir_path(str(entry.path), outdir=outdir),
            "sha256": str(entry.sha256),
            "bytes": int(entry.bytes),
            "n_lines": int(entry.n_lines),
            "n_invalid_json": int(entry.n_invalid_json),
            "n_non_object": int(entry.n_non_object),
        }
        for entry in sorted(input_entries, key=lambda x: str(x.path))
    ]

    def _counts_top(mapping: Mapping[str, int], *, limit: int) -> List[Dict[str, Any]]:
        rows = sorted(
            ((str(k), int(v)) for k, v in mapping.items()),
            key=lambda kv: (-int(kv[1]), str(kv[0])),
        )
        return [{"key": str(k), "count": int(v)} for k, v in rows[: max(0, int(limit))]]

    def _best_cmb_payload(rec: Optional[E2Record]) -> Optional[Dict[str, Any]]:
        if rec is None:
            return None
        payload = _record_summary(rec, outdir=outdir)
        payload["chi2_total"] = rec.chi2_total
        payload["microphysics_plausible_ok"] = bool(rec.plausible_ok)
        payload["params_hash"] = str(rec.params_hash)
        payload["plan_point_id"] = str(rec.plan_point_id)
        return payload

    def _best_joint_payload(rec: Optional[E2Record]) -> Optional[Dict[str, Any]]:
        if rec is None:
            return None
        payload = _record_summary(rec, outdir=outdir)
        payload["chi2_joint_total"] = rec.chi2_joint_total
        payload["chi2_total"] = rec.chi2_total
        payload["params_hash"] = str(rec.params_hash)
        payload["plan_point_id"] = str(rec.plan_point_id)
        payload["microphysics_plausible_ok"] = bool(rec.plausible_ok)
        return payload

    n_records_invalid_json = int(parse_stats.get("n_invalid_json", 0))
    n_records_non_object = int(parse_stats.get("n_non_object", 0))
    errors_top = _counts_top(error_counts, limit=10)
    markers_top = _counts_top(marker_counts, limit=3)

    inputs_payload: Dict[str, Any] = {
        "jsonl_entries": jsonl_entries_payload,
        "plan": None,
    }
    if len(jsonl_entries_payload) == 1:
        inputs_payload["jsonl"] = dict(jsonl_entries_payload[0])

    if plan_payload is not None and plan_path is not None:
        plan_abs = plan_path.expanduser().resolve()
        inputs_payload["plan"] = {
            "path": _normalize_outdir_path(_norm_path(plan_abs), outdir=outdir),
            "sha256": _sha256_file(plan_abs),
            "bytes": int(plan_abs.stat().st_size),
            "n_points": int(len(plan_point_ids)),
        }

    payload: Dict[str, Any] = {
        "schema": SCHEMA_ID,
        "generated_utc": str(created_utc),
        "tool": {
            "name": TOOL_NAME,
            "version": TOOL_VERSION,
            "repo_git_sha": _git_sha(repo_root),
        },
        "inputs": inputs_payload,
        "options": {
            "status_filter": str(status_filter),
            "eligible_status_filter": str(status_filter),
            "plausibility": str(plausibility_mode),
            "cmb_chi2_threshold": float(cmb_chi2_threshold),
            "late_chi2_threshold": float(late_chi2_threshold),
            "require_drift": str(require_drift),
            "top_k": int(top_k),
            "require_plan_coverage": str(require_plan_coverage),
        },
        "coverage": coverage,
        "counts": {
            "n_total_records": int(n_total),
            "n_records_invalid_json": int(n_records_invalid_json),
            "n_records_non_object": int(n_records_non_object),
            "n_ok": int(n_ok),
            "n_eligible": int(n_eligible),
            "n_plausible": int(n_plausible),
            "n_drift_ok": int(n_drift_ok),
            "n_cmb_ok": int(n_cmb_ok),
            "n_late_ok": int(n_late_ok),
            "n_joint_ok": int(n_joint_ok),
            "n_incomplete": int(n_incomplete),
            "status_counts": {str(k): int(status_counts[k]) for k in sorted(status_counts.keys())},
        },
        "input_summary": {
            "n_records_total": int(n_total),
            "n_records_invalid_json": int(n_records_invalid_json),
            "n_records_non_object": int(n_records_non_object),
            "eligible_status_filter": str(status_filter),
            "status_counts": {str(k): int(status_counts[k]) for k in sorted(status_counts.keys())},
        },
        "best_cmb": _best_cmb_payload(best_cmb),
        "best_cmb_plausible": _best_cmb_payload(best_cmb_plausible),
        "best_joint": _best_joint_payload(best_joint),
        "best_joint_plausible": _best_joint_payload(best_joint_plausible),
        "preconditions": {
            "errors_top": list(errors_top),
            "markers_top": list(markers_top),
        },
        "best": {
            "best_overall": _record_summary(best_overall, outdir=outdir) if best_overall is not None else None,
            "best_plausible": _record_summary(best_plausible, outdir=outdir) if best_plausible is not None else None,
            "best_drift_ok": _record_summary(best_drift_ok, outdir=outdir) if best_drift_ok is not None else None,
            "best_cmb_ok": _record_summary(best_cmb_ok, outdir=outdir) if best_cmb_ok is not None else None,
            "best_joint_ok": _record_summary(best_joint_ok, outdir=outdir) if best_joint_ok is not None else None,
        },
        "top_k": {
            "overall": [_record_summary(rec, outdir=outdir) for rec in top_overall],
            "joint_ok": [_record_summary(rec, outdir=outdir) for rec in top_joint],
        },
        "errors_top": list(errors_top),
        "warnings": list(warnings),
    }

    exit_code = 0
    if require_plan_coverage == "complete":
        if coverage is None:
            exit_code = 2
        elif int(coverage.get("n_seen_plan_point_ids", 0)) != int(coverage.get("n_plan_points", 0)):
            exit_code = 2

    return payload, exit_code


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="phase2_e2_certificate_report",
        description="Generate deterministic E2 certificate artifacts from scan JSONL/bundle inputs.",
    )
    ap.add_argument("--jsonl", action="append", type=Path, default=[], help="Input JSONL path (repeatable).")
    ap.add_argument("--bundle", action="append", type=Path, default=[], help="Input bundle path (repeatable).")
    ap.add_argument("--outdir", required=True, type=Path, help="Output directory for certificate artifacts.")
    ap.add_argument("--plan", type=Path, default=None, help="Optional refine plan for coverage accounting.")
    ap.add_argument("--require-plan-coverage", choices=["off", "complete"], default="off")
    ap.add_argument("--status-filter", choices=["ok_only", "any_eligible"], default="ok_only")
    ap.add_argument(
        "--eligible-status",
        choices=["ok_only", "any_eligible"],
        default=None,
        help="Alias for --status-filter (preferred name for certificate eligibility semantics).",
    )
    ap.add_argument("--plausibility", choices=["any", "plausible_only"], default="plausible_only")
    ap.add_argument("--cmb-chi2-threshold", type=float, default=4.0)
    ap.add_argument("--late-chi2-threshold", type=float, default=10.0)
    ap.add_argument("--require-drift", choices=["off", "positive"], default="positive")
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--max-id-list", type=int, default=50)
    ap.add_argument(
        "--created-utc",
        type=str,
        default=DEFAULT_CREATED_UTC,
        help="Deterministic timestamp embedded in certificate output (default fixed).",
    )
    args = ap.parse_args(argv)

    if not args.jsonl and not args.bundle:
        raise SystemExit("Provide at least one input via --jsonl and/or --bundle")
    if int(args.top_k) <= 0:
        raise SystemExit("--top-k must be > 0")
    if int(args.max_id_list) < 0:
        raise SystemExit("--max-id-list must be >= 0")
    if not math.isfinite(float(args.cmb_chi2_threshold)):
        raise SystemExit("--cmb-chi2-threshold must be finite")
    if not math.isfinite(float(args.late_chi2_threshold)):
        raise SystemExit("--late-chi2-threshold must be finite")

    created_utc = _normalize_created_utc(args.created_utc)
    repo_root = V101_DIR.parent
    outdir = args.outdir.expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    raw_records, input_entries, parse_stats = _load_inputs(jsonl_paths=list(args.jsonl), bundle_paths=list(args.bundle))
    if not raw_records:
        raise SystemExit("No JSON records loaded from inputs")

    normalized = [_normalize_record(raw) for raw in raw_records]

    plan_payload: Optional[Mapping[str, Any]] = None
    if args.plan is not None:
        try:
            plan_payload = load_refine_plan_v1(args.plan)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1

    effective_status_filter = str(args.eligible_status or args.status_filter)

    payload, coverage_exit = _build_certificate(
        records=normalized,
        input_entries=input_entries,
        parse_stats=parse_stats,
        jsonl_paths=list(args.jsonl),
        bundle_paths=list(args.bundle),
        plan_payload=plan_payload,
        plan_path=args.plan,
        require_plan_coverage=str(args.require_plan_coverage),
        status_filter=effective_status_filter,
        plausibility_mode=str(args.plausibility),
        cmb_chi2_threshold=float(args.cmb_chi2_threshold),
        late_chi2_threshold=float(args.late_chi2_threshold),
        require_drift=str(args.require_drift),
        top_k=int(args.top_k),
        max_id_list=int(args.max_id_list),
        created_utc=str(created_utc),
        repo_root=repo_root,
        outdir=outdir,
    )

    json_path = outdir / "e2_certificate.json"
    md_path = outdir / "e2_certificate.md"

    _write_json(json_path, payload)
    _write_text(md_path, _build_markdown(payload))

    summary = {
        "schema": SCHEMA_ID,
        "outdir": str(outdir),
        "counts": payload.get("counts", {}),
        "coverage_exit": int(coverage_exit),
    }
    print(json.dumps(summary, sort_keys=True))

    if coverage_exit != 0:
        return int(coverage_exit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

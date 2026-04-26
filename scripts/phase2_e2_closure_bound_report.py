#!/usr/bin/env python3
"""Deterministic drift-constrained CMB closure bound report (stdlib-only)."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import tarfile
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
import zipfile


SCHEMA_ID = "phase2_e2_closure_bound_report_v1"
DEFAULT_CREATED_UTC = "1970-01-01T00:00:00Z"


@dataclass(frozen=True)
class InputEntry:
    path: str
    sha256: str
    bytes: int
    n_lines: int


@dataclass(frozen=True)
class RawRecord:
    source: str
    line: int
    obj: Dict[str, Any]


@dataclass(frozen=True)
class Record:
    source: str
    line: int
    params_hash: str
    params_hash_source: str
    status: str
    status_ok: bool
    chi2_cmb: Optional[float]
    chi2_total: Optional[float]
    chi2_parts: Dict[str, float]
    drift_metric: Optional[float]
    drift_positive: Optional[bool]
    drift_positive_source: Optional[str]
    plausible_ok: bool
    plausible_present: bool
    microphysics_penalty: Optional[float]
    microphysics_max_rel_dev: Optional[float]
    params: Dict[str, Any]


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


def _decode_jsonl_bytes(source: str, data: bytes) -> str:
    raw = bytes(data)
    if str(source).lower().endswith(".gz"):
        try:
            raw = gzip.decompress(raw)
        except OSError as exc:
            raise SystemExit(f"Invalid gzip JSONL payload: {source}") from exc
    return raw.decode("utf-8")


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


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
        for candidate in sorted(list(resolved.rglob("*.jsonl")) + list(resolved.rglob("*.jsonl.gz"))):
            if candidate.is_file():
                payloads.append((str(candidate.relative_to(resolved)), candidate.read_bytes()))
        return payloads

    suffix = resolved.suffix.lower()
    if suffix == ".zip":
        payloads = []
        with zipfile.ZipFile(resolved, "r") as zf:
            names = sorted(
                name
                for name in zf.namelist()
                if not name.endswith("/")
                and (name.lower().endswith(".jsonl") or name.lower().endswith(".jsonl.gz"))
            )
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
                if not (name.lower().endswith(".jsonl") or name.lower().endswith(".jsonl.gz")):
                    continue
                if not _safe_bundle_member_path(name):
                    raise SystemExit(f"Unsafe bundle member path: {name}")
                fh = tf.extractfile(member)
                if fh is None:
                    continue
                payloads.append((name, fh.read()))
        return payloads

    raise SystemExit(f"Unsupported bundle path/type: {resolved}")


def _parse_jsonl_text(source: str, text: str) -> Tuple[List[RawRecord], int]:
    out: List[RawRecord] = []
    n_lines = 0
    for idx, line in enumerate(text.splitlines(), start=1):
        n_lines += 1
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            parsed = json.loads(stripped)
        except Exception:
            continue
        if not isinstance(parsed, Mapping):
            continue
        out.append(
            RawRecord(
                source=str(source),
                line=int(idx),
                obj={str(k): parsed[k] for k in parsed.keys()},
            )
        )
    return out, n_lines


def _load_jsonl_path(path: Path) -> Tuple[List[RawRecord], InputEntry]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise SystemExit(f"JSONL not found: {resolved}")
    data = resolved.read_bytes()
    rows, n_lines = _parse_jsonl_text(str(resolved), _decode_jsonl_bytes(str(resolved), data))
    return rows, InputEntry(path=str(resolved), sha256=_sha256_bytes(data), bytes=len(data), n_lines=int(n_lines))


def _load_bundle_path(path: Path) -> Tuple[List[RawRecord], List[InputEntry]]:
    resolved = path.expanduser().resolve()
    payloads = _iter_bundle_jsonl_payloads(resolved)
    if not payloads:
        raise SystemExit(f"No *.jsonl payloads found in bundle: {resolved}")
    rows: List[RawRecord] = []
    entries: List[InputEntry] = []
    for member_name, data in payloads:
        source = f"{resolved}!{member_name}"
        parsed, n_lines = _parse_jsonl_text(source, _decode_jsonl_bytes(member_name, data))
        rows.extend(parsed)
        entries.append(InputEntry(path=source, sha256=_sha256_bytes(data), bytes=len(data), n_lines=int(n_lines)))
    return rows, entries


def _extract_chi2_component(value: Any) -> Optional[float]:
    if isinstance(value, Mapping):
        return _finite_float(value.get("chi2"))
    return _finite_float(value)


def _extract_chi2_parts(obj: Mapping[str, Any]) -> Dict[str, float]:
    parts = _as_mapping(obj.get("chi2_parts"))
    out: Dict[str, float] = {}
    for key in sorted(parts.keys(), key=lambda x: str(x)):
        comp = _extract_chi2_component(parts[key])
        if comp is not None:
            out[str(key)] = float(comp)
    return out


def _extract_chi2_cmb(obj: Mapping[str, Any], *, chi2_parts: Mapping[str, float]) -> Optional[float]:
    direct = _finite_float(obj.get("chi2_cmb"))
    if direct is not None:
        return direct
    if "cmb_priors" in chi2_parts:
        return float(chi2_parts["cmb_priors"])
    if "cmb" in chi2_parts:
        return float(chi2_parts["cmb"])
    nested = _finite_float(_as_mapping(obj.get("cmb_priors")).get("chi2"))
    if nested is not None:
        return nested
    nested = _finite_float(_as_mapping(obj.get("cmb")).get("chi2"))
    if nested is not None:
        return nested
    return None


def _extract_chi2_total(obj: Mapping[str, Any], *, chi2_parts: Mapping[str, float]) -> Optional[float]:
    for key in ("chi2_total", "chi2", "chi2_tot"):
        value = _finite_float(obj.get(key))
        if value is not None:
            return value
    if chi2_parts:
        return float(sum(float(v) for v in chi2_parts.values()))
    return None


def _extract_drift_metric(obj: Mapping[str, Any]) -> Optional[float]:
    direct = _finite_float(obj.get("drift_metric"))
    if direct is not None:
        return direct
    candidates = [
        ("drift_metrics", "metric"),
        ("drift", "metric"),
        ("drift_metrics", "min_zdot_z2_5"),
        ("drift", "min_z_dot"),
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
            return value
    return None


def _extract_drift_positive(obj: Mapping[str, Any], *, drift_metric: Optional[float]) -> Tuple[Optional[bool], Optional[str]]:
    for key in ("drift_sign_z2_5", "drift_ok_z2_5", "drift_sign_ok"):
        if key in obj:
            value = _bool_like(obj.get(key))
            if value is not None:
                return bool(value), key

    nested_candidates = [
        ("drift_metrics", "sign_ok_z2_5"),
        ("drift_metrics", "ok_z2_5"),
        ("drift", "sign_ok_z2_5"),
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

    spec = str(obj.get("drift_precheck_spec", "")).strip().lower()
    precheck_ok = _bool_like(obj.get("drift_precheck_ok"))
    if spec == "z2_5_positive" and precheck_ok is not None:
        return bool(precheck_ok), "drift_precheck_ok"

    if drift_metric is not None:
        return bool(float(drift_metric) >= 0.0), "drift_metric>=0"
    return None, None


def _extract_params_hash(obj: Mapping[str, Any]) -> Tuple[str, str]:
    raw = obj.get("params_hash")
    if isinstance(raw, str) and raw.strip():
        return raw.strip(), "params_hash"
    params = _as_mapping(obj.get("params"))
    if params:
        canonical = _canonical_json({str(k): params[k] for k in sorted(params.keys(), key=lambda x: str(x))})
        return _sha256_bytes(canonical.encode("utf-8")), "params_fallback"
    canonical = _canonical_json({str(k): obj[k] for k in sorted(obj.keys(), key=lambda x: str(x))})
    return _sha256_bytes(canonical.encode("utf-8")), "record_fallback"


def _extract_plausibility(obj: Mapping[str, Any]) -> Tuple[bool, bool]:
    if "microphysics_plausible_ok" not in obj:
        return True, False
    value = _bool_like(obj.get("microphysics_plausible_ok"))
    return (True if value is None else bool(value)), True


def _to_json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Mapping):
        return {str(k): _to_json_safe(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_to_json_safe(v) for v in value]
    maybe = _finite_float(value)
    if maybe is not None:
        return maybe
    return str(value)


def _normalize_record(raw: RawRecord) -> Record:
    obj = raw.obj
    status_text = str(obj.get("status", "")).strip().lower()
    status = status_text if status_text else "ok"
    status_ok = not status_text or status == "ok"
    params_hash, params_hash_source = _extract_params_hash(obj)
    chi2_parts = _extract_chi2_parts(obj)
    chi2_cmb = _extract_chi2_cmb(obj, chi2_parts=chi2_parts)
    chi2_total = _extract_chi2_total(obj, chi2_parts=chi2_parts)
    drift_metric = _extract_drift_metric(obj)
    drift_positive, drift_positive_source = _extract_drift_positive(obj, drift_metric=drift_metric)
    plausible_ok, plausible_present = _extract_plausibility(obj)
    params = _as_mapping(obj.get("params"))
    return Record(
        source=str(raw.source),
        line=int(raw.line),
        params_hash=str(params_hash),
        params_hash_source=str(params_hash_source),
        status=str(status),
        status_ok=bool(status_ok),
        chi2_cmb=chi2_cmb,
        chi2_total=chi2_total,
        chi2_parts={str(k): float(v) for k, v in sorted(chi2_parts.items())},
        drift_metric=drift_metric,
        drift_positive=drift_positive,
        drift_positive_source=drift_positive_source,
        plausible_ok=bool(plausible_ok),
        plausible_present=bool(plausible_present),
        microphysics_penalty=_finite_float(obj.get("microphysics_penalty")),
        microphysics_max_rel_dev=_finite_float(obj.get("microphysics_max_rel_dev")),
        params={str(k): _to_json_safe(params[k]) for k in sorted(params.keys(), key=lambda x: str(x))},
    )


def _fmt(value: Any) -> str:
    v = _finite_float(value)
    if v is None:
        return "NA"
    return f"{float(v):.6g}"


def _fmt_bool(value: Optional[bool]) -> str:
    if value is None:
        return "NA"
    return "true" if bool(value) else "false"


def _status_bucket(record: Record) -> str:
    status = str(record.status).strip().lower()
    if not status or status == "ok":
        return "ok"
    if status == "error":
        return "error"
    return status


def _eligible(record: Record, *, status_filter: str, plausibility: str) -> bool:
    if str(status_filter) == "ok_only" and not record.status_ok:
        return False
    if record.chi2_cmb is None:
        return False
    if str(plausibility) == "plausible_only" and not record.plausible_ok:
        return False
    return True


def _sort_key(record: Record) -> Tuple[Any, ...]:
    return (
        float(record.chi2_cmb) if record.chi2_cmb is not None else float("inf"),
        float(record.chi2_total) if record.chi2_total is not None else float("inf"),
        str(record.params_hash),
        str(record.source),
        int(record.line),
    )


def _best(records: Sequence[Record]) -> Optional[Record]:
    if not records:
        return None
    return min(records, key=_sort_key)


def _summary_entry(record: Optional[Record]) -> Optional[Dict[str, Any]]:
    if record is None:
        return None
    return {
        "params_hash": str(record.params_hash),
        "params_hash_source": str(record.params_hash_source),
        "status": str(record.status),
        "chi2_cmb": record.chi2_cmb,
        "chi2_total": record.chi2_total,
        "chi2_parts": {str(k): float(v) for k, v in sorted(record.chi2_parts.items())},
        "drift_metrics": {
            "metric": record.drift_metric,
            "positive": record.drift_positive,
            "positive_source": record.drift_positive_source,
        },
        "microphysics_plausible_ok": bool(record.plausible_ok),
        "microphysics_penalty": record.microphysics_penalty,
        "microphysics_max_rel_dev": record.microphysics_max_rel_dev,
        "params": {str(k): _to_json_safe(v) for k, v in sorted(record.params.items())},
    }


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip("\n") + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "rank",
        "params_hash",
        "status",
        "chi2_cmb",
        "chi2_total",
        "drift_positive",
        "drift_metric",
        "microphysics_plausible_ok",
        "microphysics_penalty",
        "microphysics_max_rel_dev",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for idx, row in enumerate(rows, start=1):
            drift_metrics = _as_mapping(row.get("drift_metrics"))
            writer.writerow(
                {
                    "rank": str(idx),
                    "params_hash": str(row.get("params_hash", "")),
                    "status": str(row.get("status", "")),
                    "chi2_cmb": _fmt(row.get("chi2_cmb")),
                    "chi2_total": _fmt(row.get("chi2_total")),
                    "drift_positive": _fmt_bool(_bool_like(drift_metrics.get("positive"))),
                    "drift_metric": _fmt(drift_metrics.get("metric")),
                    "microphysics_plausible_ok": _fmt_bool(_bool_like(row.get("microphysics_plausible_ok"))),
                    "microphysics_penalty": _fmt(row.get("microphysics_penalty")),
                    "microphysics_max_rel_dev": _fmt(row.get("microphysics_max_rel_dev")),
                }
            )


def _build_markdown(payload: Mapping[str, Any]) -> str:
    filters = _as_mapping(payload.get("filters"))
    counts = _as_mapping(payload.get("counts"))
    best = _as_mapping(payload.get("best"))
    top = payload.get("top_candidates") if isinstance(payload.get("top_candidates"), Sequence) else []

    lines: List[str] = []
    lines.append("# Phase-2 E2 Drift-Constrained Closure Bound")
    lines.append("")
    lines.append(
        "Diagnostic summary for compressed-CMB closure bound under explicit status/plausibility/drift filters. "
        "Interpretation is conditional on scanned families and compressed priors."
    )
    lines.append("")
    lines.append("## Filters")
    lines.append("")
    lines.append(f"- status_filter: `{filters.get('status_filter', '')}`")
    lines.append(f"- plausibility: `{filters.get('plausibility', '')}`")
    lines.append(f"- drift_filter: `{filters.get('drift_filter', '')}`")
    lines.append(f"- top_n: `{filters.get('top_n', '')}`")
    lines.append("")
    lines.append("## Counts")
    lines.append("")
    for key in (
        "n_total",
        "n_status_ok",
        "n_eligible",
        "n_plausible",
        "n_drift_positive",
        "n_candidate_pool",
        "n_incomplete",
    ):
        lines.append(f"- {key}: `{counts.get(key, 0)}`")
    lines.append("")
    lines.append("## Best")
    lines.append("")
    lines.append("| selection | params_hash | chi2_cmb | chi2_total | drift_positive | plausible_ok |")
    lines.append("|---|---|---:|---:|---:|---:|")
    for key in ("overall", "drift_positive", "drift_positive_plausible_only"):
        item = best.get(key)
        if not isinstance(item, Mapping):
            lines.append(f"| {key} | NA | NA | NA | NA | NA |")
            continue
        drift_metrics = _as_mapping(item.get("drift_metrics"))
        lines.append(
            "| "
            + key
            + " | "
            + str(item.get("params_hash", ""))
            + " | "
            + _fmt(item.get("chi2_cmb"))
            + " | "
            + _fmt(item.get("chi2_total"))
            + " | "
            + _fmt_bool(_bool_like(drift_metrics.get("positive")))
            + " | "
            + _fmt_bool(_bool_like(item.get("microphysics_plausible_ok")))
            + " |"
        )
    lines.append("")
    lines.append("## Top candidates")
    lines.append("")
    lines.append("| rank | params_hash | chi2_cmb | chi2_total | drift_positive |")
    lines.append("|---:|---|---:|---:|---:|")
    for idx, item in enumerate(top, start=1):
        if not isinstance(item, Mapping):
            continue
        drift_metrics = _as_mapping(item.get("drift_metrics"))
        lines.append(
            "| "
            + str(idx)
            + " | "
            + str(item.get("params_hash", ""))
            + " | "
            + _fmt(item.get("chi2_cmb"))
            + " | "
            + _fmt(item.get("chi2_total"))
            + " | "
            + _fmt_bool(_bool_like(drift_metrics.get("positive")))
            + " |"
        )
    return "\n".join(lines)


def _build_tex(payload: Mapping[str, Any]) -> str:
    best = _as_mapping(payload.get("best"))
    lines: List[str] = []
    lines.append("% Auto-generated by phase2_e2_closure_bound_report.py")
    lines.append("\\begin{tabular}{lllll}")
    lines.append("\\hline")
    lines.append("selection & params\\_hash & chi2\\_cmb & chi2\\_total & drift\\_positive \\\\")
    lines.append("\\hline")
    for key in ("overall", "drift_positive", "drift_positive_plausible_only"):
        item = best.get(key)
        key_tex = key.replace("_", "\\_")
        if not isinstance(item, Mapping):
            lines.append(key_tex + " & NA & NA & NA & NA \\\\")
            continue
        drift_metrics = _as_mapping(item.get("drift_metrics"))
        lines.append(
            key_tex
            + " & "
            + str(item.get("params_hash", "")).replace("_", "\\_")
            + " & "
            + _fmt(item.get("chi2_cmb"))
            + " & "
            + _fmt(item.get("chi2_total"))
            + " & "
            + _fmt_bool(_bool_like(drift_metrics.get("positive")))
            + " \\\\"
        )
    lines.append("\\hline")
    lines.append("\\end{tabular}")
    lines.append("")
    lines.append(
        "Bound values are conditional on scanned deformation families/parameter ranges and compressed-CMB priors."
    )
    return "\n".join(lines)


def _inputs_digest(entries: Sequence[InputEntry]) -> str:
    payload = [
        {
            "path": str(entry.path),
            "sha256": str(entry.sha256),
            "bytes": int(entry.bytes),
            "n_lines": int(entry.n_lines),
        }
        for entry in sorted(entries, key=lambda x: str(x.path))
    ]
    return _sha256_bytes(_canonical_json({"entries": payload}).encode("utf-8"))


def _run(
    *,
    records: Sequence[Record],
    input_entries: Sequence[InputEntry],
    status_filter: str,
    plausibility: str,
    drift_filter: str,
    top_n: int,
    created_utc: str,
) -> Dict[str, Any]:
    status_counts: Dict[str, int] = {}
    n_status_ok = 0
    for rec in records:
        label = _status_bucket(rec)
        status_counts[label] = int(status_counts.get(label, 0)) + 1
        if rec.status_ok:
            n_status_ok += 1

    eligible: List[Record] = [rec for rec in records if _eligible(rec, status_filter=status_filter, plausibility=plausibility)]
    drift_positive_pool: List[Record] = [rec for rec in eligible if rec.drift_positive is True]
    plausible_present_any = any(rec.plausible_present for rec in records)
    plausible_pool = [rec for rec in eligible if rec.plausible_ok]

    candidate_pool = list(eligible)
    if str(drift_filter) == "drift_positive_only":
        candidate_pool = drift_positive_pool

    candidate_sorted = sorted(candidate_pool, key=_sort_key)[: int(top_n)]
    best_overall = _best(eligible)
    best_drift = _best(drift_positive_pool)
    best_drift_plausible = None
    if str(plausibility) == "any" and plausible_present_any:
        best_drift_plausible = _best([rec for rec in drift_positive_pool if rec.plausible_ok])

    n_incomplete = len(records) - len(eligible)
    warnings: List[str] = []
    n_legacy_plausible = sum(1 for rec in records if not rec.plausible_present)
    if n_legacy_plausible > 0:
        warnings.append(
            f"{n_legacy_plausible} record(s) missing microphysics_plausible_ok treated as plausible (legacy back-compat)"
        )

    payload: Dict[str, Any] = {
        "schema": SCHEMA_ID,
        "generated_utc": str(created_utc),
        "input_sha256": _inputs_digest(input_entries),
        "inputs": [
            {
                "path": str(entry.path),
                "sha256": str(entry.sha256),
                "bytes": int(entry.bytes),
                "n_lines": int(entry.n_lines),
            }
            for entry in sorted(input_entries, key=lambda x: str(x.path))
        ],
        "filters": {
            "status_filter": str(status_filter),
            "plausibility": str(plausibility),
            "drift_filter": str(drift_filter),
            "top_n": int(top_n),
        },
        "counts": {
            "n_total": int(len(records)),
            "n_status_ok": int(n_status_ok),
            "n_eligible": int(len(eligible)),
            "n_plausible": int(len(plausible_pool)),
            "n_drift_positive": int(len(drift_positive_pool)),
            "n_candidate_pool": int(len(candidate_pool)),
            "n_incomplete": int(n_incomplete),
            "status_counts": {str(k): int(status_counts[k]) for k in sorted(status_counts.keys())},
        },
        "best": {
            "overall": _summary_entry(best_overall),
            "drift_positive": _summary_entry(best_drift),
            "drift_positive_plausible_only": _summary_entry(best_drift_plausible),
        },
        "top_candidates": [_summary_entry(rec) for rec in candidate_sorted],
        "warnings": list(warnings),
    }
    return payload


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="phase2_e2_closure_bound_report",
        description="Compute deterministic drift-constrained compressed-CMB closure bound diagnostics (stdlib-only).",
    )
    ap.add_argument("--in-jsonl", action="append", type=Path, default=[], help="Input scan JSONL path (repeatable).")
    ap.add_argument("--bundle", action="append", type=Path, default=[], help="Optional input bundle path (repeatable).")
    ap.add_argument("--out-dir", required=True, type=Path, help="Output directory.")
    ap.add_argument("--status-filter", choices=["ok_only", "any_eligible"], default="ok_only")
    ap.add_argument("--plausibility", choices=["any", "plausible_only"], default="any")
    ap.add_argument("--drift-filter", choices=["any", "drift_positive_only"], default="drift_positive_only")
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument(
        "--created-utc",
        type=str,
        default=DEFAULT_CREATED_UTC,
        help="Deterministic timestamp value embedded in report outputs (default fixed).",
    )
    args = ap.parse_args(argv)

    if not args.in_jsonl and not args.bundle:
        raise SystemExit("Provide at least one input via --in-jsonl and/or --bundle")
    if int(args.top_n) <= 0:
        raise SystemExit("--top-n must be > 0")

    created_utc = _normalize_created_utc(args.created_utc)
    out_dir = args.out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_records: List[RawRecord] = []
    entries: List[InputEntry] = []

    for path in sorted(args.in_jsonl, key=lambda p: str(p)):
        parsed, entry = _load_jsonl_path(path)
        raw_records.extend(parsed)
        entries.append(entry)

    for path in sorted(args.bundle, key=lambda p: str(p)):
        parsed, bundle_entries = _load_bundle_path(path)
        raw_records.extend(parsed)
        entries.extend(bundle_entries)

    if not raw_records:
        raise SystemExit("No JSON records loaded from inputs")

    records = [_normalize_record(raw) for raw in raw_records]
    payload = _run(
        records=records,
        input_entries=sorted(entries, key=lambda x: str(x.path)),
        status_filter=str(args.status_filter),
        plausibility=str(args.plausibility),
        drift_filter=str(args.drift_filter),
        top_n=int(args.top_n),
        created_utc=str(created_utc),
    )

    json_path = out_dir / "phase2_e2_closure_bound_report.json"
    md_path = out_dir / "phase2_e2_closure_bound_report.md"
    tex_path = out_dir / "phase2_e2_closure_bound_report.tex"
    csv_path = out_dir / "phase2_e2_closure_bound_candidates.csv"

    _write_json(json_path, payload)
    _write_text(md_path, _build_markdown(payload))
    _write_text(tex_path, _build_tex(payload))

    top_candidates = payload.get("top_candidates")
    csv_rows: List[Mapping[str, Any]] = []
    if isinstance(top_candidates, Sequence):
        for item in top_candidates:
            if isinstance(item, Mapping):
                csv_rows.append(item)
    _write_csv(csv_path, rows=csv_rows)

    summary = {
        "schema": SCHEMA_ID,
        "out_dir": str(out_dir),
        "counts": payload.get("counts", {}),
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Deterministic stdlib Phase-2 E2 drift-comparison report tool.

Builds a compact Sandage-Loeb drift table for selected redshifts:
- LCDM baseline (Planck-like defaults)
- best eligible Phase-2 E2 candidate
- best eligible plausible Phase-2 E2 candidate

This tool is intentionally stdlib-only and robust to partial/legacy JSONL rows.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import glob
import gzip
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple
import zipfile


V101_DIR = Path(__file__).resolve().parents[1]
if str(V101_DIR) not in sys.path:
    sys.path.insert(0, str(V101_DIR))

from gsc.measurement_model import FlatLambdaCDMHistory, H0_to_SI, delta_v_cm_s  # noqa: E402


SCHEMA_ID = "phase2_e2_drift_table_report_v1"
SECONDS_PER_YEAR = 31557600.0
MAX_DRIFT_FIELDS = 12


@dataclass(frozen=True)
class InputFileStats:
    path: str
    bytes: int
    n_records: int
    n_invalid_lines: int


@dataclass(frozen=True)
class ParsedRecord:
    source: str
    line: int
    status: str
    chi2_total: Optional[float]
    params_hash: str
    params_hash_source: str
    plan_point_id: str
    plausible_ok: bool
    plausible_present: bool
    drift_by_z_per_year: Dict[float, float]
    drift_fields_present: List[str]
    raw: Dict[str, Any]


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


def _safe_member_path(name: str) -> bool:
    posix = PurePosixPath(str(name))
    if posix.is_absolute():
        return False
    return ".." not in posix.parts


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _normalize_status(record: Mapping[str, Any]) -> str:
    raw = record.get("status")
    if raw is None:
        return "unknown"
    text = str(raw).strip().lower()
    return text if text else "unknown"


def _extract_plausibility(record: Mapping[str, Any]) -> Tuple[bool, bool]:
    if "microphysics_plausible_ok" not in record:
        return True, False
    raw = record.get("microphysics_plausible_ok")
    if isinstance(raw, bool):
        return bool(raw), True
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        fv = _finite_float(raw)
        if fv is None:
            return True, True
        return bool(fv != 0.0), True
    text = str(raw).strip().lower()
    if text in {"1", "true", "t", "yes", "y", "ok"}:
        return True, True
    if text in {"0", "false", "f", "no", "n"}:
        return False, True
    return True, True


def _extract_params_hash(record: Mapping[str, Any], *, line_text: str) -> Tuple[str, str]:
    raw = record.get("params_hash")
    if isinstance(raw, str) and raw.strip():
        return raw.strip(), "params_hash"
    return _sha256_text(line_text.strip()), "line_fallback"


def _extract_plan_point_id(record: Mapping[str, Any]) -> str:
    raw = record.get("plan_point_id")
    if raw is None:
        return ""
    return str(raw).strip()


def _extract_chi2_component(value: Any) -> Optional[float]:
    if isinstance(value, Mapping):
        return _finite_float(value.get("chi2"))
    return _finite_float(value)


def _extract_chi2_total(record: Mapping[str, Any]) -> Optional[float]:
    for key in ("chi2_total", "chi2", "chi2_tot"):
        value = _finite_float(record.get(key))
        if value is not None:
            return value

    parts = _as_mapping(record.get("chi2_parts"))
    if not parts:
        return None

    total = 0.0
    used = False
    for value in parts.values():
        sub = _extract_chi2_component(value)
        if sub is None:
            continue
        total += float(sub)
        used = True
    return float(total) if used else None


def _collect_drift_fields(record: Mapping[str, Any]) -> List[str]:
    out: Set[str] = set()
    for key in record.keys():
        text = str(key)
        if "drift" in text.lower() or "dv" in text.lower():
            out.add(text)
    drift_obj = _as_mapping(record.get("drift"))
    for key in drift_obj.keys():
        out.add(f"drift.{str(key)}")
    return sorted(out)


def _candidate_z_from_key(key: str) -> Optional[float]:
    text = str(key).lower()
    match = re.search(r"z[_]?([0-9]+(?:_[0-9]+)?(?:\.[0-9]+)?)", text)
    if not match:
        return None
    token = match.group(1)
    token = token.replace("_", ".")
    return _finite_float(token)


def _scalar_dv_priority(key: str, *, years: float) -> Tuple[int, str]:
    text = str(key).lower()
    years_text = format(float(years), ".15g")
    if f"{years_text}yr" in text or f"{int(round(years))}yr" in text:
        return (0, text)
    if "per_yr" in text or "peryear" in text or "per-year" in text:
        return (1, text)
    if re.search(r"[0-9]+(?:\.[0-9]+)?yr", text):
        return (2, text)
    return (3, text)


def _scale_scalar_dv(value: float, key: str, *, years: float) -> float:
    text = str(key).lower()
    if "per_yr" in text or "peryear" in text or "per-year" in text:
        return float(value) * float(years)

    horizon_match = re.search(r"([0-9]+(?:\.[0-9]+)?)yr", text)
    if horizon_match:
        horizon = _finite_float(horizon_match.group(1))
        if horizon is not None and horizon > 0.0:
            return float(value) * float(years) / float(horizon)
    return float(value)


def _extract_drift_map_per_year(record: Mapping[str, Any]) -> Dict[float, float]:
    drift = _as_mapping(record.get("drift"))
    z_vals = drift.get("z")
    if not isinstance(z_vals, Sequence) or isinstance(z_vals, (str, bytes)):
        z_vals = drift.get("z_list")
    dv_vals = drift.get("dv_cm_s_per_yr")
    if not isinstance(dv_vals, Sequence) or isinstance(dv_vals, (str, bytes)):
        dv_vals = drift.get("dv_per_yr")

    out: Dict[float, float] = {}
    if (
        isinstance(z_vals, Sequence)
        and not isinstance(z_vals, (str, bytes))
        and isinstance(dv_vals, Sequence)
        and not isinstance(dv_vals, (str, bytes))
        and len(z_vals) == len(dv_vals)
    ):
        for raw_z, raw_v in zip(z_vals, dv_vals):
            z = _finite_float(raw_z)
            v = _finite_float(raw_v)
            if z is None or v is None:
                continue
            out[float(z)] = float(v)

    return out


def _extract_dv_at_years(record: ParsedRecord, *, z: float, years: float) -> Optional[float]:
    for key in sorted(record.drift_by_z_per_year.keys()):
        if abs(float(key) - float(z)) <= 1e-9:
            return float(record.drift_by_z_per_year[key]) * float(years)

    # Last fallback: inspect scalar keys from raw payload directly.
    scalar_candidates: List[Tuple[Tuple[int, str], float]] = []
    for mapping in (record.raw, _as_mapping(record.raw.get("drift"))):
        for raw_key, raw_val in mapping.items():
            key = str(raw_key)
            lv = key.lower()
            if "dv" not in lv and "delta_v" not in lv:
                continue
            candidate_z = _candidate_z_from_key(lv)
            value = _finite_float(raw_val)
            if candidate_z is None or value is None:
                continue
            if abs(float(candidate_z) - float(z)) > 1e-9:
                continue
            scalar_candidates.append((_scalar_dv_priority(key, years=years), _scale_scalar_dv(float(value), key, years=years)))

    if not scalar_candidates:
        return None
    scalar_candidates.sort(key=lambda item: item[0])
    return float(scalar_candidates[0][1])


def _parse_record(payload: Mapping[str, Any], *, source: str, line: int, line_text: str) -> ParsedRecord:
    obj = {str(k): payload[k] for k in payload.keys()}
    params_hash, params_hash_source = _extract_params_hash(obj, line_text=line_text)
    plausible_ok, plausible_present = _extract_plausibility(obj)
    return ParsedRecord(
        source=str(source),
        line=int(line),
        status=_normalize_status(obj),
        chi2_total=_extract_chi2_total(obj),
        params_hash=str(params_hash),
        params_hash_source=str(params_hash_source),
        plan_point_id=_extract_plan_point_id(obj),
        plausible_ok=bool(plausible_ok),
        plausible_present=bool(plausible_present),
        drift_by_z_per_year=_extract_drift_map_per_year(obj),
        drift_fields_present=_collect_drift_fields(obj),
        raw=obj,
    )


def _parse_jsonl_text(source: str, text: str, *, bytes_len: int) -> Tuple[List[ParsedRecord], InputFileStats]:
    records: List[ParsedRecord] = []
    n_invalid = 0
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except Exception:
            n_invalid += 1
            continue
        if not isinstance(payload, Mapping):
            n_invalid += 1
            continue
        records.append(_parse_record(payload, source=source, line=line_no, line_text=stripped))

    stats = InputFileStats(
        path=str(source),
        bytes=int(bytes_len),
        n_records=int(len(records)),
        n_invalid_lines=int(n_invalid),
    )
    return records, stats


def _decode_jsonl_bytes(source: str, data: bytes) -> str:
    raw = bytes(data)
    if str(source).lower().endswith(".gz"):
        try:
            raw = gzip.decompress(raw)
        except OSError as exc:
            raise ValueError(f"Invalid gzip JSONL payload: {source}") from exc
    return raw.decode("utf-8")


def _is_bundle_file(path: Path) -> bool:
    lower = path.name.lower()
    return lower.endswith(".zip") or lower.endswith(".tar") or lower.endswith(".tgz") or lower.endswith(".tar.gz")


def _member_priority(name: str) -> Tuple[int, int, str]:
    posix = PurePosixPath(str(name))
    base = posix.name.lower()
    if base in {"merged.jsonl", "merged.jsonl.gz"}:
        rank = 0
    elif "merged" in base:
        rank = 1
    else:
        rank = 2
    return (rank, len(posix.parts), str(name))


def _pick_primary_payload(payloads: Sequence[Tuple[str, bytes]]) -> Tuple[str, bytes]:
    if not payloads:
        raise FileNotFoundError("No JSONL payloads available")
    sorted_payloads = sorted(payloads, key=lambda item: _member_priority(item[0]))
    return sorted_payloads[0]


def _load_primary_from_bundle(path: Path) -> Tuple[List[ParsedRecord], List[InputFileStats]]:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Bundle path not found: {resolved}")

    if resolved.is_dir():
        candidates = sorted(
            [p for p in list(resolved.rglob("*.jsonl")) + list(resolved.rglob("*.jsonl.gz")) if p.is_file()],
            key=lambda p: _member_priority(p.as_posix()),
        )
        if not candidates:
            raise FileNotFoundError(f"No *.jsonl/.jsonl.gz found in bundle directory: {resolved}")
        selected = candidates[0]
        data = selected.read_bytes()
        source = str(selected)
        records, stats = _parse_jsonl_text(source, _decode_jsonl_bytes(source, data), bytes_len=len(data))
        return records, [stats]

    lower = resolved.name.lower()
    if lower.endswith(".zip"):
        with zipfile.ZipFile(resolved, "r") as zf:
            payloads: List[Tuple[str, bytes]] = []
            for name in sorted(zf.namelist()):
                if name.endswith("/"):
                    continue
                if not (name.lower().endswith(".jsonl") or name.lower().endswith(".jsonl.gz")):
                    continue
                if not _safe_member_path(name):
                    raise ValueError(f"Unsafe bundle member path: {name}")
                payloads.append((name, zf.read(name)))
            member, data = _pick_primary_payload(payloads)
            source = f"{resolved}!{member}"
            records, stats = _parse_jsonl_text(source, _decode_jsonl_bytes(member, data), bytes_len=len(data))
            return records, [stats]

    if lower.endswith(".tar") or lower.endswith(".tgz") or lower.endswith(".tar.gz"):
        with tarfile.open(resolved, "r:*") as tf:
            payloads = []
            members = sorted((m for m in tf.getmembers() if m.isfile()), key=lambda m: str(m.name))
            for member in members:
                name = str(member.name)
                if not (name.lower().endswith(".jsonl") or name.lower().endswith(".jsonl.gz")):
                    continue
                if not _safe_member_path(name):
                    raise ValueError(f"Unsafe bundle member path: {name}")
                fh = tf.extractfile(member)
                if fh is None:
                    continue
                payloads.append((name, fh.read()))
            member_name, data = _pick_primary_payload(payloads)
            source = f"{resolved}!{member_name}"
            records, stats = _parse_jsonl_text(
                source, _decode_jsonl_bytes(member_name, data), bytes_len=len(data)
            )
            return records, [stats]

    raise ValueError(f"Unsupported bundle path/type: {resolved}")


def _load_jsonl_path(path: Path) -> Tuple[List[ParsedRecord], List[InputFileStats]]:
    resolved = path.expanduser().resolve()
    if not resolved.exists() or not resolved.is_file():
        raise FileNotFoundError(f"Input file not found: {resolved}")
    data = resolved.read_bytes()
    records, stats = _parse_jsonl_text(
        str(resolved), _decode_jsonl_bytes(str(resolved), data), bytes_len=len(data)
    )
    return records, [stats]


def _expand_input_tokens(tokens: Sequence[str]) -> List[Path]:
    resolved: List[Path] = []
    seen: Set[Path] = set()
    for raw in tokens:
        token = str(raw).strip()
        if not token:
            continue

        expanded_any = False
        if any(ch in token for ch in "*?["):
            matches = sorted(glob.glob(token))
            for match in matches:
                candidate = Path(match).expanduser().resolve()
                if not candidate.exists():
                    continue
                if candidate.is_dir():
                    files = sorted(
                        p.resolve()
                        for p in list(candidate.glob("*.jsonl")) + list(candidate.glob("*.jsonl.gz"))
                        if p.is_file()
                    )
                    for file_path in files:
                        if file_path not in seen:
                            seen.add(file_path)
                            resolved.append(file_path)
                    expanded_any = expanded_any or bool(files)
                elif candidate.is_file():
                    if candidate not in seen:
                        seen.add(candidate)
                        resolved.append(candidate)
                    expanded_any = True
            if not expanded_any:
                raise FileNotFoundError(f"Input glob matched no paths: {token}")
            continue

        path = Path(token).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Input path not found: {token}")
        if path.is_dir():
            files = sorted(
                p.resolve() for p in list(path.glob("*.jsonl")) + list(path.glob("*.jsonl.gz")) if p.is_file()
            )
            if not files:
                raise FileNotFoundError(f"No *.jsonl/.jsonl.gz files found in directory: {path}")
            for file_path in files:
                if file_path in seen:
                    continue
                seen.add(file_path)
                resolved.append(file_path)
            continue
        if path.is_file():
            if path in seen:
                continue
            seen.add(path)
            resolved.append(path)
            continue
        raise FileNotFoundError(f"Unsupported input path type: {path}")

    return sorted(resolved, key=lambda p: str(p))


def _status_allowed(status: str, *, status_filter: str) -> bool:
    s = str(status).strip().lower()
    if status_filter == "ok_only":
        return s == "ok"
    if s == "error":
        return False
    if s.startswith("skipped"):
        return False
    return True


def _record_eligible(record: ParsedRecord, *, status_filter: str, plausible_only: bool) -> bool:
    if record.chi2_total is None:
        return False
    if not _status_allowed(record.status, status_filter=status_filter):
        return False
    if plausible_only and not bool(record.plausible_ok):
        return False
    return True


def _sort_key(record: ParsedRecord) -> Tuple[Any, ...]:
    return (
        float(record.chi2_total) if record.chi2_total is not None else float("inf"),
        str(record.params_hash),
        str(record.source),
        int(record.line),
    )


def _select_best(
    records: Sequence[ParsedRecord],
    *,
    status_filter: str,
    plausible_mode: str,
) -> Tuple[Optional[ParsedRecord], Optional[ParsedRecord], int]:
    plausible_only = str(plausibility_mode_normalized(plausible_mode)) == "plausible_only"
    eligible = [rec for rec in records if _record_eligible(rec, status_filter=status_filter, plausible_only=plausible_only)]
    eligible_sorted = sorted(eligible, key=_sort_key)
    best_overall = eligible_sorted[0] if eligible_sorted else None

    best_plausible: Optional[ParsedRecord]
    if plausible_only:
        best_plausible = best_overall
    else:
        pool = [
            rec
            for rec in records
            if _record_eligible(rec, status_filter=status_filter, plausible_only=True)
        ]
        pool_sorted = sorted(pool, key=_sort_key)
        best_plausible = pool_sorted[0] if pool_sorted else None

    return best_overall, best_plausible, len(eligible)


def plausibility_mode_normalized(mode: str) -> str:
    text = str(mode).strip().lower()
    if text in {"any", "plausible_only", "also_report_best_plausible"}:
        return text
    return "also_report_best_plausible"


def _fmt_float(value: Optional[float]) -> str:
    if value is None:
        return "NA"
    return f"{float(value):.6f}"


def _fmt_bool(value: Optional[bool]) -> str:
    if value is None:
        return "NA"
    return "true" if bool(value) else "false"


def _tex_escape(text: str) -> str:
    return (
        str(text)
        .replace("\\", "\\textbackslash{}")
        .replace("&", "\\&")
        .replace("%", "\\%")
        .replace("$", "\\$")
        .replace("#", "\\#")
        .replace("_", "\\_")
        .replace("{", "\\{")
        .replace("}", "\\}")
    )


def _parse_z_values(values: Sequence[str]) -> List[float]:
    if not values:
        return [2.0, 3.0, 4.0, 5.0]
    out: List[float] = []
    seen: Set[float] = set()
    for raw in values:
        for token in str(raw).split(","):
            text = token.strip()
            if not text:
                continue
            z = _finite_float(text)
            if z is None or z < 0.0:
                raise ValueError(f"Invalid redshift in --z: {text!r}")
            zf = float(z)
            if zf in seen:
                continue
            seen.add(zf)
            out.append(zf)
    if not out:
        raise ValueError("--z produced an empty redshift list")
    return out


def _status_counts(records: Sequence[ParsedRecord]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for rec in records:
        status = str(rec.status)
        out[status] = int(out.get(status, 0) + 1)
    return {str(k): int(out[k]) for k in sorted(out.keys())}


def _status_counts_sorted_lines(counts: Mapping[str, int]) -> List[Tuple[str, int]]:
    return sorted(
        ((str(k), int(v)) for k, v in counts.items()),
        key=lambda item: (-int(item[1]), str(item[0])),
    )


def _record_summary(record: Optional[ParsedRecord]) -> Optional[Dict[str, Any]]:
    if record is None:
        return None
    return {
        "chi2_total": float(record.chi2_total) if record.chi2_total is not None else None,
        "microphysics_plausible_ok": bool(record.plausible_ok),
        "params_hash": str(record.params_hash),
        "params_hash_source": str(record.params_hash_source),
        "plan_point_id": str(record.plan_point_id) if record.plan_point_id else None,
        "source": str(record.source),
        "status": str(record.status),
    }


def _build_payload(
    *,
    records: Sequence[ParsedRecord],
    input_tokens: Sequence[str],
    input_stats: Sequence[InputFileStats],
    years: float,
    z_points: Sequence[float],
    status_filter: str,
    plausibility_mode: str,
    lcdm_h0: float,
    lcdm_omega_m: float,
    lcdm_omega_l: float,
) -> Dict[str, Any]:
    mode = plausibility_mode_normalized(plausibility_mode)

    best_overall, best_plausible, n_eligible = _select_best(
        records,
        status_filter=status_filter,
        plausible_mode=mode,
    )

    n_missing_chi2 = int(sum(1 for rec in records if rec.chi2_total is None))
    status_counts = _status_counts(records)
    drift_fields = sorted({field for rec in records for field in rec.drift_fields_present})

    h0_si = H0_to_SI(float(lcdm_h0))
    lcdm = FlatLambdaCDMHistory(H0=h0_si, Omega_m=float(lcdm_omega_m), Omega_Lambda=float(lcdm_omega_l))

    table_rows: List[Dict[str, Any]] = []
    has_any_overall = False
    has_any_plausible = False
    for z in z_points:
        dv_lcdm = float(delta_v_cm_s(z=float(z), years=float(years), H0=h0_si, H_of_z=lcdm.H))
        dv_best = _extract_dv_at_years(best_overall, z=float(z), years=float(years)) if best_overall else None
        dv_best_plausible = (
            _extract_dv_at_years(best_plausible, z=float(z), years=float(years)) if best_plausible else None
        )
        has_any_overall = has_any_overall or (dv_best is not None)
        has_any_plausible = has_any_plausible or (dv_best_plausible is not None)
        table_rows.append(
            {
                "z": float(z),
                "dv_best_cm_s": dv_best,
                "dv_best_plausible_cm_s": dv_best_plausible,
                "dv_lcdm_cm_s": dv_lcdm,
            }
        )

    total_bytes = int(sum(int(row.bytes) for row in input_stats))
    total_invalid = int(sum(int(row.n_invalid_lines) for row in input_stats))
    total_parsed = int(sum(int(row.n_records) for row in input_stats))

    notes: List[str] = []
    if not has_any_overall:
        notes.append("candidate drift metrics missing for best eligible record; table shows NA for candidate columns")
    if not has_any_plausible:
        notes.append("candidate drift metrics missing for best plausible record; table shows NA for plausible column")
    if not notes:
        notes.append("drift values sourced from existing JSONL drift metrics; no physics model recomputation applied")

    payload: Dict[str, Any] = {
        "schema": SCHEMA_ID,
        "filters": {
            "eligible_status": str(status_filter),
            "plausibility_mode": str(mode),
        },
        "header": {
            "n_eligible": int(n_eligible),
            "n_files_expanded": int(len(input_stats)),
            "n_inputs": int(len(input_tokens)),
            "n_invalid_lines": int(total_invalid),
            "n_missing_chi2": int(n_missing_chi2),
            "n_records_parsed": int(total_parsed),
            "total_bytes": int(total_bytes),
        },
        "input_files": [
            {
                "bytes": int(row.bytes),
                "n_invalid_lines": int(row.n_invalid_lines),
                "n_records": int(row.n_records),
                "path": str(row.path),
            }
            for row in sorted(input_stats, key=lambda r: str(r.path))
        ],
        "status_counts": {str(k): int(status_counts[k]) for k in sorted(status_counts.keys())},
        "baseline": {
            "years": float(years),
            "z_points": [float(z) for z in z_points],
            "lcdm": {
                "H0_km_s_Mpc": float(lcdm_h0),
                "Omega_L": float(lcdm_omega_l),
                "Omega_m": float(lcdm_omega_m),
            },
        },
        "best_eligible_overall": _record_summary(best_overall),
        "best_eligible_plausible": _record_summary(best_plausible),
        "candidate_drift_available_overall": bool(has_any_overall),
        "candidate_drift_available_plausible": bool(has_any_plausible),
        "drift_fields_present": [str(field) for field in drift_fields[:MAX_DRIFT_FIELDS]],
        "drift_fields_truncated": int(max(0, len(drift_fields) - MAX_DRIFT_FIELDS)),
        "drift_table": table_rows,
        "notes": notes,
    }
    return payload


def _render_text(payload: Mapping[str, Any]) -> str:
    header = _as_mapping(payload.get("header"))
    status_counts = _as_mapping(payload.get("status_counts"))
    best_overall = _as_mapping(payload.get("best_eligible_overall"))
    best_plausible = _as_mapping(payload.get("best_eligible_plausible"))
    rows = payload.get("drift_table")

    lines: List[str] = []
    lines.append("Inputs:")
    lines.append(f"n_inputs={int(header.get('n_inputs', 0))}")
    lines.append(f"n_files_expanded={int(header.get('n_files_expanded', 0))}")
    lines.append(f"n_records_parsed={int(header.get('n_records_parsed', 0))}")
    lines.append(f"n_invalid_lines={int(header.get('n_invalid_lines', 0))}")
    lines.append(f"n_missing_chi2={int(header.get('n_missing_chi2', 0))}")
    lines.append("")

    lines.append("Status counts:")
    for status, count in _status_counts_sorted_lines(status_counts):
        lines.append(f"status={status} count={count}")
    lines.append("")

    lines.append("Best eligible:")
    if best_overall:
        lines.append(
            "overall chi2_total={chi2} status={status} params_hash={params_hash} plan_point_id={plan_point_id} plausible={plausible}".format(
                chi2=_fmt_float(_finite_float(best_overall.get("chi2_total"))),
                status=str(best_overall.get("status", "NA")),
                params_hash=str(best_overall.get("params_hash", "NA")),
                plan_point_id=str(best_overall.get("plan_point_id") or "-"),
                plausible=_fmt_bool(bool(best_overall.get("microphysics_plausible_ok", True))),
            )
        )
    else:
        lines.append("overall=NONE")

    if best_plausible:
        lines.append(
            "plausible chi2_total={chi2} status={status} params_hash={params_hash} plan_point_id={plan_point_id} plausible={plausible}".format(
                chi2=_fmt_float(_finite_float(best_plausible.get("chi2_total"))),
                status=str(best_plausible.get("status", "NA")),
                params_hash=str(best_plausible.get("params_hash", "NA")),
                plan_point_id=str(best_plausible.get("plan_point_id") or "-"),
                plausible=_fmt_bool(bool(best_plausible.get("microphysics_plausible_ok", True))),
            )
        )
    else:
        lines.append("plausible=NONE")
    lines.append("")

    lines.append("Drift table:")
    lines.append("z dv_lcdm_cm_s dv_best_cm_s dv_best_plausible_cm_s")
    if isinstance(rows, Sequence):
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            lines.append(
                "{z:.6f} {lcdm} {best} {best_plausible}".format(
                    z=float(row.get("z", 0.0)),
                    lcdm=_fmt_float(_finite_float(row.get("dv_lcdm_cm_s"))),
                    best=_fmt_float(_finite_float(row.get("dv_best_cm_s"))),
                    best_plausible=_fmt_float(_finite_float(row.get("dv_best_plausible_cm_s"))),
                )
            )
    lines.append("")

    lines.append("Notes:")
    for note in payload.get("notes") or []:
        lines.append(f"- {str(note)}")
    return "\n".join(lines)


def _render_md(payload: Mapping[str, Any]) -> str:
    baseline = _as_mapping(payload.get("baseline"))
    lcdm = _as_mapping(baseline.get("lcdm"))
    rows = payload.get("drift_table")
    best_overall = _as_mapping(payload.get("best_eligible_overall"))
    best_plausible = _as_mapping(payload.get("best_eligible_plausible"))

    lines: List[str] = []
    lines.append("# Phase-2 E2 Drift Comparison")
    lines.append("")
    lines.append("Illustrative Sandage-Loeb velocity drift (Delta v) comparison at selected redshifts: LCDM baseline vs best Phase-2 E2 candidate(s).")
    lines.append("")
    lines.append(
        "- baseline LCDM: `H0={h0}`, `Omega_m={om}`, `Omega_L={ol}`; years=`{years}`".format(
            h0=_fmt_float(_finite_float(lcdm.get("H0_km_s_Mpc"))),
            om=_fmt_float(_finite_float(lcdm.get("Omega_m"))),
            ol=_fmt_float(_finite_float(lcdm.get("Omega_L"))),
            years=_fmt_float(_finite_float(baseline.get("years"))),
        )
    )
    lines.append(
        "- best overall: `params_hash={ph}`, `chi2_total={chi2}`".format(
            ph=str(best_overall.get("params_hash") or "NONE"),
            chi2=_fmt_float(_finite_float(best_overall.get("chi2_total"))),
        )
    )
    lines.append(
        "- best plausible: `params_hash={ph}`, `chi2_total={chi2}`".format(
            ph=str(best_plausible.get("params_hash") or "NONE"),
            chi2=_fmt_float(_finite_float(best_plausible.get("chi2_total"))),
        )
    )
    lines.append("")
    lines.append("| z | dv_lcdm_cm_s | dv_best_cm_s | dv_best_plausible_cm_s |")
    lines.append("|---:|---:|---:|---:|")
    if isinstance(rows, Sequence):
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            lines.append(
                "| {z} | {lcdm} | {best} | {best_plausible} |".format(
                    z=_fmt_float(_finite_float(row.get("z"))),
                    lcdm=_fmt_float(_finite_float(row.get("dv_lcdm_cm_s"))),
                    best=_fmt_float(_finite_float(row.get("dv_best_cm_s"))),
                    best_plausible=_fmt_float(_finite_float(row.get("dv_best_plausible_cm_s"))),
                )
            )
    lines.append("")
    lines.append("Compressed-priors diagnostic only: this table summarizes pipeline outputs and does not by itself imply early-time closure.")
    return "\n".join(lines)


def _render_tex(payload: Mapping[str, Any]) -> str:
    rows = payload.get("drift_table")
    lines: List[str] = []
    lines.append("% Auto-generated by phase2_e2_drift_table_report.py")
    lines.append("\\paragraph{Phase-2 E2 Drift Comparison}")
    lines.append(
        "Illustrative Sandage--Loeb velocity drift ($\\Delta v$) comparison at selected redshifts: "
        "$\\Lambda$CDM baseline vs best Phase-2 E2 candidate(s)."
    )
    lines.append("\\begin{tabular}{rrrr}")
    lines.append("\\hline")
    lines.append(
        "$z$ & $\\\\Delta v_{\\\\Lambda\\\\mathrm{CDM}}$ [cm/s] & $\\\\Delta v_{\\\\mathrm{best}}$ [cm/s] & "
        "$\\\\Delta v_{\\\\mathrm{best,plausible}}$ [cm/s] \\\\\\\\"
    )
    lines.append("\\hline")
    if isinstance(rows, Sequence):
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            lines.append(
                "{z} & {lcdm} & {best} & {best_plausible} \\\\".format(
                    z=_tex_escape(_fmt_float(_finite_float(row.get("z")))),
                    lcdm=_tex_escape(_fmt_float(_finite_float(row.get("dv_lcdm_cm_s")))),
                    best=_tex_escape(_fmt_float(_finite_float(row.get("dv_best_cm_s")))),
                    best_plausible=_tex_escape(_fmt_float(_finite_float(row.get("dv_best_plausible_cm_s")))),
                )
            )
    lines.append("\\hline")
    lines.append("\\end{tabular}")
    lines.append("\\par\\smallskip")
    lines.append("\\textit{Compressed-priors diagnostic only; candidate columns show N/A when drift metrics are unavailable in the selected record(s).}")
    return "\n".join(lines)


def _load_all_records(
    *,
    input_paths: Sequence[Path],
    bundle_paths: Sequence[Path],
) -> Tuple[List[ParsedRecord], List[InputFileStats]]:
    all_records: List[ParsedRecord] = []
    all_stats: List[InputFileStats] = []

    for path in sorted(input_paths, key=lambda p: str(p)):
        records, stats = _load_jsonl_path(path)
        all_records.extend(records)
        all_stats.extend(stats)

    for path in sorted(bundle_paths, key=lambda p: str(p)):
        records, stats = _load_primary_from_bundle(path)
        all_records.extend(records)
        all_stats.extend(stats)

    return all_records, all_stats


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="phase2_e2_drift_table_report",
        description="Deterministic stdlib drift-comparison table for Phase-2 E2 JSONL/bundles.",
    )
    ap.add_argument("--input", action="append", default=[], help="Input JSONL file/dir/glob (repeatable).")
    ap.add_argument("--bundle", action="append", type=Path, default=[], help="Optional bundle path (dir/zip/tar/tgz; repeatable).")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--json-out", type=Path, default=None)
    ap.add_argument("--years", type=float, default=10.0)
    ap.add_argument("--z", action="append", default=[], help="Redshift value(s); repeat or comma-separate.")
    ap.add_argument("--eligible-status", choices=["ok_only", "any_eligible"], default="ok_only")
    ap.add_argument(
        "--plausibility-mode",
        choices=["any", "plausible_only", "also_report_best_plausible"],
        default="also_report_best_plausible",
    )
    ap.add_argument("--emit-tex", type=Path, default=None)
    ap.add_argument("--emit-md", type=Path, default=None)
    ap.add_argument("--lcdm-H0", type=float, default=67.4)
    ap.add_argument("--lcdm-Omega-m", type=float, default=0.315)
    ap.add_argument("--lcdm-Omega-L", type=float, default=0.685)
    args = ap.parse_args(argv)

    try:
        if not args.input and not args.bundle:
            raise FileNotFoundError("Provide at least one --input and/or --bundle")
        if not math.isfinite(float(args.years)) or float(args.years) <= 0.0:
            raise ValueError("--years must be finite and > 0")

        for key, value in (
            ("--lcdm-H0", args.lcdm_H0),
            ("--lcdm-Omega-m", args.lcdm_Omega_m),
            ("--lcdm-Omega-L", args.lcdm_Omega_L),
        ):
            if not math.isfinite(float(value)):
                raise ValueError(f"{key} must be finite")

        z_points = _parse_z_values(args.z)
        input_paths = _expand_input_tokens(list(args.input))
        bundle_paths = [Path(p).expanduser().resolve() for p in list(args.bundle)]

        records, input_stats = _load_all_records(input_paths=input_paths, bundle_paths=bundle_paths)

        payload = _build_payload(
            records=records,
            input_tokens=list(args.input) + [str(p) for p in bundle_paths],
            input_stats=input_stats,
            years=float(args.years),
            z_points=z_points,
            status_filter=str(args.eligible_status),
            plausibility_mode=str(args.plausibility_mode),
            lcdm_h0=float(args.lcdm_H0),
            lcdm_omega_m=float(args.lcdm_Omega_m),
            lcdm_omega_l=float(args.lcdm_Omega_L),
        )

        json_text = json.dumps(payload, indent=2, sort_keys=True)
        if args.json_out is not None:
            out_path = Path(args.json_out).expanduser().resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json_text + "\n", encoding="utf-8")

        md_text = _render_md(payload)
        tex_text = _render_tex(payload)
        if args.emit_md is not None:
            out_path = Path(args.emit_md).expanduser().resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(md_text + "\n", encoding="utf-8")
        if args.emit_tex is not None:
            out_path = Path(args.emit_tex).expanduser().resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(tex_text + "\n", encoding="utf-8")

        if str(args.format) == "json":
            sys.stdout.write(json_text + "\n")
        else:
            sys.stdout.write(_render_text(payload) + "\n")
        return 0
    except (FileNotFoundError, ValueError) as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

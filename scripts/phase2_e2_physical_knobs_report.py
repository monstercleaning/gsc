#!/usr/bin/env python3
"""Deterministic stdlib E2 closure -> physical knobs diagnostic report."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import gzip
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import sys
import tarfile
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
import zipfile


V101_DIR = Path(__file__).resolve().parents[1]
if str(V101_DIR) not in sys.path:
    sys.path.insert(0, str(V101_DIR))

from gsc.early_time.cmb_microphysics_knobs import KNOB_SPECS, iter_knob_specs_sorted  # noqa: E402


SCHEMA_ID = "phase2_e2_physical_knobs_report_v1"


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
class ReportRecord:
    source: str
    line: int
    params_hash: str
    params_hash_source: str
    status: str
    status_ok: bool
    chi2_cmb: Optional[float]
    chi2_total: Optional[float]
    chi2_parts: Dict[str, float]
    drift_precheck_ok: Optional[bool]
    drift_metric: Optional[float]
    drift_sign_z3: Optional[bool]
    plausible_ok: bool
    plausible_present: bool
    microphysics_penalty: float
    microphysics_max_rel_dev: float
    params: Dict[str, Any]
    cosmo_knobs: Dict[str, float]
    micro_knobs: Dict[str, float]


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


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


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
        f = _finite_float(value)
        if f is None:
            return None
        if f == 1.0:
            return True
        if f == 0.0:
            return False
        return f > 0.0
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
    f = _finite_float(value)
    if f is not None:
        return f
    return str(value)


def _safe_member_path(name: str) -> bool:
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
                if not _safe_member_path(name):
                    raise SystemExit(f"Unsafe bundle member path: {name}")
                payloads.append((name, zf.read(name)))
        return payloads

    if suffix in {".tar", ".tgz", ".gz"} or str(resolved).lower().endswith(".tar.gz"):
        payloads = []
        with tarfile.open(resolved, "r:*") as tf:
            members = sorted((m for m in tf.getmembers() if m.isfile()), key=lambda m: str(m.name))
            for member in members:
                name = str(member.name)
                if not (name.lower().endswith(".jsonl") or name.lower().endswith(".jsonl.gz")):
                    continue
                if not _safe_member_path(name):
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


def _toy_records() -> Tuple[List[RawRecord], List[InputEntry]]:
    rows = [
        {
            "params_hash": "toy_a",
            "status": "ok",
            "chi2_cmb": 2.1,
            "chi2_total": 9.4,
            "drift_precheck_ok": True,
            "drift_metric": 0.35,
            "drift_sign_z3": True,
            "microphysics_plausible_ok": True,
            "microphysics_penalty": 0.0,
            "microphysics_max_rel_dev": 0.01,
            "params": {"omega_b_h2": 0.02235, "omega_c_h2": 0.1201, "N_eff": 3.046, "H0": 67.4, "Omega_m": 0.315},
            "microphysics_knobs": {"z_star_scale": 1.0, "r_s_scale": 1.02, "r_d_scale": 1.0},
        },
        {
            "params_hash": "toy_b",
            "status": "ok",
            "chi2_parts": {"cmb_priors": {"chi2": 2.8}, "sn": {"chi2": 6.9}},
            "drift_precheck_ok": True,
            "drift_metric": 0.29,
            "drift_sign_z3": True,
            "microphysics_plausible_ok": False,
            "microphysics_penalty": 1.4,
            "microphysics_max_rel_dev": 0.08,
            "params": {"omega_b_h2": 0.02210, "omega_c_h2": 0.1215, "N_eff": 3.25, "H0": 68.1, "Omega_m": 0.305},
            "microphysics_knobs": {"z_star_scale": 1.03, "r_s_scale": 1.08, "r_d_scale": 0.96},
        },
        {
            "params_hash": "toy_c",
            "status": "skipped_drift",
            "chi2_cmb": 1.0e99,
            "chi2_total": 1.0e99,
            "drift_precheck_ok": False,
            "drift_metric": -0.12,
            "drift_sign_z3": False,
            "microphysics_plausible_ok": True,
            "params": {"omega_b_h2": 0.0224, "omega_c_h2": 0.1199, "N_eff": 3.0, "H0": 66.9, "Omega_m": 0.322},
            "microphysics_knobs": {"z_star_scale": 0.98, "r_s_scale": 0.93, "r_d_scale": 0.92},
        },
        {
            "params_hash": "toy_d",
            "status": "error",
            "error": "toy_failure",
            "drift_precheck_ok": True,
            "drift_metric": 0.1,
            "params": {"omega_b_h2": 0.0222, "omega_c_h2": 0.1204, "N_eff": 3.10, "H0": 67.0, "Omega_m": 0.318},
            "microphysics_knobs": {"z_star_scale": 1.01, "r_s_scale": 1.01, "r_d_scale": 1.01},
        },
        {
            "status": "ok",
            "chi2_cmb": 2.3,
            "chi2_total": 8.9,
            "drift_metric": 0.41,
            "params": {"omega_b_h2": 0.0223, "omega_c_h2": 0.1197, "N_eff": 3.12, "H0": 67.6, "Omega_m": 0.311},
            "microphysics_knobs": {"z_star_scale": 1.01, "r_s_scale": 1.04, "r_d_scale": 1.00},
        },
    ]
    text = "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)
    parsed, n_lines = _parse_jsonl_text("<toy>", text)
    entry = InputEntry(path="<toy>", sha256=_sha256_bytes(text.encode("utf-8")), bytes=len(text.encode("utf-8")), n_lines=n_lines)
    return parsed, [entry]


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


def _extract_params_hash(obj: Mapping[str, Any]) -> Tuple[str, str]:
    raw = obj.get("params_hash")
    if isinstance(raw, str) and raw.strip():
        return raw.strip(), "params_hash"

    params = _as_mapping(obj.get("params"))
    if params:
        canonical = _canonical_json({str(k): _to_json_safe(params[k]) for k in sorted(params.keys(), key=lambda x: str(x))})
        return _sha256_bytes(canonical.encode("utf-8")), "params_fallback"

    canonical = _canonical_json({str(k): _to_json_safe(obj[k]) for k in sorted(obj.keys(), key=lambda x: str(x))})
    return _sha256_bytes(canonical.encode("utf-8")), "record_fallback"


def _extract_drift_metric(obj: Mapping[str, Any]) -> Optional[float]:
    direct = _finite_float(obj.get("drift_metric"))
    if direct is not None:
        return direct
    nested_candidates = [
        ("drift_metrics", "metric"),
        ("drift", "metric"),
        ("drift_metrics", "min_zdot_z2_5"),
        ("drift", "min_z_dot"),
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
        value = _finite_float(cur)
        if value is not None:
            return value
    return None


def _extract_drift_sign_z3(obj: Mapping[str, Any]) -> Optional[bool]:
    for key in ("drift_sign_z3", "drift_ok_z3"):
        if key in obj:
            value = _bool_like(obj.get(key))
            if value is not None:
                return bool(value)

    nested_candidates = [
        ("drift_metrics", "sign_ok_z3"),
        ("drift_metrics", "ok_z3"),
        ("drift", "sign_ok_z3"),
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
            return bool(value)

    drift = _as_mapping(obj.get("drift"))
    z_list = drift.get("z_list")
    z_dot = drift.get("z_dot")
    if isinstance(z_list, Sequence) and isinstance(z_dot, Sequence):
        for idx, z in enumerate(z_list):
            fz = _finite_float(z)
            if fz is None:
                continue
            if abs(float(fz) - 3.0) > 1e-9:
                continue
            if idx >= len(z_dot):
                continue
            fzd = _finite_float(z_dot[idx])
            if fzd is None:
                return None
            return bool(float(fzd) > 0.0)

    return None


def _extract_plausibility(obj: Mapping[str, Any]) -> Tuple[bool, bool]:
    if "microphysics_plausible_ok" not in obj:
        return True, False
    value = _bool_like(obj.get("microphysics_plausible_ok"))
    return (True if value is None else bool(value)), True


def _extract_numeric_map(value: Any) -> Dict[str, float]:
    if not isinstance(value, Mapping):
        return {}
    out: Dict[str, float] = {}
    for key in sorted(value.keys(), key=lambda x: str(x)):
        fv = _finite_float(value[key])
        if fv is None:
            continue
        out[str(key)] = float(fv)
    return out


def _extract_cosmo_knobs(obj: Mapping[str, Any]) -> Dict[str, float]:
    params = _extract_numeric_map(obj.get("params"))
    cosmo = _extract_numeric_map(obj.get("cosmo_params"))
    top = _extract_numeric_map(obj)

    def pick(*aliases: str) -> Optional[float]:
        for key in aliases:
            if key in params:
                return float(params[key])
            if key in cosmo:
                return float(cosmo[key])
            if key in top:
                return float(top[key])
        return None

    out: Dict[str, float] = {}
    alias_map = {
        "omega_b_h2": ("omega_b_h2", "ombh2", "Omega_b_h2", "omega_b"),
        "omega_c_h2": ("omega_c_h2", "omch2", "Omega_c_h2", "omega_c"),
        "N_eff": ("N_eff", "Neff", "n_eff"),
        "Y_p": ("Y_p", "Yp", "y_p"),
        "H0": ("H0", "h0"),
        "Omega_m": ("Omega_m", "omega_m", "Om0"),
    }
    for canonical in ("omega_b_h2", "omega_c_h2", "N_eff", "Y_p", "H0", "Omega_m"):
        value = pick(*alias_map[canonical])
        if value is not None:
            out[canonical] = float(value)
    return out


def _extract_micro_knobs(obj: Mapping[str, Any]) -> Dict[str, float]:
    known = tuple(spec.name for spec in iter_knob_specs_sorted())
    out: Dict[str, float] = {}

    for key in ("microphysics_knobs", "cmb_microphysics_knobs", "microphysics", "micro"):
        mapping = _extract_numeric_map(obj.get(key))
        if not mapping:
            continue
        for name in known:
            if name in mapping and name not in out:
                out[name] = float(mapping[name])

    params = _extract_numeric_map(obj.get("params"))
    top = _extract_numeric_map(obj)
    for name in known:
        if name in out:
            continue
        if name in params:
            out[name] = float(params[name])
            continue
        if name in top:
            out[name] = float(top[name])

    return {name: out[name] for name in known if name in out}


def _normalize_record(raw: RawRecord) -> ReportRecord:
    obj = raw.obj
    status_text = str(obj.get("status", "")).strip().lower()
    status = status_text if status_text else "ok"
    status_ok = (not status_text) or status == "ok"

    params_hash, params_hash_source = _extract_params_hash(obj)
    chi2_parts = _extract_chi2_parts(obj)
    chi2_cmb = _extract_chi2_cmb(obj, chi2_parts=chi2_parts)
    chi2_total = _extract_chi2_total(obj, chi2_parts=chi2_parts)

    drift_precheck_ok = _bool_like(obj.get("drift_precheck_ok"))
    drift_metric = _extract_drift_metric(obj)
    drift_sign_z3 = _extract_drift_sign_z3(obj)

    plausible_ok, plausible_present = _extract_plausibility(obj)
    microphysics_penalty = _finite_float(obj.get("microphysics_penalty"))
    if microphysics_penalty is None:
        microphysics_penalty = 0.0
    microphysics_max_rel_dev = _finite_float(obj.get("microphysics_max_rel_dev"))
    if microphysics_max_rel_dev is None:
        microphysics_max_rel_dev = 0.0

    params_raw = _as_mapping(obj.get("params"))
    params = {str(k): _to_json_safe(v) for k, v in sorted(params_raw.items(), key=lambda kv: str(kv[0]))}

    return ReportRecord(
        source=str(raw.source),
        line=int(raw.line),
        params_hash=str(params_hash),
        params_hash_source=str(params_hash_source),
        status=str(status),
        status_ok=bool(status_ok),
        chi2_cmb=chi2_cmb,
        chi2_total=chi2_total,
        chi2_parts={str(k): float(v) for k, v in sorted(chi2_parts.items())},
        drift_precheck_ok=drift_precheck_ok,
        drift_metric=drift_metric,
        drift_sign_z3=drift_sign_z3,
        plausible_ok=bool(plausible_ok),
        plausible_present=bool(plausible_present),
        microphysics_penalty=float(microphysics_penalty),
        microphysics_max_rel_dev=float(microphysics_max_rel_dev),
        params=params,
        cosmo_knobs=_extract_cosmo_knobs(obj),
        micro_knobs=_extract_micro_knobs(obj),
    )


def _status_bucket(status: str) -> str:
    text = str(status).strip().lower()
    if not text:
        return "ok"
    return text


def _has_metric(record: ReportRecord) -> bool:
    return record.chi2_total is not None or record.chi2_cmb is not None


def _eligible(
    record: ReportRecord,
    *,
    status_filter: str,
    plausibility: str,
    require_drift_precheck: bool,
) -> bool:
    if str(status_filter) == "ok_only" and not record.status_ok:
        return False
    if str(plausibility) == "plausible_only" and not record.plausible_ok:
        return False
    if bool(require_drift_precheck) and record.drift_precheck_ok is False:
        return False
    return _has_metric(record)


def _selection_score(record: ReportRecord, *, selection: str) -> Optional[float]:
    mode = str(selection)
    if mode == "best_cmb":
        if record.chi2_cmb is not None:
            return float(record.chi2_cmb)
        if record.chi2_total is not None:
            return float(record.chi2_total)
        return None
    if record.chi2_total is not None:
        return float(record.chi2_total)
    if record.chi2_cmb is not None:
        return float(record.chi2_cmb)
    return None


def _selection_pool(records: Sequence[ReportRecord], *, selection: str) -> List[ReportRecord]:
    if str(selection) != "best_plausible":
        return list(records)
    return [rec for rec in records if rec.plausible_ok]


def _sort_key(record: ReportRecord, *, selection: str) -> Tuple[Any, ...]:
    score = _selection_score(record, selection=selection)
    return (
        float(score) if score is not None else float("inf"),
        float(record.chi2_cmb) if record.chi2_cmb is not None else float("inf"),
        float(record.chi2_total) if record.chi2_total is not None else float("inf"),
        str(record.params_hash),
        str(record.source),
        int(record.line),
    )


def _knob_details(record: ReportRecord, *, limit: int) -> List[Dict[str, Any]]:
    details: List[Dict[str, Any]] = []
    for spec in iter_knob_specs_sorted():
        if spec.name not in record.micro_knobs:
            continue
        value = float(record.micro_knobs[spec.name])
        baseline = float(spec.default)
        delta = float(value - baseline)
        kind = str(spec.kind)
        rel_dev: Optional[float]
        score: float
        if kind in {"scale", "mul"} and baseline != 0.0:
            rel_dev = abs(value / baseline - 1.0)
            score = float(rel_dev)
        else:
            rel_dev = None
            score = abs(delta)
        in_range = float(spec.plausible_min) <= value <= float(spec.plausible_max)
        details.append(
            {
                "name": str(spec.name),
                "value": float(value),
                "baseline": float(baseline),
                "kind": kind,
                "delta": float(delta),
                "rel_dev": None if rel_dev is None else float(rel_dev),
                "plausible_min": float(spec.plausible_min),
                "plausible_max": float(spec.plausible_max),
                "in_range": bool(in_range),
                "description": str(spec.doc),
                "score": float(score),
            }
        )

    details.sort(key=lambda d: (-float(d.get("score", 0.0)), str(d.get("name", ""))))
    clipped = details[: max(1, int(limit))]
    for row in clipped:
        row.pop("score", None)
    return clipped


def _record_summary(record: ReportRecord, *, top_k: int) -> Dict[str, Any]:
    return {
        "params_hash": str(record.params_hash),
        "params_hash_source": str(record.params_hash_source),
        "status": str(record.status),
        "chi2_total": record.chi2_total,
        "chi2_cmb": record.chi2_cmb,
        "chi2_parts": {str(k): float(v) for k, v in sorted(record.chi2_parts.items())},
        "microphysics_plausible_ok": bool(record.plausible_ok),
        "microphysics_penalty": float(record.microphysics_penalty),
        "microphysics_max_rel_dev": float(record.microphysics_max_rel_dev),
        "drift_summary": {
            "drift_precheck_ok": record.drift_precheck_ok,
            "drift_metric": record.drift_metric,
            "drift_sign_z3": record.drift_sign_z3,
        },
        "cosmo_knobs": {str(k): float(v) for k, v in sorted(record.cosmo_knobs.items())},
        "microphysics_knobs_top": _knob_details(record, limit=top_k),
        "params": {str(k): _to_json_safe(v) for k, v in sorted(record.params.items())},
    }


def _fmt(value: Any) -> str:
    fv = _finite_float(value)
    if fv is None:
        return "NA"
    return f"{float(fv):.6g}"


def _fmt_bool(value: Optional[bool]) -> str:
    if value is None:
        return "NA"
    return "true" if bool(value) else "false"


def _tex_escape(value: str) -> str:
    text = str(value)
    text = text.replace("\\", "\\textbackslash{}")
    text = text.replace("&", "\\&")
    text = text.replace("%", "\\%")
    text = text.replace("_", "\\_")
    text = text.replace("$", "\\$")
    text = text.replace("#", "\\#")
    text = text.replace("{", "\\{")
    text = text.replace("}", "\\}")
    return text


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


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip("\n") + "\n", encoding="utf-8")


def _build_markdown(payload: Mapping[str, Any]) -> str:
    filters = _as_mapping(payload.get("filters"))
    selected = payload.get("selected") if isinstance(payload.get("selected"), Mapping) else None
    table = payload.get("table") if isinstance(payload.get("table"), Sequence) else []

    lines: List[str] = []
    lines.append("# Phase-2 E2 Closure -> Physical Knobs")
    lines.append("")
    lines.append(
        "Diagnostic-only summary of how drift-eligible compressed-CMB closure candidates map to physical/cmb-microphysics knobs."
    )
    lines.append("")
    lines.append("## Filters")
    lines.append("")
    for key in ("status_filter", "plausibility", "require_drift_precheck", "selection", "top_k"):
        lines.append(f"- {key}: `{filters.get(key)}`")
    lines.append("")
    lines.append("## Counts")
    lines.append("")
    for key in (
        "n_records_total",
        "n_records_status_ok",
        "n_records_eligible",
        "n_records_plausible",
        "n_records_drift_precheck_true",
        "n_records_ineligible",
    ):
        lines.append(f"- {key}: `{payload.get(key, 0)}`")
    lines.append("")
    lines.append("## Selected")
    lines.append("")
    if selected is None:
        lines.append("No eligible point selected under current filters.")
    else:
        drift = _as_mapping(selected.get("drift_summary"))
        lines.append(f"- params_hash: `{selected.get('params_hash', 'NA')}`")
        lines.append(f"- status: `{selected.get('status', 'NA')}`")
        lines.append(f"- chi2_total: `{_fmt(selected.get('chi2_total'))}`")
        lines.append(f"- chi2_cmb: `{_fmt(selected.get('chi2_cmb'))}`")
        lines.append(f"- drift_precheck_ok: `{_fmt_bool(_bool_like(drift.get('drift_precheck_ok')))}`")
        lines.append(f"- drift_sign_z3: `{_fmt_bool(_bool_like(drift.get('drift_sign_z3')))}`")
        lines.append(
            f"- microphysics_plausible_ok: `{_fmt_bool(_bool_like(selected.get('microphysics_plausible_ok')))}`"
        )
    lines.append("")
    lines.append("## Top candidates")
    lines.append("")
    lines.append("| rank | params_hash | status | chi2_total | chi2_cmb | drift_precheck_ok | plausible_ok | top_knob |")
    lines.append("|---:|---|---|---:|---:|---:|---:|---|")
    for idx, item in enumerate(table, start=1):
        if not isinstance(item, Mapping):
            continue
        drift = _as_mapping(item.get("drift_summary"))
        knobs = item.get("microphysics_knobs_top")
        top_knob = "NA"
        if isinstance(knobs, Sequence) and knobs:
            first = knobs[0]
            if isinstance(first, Mapping):
                top_knob = str(first.get("name", "")) + "=" + _fmt(first.get("value"))
        lines.append(
            "| "
            + str(idx)
            + " | "
            + str(item.get("params_hash", ""))
            + " | "
            + str(item.get("status", ""))
            + " | "
            + _fmt(item.get("chi2_total"))
            + " | "
            + _fmt(item.get("chi2_cmb"))
            + " | "
            + _fmt_bool(_bool_like(drift.get("drift_precheck_ok")))
            + " | "
            + _fmt_bool(_bool_like(item.get("microphysics_plausible_ok")))
            + " | "
            + top_knob
            + " |"
        )

    lines.append("")
    lines.append(
        "Interpretation is diagnostic-only: required knob shifts are conditional on scanned deformation families, "
        "priors, and filters; they are not standalone physical claims."
    )
    return "\n".join(lines)


def _build_tex(payload: Mapping[str, Any]) -> str:
    table = payload.get("table") if isinstance(payload.get("table"), Sequence) else []
    lines: List[str] = []
    lines.append("% Auto-generated by phase2_e2_physical_knobs_report.py")
    lines.append("\\begin{tabular}{llllllll}")
    lines.append("\\hline")
    lines.append("rank & params\\_hash & status & chi2\\_total & chi2\\_cmb & drift\\_ok & plausible & top\\_knob \\\\")
    lines.append("\\hline")
    for idx, item in enumerate(table, start=1):
        if not isinstance(item, Mapping):
            continue
        drift = _as_mapping(item.get("drift_summary"))
        knobs = item.get("microphysics_knobs_top")
        top_knob = "NA"
        if isinstance(knobs, Sequence) and knobs:
            first = knobs[0]
            if isinstance(first, Mapping):
                top_knob = str(first.get("name", "")) + "=" + _fmt(first.get("value"))
        lines.append(
            " & ".join(
                [
                    str(idx),
                    _tex_escape(str(item.get("params_hash", ""))),
                    _tex_escape(str(item.get("status", ""))),
                    _tex_escape(_fmt(item.get("chi2_total"))),
                    _tex_escape(_fmt(item.get("chi2_cmb"))),
                    _tex_escape(_fmt_bool(_bool_like(drift.get("drift_precheck_ok")))),
                    _tex_escape(_fmt_bool(_bool_like(item.get("microphysics_plausible_ok")))),
                    _tex_escape(top_knob),
                ]
            )
            + " \\\\" 
        )
    lines.append("\\hline")
    lines.append("\\end{tabular}")
    lines.append("")
    lines.append(
        "Diagnostic-only summary: knob shifts are conditional on scanned families, compressed priors, and filters."
    )
    return "\n".join(lines)


def _run(
    *,
    records: Sequence[ReportRecord],
    input_entries: Sequence[InputEntry],
    status_filter: str,
    plausibility: str,
    require_drift_precheck: bool,
    selection: str,
    top_k: int,
) -> Dict[str, Any]:
    status_counts: Dict[str, int] = {}
    n_status_ok = 0
    n_plausible = 0
    n_drift_precheck_true = 0
    warnings: List[str] = []

    for rec in records:
        bucket = _status_bucket(rec.status)
        status_counts[bucket] = int(status_counts.get(bucket, 0)) + 1
        if rec.status_ok:
            n_status_ok += 1
        if rec.plausible_ok:
            n_plausible += 1
        if rec.drift_precheck_ok is not False:
            n_drift_precheck_true += 1

    n_missing_status = sum(1 for rec in records if str(rec.status).strip().lower() == "ok" and rec.params_hash_source != "params_hash")
    if n_missing_status > 0:
        warnings.append("legacy records without explicit status were treated as ok")

    n_legacy_plausible = sum(1 for rec in records if not rec.plausible_present)
    if n_legacy_plausible > 0:
        warnings.append(
            f"{n_legacy_plausible} record(s) missing microphysics_plausible_ok treated as plausible (legacy back-compat)"
        )

    eligible = [
        rec
        for rec in records
        if _eligible(
            rec,
            status_filter=status_filter,
            plausibility=plausibility,
            require_drift_precheck=require_drift_precheck,
        )
    ]

    pool = _selection_pool(eligible, selection=selection)
    scored_pool = [rec for rec in pool if _selection_score(rec, selection=selection) is not None]
    sorted_pool = sorted(scored_pool, key=lambda rec: _sort_key(rec, selection=selection))

    selected_rec = sorted_pool[0] if sorted_pool else None
    table_recs = sorted_pool[: max(1, int(top_k))]

    payload: Dict[str, Any] = {
        "schema_id": SCHEMA_ID,
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
            "require_drift_precheck": bool(require_drift_precheck),
            "selection": str(selection),
            "top_k": int(top_k),
        },
        "n_records_total": int(len(records)),
        "n_records_status_ok": int(n_status_ok),
        "n_records_eligible": int(len(eligible)),
        "n_records_plausible": int(n_plausible),
        "n_records_drift_precheck_true": int(n_drift_precheck_true),
        "n_records_ineligible": int(len(records) - len(eligible)),
        "status_counts": {str(k): int(status_counts[k]) for k in sorted(status_counts.keys())},
        "selected": _record_summary(selected_rec, top_k=top_k) if selected_rec is not None else None,
        "table": [_record_summary(rec, top_k=top_k) for rec in table_recs],
        "warnings": sorted(set(str(w) for w in warnings)),
    }
    return payload


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="phase2_e2_physical_knobs_report",
        description="Deterministic stdlib E2 closure->physical-knobs diagnostics report.",
    )
    ap.add_argument("--input-jsonl", action="append", type=Path, default=[], help="Input merged scan JSONL path (repeatable).")
    ap.add_argument("--bundle", action="append", type=Path, default=[], help="Optional input bundle path (repeatable).")
    ap.add_argument("--outdir", required=True, type=Path, help="Output directory.")
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--status-filter", choices=["ok_only", "any_eligible"], default="ok_only")
    ap.add_argument("--plausibility", choices=["any", "plausible_only"], default="plausible_only")
    ap.add_argument("--require-drift-precheck", dest="require_drift_precheck", action="store_true", default=True)
    ap.add_argument("--no-require-drift-precheck", dest="require_drift_precheck", action="store_false")
    ap.add_argument("--selection", choices=["best_overall", "best_cmb", "best_plausible"], default="best_plausible")
    ap.add_argument("--toy", action="store_true", help="Run on deterministic embedded toy payload.")
    args = ap.parse_args(argv)

    if int(args.top_k) <= 0:
        raise SystemExit("--top-k must be > 0")

    raw_records: List[RawRecord] = []
    entries: List[InputEntry] = []

    if bool(args.toy):
        raw_records, entries = _toy_records()
    else:
        if not args.input_jsonl and not args.bundle:
            raise SystemExit("Provide at least one input via --input-jsonl and/or --bundle (or use --toy)")
        for path in sorted(args.input_jsonl, key=lambda p: str(p)):
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
        require_drift_precheck=bool(args.require_drift_precheck),
        selection=str(args.selection),
        top_k=int(args.top_k),
    )

    outdir = args.outdir.expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    json_path = outdir / "phase2_e2_physical_knobs_report.json"
    md_path = outdir / "phase2_e2_physical_knobs.md"
    tex_path = outdir / "phase2_e2_physical_knobs.tex"

    _write_json(json_path, payload)
    _write_text(md_path, _build_markdown(payload))
    _write_text(tex_path, _build_tex(payload))

    summary = {
        "schema_id": SCHEMA_ID,
        "outdir": str(outdir),
        "n_records_total": payload.get("n_records_total", 0),
        "n_records_eligible": payload.get("n_records_eligible", 0),
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

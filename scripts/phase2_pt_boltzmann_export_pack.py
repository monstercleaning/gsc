#!/usr/bin/env python3
"""Deterministic Phase-2 perturbations/Boltzmann export-pack generator (stdlib-only).

This tool exports a reviewer-friendly handoff pack from Phase-2 E2 JSONL/bundle
results without computing CMB spectra. It is an export/readiness bridge only.
"""

from __future__ import annotations

import argparse
import fnmatch
import glob
import gzip
import hashlib
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
import zipfile


TOOL_NAME = "phase2_pt_boltzmann_export_pack"
SCHEMA_NAME = "phase2_pt_boltzmann_export_pack_v1"
ZIP_ROOT = "boltzmann_export_pack"

RSD_CHI2_FIELD_PRIORITY: Tuple[str, ...] = ("rsd_chi2_total", "rsd_chi2", "rsd_chi2_min")
MISSING_RSD_MARKER = "MISSING_RSD_CHI2_FIELD_FOR_BOLTZMANN_EXPORT"

FORBIDDEN_COMPONENTS: Tuple[str, ...] = (".git", ".venv", "__MACOSX", "site-packages")
FORBIDDEN_BASENAME_GLOBS: Tuple[str, ...] = (
    ".DS_Store",
    "error",
    "skipped_*",
    "submission_bundle*.zip",
    "referee_pack*.zip",
    "toe_bundle*.zip",
    "*PUBLICATION_BUNDLE*",
)
FORBIDDEN_PREFIXES: Tuple[str, ...] = (
    "v11.0.0/archive/packs/",
    "v11.0.0/B/",
)

VOLATILE_FALLBACK_KEYS = {
    "created_utc",
    "updated_utc",
    "timestamp",
    "scan_started_utc",
    "scan_finished_utc",
}

_CREATED_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class ExportPackError(Exception):
    """Base error."""


class ExportPackUsageError(ExportPackError):
    """CLI/config/parse error."""


class ExportPackGateError(ExportPackError):
    """Deterministic gating failure (exit code 2)."""


@dataclass(frozen=True)
class InputStats:
    source: str
    bytes: int
    n_records: int
    n_invalid_lines: int


@dataclass(frozen=True)
class ParsedRecord:
    source: str
    line: int
    status: str
    params_hash: str
    params_hash_source: str
    plan_point_id: str
    chi2_total: Optional[float]
    chi2_joint_total: Optional[float]
    raw: Dict[str, Any]


@dataclass(frozen=True)
class ArtifactRow:
    path: str
    bytes: int
    sha256: str


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


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _normalize_status(record: Mapping[str, Any]) -> str:
    raw = record.get("status")
    if raw is None:
        return "unknown"
    text = str(raw).strip().lower()
    return text if text else "unknown"


def _safe_member_path(name: str) -> bool:
    p = PurePosixPath(str(name))
    if p.is_absolute():
        return False
    return ".." not in p.parts


def _decode_payload(source: str, payload: bytes) -> str:
    raw = bytes(payload)
    if str(source).lower().endswith(".gz"):
        try:
            raw = gzip.decompress(raw)
        except OSError as exc:
            raise ExportPackUsageError(f"invalid gzip payload: {source}") from exc
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ExportPackUsageError(f"payload is not utf-8 text: {source}") from exc


def _extract_chi2_total(record: Mapping[str, Any]) -> Optional[float]:
    for key in ("chi2_total", "chi2", "chi2_tot"):
        value = _finite_float(record.get(key))
        if value is not None:
            return value

    parts_raw = _as_mapping(record.get("chi2_parts"))
    vals: List[float] = []
    for key in sorted(parts_raw.keys(), key=lambda x: str(x)):
        value = parts_raw[key]
        if isinstance(value, Mapping):
            fv = _finite_float(value.get("chi2"))
        else:
            fv = _finite_float(value)
        if fv is not None:
            vals.append(float(fv))
    if vals:
        total = float(sum(vals))
        if math.isfinite(total):
            return total
    return None


def _canonical_hash_fallback(record: Mapping[str, Any], *, line_text: str) -> Tuple[str, str]:
    params = _as_mapping(record.get("params"))
    if params:
        canonical_params = {
            str(k): params[k]
            for k in sorted(params.keys(), key=lambda x: str(x))
            if isinstance(params[k], (str, int, float, bool))
        }
        if canonical_params:
            try:
                return _sha256_text(_canonical_json(canonical_params)), "params_fallback"
            except Exception:
                pass

    payload = {
        str(k): record[k]
        for k in sorted(record.keys(), key=lambda x: str(x))
        if str(k) not in VOLATILE_FALLBACK_KEYS
    }
    if payload:
        try:
            return _sha256_text(_canonical_json(payload)), "record_fallback"
        except Exception:
            pass

    return _sha256_text(line_text.strip()), "line_fallback"


def _extract_params_hash(record: Mapping[str, Any], *, line_text: str) -> Tuple[str, str]:
    raw = record.get("params_hash")
    if isinstance(raw, str) and raw.strip():
        return raw.strip(), "params_hash"
    return _canonical_hash_fallback(record, line_text=line_text)


def _parse_line_record(*, source: str, line: int, line_text: str, obj: Mapping[str, Any]) -> ParsedRecord:
    params_hash, params_hash_source = _extract_params_hash(obj, line_text=line_text)
    chi2_total = _extract_chi2_total(obj)
    chi2_joint_total = _finite_float(obj.get("chi2_joint_total"))
    plan_point_raw = obj.get("plan_point_id")
    plan_point_id = "" if plan_point_raw is None else str(plan_point_raw).strip()
    return ParsedRecord(
        source=str(source),
        line=int(line),
        status=_normalize_status(obj),
        params_hash=str(params_hash),
        params_hash_source=str(params_hash_source),
        plan_point_id=str(plan_point_id),
        chi2_total=chi2_total,
        chi2_joint_total=chi2_joint_total,
        raw={str(k): obj[k] for k in obj.keys()},
    )


def _parse_jsonl_text(source: str, text: str, *, bytes_len: int) -> Tuple[List[ParsedRecord], InputStats]:
    parsed: List[ParsedRecord] = []
    n_invalid = 0
    for lineno, raw in enumerate(str(text).splitlines(), start=1):
        line = str(raw).strip()
        if not line:
            continue
        try:
            decoded = json.loads(line)
        except Exception:
            n_invalid += 1
            continue
        if not isinstance(decoded, Mapping):
            n_invalid += 1
            continue
        parsed.append(_parse_line_record(source=source, line=lineno, line_text=line, obj=decoded))

    return parsed, InputStats(
        source=str(source),
        bytes=int(bytes_len),
        n_records=int(len(parsed)),
        n_invalid_lines=int(n_invalid),
    )


def _iter_bundle_jsonl_payloads(bundle_path: Path) -> List[Tuple[str, bytes]]:
    resolved = bundle_path.expanduser().resolve()
    out: List[Tuple[str, bytes]] = []

    if resolved.is_dir():
        candidates = sorted(list(resolved.rglob("*.jsonl")) + list(resolved.rglob("*.jsonl.gz")))
        for candidate in candidates:
            out.append((str(candidate), candidate.read_bytes()))
        return out

    if not resolved.is_file():
        raise ExportPackUsageError(f"--bundle path does not exist: {resolved}")

    lower = resolved.name.lower()
    if lower.endswith(".zip"):
        with zipfile.ZipFile(resolved, "r") as zf:
            for name in sorted(zf.namelist()):
                lname = name.lower()
                if not (lname.endswith(".jsonl") or lname.endswith(".jsonl.gz")):
                    continue
                if not _safe_member_path(name):
                    raise ExportPackUsageError(f"unsafe bundle member path: {name}")
                out.append((f"{resolved}::{name}", zf.read(name)))
        return out

    if lower.endswith(".tar") or lower.endswith(".tar.gz") or lower.endswith(".tgz"):
        with tarfile.open(resolved, "r:*") as tf:
            members = [m for m in tf.getmembers() if m.isfile()]
            for member in sorted(members, key=lambda m: m.name):
                lname = member.name.lower()
                if not (lname.endswith(".jsonl") or lname.endswith(".jsonl.gz")):
                    continue
                if not _safe_member_path(member.name):
                    raise ExportPackUsageError(f"unsafe bundle member path: {member.name}")
                extracted = tf.extractfile(member)
                if extracted is None:
                    continue
                out.append((f"{resolved}::{member.name}", extracted.read()))
        return out

    raise ExportPackUsageError(f"unsupported --bundle format: {resolved}")


def _contains_glob_magic(token: str) -> bool:
    return any(ch in str(token) for ch in "*?[]")


def _expand_input_token(token: str) -> List[Path]:
    text = str(token).strip()
    if not text:
        return []

    if _contains_glob_magic(text):
        matches = sorted(Path(m).expanduser().resolve() for m in glob.glob(text, recursive=True))
        if not matches:
            raise ExportPackUsageError(f"--input pattern matched no paths: {text}")
        return matches

    candidate = Path(text).expanduser().resolve()
    if candidate.exists():
        return [candidate]

    # fallback: allow unquoted glob-like patterns that were not detected
    matches = sorted(Path(m).expanduser().resolve() for m in glob.glob(text, recursive=True))
    if matches:
        return matches

    raise ExportPackUsageError(f"--input path does not exist: {text}")


def _collect_jsonl_files_from_inputs(tokens: Sequence[str]) -> List[Path]:
    files: Dict[str, Path] = {}
    for token in tokens:
        for candidate in _expand_input_token(token):
            if candidate.is_dir():
                for path in sorted(list(candidate.rglob("*.jsonl")) + list(candidate.rglob("*.jsonl.gz"))):
                    files[str(path.resolve())] = path.resolve()
                continue
            if candidate.is_file():
                lname = candidate.name.lower()
                if not (lname.endswith(".jsonl") or lname.endswith(".jsonl.gz")):
                    raise ExportPackUsageError(f"--input file is not jsonl/jsonl.gz: {candidate}")
                files[str(candidate.resolve())] = candidate.resolve()
                continue
            raise ExportPackUsageError(f"--input path is neither file nor directory: {candidate}")

    ordered = [files[key] for key in sorted(files.keys())]
    if not ordered:
        raise ExportPackUsageError("no JSONL files were resolved from --input")
    return ordered


def _load_records_from_files(files: Sequence[Path]) -> Tuple[List[ParsedRecord], List[InputStats]]:
    records: List[ParsedRecord] = []
    stats: List[InputStats] = []
    for path in files:
        payload = path.read_bytes()
        text = _decode_payload(str(path), payload)
        parsed, st = _parse_jsonl_text(str(path), text, bytes_len=len(payload))
        records.extend(parsed)
        stats.append(st)
    return records, stats


def _load_records_from_bundle(bundle: Path) -> Tuple[List[ParsedRecord], List[InputStats]]:
    payloads = _iter_bundle_jsonl_payloads(bundle)
    if not payloads:
        raise ExportPackUsageError(f"bundle has no *.jsonl payloads: {bundle}")

    records: List[ParsedRecord] = []
    stats: List[InputStats] = []
    for source, data in payloads:
        text = _decode_payload(source, data)
        parsed, st = _parse_jsonl_text(source, text, bytes_len=len(data))
        records.extend(parsed)
        stats.append(st)
    return records, stats


def _status_is_eligible(status: str, *, eligible_status: str) -> bool:
    st = str(status).strip().lower()
    if eligible_status == "ok_only":
        return st == "ok"
    # any_eligible
    return st != "error"


def _extract_rsd_value(record: ParsedRecord, field: str) -> Optional[float]:
    return _finite_float(record.raw.get(field))


def _resolve_rsd_field(records: Sequence[ParsedRecord], *, field_override: Optional[str]) -> Optional[str]:
    if field_override is not None:
        key = str(field_override).strip()
        if not key:
            return None
        for rec in records:
            if _extract_rsd_value(rec, key) is not None:
                return key
        return None

    for key in RSD_CHI2_FIELD_PRIORITY:
        for rec in records:
            if _extract_rsd_value(rec, key) is not None:
                return key
    return None


def _rank_key(metric: float, rec: ParsedRecord) -> Tuple[Any, ...]:
    chi2_total = rec.chi2_total if rec.chi2_total is not None else float("inf")
    return (
        float(metric),
        float(chi2_total),
        str(rec.params_hash),
        str(rec.source),
        int(rec.line),
    )


def _select_best_record(
    records: Sequence[ParsedRecord],
    *,
    rank_by: str,
    eligible_status: str,
    rsd_chi2_field: Optional[str],
    prefer_precomputed_joint: bool,
) -> Tuple[ParsedRecord, Dict[str, Any]]:
    eligible = [r for r in records if _status_is_eligible(r.status, eligible_status=eligible_status)]
    if not eligible:
        raise ExportPackGateError("NO_ELIGIBLE_RECORDS_FOR_BOLTZMANN_EXPORT")

    chosen_field: Optional[str] = None
    if rank_by in {"rsd", "joint"}:
        chosen_field = _resolve_rsd_field(eligible, field_override=rsd_chi2_field)

    best_row: Optional[Tuple[Tuple[Any, ...], ParsedRecord, float, Dict[str, Any]]] = None
    used_precomputed_any = False

    for rec in eligible:
        metric: Optional[float] = None
        components: Dict[str, Any] = {
            "chi2_total": rec.chi2_total,
            "chi2_joint_total": rec.chi2_joint_total,
            "rsd_chi2": None,
            "rsd_weight": None,
            "used_precomputed_joint": False,
        }

        if rank_by == "cmb":
            if rec.chi2_total is None:
                continue
            metric = float(rec.chi2_total)

        elif rank_by == "rsd":
            if chosen_field is None:
                continue
            rsd = _extract_rsd_value(rec, chosen_field)
            if rsd is None:
                continue
            components["rsd_chi2"] = float(rsd)
            metric = float(rsd)

        elif rank_by == "joint":
            if prefer_precomputed_joint and rec.chi2_joint_total is not None:
                metric = float(rec.chi2_joint_total)
                components["used_precomputed_joint"] = True
                used_precomputed_any = True
                weight = _finite_float(rec.raw.get("rsd_chi2_weight"))
                if weight is not None:
                    components["rsd_weight"] = float(weight)
            else:
                if rec.chi2_total is None or chosen_field is None:
                    continue
                rsd = _extract_rsd_value(rec, chosen_field)
                if rsd is None:
                    continue
                weight = _finite_float(rec.raw.get("rsd_chi2_weight"))
                if weight is None:
                    weight = 1.0
                metric = float(rec.chi2_total + float(weight) * float(rsd))
                components["rsd_chi2"] = float(rsd)
                components["rsd_weight"] = float(weight)

        else:
            raise ExportPackUsageError(f"unsupported --rank-by: {rank_by}")

        if metric is None or not math.isfinite(metric):
            continue

        row = (_rank_key(metric, rec), rec, float(metric), components)
        if best_row is None or row[0] < best_row[0]:
            best_row = row

    if best_row is None:
        if rank_by in {"rsd", "joint"}:
            raise ExportPackGateError(MISSING_RSD_MARKER)
        raise ExportPackGateError("NO_RANKABLE_RECORDS_FOR_BOLTZMANN_EXPORT")

    _, winner, metric_value, components = best_row

    selection_meta: Dict[str, Any] = {
        "rank_by": str(rank_by),
        "eligible_status": str(eligible_status),
        "rsd_chi2_field_used": chosen_field,
        "used_precomputed_joint": bool(components.get("used_precomputed_joint", False)),
        "used_precomputed_joint_any": bool(used_precomputed_any),
        "best_metric_value": float(metric_value),
        "best_metric_components": {
            "chi2_total": components.get("chi2_total"),
            "chi2_joint_total": components.get("chi2_joint_total"),
            "rsd_chi2": components.get("rsd_chi2"),
            "rsd_weight": components.get("rsd_weight"),
        },
    }

    # when rank-by joint and best row came from precomputed metric, report row hint if present
    if rank_by == "joint" and selection_meta["used_precomputed_joint"]:
        from_row_field = winner.raw.get("rsd_chi2_field_used")
        if isinstance(from_row_field, str) and from_row_field.strip() and not selection_meta["rsd_chi2_field_used"]:
            selection_meta["rsd_chi2_field_used"] = from_row_field.strip()

    return winner, selection_meta


def _pick_param_float(sources: Sequence[Mapping[str, Any]], *names: str) -> Optional[float]:
    wanted = {str(name).strip().lower() for name in names if str(name).strip()}
    if not wanted:
        return None
    for source in sources:
        for key in source.keys():
            key_text = str(key).strip().lower()
            if key_text not in wanted:
                continue
            out = _finite_float(source.get(key))
            if out is not None:
                return float(out)
    return None


def _extract_candidate_params(record: ParsedRecord) -> Dict[str, Optional[float]]:
    raw = _as_mapping(record.raw)
    params = _as_mapping(raw.get("params"))
    bestfit = _as_mapping(raw.get("bestfit_params"))
    cosmology = _as_mapping(raw.get("cosmology"))
    sources = [raw, params, bestfit, cosmology]

    H0 = _pick_param_float(sources, "H0", "h0", "h0_km_s_mpc", "hubble0")
    h = _pick_param_float(sources, "h", "little_h")
    if h is None and H0 is not None:
        h = float(H0) / 100.0
    if H0 is None and h is not None:
        H0 = 100.0 * float(h)

    omega_m = _pick_param_float(sources, "omega_m", "omega_m0", "omegam", "om0", "Omega_m", "Omega_m0")
    Omega_b = _pick_param_float(sources, "omega_b", "omega_b0", "omegab", "ob0", "Omega_b", "Omega_b0")
    Omega_c = _pick_param_float(sources, "omega_c", "omega_c0", "Omega_c", "Omega_cdm", "omega_cdm", "Omega_cdm0")

    ombh2 = _pick_param_float(sources, "ombh2", "omega_b_h2", "omega_bh2")
    omch2 = _pick_param_float(sources, "omch2", "omega_c_h2", "omega_cdm_h2", "omega_ch2")

    if h is not None and ombh2 is None and Omega_b is not None:
        ombh2 = float(Omega_b) * float(h) * float(h)

    if Omega_c is None and omega_m is not None and Omega_b is not None:
        Omega_c = float(omega_m) - float(Omega_b)

    if h is not None and omch2 is None and Omega_c is not None:
        omch2 = float(Omega_c) * float(h) * float(h)

    As = _pick_param_float(sources, "As", "A_s", "as", "a_s")
    ns = _pick_param_float(sources, "n_s", "ns", "rsd_primordial_ns")
    k_pivot = _pick_param_float(
        sources,
        "k_pivot",
        "k_pivot_mpc",
        "k0_mpc",
        "pivot_k",
        "rsd_primordial_k_pivot_mpc",
    )
    tau_reio = _pick_param_float(sources, "tau_reio", "tau", "tau0")

    transfer_model_raw = raw.get("rsd_transfer_model")
    transfer_model = None if transfer_model_raw is None else str(transfer_model_raw).strip()
    if not transfer_model:
        transfer_model = None

    return {
        "H0_km_s_Mpc": H0,
        "h": h,
        "Omega_m0": omega_m,
        "Omega_b0": Omega_b,
        "Omega_c0": Omega_c,
        "omega_b_h2": ombh2,
        "omega_c_h2": omch2,
        "As": As,
        "n_s": ns,
        "k_pivot_mpc": k_pivot,
        "tau_reio": tau_reio,
        "transfer_model": None if transfer_model is None else str(transfer_model),
    }


def _fmt_float(value: Any, *, digits: int = 8) -> str:
    fv = _finite_float(value)
    if fv is None:
        return "NA"
    fmt = f"{{:.{int(digits)}g}}"
    return fmt.format(float(fv))


def _render_class_template(params: Mapping[str, Any], *, created_utc: str) -> str:
    lines: List[str] = []
    lines.append("# BOLTZMANN_INPUT_TEMPLATE_CLASS.ini")
    lines.append(f"# generated_by={TOOL_NAME}")
    lines.append(f"# created_utc={created_utc}")
    lines.append("# scope: export-only handoff template; no spectra are computed by this pack")
    lines.append("")

    h = _finite_float(params.get("h"))
    ombh2 = _finite_float(params.get("omega_b_h2"))
    omch2 = _finite_float(params.get("omega_c_h2"))
    As = _finite_float(params.get("As"))
    ns = _finite_float(params.get("n_s"))
    k_pivot = _finite_float(params.get("k_pivot_mpc"))
    tau = _finite_float(params.get("tau_reio"))

    if h is None:
        lines.append("# h = TODO  # missing in selected candidate")
    else:
        lines.append(f"h = {_fmt_float(h)}")

    if ombh2 is None:
        lines.append("# omega_b = TODO  # expected physical density (Omega_b h^2)")
    else:
        lines.append(f"omega_b = {_fmt_float(ombh2)}")

    if omch2 is None:
        lines.append("# omega_cdm = TODO  # expected physical density (Omega_cdm h^2)")
    else:
        lines.append(f"omega_cdm = {_fmt_float(omch2)}")

    if As is None:
        lines.append("# A_s = TODO")
    else:
        lines.append(f"A_s = {_fmt_float(As)}")

    if ns is None:
        lines.append("# n_s = TODO")
    else:
        lines.append(f"n_s = {_fmt_float(ns)}")

    if k_pivot is None:
        lines.append("# k_pivot = TODO  # 1/Mpc")
    else:
        lines.append(f"k_pivot = {_fmt_float(k_pivot)}")

    if tau is None:
        lines.append("# tau_reio = TODO")
    else:
        lines.append(f"tau_reio = {_fmt_float(tau)}")

    transfer_model = params.get("transfer_model")
    if isinstance(transfer_model, str) and transfer_model.strip():
        lines.append(f"# transfer_model_hint = {transfer_model.strip()}")

    lines.append("output = tCl,pCl,lCl,mPk")
    lines.append("l_max_scalars = 2508")
    lines.append("")
    lines.append("# TODO: complete missing entries based on your solver setup/policy.")
    return "\n".join(lines) + "\n"


def _render_camb_template(params: Mapping[str, Any], *, created_utc: str) -> str:
    lines: List[str] = []
    lines.append("# BOLTZMANN_INPUT_TEMPLATE_CAMB.ini")
    lines.append(f"# generated_by={TOOL_NAME}")
    lines.append(f"# created_utc={created_utc}")
    lines.append("# scope: export-only handoff template; no spectra are computed by this pack")
    lines.append("")

    H0 = _finite_float(params.get("H0_km_s_Mpc"))
    ombh2 = _finite_float(params.get("omega_b_h2"))
    omch2 = _finite_float(params.get("omega_c_h2"))
    As = _finite_float(params.get("As"))
    ns = _finite_float(params.get("n_s"))
    k_pivot = _finite_float(params.get("k_pivot_mpc"))
    tau = _finite_float(params.get("tau_reio"))

    if H0 is None:
        lines.append("# hubble = TODO  # H0 in km/s/Mpc")
    else:
        lines.append(f"hubble = {_fmt_float(H0)}")

    if ombh2 is None:
        lines.append("# ombh2 = TODO")
    else:
        lines.append(f"ombh2 = {_fmt_float(ombh2)}")

    if omch2 is None:
        lines.append("# omch2 = TODO")
    else:
        lines.append(f"omch2 = {_fmt_float(omch2)}")

    if As is None:
        lines.append("# scalar_amp(1) = TODO")
    else:
        lines.append(f"scalar_amp(1) = {_fmt_float(As)}")

    if ns is None:
        lines.append("# scalar_spectral_index(1) = TODO")
    else:
        lines.append(f"scalar_spectral_index(1) = {_fmt_float(ns)}")

    if k_pivot is None:
        lines.append("# pivot_scalar = TODO  # 1/Mpc")
    else:
        lines.append(f"pivot_scalar = {_fmt_float(k_pivot)}")

    if tau is None:
        lines.append("# re_optical_depth = TODO")
    else:
        lines.append(f"re_optical_depth = {_fmt_float(tau)}")

    transfer_model = params.get("transfer_model")
    if isinstance(transfer_model, str) and transfer_model.strip():
        lines.append(f"# transfer_model_hint = {transfer_model.strip()}")

    lines.append("get_scalar_cls = T")
    lines.append("get_transfer = T")
    lines.append("do_lensing = T")
    lines.append("lmax = 2508")
    lines.append("")
    lines.append("# TODO: complete missing entries based on your solver setup/policy.")
    return "\n".join(lines) + "\n"


def _render_readme(
    *,
    created_utc: str,
    rank_by: str,
    eligible_status: str,
    best_params_hash: str,
    best_plan_point_id: str,
) -> str:
    lines: List[str] = []
    lines.append("# Boltzmann / Perturbations Export Pack")
    lines.append("")
    lines.append(f"Tool: `{TOOL_NAME}`")
    lines.append(f"Schema: `{SCHEMA_NAME}`")
    lines.append(f"Created UTC: `{created_utc}`")
    lines.append("")
    lines.append("## What this pack is / is not")
    lines.append("- This pack is an export-only handoff for external Boltzmann/perturbations runs.")
    lines.append("- It does not compute CMB TT/TE/EE spectra by itself.")
    lines.append("- It captures one deterministic best-candidate export from Phase-2 E2 records.")
    lines.append("")
    lines.append("## Selected candidate")
    lines.append(f"- rank_by: `{rank_by}`")
    lines.append(f"- eligible_status: `{eligible_status}`")
    lines.append(f"- params_hash: `{best_params_hash}`")
    if best_plan_point_id:
        lines.append(f"- plan_point_id: `{best_plan_point_id}`")
    lines.append("")
    lines.append("## How to use with CLASS")
    lines.append("1. Open `BOLTZMANN_INPUT_TEMPLATE_CLASS.ini`.")
    lines.append("2. Fill any `TODO` parameters not available in the selected record.")
    lines.append("3. Run your CLASS workflow externally and store outputs in your solver environment.")
    lines.append("")
    lines.append("## How to use with CAMB")
    lines.append("1. Open `BOLTZMANN_INPUT_TEMPLATE_CAMB.ini`.")
    lines.append("2. Fill any `TODO` parameters not available in the selected record.")
    lines.append("3. Run your CAMB workflow externally and store outputs in your solver environment.")
    lines.append("")
    lines.append("## Known gaps / next milestones")
    lines.append("- Scope boundaries: `v11.0.0/docs/perturbations_and_dm_scope.md`")
    lines.append("- Roadmap/status: `v11.0.0/docs/project_status_and_roadmap.md`")
    lines.append("")
    lines.append("## Claim-safety")
    lines.append("- This export does not imply full-spectra closure or dark-matter-resolution claims.")
    lines.append("- It is a readiness bridge from Phase-2 outputs to external perturbation solvers.")
    lines.append("")
    return "\n".join(lines)


def _to_json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _to_json_safe(value[k]) for k in sorted(value.keys(), key=lambda x: str(x))}
    if isinstance(value, list):
        return [_to_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_to_json_safe(v) for v in value]
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return float(value)
    if isinstance(value, str):
        return value
    return str(value)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_to_json_safe(payload), sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _is_symlink(path: Path) -> bool:
    try:
        return path.is_symlink()
    except OSError:
        return False


def _assert_no_symlinks(root: Path) -> None:
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        dir_path = Path(dirpath)
        for d in sorted(dirnames):
            candidate = dir_path / d
            if _is_symlink(candidate):
                rel = candidate.relative_to(root).as_posix()
                raise ExportPackUsageError(f"symlink detected in outdir: {rel}")
        for f in sorted(filenames):
            candidate = dir_path / f
            if _is_symlink(candidate):
                rel = candidate.relative_to(root).as_posix()
                raise ExportPackUsageError(f"symlink detected in outdir: {rel}")


def _forbidden_reason(relpath: str) -> Optional[str]:
    rel = str(relpath).replace("\\", "/").strip("/")
    if not rel:
        return None
    lower = rel.lower()
    parts = rel.split("/")
    lower_parts = [p.lower() for p in parts]
    base = parts[-1]
    slash_wrapped = f"/{lower}/"

    for name in FORBIDDEN_COMPONENTS:
        if name.lower() in lower_parts:
            return f"contains forbidden path component '{name}'"

    for pref in FORBIDDEN_PREFIXES:
        pref_low = pref.lower().rstrip("/")
        if lower == pref_low or lower.startswith(pref_low + "/"):
            return f"matches forbidden prefix '{pref}'"
        if f"/{pref_low}/" in slash_wrapped:
            return f"contains forbidden subpath '{pref}'"

    for pattern in FORBIDDEN_BASENAME_GLOBS:
        if fnmatch.fnmatch(base.lower(), pattern.lower()):
            return f"matches forbidden basename pattern '{pattern}'"

    if "publication_bundle" in lower:
        return "matches forbidden token 'PUBLICATION_BUNDLE'"
    return None


def _scan_forbidden_paths(root: Path) -> None:
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        reason = _forbidden_reason(rel)
        if reason is not None:
            raise ExportPackUsageError(f"forbidden path in outdir: {rel} ({reason})")


def _collect_artifacts(root: Path, *, exclude_relpaths: Iterable[str] = ()) -> List[ArtifactRow]:
    excluded = {str(x).strip("/") for x in exclude_relpaths}
    rows: List[ArtifactRow] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel in excluded:
            continue
        rows.append(ArtifactRow(path=rel, bytes=int(path.stat().st_size), sha256=_sha256_path(path)))
    return rows


def _parse_created_utc(text: str) -> datetime:
    raw = str(text).strip()
    if not _CREATED_UTC_RE.match(raw):
        raise ExportPackUsageError("--created-utc must match YYYY-MM-DDTHH:MM:SSZ")
    try:
        dt = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ExportPackUsageError("--created-utc must match YYYY-MM-DDTHH:MM:SSZ") from exc
    # zip format has lower bound 1980
    if dt.year < 1980:
        raise ExportPackUsageError("--created-utc year must be >= 1980 for deterministic zip metadata")
    return dt


def _zip_dt_from_created(created_dt: datetime) -> Tuple[int, int, int, int, int, int]:
    return (
        int(created_dt.year),
        int(created_dt.month),
        int(created_dt.day),
        int(created_dt.hour),
        int(created_dt.minute),
        int(created_dt.second),
    )


def _write_deterministic_zip(*, zip_out: Path, outdir: Path, zip_dt: Tuple[int, int, int, int, int, int]) -> Tuple[str, int]:
    _assert_no_symlinks(outdir)
    _scan_forbidden_paths(outdir)

    entries: List[Tuple[str, Path, int]] = []
    for path in sorted(outdir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(outdir).as_posix()
        mode = 0o755 if os.access(path, os.X_OK) else 0o644
        entries.append((rel, path, mode))

    zip_out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_out, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel, path, mode in entries:
            info = zipfile.ZipInfo(filename=f"{ZIP_ROOT}/{rel}", date_time=zip_dt)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = ((0o100000 | mode) & 0xFFFF) << 16
            zf.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)

    sha = _sha256_path(zip_out)
    size = int(zip_out.stat().st_size)
    return sha, size


def _render_text_summary(payload: Mapping[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"tool={payload.get('tool')}")
    lines.append(f"schema={payload.get('schema')}")
    lines.append(f"created_utc={payload.get('created_utc')}")

    inp = _as_mapping(payload.get("inputs"))
    lines.append(
        "inputs="
        f"records={inp.get('n_records_parsed')} "
        f"invalid={inp.get('n_invalid_lines')} "
        f"sources={inp.get('n_sources')}"
    )

    sel = _as_mapping(payload.get("selection"))
    lines.append(
        "selection="
        f"rank_by={sel.get('rank_by')} "
        f"eligible_status={sel.get('eligible_status')} "
        f"rsd_field={sel.get('rsd_chi2_field_used')}"
    )

    best = _as_mapping(payload.get("best"))
    lines.append(
        "best="
        f"metric={best.get('best_metric_value')} "
        f"params_hash={best.get('best_params_hash')} "
        f"plan_point_id={best.get('best_plan_point_id') or ''}"
    )

    zip_meta = payload.get("zip")
    if isinstance(zip_meta, Mapping):
        lines.append(
            "zip="
            f"path={zip_meta.get('path')} bytes={zip_meta.get('bytes')} sha256={zip_meta.get('sha256')}"
        )
    else:
        lines.append("zip=none")

    lines.append(f"n_artifacts={len(payload.get('artifacts') or [])}")
    return "\n".join(lines) + "\n"


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Deterministic export pack for external Boltzmann/perturbations handoff.",
    )

    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--bundle", default=None, help="Input Phase-2 bundle path (dir/zip/tar/tgz).")
    grp.add_argument("--input", action="append", default=[], help="Input JSONL path/dir/glob (repeatable).")

    ap.add_argument("--rank-by", choices=("cmb", "rsd", "joint"), default="cmb")
    ap.add_argument("--eligible-status", choices=("ok_only", "any_eligible"), default="ok_only")
    ap.add_argument("--rsd-chi2-field", default=None)
    ap.add_argument("--prefer-precomputed-joint", type=int, choices=(0, 1), default=1)

    ap.add_argument("--outdir", required=True, help="Output directory for export pack files.")
    ap.add_argument("--created-utc", required=True, help="Deterministic timestamp (YYYY-MM-DDTHH:MM:SSZ).")
    ap.add_argument("--zip-out", default=None, help="Optional deterministic zip output path.")
    ap.add_argument("--max-zip-mb", type=float, default=50.0, help="Zip size budget in MB (applies when --zip-out is set).")

    ap.add_argument("--format", choices=("text", "json"), default="text")
    ap.add_argument("--json-out", default=None, help="Optional JSON summary output path.")
    ap.add_argument("--dry-run", action="store_true")

    return ap.parse_args(argv)


def _make_export(args: argparse.Namespace) -> Dict[str, Any]:
    script_path = Path(__file__).resolve()
    v101_root = script_path.parents[1]
    repo_root = script_path.parents[2]

    created_utc = str(args.created_utc).strip()
    created_dt = _parse_created_utc(created_utc)
    zip_dt = _zip_dt_from_created(created_dt)

    if args.max_zip_mb is not None and float(args.max_zip_mb) <= 0:
        raise ExportPackUsageError("--max-zip-mb must be positive")

    if args.bundle:
        bundle_path = Path(str(args.bundle)).expanduser().resolve()
        records, input_stats = _load_records_from_bundle(bundle_path)
        input_kind = "bundle"
        input_tokens = [str(bundle_path)]
    else:
        input_paths = _collect_jsonl_files_from_inputs(list(args.input))
        records, input_stats = _load_records_from_files(input_paths)
        input_kind = "jsonl"
        input_tokens = [str(p) for p in input_paths]

    if not records:
        raise ExportPackUsageError("no valid JSON object records were parsed from inputs")

    winner, selection_meta = _select_best_record(
        records,
        rank_by=str(args.rank_by),
        eligible_status=str(args.eligible_status),
        rsd_chi2_field=(None if args.rsd_chi2_field is None else str(args.rsd_chi2_field)),
        prefer_precomputed_joint=bool(int(args.prefer_precomputed_joint)),
    )

    candidate_params = _extract_candidate_params(winner)
    class_template = _render_class_template(candidate_params, created_utc=created_utc)
    camb_template = _render_camb_template(candidate_params, created_utc=created_utc)
    readme_text = _render_readme(
        created_utc=created_utc,
        rank_by=str(args.rank_by),
        eligible_status=str(args.eligible_status),
        best_params_hash=str(winner.params_hash),
        best_plan_point_id=str(winner.plan_point_id),
    )

    outdir = Path(str(args.outdir)).expanduser().resolve()
    if outdir.exists() and (not outdir.is_dir()):
        raise ExportPackUsageError(f"--outdir exists and is not a directory: {outdir}")

    # warning only, as requested
    try:
        if outdir.is_relative_to(repo_root):
            print(
                "WARNING: --outdir is inside repository root; avoid committing generated export-pack artifacts.",
                file=sys.stderr,
            )
    except AttributeError:
        # Python <3.9 fallback
        try:
            outdir.relative_to(repo_root)
            print(
                "WARNING: --outdir is inside repository root; avoid committing generated export-pack artifacts.",
                file=sys.stderr,
            )
        except Exception:
            pass
    except Exception:
        pass

    plan_files = {
        "summary": "EXPORT_SUMMARY.json",
        "candidate": "CANDIDATE_RECORD.json",
        "class_template": "BOLTZMANN_INPUT_TEMPLATE_CLASS.ini",
        "camb_template": "BOLTZMANN_INPUT_TEMPLATE_CAMB.ini",
        "readme": "README.md",
    }

    stats_payload = {
        "n_sources": int(len(input_stats)),
        "n_records_parsed": int(sum(s.n_records for s in input_stats)),
        "n_invalid_lines": int(sum(s.n_invalid_lines for s in input_stats)),
        "sources": [
            {
                "source": s.source,
                "bytes": int(s.bytes),
                "n_records": int(s.n_records),
                "n_invalid_lines": int(s.n_invalid_lines),
            }
            for s in input_stats
        ],
        "input_kind": str(input_kind),
    }

    best_payload = {
        "best_metric_value": float(selection_meta["best_metric_value"]),
        "best_params_hash": str(winner.params_hash),
        "best_params_hash_source": str(winner.params_hash_source),
        "best_plan_point_id": str(winner.plan_point_id),
        "best_status": str(winner.status),
        "best_source": str(winner.source),
        "best_line": int(winner.line),
    }

    selection_payload = {
        "rank_by": str(args.rank_by),
        "eligible_status": str(args.eligible_status),
        "rsd_chi2_field_used": selection_meta.get("rsd_chi2_field_used"),
        "used_precomputed_joint": bool(selection_meta.get("used_precomputed_joint", False)),
        "used_precomputed_joint_any": bool(selection_meta.get("used_precomputed_joint_any", False)),
        "best_metric_components": selection_meta.get("best_metric_components"),
    }

    summary: Dict[str, Any] = {
        "tool": TOOL_NAME,
        "schema": SCHEMA_NAME,
        "created_utc": created_utc,
        "inputs": stats_payload,
        "selection": selection_payload,
        "best": best_payload,
        "notes": [
            "export-only handoff pack for external Boltzmann/perturbations tooling",
            "no TT/TE/EE spectra are computed by this export tool",
            "claim-safe scope boundary: see v11.0.0/docs/perturbations_and_dm_scope.md",
        ],
        "artifacts": [],
        "zip": None,
        "dry_run": bool(args.dry_run),
        "planned_outputs": [plan_files[k] for k in ("summary", "candidate", "class_template", "camb_template", "readme")],
        "source_inputs": input_tokens,
    }

    if args.dry_run:
        return summary

    outdir.mkdir(parents=True, exist_ok=True)

    candidate_payload: Dict[str, Any] = {
        "schema": "phase2_pt_boltzmann_export_candidate_v1",
        "created_utc": created_utc,
        "selection": selection_payload,
        "best": best_payload,
        "candidate_params": candidate_params,
        "record": winner.raw,
    }

    _write_json(outdir / plan_files["candidate"], candidate_payload)
    _write_text(outdir / plan_files["class_template"], class_template)
    _write_text(outdir / plan_files["camb_template"], camb_template)
    _write_text(outdir / plan_files["readme"], readme_text)

    _assert_no_symlinks(outdir)
    _scan_forbidden_paths(outdir)

    artifacts = _collect_artifacts(outdir, exclude_relpaths=(plan_files["summary"],))
    summary["artifacts"] = [
        {
            "path": row.path,
            "bytes": int(row.bytes),
            "sha256": str(row.sha256),
        }
        for row in artifacts
    ]

    _write_json(outdir / plan_files["summary"], summary)

    if args.zip_out:
        zip_out = Path(str(args.zip_out)).expanduser().resolve()
        zip_sha, zip_bytes = _write_deterministic_zip(zip_out=zip_out, outdir=outdir, zip_dt=zip_dt)
        budget_bytes = int(float(args.max_zip_mb) * 1024 * 1024)
        if zip_bytes > budget_bytes:
            raise ExportPackGateError(
                f"ZIP_BUDGET_EXCEEDED bytes={zip_bytes} budget={budget_bytes} path={zip_out}"
            )
        summary["zip"] = {
            "path": str(zip_out.name),
            "bytes": int(zip_bytes),
            "sha256": str(zip_sha),
            "max_zip_mb": float(args.max_zip_mb),
        }
        _write_json(outdir / plan_files["summary"], summary)

    return summary


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)

    try:
        payload = _make_export(args)
    except ExportPackGateError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except ExportPackUsageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.format == "json":
        sys.stdout.write(json.dumps(_to_json_safe(payload), sort_keys=True, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write(_render_text_summary(payload))

    if args.json_out:
        _write_json(Path(str(args.json_out)).expanduser().resolve(), payload)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

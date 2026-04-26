#!/usr/bin/env python3
"""Reference audit for approximate rs(z*) / z* against external CLASS/CAMB outputs.

This is a diagnostic/audit helper only. It does not compute perturbation spectra.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import math
import re
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


SCHEMA = "phase2_cmb_rs_zstar_reference_audit_v1"
DEFAULT_CREATED_UTC = "2000-01-01T00:00:00Z"
_CREATED_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_NUM_RE = r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)"
_RS_RE = re.compile(r"\b(?:r[_\s-]?s(?:[_\s-]?(?:star|drag))?|rs)\b\s*[:=]\s*" + _NUM_RE, re.IGNORECASE)
_ZSTAR_RE = re.compile(r"\bz[_\s-]?star\b\s*[:=]\s*" + _NUM_RE, re.IGNORECASE)
_TEXT_EXTS = {".txt", ".dat", ".log", ".json", ".yaml", ".yml", ".md"}


def _finite_float(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except Exception:
        return None
    if not math.isfinite(out):
        return None
    return float(out)


def _to_json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _to_json_safe(value[k]) for k in sorted(value.keys(), key=lambda x: str(x))}
    if isinstance(value, list):
        return [_to_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_to_json_safe(v) for v in value]
    if isinstance(value, (str, bool, int)) or value is None:
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return str(value)


def _normalize_created_utc(value: str) -> str:
    text = str(value).strip()
    if not _CREATED_UTC_RE.match(text):
        raise SystemExit("--created-utc must match YYYY-MM-DDTHH:MM:SSZ")
    try:
        parsed = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise SystemExit("--created-utc must match YYYY-MM-DDTHH:MM:SSZ") from exc
    if parsed.year < 1900:
        raise SystemExit("--created-utc year must be >= 1900")
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"JSON file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON file: {path}") from exc
    if not isinstance(payload, Mapping):
        raise SystemExit(f"Expected JSON object at: {path}")
    return {str(k): payload[k] for k in payload.keys()}


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _lookup_float(payload: Mapping[str, Any], keys: Sequence[str]) -> Optional[float]:
    for key in keys:
        if key in payload:
            value = _finite_float(payload.get(key))
            if value is not None:
                return float(value)
    return None


def _extract_candidate_from_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    # Candidate-record-like payload.
    if "record" in payload and isinstance(payload.get("record"), Mapping):
        record = _as_mapping(payload.get("record"))
        best = _as_mapping(payload.get("best"))
    else:
        record = dict(payload)
        best = {}

    # Best-candidates report payload.
    if not record:
        best_joint = _as_mapping(payload.get("best_by_joint"))
        best_cmb = _as_mapping(payload.get("best_by_cmb"))
        if best_joint:
            record = dict(best_joint)
        elif best_cmb:
            record = dict(best_cmb)

    predicted = _as_mapping(record.get("predicted"))
    rs_approx = _lookup_float(
        record,
        [
            "r_s_star_Mpc",
            "rs_star_mpc",
            "r_s_Mpc",
        ],
    )
    if rs_approx is None:
        rs_approx = _lookup_float(predicted, ["r_s_star_Mpc", "rs_star_mpc", "r_s_Mpc"])
    zstar_approx = _lookup_float(
        record,
        [
            "z_star",
            "zstar",
            "z_star_rec",
        ],
    )
    if zstar_approx is None:
        zstar_approx = _lookup_float(predicted, ["z_star", "zstar", "z_star_rec"])

    params_hash = None
    for key in ("params_hash",):
        value = record.get(key)
        if value is None:
            value = best.get("best_params_hash")
        if value is not None and str(value).strip():
            params_hash = str(value).strip()
            break
    plan_point_id = record.get("plan_point_id")
    if plan_point_id is None:
        plan_point_id = best.get("best_plan_point_id")

    return {
        "params_hash": params_hash,
        "plan_point_id": None if plan_point_id is None else str(plan_point_id),
        "rs_approx_mpc": rs_approx,
        "z_star_approx": zstar_approx,
    }


def _iter_candidate_json_paths(bundle_dir: Path) -> Iterable[Path]:
    candidates: List[Path] = []
    direct = [
        bundle_dir / "CANDIDATE_RECORD.json",
        bundle_dir / "phase2_e2_best_candidates_report.json",
    ]
    for path in direct:
        if path.is_file():
            candidates.append(path)
    for pattern in ("**/CANDIDATE_RECORD.json", "**/phase2_e2_best_candidates_report.json"):
        for path in sorted(bundle_dir.glob(pattern), key=lambda p: str(p)):
            if path.is_file():
                candidates.append(path)
    seen: set[str] = set()
    for path in sorted(candidates, key=lambda p: str(p)):
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        yield path


def _resolve_candidate_payload(
    *,
    bundle_dir: Optional[Path],
    candidate_record: Optional[Path],
) -> Tuple[Dict[str, Any], str, str]:
    if candidate_record is not None:
        payload = _read_json(candidate_record)
        return payload, str(candidate_record.name), str(candidate_record.resolve())
    assert bundle_dir is not None
    for path in _iter_candidate_json_paths(bundle_dir):
        payload = _read_json(path)
        try:
            rel = path.resolve().relative_to(bundle_dir.resolve()).as_posix()
        except Exception:
            rel = path.name
        candidate = _extract_candidate_from_payload(payload)
        if candidate.get("rs_approx_mpc") is not None or candidate.get("z_star_approx") is not None:
            return payload, rel, str(path.resolve())
        # keep first as fallback
        return payload, rel, str(path.resolve())
    raise SystemExit(f"No candidate JSON payload found in bundle directory: {bundle_dir}")


def _extract_reference_from_text(path: Path) -> Tuple[Optional[float], Optional[float]]:
    rs_value: Optional[float] = None
    zstar_value: Optional[float] = None
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None, None
    for line in text.splitlines():
        if rs_value is None:
            m_rs = _RS_RE.search(line)
            if m_rs is not None:
                rs_value = _finite_float(m_rs.group(1))
        if zstar_value is None:
            m_z = _ZSTAR_RE.search(line)
            if m_z is not None:
                zstar_value = _finite_float(m_z.group(1))
        if rs_value is not None and zstar_value is not None:
            break
    return rs_value, zstar_value


def _extract_reference_from_run_dir(run_dir: Path) -> Dict[str, Any]:
    if not run_dir.is_dir():
        raise SystemExit(f"--run-dir is not a directory: {run_dir}")
    rs_ref: Optional[float] = None
    zstar_ref: Optional[float] = None
    rs_file: Optional[str] = None
    zstar_file: Optional[str] = None
    scanned: List[str] = []
    for path in sorted(run_dir.rglob("*"), key=lambda p: str(p)):
        if not path.is_file():
            continue
        if path.suffix.lower() not in _TEXT_EXTS:
            continue
        rel = path.relative_to(run_dir).as_posix()
        scanned.append(rel)
        rs_candidate, zstar_candidate = _extract_reference_from_text(path)
        if rs_ref is None and rs_candidate is not None:
            rs_ref = float(rs_candidate)
            rs_file = rel
        if zstar_ref is None and zstar_candidate is not None:
            zstar_ref = float(zstar_candidate)
            zstar_file = rel
        if rs_ref is not None and zstar_ref is not None:
            break
    return {
        "available": bool(rs_ref is not None and zstar_ref is not None),
        "rs_ref_mpc": rs_ref,
        "z_star_ref": zstar_ref,
        "rs_source_file": rs_file,
        "z_star_source_file": zstar_file,
        "n_scanned_files": int(len(scanned)),
    }


def _comparison_block(*, candidate: Mapping[str, Any], reference: Mapping[str, Any]) -> Dict[str, Any]:
    rs_approx = _finite_float(candidate.get("rs_approx_mpc"))
    zstar_approx = _finite_float(candidate.get("z_star_approx"))
    rs_ref = _finite_float(reference.get("rs_ref_mpc"))
    zstar_ref = _finite_float(reference.get("z_star_ref"))
    delta_rs = None if rs_approx is None or rs_ref is None else float(rs_approx - rs_ref)
    frac_rs = None if delta_rs is None or rs_ref == 0.0 else float(delta_rs / rs_ref)
    delta_zstar = None if zstar_approx is None or zstar_ref is None else float(zstar_approx - zstar_ref)
    frac_zstar = None if delta_zstar is None or zstar_ref == 0.0 else float(delta_zstar / zstar_ref)
    return {
        "delta_rs_mpc": delta_rs,
        "frac_rs": frac_rs,
        "delta_z_star": delta_zstar,
        "frac_z_star": frac_zstar,
    }


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_to_json_safe(payload), sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, lines: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _render_text_summary(payload: Mapping[str, Any]) -> List[str]:
    candidate = _as_mapping(payload.get("candidate"))
    reference = _as_mapping(payload.get("reference"))
    comparison = _as_mapping(payload.get("comparison"))
    gates = _as_mapping(payload.get("gates"))
    return [
        "RS/Z* reference audit",
        f"schema={payload.get('schema')}",
        f"created_utc={payload.get('created_utc')}",
        f"candidate_params_hash={candidate.get('params_hash')}",
        f"candidate_rs_approx_mpc={candidate.get('rs_approx_mpc')}",
        f"candidate_z_star_approx={candidate.get('z_star_approx')}",
        f"reference_available={reference.get('available')}",
        f"reference_rs_mpc={reference.get('rs_ref_mpc')}",
        f"reference_z_star={reference.get('z_star_ref')}",
        f"delta_rs_mpc={comparison.get('delta_rs_mpc')}",
        f"delta_z_star={comparison.get('delta_z_star')}",
        f"gate_ok={gates.get('ok')}",
        f"gate_marker={gates.get('marker')}",
        "scope_note=audit_only_not_full_boltzmann_validation",
    ]


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="phase2_cmb_rs_zstar_reference_audit",
        description="Audit approximate rs(z*)/z* values against external CLASS/CAMB references when available.",
    )
    source = ap.add_mutually_exclusive_group(required=True)
    source.add_argument("--bundle-dir", type=Path, default=None, help="Bundle directory with candidate artifacts.")
    source.add_argument("--candidate-record", type=Path, default=None, help="Candidate JSON payload path.")
    ap.add_argument("--run-dir", type=Path, default=None, help="External CLASS/CAMB run output directory.")
    ap.add_argument("--out", type=Path, default=None, help="Output JSON path (default: <bundle-dir>/RS_ZSTAR_REFERENCE_AUDIT.json).")
    ap.add_argument("--summary-out", type=Path, default=None, help="Optional text summary output path.")
    ap.add_argument("--created-utc", type=str, default=DEFAULT_CREATED_UTC, help="Deterministic UTC timestamp.")
    ap.add_argument("--strict", action="store_true", help="Exit 2 when references are unavailable.")
    ap.add_argument(
        "--include-absolute-paths",
        action="store_true",
        help="Include absolute source/run paths in payload (default: redacted portable paths).",
    )
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args(argv)

    created_utc = _normalize_created_utc(args.created_utc)
    bundle_dir = None if args.bundle_dir is None else args.bundle_dir.expanduser().resolve()
    candidate_record = None if args.candidate_record is None else args.candidate_record.expanduser().resolve()
    run_dir = None if args.run_dir is None else args.run_dir.expanduser().resolve()

    if candidate_record is not None and run_dir is None:
        raise SystemExit("--candidate-record requires --run-dir for reference audit context.")
    if bundle_dir is not None and not bundle_dir.is_dir():
        raise SystemExit(f"--bundle-dir is not a directory: {bundle_dir}")

    payload_raw, payload_source, payload_source_abs = _resolve_candidate_payload(
        bundle_dir=bundle_dir,
        candidate_record=candidate_record,
    )
    candidate = _extract_candidate_from_payload(payload_raw)

    if run_dir is None:
        reference = {
            "available": False,
            "rs_ref_mpc": None,
            "z_star_ref": None,
            "rs_source_file": None,
            "z_star_source_file": None,
            "n_scanned_files": 0,
            "reason": "run_dir_not_provided",
        }
    else:
        reference = _extract_reference_from_run_dir(run_dir)
        if not bool(reference.get("available")):
            reference["reason"] = "reference_values_not_found"

    comparison = _comparison_block(candidate=candidate, reference=reference)
    gate_ok = bool(reference.get("available")) or (not bool(args.strict))
    gate_marker = None
    if not gate_ok:
        gate_marker = "MISSING_RS_ZSTAR_REFERENCE_FOR_AUDIT"

    report = {
        "schema": SCHEMA,
        "created_utc": str(created_utc),
        "paths_redacted": not bool(args.include_absolute_paths),
        "source": {
            "bundle_dir": None if bundle_dir is None else ".",
            "candidate_payload": str(payload_source),
            "run_dir": None if run_dir is None else ".",
        },
        "candidate": dict(candidate),
        "reference": dict(reference),
        "comparison": dict(comparison),
        "gates": {
            "strict": bool(args.strict),
            "ok": bool(gate_ok),
            "marker": gate_marker,
        },
        "notes": [
            "audit_only",
            "no_in_repo_boltzmann_spectra_computation",
        ],
    }
    if bool(args.include_absolute_paths):
        report["source"]["candidate_payload_abs"] = str(payload_source_abs)
        if bundle_dir is not None:
            report["source"]["bundle_dir_abs"] = str(bundle_dir)
        if run_dir is not None:
            report["source"]["run_dir_abs"] = str(run_dir)

    if args.out is not None:
        out_json = args.out.expanduser().resolve()
    elif bundle_dir is not None:
        out_json = (bundle_dir / "RS_ZSTAR_REFERENCE_AUDIT.json").resolve()
    else:
        out_json = (candidate_record.parent / "RS_ZSTAR_REFERENCE_AUDIT.json").resolve()  # type: ignore[union-attr]
    summary_out = (
        args.summary_out.expanduser().resolve()
        if args.summary_out is not None
        else out_json.with_suffix(".txt")
    )
    lines = _render_text_summary(report)
    _write_json(out_json, report)
    _write_text(summary_out, lines)

    if args.format == "json":
        print(json.dumps(_to_json_safe(report), sort_keys=True, ensure_ascii=False, indent=2))
    else:
        for line in lines:
            print(line)

    if not gate_ok:
        if gate_marker is not None:
            print(gate_marker, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

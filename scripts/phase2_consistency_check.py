#!/usr/bin/env python3
"""Deterministic cross-module consistency checkpoint for Phase-2 artifacts.

This tool performs broad presence/sanity checks only. It does not compute
physics or certify model validity.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


TOOL = "phase2_consistency_check"
SCHEMA = "phase2_consistency_report_v1"
CANDIDATE_FILENAME = "CANDIDATE_RECORD.json"
BEST_CANDIDATES_FILENAME = "phase2_e2_best_candidates_report.json"
CERTIFICATE_FILENAME = "e2_certificate.json"
RESULTS_SUMMARY_FILENAME = "RESULTS_SUMMARY.json"
CONSISTENCY_JSON_NAME = "CONSISTENCY_REPORT.json"
CONSISTENCY_MD_NAME = "CONSISTENCY_REPORT.md"

RSD_CHI2_FIELDS: Tuple[str, ...] = ("rsd_chi2_total", "rsd_chi2", "rsd_chi2_min")
TT_EXTS: Tuple[str, ...] = (".dat", ".txt")


class ConsistencyUsageError(Exception):
    """Usage/input error."""


def _normalize_created_utc(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ConsistencyUsageError("--created-utc is required")
    try:
        parsed = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ConsistencyUsageError("--created-utc must match YYYY-MM-DDTHH:MM:SSZ") from exc
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip("\n") + "\n", encoding="utf-8")


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, Mapping):
        return None
    return {str(k): payload[k] for k in payload.keys()}


def _finite_float(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except Exception:
        return None
    if not math.isfinite(out):
        return None
    return float(out)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _has_any_key(mapping: Mapping[str, Any], keys: Sequence[str]) -> bool:
    for key in keys:
        if key in mapping:
            return True
    return False


def _extract_candidate_payload(best_payload: Mapping[str, Any]) -> Mapping[str, Any]:
    for key in ("best_by_joint", "best_by_cmb", "best_cmb", "best_joint"):
        nested = _mapping(best_payload.get(key))
        if nested:
            return nested
    rows = best_payload.get("rows")
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, Mapping):
                return row
    return {}


def _extract_probe_values(candidate: Mapping[str, Any]) -> Dict[str, Optional[float]]:
    params = _mapping(candidate.get("params"))
    out: Dict[str, Optional[float]] = {
        "H0": _finite_float(candidate.get("H0")),
        "Omega_m": _finite_float(candidate.get("Omega_m")),
        "omega_b_h2": _finite_float(candidate.get("omega_b_h2")),
        "omega_c_h2": _finite_float(candidate.get("omega_c_h2")),
        "n_s": _finite_float(candidate.get("n_s")),
        "k_pivot_mpc": _finite_float(candidate.get("k_pivot_mpc")),
        "rsd_chi2_total": _finite_float(candidate.get("rsd_chi2_total")),
        "rsd_chi2": _finite_float(candidate.get("rsd_chi2")),
        "rsd_chi2_min": _finite_float(candidate.get("rsd_chi2_min")),
    }
    for key in ("H0", "Omega_m", "omega_b_h2", "omega_c_h2"):
        if out.get(key) is None:
            out[key] = _finite_float(params.get(key))
    if out.get("n_s") is None:
        out["n_s"] = _finite_float(candidate.get("primordial_ns"))
    if out.get("k_pivot_mpc") is None:
        out["k_pivot_mpc"] = _finite_float(candidate.get("primordial_k_pivot_mpc"))
    return out


def _find_first_numeric_columns(path: Path, *, max_lines: int = 256) -> Dict[str, Any]:
    parsed_rows = 0
    ell_min: Optional[float] = None
    ell_max: Optional[float] = None
    neg_power = 0
    parse_errors = 0
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for raw_idx, raw_line in enumerate(fh, start=1):
            if raw_idx > int(max_lines):
                break
            text = str(raw_line).strip()
            if not text or text.startswith("#"):
                continue
            tokens = text.split()
            if len(tokens) < 2:
                parse_errors += 1
                continue
            ell = _finite_float(tokens[0])
            power = _finite_float(tokens[1])
            if ell is None or power is None:
                parse_errors += 1
                continue
            parsed_rows += 1
            ell_min = ell if ell_min is None else min(ell_min, ell)
            ell_max = ell if ell_max is None else max(ell_max, ell)
            if power < 0.0:
                neg_power += 1
    return {
        "n_rows_parsed": int(parsed_rows),
        "ell_min": ell_min,
        "ell_max": ell_max,
        "n_negative_power": int(neg_power),
        "n_parse_errors": int(parse_errors),
    }


def _render_md(payload: Mapping[str, Any]) -> str:
    summary = _mapping(payload.get("summary"))
    presence = _mapping(payload.get("presence"))
    checks = payload.get("checks")
    if not isinstance(checks, list):
        checks = []
    probe = _mapping(payload.get("numeric_probe"))
    lines: List[str] = []
    lines.append("# CONSISTENCY REPORT")
    lines.append("")
    lines.append(f"- `schema`: {payload.get('schema', '')}")
    lines.append(f"- `created_utc`: {payload.get('created_utc', '')}")
    lines.append(f"- `bundle_dir`: `{payload.get('bundle_dir', '')}`")
    lines.append(f"- `strict`: {bool(payload.get('strict', False))}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- `status`: {payload.get('status', '')}")
    lines.append(f"- `exit_code`: {summary.get('exit_code')}")
    lines.append(f"- `n_errors`: {summary.get('n_errors')}")
    lines.append(f"- `n_warnings`: {summary.get('n_warnings')}")
    lines.append("")
    lines.append("## Presence")
    lines.append("")
    lines.append(f"- `candidate_present`: {presence.get('candidate_present')}")
    lines.append(f"- `rsd_expected`: {presence.get('rsd_expected')}")
    lines.append(f"- `pt_results_present`: {presence.get('pt_results_present')}")
    lines.append("")
    lines.append("## Checks")
    lines.append("")
    lines.append("| name | severity | ok | detail |")
    lines.append("|---|---|---:|---|")
    for item in checks:
        row = _mapping(item)
        name = str(row.get("name", ""))
        severity = str(row.get("severity", ""))
        ok = bool(row.get("ok", False))
        detail = str(row.get("detail", "")).replace("\n", " ")
        lines.append(f"| {name} | {severity} | {str(ok).lower()} | {detail} |")
    lines.append("")
    lines.append("## Numeric Probe")
    lines.append("")
    for key in sorted(probe.keys()):
        lines.append(f"- `{key}`: {probe.get(key)}")
    lines.append("")
    lines.append(
        "Scope note: this is a deterministic presence/sanity checkpoint only; "
        "it does not compute spectra or certify full likelihood validity."
    )
    return "\n".join(lines)


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Deterministic Phase-2 consistency checkpoint report.")
    ap.add_argument("--bundle-dir", required=True, help="Bundle/artifacts directory to inspect.")
    ap.add_argument("--outdir", default=None, help="Output directory (default: <bundle-dir>/consistency).")
    ap.add_argument("--created-utc", required=True, help="Deterministic UTC timestamp (YYYY-MM-DDTHH:MM:SSZ).")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    ap.add_argument("--strict", action="store_true", help="Treat WARN checks as gate failures (exit 2).")
    return ap.parse_args(argv)


def _check_range(
    *,
    checks: List[Dict[str, Any]],
    key: str,
    value: Optional[float],
    min_value: float,
    max_value: float,
) -> None:
    if value is None:
        return
    ok = bool(min_value <= float(value) <= max_value)
    checks.append(
        {
            "name": f"numeric_range_{key}",
            "severity": "warn",
            "ok": ok,
            "detail": f"value={value:.12g} range=[{min_value:.12g}, {max_value:.12g}]",
        }
    )


def _find_tt_candidates(bundle_dir: Path) -> List[Path]:
    matches: List[Path] = []
    for path in sorted(bundle_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in TT_EXTS:
            continue
        name = path.name.lower()
        if "tt" in name:
            matches.append(path)
    return matches


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        created_utc = _normalize_created_utc(str(args.created_utc))
        bundle_dir = Path(str(args.bundle_dir)).expanduser().resolve()
        if not bundle_dir.is_dir():
            raise ConsistencyUsageError(f"--bundle-dir must be an existing directory: {bundle_dir}")
        outdir = (
            Path(str(args.outdir)).expanduser().resolve()
            if args.outdir is not None
            else (bundle_dir / "consistency").resolve()
        )
    except ConsistencyUsageError as exc:
        print(f"ERROR: {exc}")
        return 1

    checks: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    candidate_files = sorted(bundle_dir.rglob(CANDIDATE_FILENAME))
    best_files = sorted(bundle_dir.rglob(BEST_CANDIDATES_FILENAME))
    cert_files = sorted(bundle_dir.rglob(CERTIFICATE_FILENAME))
    results_files = sorted(bundle_dir.rglob(RESULTS_SUMMARY_FILENAME))
    rsd_summary_present = any(p.is_file() for p in bundle_dir.rglob("phase2_sf_rsd_summary.md")) or any(
        p.is_file() for p in bundle_dir.rglob("phase2_sf_rsd_summary.tex")
    )

    candidate_source_paths: List[str] = []
    candidate_payload: Mapping[str, Any] = {}
    if candidate_files:
        candidate_source_paths.append(str(candidate_files[0].relative_to(bundle_dir).as_posix()))
        candidate_payload = _mapping(_load_json(candidate_files[0]))
    elif best_files:
        candidate_source_paths.append(str(best_files[0].relative_to(bundle_dir).as_posix()))
        candidate_payload = _extract_candidate_payload(_mapping(_load_json(best_files[0])))
    elif cert_files:
        candidate_source_paths.append(str(cert_files[0].relative_to(bundle_dir).as_posix()))
        candidate_payload = _extract_candidate_payload(_mapping(_load_json(cert_files[0])))

    candidate_present = bool(candidate_payload)
    checks.append(
        {
            "name": "candidate_presence",
            "severity": "error",
            "ok": candidate_present,
            "detail": (
                f"found candidate source: {candidate_source_paths[0]}"
                if candidate_present and candidate_source_paths
                else "missing candidate source (expected one of CANDIDATE_RECORD.json / best-candidates report / certificate)"
            ),
        }
    )

    probe = _extract_probe_values(candidate_payload) if candidate_present else {}
    rsd_expected = bool(rsd_summary_present or _has_any_key(candidate_payload, RSD_CHI2_FIELDS))
    has_rsd_chi2 = any(_finite_float(candidate_payload.get(field)) is not None for field in RSD_CHI2_FIELDS)
    if not has_rsd_chi2 and best_files:
        best_payload = _mapping(_load_json(best_files[0]))
        candidate_from_best = _extract_candidate_payload(best_payload)
        has_rsd_chi2 = any(_finite_float(candidate_from_best.get(field)) is not None for field in RSD_CHI2_FIELDS)
        if not candidate_payload and candidate_from_best:
            candidate_payload = candidate_from_best
            probe = _extract_probe_values(candidate_payload)
    checks.append(
        {
            "name": "rsd_chi2_presence_when_expected",
            "severity": "warn",
            "ok": (not rsd_expected) or bool(has_rsd_chi2),
            "detail": (
                "RSD chi2 field present"
                if (not rsd_expected) or bool(has_rsd_chi2)
                else "RSD section detected but no rsd_chi2_total/rsd_chi2/rsd_chi2_min found"
            ),
        }
    )

    _check_range(checks=checks, key="H0", value=probe.get("H0"), min_value=30.0, max_value=120.0)
    _check_range(checks=checks, key="Omega_m", value=probe.get("Omega_m"), min_value=0.0, max_value=1.5)
    _check_range(checks=checks, key="omega_b_h2", value=probe.get("omega_b_h2"), min_value=0.0, max_value=1.0)
    _check_range(checks=checks, key="omega_c_h2", value=probe.get("omega_c_h2"), min_value=0.0, max_value=2.0)
    _check_range(checks=checks, key="n_s", value=probe.get("n_s"), min_value=0.0, max_value=2.0)
    _check_range(checks=checks, key="k_pivot_mpc", value=probe.get("k_pivot_mpc"), min_value=1.0e-5, max_value=10.0)

    pt_results_present = bool(results_files)
    tt_candidates = _find_tt_candidates(bundle_dir) if pt_results_present else []
    checks.append(
        {
            "name": "tt_spectrum_presence_when_pt_results_present",
            "severity": "warn",
            "ok": (not pt_results_present) or bool(tt_candidates),
            "detail": (
                "TT-like spectrum file found"
                if (not pt_results_present) or bool(tt_candidates)
                else "RESULTS_SUMMARY.json detected but no TT-like .dat/.txt file found"
            ),
        }
    )

    tt_probe: Dict[str, Any] = {}
    if tt_candidates:
        tt_probe = _find_first_numeric_columns(tt_candidates[0], max_lines=256)
        checks.append(
            {
                "name": "tt_spectrum_parse_sanity",
                "severity": "warn",
                "ok": int(tt_probe.get("n_rows_parsed", 0)) > 0 and int(tt_probe.get("n_negative_power", 0)) == 0,
                "detail": (
                    f"path={tt_candidates[0].relative_to(bundle_dir).as_posix()} "
                    f"rows={tt_probe.get('n_rows_parsed')} parse_errors={tt_probe.get('n_parse_errors')} "
                    f"negative_power={tt_probe.get('n_negative_power')}"
                ),
            }
        )

    for item in checks:
        severity = str(item.get("severity", "")).lower()
        ok = bool(item.get("ok", False))
        if ok:
            continue
        if severity == "error":
            errors.append(item)
        else:
            warnings.append(item)

    if errors:
        status = "fail"
        exit_code = 2
    elif warnings:
        status = "warn"
        exit_code = 2 if bool(args.strict) else 0
    else:
        status = "ok"
        exit_code = 0

    payload: Dict[str, Any] = {
        "schema": SCHEMA,
        "tool": TOOL,
        "created_utc": created_utc,
        "bundle_dir": ".",
        "strict": bool(args.strict),
        "status": status,
        "summary": {
            "n_errors": int(len(errors)),
            "n_warnings": int(len(warnings)),
            "exit_code": int(exit_code),
        },
        "presence": {
            "candidate_present": bool(candidate_present),
            "rsd_expected": bool(rsd_expected),
            "pt_results_present": bool(pt_results_present),
        },
        "candidate_sources": sorted(candidate_source_paths),
        "checks": [
            {
                "name": str(row.get("name", "")),
                "severity": str(row.get("severity", "")),
                "ok": bool(row.get("ok", False)),
                "detail": str(row.get("detail", "")),
            }
            for row in checks
        ],
        "numeric_probe": {str(k): probe[k] for k in sorted(probe.keys())},
        "tt_probe": {str(k): tt_probe[k] for k in sorted(tt_probe.keys())} if tt_probe else {},
        "notes": [
            "sanity/traceability checkpoint only",
            "no full-spectrum likelihood claim",
            "deterministic output with fixed created_utc",
        ],
    }

    json_path = outdir / CONSISTENCY_JSON_NAME
    md_path = outdir / CONSISTENCY_MD_NAME
    _write_json(json_path, payload)
    _write_text(md_path, _render_md(payload))

    if str(args.format) == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"status={status}")
        print(f"bundle_dir={bundle_dir}")
        print(f"errors={len(errors)} warnings={len(warnings)} strict={bool(args.strict)}")
        print(f"json={json_path}")
        print(f"md={md_path}")

    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())

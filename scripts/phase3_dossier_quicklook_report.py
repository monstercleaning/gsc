#!/usr/bin/env python3
"""Deterministic quicklook aggregation over Phase-3 candidate dossier packs."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


TOOL = "phase3_dossier_quicklook_report"
SCHEMA = "phase3_sigmatensor_candidate_dossier_quicklook_v1"
DOSSIER_SCHEMA = "phase3_sigmatensor_candidate_dossier_manifest_v1"
FAIL_MARKER = "PHASE3_DOSSIER_QUICKLOOK_FAILED"
DEFAULT_CREATED_UTC = "2000-01-01T00:00:00Z"
CREATED_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
CSV_FLOAT_FMT = "{:.12e}"


class UsageError(Exception):
    """Usage/configuration error (exit 1)."""


class GateError(Exception):
    """Gate failure (exit 2)."""


def _json_pretty(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def _normalize_created_utc(raw: str) -> str:
    text = str(raw or "").strip()
    if not CREATED_UTC_RE.match(text):
        raise UsageError("--created-utc must match YYYY-MM-DDTHH:MM:SSZ")
    try:
        parsed = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise UsageError("--created-utc must match YYYY-MM-DDTHH:MM:SSZ") from exc
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _to_float(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except Exception:
        return None
    if not math.isfinite(out):
        return None
    return float(out)


def _to_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return int(value)
    v = _to_float(value)
    if v is None:
        return None
    iv = int(v)
    if float(iv) == float(v):
        return iv
    return None


def _fmt_float(value: Optional[float]) -> str:
    if value is None or not math.isfinite(float(value)):
        return "nan"
    return CSV_FLOAT_FMT.format(float(value))


def _fmt_bool(value: Optional[bool]) -> str:
    if value is True:
        return "1"
    if value is False:
        return "0"
    return "nan"


def _fmt_int(value: Optional[int]) -> str:
    if value is None:
        return "nan"
    return str(int(value))


def _parse_json_file(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise UsageError(f"failed to parse JSON {path.name}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise UsageError(f"JSON root must be object: {path.name}")
    return payload


def _try_parse_optional_json(path: Path, missing_files: List[str], relpath: str) -> Optional[Mapping[str, Any]]:
    if not path.is_file():
        missing_files.append(str(relpath))
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        missing_files.append(f"{relpath}(parse_error)")
        return None
    if not isinstance(payload, Mapping):
        missing_files.append(f"{relpath}(parse_error)")
        return None
    return payload


def _candidate_sort_key(row: Mapping[str, Any]) -> Tuple[int, str]:
    rank = _to_int(row.get("rank"))
    return (
        int(rank) if rank is not None else 10**9,
        str(row.get("outdir_rel") or ""),
    )


def _empty_metrics() -> Dict[str, Any]:
    return {
        "chi2_total": None,
        "ndof_total": None,
        "chi2_per_dof": None,
        "delta_chi2_total": None,
        "chi2_blocks": {
            "bao": None,
            "sn": None,
            "cmb": None,
            "rsd": None,
        },
        "fsigma8": {
            "rsd_chi2": None,
            "sigma8_0_used": None,
            "sigma8_0_bestfit": None,
        },
        "class_mapping": {
            "max_rel_E": None,
            "rms_dw": None,
            "max_abs_dOmega_phi": None,
            "gates_pass": None,
        },
        "spectra": {
            "has_tt": None,
            "ell_max": None,
            "peak1_ell": None,
        },
    }


def _extract_joint(metrics: Dict[str, Any], payload: Mapping[str, Any]) -> None:
    total = _as_mapping(payload.get("total"))
    chi2_total = _to_float(total.get("chi2"))
    ndof_total = _to_int(total.get("ndof"))
    metrics["chi2_total"] = chi2_total
    metrics["ndof_total"] = ndof_total
    if chi2_total is not None and ndof_total is not None and ndof_total > 0:
        metrics["chi2_per_dof"] = float(chi2_total) / float(ndof_total)
    deltas = _as_mapping(payload.get("deltas"))
    metrics["delta_chi2_total"] = _to_float(deltas.get("delta_chi2_total"))

    blocks = _as_mapping(payload.get("blocks"))
    for key in ("bao", "sn", "cmb", "rsd"):
        block = _as_mapping(blocks.get(key))
        metrics["chi2_blocks"][key] = _to_float(block.get("chi2"))


def _extract_fsigma8(metrics: Dict[str, Any], payload: Mapping[str, Any]) -> None:
    rsd = _as_mapping(payload.get("rsd"))
    sigma8 = _as_mapping(payload.get("sigma8"))
    metrics["fsigma8"]["rsd_chi2"] = _to_float(rsd.get("chi2"))
    metrics["fsigma8"]["sigma8_0_used"] = _to_float(sigma8.get("sigma8_0_used"))
    metrics["fsigma8"]["sigma8_0_bestfit"] = _to_float(sigma8.get("sigma8_0_bestfit"))


def _extract_mapping(metrics: Dict[str, Any], payload: Mapping[str, Any]) -> None:
    residuals = _as_mapping(payload.get("residuals"))
    e_res = _as_mapping(residuals.get("E"))
    w_res = _as_mapping(residuals.get("w"))
    om_res = _as_mapping(residuals.get("Omega_phi"))

    max_rel_e = _to_float(e_res.get("max_abs_rel"))
    if max_rel_e is None:
        max_rel_e = _to_float(e_res.get("max_abs_rel_E"))
    metrics["class_mapping"]["max_rel_E"] = max_rel_e

    rms_w = _to_float(w_res.get("rms_dw"))
    metrics["class_mapping"]["rms_dw"] = rms_w

    max_abs_dom = _to_float(om_res.get("max_abs"))
    if max_abs_dom is None:
        max_abs_dom = _to_float(om_res.get("max_abs_dOmega_phi"))
    metrics["class_mapping"]["max_abs_dOmega_phi"] = max_abs_dom

    gates = _as_mapping(payload.get("gates"))
    gates_pass = gates.get("pass")
    if isinstance(gates_pass, bool):
        metrics["class_mapping"]["gates_pass"] = bool(gates_pass)


def _extract_spectra(metrics: Dict[str, Any], payload: Mapping[str, Any]) -> None:
    tt = _as_mapping(payload.get("tt_metrics"))
    has_tt = tt.get("has_tt")
    if isinstance(has_tt, bool):
        metrics["spectra"]["has_tt"] = bool(has_tt)
    metrics["spectra"]["ell_max"] = _to_int(tt.get("ell_max"))
    metrics["spectra"]["peak1_ell"] = _to_float(tt.get("peak1_ell"))


def _collect_candidate(
    dossier_root: Path,
    row: Mapping[str, Any],
) -> Dict[str, Any]:
    rank = _to_int(row.get("rank"))
    outdir_rel = str(row.get("outdir_rel") or "").strip()
    if not outdir_rel:
        outdir_rel = ""
    status_raw = str(row.get("status") or "").strip().lower()
    status = "ok" if status_raw == "ok" else "error"
    plan_point_id = str(row.get("plan_point_id") or "").strip()

    metrics = _empty_metrics()
    missing_files: List[str] = []

    cand_dir = dossier_root / outdir_rel if outdir_rel else dossier_root

    joint_payload = _try_parse_optional_json(
        cand_dir / "joint" / "LOWZ_JOINT_REPORT.json",
        missing_files,
        "joint/LOWZ_JOINT_REPORT.json",
    )
    if joint_payload is not None:
        _extract_joint(metrics, joint_payload)

    fsigma_payload = _try_parse_optional_json(
        cand_dir / "fsigma8" / "FSIGMA8_REPORT.json",
        missing_files,
        "fsigma8/FSIGMA8_REPORT.json",
    )
    if fsigma_payload is not None:
        _extract_fsigma8(metrics, fsigma_payload)

    mapping_payload = _try_parse_optional_json(
        cand_dir / "class_mapping" / "CLASS_MAPPING_REPORT.json",
        missing_files,
        "class_mapping/CLASS_MAPPING_REPORT.json",
    )
    if mapping_payload is not None:
        _extract_mapping(metrics, mapping_payload)

    spectra_payload = _try_parse_optional_json(
        cand_dir / "spectra_sanity" / "SPECTRA_SANITY_REPORT.json",
        missing_files,
        "spectra_sanity/SPECTRA_SANITY_REPORT.json",
    )
    if spectra_payload is not None:
        _extract_spectra(metrics, spectra_payload)

    return {
        "rank": int(rank) if rank is not None else -1,
        "plan_point_id": str(plan_point_id),
        "status": str(status),
        "outdir_rel": str(outdir_rel),
        "metrics": metrics,
        "missing_files": list(missing_files),
    }


def _evaluate_gates(
    candidates: Sequence[Mapping[str, Any]],
    *,
    require_max_rel_e_le: Optional[float],
    require_rms_w_le: Optional[float],
    require_has_tt: Optional[int],
) -> Tuple[bool, List[str], Dict[str, Any]]:
    required: Dict[str, Any] = {
        "max_rel_E_le": float(require_max_rel_e_le) if require_max_rel_e_le is not None else None,
        "rms_w_le": float(require_rms_w_le) if require_rms_w_le is not None else None,
        "has_tt": int(require_has_tt) if require_has_tt is not None else None,
    }
    failures: List[str] = []

    for row in candidates:
        rank = int(row.get("rank", -1))
        plan_point_id = str(row.get("plan_point_id") or "")
        metrics = _as_mapping(row.get("metrics"))
        mapping = _as_mapping(metrics.get("class_mapping"))
        spectra = _as_mapping(metrics.get("spectra"))

        if require_max_rel_e_le is not None:
            value = _to_float(mapping.get("max_rel_E"))
            if value is None or float(value) > float(require_max_rel_e_le):
                failures.append(
                    f"rank={rank} plan_point_id={plan_point_id} max_rel_E={value!r} exceeds {float(require_max_rel_e_le):.12e}"
                )

        if require_rms_w_le is not None:
            value = _to_float(mapping.get("rms_dw"))
            if value is None or float(value) > float(require_rms_w_le):
                failures.append(
                    f"rank={rank} plan_point_id={plan_point_id} rms_dw={value!r} exceeds {float(require_rms_w_le):.12e}"
                )

        if require_has_tt == 1:
            has_tt = spectra.get("has_tt")
            if has_tt is not True:
                failures.append(f"rank={rank} plan_point_id={plan_point_id} has_tt is not true")

    return (len(failures) == 0), failures, required


def _build_digest(candidates: Sequence[Mapping[str, Any]]) -> str:
    rows: List[str] = []
    for row in candidates:
        metrics = _as_mapping(row.get("metrics"))
        mapping = _as_mapping(metrics.get("class_mapping"))
        spectra = _as_mapping(metrics.get("spectra"))
        rows.append(
            "{rank},{pid},{chi2},{dchi2},{max_rel_e},{rms_w},{has_tt},{ell_max}\n".format(
                rank=int(row.get("rank", -1)),
                pid=str(row.get("plan_point_id") or ""),
                chi2=_fmt_float(_to_float(metrics.get("chi2_total"))),
                dchi2=_fmt_float(_to_float(metrics.get("delta_chi2_total"))),
                max_rel_e=_fmt_float(_to_float(mapping.get("max_rel_E"))),
                rms_w=_fmt_float(_to_float(mapping.get("rms_dw"))),
                has_tt=_fmt_bool(spectra.get("has_tt") if isinstance(spectra.get("has_tt"), bool) else None),
                ell_max=_fmt_int(_to_int(spectra.get("ell_max"))),
            )
        )
    return _sha256_text("".join(rows))


def _build_csv(candidates: Sequence[Mapping[str, Any]]) -> str:
    lines: List[str] = [
        "rank,plan_point_id,status,chi2_total,ndof_total,chi2_per_dof,delta_chi2_total,"
        "chi2_bao,chi2_sn,chi2_cmb,chi2_rsd,"
        "map_max_rel_E,map_rms_dw,map_max_abs_dOmega_phi,"
        "has_tt,ell_max,peak1_ell"
    ]
    for row in candidates:
        metrics = _as_mapping(row.get("metrics"))
        blocks = _as_mapping(metrics.get("chi2_blocks"))
        mapping = _as_mapping(metrics.get("class_mapping"))
        spectra = _as_mapping(metrics.get("spectra"))
        lines.append(
            ",".join(
                [
                    str(int(row.get("rank", -1))),
                    str(row.get("plan_point_id") or ""),
                    str(row.get("status") or ""),
                    _fmt_float(_to_float(metrics.get("chi2_total"))),
                    _fmt_int(_to_int(metrics.get("ndof_total"))),
                    _fmt_float(_to_float(metrics.get("chi2_per_dof"))),
                    _fmt_float(_to_float(metrics.get("delta_chi2_total"))),
                    _fmt_float(_to_float(blocks.get("bao"))),
                    _fmt_float(_to_float(blocks.get("sn"))),
                    _fmt_float(_to_float(blocks.get("cmb"))),
                    _fmt_float(_to_float(blocks.get("rsd"))),
                    _fmt_float(_to_float(mapping.get("max_rel_E"))),
                    _fmt_float(_to_float(mapping.get("rms_dw"))),
                    _fmt_float(_to_float(mapping.get("max_abs_dOmega_phi"))),
                    _fmt_bool(spectra.get("has_tt") if isinstance(spectra.get("has_tt"), bool) else None),
                    _fmt_int(_to_int(spectra.get("ell_max"))),
                    _fmt_float(_to_float(spectra.get("peak1_ell"))),
                ]
            )
        )
    return "\n".join(lines) + "\n"


def _build_markdown(payload: Mapping[str, Any]) -> str:
    counts = _as_mapping(payload.get("counts"))
    candidates = payload.get("candidates") if isinstance(payload.get("candidates"), list) else []
    gates = _as_mapping(payload.get("gates"))
    top_rows = [row for row in candidates if isinstance(row, Mapping)][:10]

    lines: List[str] = []
    lines.append("# Candidate dossier quicklook (diagnostic)")
    lines.append("")
    lines.append("Scope boundary: this is an aggregate diagnostics view over candidate dossiers.")
    lines.append("No global-fit claim is implied.")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- created_utc: `{payload.get('created_utc')}`")
    lines.append(f"- candidates: `{int(counts.get('n_candidates', 0))}`")
    lines.append(f"- ok: `{int(counts.get('n_ok', 0))}`")
    lines.append(f"- error: `{int(counts.get('n_error', 0))}`")
    lines.append(f"- gates_pass: `{bool(gates.get('pass'))}`")
    lines.append("")
    lines.append("## Top rows by rank")
    lines.append("")
    lines.append("| rank | plan_point_id | status | chi2_total | delta_chi2_total | map_max_rel_E | map_rms_dw | has_tt |")
    lines.append("| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |")
    for row in top_rows:
        metrics = _as_mapping(row.get("metrics"))
        mapping = _as_mapping(metrics.get("class_mapping"))
        spectra = _as_mapping(metrics.get("spectra"))
        lines.append(
            "| {rank} | {pid} | {status} | {chi2} | {dchi2} | {max_rel_e} | {rms_w} | {has_tt} |".format(
                rank=int(row.get("rank", -1)),
                pid=str(row.get("plan_point_id") or ""),
                status=str(row.get("status") or ""),
                chi2=_fmt_float(_to_float(metrics.get("chi2_total"))),
                dchi2=_fmt_float(_to_float(metrics.get("delta_chi2_total"))),
                max_rel_e=_fmt_float(_to_float(mapping.get("max_rel_E"))),
                rms_w=_fmt_float(_to_float(mapping.get("rms_dw"))),
                has_tt=_fmt_bool(spectra.get("has_tt") if isinstance(spectra.get("has_tt"), bool) else None),
            )
        )
    if not top_rows:
        lines.append("| NA | NA | NA | NA | NA | NA | NA | NA |")
    lines.append("")
    lines.append("## Reproduce")
    lines.append("")
    lines.append("```bash")
    lines.append("python3 v11.0.0/scripts/phase3_dossier_quicklook_report.py \\")
    lines.append("  --dossier <dossier_dir> \\")
    lines.append("  --outdir <outdir> \\")
    lines.append("  --created-utc 2000-01-01T00:00:00Z \\")
    lines.append("  --format text")
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Deterministic quicklook report for Phase-3 candidate dossiers.")
    ap.add_argument("--dossier", type=Path, required=True)
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--created-utc", default=DEFAULT_CREATED_UTC)
    ap.add_argument("--format", choices=("text", "json"), default="text")
    ap.add_argument("--require-max-rel-E-le", type=float, default=None)
    ap.add_argument("--require-rms-w-le", type=float, default=None)
    ap.add_argument("--require-has-tt", choices=("0", "1"), default=None)
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        created_utc = _normalize_created_utc(str(args.created_utc))
        dossier_dir = Path(args.dossier).expanduser().resolve()
        if not dossier_dir.is_dir():
            raise GateError(f"--dossier must be an existing directory: {dossier_dir}")

        manifest_path = dossier_dir / "DOSSIER_MANIFEST.json"
        if not manifest_path.is_file():
            raise GateError("DOSSIER_MANIFEST.json missing in dossier directory")
        manifest = _parse_json_file(manifest_path)
        schema = str(manifest.get("schema") or "")
        if schema and schema != DOSSIER_SCHEMA:
            raise GateError(f"dossier manifest schema mismatch: {schema}")

        outdir = Path(args.outdir).expanduser().resolve()
        if outdir.exists() and not outdir.is_dir():
            raise UsageError(f"--outdir exists and is not a directory: {outdir}")
        outdir.mkdir(parents=True, exist_ok=True)

        manifest_candidates_raw = manifest.get("candidates")
        if not isinstance(manifest_candidates_raw, list):
            raise GateError("dossier manifest missing candidates list")

        ordered_candidates = sorted(
            [row for row in manifest_candidates_raw if isinstance(row, Mapping)],
            key=_candidate_sort_key,
        )

        candidates: List[Dict[str, Any]] = []
        for row in ordered_candidates:
            candidates.append(_collect_candidate(dossier_dir, row))

        n_candidates = int(len(candidates))
        n_ok = int(sum(1 for row in candidates if str(row.get("status")) == "ok"))
        n_error = int(n_candidates - n_ok)

        require_has_tt = None if args.require_has_tt is None else int(str(args.require_has_tt))
        gate_pass, gate_failures, gate_required = _evaluate_gates(
            candidates,
            require_max_rel_e_le=args.require_max_rel_E_le,
            require_rms_w_le=args.require_rms_w_le,
            require_has_tt=require_has_tt,
        )

        payload: Dict[str, Any] = {
            "schema": SCHEMA,
            "tool": TOOL,
            "created_utc": str(created_utc),
            "dossier_input": {
                "basename": str(manifest_path.name),
                "sha256": _sha256_file(manifest_path),
            },
            "counts": {
                "n_candidates": int(n_candidates),
                "n_ok": int(n_ok),
                "n_error": int(n_error),
            },
            "gates": {
                "required": gate_required,
                "pass": bool(gate_pass),
                "failures": list(gate_failures),
            },
            "candidates": candidates,
            "digests": {
                "stable_table_sha256": _build_digest(candidates),
            },
        }

        (outdir / "DOSSIER_QUICKLOOK.json").write_text(_json_pretty(payload), encoding="utf-8")
        (outdir / "DOSSIER_QUICKLOOK.csv").write_text(_build_csv(candidates), encoding="utf-8")
        (outdir / "DOSSIER_QUICKLOOK.md").write_text(_build_markdown(payload), encoding="utf-8")

        summary = {
            "schema": "phase3_sigmatensor_candidate_dossier_quicklook_summary_v1",
            "tool": TOOL,
            "created_utc": str(created_utc),
            "n_candidates": int(n_candidates),
            "n_ok": int(n_ok),
            "gates_pass": bool(gate_pass),
            "outdir": str(outdir.name),
        }

    except UsageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except GateError as exc:
        print(FAIL_MARKER, file=sys.stderr)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if str(args.format) == "json":
        sys.stdout.write(_json_pretty(summary))
    else:
        sys.stdout.write(
            "quicklook "
            f"n_candidates={int(summary['n_candidates'])} "
            f"n_ok={int(summary['n_ok'])} "
            f"gates_pass={bool(summary['gates_pass'])}\n"
        )

    if not bool(summary["gates_pass"]):
        print(FAIL_MARKER, file=sys.stderr)
        failures = payload.get("gates", {}).get("failures", [])
        if isinstance(failures, list) and failures:
            print(f"ERROR: {str(failures[0])}", file=sys.stderr)
        else:
            print("ERROR: quicklook gate failure", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

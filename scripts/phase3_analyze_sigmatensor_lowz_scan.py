#!/usr/bin/env python3
"""Deterministic analysis of Phase-3 LOWZ scan JSONL shards."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import sys
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gsc.jsonl_io import open_text_auto  # noqa: E402


TOOL = "phase3_analyze_sigmatensor_lowz_scan"
SCHEMA = "phase3_sigmatensor_lowz_scan_analysis_v1"
ROW_SCHEMA = "phase3_sigmatensor_lowz_scan_row_v1"
DEFAULT_CREATED_UTC = "2000-01-01T00:00:00Z"
EMPTY_MARKER = "PHASE3_LOWZ_SCAN_ANALYSIS_EMPTY"
CREATED_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
JSONL_SUFFIXES = (".jsonl", ".jsonl.gz")


class UsageError(Exception):
    """Usage/configuration or IO failure (exit code 1)."""


class GateError(Exception):
    """Ranking gate failure (exit code 2)."""


def _json_compact(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _json_pretty(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


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


def _normalize_created_utc(raw: str) -> str:
    text = str(raw or "").strip()
    if not CREATED_UTC_RE.match(text):
        raise UsageError("--created-utc must match YYYY-MM-DDTHH:MM:SSZ")
    try:
        parsed = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise UsageError("--created-utc must match YYYY-MM-DDTHH:MM:SSZ") from exc
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


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


def _is_jsonl_path(path: Path) -> bool:
    name = path.name.lower()
    return name.endswith(JSONL_SUFFIXES)


def _discover_input_files(tokens: Sequence[str]) -> List[Path]:
    if not tokens:
        raise UsageError("at least one --inputs path is required")
    out: List[Path] = []
    seen: Set[Path] = set()
    for token in tokens:
        path = Path(str(token)).expanduser()
        if not path.exists():
            raise UsageError(f"--inputs path not found: {token}")
        resolved = path.resolve()
        if resolved.is_file():
            if not _is_jsonl_path(resolved):
                raise UsageError(f"--inputs file must end with .jsonl or .jsonl.gz: {resolved.name}")
            if resolved not in seen:
                seen.add(resolved)
                out.append(resolved)
            continue
        if resolved.is_dir():
            for root, _dirs, files in os.walk(resolved):
                base = Path(root)
                for name in sorted(files):
                    candidate = base / name
                    if not candidate.is_file():
                        continue
                    if not _is_jsonl_path(candidate):
                        continue
                    rp = candidate.resolve()
                    if rp in seen:
                        continue
                    seen.add(rp)
                    out.append(rp)
            continue
        raise UsageError(f"--inputs path must be file or directory: {token}")
    return sorted(out, key=lambda p: (p.name, str(p)))


def _extract_chi2_total(payload: Mapping[str, Any]) -> Optional[float]:
    direct = _finite_float(payload.get("chi2_total"))
    if direct is not None:
        return direct
    results = _as_mapping(payload.get("results"))
    nested = _finite_float(results.get("chi2_total"))
    if nested is not None:
        return nested
    return None


def _extract_ndof_total(payload: Mapping[str, Any]) -> Optional[int]:
    direct = payload.get("ndof_total")
    if isinstance(direct, int) and not isinstance(direct, bool):
        return int(direct)
    results = _as_mapping(payload.get("results"))
    nested = results.get("ndof_total")
    if isinstance(nested, int) and not isinstance(nested, bool):
        return int(nested)
    return None


def _extract_metric(payload: Mapping[str, Any], metric: str) -> Optional[float]:
    metric_name = str(metric)
    if metric_name == "chi2_total":
        return _extract_chi2_total(payload)
    if metric_name == "delta_chi2_total":
        results = _as_mapping(payload.get("results"))
        deltas = _as_mapping(results.get("deltas"))
        return _finite_float(deltas.get("delta_chi2_total"))
    return None


def _extract_params(params_raw: Mapping[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key in (
        "Omega_m",
        "w0",
        "lambda",
        "H0_km_s_Mpc",
        "Tcmb_K",
        "N_eff",
        "Omega_r0_override",
        "sign_u0",
    ):
        value = params_raw.get(key)
        if key == "Omega_r0_override":
            out[key] = None if value is None else _finite_float(value)
            continue
        if key == "sign_u0":
            if isinstance(value, int) and not isinstance(value, bool):
                out[key] = int(value)
            else:
                out[key] = None
            continue
        out[key] = _finite_float(value)
    return out


def _sorted_float_dict(raw: Mapping[str, Any]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for key in sorted(str(k) for k in raw.keys()):
        value = _finite_float(raw.get(key))
        if value is None:
            continue
        out[str(key)] = float(value)
    return out


def _normalize_status(raw: Any) -> str:
    text = str(raw or "").strip().lower()
    return "ok" if text == "ok" else "error"


def _metric_or_inf(value: Optional[float]) -> float:
    return float(value) if value is not None and math.isfinite(value) else float("inf")


def _score_for_dedupe(
    *,
    status: str,
    metric_value: Optional[float],
    chi2_total: Optional[float],
    plan_point_id: str,
    canonical_row: str,
    source_name: str,
    source_line: int,
) -> Tuple[Any, ...]:
    return (
        0 if str(status) == "ok" else 1,
        _metric_or_inf(metric_value),
        _metric_or_inf(chi2_total),
        str(plan_point_id),
        str(canonical_row),
        str(source_name),
        int(source_line),
    )


def _score_for_ranking(
    *,
    metric_value: float,
    chi2_total: Optional[float],
    plan_point_id: str,
) -> Tuple[Any, ...]:
    return (
        float(metric_value),
        _metric_or_inf(chi2_total),
        str(plan_point_id),
    )


def _format_float(value: Optional[float]) -> str:
    if value is None or not math.isfinite(float(value)):
        return "nan"
    return f"{float(value):.12e}"


def _format_int_or_nan(value: Optional[int]) -> str:
    if value is None:
        return "nan"
    return str(int(value))


def _collect_rows(
    files: Sequence[Path],
    *,
    metric: str,
) -> Tuple[List[Dict[str, Any]], Dict[str, int], Set[str], Set[str]]:
    rows: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {
        "rows_total": 0,
        "rows_parsed": 0,
        "rows_invalid_json": 0,
        "rows_missing_plan_point_id": 0,
        "ok_rows": 0,
        "error_rows": 0,
    }
    plan_sources: Set[str] = set()
    scan_configs: Set[str] = set()

    for path in files:
        with open_text_auto(path, "r", encoding="utf-8", newline="") as fh:
            for lineno, raw in enumerate(fh, start=1):
                text = str(raw).strip()
                if not text:
                    continue
                counts["rows_total"] += 1
                try:
                    parsed = json.loads(text)
                except Exception:
                    counts["rows_invalid_json"] += 1
                    continue
                if not isinstance(parsed, Mapping):
                    counts["rows_invalid_json"] += 1
                    continue
                counts["rows_parsed"] += 1

                plan_point_id = str(parsed.get("plan_point_id") or "").strip()
                status = _normalize_status(parsed.get("status"))
                if status == "ok":
                    counts["ok_rows"] += 1
                else:
                    counts["error_rows"] += 1
                if not plan_point_id:
                    counts["rows_missing_plan_point_id"] += 1
                    continue

                plan_sha = str(parsed.get("plan_source_sha256") or "").strip()
                if plan_sha:
                    plan_sources.add(plan_sha)
                scan_sha = str(parsed.get("scan_config_sha256") or "").strip()
                if scan_sha:
                    scan_configs.add(scan_sha)

                results = _as_mapping(parsed.get("results"))
                chi2_blocks = _sorted_float_dict(_as_mapping(results.get("chi2_blocks")))
                nuisances = _sorted_float_dict(_as_mapping(results.get("nuisances")))
                deltas = _sorted_float_dict(_as_mapping(results.get("deltas")))
                params = _extract_params(_as_mapping(parsed.get("params")))

                metric_value = _extract_metric(parsed, metric)
                chi2_total = _extract_chi2_total(parsed)
                ndof_total = _extract_ndof_total(parsed)

                row_payload: Dict[str, Any] = {
                    "schema": str(parsed.get("schema") or ""),
                    "status": status,
                    "plan_point_id": plan_point_id,
                    "point_index": (
                        int(parsed.get("point_index"))
                        if isinstance(parsed.get("point_index"), int) and not isinstance(parsed.get("point_index"), bool)
                        else None
                    ),
                    "plan_source_sha256": plan_sha or None,
                    "scan_config_sha256": scan_sha or None,
                    "report_sha256": (
                        str(parsed.get("report_sha256")).strip()
                        if isinstance(parsed.get("report_sha256"), str) and str(parsed.get("report_sha256")).strip()
                        else None
                    ),
                    "metric_value": metric_value,
                    "chi2_total": chi2_total,
                    "ndof_total": ndof_total,
                    "chi2_blocks": chi2_blocks,
                    "nuisances": nuisances,
                    "deltas": deltas,
                    "params": params,
                    "source_name": path.name,
                    "source_line": int(lineno),
                    "source_basename": path.name,
                    "canonical_row": _json_compact({str(k): parsed[k] for k in parsed.keys()}),
                }
                rows.append(row_payload)

    return rows, counts, plan_sources, scan_configs


def _build_markdown(
    payload: Mapping[str, Any],
    *,
    metric_name: str,
) -> str:
    counts = _as_mapping(payload.get("counts"))
    best = payload.get("best_candidates")
    rows = best if isinstance(best, list) else []
    lines: List[str] = []
    lines.append("# Phase-3 LOWZ scan analysis (diagnostic)")
    lines.append("")
    lines.append("Scope boundary: deterministic triage ranking only; not a global fit claim.")
    lines.append("")
    lines.append("## Counts")
    lines.append("")
    lines.append(f"- rows_total: {int(counts.get('rows_total', 0))}")
    lines.append(f"- rows_parsed: {int(counts.get('rows_parsed', 0))}")
    lines.append(f"- rows_invalid_json: {int(counts.get('rows_invalid_json', 0))}")
    lines.append(f"- rows_missing_plan_point_id: {int(counts.get('rows_missing_plan_point_id', 0))}")
    lines.append(f"- dedup_unique_plan_point_id: {int(counts.get('dedup_unique_plan_point_id', 0))}")
    lines.append(f"- rank_candidates_considered: {int(counts.get('rank_candidates_considered', 0))}")
    lines.append(f"- rank_candidates_with_finite_metric: {int(counts.get('rank_candidates_with_finite_metric', 0))}")
    lines.append("")
    lines.append("## Top candidates")
    lines.append("")
    lines.append(
        "| rank | plan_point_id | Omega_m | w0 | lambda | chi2_total | ndof_total | metric | delta_chi2_total |"
    )
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        params = _as_mapping(row.get("params"))
        deltas = _as_mapping(row.get("deltas"))
        lines.append(
            "| "
            f"{int(row.get('rank', 0))} | "
            f"{str(row.get('plan_point_id', ''))} | "
            f"{_format_float(_finite_float(params.get('Omega_m')))} | "
            f"{_format_float(_finite_float(params.get('w0')))} | "
            f"{_format_float(_finite_float(params.get('lambda')))} | "
            f"{_format_float(_finite_float(row.get('chi2_total')))} | "
            f"{_format_int_or_nan(row.get('ndof_total') if isinstance(row.get('ndof_total'), int) else None)} | "
            f"{_format_float(_finite_float(row.get('metric_value')))} | "
            f"{_format_float(_finite_float(deltas.get('delta_chi2_total')))} |"
        )
    if not rows:
        lines.append("| NA | NA | NA | NA | NA | NA | NA | NA | NA |")
    lines.append("")
    lines.append(f"Ranking metric: `{metric_name}`.")
    lines.append("Tie-breaks: metric, then chi2_total, then plan_point_id.")
    lines.append("")
    return "\n".join(lines) + "\n"


def _build_csv_rows(best_candidates: Sequence[Mapping[str, Any]]) -> str:
    lines: List[str] = ["rank,plan_point_id,Omega_m,w0,lambda,chi2_total,ndof_total,delta_chi2_total"]
    for row in best_candidates:
        params = _as_mapping(row.get("params"))
        deltas = _as_mapping(row.get("deltas"))
        ndof = row.get("ndof_total")
        ndof_float = float(ndof) if isinstance(ndof, int) and not isinstance(ndof, bool) else None
        lines.append(
            ",".join(
                [
                    str(int(row.get("rank", 0))),
                    str(row.get("plan_point_id", "")),
                    _format_float(_finite_float(params.get("Omega_m"))),
                    _format_float(_finite_float(params.get("w0"))),
                    _format_float(_finite_float(params.get("lambda"))),
                    _format_float(_finite_float(row.get("chi2_total"))),
                    _format_float(ndof_float),
                    _format_float(_finite_float(deltas.get("delta_chi2_total"))),
                ]
            )
        )
    return "\n".join(lines) + "\n"


def _build_reproduce_script(
    best_candidates: Sequence[Mapping[str, Any]],
    *,
    created_utc: str,
    joint_extra_args: Sequence[str],
) -> str:
    lines: List[str] = []
    lines.append("#!/usr/bin/env bash")
    lines.append("set -euo pipefail")
    lines.append("")
    lines.append("# Deterministic reproduce commands for top LOWZ_JOINT candidates.")
    lines.append("# This script only re-runs report generation; it does not run CLASS/CAMB.")
    lines.append("mkdir -p out")
    lines.append("")
    for row in best_candidates:
        params = _as_mapping(row.get("params"))
        rank = int(row.get("rank", 0))
        pid = str(row.get("plan_point_id", ""))
        pid_short = (pid[:12] if pid else "unknown")
        outdir = f"out/cand_{rank:02d}_{pid_short}/joint"

        H0 = _finite_float(params.get("H0_km_s_Mpc"))
        omega_m = _finite_float(params.get("Omega_m"))
        w0 = _finite_float(params.get("w0"))
        lambda_ = _finite_float(params.get("lambda"))
        Tcmb_K = _finite_float(params.get("Tcmb_K"))
        N_eff = _finite_float(params.get("N_eff"))
        sign_u0 = params.get("sign_u0")
        omega_r0_override = params.get("Omega_r0_override")

        if None in (H0, omega_m, w0, lambda_, Tcmb_K, N_eff) or not isinstance(sign_u0, int):
            lines.append(f"# Skipped candidate rank={rank} plan_point_id={pid} (missing required params)")
            lines.append("")
            continue

        cmd: List[str] = [
            "python3",
            "v11.0.0/scripts/phase3_joint_sigmatensor_lowz_report.py",
            "--H0-km-s-Mpc",
            f"{float(H0):.17g}",
            "--Omega-m",
            f"{float(omega_m):.17g}",
            "--w0",
            f"{float(w0):.17g}",
            "--lambda",
            f"{float(lambda_):.17g}",
            "--Tcmb-K",
            f"{float(Tcmb_K):.17g}",
            "--N-eff",
            f"{float(N_eff):.17g}",
            "--sign-u0",
            str(int(sign_u0)),
        ]
        if omega_r0_override is not None:
            ovr = _finite_float(omega_r0_override)
            if ovr is not None:
                cmd.extend(["--Omega-r0-override", f"{float(ovr):.17g}"])
        for token in joint_extra_args:
            cmd.append(str(token))
        cmd.extend(
            [
                "--created-utc",
                str(created_utc),
                "--outdir",
                str(outdir),
                "--format",
                "text",
            ]
        )

        quoted = [shlex.quote(token) for token in cmd]
        lines.append(f"# rank={rank} plan_point_id={pid}")
        lines.append(f"mkdir -p {shlex.quote(outdir)}")
        lines.append(" ".join(quoted))
        lines.append("")
    lines.append("# Optional next step (manual): feed selected points to CLASS/CAMB bridge tooling.")
    lines.append("")
    return "\n".join(lines).replace("\n\n\n", "\n\n")


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Analyze Phase-3 LOWZ scan JSONL shards deterministically.")
    ap.add_argument("--inputs", action="append", required=True, help="Input JSONL(.gz) file or directory; repeatable")
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--metric", choices=("chi2_total", "delta_chi2_total"), default="chi2_total")
    ap.add_argument("--require-ok", choices=("0", "1"), default="1")
    ap.add_argument("--min-ndof", type=int, default=None)
    ap.add_argument("--emit-reproduce", choices=("0", "1"), default="1")
    ap.add_argument("--joint-extra-arg", action="append", default=[])
    ap.add_argument("--created-utc", default=DEFAULT_CREATED_UTC)
    ap.add_argument("--format", choices=("text", "json"), default="text")

    raw = list(sys.argv[1:] if argv is None else list(argv))
    normalized: List[str] = []
    i = 0
    while i < len(raw):
        token = str(raw[i])
        if token == "--joint-extra-arg":
            if i + 1 >= len(raw):
                ap.error("argument --joint-extra-arg: expected one argument")
            normalized.append(f"--joint-extra-arg={raw[i + 1]}")
            i += 2
            continue
        normalized.append(token)
        i += 1
    return ap.parse_args(normalized)


def _build_payload(
    *,
    args: argparse.Namespace,
    created_utc: str,
    input_files: Sequence[Path],
    rows: Sequence[Mapping[str, Any]],
    counts: Mapping[str, int],
    plan_sources: Set[str],
    scan_configs: Set[str],
) -> Dict[str, Any]:
    metric_name = str(args.metric)
    require_ok = str(args.require_ok) == "1"
    min_ndof = None if args.min_ndof is None else int(args.min_ndof)
    if min_ndof is not None and min_ndof < 0:
        raise UsageError("--min-ndof must be >= 0")
    top_k = int(args.top_k)
    if top_k < 1:
        raise UsageError("--top-k must be >= 1")

    inputs_meta: List[Dict[str, Any]] = []
    for path in input_files:
        inputs_meta.append(
            {
                "basename": str(path.name),
                "sha256": _sha256_file(path),
                "kind": "file",
            }
        )
    inputs_meta = sorted(inputs_meta, key=lambda r: (str(r["basename"]), str(r["sha256"])))

    selected_by_pid: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        pid = str(row.get("plan_point_id") or "")
        if not pid:
            continue
        current = selected_by_pid.get(pid)
        if current is None:
            selected_by_pid[pid] = dict(row)
            continue
        old_score = _score_for_dedupe(
            status=str(current.get("status", "error")),
            metric_value=_finite_float(current.get("metric_value")),
            chi2_total=_finite_float(current.get("chi2_total")),
            plan_point_id=pid,
            canonical_row=str(current.get("canonical_row", "")),
            source_name=str(current.get("source_name", "")),
            source_line=int(current.get("source_line", 0)),
        )
        new_score = _score_for_dedupe(
            status=str(row.get("status", "error")),
            metric_value=_finite_float(row.get("metric_value")),
            chi2_total=_finite_float(row.get("chi2_total")),
            plan_point_id=pid,
            canonical_row=str(row.get("canonical_row", "")),
            source_name=str(row.get("source_name", "")),
            source_line=int(row.get("source_line", 0)),
        )
        if new_score < old_score:
            selected_by_pid[pid] = dict(row)

    dedup_rows = [selected_by_pid[pid] for pid in sorted(selected_by_pid.keys())]

    considered: List[Dict[str, Any]] = []
    for row in dedup_rows:
        if require_ok and str(row.get("status", "error")) != "ok":
            continue
        ndof = row.get("ndof_total")
        if min_ndof is not None:
            if not isinstance(ndof, int) or bool(ndof < min_ndof):
                continue
        considered.append(row)

    with_finite_metric: List[Dict[str, Any]] = []
    for row in considered:
        metric_value = _finite_float(row.get("metric_value"))
        if metric_value is None:
            continue
        out = dict(row)
        out["metric_value"] = float(metric_value)
        with_finite_metric.append(out)

    with_finite_metric.sort(
        key=lambda row: _score_for_ranking(
            metric_value=float(row.get("metric_value")),
            chi2_total=_finite_float(row.get("chi2_total")),
            plan_point_id=str(row.get("plan_point_id")),
        )
    )
    top = with_finite_metric[:top_k]

    if not top:
        raise GateError("no candidates with finite metric after filtering")

    best_candidates: List[Dict[str, Any]] = []
    for idx, row in enumerate(top, start=1):
        chi2_total = _finite_float(row.get("chi2_total"))
        ndof_total = row.get("ndof_total") if isinstance(row.get("ndof_total"), int) else None
        chi2_per_dof = None
        if chi2_total is not None and isinstance(ndof_total, int) and ndof_total > 0:
            chi2_per_dof = float(chi2_total / float(ndof_total))
        params = _as_mapping(row.get("params"))
        candidate = {
            "rank": int(idx),
            "plan_point_id": str(row.get("plan_point_id")),
            "point_index": (int(row.get("point_index")) if isinstance(row.get("point_index"), int) else None),
            "metric_value": float(row.get("metric_value")),
            "chi2_total": chi2_total,
            "ndof_total": ndof_total,
            "chi2_per_dof": chi2_per_dof,
            "params": {
                "Omega_m": _finite_float(params.get("Omega_m")),
                "w0": _finite_float(params.get("w0")),
                "lambda": _finite_float(params.get("lambda")),
                "H0_km_s_Mpc": _finite_float(params.get("H0_km_s_Mpc")),
                "Tcmb_K": _finite_float(params.get("Tcmb_K")),
                "N_eff": _finite_float(params.get("N_eff")),
                "Omega_r0_override": _finite_float(params.get("Omega_r0_override")),
                "sign_u0": (
                    int(params.get("sign_u0"))
                    if isinstance(params.get("sign_u0"), int) and not isinstance(params.get("sign_u0"), bool)
                    else None
                ),
            },
            "chi2_blocks": _sorted_float_dict(_as_mapping(row.get("chi2_blocks"))),
            "nuisances": _sorted_float_dict(_as_mapping(row.get("nuisances"))),
            "deltas": _sorted_float_dict(_as_mapping(row.get("deltas"))),
            "plan_source_sha256": str(row.get("plan_source_sha256") or ""),
            "scan_config_sha256": str(row.get("scan_config_sha256") or ""),
            "report_sha256": str(row.get("report_sha256") or ""),
        }
        best_candidates.append(candidate)

    digest_rows: List[str] = []
    for row in best_candidates:
        params = _as_mapping(row.get("params"))
        digest_rows.append(
            ",".join(
                [
                    str(int(row.get("rank", 0))),
                    str(row.get("plan_point_id", "")),
                    _format_float(_finite_float(row.get("metric_value"))),
                    _format_float(_finite_float(row.get("chi2_total"))),
                    _format_float(
                        float(row.get("ndof_total"))
                        if isinstance(row.get("ndof_total"), int) and not isinstance(row.get("ndof_total"), bool)
                        else None
                    ),
                    _format_float(_finite_float(params.get("Omega_m"))),
                    _format_float(_finite_float(params.get("w0"))),
                    _format_float(_finite_float(params.get("lambda"))),
                ]
            )
            + "\n"
        )

    payload: Dict[str, Any] = {
        "schema": SCHEMA,
        "tool": TOOL,
        "created_utc": str(created_utc),
        "inputs": inputs_meta,
        "unique_plan_source_sha256": sorted(str(x) for x in plan_sources if str(x)),
        "unique_scan_config_sha256": sorted(str(x) for x in scan_configs if str(x)),
        "counts": {
            "rows_total": int(counts.get("rows_total", 0)),
            "rows_parsed": int(counts.get("rows_parsed", 0)),
            "rows_invalid_json": int(counts.get("rows_invalid_json", 0)),
            "rows_missing_plan_point_id": int(counts.get("rows_missing_plan_point_id", 0)),
            "ok_rows": int(counts.get("ok_rows", 0)),
            "error_rows": int(counts.get("error_rows", 0)),
            "dedup_unique_plan_point_id": int(len(dedup_rows)),
            "rank_candidates_considered": int(len(considered)),
            "rank_candidates_with_finite_metric": int(len(with_finite_metric)),
            "top_k_emitted": int(len(best_candidates)),
        },
        "metric": {
            "name": metric_name,
            "require_ok": bool(require_ok),
            "min_ndof": (None if min_ndof is None else int(min_ndof)),
        },
        "best_candidates": best_candidates,
        "digests": {
            "best_table_sha256": _sha256_text("".join(digest_rows)),
        },
    }
    return payload


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        created_utc = _normalize_created_utc(str(args.created_utc))
        input_files = _discover_input_files([str(x) for x in list(args.inputs or [])])
        rows, counts, plan_sources, scan_configs = _collect_rows(input_files, metric=str(args.metric))
        payload = _build_payload(
            args=args,
            created_utc=created_utc,
            input_files=input_files,
            rows=rows,
            counts=counts,
            plan_sources=plan_sources,
            scan_configs=scan_configs,
        )
    except UsageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except GateError as exc:
        print(EMPTY_MARKER, file=sys.stderr)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    outdir = Path(args.outdir).expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    json_path = outdir / "SCAN_ANALYSIS.json"
    md_path = outdir / "SCAN_ANALYSIS.md"
    csv_path = outdir / "BEST_CANDIDATES.csv"
    rep_path = outdir / "REPRODUCE_TOP_CANDIDATES.sh"

    json_text = _json_pretty(payload)
    md_text = _build_markdown(payload, metric_name=str(args.metric))
    csv_text = _build_csv_rows(payload.get("best_candidates", []) if isinstance(payload.get("best_candidates"), list) else [])

    json_path.write_text(json_text, encoding="utf-8")
    md_path.write_text(md_text, encoding="utf-8")
    csv_path.write_text(csv_text, encoding="utf-8")

    if str(args.emit_reproduce) == "1":
        script_text = _build_reproduce_script(
            payload.get("best_candidates", []) if isinstance(payload.get("best_candidates"), list) else [],
            created_utc=created_utc,
            joint_extra_args=[str(x) for x in list(args.joint_extra_arg or [])],
        )
        rep_path.write_text(script_text, encoding="utf-8")
        rep_path.chmod(0o755)

    if str(args.format) == "json":
        sys.stdout.write(json_text)
    else:
        best = payload.get("best_candidates", [])
        first = best[0] if isinstance(best, list) and best else {}
        summary = (
            "analysis "
            f"rows_parsed={int(payload['counts']['rows_parsed'])} "
            f"dedup={int(payload['counts']['dedup_unique_plan_point_id'])} "
            f"metric={payload['metric']['name']} "
            f"top_k={int(payload['counts']['top_k_emitted'])}"
        )
        best_line = (
            "best "
            f"rank=1 "
            f"plan_point_id={first.get('plan_point_id', '')} "
            f"metric={_format_float(_finite_float(first.get('metric_value')))} "
            f"chi2_total={_format_float(_finite_float(first.get('chi2_total')))}"
        )
        sys.stdout.write(summary + "\n")
        sys.stdout.write(best_line + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

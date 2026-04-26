#!/usr/bin/env python3
"""Phase-2 E2 CMB tension profiling report (stdlib-only).

Consumes one or more JSONL outputs from `phase2_e2_scan.py` and produces a
diagnostic summary of required CMB scaling corrections (`D_M`, `r_s`) under
selected filters. This tool is diagnostic-only and does not claim closure.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

V101_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V101_DIR))

from gsc.jsonl_io import open_text_read  # noqa: E402


SCRIPT_VERSION = "M22"
SNIPPET_MARKER = "phase2_e2_cmb_tension_snippet_v1"
PRIOR_ORDER: Tuple[str, ...] = ("R", "lA", "omega_b_h2")
PRIOR_TENSION_PULL_KEYS: Mapping[str, str] = {
    "R": "dR_sigma_diag",
    "lA": "dlA_sigma_diag",
    "omega_b_h2": "domega_sigma_diag",
}


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _finite_float(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except Exception:
        return None
    if not math.isfinite(out):
        return None
    return float(out)


def _to_json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Mapping):
        return {str(k): _to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_json_safe(v) for v in value]
    fv = _finite_float(value)
    if fv is not None:
        return fv
    return str(value)


def _canonical_json_text(value: Any) -> str:
    return json.dumps(_to_json_safe(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _collect_jsonl_files(*, inputs: Sequence[Path], indirs: Sequence[Path]) -> List[Path]:
    out: List[Path] = []
    seen: set[Path] = set()
    for raw in inputs:
        p = raw.expanduser().resolve()
        if not p.is_file():
            raise SystemExit(f"--in-jsonl not found: {p}")
        lower_name = p.name.lower()
        if not (lower_name.endswith(".jsonl") or lower_name.endswith(".jsonl.gz")):
            raise SystemExit(f"--in-jsonl must point to a .jsonl/.jsonl.gz file: {p}")
        if p not in seen:
            seen.add(p)
            out.append(p)
    for raw in indirs:
        d = raw.expanduser().resolve()
        if not d.is_dir():
            raise SystemExit(f"--indir not found: {d}")
        for p in sorted(list(d.rglob("*.jsonl")) + list(d.rglob("*.jsonl.gz"))):
            rp = p.resolve()
            if rp not in seen:
                seen.add(rp)
                out.append(rp)
    if not out:
        raise SystemExit("No JSONL inputs found. Use --in-jsonl and/or --indir.")
    return sorted(out)


def _get_path(obj: Mapping[str, Any], path: str) -> Any:
    cur: Any = obj
    for part in str(path).split("."):
        if not isinstance(cur, Mapping):
            return None
        if part not in cur:
            return None
        cur = cur[part]
    return cur


def _flatten_numeric(obj: Any, *, prefix: str = "") -> Dict[str, float]:
    out: Dict[str, float] = {}
    if isinstance(obj, Mapping):
        for key, value in obj.items():
            name = str(key)
            child = f"{prefix}.{name}" if prefix else name
            out.update(_flatten_numeric(value, prefix=child))
        return out
    if isinstance(obj, list):
        return out
    fv = _finite_float(obj)
    if fv is not None and prefix:
        out[prefix] = float(fv)
    return out


def _first_numeric(obj: Mapping[str, Any], paths: Sequence[str]) -> Optional[float]:
    for path in paths:
        fv = _finite_float(_get_path(obj, path))
        if fv is not None:
            return float(fv)
    return None


def _extract_model_label(obj: Mapping[str, Any]) -> str:
    for key in ("model", "model_id", "family"):
        value = obj.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_params(obj: Mapping[str, Any]) -> Dict[str, float]:
    raw = obj.get("params")
    if not isinstance(raw, Mapping):
        return {}
    out: Dict[str, float] = {}
    for key in sorted(str(k) for k in raw.keys()):
        fv = _finite_float(raw.get(key))
        if fv is not None:
            out[key] = float(fv)
    return out


def _extract_params_hash(obj: Mapping[str, Any], *, source_file: str, source_line: int) -> str:
    raw = obj.get("params_hash")
    if raw is not None:
        text = str(raw).strip()
        if text:
            return text

    params = obj.get("params")
    if isinstance(params, Mapping):
        canonical_params = _canonical_json_text({str(k): params[k] for k in sorted(params.keys())})
        if canonical_params != "{}":
            digest = hashlib.sha256()
            digest.update(canonical_params.encode("utf-8"))
            return digest.hexdigest()

    payload = f"{source_file}:{int(source_line)}:{_canonical_json_text(obj)}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _extract_numeric_map_from_paths(obj: Mapping[str, Any], paths: Sequence[str]) -> Dict[str, float]:
    for path in paths:
        raw = _get_path(obj, path)
        if not isinstance(raw, Mapping):
            continue
        out: Dict[str, float] = {}
        for key in sorted(str(k) for k in raw.keys()):
            fv = _finite_float(raw.get(key))
            if fv is not None:
                out[str(key)] = float(fv)
        if out:
            return out
    return {}


def _extract_chi2_total(obj: Mapping[str, Any], *, explicit_key: Optional[str]) -> Optional[float]:
    if explicit_key:
        return _first_numeric(obj, (explicit_key, f"metrics.{explicit_key}", f"result.{explicit_key}"))
    return _first_numeric(
        obj,
        (
            "chi2_total",
            "chi2",
            "chi2_tot",
            "metrics.chi2_total",
            "metrics.chi2",
            "result.chi2_total",
            "result.chi2",
        ),
    )


def _extract_chi2_cmb(obj: Mapping[str, Any]) -> Optional[float]:
    return _first_numeric(
        obj,
        (
            "chi2_cmb",
            "chi2_parts.cmb.chi2",
            "result.chi2_cmb",
            "metrics.chi2_cmb",
        ),
    )


def _extract_drift_metric(
    obj: Mapping[str, Any],
    *,
    explicit_key: Optional[str],
) -> Tuple[Optional[str], Optional[float], Optional[int]]:
    numeric_map = _flatten_numeric(obj)
    chosen_key: Optional[str] = None
    if explicit_key:
        if explicit_key in numeric_map:
            chosen_key = explicit_key
        else:
            fv = _finite_float(_get_path(obj, explicit_key))
            if fv is not None:
                chosen_key = explicit_key
                numeric_map[explicit_key] = float(fv)
    else:
        if "drift_sign_z2_5" in numeric_map:
            chosen_key = "drift_sign_z2_5"
        else:
            dzdt = sorted(k for k in numeric_map.keys() if "dzdt" in k.lower() and "z3" in k.lower())
            if dzdt:
                chosen_key = dzdt[0]
            else:
                dv = sorted(k for k in numeric_map.keys() if "dv" in k.lower() and "z3" in k.lower())
                if dv:
                    chosen_key = dv[0]
                else:
                    drift_like = sorted(k for k in numeric_map.keys() if k.lower().startswith("drift_"))
                    if drift_like:
                        chosen_key = drift_like[0]
                    else:
                        min_zdot = _first_numeric(obj, ("drift.min_z_dot", "min_zdot_si", "chi2_parts.drift.min_zdot_si"))
                        if min_zdot is not None:
                            chosen_key = "drift.min_z_dot"
                            numeric_map[chosen_key] = float(min_zdot)
    value = numeric_map.get(chosen_key) if chosen_key else None
    drift_sign: Optional[int] = None
    if value is not None:
        if value > 0.0:
            drift_sign = 1
        elif value < 0.0:
            drift_sign = -1
        else:
            drift_sign = 0
    elif isinstance(obj.get("drift_pass"), bool):
        drift_sign = 1 if bool(obj.get("drift_pass")) else -1
    return chosen_key, (None if value is None else float(value)), drift_sign


@dataclass(frozen=True)
class ParsedPoint:
    source_file: str
    source_line: int
    params_hash: str
    plan_point_id: Optional[str]
    status: str
    model: str
    params: Dict[str, float]
    chi2_total: float
    chi2_cmb: Optional[float]
    drift_key: Optional[str]
    drift_value: Optional[float]
    drift_sign: Optional[int]
    microphysics_plausible_ok: Optional[bool]
    microphysics: Dict[str, Any]
    recombination_method: str
    cmb_num_method: str
    cmb_num_err_dm: Optional[float]
    cmb_num_err_rs: Optional[float]
    cmb_num_err_rs_drag: Optional[float]
    cmb_pred: Dict[str, Optional[float]]
    cmb_observed: Dict[str, float]
    cmb_sigma_diag: Dict[str, float]
    cmb_pulls: Dict[str, float]
    cmb_tension: Dict[str, Optional[float]]
    chi2_parts: Dict[str, Any]


def _quantile(sorted_values: Sequence[float], q: float) -> Optional[float]:
    if not sorted_values:
        return None
    if q <= 0.0:
        return float(sorted_values[0])
    if q >= 1.0:
        return float(sorted_values[-1])
    n = len(sorted_values)
    pos = (n - 1) * float(q)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(sorted_values[lo])
    w = pos - lo
    return float(sorted_values[lo] * (1.0 - w) + sorted_values[hi] * w)


def _extract_microphysics(obj: Mapping[str, Any]) -> Dict[str, Any]:
    raw = _get_path(obj, "microphysics")
    if raw is None:
        raw = _get_path(obj, "metrics.microphysics")
    m = raw if isinstance(raw, Mapping) else {}
    mode = str(m.get("mode", "none"))
    z_star_scale = _finite_float(m.get("z_star_scale"))
    r_s_scale = _finite_float(m.get("r_s_scale"))
    r_d_scale = _finite_float(m.get("r_d_scale"))
    return {
        "mode": mode if mode in {"none", "knobs"} else "none",
        "z_star_scale": 1.0 if z_star_scale is None else float(z_star_scale),
        "r_s_scale": 1.0 if r_s_scale is None else float(r_s_scale),
        "r_d_scale": 1.0 if r_d_scale is None else float(r_d_scale),
    }


def _fmt_float(value: Optional[float], digits: int) -> str:
    if value is None or not math.isfinite(float(value)):
        return "NA"
    return f"{float(value):.{int(digits)}g}"


def _parse_thresholds(raw: str) -> List[float]:
    out: List[float] = []
    for tok in str(raw).split(","):
        t = tok.strip()
        if not t:
            continue
        fv = _finite_float(t)
        if fv is None:
            raise SystemExit(f"invalid threshold value: {t!r}")
        out.append(float(fv))
    return sorted(set(out))


def _prior_rows(point: ParsedPoint) -> List[Dict[str, Optional[float]]]:
    rows: List[Dict[str, Optional[float]]] = []
    for prior in PRIOR_ORDER:
        model_value = _finite_float(point.cmb_pred.get(prior))
        data_mean = _finite_float(point.cmb_observed.get(prior))
        sigma_marg = _finite_float(point.cmb_sigma_diag.get(prior))
        pull_sigma = _finite_float(point.cmb_pulls.get(prior))
        if pull_sigma is None:
            pull_sigma = _finite_float(point.cmb_tension.get(PRIOR_TENSION_PULL_KEYS[prior]))

        delta = None
        if model_value is not None and data_mean is not None:
            delta = float(model_value) - float(data_mean)
        elif pull_sigma is not None and sigma_marg is not None:
            delta = float(pull_sigma) * float(sigma_marg)

        if sigma_marg is None and delta is not None and pull_sigma is not None and float(pull_sigma) != 0.0:
            sigma_marg = float(delta) / float(pull_sigma)
        if data_mean is None and model_value is not None and pull_sigma is not None and sigma_marg is not None:
            data_mean = float(model_value) - float(pull_sigma) * float(sigma_marg)

        rows.append(
            {
                "prior_name": prior,
                "data_mean": data_mean,
                "model_value": model_value,
                "delta": delta,
                "sigma_marg": sigma_marg,
                "pull_sigma": pull_sigma,
            }
        )
    return rows


def _fmt_bool_or_na(value: Optional[bool]) -> str:
    if value is None:
        return "NA"
    return "true" if bool(value) else "false"


def _render_candidate_md(*, title: str, point: ParsedPoint, digits: int) -> List[str]:
    lines: List[str] = []
    lines.append(f"## {title}")
    lines.append("")
    lines.append(f"- params_hash: `{point.params_hash}`")
    lines.append(f"- plan_point_id: `{point.plan_point_id or 'NA'}`")
    lines.append(f"- status: `{point.status}`")
    lines.append(f"- chi2_total: `{_fmt_float(point.chi2_total, digits)}`")
    lines.append(f"- chi2_cmb_priors: `{_fmt_float(point.chi2_cmb, digits)}`")
    lines.append(f"- microphysics_plausible_ok: `{_fmt_bool_or_na(point.microphysics_plausible_ok)}`")
    lines.append("")
    lines.append("| prior | data_mean | model_value | delta | sigma_marg | pull_sigma |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for row in _prior_rows(point):
        lines.append(
            "| "
            + str(row["prior_name"])
            + " | "
            + _fmt_float(_finite_float(row.get("data_mean")), digits)
            + " | "
            + _fmt_float(_finite_float(row.get("model_value")), digits)
            + " | "
            + _fmt_float(_finite_float(row.get("delta")), digits)
            + " | "
            + _fmt_float(_finite_float(row.get("sigma_marg")), digits)
            + " | "
            + _fmt_float(_finite_float(row.get("pull_sigma")), digits)
            + " |"
        )
    lines.append("")
    return lines


def _tex_escape(text: str) -> str:
    return str(text).replace("\\", "\\textbackslash{}").replace("_", "\\_").replace("%", "\\%")


def _render_candidate_tex(*, title: str, point: ParsedPoint, digits: int) -> List[str]:
    lines: List[str] = []
    lines.append(f"\\textbf{{{_tex_escape(title)}}}\\\\")
    lines.append(
        "\\texttt{params\\_hash="
        + _tex_escape(point.params_hash)
        + ", plan\\_point\\_id="
        + _tex_escape(point.plan_point_id or "NA")
        + ", status="
        + _tex_escape(point.status)
        + "}\\\\"
    )
    lines.append(
        "\\texttt{chi2\\_total="
        + _tex_escape(_fmt_float(point.chi2_total, digits))
        + ", chi2\\_cmb\\_priors="
        + _tex_escape(_fmt_float(point.chi2_cmb, digits))
        + ", plausible="
        + _tex_escape(_fmt_bool_or_na(point.microphysics_plausible_ok))
        + "}\\\\"
    )
    lines.append("\\begin{tabular}{lrrrrr}")
    lines.append("\\hline")
    lines.append("prior & data\\_mean & model\\_value & delta & sigma\\_marg & pull\\_sigma \\\\")
    lines.append("\\hline")
    for row in _prior_rows(point):
        lines.append(
            _tex_escape(str(row["prior_name"]))
            + " & "
            + _tex_escape(_fmt_float(_finite_float(row.get("data_mean")), digits))
            + " & "
            + _tex_escape(_fmt_float(_finite_float(row.get("model_value")), digits))
            + " & "
            + _tex_escape(_fmt_float(_finite_float(row.get("delta")), digits))
            + " & "
            + _tex_escape(_fmt_float(_finite_float(row.get("sigma_marg")), digits))
            + " & "
            + _tex_escape(_fmt_float(_finite_float(row.get("pull_sigma")), digits))
            + " \\\\"
        )
    lines.append("\\hline")
    lines.append("\\end{tabular}")
    lines.append("")
    return lines


def main() -> None:
    ap = argparse.ArgumentParser(prog="phase2_e2_cmb_tension_report")
    ap.add_argument("--in-jsonl", action="append", default=[], type=Path, help="Input JSONL file (repeatable).")
    ap.add_argument("--input", action="append", default=[], type=Path, help="Alias for --in-jsonl (repeatable).")
    ap.add_argument("--indir", action="append", default=[], type=Path, help="Input directory (searches *.jsonl recursively; repeatable).")
    ap.add_argument(
        "--outdir",
        type=Path,
        default=Path("v11.0.0/results/phase2_e2_cmb_tension"),
        help="Output directory for summary artifacts.",
    )
    ap.add_argument("--top-k", type=int, default=25)
    ap.add_argument("--require-drift-sign", choices=["positive", "negative", "any"], default="any")
    ap.add_argument("--max-chi2-cmb", type=float, default=None)
    ap.add_argument("--sort-by", choices=["chi2_total", "chi2_cmb"], default="chi2_total")
    ap.add_argument("--chi2-key", type=str, default=None, help="Override chi2 key (falls back to auto-detect).")
    ap.add_argument("--drift-key", type=str, default=None, help="Override drift metric key (falls back to auto-detect).")
    ap.add_argument("--require-ok", dest="require_ok", action="store_true", default=True)
    ap.add_argument("--no-require-ok", dest="require_ok", action="store_false")
    ap.add_argument("--model-filter", type=str, default=None, help="Optional regex on model/model_id/family.")
    ap.add_argument("--float-digits", type=int, default=6)
    ap.add_argument(
        "--created-utc",
        type=str,
        default=None,
        help="Optional deterministic timestamp to embed in outputs.",
    )
    ap.add_argument("--emit-snippets", action="store_true", help="Emit phase2_e2_cmb_tension.{tex,md} snippets.")
    ap.add_argument(
        "--snippets-outdir",
        type=Path,
        default=None,
        help="Output directory for phase2_e2_cmb_tension snippets (defaults to --outdir).",
    )
    args = ap.parse_args()

    if int(args.top_k) <= 0:
        raise SystemExit("--top-k must be > 0")
    if int(args.float_digits) <= 0:
        raise SystemExit("--float-digits must be > 0")
    if args.max_chi2_cmb is not None and not math.isfinite(float(args.max_chi2_cmb)):
        raise SystemExit("--max-chi2-cmb must be finite")

    model_re = re.compile(str(args.model_filter)) if args.model_filter else None
    inputs = _collect_jsonl_files(inputs=list(args.in_jsonl) + list(args.input), indirs=list(args.indir))
    outdir = args.outdir.expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    total_lines = 0
    n_parsed = 0
    n_skipped_err = 0
    n_with_cmb_tension = 0
    points: List[ParsedPoint] = []

    for path in inputs:
        with open_text_read(path) as fh:
            for ln, line in enumerate(fh, start=1):
                total_lines += 1
                text = line.strip()
                if not text:
                    n_skipped_err += 1
                    continue
                try:
                    obj = json.loads(text)
                except Exception:
                    n_skipped_err += 1
                    continue
                if not isinstance(obj, Mapping):
                    n_skipped_err += 1
                    continue
                n_parsed += 1

                if bool(args.require_ok):
                    status_text = str(obj.get("status", "")).strip().lower()
                    if status_text and status_text != "ok":
                        continue
                    if not status_text and "ok" in obj and not bool(obj.get("ok")):
                        continue
                status_raw = str(obj.get("status", "")).strip().lower()
                if status_raw:
                    status_for_row = status_raw
                elif "ok" in obj:
                    status_for_row = "ok" if bool(obj.get("ok")) else "error"
                else:
                    status_for_row = "unknown"

                model = _extract_model_label(obj)
                if model_re is not None and not model_re.search(model):
                    continue

                chi2_total = _extract_chi2_total(obj, explicit_key=args.chi2_key)
                if chi2_total is None:
                    continue
                chi2_cmb = _extract_chi2_cmb(obj)
                if args.max_chi2_cmb is not None:
                    if chi2_cmb is None or float(chi2_cmb) > float(args.max_chi2_cmb):
                        continue

                drift_key, drift_value, drift_sign = _extract_drift_metric(obj, explicit_key=args.drift_key)
                if args.require_drift_sign == "positive" and drift_sign is not None and drift_sign <= 0:
                    continue
                if args.require_drift_sign == "positive" and drift_sign is None:
                    continue
                if args.require_drift_sign == "negative" and drift_sign is not None and drift_sign >= 0:
                    continue
                if args.require_drift_sign == "negative" and drift_sign is None:
                    continue

                raw_pred = _get_path(obj, "cmb_pred")
                raw_tension = _get_path(obj, "cmb_tension")
                if raw_pred is None:
                    raw_pred = _get_path(obj, "metrics.cmb_pred")
                if raw_tension is None:
                    raw_tension = _get_path(obj, "metrics.cmb_tension")
                if not isinstance(raw_pred, Mapping) or not isinstance(raw_tension, Mapping):
                    continue

                n_with_cmb_tension += 1
                cmb_pred = {
                    "R": _finite_float(raw_pred.get("R")),
                    "lA": _finite_float(raw_pred.get("lA")),
                    "omega_b_h2": _finite_float(raw_pred.get("omega_b_h2")),
                }
                cmb_tension = {
                    "scale_D_from_R": _finite_float(raw_tension.get("scale_D_from_R")),
                    "scale_rs_from_lA_given_R": _finite_float(raw_tension.get("scale_rs_from_lA_given_R")),
                    "scale_rs_from_lA_only": _finite_float(raw_tension.get("scale_rs_from_lA_only")),
                    "scale_D_from_lA_only": _finite_float(raw_tension.get("scale_D_from_lA_only")),
                    "delta_D_pct": _finite_float(raw_tension.get("delta_D_pct")),
                    "delta_rs_pct": _finite_float(raw_tension.get("delta_rs_pct")),
                    "dR_sigma_diag": _finite_float(raw_tension.get("dR_sigma_diag")),
                    "dlA_sigma_diag": _finite_float(raw_tension.get("dlA_sigma_diag")),
                    "domega_sigma_diag": _finite_float(raw_tension.get("domega_sigma_diag")),
                }
                cmb_observed = _extract_numeric_map_from_paths(
                    obj,
                    (
                        "cmb_observed",
                        "cmb_data_mean",
                        "chi2_parts.cmb.observed",
                        "chi2_parts.cmb.data_mean",
                        "metrics.cmb_observed",
                    ),
                )
                cmb_sigma_diag = _extract_numeric_map_from_paths(
                    obj,
                    (
                        "cmb_sigma_diag",
                        "cmb_sigma_marg",
                        "chi2_parts.cmb.sigma_diag",
                        "chi2_parts.cmb.sigma_marg",
                        "metrics.cmb_sigma_diag",
                    ),
                )
                cmb_pulls = _extract_numeric_map_from_paths(
                    obj,
                    (
                        "cmb_pulls",
                        "chi2_parts.cmb.pulls",
                        "metrics.cmb_pulls",
                    ),
                )
                for prior, key in PRIOR_TENSION_PULL_KEYS.items():
                    if prior not in cmb_pulls:
                        pull = _finite_float(cmb_tension.get(key))
                        if pull is not None:
                            cmb_pulls[str(prior)] = float(pull)
                predicted = _get_path(obj, "predicted")
                predicted_map = predicted if isinstance(predicted, Mapping) else {}
                recombination_method = str(
                    obj.get("recombination_method", predicted_map.get("recombination_method", ""))
                ).strip()
                cmb_num_method = str(
                    obj.get("cmb_num_method", predicted_map.get("cmb_num_method", ""))
                ).strip()
                cmb_num_err_dm = _first_numeric(obj, ("cmb_num_err_dm", "predicted.cmb_num_err_dm"))
                cmb_num_err_rs = _first_numeric(obj, ("cmb_num_err_rs", "predicted.cmb_num_err_rs"))
                cmb_num_err_rs_drag = _first_numeric(
                    obj,
                    ("cmb_num_err_rs_drag", "predicted.cmb_num_err_rs_drag"),
                )
                chi2_parts = _get_path(obj, "chi2_parts")
                plan_point_id_raw = obj.get("plan_point_id")
                plan_point_id = None
                if plan_point_id_raw is not None:
                    text = str(plan_point_id_raw).strip()
                    if text:
                        plan_point_id = text
                plausible_raw = obj.get("microphysics_plausible_ok")
                plausible_ok = None if not isinstance(plausible_raw, bool) else bool(plausible_raw)
                points.append(
                    ParsedPoint(
                        source_file=str(path),
                        source_line=int(ln),
                        params_hash=_extract_params_hash(obj, source_file=str(path), source_line=int(ln)),
                        plan_point_id=plan_point_id,
                        status=status_for_row,
                        model=model,
                        params=_extract_params(obj),
                        chi2_total=float(chi2_total),
                        chi2_cmb=None if chi2_cmb is None else float(chi2_cmb),
                        drift_key=drift_key,
                        drift_value=drift_value,
                        drift_sign=drift_sign,
                        microphysics_plausible_ok=plausible_ok,
                        microphysics=_extract_microphysics(obj),
                        recombination_method=recombination_method,
                        cmb_num_method=cmb_num_method,
                        cmb_num_err_dm=cmb_num_err_dm,
                        cmb_num_err_rs=cmb_num_err_rs,
                        cmb_num_err_rs_drag=cmb_num_err_rs_drag,
                        cmb_pred=cmb_pred,
                        cmb_observed=cmb_observed,
                        cmb_sigma_diag=cmb_sigma_diag,
                        cmb_pulls=cmb_pulls,
                        cmb_tension=cmb_tension,
                        chi2_parts=chi2_parts if isinstance(chi2_parts, Mapping) else {},
                    )
                )

    def _sort_metric(p: ParsedPoint) -> float:
        if args.sort_by == "chi2_cmb":
            if p.chi2_cmb is None or not math.isfinite(float(p.chi2_cmb)):
                return float("inf")
            return float(p.chi2_cmb)
        return float(p.chi2_total)

    points_sorted = sorted(points, key=lambda p: (_sort_metric(p), p.source_file, p.source_line))
    top_k = points_sorted[: int(args.top_k)]

    delta_d = sorted(float(v) for v in (p.cmb_tension.get("delta_D_pct") for p in points) if v is not None and math.isfinite(float(v)))
    delta_rs = sorted(float(v) for v in (p.cmb_tension.get("delta_rs_pct") for p in points) if v is not None and math.isfinite(float(v)))

    def _fraction_within(vals: Sequence[float], threshold: float) -> Optional[float]:
        if not vals:
            return None
        count = sum(1 for v in vals if abs(float(v)) < float(threshold))
        return float(count) / float(len(vals))

    best_by_chi2_cmb = next((p for p in sorted(points, key=lambda p: (float("inf") if p.chi2_cmb is None else float(p.chi2_cmb), p.source_file, p.source_line)) if p.chi2_cmb is not None), None)
    best_by_chi2_total = points_sorted[0] if points_sorted else None
    eligible_by_chi2_total = sorted(
        points,
        key=lambda p: (float(p.chi2_total), str(p.params_hash), str(p.source_file), int(p.source_line)),
    )
    best_eligible = eligible_by_chi2_total[0] if eligible_by_chi2_total else None
    plausible_candidates = [p for p in eligible_by_chi2_total if p.microphysics_plausible_ok is not False]
    best_eligible_plausible = plausible_candidates[0] if plausible_candidates else None

    recombination_methods_seen = sorted({p.recombination_method for p in points if p.recombination_method})
    cmb_num_methods_seen = sorted({p.cmb_num_method for p in points if p.cmb_num_method})
    err_dm_vals = sorted(
        float(v) for v in (p.cmb_num_err_dm for p in points) if v is not None and math.isfinite(float(v))
    )
    err_rs_vals = sorted(
        float(v) for v in (p.cmb_num_err_rs for p in points) if v is not None and math.isfinite(float(v))
    )
    err_rs_drag_vals = sorted(
        float(v) for v in (p.cmb_num_err_rs_drag for p in points) if v is not None and math.isfinite(float(v))
    )

    err_thresholds_p95 = {
        "cmb_num_err_dm": _quantile(err_dm_vals, 0.95),
        "cmb_num_err_rs": _quantile(err_rs_vals, 0.95),
        "cmb_num_err_rs_drag": _quantile(err_rs_drag_vals, 0.95),
    }

    def _point_num_error_flags(point: Optional[ParsedPoint]) -> List[str]:
        if point is None:
            return []
        out: List[str] = []
        checks = [
            ("cmb_num_err_dm", point.cmb_num_err_dm),
            ("cmb_num_err_rs", point.cmb_num_err_rs),
            ("cmb_num_err_rs_drag", point.cmb_num_err_rs_drag),
        ]
        for key, value in checks:
            thr = err_thresholds_p95.get(key)
            if value is None or thr is None:
                continue
            if math.isfinite(float(value)) and float(value) > 0.0 and float(value) >= float(thr):
                out.append(str(key))
        return out

    generated_utc = str(args.created_utc).strip() if args.created_utc is not None else _now_utc()

    summary = {
        "version": SCRIPT_VERSION,
        "generated_utc": generated_utc,
        "config": {
            "top_k": int(args.top_k),
            "sort_by": str(args.sort_by),
            "require_drift_sign": str(args.require_drift_sign),
            "max_chi2_cmb": None if args.max_chi2_cmb is None else float(args.max_chi2_cmb),
            "chi2_key": None if args.chi2_key is None else str(args.chi2_key),
            "drift_key": None if args.drift_key is None else str(args.drift_key),
            "require_ok": bool(args.require_ok),
        },
        "inputs": [
            {"path": str(p), "sha256": _sha256_file(p)}
            for p in inputs
        ],
        "counts": {
            "total_lines": int(total_lines),
            "parsed_json_objects": int(n_parsed),
            "skipped_err": int(n_skipped_err),
            "with_cmb_tension": int(n_with_cmb_tension),
            "after_filters": int(len(points)),
        },
        "numerics": {
            "recombination_methods_seen": recombination_methods_seen,
            "cmb_num_methods_seen": cmb_num_methods_seen,
            "err_thresholds_p95": _to_json_safe(err_thresholds_p95),
        },
        "best_by_chi2_cmb": _to_json_safe(
            None
            if best_by_chi2_cmb is None
            else {
                "source_file": best_by_chi2_cmb.source_file,
                "source_line": best_by_chi2_cmb.source_line,
                "params_hash": best_by_chi2_cmb.params_hash,
                "plan_point_id": best_by_chi2_cmb.plan_point_id,
                "status": best_by_chi2_cmb.status,
                "model": best_by_chi2_cmb.model,
                "params": best_by_chi2_cmb.params,
                "chi2_total": best_by_chi2_cmb.chi2_total,
                "chi2_cmb": best_by_chi2_cmb.chi2_cmb,
                "drift_key": best_by_chi2_cmb.drift_key,
                "drift_value": best_by_chi2_cmb.drift_value,
                "drift_sign": best_by_chi2_cmb.drift_sign,
                "microphysics_plausible_ok": best_by_chi2_cmb.microphysics_plausible_ok,
                "microphysics": best_by_chi2_cmb.microphysics,
                "recombination_method": best_by_chi2_cmb.recombination_method,
                "cmb_num_method": best_by_chi2_cmb.cmb_num_method,
                "cmb_num_err_dm": best_by_chi2_cmb.cmb_num_err_dm,
                "cmb_num_err_rs": best_by_chi2_cmb.cmb_num_err_rs,
                "cmb_num_err_rs_drag": best_by_chi2_cmb.cmb_num_err_rs_drag,
                "numerics_high_error_flags": _point_num_error_flags(best_by_chi2_cmb),
                "cmb_pred": best_by_chi2_cmb.cmb_pred,
                "cmb_tension": best_by_chi2_cmb.cmb_tension,
            }
        ),
        "best_by_chi2_total": _to_json_safe(
            None
            if best_by_chi2_total is None
            else {
                "source_file": best_by_chi2_total.source_file,
                "source_line": best_by_chi2_total.source_line,
                "params_hash": best_by_chi2_total.params_hash,
                "plan_point_id": best_by_chi2_total.plan_point_id,
                "status": best_by_chi2_total.status,
                "model": best_by_chi2_total.model,
                "params": best_by_chi2_total.params,
                "chi2_total": best_by_chi2_total.chi2_total,
                "chi2_cmb": best_by_chi2_total.chi2_cmb,
                "drift_key": best_by_chi2_total.drift_key,
                "drift_value": best_by_chi2_total.drift_value,
                "drift_sign": best_by_chi2_total.drift_sign,
                "microphysics_plausible_ok": best_by_chi2_total.microphysics_plausible_ok,
                "microphysics": best_by_chi2_total.microphysics,
                "recombination_method": best_by_chi2_total.recombination_method,
                "cmb_num_method": best_by_chi2_total.cmb_num_method,
                "cmb_num_err_dm": best_by_chi2_total.cmb_num_err_dm,
                "cmb_num_err_rs": best_by_chi2_total.cmb_num_err_rs,
                "cmb_num_err_rs_drag": best_by_chi2_total.cmb_num_err_rs_drag,
                "numerics_high_error_flags": _point_num_error_flags(best_by_chi2_total),
                "cmb_pred": best_by_chi2_total.cmb_pred,
                "cmb_tension": best_by_chi2_total.cmb_tension,
            }
        ),
        "best_eligible": _to_json_safe(
            None
            if best_eligible is None
            else {
                "params_hash": best_eligible.params_hash,
                "plan_point_id": best_eligible.plan_point_id,
                "status": best_eligible.status,
                "chi2_total": best_eligible.chi2_total,
                "chi2_cmb": best_eligible.chi2_cmb,
                "microphysics_plausible_ok": best_eligible.microphysics_plausible_ok,
            }
        ),
        "best_eligible_plausible": _to_json_safe(
            None
            if best_eligible_plausible is None
            else {
                "params_hash": best_eligible_plausible.params_hash,
                "plan_point_id": best_eligible_plausible.plan_point_id,
                "status": best_eligible_plausible.status,
                "chi2_total": best_eligible_plausible.chi2_total,
                "chi2_cmb": best_eligible_plausible.chi2_cmb,
                "microphysics_plausible_ok": best_eligible_plausible.microphysics_plausible_ok,
            }
        ),
        "quantiles": {
            "delta_D_pct": {
                "p05": _quantile(delta_d, 0.05),
                "p50": _quantile(delta_d, 0.50),
                "p95": _quantile(delta_d, 0.95),
            },
            "delta_rs_pct": {
                "p05": _quantile(delta_rs, 0.05),
                "p50": _quantile(delta_rs, 0.50),
                "p95": _quantile(delta_rs, 0.95),
            },
        },
        "fractions": {
            "abs_delta_D_lt_1pct": _fraction_within(delta_d, 1.0),
            "abs_delta_D_lt_5pct": _fraction_within(delta_d, 5.0),
            "abs_delta_D_lt_10pct": _fraction_within(delta_d, 10.0),
            "abs_delta_rs_lt_1pct": _fraction_within(delta_rs, 1.0),
            "abs_delta_rs_lt_5pct": _fraction_within(delta_rs, 5.0),
            "abs_delta_rs_lt_10pct": _fraction_within(delta_rs, 10.0),
        },
    }

    out_json = outdir / "cmb_tension_summary.json"
    out_md = outdir / "cmb_tension_summary.md"
    out_csv = outdir / "cmb_tension_topk.csv"

    out_json.write_text(json.dumps(_to_json_safe(summary), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    csv_fields = [
        "rank",
        "source_file",
        "source_line",
        "model",
        "chi2_total",
        "chi2_cmb",
        "drift_sign",
        "drift_key",
        "drift_value",
        "micro_mode",
        "z_star_scale",
        "r_s_scale",
        "r_d_scale",
        "recombination_method",
        "cmb_num_method",
        "cmb_num_err_dm",
        "cmb_num_err_rs",
        "cmb_num_err_rs_drag",
        "numerics_high_error_flags",
        "delta_D_pct",
        "delta_rs_pct",
        "dR_sigma_diag",
        "dlA_sigma_diag",
        "domega_sigma_diag",
        "params_json",
    ]
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=csv_fields)
        writer.writeheader()
        for i, p in enumerate(top_k, start=1):
            writer.writerow(
                {
                    "rank": int(i),
                    "source_file": p.source_file,
                    "source_line": int(p.source_line),
                    "model": p.model,
                    "chi2_total": _fmt_float(p.chi2_total, int(args.float_digits)),
                    "chi2_cmb": _fmt_float(p.chi2_cmb, int(args.float_digits)),
                    "drift_sign": "" if p.drift_sign is None else int(p.drift_sign),
                    "drift_key": "" if p.drift_key is None else p.drift_key,
                    "drift_value": _fmt_float(p.drift_value, int(args.float_digits)),
                    "micro_mode": str(p.microphysics.get("mode", "none")),
                    "z_star_scale": _fmt_float(_finite_float(p.microphysics.get("z_star_scale")), int(args.float_digits)),
                    "r_s_scale": _fmt_float(_finite_float(p.microphysics.get("r_s_scale")), int(args.float_digits)),
                    "r_d_scale": _fmt_float(_finite_float(p.microphysics.get("r_d_scale")), int(args.float_digits)),
                    "recombination_method": p.recombination_method or "NA",
                    "cmb_num_method": p.cmb_num_method or "NA",
                    "cmb_num_err_dm": _fmt_float(p.cmb_num_err_dm, int(args.float_digits)),
                    "cmb_num_err_rs": _fmt_float(p.cmb_num_err_rs, int(args.float_digits)),
                    "cmb_num_err_rs_drag": _fmt_float(p.cmb_num_err_rs_drag, int(args.float_digits)),
                    "numerics_high_error_flags": ",".join(_point_num_error_flags(p)),
                    "delta_D_pct": _fmt_float(p.cmb_tension.get("delta_D_pct"), int(args.float_digits)),
                    "delta_rs_pct": _fmt_float(p.cmb_tension.get("delta_rs_pct"), int(args.float_digits)),
                    "dR_sigma_diag": _fmt_float(p.cmb_tension.get("dR_sigma_diag"), int(args.float_digits)),
                    "dlA_sigma_diag": _fmt_float(p.cmb_tension.get("dlA_sigma_diag"), int(args.float_digits)),
                    "domega_sigma_diag": _fmt_float(p.cmb_tension.get("domega_sigma_diag"), int(args.float_digits)),
                    "params_json": json.dumps(_to_json_safe(p.params), sort_keys=True),
                }
            )

    md_lines: List[str] = []
    md_lines.append("# CMB Tension Profiling Summary (M22)")
    md_lines.append("")
    md_lines.append(f"- Generated UTC: `{summary['generated_utc']}`")
    md_lines.append(f"- Inputs: `{len(inputs)}` JSONL file(s)")
    md_lines.append(f"- N_used: `{summary['counts']['after_filters']}`")
    md_lines.append("")
    md_lines.append("Diagnostic interpretation:")
    md_lines.append("- `delta_D_pct` approximates multiplicative `D_M` correction needed from `R` matching.")
    md_lines.append("- `delta_rs_pct` approximates multiplicative `r_s` correction needed after matching `R` and `lA`.")
    md_lines.append("- These are sensitivity diagnostics only (not closure claims).")
    md_lines.append("")
    md_lines.append("## Numerical Robustness")
    md_lines.append("")
    md_lines.append(
        f"- recombination_methods_seen: `{', '.join(recombination_methods_seen) if recombination_methods_seen else 'NA'}`"
    )
    md_lines.append(f"- cmb_num_methods_seen: `{', '.join(cmb_num_methods_seen) if cmb_num_methods_seen else 'NA'}`")
    md_lines.append(
        f"- p95(cmb_num_err_dm): `{_fmt_float(err_thresholds_p95.get('cmb_num_err_dm'), int(args.float_digits))}`"
    )
    md_lines.append(
        f"- p95(cmb_num_err_rs): `{_fmt_float(err_thresholds_p95.get('cmb_num_err_rs'), int(args.float_digits))}`"
    )
    md_lines.append(
        f"- p95(cmb_num_err_rs_drag): `{_fmt_float(err_thresholds_p95.get('cmb_num_err_rs_drag'), int(args.float_digits))}`"
    )
    if best_by_chi2_cmb is not None:
        flags = _point_num_error_flags(best_by_chi2_cmb)
        md_lines.append(f"- best_by_chi2_cmb high-error flags: `{','.join(flags) if flags else 'none'}`")
    if best_by_chi2_total is not None:
        flags = _point_num_error_flags(best_by_chi2_total)
        md_lines.append(f"- best_by_chi2_total high-error flags: `{','.join(flags) if flags else 'none'}`")
    md_lines.append("")
    md_lines.append("## Quantiles")
    md_lines.append("")
    md_lines.append("| metric | p05 | p50 | p95 |")
    md_lines.append("|---|---:|---:|---:|")
    for metric_key, label in (("delta_D_pct", "delta_D_pct"), ("delta_rs_pct", "delta_rs_pct")):
        q = summary["quantiles"][metric_key]
        md_lines.append(
            f"| {label} | {_fmt_float(q['p05'], int(args.float_digits))} | "
            f"{_fmt_float(q['p50'], int(args.float_digits))} | {_fmt_float(q['p95'], int(args.float_digits))} |"
        )
    md_lines.append("")
    md_lines.append("## Top-K")
    md_lines.append("")
    md_lines.append("| rank | model | chi2_cmb | chi2_total | drift_sign | micro | z*_s | rs_s | rd_s | delta_D_pct | delta_rs_pct | dR_sigma | dlA_sigma |")
    md_lines.append("|---:|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|")
    for i, p in enumerate(top_k, start=1):
        md_lines.append(
            "| "
            + " | ".join(
                [
                    str(i),
                    p.model or "NA",
                    _fmt_float(p.chi2_cmb, int(args.float_digits)),
                    _fmt_float(p.chi2_total, int(args.float_digits)),
                    "NA" if p.drift_sign is None else str(int(p.drift_sign)),
                    str(p.microphysics.get("mode", "none")),
                    _fmt_float(_finite_float(p.microphysics.get("z_star_scale")), int(args.float_digits)),
                    _fmt_float(_finite_float(p.microphysics.get("r_s_scale")), int(args.float_digits)),
                    _fmt_float(_finite_float(p.microphysics.get("r_d_scale")), int(args.float_digits)),
                    _fmt_float(p.cmb_tension.get("delta_D_pct"), int(args.float_digits)),
                    _fmt_float(p.cmb_tension.get("delta_rs_pct"), int(args.float_digits)),
                    _fmt_float(p.cmb_tension.get("dR_sigma_diag"), int(args.float_digits)),
                    _fmt_float(p.cmb_tension.get("dlA_sigma_diag"), int(args.float_digits)),
                ]
            )
            + " |"
        )
    md_lines.append("")
    out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    snippet_md_path: Optional[Path] = None
    snippet_tex_path: Optional[Path] = None
    if bool(args.emit_snippets):
        snippets_outdir = (args.snippets_outdir if args.snippets_outdir is not None else outdir).expanduser().resolve()
        snippets_outdir.mkdir(parents=True, exist_ok=True)
        snippet_md_path = snippets_outdir / "phase2_e2_cmb_tension.md"
        snippet_tex_path = snippets_outdir / "phase2_e2_cmb_tension.tex"

        snippet_md: List[str] = [
            f"<!-- {SNIPPET_MARKER} -->",
            "# Phase-2 E2 CMB Tension (compressed priors diagnostics)",
            "",
            "Pulls are reported against marginal sigma for each prior. "
            "The total CMB term uses the full covariance when available.",
            "",
        ]
        snippet_tex: List[str] = [
            f"% {SNIPPET_MARKER}",
            "\\textbf{Phase-2 E2 CMB tension (compressed-priors diagnostics)}\\\\",
            "Pulls are shown per prior using marginal $\\sigma$ values; "
            "the total CMB term uses full covariance when available.\\\\",
            "",
        ]

        if best_eligible is None:
            snippet_md.append("_No eligible record with CMB tension metrics was found._")
            snippet_tex.append("\\emph{No eligible record with CMB tension metrics was found.}")
        else:
            snippet_md.extend(_render_candidate_md(title="Best eligible", point=best_eligible, digits=int(args.float_digits)))
            snippet_tex.extend(
                _render_candidate_tex(title="Best eligible", point=best_eligible, digits=int(args.float_digits))
            )
            if best_eligible_plausible is not None:
                same_record = (
                    str(best_eligible.params_hash) == str(best_eligible_plausible.params_hash)
                    and int(best_eligible.source_line) == int(best_eligible_plausible.source_line)
                    and str(best_eligible.source_file) == str(best_eligible_plausible.source_file)
                )
                if not same_record:
                    snippet_md.extend(
                        _render_candidate_md(
                            title="Best eligible (plausible_only)",
                            point=best_eligible_plausible,
                            digits=int(args.float_digits),
                        )
                    )
                    snippet_tex.append("\\medskip")
                    snippet_tex.extend(
                        _render_candidate_tex(
                            title="Best eligible (plausible_only)",
                            point=best_eligible_plausible,
                            digits=int(args.float_digits),
                        )
                    )

        snippet_md_path.write_text("\n".join(snippet_md) + "\n", encoding="utf-8")
        snippet_tex_path.write_text("\n".join(snippet_tex) + "\n", encoding="utf-8")

    print(f"[ok] wrote {out_json}")
    print(f"[ok] wrote {out_md}")
    print(f"[ok] wrote {out_csv}")
    if snippet_md_path is not None:
        print(f"[ok] wrote {snippet_md_path}")
    if snippet_tex_path is not None:
        print(f"[ok] wrote {snippet_tex_path}")


if __name__ == "__main__":
    main()

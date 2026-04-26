#!/usr/bin/env python3
"""Phase-2 RG flow-table Pad\'e k* fit report (stdlib-only, diagnostic-only)."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gsc.rg.flow_table import RGFlowTable, load_flow_table_csv  # noqa: E402


SCHEMA_ID = "phase2_rg_pade_fit_report_v1"
SNIPPET_MARKER = "phase2_rg_pade_fit_snippet_v1"


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Fit Pad\'e pole ansatz to external RG/FRG flow tables (diagnostic).")
    ap.add_argument("--input", action="append", default=[], help="Input flow-table CSV path (repeatable).")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    ap.add_argument("--mode", choices=("summary", "by_file"), default="summary")
    ap.add_argument("--json-out", default=None, help="Optional JSON output path (always writes JSON there).")
    ap.add_argument("--k-range-min", type=float, default=None, help="Optional minimum k for fit rows.")
    ap.add_argument("--k-range-max", type=float, default=None, help="Optional maximum k for fit rows.")
    ap.add_argument("--emit-snippets", default=None, help="Optional output directory for .tex/.md snippets.")
    return ap.parse_args(argv)


def _fmt(value: object) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return "n/a"
        return f"{value:.12g}"
    return str(value)


def _fit_pade_pole2(points: Sequence[Tuple[float, float]]) -> Dict[str, Any]:
    """Fit G(k)=G_IR/(1-(k/k_*)^2) by linearized OLS on 1/G=a+b*k^2."""
    n = len(points)
    if n < 2:
        return {
            "fit_ok": False,
            "fit_reason": "insufficient_points",
            "G_ir": None,
            "k_star": None,
            "r2": None,
            "rmse_rel": None,
            "max_abs_rel": None,
        }

    sum_x = 0.0
    sum_xx = 0.0
    sum_y = 0.0
    sum_xy = 0.0
    for k, g in points:
        x = float(k) * float(k)
        y = 1.0 / float(g)
        sum_x += x
        sum_xx += x * x
        sum_y += y
        sum_xy += x * y

    den = (n * sum_xx) - (sum_x * sum_x)
    if abs(den) <= 1e-20:
        return {
            "fit_ok": False,
            "fit_reason": "degenerate_k_grid",
            "G_ir": None,
            "k_star": None,
            "r2": None,
            "rmse_rel": None,
            "max_abs_rel": None,
        }

    b = ((n * sum_xy) - (sum_x * sum_y)) / den
    a = (sum_y - (b * sum_x)) / float(n)

    if not math.isfinite(a) or not math.isfinite(b):
        return {
            "fit_ok": False,
            "fit_reason": "non_finite_coefficients",
            "G_ir": None,
            "k_star": None,
            "r2": None,
            "rmse_rel": None,
            "max_abs_rel": None,
        }

    if a <= 0.0:
        return {
            "fit_ok": False,
            "fit_reason": "non_positive_intercept",
            "G_ir": None,
            "k_star": None,
            "r2": None,
            "rmse_rel": None,
            "max_abs_rel": None,
            "a_intercept": float(a),
            "b_slope": float(b),
        }

    if b >= 0.0:
        return {
            "fit_ok": False,
            "fit_reason": "non_negative_slope",
            "G_ir": None,
            "k_star": None,
            "r2": None,
            "rmse_rel": None,
            "max_abs_rel": None,
            "a_intercept": float(a),
            "b_slope": float(b),
        }

    k_star_sq = -a / b
    if k_star_sq <= 0.0:
        return {
            "fit_ok": False,
            "fit_reason": "invalid_k_star_sq",
            "G_ir": None,
            "k_star": None,
            "r2": None,
            "rmse_rel": None,
            "max_abs_rel": None,
            "a_intercept": float(a),
            "b_slope": float(b),
        }

    g_ir = 1.0 / a
    k_star = math.sqrt(k_star_sq)

    preds: List[float] = []
    obs: List[float] = []
    rel: List[float] = []

    for k, g in points:
        denom = 1.0 - ((float(k) / k_star) ** 2)
        if abs(denom) <= 1e-18:
            return {
                "fit_ok": False,
                "fit_reason": "pole_hit_in_fit_domain",
                "G_ir": None,
                "k_star": None,
                "r2": None,
                "rmse_rel": None,
                "max_abs_rel": None,
                "a_intercept": float(a),
                "b_slope": float(b),
            }
        pred = g_ir / denom
        if not math.isfinite(pred):
            return {
                "fit_ok": False,
                "fit_reason": "non_finite_prediction",
                "G_ir": None,
                "k_star": None,
                "r2": None,
                "rmse_rel": None,
                "max_abs_rel": None,
                "a_intercept": float(a),
                "b_slope": float(b),
            }
        preds.append(float(pred))
        obs.append(float(g))
        rel.append((float(pred) - float(g)) / float(g))

    n_pred = len(preds)
    if n_pred == 0:
        return {
            "fit_ok": False,
            "fit_reason": "no_predictions",
            "G_ir": None,
            "k_star": None,
            "r2": None,
            "rmse_rel": None,
            "max_abs_rel": None,
            "a_intercept": float(a),
            "b_slope": float(b),
        }

    mean_obs = sum(obs) / float(n_pred)
    ss_res = sum((p - o) * (p - o) for p, o in zip(preds, obs))
    ss_tot = sum((o - mean_obs) * (o - mean_obs) for o in obs)
    if ss_tot > 0.0:
        r2 = 1.0 - (ss_res / ss_tot)
    else:
        r2 = 1.0 if ss_res <= 1e-24 else 0.0

    rmse_rel = math.sqrt(sum(x * x for x in rel) / float(n_pred))
    max_abs_rel = max(abs(x) for x in rel)

    return {
        "fit_ok": True,
        "fit_reason": "ok",
        "G_ir": float(g_ir),
        "k_star": float(k_star),
        "r2": float(r2),
        "rmse_rel": float(rmse_rel),
        "max_abs_rel": float(max_abs_rel),
        "a_intercept": float(a),
        "b_slope": float(b),
    }


def _prepare_points(
    table: RGFlowTable,
    *,
    k_min: Optional[float],
    k_max: Optional[float],
) -> Tuple[List[Tuple[float, float]], int, int, List[str]]:
    points: List[Tuple[float, float]] = []
    n_filtered = 0
    n_skipped = 0
    warnings: List[str] = []

    for row in table.rows:
        k = float(row.k)
        g = float(row.g)

        if k_min is not None and k < k_min:
            n_filtered += 1
            continue
        if k_max is not None and k > k_max:
            n_filtered += 1
            continue

        if (not math.isfinite(g)) or g <= 0.0:
            n_skipped += 1
            continue

        points.append((k, g))

    if n_filtered > 0:
        warnings.append(f"filtered_out_of_k_range={n_filtered}")
    if n_skipped > 0:
        warnings.append(f"skipped_non_positive_or_non_finite_g={n_skipped}")

    return points, n_filtered, n_skipped, warnings


def _process_one(
    input_path: Path,
    *,
    k_min: Optional[float],
    k_max: Optional[float],
) -> Dict[str, Any]:
    table = load_flow_table_csv(str(input_path))
    rows = table.rows
    points, n_filtered, n_skipped, warnings = _prepare_points(table, k_min=k_min, k_max=k_max)
    fit = _fit_pade_pole2(points)

    out: Dict[str, Any] = {
        "path": str(input_path),
        "fit_ok": bool(fit.get("fit_ok", False)),
        "fit_reason": str(fit.get("fit_reason", "unknown")),
        "n_rows": int(len(rows)),
        "n_rows_used": int(len(points)),
        "n_filtered_rows": int(n_filtered),
        "n_skipped_rows": int(n_skipped),
        "k_min": float(min(r.k for r in rows)),
        "k_max": float(max(r.k for r in rows)),
        "G_ir": fit.get("G_ir"),
        "k_star": fit.get("k_star"),
        "r2": fit.get("r2"),
        "rmse_rel": fit.get("rmse_rel"),
        "max_abs_rel": fit.get("max_abs_rel"),
        "warnings": sorted(list(warnings + ([] if fit.get("fit_ok") else [str(fit.get("fit_reason"))]))),
        "_points": points,
    }
    return out


def _build_payload(args: argparse.Namespace) -> Dict[str, Any]:
    files: List[Dict[str, Any]] = []

    for raw in args.input:
        p = Path(str(raw)).expanduser().resolve()
        one = _process_one(p, k_min=args.k_range_min, k_max=args.k_range_max)
        files.append(one)

    pooled_points: List[Tuple[float, float]] = []
    for item in files:
        pooled_points.extend(item.get("_points") or [])

    aggregate_fit = _fit_pade_pole2(pooled_points)

    n_fit_ok = sum(1 for item in files if item.get("fit_ok") is True)
    n_fit_fail = len(files) - n_fit_ok

    warnings_all: List[str] = []
    for item in files:
        for warn in item.get("warnings") or []:
            warnings_all.append(f"{Path(item.get('path', '')).name}:{warn}")

    payload: Dict[str, Any] = {
        "tool": SCHEMA_ID,
        "model": "pade_pole2",
        "mode": str(args.mode),
        "summary": {
            "n_inputs": int(len(files)),
            "n_rows_total": int(sum(int(item["n_rows"]) for item in files)),
            "n_rows_used_total": int(sum(int(item["n_rows_used"]) for item in files)),
            "n_fit_ok": int(n_fit_ok),
            "n_fit_fail": int(n_fit_fail),
            "k_range_applied": bool((args.k_range_min is not None) or (args.k_range_max is not None)),
            "k_range_min": args.k_range_min,
            "k_range_max": args.k_range_max,
            "aggregate_fit_ok": bool(aggregate_fit.get("fit_ok", False)),
            "aggregate_fit_reason": str(aggregate_fit.get("fit_reason", "unknown")),
            "aggregate_G_ir": aggregate_fit.get("G_ir"),
            "aggregate_k_star": aggregate_fit.get("k_star"),
            "aggregate_r2": aggregate_fit.get("r2"),
            "aggregate_rmse_rel": aggregate_fit.get("rmse_rel"),
            "aggregate_max_abs_rel": aggregate_fit.get("max_abs_rel"),
            "n_skipped_rows_total": int(sum(int(item["n_skipped_rows"]) for item in files)),
        },
        "files": [
            {
                key: value
                for key, value in item.items()
                if key != "_points"
            }
            for item in files
        ],
        "warnings": sorted(warnings_all),
    }
    return payload


def _build_illustrative_payload(args: argparse.Namespace) -> Dict[str, Any]:
    # Deterministic internal toy profile for snippet generation when no external file is provided.
    points: List[Tuple[float, float]] = []
    g_ir_true = 1.8
    k_star_true = 3.4
    for k in (0.2, 0.5, 0.9, 1.3, 1.8, 2.2):
        g = g_ir_true / (1.0 - (float(k) / k_star_true) ** 2)
        points.append((float(k), float(g)))

    fit = _fit_pade_pole2(points)
    warnings: List[str] = [] if bool(fit.get("fit_ok", False)) else [str(fit.get("fit_reason", "fit_failed"))]
    file_entry = {
        "path": "<illustrative_internal>",
        "fit_ok": bool(fit.get("fit_ok", False)),
        "fit_reason": str(fit.get("fit_reason", "unknown")),
        "n_rows": len(points),
        "n_rows_used": len(points),
        "n_filtered_rows": 0,
        "n_skipped_rows": 0,
        "k_min": min(k for k, _ in points),
        "k_max": max(k for k, _ in points),
        "G_ir": fit.get("G_ir"),
        "k_star": fit.get("k_star"),
        "r2": fit.get("r2"),
        "rmse_rel": fit.get("rmse_rel"),
        "max_abs_rel": fit.get("max_abs_rel"),
        "warnings": sorted(warnings),
    }
    n_fit_ok = 1 if bool(file_entry["fit_ok"]) else 0
    payload: Dict[str, Any] = {
        "tool": SCHEMA_ID,
        "model": "pade_pole2",
        "mode": str(args.mode),
        "illustrative_internal": True,
        "summary": {
            "n_inputs": 1,
            "n_rows_total": len(points),
            "n_rows_used_total": len(points),
            "n_fit_ok": n_fit_ok,
            "n_fit_fail": 1 - n_fit_ok,
            "k_range_applied": False,
            "k_range_min": None,
            "k_range_max": None,
            "aggregate_fit_ok": bool(fit.get("fit_ok", False)),
            "aggregate_fit_reason": str(fit.get("fit_reason", "unknown")),
            "aggregate_G_ir": fit.get("G_ir"),
            "aggregate_k_star": fit.get("k_star"),
            "aggregate_r2": fit.get("r2"),
            "aggregate_rmse_rel": fit.get("rmse_rel"),
            "aggregate_max_abs_rel": fit.get("max_abs_rel"),
            "n_skipped_rows_total": 0,
        },
        "files": [file_entry],
        "warnings": sorted(warnings),
    }
    return payload


def _payload_to_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n"


def _payload_to_text(payload: Dict[str, Any]) -> str:
    summary = payload.get("summary") or {}
    lines: List[str] = []

    lines.append("INPUTS")
    lines.append(f"  n_inputs={_fmt(summary.get('n_inputs'))}")
    lines.append(f"  n_rows_total={_fmt(summary.get('n_rows_total'))}")
    lines.append(f"  n_rows_used_total={_fmt(summary.get('n_rows_used_total'))}")
    lines.append(f"  k_range_applied={_fmt(summary.get('k_range_applied'))}")
    lines.append(f"  k_range_min={_fmt(summary.get('k_range_min'))}")
    lines.append(f"  k_range_max={_fmt(summary.get('k_range_max'))}")

    lines.append("FIT_MODEL")
    lines.append(f"  model={_fmt(payload.get('model'))}")

    lines.append("FIT_RESULTS")
    if payload.get("mode") == "by_file":
        for item in payload.get("files") or []:
            lines.append(f"  file={_fmt(item.get('path'))}")
            lines.append(f"    fit_ok={_fmt(item.get('fit_ok'))}")
            lines.append(f"    G_ir={_fmt(item.get('G_ir'))}")
            lines.append(f"    k_star={_fmt(item.get('k_star'))}")
            lines.append(f"    n_used={_fmt(item.get('n_rows_used'))}")
    else:
        lines.append(f"  aggregate_fit_ok={_fmt(summary.get('aggregate_fit_ok'))}")
        lines.append(f"  aggregate_fit_reason={_fmt(summary.get('aggregate_fit_reason'))}")
        lines.append(f"  G_ir={_fmt(summary.get('aggregate_G_ir'))}")
        lines.append(f"  k_star={_fmt(summary.get('aggregate_k_star'))}")

    lines.append("FIT_QUALITY")
    lines.append(f"  r2={_fmt(summary.get('aggregate_r2'))}")
    lines.append(f"  rmse_rel={_fmt(summary.get('aggregate_rmse_rel'))}")
    lines.append(f"  max_abs_rel={_fmt(summary.get('aggregate_max_abs_rel'))}")
    lines.append(f"  n_skipped_rows={_fmt(summary.get('n_skipped_rows_total'))}")

    lines.append("WARNINGS")
    warnings = payload.get("warnings") or []
    if warnings:
        for warning in warnings:
            lines.append(f"  - {warning}")
    else:
        lines.append("  - none")

    return "\n".join(lines) + "\n"


def _emit_snippets(outdir: Path, payload: Dict[str, Any]) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    summary = payload.get("summary") or {}

    g_ir = summary.get("aggregate_G_ir")
    k_star = summary.get("aggregate_k_star")
    r2 = summary.get("aggregate_r2")
    rmse_rel = summary.get("aggregate_rmse_rel")
    fit_ok = bool(summary.get("aggregate_fit_ok"))
    fit_reason = summary.get("aggregate_fit_reason")

    tex_lines = [
        f"% {SNIPPET_MARKER}",
        "% Diagnostic-only Pad\\'e fit summary for external RG flow tables.",
        "\\paragraph{RG flow Pad\\'e fit (diagnostic).}",
        "\\begin{itemize}",
        f"\\item Model: \\texttt{{pade\\_pole2}}.",
        f"\\item Inputs: $N_{{\\mathrm{{files}}}}={_fmt(summary.get('n_inputs'))}$, $N_{{\\mathrm{{rows,used}}}}={_fmt(summary.get('n_rows_used_total'))}$.",
        f"\\item Fit status: {('ok' if fit_ok else 'not available')} ({_fmt(fit_reason)}).",
        f"\\item $G_{{\\mathrm{{IR}}}}={_fmt(g_ir)}$, $k_*={_fmt(k_star)}$, $R^2={_fmt(r2)}$, $\\mathrm{{RMSE}}_{{\\mathrm{{rel}}}}={_fmt(rmse_rel)}$.",
        "\\end{itemize}",
        "\\noindent\\textit{Exploratory fit to provided flow-table inputs; units depend on input table conventions; this is not a first-principles derivation, and scale identification remains ansatz-level in current scope.}",
        "",
    ]

    md_lines = [
        f"<!-- {SNIPPET_MARKER} -->",
        "### RG flow Pade fit (diagnostic)",
        "",
        "- model: `pade_pole2`",
        f"- inputs: n_files={_fmt(summary.get('n_inputs'))}, n_rows_used={_fmt(summary.get('n_rows_used_total'))}",
        f"- fit_status: {'ok' if fit_ok else 'not_available'} ({_fmt(fit_reason)})",
        f"- G_IR: {_fmt(g_ir)}",
        f"- k_star: {_fmt(k_star)}",
        f"- r2: {_fmt(r2)}",
        f"- rmse_rel: {_fmt(rmse_rel)}",
        "",
        "Exploratory fit to provided flow-table inputs; units depend on input table conventions; not a first-principles derivation; scale identification remains ansatz-level.",
        "",
    ]

    (outdir / "phase2_rg_pade_fit.tex").write_text("\n".join(tex_lines), encoding="utf-8")
    (outdir / "phase2_rg_pade_fit.md").write_text("\n".join(md_lines), encoding="utf-8")
    snippet_json = {
        "marker": SNIPPET_MARKER,
        "schema": "phase2_rg_pade_fit_snippet_v1",
        "summary": {
            "fit_ok": bool(summary.get("aggregate_fit_ok")),
            "fit_reason": summary.get("aggregate_fit_reason"),
            "G_ir": summary.get("aggregate_G_ir"),
            "k_star": summary.get("aggregate_k_star"),
            "r2": summary.get("aggregate_r2"),
            "rmse_rel": summary.get("aggregate_rmse_rel"),
            "n_inputs": summary.get("n_inputs"),
            "n_rows_used_total": summary.get("n_rows_used_total"),
        },
    }
    (outdir / "phase2_rg_pade_fit.json").write_text(
        json.dumps(snippet_json, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)

    if args.k_range_min is not None and args.k_range_max is not None and float(args.k_range_min) > float(args.k_range_max):
        print("ERROR: --k-range-min must be <= --k-range-max", file=sys.stderr)
        return 1

    try:
        if list(args.input):
            payload = _build_payload(args)
        else:
            if not args.emit_snippets:
                print("ERROR: at least one --input is required unless --emit-snippets is used", file=sys.stderr)
                return 1
            payload = _build_illustrative_payload(args)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    out_json = _payload_to_json(payload)
    out_text = _payload_to_text(payload)

    if args.format == "json":
        sys.stdout.write(out_json)
    else:
        sys.stdout.write(out_text)

    if args.json_out:
        out_path = Path(str(args.json_out)).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(out_json, encoding="utf-8")

    if args.emit_snippets:
        _emit_snippets(Path(str(args.emit_snippets)).expanduser().resolve(), payload)

    n_fit_ok = int((payload.get("summary") or {}).get("n_fit_ok") or 0)
    if n_fit_ok <= 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

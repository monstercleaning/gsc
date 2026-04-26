#!/usr/bin/env python3
"""Phase-2 sigma-origin FRG flow-table scaffold report (stdlib-only)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gsc.rg.flow_table import RGFlowRow, RGFlowTable, load_flow_table_csv  # noqa: E402


SCHEMA_ID = "phase2_rg_flow_table_report_v1"
SNIPPET_MARKER = "phase2_rg_flow_table_snippet_v1"


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Deterministic FRG flow-table report scaffold (diagnostic-only).")
    ap.add_argument("--input", default=None, help="Path to FRG flow CSV (must include k,g).")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    ap.add_argument("--json-out", default=None, help="Optional JSON output path (always writes JSON there).")
    ap.add_argument(
        "--emit-snippets",
        default=None,
        help="Optional output directory for deterministic phase2_rg_flow_table.{md,tex,json} snippets.",
    )
    ap.add_argument(
        "--k-star-g-threshold",
        type=float,
        default=1.0,
        help="Heuristic threshold on g(k) used for k* crossing estimate.",
    )
    return ap.parse_args(argv)


def _json_payload(path: Path, *, threshold: float) -> Dict[str, Any]:
    table = load_flow_table_csv(str(path))
    summary = table.summary_dict(k_star_threshold=float(threshold))
    return {
        "schema": SCHEMA_ID,
        "input": str(path),
        "is_illustrative": False,
        "summary": summary,
        "notes": [
            "Diagnostic heuristic only: this report ingests external FRG flow tables.",
            "It is not a first-principles derivation of sigma(t).",
            "k(sigma) identification remains ansatz-level in the current release roadmap.",
        ],
    }


def _illustrative_payload(*, threshold: float) -> Dict[str, Any]:
    # Deterministic built-in toy profile for snippet generation when no input is supplied.
    rows = [
        RGFlowRow(k=0.2, g=0.42, lambda_value=0.08),
        RGFlowRow(k=0.5, g=0.56, lambda_value=0.10),
        RGFlowRow(k=1.0, g=0.79, lambda_value=0.14),
        RGFlowRow(k=2.0, g=1.05, lambda_value=0.18),
        RGFlowRow(k=4.0, g=1.22, lambda_value=0.22),
    ]
    table = RGFlowTable(rows)
    summary = table.summary_dict(k_star_threshold=float(threshold))
    return {
        "schema": SCHEMA_ID,
        "input": "<illustrative_internal>",
        "is_illustrative": True,
        "summary": summary,
        "notes": [
            "Illustrative diagnostic scaffold using an internal toy flow profile.",
            "Status/ansatz-level only; not a first-principles FRG derivation.",
            "k(sigma) identification remains an open roadmap item.",
        ],
    }


def _as_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n"


def _as_text(payload: Dict[str, Any]) -> str:
    summary = payload.get("summary", {})
    k_star = summary.get("k_star", {}) if isinstance(summary, dict) else {}
    lines = [
        "INPUT",
        f"  path={payload.get('input')}",
        f"  n_rows={summary.get('n_rows')}",
        "RANGE",
        f"  k_min={summary.get('k_min')}",
        f"  k_max={summary.get('k_max')}",
        f"  g_min={summary.get('g_min')}",
        f"  g_max={summary.get('g_max')}",
        "K_STAR",
        f"  threshold={k_star.get('threshold')}",
        f"  k_star={k_star.get('k_star')}",
        f"  reason={k_star.get('reason')}",
    ]
    notes = payload.get("notes", [])
    lines.append("NOTES")
    if isinstance(notes, list):
        for note in notes:
            lines.append(f"  - {note}")
    return "\n".join(lines) + "\n"


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        try:
            return f"{float(value):.12g}"
        except Exception:
            return str(value)
    return str(value)


def _emit_snippets(outdir: Path, payload: Dict[str, Any]) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    k_star = summary.get("k_star") if isinstance(summary.get("k_star"), dict) else {}
    input_tex = str(payload.get("input", "unknown")).replace("_", "\\_")

    tex_lines = [
        f"% {SNIPPET_MARKER}",
        "% Deterministic RG flow-table status snippet (diagnostic-only).",
        "\\paragraph{RG flow-table status (diagnostic).}",
        "\\begin{itemize}",
        f"\\item Input source: \\texttt{{{input_tex}}}.",
        f"\\item Rows: $N={_fmt(summary.get('n_rows'))}$, $k_\\min={_fmt(summary.get('k_min'))}$, $k_\\max={_fmt(summary.get('k_max'))}$.",
        f"\\item Coupling range: $g_\\min={_fmt(summary.get('g_min'))}$, $g_\\max={_fmt(summary.get('g_max'))}$.",
        f"\\item Heuristic $k_*$ ({_fmt(k_star.get('threshold'))} threshold): {_fmt(k_star.get('k_star'))} ({_fmt(k_star.get('reason'))}).",
        "\\end{itemize}",
        "\\noindent\\textit{Status / illustrative / ansatz-level only; not a first-principles FRG derivation; no claim of derivation.}",
        "",
    ]
    md_lines = [
        f"<!-- {SNIPPET_MARKER} -->",
        "### RG flow-table status (diagnostic)",
        "",
        f"- input: `{payload.get('input')}`",
        f"- n_rows: {_fmt(summary.get('n_rows'))}",
        f"- k_range: [{_fmt(summary.get('k_min'))}, {_fmt(summary.get('k_max'))}]",
        f"- g_range: [{_fmt(summary.get('g_min'))}, {_fmt(summary.get('g_max'))}]",
        f"- heuristic_k_star(threshold={_fmt(k_star.get('threshold'))}): {_fmt(k_star.get('k_star'))} ({_fmt(k_star.get('reason'))})",
        "",
        "Status / illustrative / ansatz-level only; not a first-principles FRG derivation; no claim of derivation.",
        "",
    ]

    snippet_json = {
        "marker": SNIPPET_MARKER,
        "schema": "phase2_rg_flow_table_snippet_v1",
        "source": payload.get("input"),
        "summary": summary,
    }

    (outdir / "phase2_rg_flow_table.tex").write_text("\n".join(tex_lines), encoding="utf-8")
    (outdir / "phase2_rg_flow_table.md").write_text("\n".join(md_lines), encoding="utf-8")
    (outdir / "phase2_rg_flow_table.json").write_text(
        json.dumps(snippet_json, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        threshold = float(args.k_star_g_threshold)
        raw_input = str(args.input or "").strip()
        if raw_input:
            src = Path(raw_input).expanduser().resolve()
            payload = _json_payload(src, threshold=threshold)
        else:
            if not args.emit_snippets:
                print("ERROR: --input is required unless --emit-snippets is used", file=sys.stderr)
                return 1
            payload = _illustrative_payload(threshold=threshold)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.format == "json":
        sys.stdout.write(_as_json(payload))
    else:
        sys.stdout.write(_as_text(payload))

    if args.json_out:
        out_path = Path(str(args.json_out)).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(_as_json(payload), encoding="utf-8")

    if args.emit_snippets:
        _emit_snippets(Path(str(args.emit_snippets)).expanduser().resolve(), payload)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

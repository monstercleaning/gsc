#!/usr/bin/env python3
"""Canonical Phase-2 E2 paper-snippet catalog (stdlib-only).

Single source of truth for:
- snippet stem order used by the phase2_e2_all aggregator
- snippet source relpaths inside paper assets
- required snippet relpaths for verify checks
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import PurePosixPath
from typing import Dict, Iterable, List, Sequence, Tuple


DRIFT_SNIPPETS_REL_DIR = "paper_assets_cmb_e2_drift_constrained_closure_bound/snippets"
KNOBS_SNIPPETS_REL_DIR = "paper_assets_cmb_e2_closure_to_physical_knobs/snippets"

PHASE2_E2_ALL_STEM = "phase2_e2_all"
PHASE2_E2_ALL_MARKER = "phase2_e2_all_snippet_v1"

# Canonical include order for paper-facing Phase-2 snippets.
PHASE2_E2_ALL_ORDER: Tuple[str, ...] = (
    "phase2_e2_summary",
    "phase2_e2_scan_audit",
    "phase2_e2_best_candidates",
    "phase2_sf_rsd_summary",
    "phase2_sf_fsigma8",
    "phase2_rg_flow_table",
    "phase2_rg_pade_fit",
    "phase2_e2_drift_table",
    "phase2_e2_cmb_tension",
    "phase2_e2_closure_bound",
    "phase2_e2_physical_knobs",
)

# Source locations of canonical snippets produced by phase2_e2_make_paper_assets.py.
PHASE2_E2_SNIPPET_SOURCE_REL_BY_STEM: Dict[str, str] = {
    "phase2_e2_summary": f"{DRIFT_SNIPPETS_REL_DIR}/phase2_e2_summary",
    "phase2_e2_scan_audit": f"{DRIFT_SNIPPETS_REL_DIR}/phase2_e2_scan_audit",
    "phase2_e2_best_candidates": f"{KNOBS_SNIPPETS_REL_DIR}/phase2_e2_best_candidates",
    "phase2_sf_rsd_summary": f"{KNOBS_SNIPPETS_REL_DIR}/phase2_sf_rsd_summary",
    "phase2_sf_fsigma8": f"{KNOBS_SNIPPETS_REL_DIR}/phase2_sf_fsigma8",
    "phase2_rg_flow_table": f"{KNOBS_SNIPPETS_REL_DIR}/phase2_rg_flow_table",
    "phase2_rg_pade_fit": f"{KNOBS_SNIPPETS_REL_DIR}/phase2_rg_pade_fit",
    "phase2_e2_drift_table": f"{DRIFT_SNIPPETS_REL_DIR}/phase2_e2_drift_table",
    "phase2_e2_cmb_tension": f"{DRIFT_SNIPPETS_REL_DIR}/phase2_e2_cmb_tension",
    "phase2_e2_closure_bound": f"{DRIFT_SNIPPETS_REL_DIR}/phase2_e2_closure_bound",
    "phase2_e2_physical_knobs": f"{KNOBS_SNIPPETS_REL_DIR}/phase2_e2_physical_knobs",
}

PHASE2_E2_ALL_TEX_RELPATH = f"{DRIFT_SNIPPETS_REL_DIR}/{PHASE2_E2_ALL_STEM}.tex"
PHASE2_E2_ALL_MD_RELPATH = f"{DRIFT_SNIPPETS_REL_DIR}/{PHASE2_E2_ALL_STEM}.md"


def _normalize_relpath(path: str) -> str:
    return str(PurePosixPath(path))


def canonical_snippet_stems() -> Tuple[str, ...]:
    return PHASE2_E2_ALL_ORDER


def canonical_snippet_source_relpath(stem: str, ext: str) -> str:
    if stem not in PHASE2_E2_SNIPPET_SOURCE_REL_BY_STEM:
        raise KeyError(f"unknown Phase-2 snippet stem: {stem!r}")
    text_ext = str(ext).strip().lower().lstrip(".")
    if text_ext not in {"tex", "md"}:
        raise ValueError(f"unsupported snippet extension: {ext!r}")
    return _normalize_relpath(f"{PHASE2_E2_SNIPPET_SOURCE_REL_BY_STEM[stem]}.{text_ext}")


def canonical_required_snippet_relpaths(*, include_aggregator: bool = True) -> Tuple[str, ...]:
    relpaths: List[str] = []
    for stem in PHASE2_E2_ALL_ORDER:
        relpaths.append(canonical_snippet_source_relpath(stem, "md"))
        relpaths.append(canonical_snippet_source_relpath(stem, "tex"))
    if include_aggregator:
        relpaths.append(_normalize_relpath(PHASE2_E2_ALL_MD_RELPATH))
        relpaths.append(_normalize_relpath(PHASE2_E2_ALL_TEX_RELPATH))
    return tuple(dict.fromkeys(relpaths))


def canonical_all_tex_inputs() -> Tuple[str, ...]:
    return tuple(f"\\input{{{stem}.tex}}" for stem in PHASE2_E2_ALL_ORDER)


def canonical_all_md_begin_markers() -> Tuple[str, ...]:
    return tuple(f"BEGIN {stem}.md" for stem in PHASE2_E2_ALL_ORDER)


def iter_canonical_tex_filenames() -> Iterable[str]:
    for stem in PHASE2_E2_ALL_ORDER:
        yield f"{stem}.tex"


def iter_canonical_md_filenames() -> Iterable[str]:
    for stem in PHASE2_E2_ALL_ORDER:
        yield f"{stem}.md"


def catalog_payload() -> Dict[str, object]:
    return {
        "tool": "phase2_e2_snippets_catalog_v1",
        "all_marker": PHASE2_E2_ALL_MARKER,
        "all_stem": PHASE2_E2_ALL_STEM,
        "all_order": list(PHASE2_E2_ALL_ORDER),
        "all_tex_relpath": _normalize_relpath(PHASE2_E2_ALL_TEX_RELPATH),
        "all_md_relpath": _normalize_relpath(PHASE2_E2_ALL_MD_RELPATH),
        "source_rel_by_stem": dict(PHASE2_E2_SNIPPET_SOURCE_REL_BY_STEM),
        "required_relpaths_with_aggregator": list(canonical_required_snippet_relpaths(include_aggregator=True)),
        "required_relpaths_without_aggregator": list(canonical_required_snippet_relpaths(include_aggregator=False)),
    }


def _render_text(payload: Dict[str, object]) -> str:
    stems = payload.get("all_order") or []
    required = payload.get("required_relpaths_with_aggregator") or []
    lines: List[str] = []
    lines.append(f"tool={payload.get('tool')}")
    lines.append(f"all_stem={payload.get('all_stem')}")
    lines.append(f"all_marker={payload.get('all_marker')}")
    lines.append("stems:")
    for stem in stems:
        lines.append(f"  - {stem}")
    lines.append("required_relpaths_with_aggregator:")
    for relpath in required:
        lines.append(f"  - {relpath}")
    return "\n".join(lines) + "\n"


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Canonical Phase-2 E2 snippet catalog exporter.")
    ap.add_argument("--format", choices=("text", "json"), default="text", help="Output format.")
    return ap.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    payload = catalog_payload()
    if args.format == "json":
        sys.stdout.write(json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write(_render_text(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

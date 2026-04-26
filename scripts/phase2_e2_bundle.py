#!/usr/bin/env python3
"""Deterministic stdlib-only Phase-2 E2 analysis bundle entrypoint.

This tool orchestrates shard merge + report generation + optional refine-plan
emission + manifest/meta writing in one command.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


STEP_ORDER: List[str] = [
    "merge",
    "pareto",
    "diagnostics",
    "tension",
    "sensitivity",
    "paper_assets",
    "robustness_compare",
    "robustness_aggregate",
    "manifest",
    "meta",
]

STEP_SET = set(STEP_ORDER)
_TS_KEYS = {"generated_utc", "created_utc"}
_MD_TS_RE = re.compile(r"generated\s*(?:\(utc\)|utc)?\s*:", re.IGNORECASE)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_or_abs(path: Path, *, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except Exception:
        return str(path.resolve())


def _file_entry(path: Path, *, rel_base: Path) -> Dict[str, Any]:
    resolved = path.resolve()
    return {
        "path": _relative_or_abs(resolved, base=rel_base),
        "sha256": _sha256_file(resolved),
        "bytes": int(resolved.stat().st_size),
    }


def _is_jsonl_file(path: Path) -> bool:
    if not path.is_file():
        return False
    lower_name = path.name.lower()
    return lower_name.endswith(".jsonl") or lower_name.endswith(".jsonl.gz")


def _discover_jsonl_targets(raw_targets: Sequence[str], *, recursive: bool) -> List[Path]:
    found: List[Path] = []
    seen: set[Path] = set()
    for raw in raw_targets:
        candidate = Path(raw).expanduser().resolve()
        if candidate.is_file():
            if not _is_jsonl_file(candidate):
                raise SystemExit(f"Input file is not .jsonl: {candidate}")
            if candidate not in seen:
                seen.add(candidate)
                found.append(candidate)
            continue
        if candidate.is_dir():
            if recursive:
                iterator = list(candidate.rglob("*.jsonl")) + list(candidate.rglob("*.jsonl.gz"))
            else:
                iterator = list(candidate.glob("*.jsonl")) + list(candidate.glob("*.jsonl.gz"))
            for path in sorted(p.resolve() for p in iterator if p.is_file()):
                if path not in seen:
                    seen.add(path)
                    found.append(path)
            continue
        raise SystemExit(f"Input path not found: {candidate}")
    return sorted(found)


def _git_sha(repo_root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            text=True,
            capture_output=True,
            check=True,
        )
        out = str((proc.stdout or "").strip())
        return out or "unknown"
    except Exception:
        return "unknown"


def _normalize_invocation_argv(argv: Sequence[str], *, outdir: Path) -> List[str]:
    normalized: List[str] = []
    outdir_abs = str(outdir.resolve())
    i = 0
    while i < len(argv):
        token = str(argv[i])
        if token in {"--outdir", "--report-out"}:
            normalized.append(token)
            if i + 1 < len(argv):
                normalized.append("<PATH>")
                i += 2
                continue
        if token.startswith("--outdir="):
            normalized.append("--outdir=<PATH>")
            i += 1
            continue
        if token == outdir_abs:
            normalized.append("<OUTDIR>")
            i += 1
            continue
        if outdir_abs and token.startswith(outdir_abs + os.sep):
            normalized.append("<OUTDIR>/" + token[len(outdir_abs) + 1 :])
            i += 1
            continue
        normalized.append(token)
        i += 1
    return normalized


def _strip_timestamp_fields(value: Any) -> Any:
    if isinstance(value, Mapping):
        out: Dict[str, Any] = {}
        for key in sorted(str(k) for k in value.keys()):
            if key in _TS_KEYS:
                continue
            out[key] = _strip_timestamp_fields(value[key])
        return out
    if isinstance(value, list):
        return [_strip_timestamp_fields(item) for item in value]
    return value


def _normalize_outdir_paths(value: Any, *, outdir: Path) -> Any:
    outdir_resolved = str(outdir.resolve())
    if isinstance(value, Mapping):
        out: Dict[str, Any] = {}
        for key in sorted(str(k) for k in value.keys()):
            out[key] = _normalize_outdir_paths(value[key], outdir=outdir)
        return out
    if isinstance(value, list):
        return [_normalize_outdir_paths(item, outdir=outdir) for item in value]
    if isinstance(value, str):
        text = str(value)
        if text == outdir_resolved:
            return "<OUTDIR>"
        prefix = outdir_resolved + os.sep
        if text.startswith(prefix):
            return "<OUTDIR>/" + text[len(prefix) :]
        return text
    return value


def _canonicalize_json_file(path: Path, *, outdir: Path) -> None:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    cleaned = _strip_timestamp_fields(obj)
    cleaned = _normalize_outdir_paths(cleaned, outdir=outdir)
    path.write_text(json.dumps(cleaned, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _canonicalize_markdown_file(path: Path, *, outdir: Path) -> None:
    outdir_resolved = str(outdir.resolve())
    prefix = outdir_resolved + os.sep
    lines = path.read_text(encoding="utf-8").splitlines()
    kept: List[str] = []
    for line in lines:
        if _MD_TS_RE.search(line) is not None:
            continue
        replaced = line.replace(prefix, "<OUTDIR>/").replace(outdir_resolved, "<OUTDIR>")
        kept.append(replaced)
    path.write_text("\n".join(kept).rstrip("\n") + "\n", encoding="utf-8")


def _canonicalize_outputs(paths: Sequence[Path], *, outdir: Path) -> None:
    for path in paths:
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix == ".json":
            _canonicalize_json_file(path, outdir=outdir)
        elif suffix == ".md":
            _canonicalize_markdown_file(path, outdir=outdir)


def _run_cmd(
    cmd: Sequence[str],
    *,
    cwd: Path,
    dry_run: bool,
) -> Tuple[int, str, str]:
    pretty = " ".join(json.dumps(str(x)) for x in cmd)
    if dry_run:
        print(f"[dry-run] {pretty}")
        return 0, "", ""
    proc = subprocess.run(
        [str(x) for x in cmd],
        cwd=str(cwd),
        text=True,
        capture_output=True,
    )
    stdout = str(proc.stdout or "")
    stderr = str(proc.stderr or "")
    if stdout.strip():
        print(stdout.strip())
    if proc.returncode != 0 and stderr.strip():
        print(stderr.strip(), file=sys.stderr)
    return int(proc.returncode), stdout, stderr


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _refresh_paper_assets_manifest(manifest_path: Path) -> None:
    if not manifest_path.is_file():
        return
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(payload, Mapping):
        return
    manifest_dir = manifest_path.parent.resolve()
    updated = dict(payload)
    changed = False
    for key in ("files", "snippets"):
        section = payload.get(key)
        if not isinstance(section, list):
            continue
        rows: List[Dict[str, Any]] = []
        for entry in section:
            if not isinstance(entry, Mapping):
                continue
            relpath = str(entry.get("relpath", "")).strip()
            if not relpath:
                continue
            abs_path = (manifest_dir / relpath).resolve()
            if not abs_path.is_file():
                rows.append(dict(entry))
                continue
            rows.append(
                {
                    "relpath": relpath,
                    "sha256": _sha256_file(abs_path),
                    "bytes": int(abs_path.stat().st_size),
                }
            )
        rows = sorted(rows, key=lambda r: str(r.get("relpath", "")))
        if rows != section:
            changed = True
        updated[key] = rows
    if changed:
        _write_json(manifest_path, updated)


def _parse_steps(raw: str) -> List[str]:
    text = str(raw).strip()
    if not text or text.lower() == "all":
        return list(STEP_ORDER)
    tokens = [tok.strip() for tok in text.split(",") if tok.strip()]
    invalid = [tok for tok in tokens if tok not in STEP_SET]
    if invalid:
        raise SystemExit(f"Unknown --steps entries: {', '.join(invalid)}")
    ordered = [name for name in STEP_ORDER if name in set(tokens)]
    if "meta" not in ordered:
        ordered.append("meta")
    return ordered


def _resolve_optional_jsonl_group(raw: Sequence[str], *, recursive: bool) -> List[Path]:
    if not raw:
        return []
    return _discover_jsonl_targets(raw, recursive=recursive)


def _require_outputs(paths: Sequence[Path]) -> Optional[str]:
    missing = [str(p) for p in paths if not p.is_file()]
    if missing:
        return f"missing expected outputs: {', '.join(missing)}"
    return None


def _step_result(status: str, *, reason: str = "", outputs: Optional[Sequence[Path]] = None, outdir: Path) -> Dict[str, Any]:
    output_entries: List[Dict[str, Any]] = []
    for path in outputs or []:
        if path.is_file():
            output_entries.append(_file_entry(path, rel_base=outdir))
    payload: Dict[str, Any] = {
        "status": str(status),
        "reason": str(reason),
        "outputs": output_entries,
    }
    return payload


def _invoke_step(
    *,
    name: str,
    cmd: Sequence[str],
    cwd: Path,
    dry_run: bool,
    strict: bool,
    expected_outputs: Sequence[Path],
    canonicalize_outputs: bool,
    outdir: Path,
) -> Dict[str, Any]:
    rc, stdout, stderr = _run_cmd(cmd, cwd=cwd, dry_run=dry_run)
    if dry_run:
        return _step_result("ok", reason="dry-run", outputs=[], outdir=outdir)

    if rc != 0:
        reason = f"command failed (rc={rc})"
        if strict:
            detail_text = (stderr.strip() or stdout.strip() or "(no output)")
            raise SystemExit(f"Step '{name}' failed: {reason}\n{detail_text}")
        return _step_result("skipped", reason=reason, outputs=[], outdir=outdir)

    missing_reason = _require_outputs(expected_outputs)
    if missing_reason is not None:
        if strict:
            raise SystemExit(f"Step '{name}' failed: {missing_reason}")
        return _step_result("skipped", reason=missing_reason, outputs=[], outdir=outdir)

    if canonicalize_outputs:
        _canonicalize_outputs(expected_outputs, outdir=outdir)

    return _step_result("ok", outputs=expected_outputs, outdir=outdir)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="phase2_e2_bundle",
        description="Deterministic stdlib entrypoint: merge -> reports -> optional refine plan -> manifest/meta.",
    )
    ap.add_argument("--in", dest="inputs", action="append", default=[], help="Input JSONL file or directory (repeatable).")
    ap.add_argument("--recursive", action="store_true", help="If set, scan input directories recursively for *.jsonl files.")
    ap.add_argument("--outdir", type=Path, required=True, help="Output bundle directory.")
    ap.add_argument(
        "--steps",
        type=str,
        default="all",
        help="all or comma-separated subset: merge,pareto,diagnostics,tension,sensitivity,paper_assets,robustness_compare,robustness_aggregate,manifest,meta",
    )
    ap.add_argument("--strict", action="store_true", help="Fail on step errors or missing required inputs.")
    ap.add_argument("--overwrite", action="store_true", help="Allow using an existing outdir.")
    ap.add_argument(
        "--merge-policy",
        choices=["ok_then_lowest_chi2", "ok_then_first", "first"],
        default="ok_then_lowest_chi2",
    )
    ap.add_argument("--emit-refine-plan", action="store_true", help="Emit refine plan via pareto step.")
    ap.add_argument("--refine-top-k", type=int, default=None)
    ap.add_argument("--refine-n-per-seed", type=int, default=None)
    ap.add_argument("--refine-radius-rel", type=float, default=None)
    ap.add_argument("--refine-seed", type=int, default=None)
    ap.add_argument("--refine-strategy", choices=["grid", "sensitivity"], default=None)
    ap.add_argument("--refine-target-metric", type=str, default="")
    ap.add_argument("--refine-neighbors", type=int, default=None)
    ap.add_argument("--refine-top-params", type=int, default=None)
    ap.add_argument("--refine-step-frac", type=float, default=None)
    ap.add_argument("--refine-direction", choices=["downhill_only", "both"], default=None)
    ap.add_argument("--plausibility", choices=["any", "plausible_only"], default="any")
    ap.add_argument(
        "--paper-assets",
        choices=["none", "data", "snippets"],
        default="none",
        help="Optional paper-assets generation: none (default), data, snippets.",
    )
    ap.add_argument("--robustness-a", action="append", default=[], help="JSONL file/dir group A for robustness compare/aggregate.")
    ap.add_argument("--robustness-b", action="append", default=[], help="JSONL file/dir group B for robustness compare/aggregate.")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--with-timestamps", action="store_true", help="Include timestamps in bundle_meta.json (default off).")
    args = ap.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]
    scripts_dir = repo_root / "scripts"
    py = Path(sys.executable).resolve()

    selected_steps = _parse_steps(str(args.steps))
    outdir = args.outdir.expanduser().resolve()

    if outdir.exists() and any(outdir.iterdir()) and not bool(args.overwrite):
        raise SystemExit(f"Output directory exists and is not empty (use --overwrite): {outdir}")
    if not args.dry_run:
        outdir.mkdir(parents=True, exist_ok=True)

    if not args.inputs:
        raise SystemExit("At least one --in path is required")
    input_jsonls = _discover_jsonl_targets(args.inputs, recursive=bool(args.recursive))
    if not input_jsonls:
        raise SystemExit("No input JSONL files found from --in targets")

    robustness_a = _resolve_optional_jsonl_group(args.robustness_a, recursive=bool(args.recursive))
    robustness_b = _resolve_optional_jsonl_group(args.robustness_b, recursive=bool(args.recursive))
    if (robustness_a and not robustness_b) or (robustness_b and not robustness_a):
        msg = "Both --robustness-a and --robustness-b must be provided together"
        if args.strict:
            raise SystemExit(msg)
        print(f"[warn] {msg}")
        robustness_a = []
        robustness_b = []

    merged_jsonl = outdir / "merged.jsonl"
    pareto_summary = outdir / "pareto_summary.json"
    pareto_frontier = outdir / "pareto_frontier.csv"
    pareto_top = outdir / "pareto_top_positive.csv"
    pareto_md = outdir / "pareto_report.md"
    refine_plan = outdir / "refine_plan.json"

    diagnostics_md = outdir / "e2_diagnostics_summary.md"
    diagnostics_best = outdir / "e2_best_points.csv"
    diagnostics_envelope = outdir / "e2_tradeoff_envelope.csv"
    diagnostics_corr = outdir / "e2_param_correlations.csv"

    tension_json = outdir / "cmb_tension_summary.json"
    tension_md = outdir / "cmb_tension_summary.md"
    tension_csv = outdir / "cmb_tension_topk.csv"

    sensitivity_md = outdir / "sensitivity.md"
    sensitivity_csv = outdir / "sensitivity.csv"
    sensitivity_json = outdir / "sensitivity.json"

    paper_assets_root = outdir / "paper_assets"
    paper_assets_manifest = paper_assets_root / "paper_assets_manifest.json"
    paper_assets_drift_readme = paper_assets_root / "paper_assets_cmb_e2_drift_constrained_closure_bound" / "README.md"
    paper_assets_knobs_readme = paper_assets_root / "paper_assets_cmb_e2_closure_to_physical_knobs" / "README.md"

    compare_tsv = outdir / "robustness_compare.tsv"
    aggregate_csv = outdir / "robustness_aggregate.csv"
    aggregate_md = outdir / "robustness_aggregate.md"
    aggregate_meta = outdir / "robustness_aggregate_meta.json"

    manifest_json = outdir / "manifest.json"
    bundle_meta = outdir / "bundle_meta.json"
    lineage_json = outdir / "LINEAGE.json"

    step_results: Dict[str, Dict[str, Any]] = {}
    produced_files: List[Path] = []

    # merge
    if "merge" in selected_steps:
        merge_inputs = list(input_jsonls)
        if len(merge_inputs) == 1:
            merge_inputs = [merge_inputs[0], merge_inputs[0]]
        merge_cmd: List[str] = [
            str(py),
            str(scripts_dir / "phase2_e2_merge_jsonl.py"),
            *[str(p) for p in merge_inputs],
            "--out",
            str(merged_jsonl),
            "--prefer",
            str(args.merge_policy),
            "--canonicalize",
        ]
        res = _invoke_step(
            name="merge",
            cmd=merge_cmd,
            cwd=repo_root,
            dry_run=bool(args.dry_run),
            strict=bool(args.strict),
            expected_outputs=[merged_jsonl],
            canonicalize_outputs=False,
            outdir=outdir,
        )
        step_results["merge"] = res
        if res["status"] == "ok":
            produced_files.append(merged_jsonl)
    else:
        step_results["merge"] = _step_result("skipped", reason="step disabled", outputs=[], outdir=outdir)

    merged_available = merged_jsonl.is_file() or bool(args.dry_run and step_results["merge"]["status"] == "ok")

    # pareto
    if "pareto" in selected_steps:
        if not merged_available and not args.dry_run:
            reason = "merged.jsonl not available"
            if args.strict:
                raise SystemExit(f"Step 'pareto' failed: {reason}")
            step_results["pareto"] = _step_result("skipped", reason=reason, outputs=[], outdir=outdir)
        else:
            cmd = [
                str(py),
                str(scripts_dir / "phase2_e2_pareto_report.py"),
                "--jsonl",
                str(merged_jsonl),
                "--out-dir",
                str(outdir),
                "--out-summary",
                str(pareto_summary.name),
                "--out-frontier",
                str(pareto_frontier.name),
                "--out-top-positive",
                str(pareto_top.name),
                "--out-report-md",
                str(pareto_md.name),
                "--plausibility",
                str(args.plausibility),
            ]
            if bool(args.emit_refine_plan):
                cmd.extend(["--emit-refine-plan", str(refine_plan.name)])
            if args.refine_top_k is not None:
                cmd.extend(["--refine-top-k", str(int(args.refine_top_k))])
            if args.refine_n_per_seed is not None:
                cmd.extend(["--refine-n-per-seed", str(int(args.refine_n_per_seed))])
            if args.refine_radius_rel is not None:
                cmd.extend(["--refine-radius-rel", str(float(args.refine_radius_rel))])
            if args.refine_seed is not None:
                cmd.extend(["--refine-seed", str(int(args.refine_seed))])
            if args.refine_strategy is not None:
                cmd.extend(["--refine-strategy", str(args.refine_strategy)])
            if str(args.refine_target_metric).strip():
                cmd.extend(["--refine-target-metric", str(args.refine_target_metric).strip()])
            if args.refine_neighbors is not None:
                cmd.extend(["--refine-neighbors", str(int(args.refine_neighbors))])
            if args.refine_top_params is not None:
                cmd.extend(["--refine-top-params", str(int(args.refine_top_params))])
            if args.refine_step_frac is not None:
                cmd.extend(["--refine-step-frac", str(float(args.refine_step_frac))])
            if args.refine_direction is not None:
                cmd.extend(["--refine-direction", str(args.refine_direction)])

            expected = [pareto_summary, pareto_frontier, pareto_top, pareto_md]
            if bool(args.emit_refine_plan):
                expected.append(refine_plan)
            res = _invoke_step(
                name="pareto",
                cmd=cmd,
                cwd=repo_root,
                dry_run=bool(args.dry_run),
                strict=bool(args.strict),
                expected_outputs=expected,
                canonicalize_outputs=True,
                outdir=outdir,
            )
            step_results["pareto"] = res
            if res["status"] == "ok":
                produced_files.extend(expected)
    else:
        step_results["pareto"] = _step_result("skipped", reason="step disabled", outputs=[], outdir=outdir)

    # diagnostics
    if "diagnostics" in selected_steps:
        if not merged_available and not args.dry_run:
            reason = "merged.jsonl not available"
            if args.strict:
                raise SystemExit(f"Step 'diagnostics' failed: {reason}")
            step_results["diagnostics"] = _step_result("skipped", reason=reason, outputs=[], outdir=outdir)
        else:
            cmd = [
                str(py),
                str(scripts_dir / "phase2_e2_diagnostics_report.py"),
                "--jsonl",
                str(merged_jsonl),
                "--outdir",
                str(outdir),
            ]
            expected = [diagnostics_md, diagnostics_best, diagnostics_envelope, diagnostics_corr]
            res = _invoke_step(
                name="diagnostics",
                cmd=cmd,
                cwd=repo_root,
                dry_run=bool(args.dry_run),
                strict=bool(args.strict),
                expected_outputs=expected,
                canonicalize_outputs=True,
                outdir=outdir,
            )
            step_results["diagnostics"] = res
            if res["status"] == "ok":
                produced_files.extend(expected)
    else:
        step_results["diagnostics"] = _step_result("skipped", reason="step disabled", outputs=[], outdir=outdir)

    # tension
    if "tension" in selected_steps:
        if not merged_available and not args.dry_run:
            reason = "merged.jsonl not available"
            if args.strict:
                raise SystemExit(f"Step 'tension' failed: {reason}")
            step_results["tension"] = _step_result("skipped", reason=reason, outputs=[], outdir=outdir)
        else:
            cmd = [
                str(py),
                str(scripts_dir / "phase2_e2_cmb_tension_report.py"),
                "--in-jsonl",
                str(merged_jsonl),
                "--outdir",
                str(outdir),
            ]
            expected = [tension_json, tension_md, tension_csv]
            res = _invoke_step(
                name="tension",
                cmd=cmd,
                cwd=repo_root,
                dry_run=bool(args.dry_run),
                strict=bool(args.strict),
                expected_outputs=expected,
                canonicalize_outputs=True,
                outdir=outdir,
            )
            step_results["tension"] = res
            if res["status"] == "ok":
                produced_files.extend(expected)
    else:
        step_results["tension"] = _step_result("skipped", reason="step disabled", outputs=[], outdir=outdir)

    # sensitivity
    if "sensitivity" in selected_steps:
        if not merged_available and not args.dry_run:
            reason = "merged.jsonl not available"
            if args.strict:
                raise SystemExit(f"Step 'sensitivity' failed: {reason}")
            step_results["sensitivity"] = _step_result("skipped", reason=reason, outputs=[], outdir=outdir)
        else:
            cmd = [
                str(py),
                str(scripts_dir / "phase2_e2_sensitivity_report.py"),
                "--in-jsonl",
                str(merged_jsonl),
                "--out-md",
                str(sensitivity_md),
                "--out-csv",
                str(sensitivity_csv),
                "--out-json",
                str(sensitivity_json),
                "--plausibility",
                str(args.plausibility),
            ]
            expected = [sensitivity_md, sensitivity_csv, sensitivity_json]
            res = _invoke_step(
                name="sensitivity",
                cmd=cmd,
                cwd=repo_root,
                dry_run=bool(args.dry_run),
                strict=bool(args.strict),
                expected_outputs=expected,
                canonicalize_outputs=True,
                outdir=outdir,
            )
            step_results["sensitivity"] = res
            if res["status"] == "ok":
                produced_files.extend(expected)
    else:
        step_results["sensitivity"] = _step_result("skipped", reason="step disabled", outputs=[], outdir=outdir)

    # paper assets
    if "paper_assets" in selected_steps:
        if str(args.paper_assets) == "none":
            step_results["paper_assets"] = _step_result(
                "skipped",
                reason="paper assets disabled (--paper-assets none)",
                outputs=[],
                outdir=outdir,
            )
        elif not merged_available and not args.dry_run:
            reason = "merged.jsonl not available"
            if args.strict:
                raise SystemExit(f"Step 'paper_assets' failed: {reason}")
            step_results["paper_assets"] = _step_result("skipped", reason=reason, outputs=[], outdir=outdir)
        else:
            cmd = [
                str(py),
                str(scripts_dir / "phase2_e2_make_paper_assets.py"),
                "--jsonl",
                str(merged_jsonl),
                "--mode",
                "all",
                "--outdir",
                str(paper_assets_root),
                "--plausibility",
                str(args.plausibility),
                "--robustness",
                "any",
                "--overwrite",
            ]
            if str(args.paper_assets) == "snippets":
                cmd.extend(["--emit-snippets", "--snippets-format", "both"])
            res = _invoke_step(
                name="paper_assets",
                cmd=cmd,
                cwd=repo_root,
                dry_run=bool(args.dry_run),
                strict=bool(args.strict),
                expected_outputs=[paper_assets_manifest, paper_assets_drift_readme, paper_assets_knobs_readme],
                canonicalize_outputs=False,
                outdir=outdir,
            )
            if res["status"] == "ok":
                paper_files = sorted(p for p in paper_assets_root.rglob("*") if p.is_file())
                _canonicalize_outputs(paper_files, outdir=outdir)
                _refresh_paper_assets_manifest(paper_assets_manifest)
                paper_files = sorted(p for p in paper_assets_root.rglob("*") if p.is_file())
                step_results["paper_assets"] = _step_result("ok", outputs=paper_files, outdir=outdir)
                produced_files.extend(paper_files)
            else:
                step_results["paper_assets"] = res
    else:
        step_results["paper_assets"] = _step_result("skipped", reason="step disabled", outputs=[], outdir=outdir)

    # robustness compare
    if "robustness_compare" in selected_steps:
        if not robustness_a or not robustness_b:
            step_results["robustness_compare"] = _step_result(
                "skipped",
                reason="robustness inputs not provided",
                outputs=[],
                outdir=outdir,
            )
        else:
            cmd = [
                str(py),
                str(scripts_dir / "phase2_e2_robustness_compare.py"),
                "--jsonl-a",
                str(robustness_a[0]),
                "--jsonl-b",
                str(robustness_b[0]),
                "--out-tsv",
                str(compare_tsv),
                "--preset",
                "core",
            ]
            expected = [compare_tsv]
            res = _invoke_step(
                name="robustness_compare",
                cmd=cmd,
                cwd=repo_root,
                dry_run=bool(args.dry_run),
                strict=bool(args.strict),
                expected_outputs=expected,
                canonicalize_outputs=False,
                outdir=outdir,
            )
            step_results["robustness_compare"] = res
            if res["status"] == "ok":
                produced_files.extend(expected)
    else:
        step_results["robustness_compare"] = _step_result("skipped", reason="step disabled", outputs=[], outdir=outdir)

    # robustness aggregate
    if "robustness_aggregate" in selected_steps:
        agg_inputs = sorted(set(robustness_a + robustness_b))
        if len(agg_inputs) < 2:
            step_results["robustness_aggregate"] = _step_result(
                "skipped",
                reason="need at least two robustness JSONL inputs",
                outputs=[],
                outdir=outdir,
            )
        else:
            cmd: List[str] = [
                str(py),
                str(scripts_dir / "phase2_e2_robustness_aggregate.py"),
                "--outdir",
                str(outdir),
            ]
            for path in agg_inputs:
                cmd.extend(["--jsonl", str(path)])
            expected = [aggregate_csv, aggregate_md, aggregate_meta]
            res = _invoke_step(
                name="robustness_aggregate",
                cmd=cmd,
                cwd=repo_root,
                dry_run=bool(args.dry_run),
                strict=bool(args.strict),
                expected_outputs=expected,
                canonicalize_outputs=True,
                outdir=outdir,
            )
            step_results["robustness_aggregate"] = res
            if res["status"] == "ok":
                produced_files.extend(expected)
    else:
        step_results["robustness_aggregate"] = _step_result("skipped", reason="step disabled", outputs=[], outdir=outdir)

    # manifest
    if "manifest" in selected_steps:
        if bool(args.dry_run):
            step_results["manifest"] = _step_result("ok", reason="dry-run", outputs=[], outdir=outdir)
        else:
            artifact_paths = sorted(set(path.resolve() for path in produced_files if path.is_file()))
            input_paths = sorted(
                set(
                    input_jsonls
                    + robustness_a
                    + robustness_b
                    + [
                        scripts_dir / "phase2_e2_bundle.py",
                        scripts_dir / "phase2_e2_merge_jsonl.py",
                        scripts_dir / "phase2_e2_pareto_report.py",
                        scripts_dir / "phase2_e2_diagnostics_report.py",
                        scripts_dir / "phase2_e2_cmb_tension_report.py",
                        scripts_dir / "phase2_e2_sensitivity_report.py",
                        scripts_dir / "phase2_e2_make_paper_assets.py",
                        scripts_dir / "phase2_e2_robustness_compare.py",
                        scripts_dir / "phase2_e2_robustness_aggregate.py",
                        scripts_dir / "phase2_e2_make_manifest.py",
                    ]
                )
            )
            input_paths = [p for p in input_paths if p.is_file()]

            normalized_argv = _normalize_invocation_argv(
                list(argv if argv is not None else sys.argv[1:]),
                outdir=outdir,
            )
            cmd: List[str] = [
                str(py),
                str(scripts_dir / "phase2_e2_make_manifest.py"),
                "--outdir",
                str(outdir),
                "--repo-root",
                str(repo_root),
                "--manifest-name",
                str(manifest_json.name),
                "--deterministic",
                "--run-argv-json",
                json.dumps(normalized_argv, sort_keys=False),
            ]
            for path in artifact_paths:
                cmd.extend(["--artifact", _relative_or_abs(path, base=outdir)])
            for path in input_paths:
                cmd.extend(["--input", str(path)])

            res = _invoke_step(
                name="manifest",
                cmd=cmd,
                cwd=repo_root,
                dry_run=False,
                strict=bool(args.strict),
                expected_outputs=[manifest_json],
                canonicalize_outputs=True,
                outdir=outdir,
            )
            step_results["manifest"] = res
            if res["status"] == "ok":
                produced_files.append(manifest_json)
    else:
        step_results["manifest"] = _step_result("skipped", reason="step disabled", outputs=[], outdir=outdir)

    # meta (always)
    all_output_entries: Dict[str, str] = {}
    for step_name in STEP_ORDER:
        step_payload = step_results.get(step_name)
        if not isinstance(step_payload, Mapping):
            continue
        for item in step_payload.get("outputs") or []:
            path_str = str(item.get("path", "")).strip()
            sha = str(item.get("sha256", "")).strip()
            if path_str and sha:
                all_output_entries[path_str] = sha

    meta_payload: Dict[str, Any] = {
        "schema": "phase2_e2_bundle_v1",
        "git_sha": _git_sha(repo_root),
        "invocation": {
            "argv": _normalize_invocation_argv(list(argv if argv is not None else sys.argv[1:]), outdir=outdir),
            "python_executable": str(py),
            "python_version": platform.python_version(),
        },
        "inputs": [_file_entry(path, rel_base=repo_root) for path in input_jsonls],
        "steps": {name: step_results.get(name, _step_result("skipped", reason="not-run", outputs=[], outdir=outdir)) for name in STEP_ORDER},
        "outputs": {key: all_output_entries[key] for key in sorted(all_output_entries.keys())},
    }
    if bool(args.with_timestamps):
        meta_payload["generated_utc"] = datetime.now(timezone.utc).isoformat()

    if not args.dry_run:
        step_results["meta"] = _step_result("ok", outputs=[], outdir=outdir)
        meta_payload["steps"]["meta"] = step_results["meta"]
        _write_json(bundle_meta, meta_payload)
    else:
        step_results["meta"] = _step_result("ok", reason="dry-run", outputs=[], outdir=outdir)

    # lineage (always attempted when manifest exists and this is not dry-run)
    if not args.dry_run and manifest_json.is_file():
        lineage_cmd: List[str] = [
            str(py),
            str(scripts_dir / "phase2_lineage_dag.py"),
            "--bundle-dir",
            str(outdir),
            "--out",
            str(lineage_json),
            "--format",
            "json",
        ]
        rc, stdout, stderr = _run_cmd(lineage_cmd, cwd=repo_root, dry_run=False)
        if rc != 0:
            detail_text = (stderr.strip() or stdout.strip() or "(no output)")
            raise SystemExit(f"Step 'lineage' failed: command failed (rc={rc})\n{detail_text}")
        if lineage_json.is_file():
            produced_files.append(lineage_json)

    summary = {
        "ok": True,
        "outdir": str(outdir),
        "steps": selected_steps,
        "inputs": [str(p) for p in input_jsonls],
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

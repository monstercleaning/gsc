#!/usr/bin/env python3
"""One-button reproducible Phase-2 E2 workflow orchestration (stdlib-only).

Pipeline:
1) base scan
2) base reports
3) optional refine-plan emission + refine scan
4) canonical combined JSONL (dedupe by params_hash, deterministic order)
5) final reports on combined JSONL
6) manifest with artifact/input checksums
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _finite_float(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except Exception:
        return None
    if out != out or out in (float("inf"), float("-inf")):
        return None
    return out


def _is_flag_present(tokens: Sequence[str], names: Sequence[str]) -> bool:
    name_set = set(str(name) for name in names)
    for token in tokens:
        raw = str(token)
        if raw in name_set:
            return True
        if "=" in raw:
            key = raw.split("=", 1)[0]
            if key in name_set:
                return True
    return False


def _parse_extra_args(raw_list: Sequence[str]) -> List[str]:
    out: List[str] = []
    for raw in raw_list:
        chunk = str(raw).strip()
        if not chunk:
            continue
        out.extend(shlex.split(chunk))
    return out


def _validate_forwarded_scan_args(tokens: Sequence[str], *, mode: str) -> None:
    forbidden_common = {"--out-dir", "--outdir"}
    forbidden_base = forbidden_common | {"--plan", "--resume"}
    forbidden_refine = forbidden_common | {"--plan", "--resume"}
    forbidden = forbidden_base if mode == "base" else forbidden_refine
    for token in tokens:
        key = str(token)
        if "=" in key:
            key = key.split("=", 1)[0]
        if key in forbidden:
            raise SystemExit(
                f"{mode} scan args must not include {key}; it is controlled by phase2_e2_reproduce.py"
            )


def _run_cmd(cmd: Sequence[str], *, cwd: Path, dry_run: bool) -> None:
    pretty = shlex.join([str(x) for x in cmd])
    if dry_run:
        print(f"[dry-run] would run: {pretty}")
        return
    proc = subprocess.run(
        [str(x) for x in cmd],
        cwd=str(cwd),
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        stdout = (proc.stdout or "").strip()
        detail = stderr or stdout or "(no output)"
        raise SystemExit(f"Command failed ({proc.returncode}): {pretty}\n{detail}")
    if (proc.stdout or "").strip():
        print((proc.stdout or "").strip())


def _copy_file(src: Path, dst: Path, *, dry_run: bool) -> None:
    if dry_run:
        print(f"[dry-run] would copy: {src} -> {dst}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _stage_scan_outputs(stage_dir: Path) -> Tuple[Path, Path, Path]:
    points_jsonl = stage_dir / "e2_scan_points.jsonl"
    points_csv = stage_dir / "e2_scan_points.csv"
    summary_json = stage_dir / "e2_scan_summary.json"
    if not points_jsonl.is_file():
        raise SystemExit(f"Missing scan output: {points_jsonl}")
    if not points_csv.is_file():
        raise SystemExit(f"Missing scan output: {points_csv}")
    if not summary_json.is_file():
        raise SystemExit(f"Missing scan output: {summary_json}")
    return points_jsonl, points_csv, summary_json


def _read_jsonl_objects(path: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            try:
                payload = json.loads(text)
            except Exception:
                continue
            if isinstance(payload, Mapping):
                out.append({str(k): payload[k] for k in payload.keys()})
    return out


def _score_record_for_dedupe(obj: Mapping[str, Any], *, source_rank: int, source_line: int) -> Tuple[Any, ...]:
    status_ok = 0 if str(obj.get("status", "ok")).strip().lower() == "ok" else 1
    chi2_total = _finite_float(obj.get("chi2_total"))
    if chi2_total is None:
        chi2_total = _finite_float(obj.get("chi2"))
    if chi2_total is None:
        chi2_total = float("inf")
    canonical = _canonical_json_bytes(obj).decode("utf-8")
    return (int(status_ok), float(chi2_total), int(source_rank), int(source_line), canonical)


def _canonical_params_hash(obj: Mapping[str, Any]) -> Tuple[str, bool]:
    raw = str(obj.get("params_hash", "")).strip()
    if raw:
        return raw, False
    fallback = hashlib.sha256(_canonical_json_bytes(obj)).hexdigest()
    return fallback, True


def _combine_jsonl(
    *,
    base_jsonl: Path,
    refine_jsonl: Optional[Path],
    out_jsonl: Path,
    dry_run: bool,
) -> Dict[str, Any]:
    sources: List[Tuple[int, Path]] = [(0, base_jsonl)]
    if refine_jsonl is not None:
        sources.append((1, refine_jsonl))

    selected: Dict[str, Tuple[Dict[str, Any], Tuple[Any, ...]]] = {}
    n_total = 0
    n_fallback_hash = 0
    for source_rank, path in sources:
        objects = _read_jsonl_objects(path)
        for line_idx, obj in enumerate(objects, start=1):
            n_total += 1
            key, used_fallback = _canonical_params_hash(obj)
            candidate = dict(obj)
            if used_fallback:
                n_fallback_hash += 1
                candidate["params_hash"] = str(key)
                candidate["params_hash_fallback"] = True
            score = _score_record_for_dedupe(
                candidate,
                source_rank=int(source_rank),
                source_line=int(line_idx),
            )
            existing = selected.get(key)
            if existing is None or score < existing[1]:
                selected[key] = (candidate, score)

    ordered_keys = sorted(selected.keys())
    if dry_run:
        print(
            f"[dry-run] would write combined JSONL: {out_jsonl} "
            f"(rows={len(ordered_keys)}, source_rows={n_total})"
        )
        return {
            "rows_total_source": int(n_total),
            "rows_unique": int(len(ordered_keys)),
            "rows_fallback_hash": int(n_fallback_hash),
            "combined_sha256": None,
        }

    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with out_jsonl.open("w", encoding="utf-8") as fh:
        for key in ordered_keys:
            payload = selected[key][0]
            fh.write(
                json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
            )
    return {
        "rows_total_source": int(n_total),
        "rows_unique": int(len(ordered_keys)),
        "rows_fallback_hash": int(n_fallback_hash),
        "combined_sha256": _sha256_file(out_jsonl),
    }


def _run_reports(
    *,
    repo_root: Path,
    jsonl_path: Path,
    outdir: Path,
    reports_prefix: str,
    stage_name: str,
    dry_run: bool,
    emit_refine_plan: Optional[Path],
    refine_strategy: str,
    refine_target_metric: str,
) -> List[Path]:
    scripts_dir = repo_root / "scripts"
    py = Path(sys.executable).resolve()
    produced: List[Path] = []
    stage_tag = f"{reports_prefix}{stage_name}"

    pareto_summary = outdir / f"{stage_tag}_pareto_summary.json"
    pareto_frontier = outdir / f"{stage_tag}_pareto_frontier.csv"
    pareto_top = outdir / f"{stage_tag}_pareto_top_positive.csv"
    pareto_md = outdir / f"{stage_tag}_pareto_report.md"
    cmd = [
        str(py),
        str(scripts_dir / "phase2_e2_pareto_report.py"),
        "--jsonl",
        str(jsonl_path),
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
    ]
    if emit_refine_plan is not None:
        cmd.extend(["--emit-refine-plan", str(emit_refine_plan)])
        cmd.extend(["--refine-strategy", str(refine_strategy)])
        if str(refine_target_metric).strip():
            cmd.extend(["--refine-target-metric", str(refine_target_metric).strip()])
    _run_cmd(cmd, cwd=repo_root, dry_run=dry_run)
    produced.extend([pareto_summary, pareto_frontier, pareto_top, pareto_md])
    if emit_refine_plan is not None:
        produced.append(emit_refine_plan)

    diagnostics_tmp = outdir / f".tmp_{stage_tag}_diagnostics"
    cmd = [
        str(py),
        str(scripts_dir / "phase2_e2_diagnostics_report.py"),
        "--jsonl",
        str(jsonl_path),
        "--outdir",
        str(diagnostics_tmp),
    ]
    _run_cmd(cmd, cwd=repo_root, dry_run=dry_run)
    diagnostics_map = {
        diagnostics_tmp / "e2_diagnostics_summary.md": outdir / f"{stage_tag}_diagnostics_summary.md",
        diagnostics_tmp / "e2_best_points.csv": outdir / f"{stage_tag}_best_points.csv",
        diagnostics_tmp / "e2_tradeoff_envelope.csv": outdir / f"{stage_tag}_tradeoff_envelope.csv",
        diagnostics_tmp / "e2_param_correlations.csv": outdir / f"{stage_tag}_param_correlations.csv",
    }
    for src, dst in diagnostics_map.items():
        _copy_file(src, dst, dry_run=dry_run)
        produced.append(dst)

    tension_tmp = outdir / f".tmp_{stage_tag}_tension"
    cmd = [
        str(py),
        str(scripts_dir / "phase2_e2_cmb_tension_report.py"),
        "--in-jsonl",
        str(jsonl_path),
        "--outdir",
        str(tension_tmp),
    ]
    _run_cmd(cmd, cwd=repo_root, dry_run=dry_run)
    tension_map = {
        tension_tmp / "cmb_tension_summary.json": outdir / f"{stage_tag}_cmb_tension_summary.json",
        tension_tmp / "cmb_tension_summary.md": outdir / f"{stage_tag}_cmb_tension_summary.md",
        tension_tmp / "cmb_tension_topk.csv": outdir / f"{stage_tag}_cmb_tension_topk.csv",
    }
    for src, dst in tension_map.items():
        _copy_file(src, dst, dry_run=dry_run)
        produced.append(dst)

    sensitivity_md = outdir / f"{stage_tag}_sensitivity.md"
    sensitivity_csv = outdir / f"{stage_tag}_sensitivity.csv"
    sensitivity_json = outdir / f"{stage_tag}_sensitivity.json"
    cmd = [
        str(py),
        str(scripts_dir / "phase2_e2_sensitivity_report.py"),
        "--in-jsonl",
        str(jsonl_path),
        "--out-md",
        str(sensitivity_md),
        "--out-csv",
        str(sensitivity_csv),
        "--out-json",
        str(sensitivity_json),
    ]
    _run_cmd(cmd, cwd=repo_root, dry_run=dry_run)
    produced.extend([sensitivity_md, sensitivity_csv, sensitivity_json])

    if not dry_run:
        shutil.rmtree(diagnostics_tmp, ignore_errors=True)
        shutil.rmtree(tension_tmp, ignore_errors=True)
    return produced


def _collect_input_files(repo_root: Path) -> List[Path]:
    candidates = [
        repo_root / "scripts" / "phase2_e2_reproduce.py",
        repo_root / "scripts" / "phase2_e2_make_manifest.py",
        repo_root / "scripts" / "phase2_e2_scan.py",
        repo_root / "scripts" / "phase2_e2_pareto_report.py",
        repo_root / "scripts" / "phase2_e2_diagnostics_report.py",
        repo_root / "scripts" / "phase2_e2_cmb_tension_report.py",
        repo_root / "scripts" / "phase2_e2_sensitivity_report.py",
        repo_root / "gsc" / "search_sampling.py",
        repo_root / "gsc" / "measurement_model.py",
        repo_root / "gsc" / "numerics_adaptive_quad.py",
        repo_root / "gsc" / "early_time" / "cmb_distance_priors.py",
        repo_root / "gsc" / "early_time" / "cmb_shift_params.py",
        repo_root / "gsc" / "early_time" / "cmb_priors_driver.py",
        repo_root / "gsc" / "early_time" / "cmb_microphysics_knobs.py",
        repo_root / "gsc" / "early_time" / "numerics_invariants.py",
    ]
    out: List[Path] = []
    seen: set[Path] = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen or not resolved.is_file():
            continue
        seen.add(resolved)
        out.append(resolved)
    return out


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="phase2_e2_reproduce",
        description="One-button reproducible Phase-2 E2 workflow orchestration.",
    )
    ap.add_argument("--outdir", type=Path, required=True, help="Output directory root.")
    ap.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repo root (default: v11.0.0).",
    )
    ap.add_argument("--base-jsonl", type=str, default="e2_base.jsonl")
    ap.add_argument("--combined-jsonl", type=str, default="e2_combined.jsonl")
    ap.add_argument("--reports-prefix", type=str, default="e2_")
    ap.add_argument("--emit-refine-plan", action="store_true")
    ap.add_argument("--refine-plan", type=str, default="e2_refine_plan.json")
    ap.add_argument("--refine-jsonl", type=str, default="e2_refine.jsonl")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--keep-intermediate", action="store_true")
    ap.add_argument("--toy", action="store_true")
    ap.add_argument("--jobs", type=int, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--scan-args", action="append", default=[], help="Extra base scan args (repeatable; parsed via shlex).")
    ap.add_argument("--refine-scan-args", action="append", default=[], help="Extra refine scan args (repeatable; parsed via shlex).")
    ap.add_argument("--refine-strategy", choices=["grid", "sensitivity"], default="grid")
    ap.add_argument("--refine-target-metric", type=str, default="")
    args = ap.parse_args(argv)

    if args.jobs is not None and int(args.jobs) <= 0:
        raise SystemExit("--jobs must be > 0 when provided")

    repo_root = args.repo_root.expanduser().resolve()
    scripts_dir = repo_root / "scripts"
    scan_script = scripts_dir / "phase2_e2_scan.py"
    for required in (
        scan_script,
        scripts_dir / "phase2_e2_pareto_report.py",
        scripts_dir / "phase2_e2_diagnostics_report.py",
        scripts_dir / "phase2_e2_cmb_tension_report.py",
        scripts_dir / "phase2_e2_sensitivity_report.py",
        scripts_dir / "phase2_e2_make_manifest.py",
    ):
        if not required.is_file():
            raise SystemExit(f"Missing required script: {required}")

    outdir = args.outdir.expanduser().resolve()
    if not args.dry_run:
        outdir.mkdir(parents=True, exist_ok=True)

    base_scan_args = _parse_extra_args(args.scan_args)
    refine_scan_args_raw = _parse_extra_args(args.refine_scan_args)
    _validate_forwarded_scan_args(base_scan_args, mode="base")
    if refine_scan_args_raw:
        _validate_forwarded_scan_args(refine_scan_args_raw, mode="refine")

    def _compose_scan_tokens(raw_tokens: Sequence[str], *, include_toy: bool) -> List[str]:
        tokens = [str(x) for x in raw_tokens]
        if include_toy and not _is_flag_present(tokens, ["--toy"]):
            tokens = ["--toy"] + tokens
        if args.jobs is not None and not _is_flag_present(tokens, ["--jobs"]):
            tokens.extend(["--jobs", str(int(args.jobs))])
        if args.seed is not None and not _is_flag_present(tokens, ["--seed", "--sampler-seed"]):
            tokens.extend(["--seed", str(int(args.seed))])
        return tokens

    base_stage_dir = outdir / "_stage_base_scan"
    refine_stage_dir = outdir / "_stage_refine_scan"
    base_tokens = _compose_scan_tokens(base_scan_args, include_toy=bool(args.toy))
    if args.emit_refine_plan and refine_scan_args_raw:
        refine_tokens = _compose_scan_tokens(refine_scan_args_raw, include_toy=bool(args.toy))
    else:
        refine_tokens = list(base_tokens)

    base_cmd = [str(Path(sys.executable).resolve()), str(scan_script), "--out-dir", str(base_stage_dir)]
    base_cmd.extend(base_tokens)
    _run_cmd(base_cmd, cwd=repo_root, dry_run=bool(args.dry_run))

    base_jsonl = outdir / str(args.base_jsonl)
    combined_jsonl = outdir / str(args.combined_jsonl)
    refine_plan_path = outdir / str(args.refine_plan)
    refine_jsonl = outdir / str(args.refine_jsonl)

    base_scan_jsonl = base_stage_dir / "e2_scan_points.jsonl"
    base_scan_csv = base_stage_dir / "e2_scan_points.csv"
    base_scan_summary = base_stage_dir / "e2_scan_summary.json"
    if not args.dry_run:
        base_scan_jsonl, base_scan_csv, base_scan_summary = _stage_scan_outputs(base_stage_dir)
        _copy_file(base_scan_jsonl, base_jsonl, dry_run=False)
        _copy_file(base_scan_csv, outdir / f"{Path(args.base_jsonl).stem}_points.csv", dry_run=False)
        _copy_file(base_scan_summary, outdir / f"{Path(args.base_jsonl).stem}_summary.json", dry_run=False)
    else:
        _copy_file(base_scan_jsonl, base_jsonl, dry_run=True)

    produced_artifacts: List[Path] = [base_jsonl]
    produced_artifacts.extend(
        _run_reports(
            repo_root=repo_root,
            jsonl_path=base_jsonl,
            outdir=outdir,
            reports_prefix=str(args.reports_prefix),
            stage_name="base",
            dry_run=bool(args.dry_run),
            emit_refine_plan=refine_plan_path if bool(args.emit_refine_plan) else None,
            refine_strategy=str(args.refine_strategy),
            refine_target_metric=str(args.refine_target_metric),
        )
    )

    refine_jsonl_for_combine: Optional[Path] = None
    if bool(args.emit_refine_plan):
        if not args.dry_run and not refine_plan_path.is_file():
            raise SystemExit(f"Missing emitted refine plan: {refine_plan_path}")

        refine_cmd = [
            str(Path(sys.executable).resolve()),
            str(scan_script),
            "--out-dir",
            str(refine_stage_dir),
            "--plan",
            str(refine_plan_path),
            "--resume",
        ]
        refine_cmd.extend(refine_tokens)
        _run_cmd(refine_cmd, cwd=repo_root, dry_run=bool(args.dry_run))

        refine_scan_jsonl = refine_stage_dir / "e2_scan_points.jsonl"
        refine_scan_csv = refine_stage_dir / "e2_scan_points.csv"
        refine_scan_summary = refine_stage_dir / "e2_scan_summary.json"
        if not args.dry_run:
            refine_scan_jsonl, refine_scan_csv, refine_scan_summary = _stage_scan_outputs(refine_stage_dir)
            _copy_file(refine_scan_jsonl, refine_jsonl, dry_run=False)
            _copy_file(refine_scan_csv, outdir / f"{Path(args.refine_jsonl).stem}_points.csv", dry_run=False)
            _copy_file(refine_scan_summary, outdir / f"{Path(args.refine_jsonl).stem}_summary.json", dry_run=False)
        else:
            _copy_file(refine_scan_jsonl, refine_jsonl, dry_run=True)
        produced_artifacts.append(refine_jsonl)
        refine_jsonl_for_combine = refine_jsonl

    combine_stats = _combine_jsonl(
        base_jsonl=base_jsonl,
        refine_jsonl=refine_jsonl_for_combine,
        out_jsonl=combined_jsonl,
        dry_run=bool(args.dry_run),
    )
    if not args.dry_run:
        produced_artifacts.append(combined_jsonl)

    produced_artifacts.extend(
        _run_reports(
            repo_root=repo_root,
            jsonl_path=combined_jsonl,
            outdir=outdir,
            reports_prefix=str(args.reports_prefix),
            stage_name="combined",
            dry_run=bool(args.dry_run),
            emit_refine_plan=None,
            refine_strategy=str(args.refine_strategy),
            refine_target_metric=str(args.refine_target_metric),
        )
    )

    if not args.dry_run:
        from phase2_e2_make_manifest import make_manifest

        manifest_inputs = _collect_input_files(repo_root)
        make_manifest(
            outdir=outdir,
            repo_root=repo_root,
            artifact_paths=sorted(set(path.resolve() for path in produced_artifacts if path.is_file())),
            input_paths=manifest_inputs,
            run_argv=[str(x) for x in (argv if argv is not None else sys.argv[1:])],
            dry_run=False,
            manifest_name="manifest.json",
        )
        produced_artifacts.append(outdir / "manifest.json")

    if not bool(args.keep_intermediate):
        if not args.dry_run:
            shutil.rmtree(base_stage_dir, ignore_errors=True)
            shutil.rmtree(refine_stage_dir, ignore_errors=True)
        else:
            print(f"[dry-run] would remove intermediate dir: {base_stage_dir}")
            if bool(args.emit_refine_plan):
                print(f"[dry-run] would remove intermediate dir: {refine_stage_dir}")

    print(
        json.dumps(
            {
                "ok": True,
                "outdir": str(outdir),
                "emit_refine_plan": bool(args.emit_refine_plan),
                "dry_run": bool(args.dry_run),
                "combine_stats": combine_stats,
                "artifacts": sorted(str(path) for path in set(produced_artifacts)),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

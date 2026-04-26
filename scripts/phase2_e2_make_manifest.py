#!/usr/bin/env python3
"""Create deterministic manifest metadata for Phase-2 E2 reproduction outputs.

This tool is stdlib-only and intentionally lightweight. It records SHA256 hashes
for selected artifacts and input files to make result bundles reproducible.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _as_relative(path: Path, *, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except Exception:
        return str(path.resolve())


def _git_info(repo_root: Path) -> Dict[str, Any]:
    git_sha = "UNKNOWN"
    dirty: Optional[bool] = None
    try:
        sha_proc = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=True,
            text=True,
            capture_output=True,
        )
        git_sha = str((sha_proc.stdout or "").strip()) or "UNKNOWN"
        status_proc = subprocess.run(
            ["git", "-C", str(repo_root), "status", "--porcelain"],
            check=True,
            text=True,
            capture_output=True,
        )
        dirty = bool((status_proc.stdout or "").strip())
    except Exception:
        git_sha = "UNKNOWN"
        dirty = None
    return {"sha": git_sha, "dirty": dirty}


def _entry(path: Path, *, rel_base: Path) -> Dict[str, Any]:
    return {
        "path": _as_relative(path, base=rel_base),
        "sha256": _sha256_file(path),
        "bytes": int(path.stat().st_size),
    }


def _resolve_list(
    raw_paths: Sequence[Path],
    *,
    outdir: Path,
) -> List[Path]:
    resolved: List[Path] = []
    seen: set[Path] = set()
    for raw in raw_paths:
        candidate = raw.expanduser()
        if not candidate.is_absolute():
            candidate = (outdir / candidate).resolve()
        else:
            candidate = candidate.resolve()
        if candidate in seen:
            continue
        seen.add(candidate)
        resolved.append(candidate)
    return resolved


def _autodiscover_artifacts(outdir: Path, *, manifest_name: str) -> List[Path]:
    found: List[Path] = []
    for path in sorted(outdir.rglob("*")):
        if not path.is_file():
            continue
        if path.name == manifest_name:
            continue
        found.append(path.resolve())
    return found


def make_manifest(
    *,
    outdir: Path,
    repo_root: Path,
    artifact_paths: Sequence[Path],
    input_paths: Sequence[Path],
    run_argv: Sequence[str],
    dry_run: bool,
    manifest_name: str = "manifest.json",
    include_generated_utc: bool = True,
    run_outdir_value: Optional[str] = None,
) -> Dict[str, Any]:
    outdir_resolved = outdir.expanduser().resolve()
    repo_root_resolved = repo_root.expanduser().resolve()
    outdir_resolved.mkdir(parents=True, exist_ok=True)

    artifacts = _resolve_list(artifact_paths, outdir=outdir_resolved)
    inputs = _resolve_list(input_paths, outdir=outdir_resolved)

    artifact_entries: List[Dict[str, Any]] = []
    for path in artifacts:
        if not path.is_file():
            raise SystemExit(f"Artifact path does not exist: {path}")
        artifact_entries.append(_entry(path, rel_base=outdir_resolved))
    artifact_entries = sorted(artifact_entries, key=lambda e: str(e["path"]))

    input_entries: List[Dict[str, Any]] = []
    for path in inputs:
        if not path.is_file():
            raise SystemExit(f"Input path does not exist: {path}")
        input_entries.append(_entry(path, rel_base=repo_root_resolved))
    input_entries = sorted(input_entries, key=lambda e: str(e["path"]))

    payload: Dict[str, Any] = {
        "schema": "phase2_e2_manifest_v1",
        "git": _git_info(repo_root_resolved),
        "python": {
            "executable": str(Path(sys.executable).resolve()),
            "version": platform.python_version(),
        },
        "run": {
            "argv": [str(x) for x in run_argv],
            "outdir": str(run_outdir_value) if run_outdir_value is not None else str(outdir_resolved),
            "dry_run": bool(dry_run),
        },
        "artifacts": artifact_entries,
        "inputs": input_entries,
    }
    if bool(include_generated_utc):
        payload["generated_utc"] = _now_utc()
    manifest_path = outdir_resolved / manifest_name
    manifest_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="phase2_e2_make_manifest",
        description="Create deterministic phase2 E2 artifact/input manifest with SHA256 checksums.",
    )
    ap.add_argument("--outdir", type=Path, required=True, help="Output directory containing artifacts.")
    ap.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root for input path relativization (default: v11.0.0).",
    )
    ap.add_argument(
        "--artifact",
        action="append",
        default=[],
        type=Path,
        help="Artifact file path (repeatable). Relative paths resolve under --outdir.",
    )
    ap.add_argument(
        "--input",
        action="append",
        default=[],
        type=Path,
        help="Input file path (repeatable). Relative paths resolve under --outdir unless absolute.",
    )
    ap.add_argument(
        "--manifest-name",
        type=str,
        default="manifest.json",
        help="Manifest filename written inside --outdir (default: manifest.json).",
    )
    ap.add_argument(
        "--run-argv-json",
        type=str,
        default="",
        help="Optional JSON list overriding run.argv payload.",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Record dry-run=true in manifest metadata.",
    )
    ap.add_argument(
        "--deterministic",
        action="store_true",
        help="Omit generated_utc and normalize run.outdir to '.' for stable bundle hashes.",
    )
    args = ap.parse_args(argv)

    outdir = args.outdir.expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    manifest_name = str(args.manifest_name).strip() or "manifest.json"
    if "/" in manifest_name or "\\" in manifest_name:
        raise SystemExit("--manifest-name must be a plain filename")

    run_argv: List[str]
    if str(args.run_argv_json).strip():
        try:
            parsed = json.loads(str(args.run_argv_json))
        except Exception as exc:
            raise SystemExit(f"Invalid --run-argv-json: {exc}") from exc
        if not isinstance(parsed, list):
            raise SystemExit("--run-argv-json must be a JSON list")
        run_argv = [str(x) for x in parsed]
    else:
        run_argv = [str(x) for x in (argv if argv is not None else sys.argv[1:])]

    artifact_paths: List[Path] = list(args.artifact)
    if not artifact_paths:
        artifact_paths = _autodiscover_artifacts(outdir, manifest_name=manifest_name)

    make_manifest(
        outdir=outdir,
        repo_root=args.repo_root,
        artifact_paths=artifact_paths,
        input_paths=list(args.input),
        run_argv=run_argv,
        dry_run=bool(args.dry_run),
        manifest_name=manifest_name,
        include_generated_utc=(not bool(args.deterministic)),
        run_outdir_value="." if bool(args.deterministic) else None,
    )
    print(f"[ok] wrote {outdir / manifest_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

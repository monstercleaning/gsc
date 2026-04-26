#!/usr/bin/env python3
"""Safe cleanup helper for ignored worktree bloat (stdlib-only)."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Sequence, Tuple


SCHEMA_ID = "gsc_clean_ignored_bloat_v1"


class RefuseError(RuntimeError):
    """Refusal/safety stop (exit code 2)."""


class ToolError(RuntimeError):
    """I/O or subprocess failure (exit code 1)."""


@dataclass(frozen=True)
class Candidate:
    path: str
    kind: str  # file|dir|other
    size_bytes: int


def _norm_rel(path: str) -> str:
    raw = str(path).strip().replace("\\", "/")
    if raw.startswith("./"):
        raw = raw[2:]
    while raw.endswith("/"):
        raw = raw[:-1]
    pure = PurePosixPath(raw)
    if pure.is_absolute() or ".." in pure.parts:
        raise RefuseError(f"unsafe path candidate: {path}")
    norm = str(pure)
    if norm in {"", "."}:
        raise RefuseError(f"invalid path candidate: {path}")
    return norm


def _run_git(root: Path, args: Sequence[str], *, allow_rc: Optional[Tuple[int, ...]] = None) -> subprocess.CompletedProcess:
    cmd = ["git", "-C", str(root)] + [str(x) for x in args]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    allowed = tuple(allow_rc or (0,))
    if proc.returncode not in allowed:
        msg = (proc.stderr or proc.stdout or "").strip()
        raise ToolError(f"git command failed ({' '.join(args)}): {msg or f'rc={proc.returncode}'}")
    return proc


def _resolve_git_root(root: Path) -> Path:
    proc = _run_git(root, ["rev-parse", "--show-toplevel"], allow_rc=(0, 128))
    if proc.returncode != 0:
        raise RefuseError(f"not a git repository: {root}")
    out = (proc.stdout or "").strip()
    if not out:
        raise RefuseError(f"not a git repository: {root}")
    return Path(out).resolve()


def _git_clean_candidates(root: Path) -> List[str]:
    # -d is required so ignored directories are listed too.
    proc = _run_git(root, ["clean", "-ndX", "-d"])
    rows: List[str] = []
    prefix = "Would remove "
    for line in (proc.stdout or "").splitlines():
        text = line.strip()
        if not text or not text.startswith(prefix):
            continue
        candidate = text[len(prefix) :].strip()
        if not candidate:
            continue
        rows.append(_norm_rel(candidate))
    return sorted(set(rows))


def _is_ignored(root: Path, relpath: str) -> bool:
    for probe in (relpath, relpath + "/"):
        proc = _run_git(root, ["check-ignore", "-q", "--", probe], allow_rc=(0, 1))
        if proc.returncode == 0:
            return True
    return False


def _has_tracked_descendants(root: Path, relpath: str) -> bool:
    proc = _run_git(root, ["ls-files", "-z", "--", relpath])
    return bool(proc.stdout)


def _path_kind(path: Path) -> str:
    if path.is_file():
        return "file"
    if path.is_dir():
        return "dir"
    return "other"


def _dir_size_bytes(path: Path) -> Tuple[int, int, int]:
    total = 0
    symlink_count = 0
    error_count = 0
    for current, dirnames, filenames in os.walk(path, topdown=True, followlinks=False):
        current_path = Path(current)
        kept_dirs: List[str] = []
        for dirname in sorted(dirnames):
            full = current_path / dirname
            try:
                if full.is_symlink():
                    symlink_count += 1
                    continue
                st = full.stat()
            except OSError:
                error_count += 1
                continue
            if not stat.S_ISDIR(st.st_mode):
                continue
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        for filename in sorted(filenames):
            full = current_path / filename
            try:
                if full.is_symlink():
                    symlink_count += 1
                    continue
                st = full.stat()
            except OSError:
                error_count += 1
                continue
            if stat.S_ISREG(st.st_mode):
                total += int(st.st_size)
    return int(total), int(symlink_count), int(error_count)


def _candidate_size(path: Path) -> Tuple[int, str, int, int]:
    if not path.exists():
        return 0, "missing", 0, 0
    if path.is_symlink():
        return 0, "symlink", 1, 0
    kind = _path_kind(path)
    if kind == "file":
        try:
            return int(path.stat().st_size), "file", 0, 0
        except OSError:
            return 0, "file_error", 0, 1
    if kind == "dir":
        size, syms, errs = _dir_size_bytes(path)
        return int(size), "dir", int(syms), int(errs)
    return 0, "other", 0, 0


def _collect_candidates(root: Path) -> Dict[str, Any]:
    rels = _git_clean_candidates(root)
    rows: List[Candidate] = []
    skipped_symlink = 0
    skipped_error = 0
    skipped_missing = 0
    skipped_other = 0

    for relpath in rels:
        if not _is_ignored(root, relpath):
            raise RefuseError(f"candidate is not ignored (refusing): {relpath}")
        if _has_tracked_descendants(root, relpath):
            raise RefuseError(f"candidate has tracked files (refusing): {relpath}")

        abspath = root / relpath
        size, kind, symlink_count, error_count = _candidate_size(abspath)
        if kind == "missing":
            skipped_missing += 1
            continue
        if kind == "symlink" or symlink_count > 0:
            skipped_symlink += 1
            continue
        if error_count > 0 or kind == "file_error":
            skipped_error += 1
            continue
        if kind == "other":
            skipped_other += 1
            continue
        rows.append(Candidate(path=relpath, kind=kind, size_bytes=int(size)))

    rows.sort(key=lambda x: (-int(x.size_bytes), str(x.path)))
    return {
        "candidates": rows,
        "n_candidates_total": int(len(rels)),
        "skipped_symlink": int(skipped_symlink),
        "skipped_error": int(skipped_error),
        "skipped_missing": int(skipped_missing),
        "skipped_other": int(skipped_other),
    }


def _make_report(root: Path, *, min_mb: float, top_n: int) -> Dict[str, Any]:
    collected = _collect_candidates(root)
    candidates: List[Candidate] = list(collected["candidates"])
    threshold = int(float(min_mb) * 1024.0 * 1024.0)
    over = [x for x in candidates if int(x.size_bytes) >= int(threshold)]
    over.sort(key=lambda x: (-int(x.size_bytes), str(x.path)))
    selected = over[: int(top_n)]

    total_reclaimable_bytes = int(sum(int(x.size_bytes) for x in over))
    report: Dict[str, Any] = {
        "schema": SCHEMA_ID,
        "root": str(root),
        "min_mb": float(min_mb),
        "top_n": int(top_n),
        "n_candidates_total": int(collected["n_candidates_total"]),
        "n_candidates_over_threshold": int(len(over)),
        "n_selected": int(len(selected)),
        "total_reclaimable_bytes": int(total_reclaimable_bytes),
        "total_reclaimable_mb": float(total_reclaimable_bytes / (1024.0 * 1024.0)),
        "skipped_symlink_candidates": int(collected["skipped_symlink"]),
        "skipped_error_candidates": int(collected["skipped_error"]),
        "skipped_missing_candidates": int(collected["skipped_missing"]),
        "skipped_other_candidates": int(collected["skipped_other"]),
        "top_items": [
            {
                "path": str(x.path),
                "kind": str(x.kind),
                "size_bytes": int(x.size_bytes),
                "size_mb": float(int(x.size_bytes) / (1024.0 * 1024.0)),
            }
            for x in selected
        ],
    }
    return report


def _emit_script(root: Path, script_out: Path, items: Sequence[Dict[str, Any]]) -> None:
    lines: List[str] = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        "# Generated by clean_ignored_bloat.py",
        f"cd {json.dumps(str(root))}",
        "",
    ]
    for row in items:
        relpath = str(row.get("path", ""))
        if not relpath:
            continue
        lines.append(f"rm -rf -- {json.dumps(relpath)}")
    lines.append("")
    script_out.parent.mkdir(parents=True, exist_ok=True)
    script_out.write_text("\n".join(lines), encoding="utf-8")
    script_out.chmod(0o755)


def _delete_selected(root: Path, items: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    deleted = 0
    skipped_missing = 0
    for row in items:
        relpath = str(row.get("path", "")).strip()
        if not relpath:
            continue
        relpath = _norm_rel(relpath)
        if not _is_ignored(root, relpath):
            raise RefuseError(f"refusing to delete non-ignored path: {relpath}")
        if _has_tracked_descendants(root, relpath):
            raise RefuseError(f"refusing to delete path with tracked files: {relpath}")

        target = root / relpath
        if not target.exists():
            skipped_missing += 1
            continue
        if target.is_symlink():
            raise RefuseError(f"refusing to delete symlink candidate: {relpath}")
        if target.is_dir():
            shutil.rmtree(target)
            deleted += 1
        elif target.is_file():
            target.unlink()
            deleted += 1
        else:
            raise RefuseError(f"unsupported filesystem entry (refusing): {relpath}")
    return {"deleted": int(deleted), "skipped_missing": int(skipped_missing)}


def _print_text(mode: str, report: Dict[str, Any], *, script_out: Optional[Path], clean_meta: Optional[Dict[str, Any]]) -> None:
    print("== Root ==")
    print(f"root={report.get('root')}")
    print(f"mode={mode}")
    print("== Ignored candidates ==")
    print(
        f"n_total={report.get('n_candidates_total')} "
        f"n_over_threshold={report.get('n_candidates_over_threshold')} "
        f"n_selected={report.get('n_selected')}"
    )
    print(
        f"skipped_symlink={report.get('skipped_symlink_candidates')} "
        f"skipped_error={report.get('skipped_error_candidates')} "
        f"skipped_missing={report.get('skipped_missing_candidates')} "
        f"skipped_other={report.get('skipped_other_candidates')}"
    )
    print("== Top items ==")
    top_items = report.get("top_items") or []
    if not top_items:
        print("none")
    else:
        for row in top_items:
            print(
                f"path={row.get('path')} size_mb={row.get('size_mb'):.3f} "
                f"size_bytes={row.get('size_bytes')} kind={row.get('kind')}"
            )
    print("== Totals ==")
    print(
        f"total_reclaimable_mb={report.get('total_reclaimable_mb'):.3f} "
        f"total_reclaimable_bytes={report.get('total_reclaimable_bytes')}"
    )

    if mode == "emit_script" and script_out is not None:
        print("== Script ==")
        print(f"script_out={script_out}")

    if mode == "clean" and isinstance(clean_meta, dict):
        print("== Clean result ==")
        print(
            f"deleted={clean_meta.get('deleted')} "
            f"skipped_missing={clean_meta.get('skipped_missing')} "
            f"before_reclaimable_mb={clean_meta.get('before_reclaimable_mb'):.3f} "
            f"after_reclaimable_mb={clean_meta.get('after_reclaimable_mb'):.3f}"
        )

    print("== How to clean ==")
    print("report: python3 v11.0.0/scripts/clean_ignored_bloat.py --root . --mode report")
    print(
        "emit_script: python3 v11.0.0/scripts/clean_ignored_bloat.py "
        "--root . --mode emit_script --script-out cleanup_ignored_bloat.sh"
    )
    print(
        "clean: python3 v11.0.0/scripts/clean_ignored_bloat.py "
        "--root . --mode clean --yes"
    )


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Safe cleanup of ignored worktree bloat (stdlib-only).")
    ap.add_argument("--root", default=".", help="Repository root (default: .)")
    ap.add_argument("--mode", choices=("report", "emit_script", "clean"), default="report")
    ap.add_argument("--min-mb", type=float, default=1.0, help="Size threshold in MB (default: 1.0)")
    ap.add_argument("--top-n", type=int, default=50, help="Max number of selected items (default: 50)")
    ap.add_argument("--script-out", default=None, help="Output script path (required for --mode emit_script)")
    ap.add_argument("--yes", action="store_true", help="Required for --mode clean")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    ap.add_argument("--json-out", default=None, help="Write JSON report to path.")
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = parse_args(argv)
        root = Path(args.root).expanduser().resolve()
        git_root = _resolve_git_root(root)

        mode = str(args.mode)
        min_mb = float(args.min_mb)
        top_n = int(args.top_n)
        if top_n <= 0:
            raise RefuseError("--top-n must be > 0")
        if min_mb < 0.0:
            raise RefuseError("--min-mb must be >= 0")

        report = _make_report(git_root, min_mb=min_mb, top_n=top_n)
        payload: Dict[str, Any] = dict(report)
        payload["mode"] = mode

        script_out: Optional[Path] = None
        clean_meta: Optional[Dict[str, Any]] = None

        if mode == "emit_script":
            if not args.script_out:
                raise RefuseError("--script-out is required for --mode emit_script")
            script_out = Path(str(args.script_out)).expanduser().resolve()
            _emit_script(git_root, script_out, list(payload.get("top_items") or []))
            payload["script_out"] = str(script_out)

        elif mode == "clean":
            if not bool(args.yes):
                raise RefuseError("--mode clean requires --yes")
            before_mb = float(payload.get("total_reclaimable_mb", 0.0))
            clean_meta = _delete_selected(git_root, list(payload.get("top_items") or []))
            after = _make_report(git_root, min_mb=min_mb, top_n=top_n)
            after_mb = float(after.get("total_reclaimable_mb", 0.0))
            clean_meta["before_reclaimable_mb"] = float(before_mb)
            clean_meta["after_reclaimable_mb"] = float(after_mb)
            payload["clean"] = clean_meta
            payload["after"] = after

        if args.json_out:
            _write_json(Path(str(args.json_out)).expanduser().resolve(), payload)

        if str(args.format) == "json":
            print(json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False))
        else:
            _print_text(mode, report, script_out=script_out, clean_meta=clean_meta)

        return 0
    except RefuseError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except ToolError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

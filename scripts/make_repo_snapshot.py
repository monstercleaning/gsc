#!/usr/bin/env python3
"""Deterministic clean source snapshot export (stdlib-only)."""

from __future__ import annotations

import argparse
import fnmatch
import gzip
import hashlib
import io
import json
import os
import re
import stat
import subprocess
import sys
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


SCHEMA_ID = "gsc_repo_snapshot_manifest_v1"
FIXED_ZIP_DT = (2000, 1, 1, 0, 0, 0)
FIXED_UNIX_TS = 946684800  # 2000-01-01T00:00:00Z
SNAPSHOT_ROOT = "GSC"


PROFILE_SLIM_EXCLUDES: Tuple[str, ...] = (
    "v11.0.0/B/",
    "v11.0.0/archive/",
    "GSC_v8.2_COMPLETE.zip",
    "GSC_v10_sims.zip",
    "v11.0.0/GSC_v10_1_release.zip",
    "v11.0.0/GSC_v10_1_simulations.zip",
    "v11.0.0/archive/legacy/branch_A_v10.1/GSC_v10_1_release.zip",
    "v11.0.0/B/GSC_v10_8_PUBLICATION_BUNDLE.zip",
    "v11.0.0/B/GSC_v10_8_PUBLICATION_BUNDLE/phase10_upload.zip",
    "v11.0.0/B/GSC_v10_8_PUBLICATION_BUNDLE/phase10_upload_20260131_232127.zip",
)

PROFILE_SHARE_EXCLUDES: Tuple[str, ...] = (
    ".git/",
    "__MACOSX/",
    "._*",
    "**/._*",
    ".DS_Store",
    "**/.DS_Store",
    "**/.venv/",
    "**/__pycache__/",
    "v11.0.0/data/sn/",
    "v11.0.0/data/**/*.dat",
    "v11.0.0/results/",
    "v11.0.0/data/**/*.cov",
    "v11.0.0/data/**/*.npz",
    "v11.0.0/data/**",
    "v11.0.0/paper_assets*/",
    "v11.0.0/paper_assets*.zip",
    "paper_assets_v10.1.1-*.zip",
    "submission_bundle_*.zip",
    "referee_pack_*.zip",
    "toe_bundle_*.zip",
    "v11.0.0/artifacts/",
    "v11.0.0/archive/",
    "v11.0.0/archive/packs/",
    "v11.0.0/B/",
    "v11.0.0/B/GSC_v10_8_PUBLICATION_BUNDLE/",
)

PROFILE_REVIEW_WITH_DATA_EXCLUDES: Tuple[str, ...] = (
    "v11.0.0/results/",
    "v11.0.0/paper_assets",
    "v11.0.0/paper_assets*/",
    "v11.0.0/paper_assets*/**",
    "v11.0.0/artifacts/",
    "v11.0.0/archive/",
    "v11.0.0/B/",
    "paper_assets_v10.1.1-*.zip",
    "submission_bundle_*.zip",
    "referee_pack_*.zip",
    "toe_bundle_*.zip",
)

SHARE_DEFENSE_DENYLIST: Tuple[str, ...] = (
    ".git/",
    "**/.git/**",
    ".venv/",
    "**/.venv/**",
    "__pycache__/",
    "**/__pycache__/**",
    "__MACOSX/",
    "**/__MACOSX/**",
    "._*",
    "**/._*",
    ".DS_Store",
    "**/.DS_Store",
    "v11.0.0/results*/**",
    "v11.0.0/paper_assets*/**",
    "v11.0.0/data/**",
    "referee_pack_*.zip",
    "submission_bundle_*.zip",
    "toe_bundle_*.zip",
    "**/*.aux",
    "**/*.log",
    "**/*.out",
    "**/*.synctex.gz",
    "**/*.fls",
    "**/*.fdb_latexmk",
)

FS_FALLBACK_EXCLUDE_DIR_NAMES = {".git", ".venv", "__pycache__", "__MACOSX"}
FS_FALLBACK_EXCLUDE_FILE_NAMES = {".DS_Store"}
FS_FALLBACK_EXCLUDE_FILE_SUFFIXES = {".pyc"}


class SnapshotError(RuntimeError):
    """Hard execution failure (I/O/git/archive)."""


class SnapshotUsageError(ValueError):
    """Usage/config failure."""


@dataclass(frozen=True)
class SourceEntry:
    path: str
    mode: int
    source_kind: str  # git_blob | fs_path
    source_value: str


@dataclass
class SnapshotFile:
    path: str
    mode: int
    data: bytes
    sha256: str

    @property
    def size(self) -> int:
        return len(self.data)


@dataclass(frozen=True)
class DenylistHit:
    pattern: str
    count: int
    examples: Tuple[str, ...]


def _norm_posix(path: str) -> str:
    raw = str(path).strip().replace("\\", "/")
    # Strip only one explicit relative prefix; preserve dotfile names.
    if raw.startswith("./"):
        raw = raw[2:]
    pure = PurePosixPath(raw)
    if pure.is_absolute() or ".." in pure.parts:
        raise SnapshotUsageError(f"unsafe path: {path}")
    norm = str(pure)
    if norm in {"", "."}:
        raise SnapshotUsageError(f"invalid path: {path}")
    return norm


def _run_git(repo_root: Path, args: Sequence[str], *, text: bool) -> str | bytes:
    cmd = ["git", "-C", str(repo_root)] + [str(a) for a in args]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace").strip()
        stdout = proc.stdout.decode("utf-8", errors="replace").strip()
        details = stderr or stdout or f"git exited {proc.returncode}"
        raise SnapshotError(f"git command failed ({' '.join(args)}): {details}")
    return proc.stdout.decode("utf-8", errors="strict") if text else bytes(proc.stdout)


def _git_available(repo_root: Path) -> bool:
    try:
        _run_git(repo_root, ["rev-parse", "--is-inside-work-tree"], text=True)
        return True
    except SnapshotError:
        return False


def _resolve_repo_root(repo_root: Path) -> Path:
    candidate = repo_root.expanduser().resolve()
    if _git_available(candidate):
        out = _run_git(candidate, ["rev-parse", "--show-toplevel"], text=True)
        return Path(out.strip()).resolve()
    return candidate


def _resolve_ref_sha(repo_root: Path, ref: str) -> str:
    token = str(ref).strip() or "HEAD"
    out = _run_git(repo_root, ["rev-parse", f"{token}^{{commit}}"], text=True)
    return out.strip()


def _git_dirty(repo_root: Path, *, include_untracked: bool = False) -> bool:
    args: List[str] = ["status", "--porcelain"]
    if not include_untracked:
        args.append("--untracked-files=no")
    out = _run_git(repo_root, args, text=True)
    return bool(out.strip())


def _git_ls_tree_entries(repo_root: Path, ref: str) -> List[SourceEntry]:
    raw = _run_git(repo_root, ["ls-tree", "-r", "-l", "-z", str(ref)], text=False)
    pattern = re.compile(br"^(\d{6})\s+blob\s+([0-9a-f]{40})\s+(\d+|-)\t(.+)$")
    rows: List[SourceEntry] = []
    for item in bytes(raw).split(b"\0"):
        if not item:
            continue
        match = pattern.match(item)
        if match is None:
            continue
        mode_text = match.group(1).decode("ascii")
        blob = match.group(2).decode("ascii")
        relpath = _norm_posix(match.group(4).decode("utf-8", errors="surrogateescape"))
        mode = int(mode_text, 8)
        rows.append(SourceEntry(path=relpath, mode=mode, source_kind="git_blob", source_value=blob))
    rows.sort(key=lambda r: r.path)
    return rows


def _git_blob_bytes(repo_root: Path, blob_id: str) -> bytes:
    out = _run_git(repo_root, ["cat-file", "blob", str(blob_id)], text=False)
    return bytes(out)


def _describe_ref(repo_root: Path, sha: str) -> str:
    try:
        out = _run_git(repo_root, ["describe", "--tags", "--always", str(sha)], text=True)
        return out.strip()
    except SnapshotError:
        return str(sha)


def _fallback_git_meta_from_manifest(repo_root: Path) -> Optional[Dict[str, Any]]:
    manifest_path = repo_root / "repo_snapshot_manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None

    git_block = payload.get("git")
    sha = ""
    describe = ""
    dirty = False
    if isinstance(git_block, dict):
        sha = str(git_block.get("sha", "")).strip()
        describe = str(git_block.get("describe", "")).strip()
        dirty = bool(git_block.get("dirty", False))
    if not sha:
        sha = str(payload.get("git_head", "")).strip()
    if not sha:
        return None
    if not describe:
        describe = sha

    return {
        "sha": sha,
        "dirty": dirty,
        "describe": describe,
    }


def _is_lean_path(path: str) -> bool:
    p = str(path)
    root_allow = {
        "README.md",
        "LICENSE",
        "LICENSE.md",
        ".gitignore",
        "GSC_ONBOARDING_NEXT_SESSION.md",
    }
    if p in root_allow:
        return True
    if p in {
        "v11.0.0/GSC_Framework_v10_1_FINAL.md",
        "v11.0.0/GSC_Framework_v10_1_FINAL.tex",
    }:
        return True
    for prefix in (
        "v11.0.0/gsc/",
        "v11.0.0/scripts/",
        "v11.0.0/tests/",
        "v11.0.0/docs/",
    ):
        if p.startswith(prefix):
            return True
    return False


def _normalize_prefix(prefix: str) -> str:
    norm = _norm_posix(str(prefix).strip())
    if norm.endswith("/"):
        return norm
    return norm


def _prefix_matches(path: str, prefix: str) -> bool:
    p = str(path)
    q = str(prefix)
    if q.endswith("/"):
        return p.startswith(q)
    return p == q or p.startswith(q + "/")


def _rule_matches(path: str, rule: str) -> bool:
    token = str(rule)
    if any(ch in token for ch in ("*", "?", "[")):
        return fnmatch.fnmatch(path, token)
    return _prefix_matches(path, token)


def _canonical_profile(profile: str) -> str:
    mode = str(profile)
    if mode == "ultra_slim":
        return "share"
    return mode


def _apply_profile(entries: Sequence[SourceEntry], profile: str) -> Tuple[List[SourceEntry], List[str]]:
    mode = _canonical_profile(str(profile))
    selected: List[SourceEntry]
    profile_excludes: List[str] = []
    if mode == "full":
        selected = list(entries)
    elif mode == "slim":
        profile_excludes = [str(x) for x in PROFILE_SLIM_EXCLUDES]
        selected = [
            row
            for row in entries
            if not any(_rule_matches(row.path, pref) for pref in profile_excludes)
        ]
    elif mode == "lean":
        selected = [row for row in entries if _is_lean_path(row.path)]
    elif mode == "share":
        profile_excludes = [str(x) for x in PROFILE_SHARE_EXCLUDES]
        selected = [row for row in entries if _is_lean_path(row.path)]
        selected = [
            row
            for row in selected
            if not any(_rule_matches(row.path, pref) for pref in profile_excludes)
        ]
    elif mode == "review_with_data":
        profile_excludes = [str(x) for x in PROFILE_REVIEW_WITH_DATA_EXCLUDES]
        selected = [
            row
            for row in entries
            if not any(_rule_matches(row.path, pref) for pref in profile_excludes)
        ]
    else:
        raise SnapshotUsageError(f"unsupported profile: {mode}")
    selected.sort(key=lambda r: r.path)
    return selected, profile_excludes


def _apply_user_excludes(
    entries: Sequence[SourceEntry],
    *,
    exclude_prefixes: Sequence[str],
    exclude_globs: Sequence[str],
) -> List[SourceEntry]:
    out: List[SourceEntry] = []
    for row in entries:
        if any(_prefix_matches(row.path, pref) for pref in exclude_prefixes):
            continue
        if any(fnmatch.fnmatch(row.path, pat) for pat in exclude_globs):
            continue
        out.append(row)
    out.sort(key=lambda r: r.path)
    return out


def _apply_denylist(
    entries: Sequence[SourceEntry], patterns: Sequence[str]
) -> Tuple[List[SourceEntry], List[DenylistHit]]:
    kept: List[SourceEntry] = []
    counts: Dict[str, int] = {}
    samples: Dict[str, List[str]] = {}
    for row in entries:
        matched: Optional[str] = None
        for pattern in patterns:
            if _rule_matches(row.path, pattern):
                matched = str(pattern)
                break
        if matched is None:
            kept.append(row)
            continue
        counts[matched] = int(counts.get(matched, 0)) + 1
        if matched not in samples:
            samples[matched] = []
        if len(samples[matched]) < 3:
            samples[matched].append(str(row.path))

    hits: List[DenylistHit] = []
    for pattern in patterns:
        key = str(pattern)
        count = int(counts.get(key, 0))
        if count <= 0:
            continue
        hits.append(
            DenylistHit(
                pattern=key,
                count=count,
                examples=tuple(sorted(samples.get(key, []))),
            )
        )
    kept.sort(key=lambda r: r.path)
    return kept, hits


def _collect_filesystem_entries(repo_root: Path) -> List[SourceEntry]:
    rows: List[SourceEntry] = []
    for current, dirnames, filenames in os.walk(repo_root, topdown=True, followlinks=False):
        current_path = Path(current)

        kept_dirs: List[str] = []
        for name in sorted(dirnames):
            if name in FS_FALLBACK_EXCLUDE_DIR_NAMES:
                continue
            kept_dirs.append(name)
        dirnames[:] = kept_dirs

        for name in sorted(filenames):
            if name in FS_FALLBACK_EXCLUDE_FILE_NAMES:
                continue
            if any(name.endswith(sfx) for sfx in FS_FALLBACK_EXCLUDE_FILE_SUFFIXES):
                continue
            abs_path = current_path / name
            try:
                if abs_path.is_symlink():
                    # Keep symlink handling simple and deterministic in fallback mode.
                    continue
                st = abs_path.stat()
            except (FileNotFoundError, PermissionError, OSError):
                continue
            if not stat.S_ISREG(st.st_mode):
                continue
            rel = _norm_posix(str(abs_path.resolve().relative_to(repo_root.resolve())))
            rows.append(
                SourceEntry(
                    path=rel,
                    mode=int(st.st_mode) & 0o777,
                    source_kind="fs_path",
                    source_value=str(abs_path.resolve()),
                )
            )
    rows.sort(key=lambda r: r.path)
    return rows


def _read_entry_bytes(repo_root: Path, row: SourceEntry) -> bytes:
    if row.source_kind == "git_blob":
        return _git_blob_bytes(repo_root, row.source_value)
    if row.source_kind == "fs_path":
        return Path(row.source_value).read_bytes()
    raise SnapshotError(f"unknown source_kind: {row.source_kind}")


def _snapshot_files(repo_root: Path, entries: Sequence[SourceEntry]) -> List[SnapshotFile]:
    files: List[SnapshotFile] = []
    for row in entries:
        if stat.S_IFMT(int(row.mode)) == stat.S_IFLNK:
            raise SnapshotError(f"symlink entries are not allowed in snapshot: {row.path}")
        data = _read_entry_bytes(repo_root, row)
        sha = hashlib.sha256(data).hexdigest()
        mode = int(row.mode)
        files.append(SnapshotFile(path=row.path, mode=mode, data=data, sha256=sha))
    files.sort(key=lambda f: f.path)
    return files


def _norm_perm(mode: int) -> int:
    mode_bits = int(mode) & 0o777
    if mode_bits & 0o111:
        return 0o755
    return 0o644


def _build_manifest_base(
    *,
    repo_root: Path,
    ref: str,
    profile: str,
    git_meta: Optional[Dict[str, Any]],
    files: Sequence[SnapshotFile],
    profile_excludes: Sequence[str],
    user_excludes: Sequence[str],
    user_exclude_globs: Sequence[str],
    denylist_hits: Sequence[DenylistHit],
    include_absolute_paths: bool,
) -> Dict[str, Any]:
    file_rows = [
        {
            "bytes": int(f.size),
            "path": str(f.path),
            "sha256": str(f.sha256),
        }
        for f in files
    ]
    total_bytes = int(sum(int(row["bytes"]) for row in file_rows))
    manifest: Dict[str, Any] = {
        "schema": SCHEMA_ID,
        "repo_root": ".",
        "ref": str(ref),
        "profile": str(profile),
        "git": git_meta,
        "git_head": git_meta.get("sha") if isinstance(git_meta, dict) else None,
        "n_files": int(len(file_rows)),
        "total_bytes": int(total_bytes),
        "estimated_total_bytes": int(total_bytes),
        "total_bytes_estimate": int(total_bytes),
        "files": file_rows,
        "excluded": {
            "profile_excludes": [str(x) for x in profile_excludes],
            "user_excludes": [str(x) for x in user_excludes],
            "user_exclude_globs": [str(x) for x in user_exclude_globs],
        },
        "denylist_hits": [
            {
                "pattern": str(hit.pattern),
                "count": int(hit.count),
                "examples": [str(x) for x in hit.examples],
            }
            for hit in denylist_hits
        ],
    }
    if bool(include_absolute_paths):
        manifest["repo_root_abs"] = str(repo_root)
    return manifest


def _manifest_bytes(manifest: Dict[str, Any]) -> bytes:
    return (json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def _ensure_clean_output_dir(path: Path) -> None:
    if path.exists():
        if not path.is_dir():
            raise SnapshotError(f"outdir exists and is not a directory: {path}")
        if any(path.iterdir()):
            raise SnapshotUsageError(f"outdir must be empty: {path}")
    path.mkdir(parents=True, exist_ok=True)


def _write_dir_snapshot(outdir: Path, files: Sequence[SnapshotFile], manifest: Dict[str, Any]) -> None:
    _ensure_clean_output_dir(outdir)
    root = outdir / SNAPSHOT_ROOT
    root.mkdir(parents=True, exist_ok=True)

    for row in files:
        target = root / Path(row.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(row.data)
        target.chmod(_norm_perm(row.mode))

    (root / "repo_snapshot_manifest.json").write_bytes(_manifest_bytes(manifest))


def _write_zip_snapshot(output: Path, files: Sequence[SnapshotFile], manifest: Dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for row in files:
            arcname = f"{SNAPSHOT_ROOT}/{row.path}"
            info = zipfile.ZipInfo(filename=arcname, date_time=FIXED_ZIP_DT)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = ((0o100000 | _norm_perm(row.mode)) & 0xFFFF) << 16
            zf.writestr(info, row.data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)

        m_info = zipfile.ZipInfo(
            filename=f"{SNAPSHOT_ROOT}/repo_snapshot_manifest.json",
            date_time=FIXED_ZIP_DT,
        )
        m_info.compress_type = zipfile.ZIP_DEFLATED
        m_info.create_system = 3
        m_info.external_attr = ((0o100000 | 0o644) & 0xFFFF) << 16
        zf.writestr(m_info, _manifest_bytes(manifest), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def _write_targz_snapshot(output: Path, files: Sequence[SnapshotFile], manifest: Dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=FIXED_UNIX_TS, filename="") as gz:
            with tarfile.open(fileobj=gz, mode="w") as tf:
                for row in files:
                    arcname = f"{SNAPSHOT_ROOT}/{row.path}"
                    data = row.data
                    info = tarfile.TarInfo(name=arcname)
                    info.size = len(data)
                    info.mode = _norm_perm(row.mode)
                    info.mtime = FIXED_UNIX_TS
                    info.uid = 0
                    info.gid = 0
                    info.uname = "root"
                    info.gname = "root"
                    tf.addfile(info, io.BytesIO(data))

                manifest_data = _manifest_bytes(manifest)
                m_info = tarfile.TarInfo(name=f"{SNAPSHOT_ROOT}/repo_snapshot_manifest.json")
                m_info.size = len(manifest_data)
                m_info.mode = 0o644
                m_info.mtime = FIXED_UNIX_TS
                m_info.uid = 0
                m_info.gid = 0
                m_info.uname = "root"
                m_info.gname = "root"
                tf.addfile(m_info, io.BytesIO(manifest_data))


def _sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve_formats(args: argparse.Namespace) -> Tuple[str, str]:
    fmt = str(args.format)
    summary_format = fmt if fmt in {"text", "json"} else "text"
    snapshot_format = str(args.snapshot_format) if args.snapshot_format else None
    if snapshot_format is None and fmt in {"dir", "tar.gz", "zip"}:
        snapshot_format = fmt
    if snapshot_format is None:
        snapshot_format = "zip"
    return summary_format, snapshot_format


def _gate_size_or_raise(*, max_mb: Optional[float], size_bytes: int, what: str) -> None:
    if max_mb is None:
        return
    limit = int(float(max_mb) * 1024.0 * 1024.0)
    if int(size_bytes) > int(limit):
        raise SnapshotUsageError(
            f"size gate failed ({what}): {size_bytes} bytes > limit {limit} bytes (--max-mb {max_mb})"
        )


def _print_text(manifest: Dict[str, Any], *, list_files: bool) -> None:
    print(f"schema={manifest.get('schema')}")
    print(f"profile={manifest.get('profile')}")
    print(f"ref={manifest.get('ref')}")
    git_meta = manifest.get("git")
    if isinstance(git_meta, dict):
        print(f"git_sha={git_meta.get('sha')}")
        print(f"git_dirty={str(bool(git_meta.get('dirty'))).lower()}")
    else:
        print("git_sha=none")
        print("git_dirty=unknown")
    print(f"n_files={manifest.get('n_files')}")
    print(f"total_bytes={manifest.get('total_bytes')}")
    denylist_hits = manifest.get("denylist_hits")
    if isinstance(denylist_hits, list):
        print(f"denylist_hits={len(denylist_hits)}")
        for row in denylist_hits:
            if not isinstance(row, dict):
                continue
            print(f"denylist_hit pattern={row.get('pattern')} count={row.get('count')}")
    archive = manifest.get("archive")
    if isinstance(archive, dict):
        print(f"archive_format={archive.get('format')}")
        print(f"archive_path={archive.get('path')}")
        print(f"archive_bytes={archive.get('bytes')}")
        print(f"archive_sha256={archive.get('sha256')}")
    if list_files:
        for row in manifest.get("files", []):
            if isinstance(row, dict):
                print(f"file={row.get('path')}")


def _write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Create deterministic clean repo snapshot from git/filesystem (stdlib-only).")
    ap.add_argument("--repo-root", default=".", help="Repository root (default: current directory).")
    ap.add_argument("--ref", default="HEAD", help="Git ref to snapshot when git is available (default: HEAD).")

    ap.add_argument(
        "--profile",
        choices=("full", "slim", "lean", "share", "ultra_slim", "review_with_data"),
        default="lean",  # Preserve M74 default behavior.
        help=(
            "Snapshot profile (lean keeps M74 behavior; slim excludes heavy legacy/bundle paths; "
            "share/ultra_slim is a shareable code+docs profile; review_with_data keeps tracked data "
            "while excluding derived/bloat paths)."
        ),
    )
    ap.add_argument("--exclude", action="append", default=[], help="Repeatable repo-relative exclude prefix.")
    ap.add_argument("--exclude-glob", action="append", default=[], help="Repeatable fnmatch glob exclude.")

    ap.add_argument(
        "--format",
        choices=("text", "json", "dir", "tar.gz", "zip"),
        default="text",
        help="Stdout format (text/json). For compatibility, also accepts dir/tar.gz/zip to set snapshot format.",
    )
    ap.add_argument(
        "--snapshot-format",
        choices=("dir", "tar.gz", "zip"),
        default=None,
        help="Snapshot artifact format (default: zip).",
    )

    ap.add_argument(
        "--out",
        default=None,
        help=(
            "Unified output path alias. For zip/tar.gz it is the archive file path; "
            "for dir format it is the destination directory."
        ),
    )
    ap.add_argument(
        "--zip-out",
        default=None,
        help="User-friendly alias for zip snapshots (equivalent to --out when snapshot format is zip).",
    )
    ap.add_argument("--output", default=None, help="Legacy archive output alias for tar.gz/zip snapshot formats.")
    ap.add_argument("--outdir", default=None, help="Legacy directory output alias for dir snapshot format.")

    ap.add_argument("--json-out", default=None, help="Optional JSON manifest output path.")
    ap.add_argument("--list-files", action="store_true", help="Include per-file lines in text output.")
    ap.add_argument("--dry-run", action="store_true", help="Do not materialize snapshot; emit manifest only.")
    ap.add_argument(
        "--require-clean",
        choices=("0", "1"),
        default="0",
        help="If 1, fail with exit code 2 when git worktree is dirty (includes untracked files).",
    )
    ap.add_argument("--max-mb", type=float, default=None, help="Optional size gate in MB (exit code 2 on violation).")
    ap.add_argument(
        "--include-absolute-paths",
        action="store_true",
        help="Include absolute path metadata fields in manifest (default: portable redacted manifest).",
    )
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = parse_args(argv)
        summary_format, snapshot_format = _resolve_formats(args)
        zip_out_raw = str(args.zip_out).strip() if args.zip_out is not None else ""
        if zip_out_raw:
            if snapshot_format != "zip":
                raise SnapshotUsageError(
                    "--zip-out requires zip snapshot format (do not use --snapshot-format/--format dir|tar.gz)"
                )
            out_raw = str(args.out).strip() if args.out is not None else ""
            output_raw = str(args.output).strip() if args.output is not None else ""
            if out_raw and out_raw != zip_out_raw:
                raise SnapshotUsageError("--zip-out conflicts with --out (different paths)")
            if output_raw and output_raw != zip_out_raw:
                raise SnapshotUsageError("--zip-out conflicts with --output (different paths)")
            if not out_raw and not output_raw:
                args.out = zip_out_raw

        repo_root = _resolve_repo_root(Path(args.repo_root))

        git_meta: Optional[Dict[str, Any]] = None
        warnings: List[str] = []

        profile = _canonical_profile(str(args.profile))

        if _git_available(repo_root):
            try:
                sha = _resolve_ref_sha(repo_root, str(args.ref))
                git_meta = {
                    "sha": str(sha),
                    "dirty": bool(_git_dirty(repo_root)),
                    "describe": _describe_ref(repo_root, str(sha)),
                }
                entries = _git_ls_tree_entries(repo_root, str(args.ref))
            except SnapshotError as exc:
                raise SnapshotError(f"git mode failed: {exc}") from exc
        else:
            entries = _collect_filesystem_entries(repo_root)
            warnings.append("git unavailable; used filesystem fallback mode")
            fallback_meta = _fallback_git_meta_from_manifest(repo_root)
            if fallback_meta is None:
                git_meta = {
                    "sha": "unknown",
                    "dirty": False,
                    "describe": "unknown",
                }
                warnings.append("git metadata fallback unresolved; using sha=unknown")
            else:
                git_meta = fallback_meta
                warnings.append("git metadata fallback sourced from repo_snapshot_manifest.json")

        if str(args.require_clean) == "1":
            if not _git_available(repo_root):
                raise SnapshotUsageError("--require-clean 1 requires git metadata (no .git repository available)")
            if _git_dirty(repo_root, include_untracked=True):
                raise SnapshotUsageError("--require-clean 1 but git worktree is dirty")

        selected_profile, profile_excludes = _apply_profile(entries, profile)

        user_excludes = [_normalize_prefix(x) for x in list(args.exclude or []) if str(x).strip()]
        user_exclude_globs = [str(x).strip() for x in list(args.exclude_glob or []) if str(x).strip()]

        selected = _apply_user_excludes(
            selected_profile,
            exclude_prefixes=user_excludes,
            exclude_globs=user_exclude_globs,
        )
        denylist_hits: List[DenylistHit] = []
        if profile == "share":
            selected, denylist_hits = _apply_denylist(selected, SHARE_DEFENSE_DENYLIST)
        if not selected:
            raise SnapshotUsageError("selected file set is empty after profile/exclude filtering")

        files = _snapshot_files(repo_root, selected)

        manifest = _build_manifest_base(
            repo_root=repo_root,
            ref=str(args.ref),
            profile=profile,
            git_meta=git_meta,
            files=files,
            profile_excludes=profile_excludes,
            user_excludes=user_excludes,
            user_exclude_globs=user_exclude_globs,
            denylist_hits=denylist_hits,
            include_absolute_paths=bool(args.include_absolute_paths),
        )
        if warnings:
            manifest["warnings"] = [str(x) for x in warnings]

        if not bool(args.dry_run):
            if snapshot_format == "dir":
                outdir_raw = args.outdir or args.output or args.out
                if not outdir_raw:
                    raise SnapshotUsageError("--outdir is required for --snapshot-format dir (or use --output as alias)")
                outdir = Path(outdir_raw).expanduser().resolve()
                _write_dir_snapshot(outdir, files, manifest)
                _gate_size_or_raise(max_mb=args.max_mb, size_bytes=int(manifest["total_bytes"]), what="dir total bytes")
                manifest["archive"] = None
                manifest["output_dir"] = str(outdir)
            else:
                out_raw = args.output or args.out
                if not out_raw:
                    raise SnapshotUsageError("--output (or legacy --out) is required for archive snapshot formats")
                output = Path(out_raw).expanduser().resolve()
                if snapshot_format == "zip":
                    _write_zip_snapshot(output, files, manifest)
                elif snapshot_format == "tar.gz":
                    _write_targz_snapshot(output, files, manifest)
                else:
                    raise SnapshotUsageError(f"unsupported snapshot format: {snapshot_format}")

                archive_bytes = int(output.stat().st_size)
                archive_sha = _sha256_path(output)
                _gate_size_or_raise(max_mb=args.max_mb, size_bytes=archive_bytes, what="archive size")
                manifest["archive"] = {
                    "format": str(snapshot_format),
                    "path": str(output),
                    "bytes": int(archive_bytes),
                    "sha256": str(archive_sha),
                }
        else:
            if args.max_mb is not None:
                _gate_size_or_raise(max_mb=args.max_mb, size_bytes=int(manifest["total_bytes"]), what="dry-run total bytes")
            manifest["archive"] = None

        if args.json_out:
            _write_json(Path(args.json_out).expanduser().resolve(), manifest)

        if summary_format == "json":
            print(json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False))
        else:
            _print_text(manifest, list_files=bool(args.list_files))
        return 0

    except SnapshotUsageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except SnapshotError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

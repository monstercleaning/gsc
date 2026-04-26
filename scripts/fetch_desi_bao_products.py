#!/usr/bin/env python3
"""Fetch DESI BAO compact products and emit a pinned deterministic manifest."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple
from urllib.parse import urlparse
from urllib.request import urlopen


TOOL = "fetch_desi_bao_products"
TOOL_VERSION = "m156-v1"
SCHEMA = "phase4_desi_bao_fetch_manifest_v1"
FAIL_MARKER = "PHASE4_DESI_BAO_FETCH_FAILED"
DEFAULT_CREATED_UTC_EPOCH = 946684800  # 2000-01-01T00:00:00Z
DEFAULT_FILES: Tuple[str, ...] = ("desi_dr1_bao_baseline.csv",)
DR1_GAUSSIAN_COMMIT = "bb0c1c9009dc76d1391300e169e8df38fd1096db"
DR1_GAUSSIAN_FILES: Tuple[str, ...] = (
    "desi_2024_gaussian_bao_ALL_GCcomb_mean.txt",
    "desi_2024_gaussian_bao_ALL_GCcomb_cov.txt",
)


class UsageError(Exception):
    """CLI usage/configuration error."""


class FetchError(Exception):
    """Fetch/verification error."""


def _sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_pretty(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def _to_iso_utc(epoch_seconds: int) -> str:
    try:
        dt = datetime.fromtimestamp(int(epoch_seconds), tz=timezone.utc)
    except Exception as exc:
        raise UsageError("--created-utc must be a valid integer epoch-seconds value") from exc
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _source_kind(raw: str) -> Tuple[str, str]:
    parsed = urlparse(raw)
    if parsed.scheme in ("http", "https"):
        return "url_prefix", raw.rstrip("/")
    if parsed.scheme == "file":
        return "local_dir", Path(parsed.path).expanduser().resolve().as_posix()

    path = Path(raw).expanduser()
    if path.is_dir():
        return "local_dir", str(path.resolve())
    if parsed.scheme:
        raise UsageError(f"unsupported --source scheme: {parsed.scheme}")
    raise UsageError("--source must be an existing directory or an http(s)/file URL prefix")


def _source_hint(kind: str, value: str) -> str:
    if kind == "url_prefix":
        return value
    return Path(value).name or "."


def _fetch_url_bytes(url: str) -> bytes:
    with urlopen(url, timeout=60) as resp:  # nosec B310
        data = resp.read()
    if not isinstance(data, (bytes, bytearray)) or len(data) == 0:
        raise FetchError(f"empty response from source url: {url}")
    return bytes(data)


def _fetch_one(source_kind: str, source_value: str, filename: str) -> bytes:
    if source_kind == "local_dir":
        path = Path(source_value) / filename
        if not path.is_file():
            raise FetchError(f"source file not found: {filename}")
        data = path.read_bytes()
        if not data:
            raise FetchError(f"source file is empty: {filename}")
        return data
    if source_kind == "url_prefix":
        return _fetch_url_bytes(f"{source_value}/{filename}")
    raise FetchError(f"unsupported source kind: {source_kind}")


def _load_existing_manifest(path: Path) -> Optional[Dict[str, Any]]:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise FetchError(f"failed to parse existing manifest: {path.name}") from exc
    if not isinstance(payload, dict):
        raise FetchError("existing manifest must be a JSON object")
    return payload


def _verify_existing_hash(existing: Optional[Dict[str, Any]], filename: str, observed_sha256: str) -> None:
    if existing is None:
        return
    files = existing.get("files")
    if not isinstance(files, Mapping):
        raise FetchError("existing manifest is missing files object")
    entry = files.get(filename)
    if not isinstance(entry, Mapping):
        raise FetchError(f"existing manifest is missing files.{filename}")
    expected = entry.get("sha256")
    if not isinstance(expected, str):
        raise FetchError(f"existing manifest files.{filename}.sha256 is invalid")
    if expected.lower() != observed_sha256.lower():
        raise FetchError(
            f"sha256 mismatch for {filename}: expected {expected.lower()} got {observed_sha256.lower()}"
        )


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Fetch DESI BAO compact products with pinned SHA256 manifesting.")
    ap.add_argument("--outdir", required=True, type=Path)
    ap.add_argument("--source", default=None)
    ap.add_argument("--preset", choices=("none", "dr1_gaussian_all_gccomb"), default="none")
    ap.add_argument("--manifest-out", required=True, type=Path)
    ap.add_argument("--file", action="append", default=None, help="File name to fetch (repeatable)")
    ap.add_argument("--release-id", default="desi_dr1_bao_baseline_compact_v1")
    ap.add_argument(
        "--license-note",
        default="See v11.0.0/docs/DATA_LICENSES_AND_SOURCES.md and upstream DESI terms.",
    )
    ap.add_argument("--deterministic", choices=(0, 1), type=int, default=1)
    ap.add_argument("--created-utc", type=int, default=None)
    ap.add_argument("--format", choices=("text", "json"), default="text")
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = _parse_args(argv)

        deterministic_mode = bool(int(args.deterministic))
        if args.created_utc is not None:
            created_epoch = int(args.created_utc)
        elif deterministic_mode:
            created_epoch = DEFAULT_CREATED_UTC_EPOCH
        else:
            created_epoch = int(time.time())
        retrieved_utc = _to_iso_utc(created_epoch)

        outdir = Path(args.outdir).expanduser().resolve()
        outdir.mkdir(parents=True, exist_ok=True)

        manifest_out = Path(args.manifest_out).expanduser().resolve()
        manifest_out.parent.mkdir(parents=True, exist_ok=True)

        source_raw = str(args.source).strip() if args.source is not None else ""
        source_kind: str
        source_value: str
        release_id = str(args.release_id)
        license_note = str(args.license_note)
        preset = str(args.preset)
        pinned_commit: Optional[str] = None

        if preset == "dr1_gaussian_all_gccomb":
            pinned_commit = DR1_GAUSSIAN_COMMIT
            source_kind = "url_prefix"
            source_value = (
                "https://raw.githubusercontent.com/CobayaSampler/bao_data/"
                f"{DR1_GAUSSIAN_COMMIT}"
            )
            release_id = "desi_dr1_gaussian_all_gccomb_2024"
            license_note = (
                "DESI DR1 BAO Gaussian summary products from CobayaSampler/bao_data "
                "(see v11.0.0/docs/DATA_LICENSES_AND_SOURCES.md)."
            )
        else:
            if not source_raw:
                raise UsageError("--source is required when --preset none")
            source_kind, source_value = _source_kind(source_raw)

        source_hint = _source_hint(source_kind, source_value)

        if args.file is None:
            if preset == "dr1_gaussian_all_gccomb":
                files_in = list(DR1_GAUSSIAN_FILES)
            else:
                files_in = list(DEFAULT_FILES)
        else:
            files_in = list(args.file)
        files = sorted({str(v).strip() for v in files_in if str(v).strip()})
        if not files:
            raise UsageError("at least one --file is required")

        existing_manifest = _load_existing_manifest(manifest_out)

        files_payload: Dict[str, Dict[str, Any]] = {}
        for filename in files:
            data = _fetch_one(source_kind, source_value, filename)
            sha = _sha256_bytes(data)
            _verify_existing_hash(existing_manifest, filename, sha)

            dst = outdir / filename
            dst.write_bytes(data)
            files_payload[filename] = {
                "sha256": _sha256_file(dst),
                "bytes": int(len(data)),
            }

        payload: Dict[str, Any] = {
            "schema": SCHEMA,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "retrieved_utc": retrieved_utc,
            "retrieved_utc_epoch": int(created_epoch),
            "deterministic_mode": bool(deterministic_mode),
            "source": {
                "kind": source_kind,
                "value": source_hint,
                "release_id": release_id,
                "preset": preset,
            },
            "files": files_payload,
            "license_terms_note": license_note,
            "paths_redacted": True,
        }
        if pinned_commit is not None:
            payload["source"]["pinned_commit"] = pinned_commit

        text = _json_pretty(payload)
        manifest_out.write_text(text, encoding="utf-8")

        if str(args.format) == "json":
            print(text, end="")
        else:
            print(f"schema={SCHEMA}")
            print(f"source_kind={source_kind}")
            print(f"source={source_hint}")
            print(f"release_id={release_id}")
            print(f"preset={preset}")
            if pinned_commit is not None:
                print(f"pinned_commit={pinned_commit}")
            print(f"n_files={len(files_payload)}")
            for name in sorted(files_payload):
                print(f"file.{name}.sha256={files_payload[name]['sha256']}")
            print(f"manifest={manifest_out.name}")
        return 0

    except (UsageError, FetchError) as exc:
        print(f"{FAIL_MARKER}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

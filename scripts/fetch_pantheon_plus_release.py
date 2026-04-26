#!/usr/bin/env python3
"""Fetch Pantheon+ data artifacts with deterministic SHA256 manifesting."""

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


TOOL = "fetch_pantheon_plus_release"
TOOL_VERSION = "m154-v1"
SCHEMA = "phase4_pantheon_plus_fetch_manifest_v1"
FAIL_MARKER = "PHASE4_PANTHEON_FETCH_FAILED"
DEFAULT_CREATED_UTC_EPOCH = 946684800  # 2000-01-01T00:00:00Z


class UsageError(Exception):
    """CLI usage error."""


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


def _fetch_url_bytes(url: str) -> bytes:
    with urlopen(url, timeout=60) as resp:  # nosec B310
        data = resp.read()
    if not isinstance(data, (bytes, bytearray)) or len(data) == 0:
        raise FetchError(f"empty response from source url: {url}")
    return bytes(data)


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


def _verify_existing_hash(existing: Optional[Dict[str, Any]], logical_name: str, observed_sha256: str) -> None:
    if existing is None:
        return
    files = existing.get("files")
    if not isinstance(files, Mapping):
        raise FetchError("existing manifest is missing files object")
    entry = files.get(logical_name)
    if not isinstance(entry, Mapping):
        raise FetchError(f"existing manifest is missing files.{logical_name}")
    expected = entry.get("sha256")
    if not isinstance(expected, str):
        raise FetchError(f"existing manifest files.{logical_name}.sha256 is invalid")
    if expected.lower() != observed_sha256.lower():
        raise FetchError(
            f"sha256 mismatch for {logical_name}: expected {expected.lower()} got {observed_sha256.lower()}"
        )


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


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Fetch Pantheon+ mu/cov artifacts with pinned SHA256 manifest.")
    ap.add_argument("--outdir", required=True, type=Path)
    ap.add_argument("--source", required=True)
    ap.add_argument("--manifest-out", required=True, type=Path)
    ap.add_argument("--mu-name", default="pantheon_plus_shoes_mu.csv")
    ap.add_argument("--cov-name", default="pantheon_plus_shoes_cov.cov")
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
        created_utc = _to_iso_utc(created_epoch)

        outdir = Path(args.outdir).expanduser().resolve()
        outdir.mkdir(parents=True, exist_ok=True)

        manifest_out = Path(args.manifest_out).expanduser().resolve()
        if not manifest_out.parent.exists():
            manifest_out.parent.mkdir(parents=True, exist_ok=True)

        source_kind, source_value = _source_kind(str(args.source))
        source_hint = _source_hint(source_kind, source_value)

        existing_manifest = _load_existing_manifest(manifest_out)

        files_payload: Dict[str, Dict[str, Any]] = {}
        for logical_name, filename in (("mu", str(args.mu_name)), ("cov", str(args.cov_name))):
            data = _fetch_one(source_kind, source_value, filename)
            sha = _sha256_bytes(data)
            _verify_existing_hash(existing_manifest, logical_name, sha)

            dst = outdir / filename
            dst.write_bytes(data)
            files_payload[logical_name] = {
                "filename": filename,
                "sha256": _sha256_file(dst),
                "bytes": int(len(data)),
            }

        payload: Dict[str, Any] = {
            "schema": SCHEMA,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "created_utc": created_utc,
            "created_utc_epoch": int(created_epoch),
            "deterministic_mode": bool(deterministic_mode),
            "source": {
                "kind": source_kind,
                "value": source_hint,
            },
            "files": files_payload,
            "paths_redacted": True,
        }

        text = _json_pretty(payload)
        manifest_out.write_text(text, encoding="utf-8")

        if str(args.format) == "json":
            print(text, end="")
        else:
            print(f"schema={SCHEMA}")
            print(f"source_kind={source_kind}")
            print(f"source={source_hint}")
            print(f"mu_sha256={files_payload['mu']['sha256']}")
            print(f"cov_sha256={files_payload['cov']['sha256']}")
            print(f"manifest={manifest_out.name}")
        return 0

    except (UsageError, FetchError) as exc:
        print(f"{FAIL_MARKER}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

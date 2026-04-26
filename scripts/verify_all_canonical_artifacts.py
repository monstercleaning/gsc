#!/usr/bin/env python3
"""Meta verifier for canonical artifact lines (offline-safe)."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Set


_ALLOWED_TYPES = {"late-time", "submission", "referee", "toe"}
_ALLOWED_TIERS = {"frozen", "recommended"}
_REQUIRED_ARTIFACT_KEYS = {"late_time", "submission", "referee_pack", "toe_bundle"}
_RE_SHA256 = re.compile(r"^[0-9a-f]{64}$")

V101_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = V101_DIR / "canonical_artifacts.json"
DEFAULT_STATUS_DOC = V101_DIR / "docs" / "status_canonical_artifacts.md"


class CatalogError(ValueError):
    pass


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _parse_csv_set(text: str, *, allowed: Set[str], name: str) -> Set[str]:
    toks = {t.strip() for t in str(text).split(",") if t.strip()}
    if not toks:
        raise CatalogError(f"{name} selection is empty")
    unknown = sorted(t for t in toks if t not in allowed)
    if unknown:
        raise CatalogError(f"unknown {name}: {', '.join(unknown)}")
    return toks


def _validate_leaf_record(record: Dict[str, Any], *, expected_type: str, label: str) -> Dict[str, Any]:
    if not isinstance(record, dict):
        raise CatalogError(f"{label} must be an object")
    required_keys = {"type", "tier", "tag", "release_url", "asset", "sha256"}
    missing = sorted(required_keys - set(record.keys()))
    if missing:
        raise CatalogError(f"{label} missing keys: {', '.join(missing)}")

    typ = str(record["type"])
    if typ != expected_type:
        raise CatalogError(f"{label} type must be {expected_type!r}, got {typ!r}")

    tier = str(record["tier"])
    if tier not in _ALLOWED_TIERS:
        raise CatalogError(f"{label} has invalid tier: {tier!r}")

    for key in ("tag", "release_url", "asset"):
        if not str(record[key]).strip():
            raise CatalogError(f"{label} has empty {key}")

    sha = str(record["sha256"]).strip().lower()
    if _RE_SHA256.match(sha) is None:
        raise CatalogError(f"{label} has invalid sha256: {sha!r}")

    out = dict(record)
    out["sha256"] = sha
    return out


def _normalize_catalog_schema_v2(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    artifacts = obj.get("artifacts")
    if not isinstance(artifacts, dict):
        raise CatalogError("catalog.artifacts must be an object for schema_version=2")
    keys = set(artifacts.keys())
    if keys != _REQUIRED_ARTIFACT_KEYS:
        missing = sorted(_REQUIRED_ARTIFACT_KEYS - keys)
        extra = sorted(keys - _REQUIRED_ARTIFACT_KEYS)
        parts: List[str] = []
        if missing:
            parts.append(f"missing: {', '.join(missing)}")
        if extra:
            parts.append(f"unexpected: {', '.join(extra)}")
        raise CatalogError(f"catalog.artifacts keys mismatch ({'; '.join(parts)})")

    entries: List[Dict[str, Any]] = []
    mapping = {
        "late_time": "late-time",
        "submission": "submission",
        "referee_pack": "referee",
        "toe_bundle": "toe",
    }
    for key, expected_type in mapping.items():
        rec = _validate_leaf_record(artifacts[key], expected_type=expected_type, label=f"artifacts.{key}")
        rec["id"] = key
        entries.append(rec)
    return entries


def _normalize_catalog_schema_v1(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    artifacts = obj.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise CatalogError("catalog.artifacts must be a non-empty list")

    required_keys = {"id", "type", "tier", "tag", "release_url", "asset", "sha256"}
    seen_ids: Set[str] = set()
    entries: List[Dict[str, Any]] = []
    for idx, art in enumerate(artifacts):
        if not isinstance(art, dict):
            raise CatalogError(f"artifacts[{idx}] must be an object")
        missing = sorted(required_keys - set(art.keys()))
        if missing:
            raise CatalogError(f"artifacts[{idx}] missing keys: {', '.join(missing)}")

        aid = str(art["id"])
        if not aid:
            raise CatalogError(f"artifacts[{idx}] has empty id")
        if aid in seen_ids:
            raise CatalogError(f"duplicate artifact id: {aid}")
        seen_ids.add(aid)

        atyp = str(art["type"])
        if atyp not in _ALLOWED_TYPES:
            raise CatalogError(f"artifacts[{idx}] has unknown type: {atyp}")

        tier = str(art["tier"])
        if tier not in _ALLOWED_TIERS:
            raise CatalogError(f"artifacts[{idx}] has unknown tier: {tier}")

        sha = str(art["sha256"]).strip().lower()
        if _RE_SHA256.match(sha) is None:
            raise CatalogError(f"artifacts[{idx}] has invalid sha256: {sha!r}")

        out = dict(art)
        out["sha256"] = sha
        entries.append(out)

    return entries


def load_catalog(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise CatalogError(f"catalog not found: {path}")
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise CatalogError(f"catalog is not valid JSON: {e}") from e

    if not isinstance(obj, dict):
        raise CatalogError("catalog root must be a JSON object")

    schema_version = int(obj.get("schema_version", 0))
    if schema_version == 2:
        normalized = _normalize_catalog_schema_v2(obj)
    elif schema_version == 1:
        normalized = _normalize_catalog_schema_v1(obj)
    else:
        raise CatalogError("catalog schema_version must be 1 or 2")

    out = dict(obj)
    out["_normalized_artifacts"] = normalized
    return out


def _selected_artifacts(catalog: Dict[str, Any], *, tiers: Set[str], types: Set[str] | None) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for art in catalog["_normalized_artifacts"]:
        if art["tier"] not in tiers:
            continue
        if types is not None and art["type"] not in types:
            continue
        out.append(art)
    return out


def _validate_status_sync(status_doc: Path, artifacts: Sequence[Dict[str, Any]]) -> List[str]:
    if not status_doc.is_file():
        return [f"missing status doc: {status_doc}"]
    text = status_doc.read_text(encoding="utf-8", errors="replace")
    misses: List[str] = []
    for art in artifacts:
        for key in ("tag", "asset", "sha256"):
            val = str(art[key])
            if val not in text:
                misses.append(f"status doc missing {key} token for {art['id']}: {val}")
    return misses


def _verifier_cmd(artifact: Dict[str, Any], *, scripts_dir: Path, asset_path: Path, skip_smoke_compile: bool) -> List[str]:
    kind = artifact["type"]
    if kind == "late-time":
        return [
            sys.executable,
            str(scripts_dir / "verify_release_bundle.py"),
            str(asset_path),
            "--expected-sha256",
            artifact["sha256"],
        ]
    if kind == "submission":
        cmd = [sys.executable, str(scripts_dir / "verify_submission_bundle.py"), str(asset_path)]
        if not skip_smoke_compile:
            cmd.append("--smoke-compile")
        return cmd
    if kind == "referee":
        return [sys.executable, str(scripts_dir / "verify_referee_pack.py"), str(asset_path)]
    if kind == "toe":
        return [sys.executable, str(scripts_dir / "verify_toe_bundle.py"), str(asset_path)]
    raise CatalogError(f"unsupported artifact type: {kind}")


def _resolve_asset_path(artifacts_dir: Path, asset_value: str) -> Path:
    asset = Path(asset_value)
    if asset.is_absolute():
        return asset

    candidates = [artifacts_dir / asset]
    # Release assets are often in repo root, but paper-assets zips may live under v11.0.0/.
    if "/" not in asset_value and "\\" not in asset_value:
        candidates.append(artifacts_dir / "v11.0.0" / asset)

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="verify_all_canonical_artifacts",
        description="Verify canonical/recommended artifacts from v11.0.0/canonical_artifacts.json",
    )
    ap.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    ap.add_argument("--artifacts-dir", type=Path, default=Path.cwd())
    ap.add_argument("--tiers", default="frozen,recommended", help="CSV subset of {frozen,recommended}")
    ap.add_argument("--types", default="", help="Optional CSV subset of {late-time,submission,referee,toe}")
    ap.add_argument("--dry-run", action="store_true", help="Check schema/sync/sha only; skip per-type verifier scripts")
    ap.add_argument("--skip-smoke-compile", action="store_true", help="Skip pdflatex smoke compile for submission artifact")
    ap.add_argument("--skip-status-doc-check", action="store_true")
    ap.add_argument("--status-doc", type=Path, default=DEFAULT_STATUS_DOC)
    args = ap.parse_args(argv)

    try:
        catalog = load_catalog(args.catalog)
        tiers = _parse_csv_set(args.tiers, allowed=_ALLOWED_TIERS, name="tiers")
        types = None
        if str(args.types).strip():
            types = _parse_csv_set(args.types, allowed=_ALLOWED_TYPES, name="types")
    except CatalogError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    selected = _selected_artifacts(catalog, tiers=tiers, types=types)
    if not selected:
        print("ERROR: no artifacts selected by current --tiers/--types filters", file=sys.stderr)
        return 2

    if not args.skip_status_doc_check:
        misses = _validate_status_sync(args.status_doc, selected)
        if misses:
            print("ERROR: status markdown is out of sync with canonical_artifacts.json:", file=sys.stderr)
            for m in misses:
                print(f"  - {m}", file=sys.stderr)
            return 2

    scripts_dir = Path(__file__).resolve().parent
    artifacts_dir = args.artifacts_dir.expanduser().resolve()

    for art in selected:
        asset_path = _resolve_asset_path(artifacts_dir, str(art["asset"]))
        if not asset_path.is_file():
            print(f"ERROR: missing asset file for {art['id']}: {asset_path}", file=sys.stderr)
            return 2

        got_sha = _sha256_file(asset_path)
        if got_sha.lower() != str(art["sha256"]).lower():
            print(
                f"ERROR: sha256 mismatch for {art['id']} ({asset_path.name}):\n"
                f"  expected: {art['sha256']}\n"
                f"  got:      {got_sha}",
                file=sys.stderr,
            )
            return 2

        print(f"[ok] sha256 {art['id']} -> {asset_path.name}")

        if args.dry_run:
            continue

        cmd = _verifier_cmd(art, scripts_dir=scripts_dir, asset_path=asset_path, skip_smoke_compile=args.skip_smoke_compile)
        r = subprocess.run(cmd, capture_output=True, text=True)
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        if r.returncode != 0:
            print(f"ERROR: verifier failed for {art['id']} with command: {' '.join(cmd)}", file=sys.stderr)
            if out:
                print(out, file=sys.stderr)
            return 2
        print(f"[ok] verifier {art['id']}")

    print("OK: all selected canonical artifacts verified")
    print(f"  catalog: {args.catalog}")
    print(f"  artifacts_dir: {artifacts_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

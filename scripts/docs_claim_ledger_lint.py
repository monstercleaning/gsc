#!/usr/bin/env python3
"""Validate docs/claim_ledger.json for structural and path-safety constraints."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set


SCHEMA = "phase2_claim_ledger_lint_v1"
DEFAULT_LEDGER_REL = "docs/claim_ledger.json"
VALID_STATUS = {"supported", "bounded", "planned"}
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")

FORBIDDEN_PARTS: Set[str] = {
    ".git",
    ".venv",
    "__MACOSX",
    "node_modules",
    "site-packages",
    "dist",
    "build",
    "artifacts",
}
FORBIDDEN_SUFFIXES: Set[str] = {
    ".DS_Store",
}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _is_safe_relative_path(path_text: str) -> bool:
    if not path_text or path_text.startswith("/"):
        return False
    normalized = path_text.replace("\\", "/")
    parts = PurePosixPath(normalized).parts
    if not parts:
        return False
    if ".." in parts:
        return False
    if any(part in FORBIDDEN_PARTS for part in parts):
        return False
    if any(normalized.endswith(suffix) for suffix in FORBIDDEN_SUFFIXES):
        return False
    return True


def _lint_payload(payload: Any, repo_root: Path) -> Dict[str, Any]:
    errors: List[str] = []

    if not isinstance(payload, Mapping):
        return {
            "schema": SCHEMA,
            "status": "fail",
            "error_count": 1,
            "errors": ["Ledger root must be a JSON object."],
        }

    entries = payload.get("entries")
    if not isinstance(entries, list):
        errors.append("Ledger 'entries' must be a list.")
        entries = []

    seen_ids: Set[str] = set()
    for idx, raw_entry in enumerate(entries):
        where = f"entries[{idx}]"
        if not isinstance(raw_entry, Mapping):
            errors.append(f"{where}: entry must be an object.")
            continue

        entry = dict(raw_entry)
        entry_id = str(entry.get("id", "")).strip()
        if not entry_id:
            errors.append(f"{where}: missing non-empty 'id'.")
        elif entry_id in seen_ids:
            errors.append(f"{where}: duplicate id '{entry_id}'.")
        else:
            seen_ids.add(entry_id)

        claim_text = str(entry.get("claim_text", "")).strip()
        if not claim_text:
            errors.append(f"{where}: missing non-empty 'claim_text'.")

        status = str(entry.get("status", "")).strip()
        if status not in VALID_STATUS:
            errors.append(f"{where}: status must be one of {sorted(VALID_STATUS)}.")

        doc_locations = entry.get("doc_locations")
        if not isinstance(doc_locations, list) or not doc_locations:
            errors.append(f"{where}: 'doc_locations' must be a non-empty list.")
        else:
            for jdx, raw_loc in enumerate(doc_locations):
                loc_where = f"{where}.doc_locations[{jdx}]"
                if not isinstance(raw_loc, Mapping):
                    errors.append(f"{loc_where}: location must be an object.")
                    continue
                doc_path = str(raw_loc.get("path", "")).strip()
                if not _is_safe_relative_path(doc_path):
                    errors.append(f"{loc_where}: invalid or forbidden doc path '{doc_path}'.")
                    continue
                abs_doc = (repo_root / doc_path).resolve()
                if not abs_doc.is_file():
                    errors.append(f"{loc_where}: referenced doc does not exist: {doc_path}")
                section = str(raw_loc.get("section", "")).strip()
                if not section:
                    errors.append(f"{loc_where}: missing non-empty 'section'.")

        artifacts = entry.get("supporting_artifacts")
        if not isinstance(artifacts, list):
            errors.append(f"{where}: 'supporting_artifacts' must be a list.")
            artifacts = []
        for jdx, raw_art in enumerate(artifacts):
            art_where = f"{where}.supporting_artifacts[{jdx}]"
            if not isinstance(raw_art, Mapping):
                errors.append(f"{art_where}: artifact must be an object.")
                continue
            art_path = str(raw_art.get("path", "")).strip()
            if not _is_safe_relative_path(art_path):
                errors.append(f"{art_where}: invalid or forbidden artifact path '{art_path}'.")
            sha = raw_art.get("sha256")
            if sha is not None:
                sha_text = str(sha).strip()
                if not HEX64_RE.match(sha_text):
                    errors.append(f"{art_where}: sha256 must be 64 lowercase hex chars.")

        tests = entry.get("tests")
        if not isinstance(tests, list):
            errors.append(f"{where}: 'tests' must be a list.")
        else:
            for jdx, raw_test in enumerate(tests):
                test_where = f"{where}.tests[{jdx}]"
                test_path = str(raw_test).strip()
                if not _is_safe_relative_path(test_path):
                    errors.append(f"{test_where}: invalid or forbidden test path '{test_path}'.")

    return {
        "schema": SCHEMA,
        "status": "ok" if not errors else "fail",
        "error_count": len(errors),
        "errors": sorted(errors),
    }


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Lint docs/claim_ledger.json structure and references.")
    ap.add_argument("--repo-root", default="v11.0.0", help="Repository sub-root that contains docs/ and scripts/")
    ap.add_argument("--ledger", default=DEFAULT_LEDGER_REL, help=f"Ledger path relative to --repo-root (default: {DEFAULT_LEDGER_REL})")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    repo_root = Path(str(args.repo_root)).expanduser().resolve()
    if not repo_root.is_dir():
        print(f"ERROR: --repo-root is not a directory: {repo_root}")
        return 1

    ledger_path = (repo_root / str(args.ledger)).resolve()
    if not ledger_path.is_file():
        print(f"ERROR: --ledger file not found: {ledger_path}")
        return 1

    try:
        payload = _load_json(ledger_path)
    except Exception as exc:
        print(f"ERROR: failed to parse JSON ledger: {exc}")
        return 1

    result = _lint_payload(payload, repo_root)
    if str(args.format) == "json":
        print(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2))
    else:
        print(f"schema={result.get('schema')}")
        print(f"status={result.get('status')}")
        print(f"error_count={result.get('error_count')}")
        for err in result.get("errors", []):
            print(f"- {err}")

    if result.get("status") != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

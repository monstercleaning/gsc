#!/usr/bin/env python3
"""
predictions_sign.py — sign and timestamp a pre-registered prediction.

Implements the signing protocol documented in docs/pre_registration.md.

Usage:
    python3 scripts/predictions_sign.py P1
    python3 scripts/predictions_sign.py P1 --gpg-key <key-id>
    python3 scripts/predictions_sign.py --list

Status: SCAFFOLD — protocol defined, full GPG integration pending (M201).

The signing operation:

1. Verifies the prediction directory exists at predictions_register/<ID>/.
2. Reads prediction.md and validates required front-matter fields.
3. Loads pipeline_output.json and computes its SHA-256 hash.
4. Captures the current repository commit SHA via `git rev-parse HEAD`.
5. Captures an ISO-8601 UTC timestamp.
6. Updates prediction.md front-matter with signature fields:
       signed_by, signature_timestamp, repo_commit_at_signing, pipeline_output_hash, status
7. Optionally produces a GPG-signed bundle of the entire prediction directory.

Once signed, prediction.md is immutable. Edits require creating a superseding
prediction (e.g., P1.r2) that explicitly references the original.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTER_DIR = REPO_ROOT / "predictions_register"


REQUIRED_FRONT_MATTER = (
    "prediction_id",
    "title",
    "tier",
    "ansatz",
    "target_dataset",
    "target_release_date",
    "status",
)


def list_predictions() -> list[str]:
    """Return the IDs of all prediction directories present."""
    if not REGISTER_DIR.exists():
        return []
    return sorted(
        p.name
        for p in REGISTER_DIR.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    )


def parse_front_matter(text: str) -> dict[str, str]:
    """Lightweight YAML front-matter parser (key: value, no nesting)."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    out: dict[str, str] = {}
    for line in text[3:end].splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            out[key.strip()] = value.strip()
    return out


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def current_git_commit(cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(cwd),
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def resolve_prediction_dir(prediction_id: str) -> Path | None:
    """Accept either full directory name (P1_bao_ruler_shift) or short ID (P1)."""
    direct = REGISTER_DIR / prediction_id
    if direct.is_dir():
        return direct
    candidates = sorted(
        p for p in REGISTER_DIR.iterdir()
        if p.is_dir() and p.name.startswith(prediction_id + "_")
    )
    if len(candidates) == 1:
        return candidates[0]
    return None


def split_front_matter(text: str) -> tuple[list[str], str]:
    """Split a markdown file into (front_matter_lines, body) where body excludes the
    front-matter delimiters. Returns ([], full_text) if no front-matter present.
    """
    if not text.startswith("---"):
        return [], text
    end = text.find("\n---", 3)
    if end == -1:
        return [], text
    fm_block = text[3:end].strip("\n")
    body = text[end + 4 :]
    if body.startswith("\n"):
        body = body[1:]
    return fm_block.splitlines(), body


def update_front_matter_lines(lines: list[str], updates: dict[str, str]) -> list[str]:
    """Return a new list of front-matter lines with `updates` applied.

    For each key in `updates`, if a line `key: ...` exists, replace its value;
    otherwise append `key: value` to the end.
    """
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        key = stripped.split(":", 1)[0].strip() if ":" in stripped else None
        if key is not None and key in updates:
            indent = line[: len(line) - len(stripped)]
            out.append(f"{indent}{key}: {updates[key]}")
            seen.add(key)
        else:
            out.append(line)
    for key, value in updates.items():
        if key not in seen:
            out.append(f"{key}: {value}")
    return out


def write_signed_markdown(md_path: Path, fm_lines: list[str], body: str) -> None:
    """Write back the signed markdown with deterministic format."""
    text = "---\n" + "\n".join(fm_lines) + "\n---\n" + body
    md_path.write_text(text, encoding="utf-8")


def sign(prediction_id: str, gpg_key: str | None = None, dry_run: bool = False) -> int:
    pred_dir = resolve_prediction_dir(prediction_id)
    if pred_dir is None:
        sys.stderr.write(f"error: no such prediction: {prediction_id}\n")
        return 2

    md_path = pred_dir / "prediction.md"
    if not md_path.is_file():
        sys.stderr.write(f"error: missing {md_path}\n")
        return 2

    pipeline_path = pred_dir / "pipeline_output.json"
    if not pipeline_path.is_file():
        sys.stderr.write(
            f"error: missing {pipeline_path}; run the prediction pipeline first\n"
        )
        return 2

    md_text = md_path.read_text(encoding="utf-8")
    fm = parse_front_matter(md_text)
    missing = [k for k in REQUIRED_FRONT_MATTER if k not in fm]
    if missing:
        sys.stderr.write(
            f"error: prediction.md missing required front-matter fields: {missing}\n"
        )
        return 2

    status_upper = fm.get("status", "").upper()
    if not (status_upper.startswith("SCAFFOLD") or status_upper.startswith("DRAFT")):
        sys.stderr.write(
            f"error: prediction status is {fm.get('status')}; "
            "only SCAFFOLD/DRAFT predictions may be signed\n"
        )
        return 2

    pipeline_hash = sha256_of_file(pipeline_path)
    commit_sha = current_git_commit(REPO_ROOT)
    timestamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    signer = os.environ.get("GSC_SIGNER", os.environ.get("USER", "unknown"))

    sys.stdout.write(
        f"prediction {prediction_id}:\n"
        f"  pipeline_output_hash = {pipeline_hash}\n"
        f"  repo_commit_at_signing = {commit_sha}\n"
        f"  signature_timestamp = {timestamp}\n"
        f"  signed_by = {signer}\n"
    )
    if gpg_key:
        sys.stdout.write(f"  gpg_key = {gpg_key}\n")

    if dry_run:
        sys.stdout.write("\nDRY RUN: front-matter not modified.\n")
        return 0

    fm_lines, body = split_front_matter(md_text)
    updates = {
        "status": "SIGNED",
        "signed_by": signer,
        "signature_timestamp": timestamp,
        "repo_commit_at_signing": commit_sha,
        "pipeline_output_hash": pipeline_hash,
    }
    if gpg_key:
        updates["gpg_key"] = gpg_key
    new_fm_lines = update_front_matter_lines(fm_lines, updates)
    write_signed_markdown(md_path, new_fm_lines, body)

    sys.stdout.write(f"\nsigned: {md_path}\n")
    if gpg_key:
        sys.stdout.write(
            "  (note: GPG --detach-sign of the prediction directory bundle "
            "is not yet wired; the signature_timestamp and pipeline_output_hash "
            "are recorded in front-matter as the signing record.)\n"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("prediction_id", nargs="?", help="prediction ID, e.g. P1")
    parser.add_argument("--gpg-key", help="GPG key ID to sign with")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="preview the signature record without modifying prediction.md",
    )
    parser.add_argument(
        "--list", action="store_true", help="list available predictions and exit"
    )
    args = parser.parse_args(argv)

    if args.list:
        for pid in list_predictions():
            sys.stdout.write(f"{pid}\n")
        return 0

    if not args.prediction_id:
        parser.error("prediction_id is required (or use --list)")
        return 2

    return sign(args.prediction_id, gpg_key=args.gpg_key, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())

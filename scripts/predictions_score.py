#!/usr/bin/env python3
"""
predictions_score.py — score a pre-registered prediction against released data.

Implements the scoring protocol documented in docs/pre_registration.md.

Usage:
    python3 scripts/predictions_score.py P1
    python3 scripts/predictions_score.py P1 --observed-data path/to/observed.json
    python3 scripts/predictions_score.py --list

Status: SCAFFOLD — protocol defined, per-prediction scoring algorithms pending.

The scoring operation:

1. Loads the signed prediction at predictions_register/<ID>/prediction.md.
2. Verifies the signature is intact (pipeline_output_hash, signature_timestamp).
3. Loads the observational data file (CSV/JSON) corresponding to the target.
4. Runs the per-prediction scoring algorithm declared in prediction.md.
5. Writes scorecard.md alongside the prediction with the pass/fail outcome.
6. The scorecard is appended to the register; the original prediction.md is unchanged.

Scoring outcomes drive tier/module promotion or demotion in the next framework cycle.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTER_DIR = REPO_ROOT / "predictions_register"


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def list_predictions() -> list[str]:
    if not REGISTER_DIR.exists():
        return []
    return sorted(
        p.name
        for p in REGISTER_DIR.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    )


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


def score(prediction_id: str, observed_path: Path | None) -> int:
    pred_dir = resolve_prediction_dir(prediction_id)
    if pred_dir is None:
        sys.stderr.write(f"error: no such prediction: {prediction_id}\n")
        return 2

    md_path = pred_dir / "prediction.md"
    pipeline_path = pred_dir / "pipeline_output.json"
    if not md_path.is_file():
        sys.stderr.write(f"error: missing {md_path}\n")
        return 2
    if not pipeline_path.is_file():
        sys.stderr.write(
            f"error: missing {pipeline_path}; "
            "the prediction has no signed pipeline output\n"
        )
        return 2

    # Verify the registered hash matches the on-disk pipeline output.
    md_text = md_path.read_text(encoding="utf-8")
    if "pipeline_output_hash:" not in md_text:
        sys.stderr.write(
            f"error: prediction is unsigned (no pipeline_output_hash in front-matter)\n"
        )
        return 2

    actual_hash = sha256_of_file(pipeline_path)
    sys.stdout.write(f"prediction {prediction_id}:\n")
    sys.stdout.write(f"  computed pipeline_output_hash = {actual_hash}\n")
    sys.stdout.write(
        "  (signature verification not yet implemented; implementation in M201)\n"
    )

    if observed_path is None:
        sys.stdout.write(
            "  no observed-data path supplied; scoring deferred until observation released\n"
        )
        return 0

    if not observed_path.is_file():
        sys.stderr.write(f"error: observed-data file not found: {observed_path}\n")
        return 2

    sys.stdout.write(f"  observed-data file: {observed_path}\n")
    sys.stdout.write(
        "  per-prediction scoring algorithm not yet implemented for this ID.\n"
    )
    sys.stdout.write(
        "  Scoring algorithms are defined in each predictions_register/<ID>/prediction.md.\n"
    )

    timestamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    scorecard_path = pred_dir / "scorecard.md"
    sys.stdout.write(f"\nDRY RUN: would write scorecard to {scorecard_path}\n")
    sys.stdout.write(f"  scorecard timestamp = {timestamp}\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("prediction_id", nargs="?", help="prediction ID, e.g. P1")
    parser.add_argument(
        "--observed-data",
        type=Path,
        help="path to observational data file to score against",
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

    return score(args.prediction_id, args.observed_data)


if __name__ == "__main__":
    sys.exit(main())

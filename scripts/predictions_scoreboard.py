#!/usr/bin/env python3
"""
predictions_scoreboard.py — render a summary of all pre-registered predictions.

Usage:
    python3 scripts/predictions_scoreboard.py
    python3 scripts/predictions_scoreboard.py --format json
    python3 scripts/predictions_scoreboard.py --format markdown > scoreboard.md

Reads each predictions_register/<ID>/prediction.md, extracts front-matter,
and produces a tabular summary of:

- prediction ID and title;
- tier;
- target dataset and release date;
- signing status (UNSIGNED, SIGNED, SCORED);
- last scored result (if any).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTER_DIR = REPO_ROOT / "predictions_register"


def parse_front_matter(text: str) -> dict[str, str]:
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


def collect_predictions() -> list[dict]:
    if not REGISTER_DIR.exists():
        return []
    rows: list[dict] = []
    for d in sorted(REGISTER_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        md = d / "prediction.md"
        if not md.is_file():
            continue
        fm = parse_front_matter(md.read_text(encoding="utf-8"))
        scorecard = d / "scorecard.md"
        if scorecard.is_file():
            status = "SCORED"
        elif fm.get("status", "").upper() == "SIGNED":
            status = "SIGNED"
        else:
            status = "UNSIGNED"
        rows.append(
            {
                "id": fm.get("prediction_id", d.name),
                "directory": d.name,
                "title": fm.get("title", "—"),
                "tier": fm.get("tier", "—"),
                "target": fm.get("target_dataset", "—"),
                "release": fm.get("target_release_date", "—"),
                "status": status,
                "signed_by": fm.get("signed_by", "—"),
                "signature_timestamp": fm.get("signature_timestamp", "—"),
            }
        )
    return rows


def render_text(rows: list[dict]) -> str:
    if not rows:
        return "(no predictions found in predictions_register/)\n"
    out: list[str] = []
    out.append(f"{'ID':<4}  {'TIER':<14}  {'STATUS':<10}  TITLE")
    out.append("-" * 80)
    for r in rows:
        out.append(
            f"{r['id']:<4}  {r['tier']:<14}  {r['status']:<10}  {r['title']}"
        )
    return "\n".join(out) + "\n"


def render_markdown(rows: list[dict]) -> str:
    if not rows:
        return "_(no predictions found)_\n"
    out: list[str] = []
    out.append("# Predictions Scoreboard\n")
    out.append("| ID | Title | Tier | Target | Release | Status |")
    out.append("|---|---|---|---|---|---|")
    for r in rows:
        out.append(
            f"| {r['id']} | {r['title']} | {r['tier']} | "
            f"{r['target']} | {r['release']} | {r['status']} |"
        )
    return "\n".join(out) + "\n"


def render_json(rows: list[dict]) -> str:
    return json.dumps(rows, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--format",
        choices=("text", "markdown", "json"),
        default="text",
        help="output format",
    )
    args = parser.parse_args(argv)

    rows = collect_predictions()
    if args.format == "text":
        sys.stdout.write(render_text(rows))
    elif args.format == "markdown":
        sys.stdout.write(render_markdown(rows))
    elif args.format == "json":
        sys.stdout.write(render_json(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Deterministic JOSS readiness preflight checks for repository root metadata."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence


TOOL = "phase4_joss_preflight"
FAIL_MARKER = "PHASE4_JOSS_PREFLIGHT_FAILED"
DEFAULT_CREATED_UTC = "2000-01-01T00:00:00Z"
PLACEHOLDER_DATES = {"2000-01-01", "1970-01-01", "0000-00-00", "1900-01-01"}


class UsageError(Exception):
    """CLI/configuration error."""


class PreflightError(Exception):
    """Validation failure."""


def _json_pretty(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def _check_exists(repo_root: Path, relpath: str) -> Dict[str, Any]:
    p = repo_root / relpath
    ok = p.is_file()
    return {
        "id": f"exists:{relpath}",
        "status": "ok" if ok else "fail",
        "detail": relpath,
    }


def _parse_front_matter(path: Path) -> Dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise PreflightError("paper.md must start with YAML front matter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise PreflightError("paper.md front matter closing delimiter missing")
    front = text[4:end]
    out: Dict[str, str] = {}
    for raw in front.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        out[key.strip()] = value.strip()
    return out


def _paper_heading_checks(repo_root: Path) -> List[Dict[str, Any]]:
    paper = repo_root / "paper.md"
    if not paper.is_file():
        return [
            {
                "id": "paper_required_headings",
                "status": "fail",
                "detail": "paper.md not found",
            }
        ]
    text = paper.read_text(encoding="utf-8")
    required = ("# Summary", "# Statement of need", "# References", "# AI usage disclosure")
    missing = [h for h in required if h not in text]
    return [
        {
            "id": "paper_required_headings",
            "status": "ok" if not missing else "fail",
            "detail": "missing=" + ",".join(missing) if missing else "all required headings present",
        }
    ]


def _validate_date(date_value: str) -> bool:
    if date_value in PLACEHOLDER_DATES:
        return False
    try:
        parsed = date.fromisoformat(date_value)
    except ValueError:
        return False
    return parsed.year >= 2020


def _front_matter_checks(repo_root: Path) -> List[Dict[str, Any]]:
    paper = repo_root / "paper.md"
    if not paper.is_file():
        return [
            {
                "id": "paper_front_matter",
                "status": "fail",
                "detail": "paper.md not found",
            }
        ]

    front = _parse_front_matter(paper)
    required = ("title", "tags", "authors", "affiliations", "date", "bibliography")
    missing = [k for k in required if k not in front]
    checks: List[Dict[str, Any]] = []
    checks.append(
        {
            "id": "paper_front_matter_required_keys",
            "status": "ok" if not missing else "fail",
            "detail": "missing=" + ",".join(missing) if missing else "all required keys present",
        }
    )

    date_value = front.get("date", "")
    checks.append(
        {
            "id": "paper_date_non_placeholder",
            "status": "ok" if _validate_date(date_value) else "fail",
            "detail": f"date={date_value!r}",
        }
    )

    bibliography_value = front.get("bibliography", "")
    bib_ok = bool(bibliography_value) and (repo_root / bibliography_value).is_file()
    checks.append(
        {
            "id": "paper_bibliography_path",
            "status": "ok" if bib_ok else "fail",
            "detail": f"bibliography={bibliography_value!r}",
        }
    )
    return checks


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Run deterministic JOSS readiness preflight checks.")
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    ap.add_argument("--out-json", default=None, help="Optional path to write JSON report deterministically.")
    ap.add_argument("--created-utc", default=DEFAULT_CREATED_UTC)
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = _parse_args(argv)
        repo_root = Path(str(args.repo_root)).expanduser().resolve()
        if not repo_root.is_dir():
            raise UsageError(f"repo-root not found: {repo_root}")

        checks: List[Dict[str, Any]] = []
        for rel in (
            "LICENSE",
            "CODE_OF_CONDUCT.md",
            "CONTRIBUTING.md",
            "paper.md",
            "paper.bib",
            "CITATION.cff",
        ):
            checks.append(_check_exists(repo_root, rel))

        checks.extend(_front_matter_checks(repo_root))
        checks.extend(_paper_heading_checks(repo_root))

        failures = [row for row in checks if row.get("status") != "ok"]
        payload: Dict[str, Any] = {
            "schema": "phase4_joss_preflight_report_v1",
            "tool": TOOL,
            "created_utc": str(args.created_utc),
            "repo_root_name": repo_root.name,
            "status": "ok" if not failures else "fail",
            "checks": checks,
        }

        if args.out_json:
            out_path = Path(str(args.out_json)).expanduser().resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(_json_pretty(payload), encoding="utf-8")

        if str(args.format) == "json":
            print(_json_pretty(payload), end="")
        else:
            print(f"tool={TOOL}")
            print(f"status={payload['status']}")
            print(f"checks_total={len(checks)}")
            print(f"checks_failed={len(failures)}")
            for row in checks:
                print(f"- {row['id']}: {row['status']} ({row['detail']})")

        return 0 if not failures else 2

    except (UsageError, PreflightError) as exc:
        print(f"{FAIL_MARKER}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

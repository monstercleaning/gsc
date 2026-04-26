#!/usr/bin/env python3
"""Lint canonical artifact pointers in docs against canonical_artifacts.json (schema v2)."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

import verify_all_canonical_artifacts as verify_all


V101_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = V101_DIR.parent
DEFAULT_CATALOG = V101_DIR / "canonical_artifacts.json"

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_ALLOW_CONTEXT = ("frozen", "baseline", "guardrail", "legacy", "by default", "default output")
_CANONICAL_CONTEXT_RE = re.compile(
    r"v10\.1\.1-(late-time-r\d+|submission-r\d+|referee-pack-r\d+|toe-track-r\d+)"
    r"|paper_assets_v10\.1\.1-late-time-r\d+\.zip"
    r"|submission_bundle_v10\.1\.1-late-time-r\d+\.zip"
    r"|referee_pack_v10\.1\.1-late-time-r\d+(?:-r\d+)?\.zip"
    r"|toe_bundle_v10\.1\.1-r\d+\.zip",
    flags=re.IGNORECASE,
)


@dataclass
class LintIssue:
    file: Path
    line: int
    found: str
    expected: str
    reason: str


def _scan_files(repo_root: Path) -> List[Path]:
    docs_root = repo_root / "v11.0.0" / "docs"
    out: List[Path] = [
        repo_root / "README.md",
        repo_root / "GSC_ONBOARDING_NEXT_SESSION.md",
        repo_root / "v11.0.0" / "README.md",
    ]
    if docs_root.is_dir():
        for p in sorted(docs_root.rglob("*.md")):
            if "popular" in p.parts:
                continue
            out.append(p)
    return [p for p in out if p.is_file()]


def _find_tokens(line: str, pattern: re.Pattern[str]) -> Iterable[str]:
    for m in pattern.finditer(line):
        tok = m.group(0)
        if tok:
            yield tok


def _line_is_exception(text: str) -> bool:
    low = text.lower()
    return any(k in low for k in _ALLOW_CONTEXT)


def run_lint(repo_root: Path, catalog_path: Path) -> List[LintIssue]:
    catalog = verify_all.load_catalog(catalog_path)
    artifacts = catalog.get("artifacts")
    if not isinstance(artifacts, dict):
        raise verify_all.CatalogError("catalog.artifacts must be an object")

    expected = {
        "late_tag": str(artifacts["late_time"]["tag"]),
        "submission_tag": str(artifacts["submission"]["tag"]),
        "referee_tag": str(artifacts["referee_pack"]["tag"]),
        "toe_tag": str(artifacts["toe_bundle"]["tag"]),
        "late_asset": str(artifacts["late_time"]["asset"]),
        "submission_asset": str(artifacts["submission"]["asset"]),
        "referee_asset": str(artifacts["referee_pack"]["asset"]),
        "toe_asset": str(artifacts["toe_bundle"]["asset"]),
        "late_sha": str(artifacts["late_time"]["sha256"]).lower(),
        "submission_sha": str(artifacts["submission"]["sha256"]).lower(),
        "referee_sha": str(artifacts["referee_pack"]["sha256"]).lower(),
        "toe_sha": str(artifacts["toe_bundle"]["sha256"]).lower(),
    }

    patterns = {
        "late_tag": re.compile(r"\bv10\.1\.1-late-time-r\d+\b"),
        "submission_tag": re.compile(r"\bv10\.1\.1-submission-r\d+\b"),
        "referee_tag": re.compile(r"\bv10\.1\.1-referee-pack-r\d+\b"),
        "toe_tag": re.compile(r"\bv10\.1\.1-toe-track-r\d+\b"),
        "late_asset": re.compile(r"\bpaper_assets_v10\.1\.1-late-time-r\d+\.zip\b"),
        "submission_asset": re.compile(r"\bsubmission_bundle_v10\.1\.1-late-time-r\d+\.zip\b"),
        "referee_asset": re.compile(r"\breferee_pack_v10\.1\.1-late-time-r\d+(?:-r\d+)?\.zip\b"),
        "toe_asset": re.compile(r"\btoe_bundle_v10\.1\.1-r\d+\.zip\b"),
    }

    expected_tokens = set(expected.values())
    observed_expected: set[str] = set()
    issues: List[LintIssue] = []

    for fp in _scan_files(repo_root):
        text = fp.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        for idx, line in enumerate(lines):
            lineno = idx + 1
            prev2_line = lines[idx - 2] if idx > 1 else ""
            prev_line = lines[idx - 1] if idx > 0 else ""
            next_line = lines[idx + 1] if idx + 1 < len(lines) else ""
            context = "\n".join((prev2_line, prev_line, line, next_line))

            for key, pat in patterns.items():
                for tok in _find_tokens(line, pat):
                    if tok == expected[key]:
                        observed_expected.add(tok)
                        continue
                    if _line_is_exception(context):
                        continue
                    issues.append(
                        LintIssue(
                            file=fp,
                            line=lineno,
                            found=tok,
                            expected=expected[key],
                            reason=f"{key} mismatch",
                        )
                    )

            for tok in re.findall(r"\b[0-9a-f]{64}\b", line.lower()):
                if _HEX64.match(tok) is None:
                    continue
                if _CANONICAL_CONTEXT_RE.search(context) is None:
                    continue
                if tok in expected_tokens:
                    observed_expected.add(tok)
                    continue
                if _line_is_exception(context):
                    continue
                if "sha256" in line.lower():
                    issues.append(
                        LintIssue(
                            file=fp,
                            line=lineno,
                            found=tok,
                            expected="<canonical sha from SoT>",
                            reason="sha256 token not present in canonical_artifacts.json",
                        )
                    )

    # Ensure canonical tokens are actually present in docs.
    required_presence = [
        expected["late_tag"],
        expected["submission_tag"],
        expected["referee_tag"],
        expected["toe_tag"],
        expected["late_asset"],
        expected["submission_asset"],
        expected["referee_asset"],
        expected["toe_asset"],
        expected["late_sha"],
        expected["submission_sha"],
        expected["referee_sha"],
        expected["toe_sha"],
    ]
    for tok in required_presence:
        if tok not in observed_expected:
            issues.append(
                LintIssue(
                    file=repo_root / "v11.0.0" / "docs" / "status_canonical_artifacts.md",
                    line=1,
                    found="<missing>",
                    expected=tok,
                    reason="canonical token not found in scanned pointers",
                )
            )

    return issues


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="pointer_sot_lint",
        description="Lint canonical pointer tags/assets/SHA in docs against canonical_artifacts.json",
    )
    ap.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    ap.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    args = ap.parse_args(argv)

    repo_root = args.repo_root.expanduser().resolve()
    catalog = args.catalog.expanduser().resolve()

    try:
        issues = run_lint(repo_root, catalog)
    except verify_all.CatalogError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if issues:
        print("ERROR: pointer SoT lint failed")
        for it in issues:
            rel = it.file.relative_to(repo_root) if it.file.is_absolute() else it.file
            print(
                f"  - {rel}:{it.line}: {it.reason}; expected={it.expected!r}; found={it.found!r}",
                file=sys.stderr,
            )
        return 2

    print("OK: pointer SoT lint passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

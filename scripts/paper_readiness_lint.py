#!/usr/bin/env python3
"""Paper-readiness lint for reviewer-facing narrative guardrails (pattern-based)."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence


V101_DIR = Path(__file__).resolve().parents[1]
DEFAULT_TEX = V101_DIR / "GSC_Framework_v10_1_FINAL.tex"
DEFAULT_MD = V101_DIR / "GSC_Framework_v10_1_FINAL.md"


@dataclass
class CheckResult:
    key: str
    ok: bool
    message: str


def _has_all(text: str, patterns: Sequence[str]) -> bool:
    for p in patterns:
        if re.search(p, text, flags=re.IGNORECASE | re.MULTILINE) is None:
            return False
    return True


def _explicit_diagnostic_context(line: str) -> bool:
    return bool(
        re.search(
            r"checkpoint|out[- ]of[- ]scope|companion|table|appendix|summary|caption|path|numbers|strict",
            line,
            flags=re.IGNORECASE,
        )
    )


def run_lint(tex_path: Path, md_path: Path | None = None, profile: str = "repo") -> List[CheckResult]:
    text = tex_path.read_text(encoding="utf-8", errors="replace")
    md_text = ""
    if md_path is not None and md_path.is_file():
        md_text = md_path.read_text(encoding="utf-8", errors="replace")

    checks = [
        (
            "scope_claims_kill_box",
            [
                r"\\textbf\{Scope \(v11\.0\.0\)\}",
                r"\\textbf\{Primary falsifier / kill test\}",
            ],
            "Scope/claims/kill-tests box missing or incomplete",
        ),
        (
            "drift_sign_condition",
            [
                r"\\dot z\s*>\s*0",
                r"H\(z\)\s*<\s*H_0\(1\+z\)",
            ],
            "Drift sign condition line missing (dot z > 0 <=> H(z) < H0(1+z))",
        ),
        (
            "universality_epsilon_baseline",
            [
                r"Parameterized departures from universality",
                r"\\epsilon_\{\\rm EM\}\s*=\s*\\epsilon_\{\\rm QCD\}\s*=\s*0",
            ],
            "Universality epsilon risk model/baseline statement missing",
        ),
        (
            "not_tired_light_classic_tests",
            [
                r"not a tired-?light mechanism|not tired light",
                r"time dilation",
                r"Tolman",
            ],
            "Not-tired-light + classic tests wording missing",
        ),
        (
            "early_time_out_of_scope_with_referee_pointer",
            [
                r"late-time only",
                r"referee pack includes",
                r"Early-time/CMB closure checkpoint",
            ],
            "Early-time out-of-scope + referee-pack pointer missing",
        ),
        (
            "no_popular_or_diagnostic_asset_references_in_tex",
            [
                r"^(?!.*docs/popular/)(?!.*results/diagnostic_)(?!.*paper_assets_.*diagnostic).*$",
            ],
            "TeX references docs/popular or diagnostic result/assets paths",
        ),
    ]
    if profile == "submission":
        checks = [c for c in checks if c[0] != "early_time_out_of_scope_with_referee_pointer"]

    out: List[CheckResult] = []
    for key, pats, fail_msg in checks:
        if key == "no_popular_or_diagnostic_asset_references_in_tex":
            ok = (
                re.search(r"docs/popular/", text, flags=re.IGNORECASE) is None
                and re.search(r"results/diagnostic_", text, flags=re.IGNORECASE) is None
                and re.search(r"paper_assets_.*diagnostic", text, flags=re.IGNORECASE) is None
            )
        else:
            ok = _has_all(text, pats)
        out.append(CheckResult(key=key, ok=ok, message=("OK" if ok else fail_msg)))

    if md_text:
        ok_md_refs = (
            re.search(r"docs/popular/", md_text, flags=re.IGNORECASE) is None
            and re.search(r"results/diagnostic_", md_text, flags=re.IGNORECASE) is None
            and re.search(r"paper_assets_.*diagnostic", md_text, flags=re.IGNORECASE) is None
        )
        out.append(
            CheckResult(
                key="no_popular_or_diagnostic_asset_references_in_md",
                ok=ok_md_refs,
                message=("OK" if ok_md_refs else "MD references docs/popular or diagnostic result/assets paths"),
            )
        )

    banned = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if re.search(r"\bTODO\b|\bTBD\b", line, flags=re.IGNORECASE):
            banned.append(f"line {lineno}: unresolved marker {line.strip()}")
            continue
        if re.search(r"\bdraft\b", line, flags=re.IGNORECASE) and re.search(
            r"v10 draft is written to be compatible", line, flags=re.IGNORECASE
        ) is None:
            banned.append(f"line {lineno}: ambiguous draft wording {line.strip()}")
            continue
        if re.search(r"diagnostic-only", line, flags=re.IGNORECASE) and not _explicit_diagnostic_context(line):
            banned.append(f"line {lineno}: diagnostic-only without explicit context {line.strip()}")

    out.append(
        CheckResult(
            key="no_unresolved_draft_markers",
            ok=(len(banned) == 0),
            message=("OK" if not banned else "; ".join(banned[:4])),
        )
    )

    return out


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="paper_readiness_lint", description="Pattern lint for reviewer-facing paper readiness markers")
    ap.add_argument("--tex", type=Path, default=DEFAULT_TEX)
    ap.add_argument("--md", type=Path, default=DEFAULT_MD)
    ap.add_argument("--skip-md-check", action="store_true")
    ap.add_argument("--profile", choices=("repo", "submission"), default="repo")
    args = ap.parse_args(argv)

    tex = args.tex.expanduser().resolve()
    if not tex.is_file():
        print(f"ERROR: TeX file not found: {tex}")
        return 2
    md: Path | None = None
    if not args.skip_md_check:
        md = args.md.expanduser().resolve()
        if not md.is_file():
            print(f"ERROR: MD mirror file not found: {md}")
            return 2

    results = run_lint(tex, md_path=md, profile=args.profile)
    failed = [r for r in results if not r.ok]

    print(f"paper readiness lint: {tex}")
    print(f"  profile: {args.profile}")
    if md is not None:
        print(f"  md mirror: {md}")
    for r in results:
        status = "OK" if r.ok else "FAIL"
        print(f"  [{status}] {r.key}: {r.message}")

    if failed:
        print(f"ERROR: {len(failed)} readiness checks failed")
        return 2

    print("OK: paper readiness lint passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

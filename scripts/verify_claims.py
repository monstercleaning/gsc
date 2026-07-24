#!/usr/bin/env python3
"""verify_claims.py — bind prose claims to executable facts about the artifact.

Motivation
----------
This repository already ships a claims linter (`docs_claims_lint.py`). It can
express exactly two things: "this phrase must not appear" (BANNED_RULES) and
"this phrase must appear" (REQUIRED_RULES). Both are pure text checks. Neither
can ask whether a sentence is *true*.

That gap is not hypothetical. For twelve build cycles this project's headline
methodological claim — that its predictions were "cryptographically signed and
time-stamped before the corresponding observational data are released" — was
false: every register entry was an unsigned scaffold. A phrase linter cannot
catch that; it would happily *require* the sentence. What eventually caught it
was one mechanical check nobody had run: `grep SCAFFOLD`.

This tool generalizes that check. Each load-bearing claim in `CLAIMS.json` is
paired with a machine-checkable predicate over the repository's actual state.
The dangerous case it exists to catch is ASSERTED + UNBACKED: the docs say it,
the artifact does not do it.

Design notes (honest about what is exact and what is heuristic)
--------------------------------------------------------------
* The **verification** side is exact and mechanical: file counts, front-matter
  field values, hash comparisons, schema resolution, subprocess exit codes.
* The **detection** side ("is this claim actually being asserted?") is
  heuristic when it relies on regex, because prose varies and legitimate
  mentions exist (a changelog documenting a retraction, a paper quoting its own
  corrected wording). Each claim therefore carries an explicit, auditable
  `unless` list of hedge patterns. Curating a hedge list is far cheaper, and far
  more reviewable, than remembering to check reality by hand.
* For claims where exactness matters more than convenience, prefer an explicit
  HTML-comment anchor in the prose (`<!-- claim:some-id -->`) and set
  `"detect": {"anchor": "some-id"}`. Anchors are exact.

Stdlib only. Python 3.9+.

Usage
-----
    python3 scripts/verify_claims.py                    # verify current tree
    python3 scripts/verify_claims.py --root /path/to/tree
    python3 scripts/verify_claims.py --format json
    python3 scripts/verify_claims.py --include-slow     # also run subprocess facts
    python3 scripts/verify_claims.py --explain          # show every claim's reasoning

Exit codes: 0 = no unbacked claims; 1 = at least one unbacked claim; 2 = config error.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

SCHEMA = "claim_verification_v1"

# Values that mean "this front-matter field is unfilled".
EMPTY_MARKERS = {"", "-", "—", "–", "none", "n/a", "na", "tbd", "todo", "pending", "?"}

NUMBER_WORDS: Dict[str, int] = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
}

# Verdict constants.
OK_BACKED = "OK_BACKED"                # asserted and reality agrees
UNBACKED = "UNBACKED"                  # asserted and reality DISAGREES  <-- the dangerous case
OK_NOT_ASSERTED = "OK_NOT_ASSERTED"    # claim not made anywhere; nothing to check
SKIPPED_SLOW = "SKIPPED_SLOW"          # subprocess fact, not requested
CONFIG_ERROR = "CONFIG_ERROR"


@dataclass
class Result:
    claim_id: str
    claim: str
    verdict: str
    detail: str = ""
    sites: List[str] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return self.verdict in (UNBACKED, CONFIG_ERROR)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _iter_paths(root: Path, globs: Sequence[str], exclude: Sequence[str] = (),
                want: str = "file") -> List[Path]:
    """Collect files (want='file') or directories (want='dir') matching globs."""
    seen: Dict[Path, None] = {}
    for pattern in globs:
        for p in sorted(root.glob(pattern)):
            if want == "file" and not p.is_file():
                continue
            if want == "dir" and not p.is_dir():
                continue
            rel = p.relative_to(root).as_posix()
            if any(re.search(x, rel) for x in exclude):
                continue
            seen.setdefault(p, None)
    return list(seen)


def _iter_files(root: Path, globs: Sequence[str], exclude: Sequence[str] = ()) -> List[Path]:
    return _iter_paths(root, globs, exclude, want="file")


def _count_target(root: Path, spec: Dict[str, Any]) -> int:
    """Count the artifact-side quantity a claim is measured against.

    Accepts `count_globs` (files) and/or `count_dir_globs` (directories) so a
    claim like "five papers" can count directories rather than a file that only
    some of them happen to have.
    """
    n = 0
    if spec.get("count_globs"):
        n += len(_iter_paths(root, spec["count_globs"], spec.get("count_exclude", []), "file"))
    if spec.get("count_dir_globs"):
        n += len(_iter_paths(root, spec["count_dir_globs"], spec.get("count_exclude", []), "dir"))
    return n


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _front_matter(text: str) -> Dict[str, str]:
    """Parse a leading '---' YAML-ish block into flat key -> value strings."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", text, re.DOTALL)
    if not m:
        return {}
    out: Dict[str, str] = {}
    for line in m.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        out[key.strip()] = val.strip().strip('"').strip("'")
    return out


def _is_empty_marker(value: str) -> bool:
    return value.strip().lower() in EMPTY_MARKERS


def _word_to_int(token: str) -> Optional[int]:
    t = token.strip().lower().replace(",", "")
    if t.isdigit():
        return int(t)
    return NUMBER_WORDS.get(t)


# --------------------------------------------------------------------------
# detection: is the claim being asserted in the prose?
# --------------------------------------------------------------------------

def detect_assertions(root: Path, detect: Dict[str, Any]) -> List[str]:
    """Return human-readable 'file:line' sites where the claim appears to be asserted."""
    globs = detect.get("globs", ["**/*.md"])
    exclude = detect.get("exclude", [])
    sites: List[str] = []

    anchor = detect.get("anchor")
    if anchor:
        needle = "claim:%s" % anchor
        for p in _iter_files(root, globs, exclude):
            for i, line in enumerate(_read(p).splitlines(), 1):
                if needle in line:
                    sites.append("%s:%d" % (p.relative_to(root).as_posix(), i))
        return sites

    pattern = detect.get("pattern")
    if not pattern:
        return sites
    rx = re.compile(pattern, re.IGNORECASE)
    unless = [re.compile(u, re.IGNORECASE) for u in detect.get("unless", [])]
    for p in _iter_files(root, globs, exclude):
        for i, line in enumerate(_read(p).splitlines(), 1):
            if not rx.search(line):
                continue
            if any(u.search(line) for u in unless):
                continue  # hedged / historical / self-correcting mention
            sites.append("%s:%d" % (p.relative_to(root).as_posix(), i))
    return sites


# --------------------------------------------------------------------------
# verification primitives: does the artifact actually back the claim?
# each returns (backed: bool, detail: str)
# --------------------------------------------------------------------------

def _v_frontmatter_field_nonempty(root: Path, spec: Dict[str, Any]) -> Tuple[bool, str]:
    files = _iter_files(root, spec["globs"], spec.get("exclude", []))
    fields = spec["fields"] if "fields" in spec else [spec["field"]]
    min_count = int(spec.get("min_count", 1))
    filled: List[str] = []
    for p in files:
        fm = _front_matter(_read(p))
        for f in fields:
            val = fm.get(f, "")
            if val and not _is_empty_marker(val):
                filled.append("%s[%s=%s]" % (p.relative_to(root).as_posix(), f, val[:24]))
                break
    ok = len(filled) >= min_count
    detail = "%d/%d file(s) have a non-empty %s (need >= %d)" % (
        len(filled), len(files), "/".join(fields), min_count)
    if filled:
        detail += "; e.g. " + filled[0]
    return ok, detail


def _v_path_count(root: Path, spec: Dict[str, Any]) -> Tuple[bool, str]:
    n = len(_iter_paths(root, spec["globs"], spec.get("exclude", []),
                        want=spec.get("want", "file")))
    if "equals" in spec:
        return n == int(spec["equals"]), "found %d, expected %d" % (n, int(spec["equals"]))
    lo = int(spec.get("min", 0))
    hi = int(spec.get("max", 10 ** 9))
    return lo <= n <= hi, "found %d, allowed [%d, %s]" % (n, lo, hi if hi < 10 ** 9 else "inf")


def _v_number_agreement(root: Path, spec: Dict[str, Any]) -> Tuple[bool, str]:
    """A number stated in prose must equal a number counted from the artifact.

    mode='each' (default): every stated number must equal the count.
    mode='max':  only the largest stated number must equal the count — for
                 enumerations (e.g. section headings P1..P10) where individual
                 values are indices, not totals.
    """
    counted = _count_target(root, spec)
    mode = spec.get("mode", "each")
    rx = re.compile(spec["pattern"], re.IGNORECASE)
    unless = [re.compile(u, re.IGNORECASE) for u in spec.get("unless", [])]
    mismatches: List[str] = []
    found: List[Tuple[str, int]] = []
    for p in _iter_files(root, spec.get("globs", ["**/*.md"]), spec.get("exclude", [])):
        for i, line in enumerate(_read(p).splitlines(), 1):
            m = rx.search(line)
            if not m:
                continue
            if any(u.search(line) for u in unless):
                continue
            stated = _word_to_int(m.group(1))
            if stated is None:
                continue
            site = "%s:%d" % (p.relative_to(root).as_posix(), i)
            found.append((site, stated))
            if mode == "each" and stated != counted:
                mismatches.append("%s says %d" % (site, stated))
    if not found:
        return True, "no prose statement of this count found; artifact has %d" % counted
    if mode == "max":
        best_site, best = max(found, key=lambda t: t[1])
        if best != counted:
            return False, ("artifact has %d but the highest enumerated value is %d (%s)"
                           % (counted, best, best_site))
        return True, "highest enumerated value %d matches the counted %d (%d site(s))" % (
            best, counted, len(found))
    if mismatches:
        return False, "artifact has %d but %d site(s) disagree: %s" % (
            counted, len(mismatches), "; ".join(mismatches[:6]))
    return True, "all %d prose site(s) agree with the counted %d" % (len(found), counted)


def _v_sibling_hash_match(root: Path, spec: Dict[str, Any]) -> Tuple[bool, str]:
    """Every recorded hash in `record` must equal the sha256 of its sibling `target`."""
    import hashlib
    records = _iter_files(root, spec["record_globs"], spec.get("exclude", []))
    target_name = spec["target_name"]
    rx = re.compile(spec.get("hash_pattern", r"\b([0-9a-f]{64})\b"))
    checked = 0
    bad: List[str] = []
    for rec in records:
        m = rx.search(_read(rec))
        if not m:
            continue
        target = rec.parent / target_name
        if not target.is_file():
            bad.append("%s: no sibling %s" % (rec.relative_to(root).as_posix(), target_name))
            continue
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        checked += 1
        if actual != m.group(1):
            bad.append("%s: recorded %s… != actual %s…" % (
                rec.relative_to(root).as_posix(), m.group(1)[:12], actual[:12]))
    if bad:
        return False, "%d/%d mismatched: %s" % (len(bad), checked or len(records), "; ".join(bad[:4]))
    return True, "%d recorded hash(es) match their artifact" % checked


def _v_json_field_resolves(root: Path, spec: Dict[str, Any]) -> Tuple[bool, str]:
    """A JSON field must name a file that exists (e.g. schema -> schemas/<name>.schema.json)."""
    files = _iter_files(root, spec["globs"], spec.get("exclude", []))
    template = spec["resolves_to"]
    field_name = spec["field"]
    missing: List[str] = []
    ok_n = 0
    for p in files:
        try:
            data = json.loads(_read(p))
        except json.JSONDecodeError as exc:
            missing.append("%s: invalid JSON (%s)" % (p.relative_to(root).as_posix(), exc.msg))
            continue
        val = data.get(field_name)
        if not val:
            missing.append("%s: no '%s' field" % (p.relative_to(root).as_posix(), field_name))
            continue
        target = root / template.replace("{value}", str(val))
        if target.is_file():
            ok_n += 1
        else:
            missing.append("%s: '%s' -> missing %s" % (
                p.relative_to(root).as_posix(), val, target.relative_to(root).as_posix()))
    if missing:
        return False, "%d unresolved: %s" % (len(missing), "; ".join(missing[:4]))
    return True, "all %d '%s' value(s) resolve to real files" % (ok_n, field_name)


def _v_file_regex_count(root: Path, spec: Dict[str, Any]) -> Tuple[bool, str]:
    rx = re.compile(spec["pattern"], re.IGNORECASE if spec.get("ignore_case", True) else 0)
    unless = [re.compile(u, re.IGNORECASE) for u in spec.get("unless", [])]
    hits: List[str] = []
    for p in _iter_files(root, spec["globs"], spec.get("exclude", [])):
        for i, line in enumerate(_read(p).splitlines(), 1):
            if rx.search(line) and not any(u.search(line) for u in unless):
                hits.append("%s:%d" % (p.relative_to(root).as_posix(), i))
    lo = int(spec.get("min", 0))
    hi = int(spec.get("max", 10 ** 9))
    ok = lo <= len(hits) <= hi
    detail = "%d match(es), allowed [%d, %s]" % (len(hits), lo, hi if hi < 10 ** 9 else "inf")
    if hits and not ok:
        detail += "; e.g. " + ", ".join(hits[:4])
    return ok, detail


def _v_command_exit_zero(root: Path, spec: Dict[str, Any]) -> Tuple[bool, str]:
    cmd = spec["cmd"]
    try:
        proc = subprocess.run(cmd, cwd=str(root), stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=int(spec.get("timeout", 600)))
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, "command failed to run: %s" % exc
    tail = proc.stdout.decode("utf-8", "replace").strip().splitlines()[-1:] or [""]
    return proc.returncode == 0, "exit=%d; last line: %s" % (proc.returncode, tail[0][:120])


VERIFIERS = {
    "frontmatter_field_nonempty": _v_frontmatter_field_nonempty,
    "path_count": _v_path_count,
    "number_agreement": _v_number_agreement,
    "sibling_hash_match": _v_sibling_hash_match,
    "json_field_resolves": _v_json_field_resolves,
    "file_regex_count": _v_file_regex_count,
    "command_exit_zero": _v_command_exit_zero,
}

SLOW_VERIFIERS = {"command_exit_zero"}


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------

def evaluate(root: Path, claims: Sequence[Dict[str, Any]], include_slow: bool) -> List[Result]:
    results: List[Result] = []
    for c in claims:
        cid = c.get("id", "<no-id>")
        prose = c.get("claim", "")
        verify = c.get("verify") or {}
        vtype = verify.get("type")
        if vtype not in VERIFIERS:
            results.append(Result(cid, prose, CONFIG_ERROR,
                                  "unknown verify type %r" % vtype))
            continue

        detect = c.get("detect")
        # `always: true` claims are invariants: checked whether or not prose asserts them.
        always = bool(c.get("always"))
        sites = detect_assertions(root, detect) if detect else []
        if not always and detect and not sites:
            results.append(Result(cid, prose, OK_NOT_ASSERTED,
                                  "claim not asserted in prose; nothing to verify"))
            continue

        if vtype in SLOW_VERIFIERS and not include_slow:
            results.append(Result(cid, prose, SKIPPED_SLOW,
                                  "subprocess fact; re-run with --include-slow", sites))
            continue

        try:
            backed, detail = VERIFIERS[vtype](root, verify)
        except (KeyError, OSError, re.error) as exc:
            results.append(Result(cid, prose, CONFIG_ERROR,
                                  "%s: %s" % (type(exc).__name__, exc), sites))
            continue

        results.append(Result(cid, prose, OK_BACKED if backed else UNBACKED, detail, sites))
    return results


def render_text(results: Sequence[Result], explain: bool) -> str:
    glyph = {OK_BACKED: "ok  ", UNBACKED: "FAIL", OK_NOT_ASSERTED: "--  ",
             SKIPPED_SLOW: "skip", CONFIG_ERROR: "ERR "}
    lines = ["claim verification (prose <-> artifact)", "=" * 52]
    for r in results:
        if not explain and r.verdict in (OK_NOT_ASSERTED, SKIPPED_SLOW):
            continue
        lines.append("[%s] %s" % (glyph.get(r.verdict, "?"), r.claim_id))
        if explain or r.failed:
            lines.append("        claim: %s" % r.claim)
            lines.append("        fact:  %s" % r.detail)
            if r.sites:
                shown = ", ".join(r.sites[:4])
                more = "" if len(r.sites) <= 4 else " (+%d more)" % (len(r.sites) - 4)
                lines.append("        cited: %s%s" % (shown, more))
    failed = [r for r in results if r.failed]
    lines.append("=" * 52)
    if failed:
        lines.append("UNBACKED CLAIMS: %d — the docs assert what the artifact does not do."
                     % len(failed))
        for r in failed:
            lines.append("  - %s" % r.claim_id)
    else:
        checked = sum(1 for r in results if r.verdict == OK_BACKED)
        lines.append("All %d asserted claim(s) are backed by the artifact." % checked)
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    here = Path(__file__).resolve().parents[1]
    ap.add_argument("--root", default=str(here), help="tree to verify (default: this package)")
    ap.add_argument("--claims", default=None, help="claims manifest (default: <root>/CLAIMS.json)")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    ap.add_argument("--include-slow", action="store_true", help="also run subprocess facts")
    ap.add_argument("--explain", action="store_true", help="show every claim, including skips")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    manifest = Path(args.claims) if args.claims else root / "CLAIMS.json"
    if not manifest.is_file():
        # Allow verifying an old tree with the current manifest.
        fallback = here / "CLAIMS.json"
        if fallback.is_file():
            manifest = fallback
        else:
            sys.stderr.write("error: no claims manifest at %s\n" % manifest)
            return 2
    try:
        doc = json.loads(manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.stderr.write("error: %s is not valid JSON: %s\n" % (manifest, exc))
        return 2
    if doc.get("schema") != SCHEMA:
        sys.stderr.write("error: expected schema %r, got %r\n" % (SCHEMA, doc.get("schema")))
        return 2

    results = evaluate(root, doc.get("claims", []), args.include_slow)

    if args.format == "json":
        print(json.dumps({
            "root": str(root),
            "manifest": str(manifest),
            "results": [
                {"id": r.claim_id, "claim": r.claim, "verdict": r.verdict,
                 "detail": r.detail, "sites": r.sites}
                for r in results
            ],
            "unbacked": [r.claim_id for r in results if r.failed],
        }, indent=2))
    else:
        print(render_text(results, args.explain))

    return 1 if any(r.failed for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())

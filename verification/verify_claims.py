#!/usr/bin/env python3
"""verify_claims.py — bind prose claims to executable facts about the artifact.

Motivation
----------
Earlier releases of this project shipped a claims linter (not carried into this
package). It could express exactly two things: "this phrase must not appear" and
"this phrase must appear". Both are pure text checks. Neither can ask whether a
sentence is *true*.

That gap is not hypothetical. For twelve build cycles this project's headline
methodological claim — that its predictions were "cryptographically signed and
time-stamped before the corresponding observational data are released" — was
false: every register entry was an unsigned scaffold. A phrase linter cannot
catch that; it would happily *require* the sentence. What eventually caught it
was one mechanical check nobody had run: `grep SCAFFOLD`.

This tool generalizes that check. Each load-bearing claim in `verification/claims.json` is
paired with a machine-checkable predicate over the repository's actual state.
The dangerous case it exists to catch is ASSERTED + UNBACKED: the docs say it,
the artifact does not do it.

Design notes (honest about what is exact and what is heuristic)
--------------------------------------------------------------
* The **verification** side is exact and mechanical: file counts, front-matter
  field values, hash comparisons, JSON-schema validation, subprocess exit codes.
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
    python3 verification/verify_claims.py                    # verify current tree
    python3 verification/verify_claims.py --root /path/to/tree
    python3 verification/verify_claims.py --format json
    python3 verification/verify_claims.py --include-slow     # also run subprocess facts
    python3 verification/verify_claims.py --explain          # show every claim's reasoning

Exit codes: 0 = no unbacked claims; 1 = at least one unbacked claim; 2 = config error.
"""

from __future__ import annotations

import argparse
import hashlib
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
            # A pattern may offer alternative phrasings, each with its own capture
            # group; the stated number is whichever group matched.
            token = next((g for g in m.groups() if g is not None), None)
            stated = _word_to_int(token) if token is not None else None
            if stated is None:
                continue
            site = "%s:%d" % (p.relative_to(root).as_posix(), i)
            found.append((site, stated))
            if mode == "each" and stated != counted:
                mismatches.append("%s says %d" % (site, stated))
    if not found:
        # Liveness floor: a count claim that matches zero prose sites
        # verifies nothing. It passed vacuously for two months after the register
        # reached thirteen because the number-word alternation stopped at twelve.
        min_sites = int(spec.get("min_sites", 0))
        if min_sites > 0:
            return False, ("no prose statement of this count found (artifact has %d); "
                           "liveness floor min_sites=%d — zero matched sites is a dead check, "
                           "not a pass (pattern/alternation probably lags the prose)"
                           % (counted, min_sites))
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


# JSON Schema validation, standard library only. It implements the draft-07
# keywords this package's schemas use. Any other validation keyword is reported
# as an error rather than skipped: a validator that ignores what it does not
# understand passes anything, which is the failure this tool exists to prevent.
_SCHEMA_ANNOTATIONS = frozenset({"$schema", "$id", "$comment", "title", "description",
                                 "default", "examples"})
_SCHEMA_KEYWORDS = frozenset({"type", "enum", "const", "required", "properties",
                              "additionalProperties", "items", "minItems", "maxItems",
                              "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
                              "pattern", "minLength", "maxLength"})
_JSON_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "integer": lambda v: ((isinstance(v, int) and not isinstance(v, bool))
                          or (isinstance(v, float) and v.is_integer())),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}
_NUMERIC_BOUNDS = (
    ("minimum", lambda x, b: x < b),
    ("maximum", lambda x, b: x > b),
    ("exclusiveMinimum", lambda x, b: x <= b),
    ("exclusiveMaximum", lambda x, b: x >= b),
)


def _is_json_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _json_equal(a: Any, b: Any) -> bool:
    """Equality as JSON defines it: 1 equals 1.0, but true does not equal 1."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if _is_json_number(a) and _is_json_number(b):
        return a == b
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_json_equal(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_json_equal(x, y) for x, y in zip(a, b))
    return type(a) is type(b) and a == b


def schema_errors(data: Any, schema: Any, path: str = "$") -> List[str]:
    """Return every violation of `schema` by `data` (an empty list means valid)."""
    errors: List[str] = []
    _schema_check(data, schema, path, errors)
    return errors


def _schema_check(data: Any, schema: Any, path: str, errors: List[str]) -> None:
    if schema is True:
        return
    if schema is False:
        errors.append("%s: no value is allowed here" % path)
        return
    if not isinstance(schema, dict):
        errors.append("%s: schema node is not an object" % path)
        return
    unknown = sorted(set(schema) - _SCHEMA_KEYWORDS - _SCHEMA_ANNOTATIONS)
    if unknown:
        errors.append("%s: unsupported schema keyword(s) %s" % (path, ", ".join(unknown)))
        return
    if "type" in schema:
        names = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        unsupported = [n for n in names if n not in _JSON_TYPES]
        if unsupported:
            errors.append("%s: unsupported type name(s) %s" % (path, unsupported))
            return
        if not any(_JSON_TYPES[n](data) for n in names):
            errors.append("%s: expected %s, got %s" % (path, "/".join(names), type(data).__name__))
            return
    if "const" in schema and not _json_equal(data, schema["const"]):
        errors.append("%s: expected %r, got %r" % (path, schema["const"], data))
    if "enum" in schema and not any(_json_equal(data, v) for v in schema["enum"]):
        errors.append("%s: %r is not one of %r" % (path, data, schema["enum"]))
    for key, violates in _NUMERIC_BOUNDS:
        if key not in schema:
            continue
        if not _is_json_number(schema[key]):
            errors.append("%s: %s must be a number in draft-07" % (path, key))
        elif _is_json_number(data) and violates(data, schema[key]):
            errors.append("%s: %r violates %s %r" % (path, data, key, schema[key]))
    if isinstance(data, str):
        if "pattern" in schema and not re.search(schema["pattern"], data):
            errors.append("%s: %r does not match /%s/" % (path, data, schema["pattern"]))
        if "minLength" in schema and len(data) < schema["minLength"]:
            errors.append("%s: shorter than minLength %d" % (path, schema["minLength"]))
        if "maxLength" in schema and len(data) > schema["maxLength"]:
            errors.append("%s: longer than maxLength %d" % (path, schema["maxLength"]))
    if isinstance(data, list):
        if "minItems" in schema and len(data) < schema["minItems"]:
            errors.append("%s: %d item(s), minItems %d" % (path, len(data), schema["minItems"]))
        if "maxItems" in schema and len(data) > schema["maxItems"]:
            errors.append("%s: %d item(s), maxItems %d" % (path, len(data), schema["maxItems"]))
        if "items" in schema:
            if isinstance(schema["items"], list):
                errors.append("%s: tuple-form 'items' is not supported" % path)
            else:
                for i, item in enumerate(data):
                    _schema_check(item, schema["items"], "%s[%d]" % (path, i), errors)
    if isinstance(data, dict):
        for key in schema.get("required", []):
            if key not in data:
                errors.append("%s: missing required key %r" % (path, key))
        properties = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        for key in sorted(data):
            _schema_check(data[key], properties.get(key, extra), "%s.%s" % (path, key), errors)


def _v_json_schema_valid(root: Path, spec: Dict[str, Any]) -> Tuple[bool, str]:
    """Every matching JSON file must name a schema that exists, and validate against it."""
    files = _iter_files(root, spec["globs"], spec.get("exclude", []))
    template = spec.get("resolves_to", "schemas/{value}.schema.json")
    field_name = spec.get("field", "schema")
    problems: List[str] = []
    valid = 0
    for p in files:
        rel = p.relative_to(root).as_posix()
        try:
            data = json.loads(_read(p))
        except json.JSONDecodeError as exc:
            problems.append("%s: invalid JSON (%s)" % (rel, exc.msg))
            continue
        name = data.get(field_name) if isinstance(data, dict) else None
        if not name:
            problems.append("%s: no '%s' field" % (rel, field_name))
            continue
        schema_path = root / template.replace("{value}", str(name))
        if not schema_path.is_file():
            problems.append("%s: '%s' names a missing schema" % (rel, name))
            continue
        try:
            schema = json.loads(_read(schema_path))
        except json.JSONDecodeError as exc:
            problems.append("%s: schema %s is invalid JSON (%s)" % (rel, name, exc.msg))
            continue
        errs = schema_errors(data, schema)
        if errs:
            problems.append("%s: %d violation(s), first: %s" % (rel, len(errs), errs[0]))
        else:
            valid += 1
    if problems:
        return False, "%d of %d file(s) fail: %s" % (len(problems), len(files), "; ".join(problems[:3]))
    min_checked = int(spec.get("min_checked", 1))
    if valid < min_checked:
        return False, ("only %d file(s) validated (floor %d): the glob is not seeing the outputs"
                       % (valid, min_checked))
    return True, "all %d file(s) validate against the JSON schema they name" % valid


_VERDICT_WORD = re.compile(r"\b(PASS|FAIL|SUB-THRESHOLD)(?:ES|ED|S)?\b")
_PREDICTION_ID = re.compile(r"\bP0*(\d{1,2})\b")
_VERDICT_BOUNDARY = re.compile(r"[.;(|]\s|[;(]")
_VERDICT_TARGET_AFTER = re.compile(r"^\s+(?:on|for|in)\s+P0*(\d{1,2})\b")


def stated_verdicts(line: str) -> List[Tuple[int, str]]:
    """(prediction number, verdict) pairs that a line of prose states.

    A verdict word applies to every prediction ID between it and the previous
    clause boundary or verdict word ("P1, P3 FAIL; P5 PASS"), and to an ID that
    directly follows it ("a FAIL on P4"). Verdict words are matched in capitals
    only, which is how the documents state verdicts.
    """
    out: List[Tuple[int, str]] = []
    last = 0
    for v in _VERDICT_WORD.finditer(line):
        segment = line[last:v.start()]
        cut = max((m.end() for m in _VERDICT_BOUNDARY.finditer(segment)), default=0)
        ids = [int(x) for x in _PREDICTION_ID.findall(segment[cut:])]
        after = _VERDICT_TARGET_AFTER.match(line[v.end():])
        if after:
            ids.append(int(after.group(1)))
        out.extend((i, v.group(1)) for i in ids)
        last = v.end()
    return out


def _v_verdict_agreement(root: Path, spec: Dict[str, Any]) -> Tuple[bool, str]:
    """Every verdict a document states for a prediction must match its scorecard."""
    rx_outcome = re.compile(spec.get("outcome_pattern",
                                     r"\*\*Outcome:\*\*\s*\S+\s+(PASS|FAIL|SUB-THRESHOLD)"))
    rx_id = re.compile(spec.get("id_pattern", r"^P0*(\d+)_"))
    actual: Dict[int, str] = {}
    for card in _iter_files(root, spec["scorecard_globs"]):
        m_id, m_out = rx_id.match(card.parent.name), rx_outcome.search(_read(card))
        if m_id and m_out:
            actual[int(m_id.group(1))] = m_out.group(1)
    if not actual:
        return False, "no scorecard with a readable outcome was found"
    unless = [re.compile(u, re.IGNORECASE) for u in spec.get("unless", [])]
    checked = 0
    mismatches: List[str] = []
    for p in _iter_files(root, spec["globs"], spec.get("exclude", [])):
        for i, line in enumerate(_read(p).splitlines(), 1):
            if any(u.search(line) for u in unless):
                continue
            for pid, said in stated_verdicts(line):
                if pid not in actual:
                    continue
                checked += 1
                if said != actual[pid]:
                    mismatches.append("%s:%d says P%d %s (scorecard: %s)"
                                      % (p.relative_to(root).as_posix(), i, pid, said, actual[pid]))
    if mismatches:
        return False, "%d of %d stated verdict(s) disagree: %s" % (
            len(mismatches), checked, "; ".join(mismatches[:4]))
    min_sites = int(spec.get("min_sites", 1))
    if checked < min_sites:
        return False, ("only %d stated verdict(s) found (floor %d): the pattern is not seeing the prose"
                       % (checked, min_sites))
    return True, "all %d stated verdict(s) match the scorecards" % checked


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


_EXTENSIONS = "md|py|sh|json|csv|yml|yaml|cff|txt|pdf|bib|tex|sha256|toml"
_PATH_EXT = r"(?:" + _EXTENSIONS + r")"
_PATH_TOKEN = re.compile(r"^(?:\./)?[A-Za-z0-9_.\-]+(?:/[A-Za-z0-9_.\-]+)*(?:\." + _PATH_EXT + r"|/)$")
_BARE_NAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]*\." + _PATH_EXT + r"$")
_MD_LINK = re.compile(r"\]\(([^)\s]+)\)")
_BACKTICK = re.compile(r"`([^`\n]+)`")


def _path_candidates(text: str):
    """Yield (token, kind) for path-like references in a markdown document.

    kind 'link' = markdown link target (resolved relative to the file);
    kind 'root' = backticked or code-block path (resolved relative to the root);
    kind 'name' = backticked or code-block bare file name such as `run_all.sh`
                  (it must exist somewhere in the package).
    """
    for m in _MD_LINK.finditer(text):
        target = m.group(1).split("#", 1)[0]
        if target and not re.match(r"^[a-z]+:", target):
            yield target, "link"
    in_block = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_block = not in_block
            continue
        tokens = line.split() if in_block else [t for m in _BACKTICK.finditer(line) for t in m.group(1).split()]
        for tok in tokens:
            tok = tok.strip("\"'(),;:")
            if "/" in tok and _PATH_TOKEN.match(tok) and not tok.startswith(("path/to", "/")):
                yield tok, "root"
            elif "/" not in tok and _BARE_NAME.match(tok):
                yield tok, "name"


def _v_path_references_resolve(root: Path, spec: Dict[str, Any]) -> Tuple[bool, str]:
    """Every repository path a living document mentions must exist in this tree.

    Catches stale paths and references to files that live only in other versions
    of the project — the standalone guarantee, made mechanical. A bare file name
    (no directory) must match a file somewhere in the tree, outside the
    directories listed in `name_index_exclude` (verbatim historical fixtures
    would otherwise make old file names look present).
    """
    dangling: List[str] = []
    allowed = set(spec.get("allow", []))
    index_exclude = spec.get("name_index_exclude", [])
    names = {q.name for q in root.rglob("*")
             if q.is_file() and ".git" not in q.parts
             and not any(re.search(x, q.relative_to(root).as_posix()) for x in index_exclude)}
    checked = 0
    for p in _iter_files(root, spec["globs"], spec.get("exclude", [])):
        for tok, kind in _path_candidates(_read(p)):
            checked += 1
            if tok in allowed:
                continue
            if kind == "name":
                present = tok in names
            else:
                present = (p.parent / tok).exists() or (root / tok).exists()
            if not present:
                dangling.append("%s -> %s" % (p.relative_to(root).as_posix(), tok))
    min_checked = int(spec.get("min_checked", 1))
    if checked < min_checked:
        return False, ("only %d path reference(s) examined (floor %d): the scanner is not seeing the docs"
                       % (checked, min_checked))
    if dangling:
        return False, "%d dangling path reference(s); e.g. %s" % (len(dangling), "; ".join(dangling[:4]))
    return True, "all %d path reference(s) resolve" % checked


def _v_sha256_manifest(root: Path, spec: Dict[str, Any]) -> Tuple[bool, str]:
    """A checksum manifest must match the files it lists, and list every covered file."""
    manifest = root / spec["manifest"]
    if not manifest.is_file():
        return False, "manifest missing: %s" % spec["manifest"]
    listed: Dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            digest, rel = line.split(None, 1)
            listed[rel.strip()] = digest.strip()
    mismatched = [rel for rel, d in listed.items()
                  if not (root / rel).is_file() or hashlib.sha256((root / rel).read_bytes()).hexdigest() != d]
    covered = {p.relative_to(root).as_posix() for p in _iter_files(root, spec["covers_globs"])}
    unlisted = sorted(covered - set(listed))
    if mismatched or unlisted:
        return False, "%d mismatched, %d unlisted; e.g. %s" % (
            len(mismatched), len(unlisted), ", ".join((mismatched + unlisted)[:4]))
    return True, "all %d listed file(s) match; every covered file is listed" % len(listed)


VERIFIERS = {
    "frontmatter_field_nonempty": _v_frontmatter_field_nonempty,
    "path_count": _v_path_count,
    "number_agreement": _v_number_agreement,
    "sibling_hash_match": _v_sibling_hash_match,
    "json_field_resolves": _v_json_field_resolves,
    "json_schema_valid": _v_json_schema_valid,
    "verdict_agreement": _v_verdict_agreement,
    "file_regex_count": _v_file_regex_count,
    "command_exit_zero": _v_command_exit_zero,
    "path_references_resolve": _v_path_references_resolve,
    "sha256_manifest": _v_sha256_manifest,
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
    ap.add_argument("--claims", default=None, help="claims manifest (default: <root>/verification/claims.json)")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    ap.add_argument("--include-slow", action="store_true", help="also run subprocess facts")
    ap.add_argument("--explain", action="store_true", help="show every claim, including skips")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    manifest = Path(args.claims) if args.claims else root / "verification" / "claims.json"
    if not manifest.is_file():
        # Allow verifying an old tree with the current manifest.
        fallback = Path(__file__).resolve().parent / "claims.json"
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

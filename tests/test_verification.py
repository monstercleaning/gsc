"""The claim checker passes on the package, still fires on known-bad inputs,
and each new guard has a negative control."""

import copy
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "verification" / "verify_claims.py"
CLAIMS = ROOT / "verification" / "claims.json"


def run_checker(root, claims=CLAIMS):
    proc = subprocess.run([sys.executable, str(VERIFY), "--root", str(root), "--claims", str(claims),
                           "--format", "json"], capture_output=True, text=True)
    return json.loads(proc.stdout)


class TestVerification(unittest.TestCase):
    def test_all_fast_claims_are_backed(self):
        doc = run_checker(ROOT)
        self.assertEqual(doc["unbacked"], [], doc["unbacked"])

    def test_negative_control_still_catches_the_historical_false_claim(self):
        proc = subprocess.run([sys.executable, str(ROOT / "verification" / "retro_test.py")],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_liveness_floor_fails_a_count_pattern_that_matches_nothing(self):
        claims = json.loads(CLAIMS.read_text())
        for c in claims["claims"]:
            if c["id"] == "prediction-count":
                c["verify"]["pattern"] = r"\b(zero|one|two)\s+registered\s+predictions?\b"
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "claims.json"
            bad.write_text(json.dumps(claims))
            doc = run_checker(ROOT, bad)
        self.assertIn("prediction-count", doc["unbacked"])

    def test_path_check_fails_on_a_dangling_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp)
            (tree / "README.md").write_text("See `docs/missing_note.md` for details.\n")
            claims = {"schema": json.loads(CLAIMS.read_text())["schema"], "claims": [
                {"id": "paths", "claim": "paths resolve", "always": True,
                 "verify": {"type": "path_references_resolve", "globs": ["*.md"], "min_checked": 1}}]}
            (tree / "claims.json").write_text(json.dumps(claims))
            self.assertIn("paths", run_checker(tree, tree / "claims.json")["unbacked"])
            (tree / "docs").mkdir()
            (tree / "docs" / "missing_note.md").write_text("now it exists\n")
            self.assertEqual(run_checker(tree, tree / "claims.json")["unbacked"], [])

    def test_manifest_check_fails_when_a_registered_file_is_altered(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp) / "pkg"
            shutil.copytree(ROOT / "predictions", tree / "predictions")
            target = next((tree / "predictions").glob("P11_*/pipeline_output.json"))
            target.write_text(target.read_text().replace('"eta1_linear_coefficient": 0.0', '"eta1_linear_coefficient": 0.01'))
            claims = {"schema": json.loads(CLAIMS.read_text())["schema"], "claims": [
                c for c in json.loads(CLAIMS.read_text())["claims"] if c["id"] == "register-manifest-intact"]}
            (tree / "claims.json").write_text(json.dumps(claims))
            self.assertIn("register-manifest-intact", run_checker(tree, tree / "claims.json")["unbacked"])


# In-process tests of the guards added at the 20.0 deposit review. Each guard has
# a negative control: an input it must reject.
sys.path.insert(0, str(ROOT / "verification"))
import verify_claims as vc  # noqa: E402

FIXTURE = ROOT / "verification" / "fixtures" / "historical_false_claim"


def claim_spec(claim_id):
    for c in json.loads(CLAIMS.read_text())["claims"]:
        if c["id"] == claim_id:
            return c["verify"]
    raise KeyError(claim_id)


def regex_hits(root, spec):
    rx = re.compile(spec["pattern"], re.IGNORECASE)
    unless = [re.compile(u, re.IGNORECASE) for u in spec.get("unless", [])]
    hits = []
    for p in vc._iter_files(root, spec["globs"], spec.get("exclude", [])):
        for i, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
            if rx.search(line) and not any(u.search(line) for u in unless):
                hits.append("%s:%d" % (p.relative_to(root).as_posix(), i))
    return hits


def mutations(doc, limit=60):
    """Invalid-looking variants of a JSON document: wrong types, extreme numbers, dropped keys."""
    out = []

    def leaves(node, path=()):
        items = node.items() if isinstance(node, dict) else enumerate(node[:3]) if isinstance(node, list) else ()
        for k, v in items:
            yield path + (k,), v
            yield from leaves(v, path + (k,))

    def put(doc_copy, path, value=None, delete=False):
        node = doc_copy
        for k in path[:-1]:
            node = node[k]
        if delete:
            del node[path[-1]]
        else:
            node[path[-1]] = value

    for path, value in leaves(doc):
        if isinstance(value, bool):
            replacements = ["text"]
        elif isinstance(value, (int, float)):
            replacements = [-1e30, 1e30, "text"]
        elif isinstance(value, str):
            replacements = [0]
        else:
            replacements = []
        for r in replacements:
            d = copy.deepcopy(doc)
            put(d, path, r)
            out.append(d)
        if isinstance(path[-1], str):
            d = copy.deepcopy(doc)
            put(d, path, delete=True)
            out.append(d)
        if len(out) >= limit:
            break
    return out


class TestSchemaValidator(unittest.TestCase):
    SCHEMA = {"type": "object", "required": ["id", "x"], "additionalProperties": False,
              "properties": {"id": {"type": "string", "const": "P1"},
                             "x": {"type": "number", "exclusiveMinimum": 0, "maximum": 10},
                             "n": {"type": "integer", "minimum": 1},
                             "tags": {"type": "array", "minItems": 1,
                                      "items": {"type": "string", "enum": ["a", "b"]}}}}

    def test_a_valid_document_passes(self):
        self.assertEqual(vc.schema_errors({"id": "P1", "x": 2.5, "n": 3, "tags": ["a"]}, self.SCHEMA), [])

    def test_each_keyword_is_enforced(self):
        bad = {
            "required": {"id": "P1"},
            "type": {"id": "P1", "x": "2"},
            "const": {"id": "P2", "x": 1},
            "exclusiveMinimum": {"id": "P1", "x": 0},
            "maximum": {"id": "P1", "x": 11},
            "minimum": {"id": "P1", "x": 1, "n": 0},
            "integer": {"id": "P1", "x": 1, "n": 1.5},
            "minItems": {"id": "P1", "x": 1, "tags": []},
            "items/enum": {"id": "P1", "x": 1, "tags": ["c"]},
            "additionalProperties": {"id": "P1", "x": 1, "extra": True},
            "a boolean is not a number": {"id": "P1", "x": True},
        }
        for keyword, data in bad.items():
            with self.subTest(keyword):
                self.assertNotEqual(vc.schema_errors(data, self.SCHEMA), [])
        self.assertNotEqual(vc.schema_errors("X12", {"type": "string", "pattern": "^P\\d+$"}), [])

    def test_draft07_semantics(self):
        self.assertEqual(vc.schema_errors(2.0, {"type": "integer"}), [])
        self.assertNotEqual(vc.schema_errors(1, {"const": True}), [])

    def test_an_unknown_keyword_is_an_error_not_a_silent_pass(self):
        self.assertNotEqual(vc.schema_errors(5, {"oneOf": [{"type": "string"}]}), [])
        self.assertNotEqual(vc.schema_errors(5, {"type": "number", "multipleOf": 2}), [])

    @unittest.skipUnless(importlib.util.find_spec("jsonschema"), "reference validator not installed")
    def test_agrees_with_the_reference_validator(self):
        import jsonschema
        verdicts = {True: 0, False: 0}
        for out in sorted((ROOT / "predictions").glob("P*/pipeline_output*.json")):
            data = json.loads(out.read_text())
            schema = json.loads((ROOT / "schemas" / (data["schema"] + ".schema.json")).read_text())
            reference = jsonschema.Draft7Validator(schema)
            for variant in [data] + mutations(data):
                expected = reference.is_valid(variant)
                verdicts[expected] += 1
                self.assertEqual(not vc.schema_errors(variant, schema), expected,
                                 "%s: %s" % (out.parent.name, json.dumps(variant)[:160]))
        # Both outcomes must be well represented, or the comparison proves little.
        self.assertGreater(verdicts[True], 100)
        self.assertGreater(verdicts[False], 100)

    def test_schema_claim_fails_when_a_registered_output_violates_its_schema(self):
        spec = claim_spec("schema-validated-artifacts")
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp)
            self.assertFalse(vc._v_json_schema_valid(tree, spec)[0], "an empty tree must not pass")
            shutil.copytree(ROOT / "predictions", tree / "predictions")
            shutil.copytree(ROOT / "schemas", tree / "schemas")
            self.assertTrue(vc._v_json_schema_valid(tree, spec)[0])
            target = next((tree / "predictions").glob("P01_*/pipeline_output.json"))
            data = json.loads(target.read_text())
            del data["tier"]
            target.write_text(json.dumps(data))
            ok, detail = vc._v_json_schema_valid(tree, spec)
            self.assertFalse(ok)
            self.assertIn("tier", detail)


class TestDepositReviewGuards(unittest.TestCase):
    def test_explained_anomaly_guard_catches_the_phrasing_that_survived(self):
        hits = regex_hits(FIXTURE, claim_spec("no-unqualified-explained-anomaly"))
        self.assertIn("papers/paper_D_methodology/main.md:179", hits)

    def test_signed_entries_guard_fires_on_the_historical_fixture(self):
        hits = regex_hits(FIXTURE, claim_spec("no-unqualified-signed-entries"))
        self.assertIn("papers/paper_D_methodology/main.md:183", hits)
        self.assertGreaterEqual(len(hits), 3)

    def test_count_check_reads_the_phrasings_that_escaped(self):
        spec = claim_spec("prediction-count")
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp)
            shutil.copytree(ROOT / "predictions", tree / "predictions")
            for sentence in ("We demonstrate it on ten near-term cosmological predictions.",
                             "Confirm all 10 predictions compute deterministically.",
                             "The repository ships ten worked examples."):
                (tree / "README.md").write_text(sentence + "\n")
                with self.subTest(sentence):
                    ok, detail = vc._v_number_agreement(tree, spec)
                    self.assertFalse(ok)
                    self.assertIn("says 10", detail)
            (tree / "README.md").write_text("Confirm all thirteen predictions compute deterministically.\n")
            self.assertTrue(vc._v_number_agreement(tree, spec)[0])

    def test_verdict_parsing(self):
        self.assertEqual(vc.stated_verdicts("outcomes (P1, P3, P4, P6 FAIL; P5, P9 PASS; P7 SUB-THRESHOLD)."),
                         [(1, "FAIL"), (3, "FAIL"), (4, "FAIL"), (6, "FAIL"),
                          (5, "PASS"), (9, "PASS"), (7, "SUB-THRESHOLD")])
        self.assertEqual(vc.stated_verdicts("the framework records a useful FAIL on P4 (the hint)"), [(4, "FAIL")])
        self.assertEqual(vc.stated_verdicts("squeezes the module (P4, already FAIL)."), [(4, "FAIL")])
        self.assertEqual(vc.stated_verdicts("P4 passes weakly"), [])

    def test_verdict_claim_fails_on_a_stale_verdict_and_skips_hedged_history(self):
        spec = dict(claim_spec("prose-verdicts-match-scorecards"), min_sites=1)
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp)
            shutil.copytree(ROOT / "predictions", tree / "predictions")
            (tree / "NOTES.md").write_text("P4 was FAIL under the earlier 2σ rule.\nThe register records P4 PASS.\n")
            self.assertTrue(vc._v_verdict_agreement(tree, spec)[0])
            (tree / "NOTES.md").write_text("The register records P4 FAIL.\n")
            ok, detail = vc._v_verdict_agreement(tree, spec)
            self.assertFalse(ok)
            self.assertIn("P4 FAIL", detail)

    def test_bare_file_names_must_exist_outside_excluded_directories(self):
        spec = {"globs": ["*.md"], "min_checked": 1, "name_index_exclude": ["^fixtures/"]}
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp)
            (tree / "README.md").write_text("Run `release_check.sh` first.\n")
            self.assertFalse(vc._v_path_references_resolve(tree, spec)[0])
            (tree / "fixtures").mkdir()
            (tree / "fixtures" / "release_check.sh").write_text("")
            self.assertFalse(vc._v_path_references_resolve(tree, spec)[0], "a historical copy does not count")
            (tree / "tools").mkdir()
            (tree / "tools" / "release_check.sh").write_text("")
            self.assertTrue(vc._v_path_references_resolve(tree, spec)[0])


if __name__ == "__main__":
    unittest.main()

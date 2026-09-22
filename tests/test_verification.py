"""The claim checker passes on the package, still fires on known-bad inputs,
and each new guard has a negative control."""

import json
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


if __name__ == "__main__":
    unittest.main()

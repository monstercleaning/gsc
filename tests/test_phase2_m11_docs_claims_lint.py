import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]  # v11.0.0/
SCRIPTS = ROOT / "scripts"

sys.path.insert(0, str(SCRIPTS))


class TestPhase2M11DocsClaimsLint(unittest.TestCase):
    def test_repo_docs_claims_lint_passes(self):
        script = SCRIPTS / "docs_claims_lint.py"
        self.assertTrue(script.exists())
        r = subprocess.run(
            [sys.executable, str(script), "--repo-root", str(ROOT)],
            capture_output=True,
            text=True,
        )
        out = (r.stdout or "") + (r.stderr or "")
        self.assertEqual(r.returncode, 0, msg=out)
        self.assertIn("OK: docs claims lint passed", out)

    def test_banned_phrase_is_detected(self):
        script = SCRIPTS / "docs_claims_lint.py"
        self.assertTrue(script.exists())
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bad = td_path / "bad.md"
            bad.write_text("This note says torsion behaves like axion.\n", encoding="utf-8")
            r = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--repo-root",
                    str(ROOT),
                    "--file",
                    str(bad),
                    "--skip-required-patterns",
                ],
                capture_output=True,
                text=True,
            )
            out = (r.stdout or "") + (r.stderr or "")
            self.assertNotEqual(r.returncode, 0, msg=out)
            self.assertIn("ban_torsion_behaves_like_axion", out)

    def test_missing_required_measurement_model_clause_is_detected(self):
        import docs_claims_lint as lint  # noqa: E402

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mm = root / "docs" / "measurement_model.md"
            mm.parent.mkdir(parents=True, exist_ok=True)
            mm.write_text("Placeholder without required guardrail wording.\n", encoding="utf-8")
            findings = lint.lint_files(repo_root=root, files=[mm], enforce_required=True)
            keys = {f.key for f in findings}
            self.assertIn("require_history_not_frame_measurement_model", keys)
            self.assertIn("require_kinematic_sandage_loeb_measurement_model", keys)


if __name__ == "__main__":
    unittest.main()

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


class TestPhase2M13DocsClaimsLintFrameEquivalence(unittest.TestCase):
    def test_bad_frame_discriminator_phrase_fails(self):
        script = SCRIPTS / "docs_claims_lint.py"
        self.assertTrue(script.exists())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bad = td_path / "bad.md"
            bad.write_text(
                "Redshift drift distinguishes freeze frame vs expansion directly.\n",
                encoding="utf-8",
            )
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
            self.assertIn("ban_drift_as_frame_discriminator", out)

    def test_good_history_based_phrase_passes(self):
        script = SCRIPTS / "docs_claims_lint.py"
        self.assertTrue(script.exists())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            good = td_path / "good.md"
            good.write_text(
                (
                    "Redshift drift uses the same kinematic relation in both frames.\n"
                    "It discriminates competing H(z) histories, not frame labels.\n"
                ),
                encoding="utf-8",
            )
            r = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--repo-root",
                    str(ROOT),
                    "--file",
                    str(good),
                    "--skip-required-patterns",
                ],
                capture_output=True,
                text=True,
            )
            out = (r.stdout or "") + (r.stderr or "")
            self.assertEqual(r.returncode, 0, msg=out)
            self.assertIn("OK: docs claims lint passed", out)


if __name__ == "__main__":
    unittest.main()

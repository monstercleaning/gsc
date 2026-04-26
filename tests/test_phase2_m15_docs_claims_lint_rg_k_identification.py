import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


class TestPhase2M15DocsClaimsLintRgKIdentification(unittest.TestCase):
    def test_rg_trigger_without_qualifier_fails(self):
        script = SCRIPTS / "docs_claims_lint.py"
        self.assertTrue(script.exists())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bad = td_path / "bad_rg.md"
            bad.write_text(
                (
                    "Asymptotic safety and FRG motivate running couplings with k.\n"
                    "Here we directly use k = 1/sigma in the model.\n"
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
                    str(bad),
                    "--skip-required-patterns",
                ],
                capture_output=True,
                text=True,
            )
            out = (r.stdout or "") + (r.stderr or "")
            self.assertNotEqual(r.returncode, 0, msg=out)
            self.assertIn("require_rg_scale_qualifier_if_triggered", out)

    def test_rg_trigger_with_qualifier_passes(self):
        script = SCRIPTS / "docs_claims_lint.py"
        self.assertTrue(script.exists())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            good = td_path / "good_rg.md"
            good.write_text(
                (
                    "Asymptotic safety uses momentum scale k in FRG.\n"
                    "In this release k(sigma) is a working identification ansatz and not derived.\n"
                    "Its derivation remains an open problem.\n"
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

    def test_banned_torsion_axion_phrase_fails(self):
        script = SCRIPTS / "docs_claims_lint.py"
        self.assertTrue(script.exists())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bad = td_path / "bad_phrase.md"
            bad.write_text("Legacy claim: torsion = axion.\n", encoding="utf-8")
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
            self.assertIn("ban_torsion_equals_axion", out)


if __name__ == "__main__":
    unittest.main()

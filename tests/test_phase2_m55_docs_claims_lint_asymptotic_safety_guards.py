import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "docs_claims_lint.py"


class TestPhase2M55DocsClaimsLintAsymptoticSafetyGuards(unittest.TestCase):
    def test_fail_when_as_claims_landau_prediction_without_disclaimer(self):
        self.assertTrue(SCRIPT.is_file())
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bad = td_path / "bad_as_claim.md"
            bad.write_text(
                (
                    "Asymptotic safety predicts our exact Landau pole form.\n"
                    "We therefore use 1-(k/k*)^2 as a direct derivation.\n"
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo-root",
                    str(ROOT),
                    "--file",
                    str(bad),
                    "--skip-required-patterns",
                ],
                capture_output=True,
                text=True,
            )
            out = (proc.stdout or "") + (proc.stderr or "")
            self.assertNotEqual(proc.returncode, 0, msg=out)
            self.assertIn("AS_LANDAU_CONFLATION", out)
            self.assertIn("bad_as_claim.md", out)

    def test_pass_when_as_frg_language_is_explicitly_ansatz_level(self):
        self.assertTrue(SCRIPT.is_file())
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            good = td_path / "good_as_note.md"
            good.write_text(
                (
                    "Asymptotic safety and FRG are used here as conceptual motivation only.\n"
                    "The running form is a phenomenological ansatz, not derived, and we do not attempt derivation.\n"
                    "The k(sigma) mapping is a working identification and remains an open problem.\n"
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo-root",
                    str(ROOT),
                    "--file",
                    str(good),
                    "--skip-required-patterns",
                ],
                capture_output=True,
                text=True,
            )
            out = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=out)
            self.assertIn("OK: docs claims lint passed", out)

    def test_repo_docs_claims_lint_passes_with_new_as_guards(self):
        self.assertTrue(SCRIPT.is_file())
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--repo-root", str(ROOT)],
            capture_output=True,
            text=True,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        self.assertEqual(proc.returncode, 0, msg=out)
        self.assertIn("OK: docs claims lint passed", out)


if __name__ == "__main__":
    unittest.main()

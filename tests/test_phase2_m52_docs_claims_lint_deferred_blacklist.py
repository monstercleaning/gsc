import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "docs_claims_lint.py"


class TestPhase2M52DocsClaimsLintDeferredBlacklist(unittest.TestCase):
    def test_deferred_blacklist_patterns_fail_with_file_and_key(self):
        self.assertTrue(SCRIPT.is_file())
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bad = td_path / "bad_deferred.md"
            bad.write_text(
                (
                    "Legacy claim: m_vac equals axion mass.\n"
                    "Also wrong: Omega_0 ~ H_0 gives beta ~ 0.1.\n"
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
            self.assertIn("deferred_mvac_equals_axion_mass", out)
            self.assertIn("deferred_wrong_omega0_h0_beta_point1", out)
            self.assertIn("bad_deferred.md", out)


if __name__ == "__main__":
    unittest.main()

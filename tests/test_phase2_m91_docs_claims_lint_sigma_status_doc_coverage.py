import subprocess
import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


class TestPhase2M91DocsClaimsLintSigmaStatusDocCoverage(unittest.TestCase):
    def test_sigma_status_doc_is_in_default_coverage(self) -> None:
        import docs_claims_lint as lint  # noqa: E402

        self.assertIn("docs/sigma_field_origin_status.md", set(lint.DEFAULT_REL_FILES))

    def test_sigma_status_doc_passes_claims_lint(self) -> None:
        script = SCRIPTS / "docs_claims_lint.py"
        target = ROOT / "docs" / "sigma_field_origin_status.md"
        run = subprocess.run(
            [
                sys.executable,
                str(script),
                "--repo-root",
                str(ROOT),
                "--file",
                str(target),
                "--skip-required-patterns",
            ],
            capture_output=True,
            text=True,
        )
        out = (run.stdout or "") + (run.stderr or "")
        self.assertEqual(run.returncode, 0, msg=out)


if __name__ == "__main__":
    unittest.main()

import subprocess
import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


class TestPhase2M102DocsClaimsLintPerturbationsDmScopeCoverage(unittest.TestCase):
    def test_doc_is_in_default_coverage(self) -> None:
        import docs_claims_lint as lint  # noqa: E402

        self.assertIn("docs/perturbations_and_dm_scope.md", set(lint.DEFAULT_REL_FILES))

    def test_doc_passes_claims_lint(self) -> None:
        script = SCRIPTS / "docs_claims_lint.py"
        target = ROOT / "docs" / "perturbations_and_dm_scope.md"
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

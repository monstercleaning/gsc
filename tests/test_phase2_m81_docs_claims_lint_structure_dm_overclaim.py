import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "docs_claims_lint.py"


class TestPhase2M81DocsClaimsLintStructureDMOverclaim(unittest.TestCase):
    def _run_lint(self, *, repo_root: Path, file_path: Path) -> subprocess.CompletedProcess:
        cmd = [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(repo_root),
            "--file",
            str(file_path),
            "--skip-required-patterns",
        ]
        return subprocess.run(cmd, capture_output=True, text=True)

    def test_dm_and_structure_overclaim_fail(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td) / "v11.0.0"
            docs_dir = repo_root / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            bad = docs_dir / "review.md"
            bad.write_text(
                "This model eliminates dark matter and solves structure formation.\n",
                encoding="utf-8",
            )

            proc = self._run_lint(repo_root=repo_root, file_path=bad)
            combined = (proc.stdout or "") + (proc.stderr or "")
            self.assertNotEqual(proc.returncode, 0, msg=combined)
            self.assertIn("DARK_MATTER_ELIMINATION_OVERCLAIM", combined)
            self.assertIn("STRUCTURE_FORMATION_SOLVED_OVERCLAIM", combined)

    def test_deferred_marker_allows_deferred_claim_text(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td) / "v11.0.0"
            docs_dir = repo_root / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            ok_doc = docs_dir / "deferred_note.md"
            ok_doc.write_text(
                "DEFERRED_DM_CLAIM DEFERRED_STRUCTURE_CLAIM: no dark matter needed; solves structure formation.\n",
                encoding="utf-8",
            )

            proc = self._run_lint(repo_root=repo_root, file_path=ok_doc)
            combined = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=combined)
            self.assertIn("OK: docs claims lint passed", combined)


if __name__ == "__main__":
    unittest.main()

import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "docs_claims_lint.py"


class TestPhase2M88DocsClaimsLintScopeOverclaimGuards(unittest.TestCase):
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

    def test_fail_cmb_full_spectra_without_scope_disclaimer(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td) / "v11.0.0"
            docs_dir = repo_root / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            doc = docs_dir / "bad_cmb_scope.md"
            doc.write_text(
                "We now fit TT/TE/EE acoustic peaks with CAMB in canonical mode.\n",
                encoding="utf-8",
            )
            proc = self._run_lint(repo_root=repo_root, file_path=doc)
            combined = (proc.stdout or "") + (proc.stderr or "")
            self.assertNotEqual(proc.returncode, 0, msg=combined)
            self.assertIn("CMB_FULL_SPECTRA_OVERCLAIM", combined)

    def test_pass_cmb_full_spectra_with_scope_disclaimer(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td) / "v11.0.0"
            docs_dir = repo_root / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            doc = docs_dir / "good_cmb_scope.md"
            doc.write_text(
                (
                    "TT/TE/EE and Boltzmann-class paths are future work. "
                    "Current release uses compressed priors diagnostic only and "
                    "is not a full spectra fit.\n"
                ),
                encoding="utf-8",
            )
            proc = self._run_lint(repo_root=repo_root, file_path=doc)
            combined = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=combined)
            self.assertIn("OK: docs claims lint passed", combined)

    def test_fail_dm_solved_kill_lcdm_and_journal_hype(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td) / "v11.0.0"
            docs_dir = repo_root / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            doc = docs_dir / "bad_claims.md"
            doc.write_text(
                (
                    "This model kills LCDM, solves dark matter, and was accepted by Nature as proof.\n"
                ),
                encoding="utf-8",
            )
            proc = self._run_lint(repo_root=repo_root, file_path=doc)
            combined = (proc.stdout or "") + (proc.stderr or "")
            self.assertNotEqual(proc.returncode, 0, msg=combined)
            self.assertIn("KILL_LCDM_RHETORIC", combined)
            self.assertIn("DM_SOLVED_OVERCLAIM", combined)
            self.assertIn("JOURNAL_NAME_DROP_OVERHYPE", combined)


if __name__ == "__main__":
    unittest.main()

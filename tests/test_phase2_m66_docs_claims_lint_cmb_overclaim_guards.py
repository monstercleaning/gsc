import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "docs_claims_lint.py"


class TestPhase2M66DocsClaimsLintCmbOverclaimGuards(unittest.TestCase):
    def _run_lint(
        self,
        *,
        repo_root: Path,
        file_path: Path,
        skip_required: bool = True,
    ) -> subprocess.CompletedProcess:
        cmd = [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(repo_root),
            "--file",
            str(file_path),
        ]
        if skip_required:
            cmd.append("--skip-required-patterns")
        return subprocess.run(cmd, capture_output=True, text=True)

    def test_fail_on_cmb_planck_overclaim_without_disclaimer(self) -> None:
        self.assertTrue(SCRIPT.is_file())
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td) / "v11.0.0"
            docs_dir = repo_root / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            bad = docs_dir / "reviewer_faq.md"
            bad.write_text(
                "GSC fits CMB and is consistent with Planck.\n",
                encoding="utf-8",
            )

            proc = self._run_lint(repo_root=repo_root, file_path=bad)
            out = (proc.stdout or "") + (proc.stderr or "")
            self.assertNotEqual(proc.returncode, 0, msg=out)
            self.assertIn("CMB_OVERCLAIM_LANGUAGE", out)
            self.assertIn("reviewer_faq.md", out)

    def test_fail_on_peak_reproduction_claim_without_disclaimer(self) -> None:
        self.assertTrue(SCRIPT.is_file())
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td) / "v11.0.0"
            docs_dir = repo_root / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            bad = docs_dir / "framework_note.md"
            bad.write_text(
                "This model explains acoustic peaks and reproduces peaks.\n",
                encoding="utf-8",
            )

            proc = self._run_lint(repo_root=repo_root, file_path=bad)
            out = (proc.stdout or "") + (proc.stderr or "")
            self.assertNotEqual(proc.returncode, 0, msg=out)
            self.assertIn("CMB_OVERCLAIM_LANGUAGE", out)

    def test_pass_with_compressed_priors_diagnostic_disclaimer(self) -> None:
        self.assertTrue(SCRIPT.is_file())
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td) / "v11.0.0"
            docs_dir = repo_root / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            good = docs_dir / "reviewer_faq.md"
            good.write_text(
                (
                    "We test CMB compressed priors as diagnostic only; "
                    "this is not a full power spectrum fit and not peak-level.\n"
                ),
                encoding="utf-8",
            )

            proc = self._run_lint(repo_root=repo_root, file_path=good)
            out = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=out)
            self.assertIn("OK: docs claims lint passed", out)

    def test_repo_docs_claims_lint_passes_with_m66_rules(self) -> None:
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

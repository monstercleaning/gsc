from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase4_pantheon_plus_epsilon_posterior.py"
DATASET = ROOT / "tests" / "fixtures" / "phase4_m154" / "pantheon_toy_mu_fullcov.csv"
MANIFEST = ROOT / "tests" / "fixtures" / "phase4_m154" / "pantheon_toy_manifest.json"


class TestPhase4M155PantheonPaperGradeRequiresFullCovToy(unittest.TestCase):
    def test_paper_grade_requires_full_covariance_mode(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo-root",
                    str(ROOT),
                    "--outdir",
                    str(Path(td) / "out"),
                    "--deterministic",
                    "1",
                    "--format",
                    "json",
                    "--run-mode",
                    "paper_grade",
                    "--covariance-mode",
                    "diag_only_proof_of_concept",
                    "--data-manifest",
                    str(MANIFEST),
                    "--dataset",
                    str(DATASET),
                    "--omega-m-n",
                    "7",
                    "--epsilon-n",
                    "7",
                    "--integration-n",
                    "256",
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 2, msg=(proc.stdout or "") + (proc.stderr or ""))
            self.assertIn("paper_grade requires --covariance-mode full", proc.stderr)


if __name__ == "__main__":
    unittest.main()

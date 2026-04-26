from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase4_pantheon_plus_epsilon_posterior.py"
DATASET = ROOT / "tests" / "fixtures" / "phase4_m154" / "pantheon_toy_mu_fullcov.csv"
COV = ROOT / "tests" / "fixtures" / "phase4_m154" / "pantheon_toy_cov.txt"


class TestPhase4M155PantheonPaperGradeRequiresManifestToy(unittest.TestCase):
    def test_paper_grade_requires_manifest(self) -> None:
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
                    "full",
                    "--dataset",
                    str(DATASET),
                    "--covariance",
                    str(COV),
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
            self.assertIn("paper_grade requires --data-manifest", proc.stderr)


if __name__ == "__main__":
    unittest.main()

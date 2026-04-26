from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SANITY_SCRIPT = ROOT / "scripts" / "phase3_pt_spectra_sanity_report.py"


class TestPhase3M126SpectraSanityGateRequireTTFailsWhenMissing(unittest.TestCase):
    def test_require_tt_gate_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            run_dir = td_path / "run_dir"
            outdir = td_path / "out"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "not_a_spectrum.dat").write_text("# l TT\nfoo bar\nbaz qux\n", encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SANITY_SCRIPT),
                    "--path",
                    str(run_dir),
                    "--outdir",
                    str(outdir),
                    "--created-utc",
                    "2000-01-01T00:00:00Z",
                    "--require-tt",
                    "1",
                    "--format",
                    "text",
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 2, msg=output)
            self.assertIn("PHASE3_SPECTRA_SANITY_FAILED", output)


if __name__ == "__main__":
    unittest.main()


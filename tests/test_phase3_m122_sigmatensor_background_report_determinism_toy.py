import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase3_st_sigmatensor_background_report.py"


def _sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class TestPhase3M122SigmaTensorBackgroundReportDeterminismToy(unittest.TestCase):
    def _run_report(self, outdir: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--H0-km-s-Mpc",
                "67.4",
                "--Omega-m",
                "0.315",
                "--w0",
                "-0.95",
                "--lambda",
                "0.4",
                "--z-max",
                "3",
                "--n-steps",
                "512",
                "--outdir",
                str(outdir),
                "--format",
                "json",
            ],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
        )

    def test_report_outputs_are_deterministic_and_portable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            out1 = td_path / "out1"
            out2 = td_path / "out2"

            proc1 = self._run_report(out1)
            self.assertEqual(proc1.returncode, 0, msg=(proc1.stdout or "") + (proc1.stderr or ""))
            proc2 = self._run_report(out2)
            self.assertEqual(proc2.returncode, 0, msg=(proc2.stdout or "") + (proc2.stderr or ""))

            spec1 = out1 / "THEORY_SPEC.json"
            spec2 = out2 / "THEORY_SPEC.json"
            grid1 = out1 / "H_GRID.csv"
            grid2 = out2 / "H_GRID.csv"
            self.assertTrue(spec1.is_file())
            self.assertTrue(spec2.is_file())
            self.assertTrue(grid1.is_file())
            self.assertTrue(grid2.is_file())

            self.assertEqual(spec1.read_bytes(), spec2.read_bytes())
            self.assertEqual(grid1.read_bytes(), grid2.read_bytes())
            self.assertEqual(_sha256_path(spec1), _sha256_path(spec2))
            self.assertEqual(_sha256_path(grid1), _sha256_path(grid2))

            tokens = ["/Users/", "/home/", "/var/folders/", "C:\\\\Users\\\\"]
            for path in (spec1, out1 / "SUMMARY.md"):
                text = path.read_text(encoding="utf-8")
                for token in tokens:
                    self.assertNotIn(token, text)
                self.assertNotIn(str(ROOT.resolve()), text)
                self.assertNotIn(str(out1.resolve()), text)


if __name__ == "__main__":
    unittest.main()

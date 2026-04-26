import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase3_sf_sigmatensor_fsigma8_report.py"
ABS_TOKENS = ("/Users/", "/home/", "/var/folders/", "C:\\\\Users\\\\")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


class TestPhase3M127Fsigma8ReportDeterminismToy(unittest.TestCase):
    def test_deterministic_outputs_and_portable_content(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            out_a = td_path / "out_a"
            out_b = td_path / "out_b"

            base_cmd = [
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
                "--sigma8-mode",
                "fixed",
                "--sigma8-0",
                "0.8",
                "--z-start",
                "20",
                "--n-steps-growth",
                "256",
                "--n-steps-bg",
                "1024",
                "--rsd",
                "1",
                "--ap-correction",
                "0",
                "--created-utc",
                "2000-01-01T00:00:00Z",
                "--format",
                "json",
            ]

            proc_a = subprocess.run(
                [*base_cmd, "--outdir", str(out_a)],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_a.returncode, 0, msg=(proc_a.stdout or "") + (proc_a.stderr or ""))

            proc_b = subprocess.run(
                [*base_cmd, "--outdir", str(out_b)],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_b.returncode, 0, msg=(proc_b.stdout or "") + (proc_b.stderr or ""))

            files = ("FSIGMA8_REPORT.json", "FSIGMA8_GRID.csv", "SUMMARY.md")
            for name in files:
                self.assertTrue((out_a / name).is_file(), msg=f"missing {name} in run A")
                self.assertTrue((out_b / name).is_file(), msg=f"missing {name} in run B")
                self.assertEqual(_sha256(out_a / name), _sha256(out_b / name), msg=f"non-deterministic: {name}")

            for name in files:
                text = (out_a / name).read_text(encoding="utf-8")
                for token in ABS_TOKENS:
                    self.assertNotIn(token, text, msg=f"absolute path token leaked in {name}: {token}")


if __name__ == "__main__":
    unittest.main()

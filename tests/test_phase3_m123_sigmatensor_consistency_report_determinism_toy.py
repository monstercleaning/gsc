import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase3_st_sigmatensor_consistency_report.py"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class TestPhase3M123SigmaTensorConsistencyReportDeterminismToy(unittest.TestCase):
    def _run(self, outdir: Path) -> subprocess.CompletedProcess:
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
                "30",
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

    def test_deterministic_and_portable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            out1 = td_path / "out1"
            out2 = td_path / "out2"

            proc1 = self._run(out1)
            self.assertEqual(proc1.returncode, 0, msg=(proc1.stdout or "") + (proc1.stderr or ""))
            proc2 = self._run(out2)
            self.assertEqual(proc2.returncode, 0, msg=(proc2.stdout or "") + (proc2.stderr or ""))

            j1 = out1 / "THEORY_CONSISTENCY_REPORT.json"
            j2 = out2 / "THEORY_CONSISTENCY_REPORT.json"
            m1 = out1 / "THEORY_CONSISTENCY_REPORT.md"
            m2 = out2 / "THEORY_CONSISTENCY_REPORT.md"

            self.assertTrue(j1.is_file())
            self.assertTrue(j2.is_file())
            self.assertTrue(m1.is_file())
            self.assertTrue(m2.is_file())

            self.assertEqual(j1.read_bytes(), j2.read_bytes())
            self.assertEqual(m1.read_bytes(), m2.read_bytes())
            self.assertEqual(_sha256(j1), _sha256(j2))
            self.assertEqual(_sha256(m1), _sha256(m2))

            text = j1.read_text(encoding="utf-8") + "\n" + m1.read_text(encoding="utf-8")
            for token in ("/Users/", "/home/", "/var/folders/", "C:\\\\Users\\\\"):
                self.assertNotIn(token, text)
            self.assertNotIn(str(ROOT.resolve()), text)
            self.assertNotIn(str(out1.resolve()), text)


if __name__ == "__main__":
    unittest.main()

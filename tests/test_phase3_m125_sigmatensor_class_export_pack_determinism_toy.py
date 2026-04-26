import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase3_pt_sigmatensor_class_export_pack.py"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class TestPhase3M125SigmaTensorClassExportPackDeterminismToy(unittest.TestCase):
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
                "5",
                "--n-steps",
                "256",
                "--outdir",
                str(outdir),
                "--format",
                "json",
            ],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
        )

    def test_deterministic_files_and_portable_content(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            out1 = td_path / "out1"
            out2 = td_path / "out2"
            proc1 = self._run(out1)
            self.assertEqual(proc1.returncode, 0, msg=(proc1.stdout or "") + (proc1.stderr or ""))
            proc2 = self._run(out2)
            self.assertEqual(proc2.returncode, 0, msg=(proc2.stdout or "") + (proc2.stderr or ""))

            names = [
                "EXPORT_SUMMARY.json",
                "CANDIDATE_RECORD.json",
                "BOLTZMANN_INPUT_TEMPLATE_CLASS.ini",
                "README.md",
                "SIGMATENSOR_DIAGNOSTIC_GRID.csv",
            ]
            for name in names:
                p1 = out1 / name
                p2 = out2 / name
                self.assertTrue(p1.is_file(), msg=name)
                self.assertTrue(p2.is_file(), msg=name)
                self.assertEqual(p1.read_bytes(), p2.read_bytes(), msg=name)
                self.assertEqual(_sha256(p1), _sha256(p2), msg=name)

            portable_text = (
                (out1 / "EXPORT_SUMMARY.json").read_text(encoding="utf-8")
                + "\n"
                + (out1 / "CANDIDATE_RECORD.json").read_text(encoding="utf-8")
                + "\n"
                + (out1 / "README.md").read_text(encoding="utf-8")
            )
            for token in ("/Users/", "/home/", "/var/folders/", "C:\\\\Users\\\\"):
                self.assertNotIn(token, portable_text)
            self.assertNotIn(str(ROOT.resolve()), portable_text)
            self.assertNotIn(str(out1.resolve()), portable_text)


if __name__ == "__main__":
    unittest.main()


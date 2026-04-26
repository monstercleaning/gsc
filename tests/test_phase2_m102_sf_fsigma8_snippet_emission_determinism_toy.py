import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_sf_fsigma8_report.py"
MARKER = "phase2_sf_fsigma8_snippet_v1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestPhase2M102SFFSigma8SnippetEmissionDeterminismToy(unittest.TestCase):
    def _run(self, outdir: Path) -> subprocess.CompletedProcess:
        cmd = [
            sys.executable,
            str(SCRIPT),
            "--toy",
            "--emit-snippets",
            str(outdir),
            "--format",
            "json",
        ]
        return subprocess.run(cmd, cwd=str(ROOT.parent), text=True, capture_output=True)

    def test_snippets_are_emitted_with_marker_and_deterministic(self) -> None:
        self.assertTrue(SCRIPT.is_file())
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            out_a = tmp / "a"
            out_b = tmp / "b"

            run_a = self._run(out_a)
            out_a_msg = (run_a.stdout or "") + (run_a.stderr or "")
            self.assertEqual(run_a.returncode, 0, msg=out_a_msg)

            run_b = self._run(out_b)
            out_b_msg = (run_b.stdout or "") + (run_b.stderr or "")
            self.assertEqual(run_b.returncode, 0, msg=out_b_msg)

            names = (
                "phase2_sf_fsigma8.md",
                "phase2_sf_fsigma8.tex",
                "phase2_sf_fsigma8.json",
            )
            for name in names:
                pa = out_a / name
                pb = out_b / name
                self.assertTrue(pa.is_file(), msg=str(pa))
                self.assertTrue(pb.is_file(), msg=str(pb))
                self.assertEqual(_sha256(pa), _sha256(pb), msg=name)

            self.assertIn(MARKER, (out_a / "phase2_sf_fsigma8.md").read_text(encoding="utf-8"))
            self.assertIn(MARKER, (out_a / "phase2_sf_fsigma8.tex").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

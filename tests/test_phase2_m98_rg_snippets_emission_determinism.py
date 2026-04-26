import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
FLOW_SCRIPT = ROOT / "scripts" / "phase2_rg_flow_table_report.py"
PADE_SCRIPT = ROOT / "scripts" / "phase2_rg_pade_fit_report.py"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestPhase2M98RgSnippetsEmissionDeterminism(unittest.TestCase):
    def _run(self, cmd: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, cwd=str(ROOT.parent), text=True, capture_output=True)

    def _emit_pair(self, outdir: Path) -> None:
        flow = self._run([sys.executable, str(FLOW_SCRIPT), "--emit-snippets", str(outdir)])
        flow_out = (flow.stdout or "") + (flow.stderr or "")
        self.assertEqual(flow.returncode, 0, msg=flow_out)

        pade = self._run([sys.executable, str(PADE_SCRIPT), "--emit-snippets", str(outdir)])
        pade_out = (pade.stdout or "") + (pade.stderr or "")
        self.assertEqual(pade.returncode, 0, msg=pade_out)

    def test_emission_and_determinism(self) -> None:
        self.assertTrue(FLOW_SCRIPT.is_file())
        self.assertTrue(PADE_SCRIPT.is_file())

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            out_a = tmp / "a"
            out_b = tmp / "b"

            self._emit_pair(out_a)
            self._emit_pair(out_b)

            expected = [
                "phase2_rg_flow_table.md",
                "phase2_rg_flow_table.tex",
                "phase2_rg_pade_fit.md",
                "phase2_rg_pade_fit.tex",
            ]
            for name in expected:
                pa = out_a / name
                pb = out_b / name
                self.assertTrue(pa.is_file(), msg=str(pa))
                self.assertTrue(pb.is_file(), msg=str(pb))
                self.assertEqual(_sha256(pa), _sha256(pb), msg=name)

            self.assertIn(
                "phase2_rg_flow_table_snippet_v1",
                (out_a / "phase2_rg_flow_table.md").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "phase2_rg_flow_table_snippet_v1",
                (out_a / "phase2_rg_flow_table.tex").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "phase2_rg_pade_fit_snippet_v1",
                (out_a / "phase2_rg_pade_fit.md").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "phase2_rg_pade_fit_snippet_v1",
                (out_a / "phase2_rg_pade_fit.tex").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()

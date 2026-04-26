import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_sf_structure_report.py"


class TestPhase2M81StructureReportCliToy(unittest.TestCase):
    def test_cli_outputs_and_outdir_scope(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            outdir = tmp / "out"
            before = sorted(str(p.relative_to(tmp)) for p in tmp.rglob("*"))
            self.assertEqual(before, [])

            cmd = [
                sys.executable,
                str(SCRIPT),
                "--outdir",
                str(outdir),
                "--background",
                "lcdm_params",
                "--Omega_m0",
                "0.315",
                "--Omega_b0",
                "0.049",
                "--h",
                "0.674",
                "--z-eval",
                "0,1,2",
                "--k-sample",
                "1e-4,1e-2,1",
            ]
            proc = subprocess.run(cmd, cwd=str(tmp), text=True, capture_output=True)
            out = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=out)

            report_json = outdir / "structure_report.json"
            report_txt = outdir / "structure_report.txt"
            self.assertTrue(report_json.is_file())
            self.assertTrue(report_txt.is_file())

            payload = json.loads(report_json.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "phase2_structure_report_v1")
            self.assertIn("background", payload)
            self.assertIn("transfer", payload)
            self.assertIn("growth", payload)

            self.assertEqual(payload.get("inputs", {}).get("z_eval"), [0.0, 1.0, 2.0])
            transfer_samples = payload.get("transfer", {}).get("samples", [])
            self.assertEqual(len(transfer_samples), 3)

            txt = report_txt.read_text(encoding="utf-8")
            self.assertIn("Structure Formation Bridge Report", txt)
            self.assertIn("Transfer (BBKS)", txt)
            self.assertIn("Growth (GR baseline)", txt)

            after = sorted(str(p.relative_to(tmp)) for p in tmp.rglob("*"))
            self.assertTrue(all(path.startswith("out") for path in after), msg=str(after))


if __name__ == "__main__":
    unittest.main()

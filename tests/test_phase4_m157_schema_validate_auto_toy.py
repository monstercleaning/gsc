from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase4_triangle1_sn_bao_planck_thetastar.py"
VALIDATE = ROOT / "scripts" / "phase2_schema_validate.py"


class TestPhase4M157SchemaValidateAutoToy(unittest.TestCase):
    def test_report_schema_auto_validates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            outdir = Path(td) / "out"
            run_proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repo-root",
                    str(ROOT),
                    "--outdir",
                    str(outdir),
                    "--deterministic",
                    "1",
                    "--toy",
                    "1",
                    "--omega-m-steps",
                    "7",
                    "--epsilon-steps",
                    "7",
                    "--integration-n",
                    "256",
                    "--format",
                    "json",
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(run_proc.returncode, 0, msg=(run_proc.stdout or "") + (run_proc.stderr or ""))

            report = outdir / "TRIANGLE1_SN_BAO_PLANCK_REPORT.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "phase4_triangle1_report_v1")

            val_proc = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATE),
                    "--auto",
                    "--schema-dir",
                    str(ROOT / "schemas"),
                    "--json",
                    str(report),
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(val_proc.returncode, 0, msg=(val_proc.stdout or "") + (val_proc.stderr or ""))


if __name__ == "__main__":
    unittest.main()

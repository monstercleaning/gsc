from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase4_desi_bao_epsilon_or_rd_diagnostic.py"
VALIDATE = ROOT / "scripts" / "phase2_schema_validate.py"


class TestPhase4M156SchemaValidateAutoToy(unittest.TestCase):
    def test_report_schema_auto_validates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            outdir = td_path / "out"

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
                    "--format",
                    "json",
                    "--toy",
                    "1",
                    "--omega-m-n",
                    "7",
                    "--epsilon-n",
                    "7",
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(run_proc.returncode, 0, msg=(run_proc.stdout or "") + (run_proc.stderr or ""))

            report = outdir / "DESI_BAO_TRIANGLE1_REPORT.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "phase4_desi_bao_triangle1_report_v1")

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

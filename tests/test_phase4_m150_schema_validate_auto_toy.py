from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase4_pantheon_plus_epsilon_posterior.py"
SCHEMA_VALIDATE = ROOT / "scripts" / "phase2_schema_validate.py"


class TestPhase4M150SchemaValidateAutoToy(unittest.TestCase):
    def test_report_schema_auto_validates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            outdir = Path(td) / "posterior"

            proc_report = subprocess.run(
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
                    "9",
                    "--epsilon-n",
                    "9",
                    "--integration-n",
                    "400",
                ],
                cwd=str(ROOT.parent),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_report.returncode, 0, msg=(proc_report.stdout or "") + (proc_report.stderr or ""))

            report = outdir / "PANTHEON_EPSILON_POSTERIOR_REPORT.json"
            self.assertTrue(report.is_file())
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "phase4_pantheon_plus_epsilon_posterior_report_v2")

            proc_val = subprocess.run(
                [
                    sys.executable,
                    str(SCHEMA_VALIDATE),
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
            self.assertEqual(proc_val.returncode, 0, msg=(proc_val.stdout or "") + (proc_val.stderr or ""))


if __name__ == "__main__":
    unittest.main()

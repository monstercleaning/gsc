from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
M122_SCRIPT = ROOT / "scripts" / "phase3_st_sigmatensor_background_report.py"
M123_SCRIPT = ROOT / "scripts" / "phase3_st_sigmatensor_consistency_report.py"
VALIDATOR = ROOT / "scripts" / "phase2_schema_validate.py"


class TestPhase3M123SigmaTensorSchemaValidateAutoToy(unittest.TestCase):
    def test_auto_schema_validation_for_m122_and_m123_reports(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            out_spec = td_path / "spec"
            out_cons = td_path / "cons"

            proc_spec = subprocess.run(
                [
                    sys.executable,
                    str(M122_SCRIPT),
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
                    str(out_spec),
                    "--format",
                    "json",
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_spec.returncode, 0, msg=(proc_spec.stdout or "") + (proc_spec.stderr or ""))

            proc_cons = subprocess.run(
                [
                    sys.executable,
                    str(M123_SCRIPT),
                    "--H0-km-s-Mpc",
                    "67.4",
                    "--Omega-m",
                    "0.315",
                    "--w0",
                    "-0.95",
                    "--lambda",
                    "0.4",
                    "--z-max",
                    "20",
                    "--n-steps",
                    "512",
                    "--outdir",
                    str(out_cons),
                    "--format",
                    "json",
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_cons.returncode, 0, msg=(proc_cons.stdout or "") + (proc_cons.stderr or ""))

            spec_json = out_spec / "THEORY_SPEC.json"
            cons_json = out_cons / "THEORY_CONSISTENCY_REPORT.json"
            self.assertTrue(spec_json.is_file())
            self.assertTrue(cons_json.is_file())

            for path in (spec_json, cons_json):
                proc_val = subprocess.run(
                    [
                        sys.executable,
                        str(VALIDATOR),
                        "--auto",
                        "--schema-dir",
                        str(ROOT / "schemas"),
                        "--json",
                        str(path),
                        "--format",
                        "text",
                    ],
                    cwd=str(ROOT),
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(
                    proc_val.returncode,
                    0,
                    msg=f"validation failed for {path}: {(proc_val.stdout or '') + (proc_val.stderr or '')}",
                )


if __name__ == "__main__":
    unittest.main()

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SANITY_SCRIPT = ROOT / "scripts" / "phase3_pt_spectra_sanity_report.py"
VALIDATE_SCRIPT = ROOT / "scripts" / "phase2_schema_validate.py"


class TestPhase3M126SchemaValidateAutoToy(unittest.TestCase):
    def test_auto_schema_validation_for_sanity_report(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            run_dir = td_path / "run_dir"
            outdir = td_path / "out"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "cl.dat").write_text(
                "# l TT EE TE\n2 1 1 1\n50 5 1 1\n100 8 2 2\n220 9 3 3\n500 4 1 1\n1000 2 1 1\n",
                encoding="utf-8",
            )

            proc_report = subprocess.run(
                [
                    sys.executable,
                    str(SANITY_SCRIPT),
                    "--path",
                    str(run_dir),
                    "--outdir",
                    str(outdir),
                    "--created-utc",
                    "2000-01-01T00:00:00Z",
                    "--require-tt",
                    "1",
                    "--format",
                    "json",
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_report.returncode, 0, msg=(proc_report.stdout or "") + (proc_report.stderr or ""))

            report_json = outdir / "SPECTRA_SANITY_REPORT.json"
            self.assertTrue(report_json.is_file())

            proc_val = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATE_SCRIPT),
                    "--auto",
                    "--schema-dir",
                    str(ROOT / "schemas"),
                    "--json",
                    str(report_json),
                    "--format",
                    "text",
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc_val.returncode, 0, msg=(proc_val.stdout or "") + (proc_val.stderr or ""))


if __name__ == "__main__":
    unittest.main()


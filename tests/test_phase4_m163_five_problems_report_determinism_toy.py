from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase4_m163_five_problems_report.py"
ABS_TOKENS = ("/Users/", "/home/", "/var/folders/", "C:\\\\Users\\\\")


class TestPhase4M163FiveProblemsReportDeterminismToy(unittest.TestCase):
    def test_deterministic_outputs_and_sigma_scale(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            out_a = td_path / "out_a"
            out_b = td_path / "out_b"

            for outdir in (out_a, out_b):
                proc = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPT),
                        "--outdir",
                        str(outdir),
                        "--format",
                        "json",
                        "--created-utc",
                        "946684800",
                        "--drift-eps",
                        "0.01",
                        "--use-cov",
                        "0",
                    ],
                    cwd=str(ROOT.parent),
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))

            json_a = out_a / "FIVE_PROBLEMS_REPORT.json"
            json_b = out_b / "FIVE_PROBLEMS_REPORT.json"
            md_a = out_a / "FIVE_PROBLEMS_REPORT.md"
            md_b = out_b / "FIVE_PROBLEMS_REPORT.md"

            self.assertEqual(json_a.read_bytes(), json_b.read_bytes())
            self.assertEqual(md_a.read_bytes(), md_b.read_bytes())

            payload = json.loads(json_a.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "phase4_m163_five_problems_report_v1")
            self.assertTrue(bool(payload.get("paths_redacted")))

            n_sigma_R = float(payload.get("summary", {}).get("n_sigma_R"))
            self.assertGreater(n_sigma_R, 10.0)
            self.assertLess(n_sigma_R, 20.0)
            self.assertAlmostEqual(n_sigma_R, 13.0, delta=3.0)

            for token in ABS_TOKENS:
                self.assertNotIn(token, json_a.read_text(encoding="utf-8"))
                self.assertNotIn(token, md_a.read_text(encoding="utf-8"))
            self.assertNotIn(str(td_path.resolve()), json_a.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase4_red_team_check.py"
ABS_TOKENS = ("/Users/", "/home/", "/var/folders/", "C:\\\\Users\\\\")


class TestPhase4M141RedTeamCheckEmitsDeterministicReportToy(unittest.TestCase):
    def test_report_is_deterministic_and_paths_are_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            out_a = td_path / "out_a"
            out_b = td_path / "out_b"

            for outdir in (out_a, out_b):
                proc = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPT),
                        "--repo-root",
                        str(ROOT),
                        "--outdir",
                        str(outdir),
                        "--strict",
                        "1",
                        "--format",
                        "json",
                    ],
                    cwd=str(ROOT.parent),
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))

            json_a = (out_a / "RED_TEAM_REPORT.json").read_bytes()
            json_b = (out_b / "RED_TEAM_REPORT.json").read_bytes()
            md_a = (out_a / "RED_TEAM_REPORT.md").read_bytes()
            md_b = (out_b / "RED_TEAM_REPORT.md").read_bytes()
            self.assertEqual(json_a, json_b)
            self.assertEqual(md_a, md_b)

            report_text = json_a.decode("utf-8")
            self.assertIn('"paths_redacted": true', report_text)
            self.assertIn('"schema": "phase4_red_team_check_report_v1"', report_text)
            self.assertNotIn(str(td_path.resolve()), report_text)
            for token in ABS_TOKENS:
                self.assertNotIn(token, report_text)


if __name__ == "__main__":
    unittest.main()

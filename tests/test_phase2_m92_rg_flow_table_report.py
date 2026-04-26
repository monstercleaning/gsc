import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gsc.rg.flow_table import load_flow_table_csv  # noqa: E402


SCRIPT = ROOT / "scripts" / "phase2_rg_flow_table_report.py"


def _toy_csv_text() -> str:
    return (
        "# external FRG flow toy table\n"
        "k,g,lambda,notes\n"
        "5,1.3,0.20,hi\n"
        "\n"
        "1,0.5,0.10,lo\n"
        "3,0.9,0.15,mid\n"
        "7,1.2,0.22,tail\n"
    )


class TestPhase2M92RGFlowTableReport(unittest.TestCase):
    def test_loader_sort_interpolate_and_kstar(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            csv_path = Path(td) / "flow.csv"
            csv_path.write_text(_toy_csv_text(), encoding="utf-8")

            table = load_flow_table_csv(str(csv_path))
            ks = [row.k for row in table.rows]
            self.assertEqual(ks, [1.0, 3.0, 5.0, 7.0])

            self.assertAlmostEqual(table.g_of_k(2.0), 0.7, places=12)
            self.assertAlmostEqual(table.g_of_k(0.1), 0.5, places=12)
            self.assertAlmostEqual(table.g_of_k(99.0), 1.2, places=12)

            k_star = table.estimate_k_star_by_g_threshold(1.0)
            self.assertEqual(k_star.get("reason"), "crossing")
            self.assertAlmostEqual(float(k_star.get("k_star")), 3.5, places=12)

            summary = table.summary_dict(k_star_threshold=1.0)
            self.assertEqual(summary.get("n_rows"), 4)
            self.assertAlmostEqual(float(summary.get("k_min")), 1.0, places=12)
            self.assertAlmostEqual(float(summary.get("k_max")), 7.0, places=12)
            self.assertAlmostEqual(float(summary.get("g_min")), 0.5, places=12)
            self.assertAlmostEqual(float(summary.get("g_max")), 1.3, places=12)
            self.assertTrue(bool(summary.get("has_lambda")))
            self.assertAlmostEqual(float(summary.get("lambda_min")), 0.1, places=12)
            self.assertAlmostEqual(float(summary.get("lambda_max")), 0.22, places=12)

    def test_cli_json_output_and_invalid_row_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            csv_path = tmp / "flow.csv"
            csv_path.write_text(_toy_csv_text(), encoding="utf-8")

            cmd = [
                sys.executable,
                str(SCRIPT),
                "--input",
                str(csv_path),
                "--format",
                "json",
                "--k-star-g-threshold",
                "1.0",
            ]
            run = subprocess.run(cmd, text=True, capture_output=True, cwd=str(tmp))
            out = (run.stdout or "") + (run.stderr or "")
            self.assertEqual(run.returncode, 0, msg=out)

            payload = json.loads(run.stdout)
            self.assertEqual(payload.get("schema"), "phase2_rg_flow_table_report_v1")
            summary = payload.get("summary") or {}
            k_star = summary.get("k_star") or {}
            self.assertEqual(summary.get("n_rows"), 4)
            self.assertEqual(k_star.get("reason"), "crossing")
            self.assertAlmostEqual(float(k_star.get("k_star")), 3.5, places=12)

            bad_csv = tmp / "bad.csv"
            bad_csv.write_text("k,g\n1,abc\n", encoding="utf-8")
            bad_cmd = [
                sys.executable,
                str(SCRIPT),
                "--input",
                str(bad_csv),
                "--format",
                "json",
            ]
            bad_run = subprocess.run(bad_cmd, text=True, capture_output=True, cwd=str(tmp))
            bad_out = (bad_run.stdout or "") + (bad_run.stderr or "")
            self.assertEqual(bad_run.returncode, 1, msg=bad_out)
            self.assertIn("must be a finite float", bad_out)


if __name__ == "__main__":
    unittest.main()

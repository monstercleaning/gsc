import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M29E2RobustnessCompare(unittest.TestCase):
    def test_compare_by_plan_point_id_with_nested_fields(self):
        script = ROOT / "scripts" / "phase2_e2_robustness_compare.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            jsonl_a = td_path / "scan_a.jsonl"
            jsonl_b = td_path / "scan_b.jsonl"
            out_tsv = td_path / "compare.tsv"

            rows_a = [
                {"schema": "gsc.phase2.e2.scan.v1", "type": "header"},
                {
                    "plan_point_id": 1,
                    "params_hash": "h1",
                    "status": "ok",
                    "chi2_parts": {"cmb": 10.0, "late": 1.0},
                    "numerics": {"method": "adaptive", "n_eval": 120},
                    "robustness": {"recombination": {"method": "fit"}},
                },
                {
                    "plan_point_id": 2,
                    "params_hash": "h2",
                    "status": "ok",
                    "chi2_parts": {"cmb": 20.0, "late": 2.0},
                    "numerics": {"method": "adaptive", "n_eval": 140},
                    "robustness": {"recombination": {"method": "fit"}},
                },
                {
                    "plan_point_id": 3,
                    "params_hash": "h3",
                    "status": "ok",
                    "chi2_parts": {"cmb": 30.0, "late": 3.0},
                    "numerics": {"method": "adaptive", "n_eval": 160},
                    "robustness": {"recombination": {"method": "fit"}},
                },
            ]
            rows_b = [
                {"schema": "gsc.phase2.e2.scan.v1", "type": "header"},
                {
                    "plan_point_id": 1,
                    "params_hash": "h1",
                    "status": "ok",
                    "chi2_parts": {"cmb": 12.0, "late": 1.0},
                    "numerics": {"method": "adaptive", "n_eval": 100},
                    "robustness": {"recombination": {"method": "peebles3"}},
                },
                {
                    "plan_point_id": 2,
                    "params_hash": "h2",
                    "status": "ok",
                    "chi2_parts": {"cmb": 18.0, "late": 2.0},
                    "numerics": {"method": "adaptive", "n_eval": 150},
                    "robustness": {"recombination": {"method": "fit"}},
                },
                {
                    "plan_point_id": 3,
                    "params_hash": "h3",
                    "status": "ok",
                    "chi2_parts": {"cmb": 30.0, "late": 3.0},
                    "numerics": {"method": "adaptive", "n_eval": 160},
                    "robustness": {"recombination": {"method": "fit"}},
                },
            ]

            jsonl_a.write_text(
                "\n".join(
                    [
                        json.dumps(rows_a[0]),
                        "{not-json",
                        json.dumps(rows_a[1]),
                        json.dumps(rows_a[2]),
                        json.dumps(rows_a[3]),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            jsonl_b.write_text(
                "\n".join([json.dumps(r) for r in rows_b]) + "\n",
                encoding="utf-8",
            )

            cmd = [
                sys.executable,
                str(script),
                "--jsonl-a",
                str(jsonl_a),
                "--jsonl-b",
                str(jsonl_b),
                "--out-tsv",
                str(out_tsv),
                "--match-key",
                "plan_point_id",
                "--fields",
                "chi2_parts.cmb,numerics.n_eval,robustness.recombination.method",
            ]
            proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)
            self.assertTrue(out_tsv.is_file())

            with out_tsv.open("r", encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh, delimiter="\t")
                rows = list(reader)
                header = list(reader.fieldnames or [])

            self.assertIn("chi2_parts.cmb_a", header)
            self.assertIn("chi2_parts.cmb_b", header)
            self.assertIn("d_chi2_parts.cmb", header)
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[0]["plan_point_id"], "1")
            self.assertAlmostEqual(float(rows[0]["d_chi2_parts.cmb"]), 2.0, places=12)

    def test_missing_plan_point_id_errors_with_hint(self):
        script = ROOT / "scripts" / "phase2_e2_robustness_compare.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            jsonl_a = td_path / "scan_a.jsonl"
            jsonl_b = td_path / "scan_b.jsonl"
            out_tsv = td_path / "compare.tsv"

            row = {"params_hash": "abc", "status": "ok", "chi2_total": 1.0}
            jsonl_a.write_text(json.dumps(row) + "\n", encoding="utf-8")
            jsonl_b.write_text(json.dumps(row) + "\n", encoding="utf-8")

            cmd = [
                sys.executable,
                str(script),
                "--jsonl-a",
                str(jsonl_a),
                "--jsonl-b",
                str(jsonl_b),
                "--out-tsv",
                str(out_tsv),
                "--match-key",
                "plan_point_id",
                "--fields",
                "chi2_total",
            ]
            proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("Run scans with --plan", output)

    def test_compare_by_params_hash(self):
        script = ROOT / "scripts" / "phase2_e2_robustness_compare.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            jsonl_a = td_path / "scan_a.jsonl"
            jsonl_b = td_path / "scan_b.jsonl"
            out_tsv = td_path / "compare.tsv"

            rows_a = [
                {"params_hash": "aaa", "status": "ok", "chi2_total": 5.0},
                {"params_hash": "bbb", "status": "ok", "chi2_total": 7.0},
            ]
            rows_b = [
                {"params_hash": "aaa", "status": "ok", "chi2_total": 6.5},
                {"params_hash": "bbb", "status": "ok", "chi2_total": 6.0},
            ]
            jsonl_a.write_text("\n".join(json.dumps(r) for r in rows_a) + "\n", encoding="utf-8")
            jsonl_b.write_text("\n".join(json.dumps(r) for r in rows_b) + "\n", encoding="utf-8")

            cmd = [
                sys.executable,
                str(script),
                "--jsonl-a",
                str(jsonl_a),
                "--jsonl-b",
                str(jsonl_b),
                "--out-tsv",
                str(out_tsv),
                "--match-key",
                "params_hash",
                "--fields",
                "chi2_total",
            ]
            proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            with out_tsv.open("r", encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh, delimiter="\t"))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["params_hash_a"], "aaa")
            self.assertAlmostEqual(float(rows[0]["d_chi2_total"]), 1.5, places=12)


if __name__ == "__main__":
    unittest.main()

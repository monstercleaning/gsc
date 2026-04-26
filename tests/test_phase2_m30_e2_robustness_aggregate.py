import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M30E2RobustnessAggregate(unittest.TestCase):
    def _write_jsonl(self, path: Path, rows):
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    def test_aggregate_union_outputs_and_refine_plan(self):
        script = ROOT / "scripts" / "phase2_e2_robustness_aggregate.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            run_a = td_path / "run_a.jsonl"
            run_b = td_path / "run_b.jsonl"
            run_c = td_path / "run_c.jsonl"
            out_dir = td_path / "out"

            self._write_jsonl(
                run_a,
                [
                    json.dumps({"type": "header", "schema": "gsc.phase2.e2.scan.v1"}),
                    "{invalid-json",
                    json.dumps(
                        {
                            "params_hash": "hash_a",
                            "status": "ok",
                            "chi2_total": 12.0,
                            "chi2_cmb": 8.0,
                            "drift_pass": True,
                            "microphysics_plausible_ok": True,
                            "microphysics_penalty": 0.0,
                            "microphysics_max_rel_dev": 0.0,
                            "params": {"H0": 67.0, "Omega_m": 0.31},
                        }
                    ),
                    json.dumps(
                        {
                            "params_hash": "hash_b",
                            "status": "ok",
                            "chi2_total": 9.0,
                            "chi2_parts": {"cmb": {"chi2": 2.0}},
                            "drift_pass": False,
                            "microphysics_plausible_ok": False,
                            "microphysics_penalty": 10.0,
                            "microphysics_max_rel_dev": 0.2,
                            "params": {"H0": 66.0, "Omega_m": 0.33},
                        }
                    ),
                    json.dumps(
                        {
                            "params_hash": "hash_c",
                            "status": "ok",
                            "chi2_total": 5.0,
                            "chi2_cmb": 1.0,
                            "drift": {"min_z_dot": 1.0e-12},
                            "microphysics_plausible_ok": True,
                            "microphysics_penalty": 0.0,
                            "params": {"H0": 65.0, "Omega_m": 0.29},
                        }
                    ),
                    json.dumps(
                        {
                            "params_hash": "hash_d",
                            "status": "error",
                            "chi2_total": 100.0,
                            "chi2_cmb": 50.0,
                            "params": {"H0": 70.0, "Omega_m": 0.3},
                        }
                    ),
                    json.dumps(
                        {
                            "params_hash": "hash_d",
                            "status": "ok",
                            "chi2_total": 4.0,
                            "chi2_cmb": 3.0,
                            "drift_pass": True,
                            "params": {"H0": 70.0, "Omega_m": 0.3},
                        }
                    ),
                    json.dumps(
                        {
                            "params_hash": "hash_d",
                            "status": "ok",
                            "chi2_total": 6.0,
                            "chi2_cmb": 5.0,
                            "drift_pass": True,
                            "params": {"H0": 70.0, "Omega_m": 0.3},
                        }
                    ),
                    json.dumps({"status": "ok", "chi2_total": 1.0}),
                ],
            )

            self._write_jsonl(
                run_b,
                [
                    json.dumps({"type": "header", "schema": "gsc.phase2.e2.scan.v1"}),
                    json.dumps(
                        {
                            "params_hash": "hash_a",
                            "status": "ok",
                            "chi2_total": 12.3,
                            "chi2_cmb": 8.1,
                            "drift_pass": True,
                            "microphysics_plausible_ok": True,
                            "microphysics_penalty": 0.1,
                            "params": {"H0": 67.0, "Omega_m": 0.31},
                        }
                    ),
                    json.dumps(
                        {
                            "params_hash": "hash_b",
                            "status": "ok",
                            "chi2_total": 13.0,
                            "chi2_cmb": 7.0,
                            "drift_pass": False,
                            "microphysics_plausible_ok": False,
                            "microphysics_penalty": 11.0,
                            "params": {"H0": 66.0, "Omega_m": 0.33},
                        }
                    ),
                ],
            )

            self._write_jsonl(
                run_c,
                [
                    json.dumps({"type": "header", "schema": "gsc.phase2.e2.scan.v1"}),
                    json.dumps(
                        {
                            "params_hash": "hash_a",
                            "status": "ok",
                            "chi2_total": 12.1,
                            "chi2_cmb": 8.2,
                            "drift_pass": True,
                            "microphysics_plausible_ok": True,
                            "microphysics_penalty": 0.05,
                            "params": {"H0": 67.0, "Omega_m": 0.31},
                        }
                    ),
                    json.dumps(
                        {
                            "params_hash": "hash_b",
                            "status": "ok",
                            "chi2_total": 14.0,
                            "chi2_cmb": 8.5,
                            "drift_pass": False,
                            "microphysics_plausible_ok": False,
                            "microphysics_penalty": 12.0,
                            "params": {"H0": 66.0, "Omega_m": 0.33},
                        }
                    ),
                ],
            )

            cmd = [
                sys.executable,
                str(script),
                "--jsonl",
                str(run_a),
                "--jsonl",
                str(run_b),
                "--jsonl",
                str(run_c),
                "--label",
                "runA",
                "--label",
                "runB",
                "--label",
                "runC",
                "--outdir",
                str(out_dir),
                "--top-n",
                "5",
                "--emit-refine-plan",
                "refine_plan.json",
            ]
            proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            out_csv = out_dir / "robustness_aggregate.csv"
            out_md = out_dir / "robustness_aggregate.md"
            out_meta = out_dir / "robustness_aggregate_meta.json"
            out_plan = out_dir / "refine_plan.json"
            self.assertTrue(out_csv.is_file())
            self.assertTrue(out_md.is_file())
            self.assertTrue(out_meta.is_file())
            self.assertTrue(out_plan.is_file())

            with out_csv.open("r", encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(len(rows), 4)
            by_hash = {row["params_hash"]: row for row in rows}
            self.assertEqual(set(by_hash.keys()), {"hash_a", "hash_b", "hash_c", "hash_d"})

            self.assertEqual(by_hash["hash_a"]["robust_ok"], "true")
            self.assertEqual(by_hash["hash_b"]["robust_ok"], "false")
            self.assertEqual(by_hash["hash_d"]["chi2_total__runA"], "4")

            meta = json.loads(out_meta.read_text(encoding="utf-8"))
            self.assertEqual(meta["schema"], "phase2_e2_robustness_aggregate_v1")
            self.assertEqual(int(meta["counts"]["n_union"]), 4)
            self.assertEqual(int(meta["counts"]["n_intersection"]), 2)
            self.assertEqual(int(meta["counts"]["n_robust_ok"]), 1)
            self.assertGreaterEqual(int(meta["inputs"][0]["n_skipped_missing_hash"]), 1)
            self.assertEqual(int(meta["inputs"][0]["n_dupe_hash"]), 1)

            plan = json.loads(out_plan.read_text(encoding="utf-8"))
            self.assertEqual(plan["plan_version"], "phase2_e2_refine_plan_v1")
            self.assertEqual(len(plan.get("points", [])), 1)
            self.assertEqual(plan["points"][0]["seed_params_hash"], "hash_a")

    def test_require_common_filters_to_intersection(self):
        script = ROOT / "scripts" / "phase2_e2_robustness_aggregate.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            run_a = td_path / "run_a.jsonl"
            run_b = td_path / "run_b.jsonl"
            out_dir = td_path / "out"

            self._write_jsonl(
                run_a,
                [
                    json.dumps({"params_hash": "x", "status": "ok", "chi2_total": 1.0, "chi2_cmb": 1.2, "drift_pass": True}),
                    json.dumps({"params_hash": "y", "status": "ok", "chi2_total": 2.0, "chi2_cmb": 2.2, "drift_pass": False}),
                    json.dumps({"params_hash": "z", "status": "ok", "chi2_total": 3.0, "chi2_cmb": 3.2, "drift_pass": True}),
                ],
            )
            self._write_jsonl(
                run_b,
                [
                    json.dumps({"params_hash": "x", "status": "ok", "chi2_total": 1.1, "chi2_cmb": 1.3, "drift_pass": True}),
                    json.dumps({"params_hash": "y", "status": "ok", "chi2_total": 2.1, "chi2_cmb": 2.3, "drift_pass": False}),
                ],
            )

            cmd = [
                sys.executable,
                str(script),
                "--jsonl",
                str(run_a),
                "--jsonl",
                str(run_b),
                "--outdir",
                str(out_dir),
                "--require-common",
            ]
            proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            out_csv = out_dir / "robustness_aggregate.csv"
            self.assertTrue(out_csv.is_file())
            with out_csv.open("r", encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))

            self.assertEqual(len(rows), 2)
            hashes = {row["params_hash"] for row in rows}
            self.assertEqual(hashes, {"x", "y"})


if __name__ == "__main__":
    unittest.main()

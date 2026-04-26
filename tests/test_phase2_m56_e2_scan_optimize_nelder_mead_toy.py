import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M56E2ScanOptimizeNelderMeadToy(unittest.TestCase):
    def _write_plan(self, path: Path) -> None:
        payload = {
            "plan_version": "phase2_e2_refine_plan_v1",
            "source": {"jsonl_sha256": "m56toyseed"},
            "points": [
                {
                    "point_id": "seed0",
                    "params": {
                        "H0": 71.0,
                        "Omega_m": 0.40,
                    },
                }
            ],
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _run_scan(self, *, plan: Path, out_dir: Path, optimize: bool) -> subprocess.CompletedProcess:
        script = ROOT / "scripts" / "phase2_e2_scan.py"
        cmd = [
            sys.executable,
            str(script),
            "--model",
            "lcdm",
            "--toy",
            "--plan",
            str(plan),
            "--jobs",
            "1",
            "--out-dir",
            str(out_dir),
        ]
        if optimize:
            cmd.extend(
                [
                    "--optimize",
                    "nelder_mead",
                    "--opt-objective-key",
                    "chi2_total",
                    "--opt-max-eval",
                    "80",
                    "--opt-step-frac",
                    "0.1",
                ]
            )
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def _load_single_row(self, path: Path) -> dict:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(rows), 1)
        return rows[0]

    def test_optimize_nelder_mead_toy_plan_improves_and_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            plan = td_path / "plan.json"
            self._write_plan(plan)

            out_seed = td_path / "seed"
            out_opt_1 = td_path / "opt_1"
            out_opt_2 = td_path / "opt_2"

            proc_seed = self._run_scan(plan=plan, out_dir=out_seed, optimize=False)
            seed_output = (proc_seed.stdout or "") + (proc_seed.stderr or "")
            self.assertEqual(proc_seed.returncode, 0, msg=seed_output)
            seed_row = self._load_single_row(out_seed / "e2_scan_points.jsonl")
            seed_obj = float(seed_row.get("chi2_total"))
            self.assertEqual(seed_row.get("status"), "ok")

            proc_opt_1 = self._run_scan(plan=plan, out_dir=out_opt_1, optimize=True)
            opt_output_1 = (proc_opt_1.stdout or "") + (proc_opt_1.stderr or "")
            self.assertEqual(proc_opt_1.returncode, 0, msg=opt_output_1)
            opt_row_1 = self._load_single_row(out_opt_1 / "e2_scan_points.jsonl")

            refine_meta = opt_row_1.get("refine_meta") or {}
            self.assertEqual(refine_meta.get("method"), "nelder_mead")
            self.assertEqual(refine_meta.get("objective_key"), "chi2_total")

            best_obj = float(refine_meta.get("best_objective", opt_row_1.get("chi2_total")))
            seed_obj_from_meta = float(refine_meta.get("seed_objective", seed_obj))
            self.assertLessEqual(best_obj, seed_obj_from_meta + 1e-12)
            self.assertLessEqual(best_obj, seed_obj + 1e-12)

            params = opt_row_1.get("params") or {}
            self.assertGreaterEqual(float(params.get("H0")), 40.0)
            self.assertLessEqual(float(params.get("H0")), 100.0)
            self.assertGreaterEqual(float(params.get("Omega_m")), 0.05)
            self.assertLessEqual(float(params.get("Omega_m")), 0.95)

            proc_opt_2 = self._run_scan(plan=plan, out_dir=out_opt_2, optimize=True)
            opt_output_2 = (proc_opt_2.stdout or "") + (proc_opt_2.stderr or "")
            self.assertEqual(proc_opt_2.returncode, 0, msg=opt_output_2)

            jsonl_1 = out_opt_1 / "e2_scan_points.jsonl"
            jsonl_2 = out_opt_2 / "e2_scan_points.jsonl"
            self.assertEqual(jsonl_1.read_bytes(), jsonl_2.read_bytes())


if __name__ == "__main__":
    unittest.main()

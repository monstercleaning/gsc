import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M112MultistartDeterminismToy(unittest.TestCase):
    def _write_plan(self, path: Path) -> None:
        payload = {
            "plan_version": "phase2_e2_refine_plan_v1",
            "source": {"jsonl_sha256": "m112_multistart_toy"},
            "points": [
                {
                    "point_id": "seed0",
                    "params": {
                        "H0": 70.8,
                        "Omega_m": 0.39,
                    },
                }
            ],
        }
        path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    def _run_scan(self, *, plan_path: Path, out_dir: Path) -> subprocess.CompletedProcess[str]:
        script = ROOT / "scripts" / "phase2_e2_scan.py"
        cmd = [
            sys.executable,
            str(script),
            "--model",
            "lcdm",
            "--toy",
            "--plan",
            str(plan_path),
            "--optimize",
            "nelder_mead",
            "--opt-objective-key",
            "chi2_total",
            "--opt-max-eval",
            "80",
            "--opt-step-frac",
            "0.1",
            "--opt-multistart",
            "3",
            "--opt-init",
            "latin_hypercube",
            "--opt-seed",
            "17",
            "--jobs",
            "1",
            "--out-dir",
            str(out_dir),
        ]
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def _load_single_row(self, path: Path) -> dict:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(rows), 1)
        return rows[0]

    def test_multistart_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            plan = base / "plan.json"
            self._write_plan(plan)

            out_a = base / "out_a"
            out_b = base / "out_b"

            proc_a = self._run_scan(plan_path=plan, out_dir=out_a)
            msg_a = (proc_a.stdout or "") + (proc_a.stderr or "")
            self.assertEqual(proc_a.returncode, 0, msg=msg_a)

            proc_b = self._run_scan(plan_path=plan, out_dir=out_b)
            msg_b = (proc_b.stdout or "") + (proc_b.stderr or "")
            self.assertEqual(proc_b.returncode, 0, msg=msg_b)

            jsonl_a = out_a / "e2_scan_points.jsonl"
            jsonl_b = out_b / "e2_scan_points.jsonl"
            self.assertEqual(jsonl_a.read_bytes(), jsonl_b.read_bytes())

            row_a = self._load_single_row(jsonl_a)
            row_b = self._load_single_row(jsonl_b)
            self.assertEqual(row_a.get("opt_multistart"), 3)
            self.assertEqual(row_a.get("opt_seed"), 17)
            self.assertEqual(row_a.get("opt_init"), "latin_hypercube")
            self.assertIsInstance(row_a.get("opt_best_start_index"), int)
            self.assertGreaterEqual(int(row_a.get("opt_best_start_index")), 0)
            self.assertLess(int(row_a.get("opt_best_start_index")), 3)
            self.assertEqual(row_a.get("opt_best_start_index"), row_b.get("opt_best_start_index"))
            self.assertEqual(row_a.get("params"), row_b.get("params"))


if __name__ == "__main__":
    unittest.main()


import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M112BBNPriorFieldPresentToy(unittest.TestCase):
    def _write_plan(self, path: Path) -> None:
        payload = {
            "plan_version": "phase2_e2_refine_plan_v1",
            "source": {"jsonl_sha256": "m112_bbn_toy"},
            "points": [
                {
                    "point_id": "seed0",
                    "params": {
                        "H0": 67.4,
                        "Omega_m": 0.315,
                        "omega_b_h2": 0.02237,
                        "omega_c_h2": 0.12,
                    },
                }
            ],
        }
        path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    def test_bbn_prior_adds_numeric_field(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            plan = base / "plan.json"
            out_dir = base / "out"
            self._write_plan(plan)

            script = ROOT / "scripts" / "phase2_e2_scan.py"
            cmd = [
                sys.executable,
                str(script),
                "--model",
                "lcdm",
                "--toy",
                "--plan",
                str(plan),
                "--bbn-prior",
                "standard",
                "--jobs",
                "1",
                "--out-dir",
                str(out_dir),
            ]
            proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            rows = [
                json.loads(line)
                for line in (out_dir / "e2_scan_points.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertIn("chi2_bbn", row)
            self.assertIsInstance(row.get("chi2_bbn"), (int, float))
            self.assertGreaterEqual(float(row.get("chi2_bbn")), 0.0)
            chi2_parts = row.get("chi2_parts") or {}
            self.assertIn("bbn", chi2_parts)
            self.assertTrue(bool((chi2_parts.get("bbn") or {}).get("enabled")))


if __name__ == "__main__":
    unittest.main()


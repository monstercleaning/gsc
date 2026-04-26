import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_e2_live_status.py"


class TestPhase2M89E2LiveStatusRsdSection(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        cmd = [sys.executable, str(SCRIPT), *args]
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def test_json_output_has_rsd_overlay_section(self) -> None:
        self.assertTrue(SCRIPT.is_file())
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            jsonl = tdp / "scan.jsonl"
            rows = [
                {
                    "status": "ok",
                    "params_hash": "m89_p0",
                    "plan_point_id": "p0",
                    "chi2_total": 5.0,
                    "rsd_overlay_ok": True,
                    "rsd_chi2": 3.5,
                    "rsd_sigma8_0_best": 0.79,
                    "rsd_n": 22,
                    "rsd_transfer_model": "bbks",
                },
                {
                    "status": "ok",
                    "params_hash": "m89_p1",
                    "plan_point_id": "p1",
                    "chi2_total": 4.0,
                    "rsd_overlay_ok": True,
                    "rsd_chi2": 1.25,
                    "rsd_sigma8_0_best": 0.81,
                    "rsd_n": 22,
                    "rsd_transfer_model": "eh98_nowiggle",
                    "rsd_primordial_ns": 0.965,
                    "rsd_primordial_k_pivot_mpc": 0.05,
                },
                {
                    "status": "error",
                    "params_hash": "m89_p2",
                    "chi2_total": 9.0,
                },
            ]
            jsonl.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")

            proc = self._run("--input", str(jsonl), "--format", "json")
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)
            payload = json.loads(proc.stdout)

            rsd = payload.get("rsd_overlay") or {}
            self.assertEqual(int(rsd.get("present_records", -1)), 2)
            self.assertEqual(int(rsd.get("ok_records", -1)), 2)
            self.assertAlmostEqual(float(rsd.get("best_chi2")), 1.25, places=12)
            self.assertAlmostEqual(float(rsd.get("best_chi2_total")), 4.0, places=12)
            self.assertEqual(str(rsd.get("best_params_hash")), "m89_p1")
            self.assertEqual(str(rsd.get("best_plan_point_id")), "p1")
            self.assertEqual(str(rsd.get("best_transfer_model")), "eh98_nowiggle")
            self.assertAlmostEqual(float(rsd.get("best_primordial_ns")), 0.965, places=12)
            self.assertAlmostEqual(float(rsd.get("best_primordial_k_pivot_mpc")), 0.05, places=12)
            counts = rsd.get("transfer_model_counts") or {}
            self.assertEqual(int(counts.get("bbks", 0)), 1)
            self.assertEqual(int(counts.get("eh98_nowiggle", 0)), 1)


if __name__ == "__main__":
    unittest.main()

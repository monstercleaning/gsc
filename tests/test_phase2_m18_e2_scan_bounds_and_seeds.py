import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.optional_deps import has_numpy  # noqa: E402


class TestPhase2M18E2ScanBoundsAndSeeds(unittest.TestCase):
    def _write_priors(self, path: Path) -> None:
        from gsc.early_time import compute_lcdm_distance_priors  # local import (numpy-tier)

        pred = compute_lcdm_distance_priors(
            H0_km_s_Mpc=67.4,
            Omega_m=0.315,
            omega_b_h2=0.02237,
            omega_c_h2=0.1200,
            N_eff=3.046,
            Tcmb_K=2.7255,
        )
        lines = ["name,value,sigma"]
        lines.append(f"100theta_star,{100.0 * float(pred['theta_star']):.16g},1e-3")
        lines.append(f"R,{float(pred['R']):.16g},1e-3")
        lines.append(f"lA,{float(pred['lA']):.16g},1e-2")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_scan_honors_bounds_json_and_evaluates_seed_points_first(self):
        if not has_numpy():
            self.skipTest("numpy not installed (skipping numpy-tier test)")

        script = ROOT / "scripts" / "phase2_e2_scan.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            priors_csv = td_path / "cmb.csv"
            out_dir = td_path / "out"
            bounds_json = td_path / "bounds.json"
            seeds_jsonl = td_path / "seeds.jsonl"
            self._write_priors(priors_csv)

            bounds_payload = {
                "schema": "gsc.phase2.e2.refine_bounds.v1",
                "bounds": {
                    "H0": {"min": 67.2, "max": 67.6},
                    "Omega_m": {"min": 0.305, "max": 0.320},
                },
            }
            bounds_json.write_text(json.dumps(bounds_payload, sort_keys=True) + "\n", encoding="utf-8")

            seed_rows = [
                {"sample_id": "s1", "params": {"H0": 67.25, "Omega_m": 0.307}},
                {"sample_id": "s2", "params": {"H0": 67.55, "Omega_m": 0.319}},
            ]
            seeds_jsonl.write_text("\n".join(json.dumps(r, sort_keys=True) for r in seed_rows) + "\n", encoding="utf-8")

            cmd = [
                sys.executable,
                str(script),
                "--model",
                "lcdm",
                "--sampler",
                "random",
                "--n-samples",
                "2",
                "--seed",
                "19",
                "--grid",
                "H0=67.0:68.0",
                "--grid",
                "Omega_m=0.30:0.33",
                "--bounds-json",
                str(bounds_json),
                "--seed-points-jsonl",
                str(seeds_jsonl),
                "--cmb",
                str(priors_csv),
                "--omega-b-h2",
                "0.02237",
                "--omega-c-h2",
                "0.1200",
                "--Neff",
                "3.046",
                "--Tcmb-K",
                "2.7255",
                "--out-dir",
                str(out_dir),
            ]
            proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            jsonl_path = out_dir / "e2_scan_points.jsonl"
            summary_path = out_dir / "e2_scan_summary.json"
            self.assertTrue(jsonl_path.is_file())
            self.assertTrue(summary_path.is_file())

            rows = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertGreaterEqual(len(rows), 3)

            first_sampler = (rows[0].get("sampler") or {}).get("detail") or {}
            self.assertTrue(bool(first_sampler.get("seed_point")))

            seen_seed_params = [{"H0": float(r["params"]["H0"]), "Omega_m": float(r["params"]["Omega_m"])} for r in rows[:2]]
            self.assertIn({"H0": 67.25, "Omega_m": 0.307}, seen_seed_params)

            for row in rows:
                p = row.get("params") or {}
                h0 = float(p["H0"])
                om = float(p["Omega_m"])
                self.assertGreaterEqual(h0, 67.2)
                self.assertLessEqual(h0, 67.6)
                self.assertGreaterEqual(om, 0.305)
                self.assertLessEqual(om, 0.320)

            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            sampler_cfg = (summary.get("config") or {}).get("sampler_config") or {}
            self.assertEqual(int(sampler_cfg.get("seed_points_loaded", -1)), 2)
            self.assertGreaterEqual(int(sampler_cfg.get("seed_points_used", -1)), 1)


if __name__ == "__main__":
    unittest.main()

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.optional_deps import skip_module_unless_numpy  # noqa: E402

skip_module_unless_numpy("numpy not installed (skipping numpy-tier tests)")

from gsc.early_time import compute_lcdm_distance_priors  # noqa: E402


class TestPhase2M20E2ScanIntegratorFlag(unittest.TestCase):
    def _write_priors(self, path: Path) -> None:
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

    def test_scan_records_integrator_metadata(self):
        script = ROOT / "scripts" / "phase2_e2_scan.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            priors_csv = td_path / "cmb.csv"
            out_dir = td_path / "out"
            self._write_priors(priors_csv)

            cmd = [
                sys.executable,
                str(script),
                "--model",
                "lcdm",
                "--sampler",
                "random",
                "--n-samples",
                "3",
                "--seed",
                "11",
                "--integrator",
                "adaptive_simpson",
                "--grid",
                "H0=67.0:68.0",
                "--grid",
                "Omega_m=0.30:0.33",
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
            self.assertTrue(jsonl_path.is_file())
            rows = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(rows), 3)
            for row in rows:
                self.assertEqual(row.get("integrator"), "adaptive_simpson")
                early = row.get("early_time") or {}
                self.assertEqual(early.get("integrator"), "adaptive_simpson")

            summary = json.loads((out_dir / "e2_scan_summary.json").read_text(encoding="utf-8"))
            cfg = summary.get("config") or {}
            self.assertEqual(cfg.get("integrator"), "adaptive_simpson")


if __name__ == "__main__":
    unittest.main()

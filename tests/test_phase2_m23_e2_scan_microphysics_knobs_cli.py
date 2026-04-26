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


class TestPhase2M23E2ScanMicrophysicsKnobsCLI(unittest.TestCase):
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
        lines.append("omega_b_h2,0.02237,5e-4")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _run_scan(self, *, priors_csv: Path, out_dir: Path, microphysics: str, extra: list[str]) -> subprocess.CompletedProcess[str]:
        script = ROOT / "scripts" / "phase2_e2_scan.py"
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
            "23",
            "--grid",
            "H0=67.0:67.4",
            "--grid",
            "Omega_m=0.30:0.32",
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
            "--microphysics",
            str(microphysics),
            "--out-dir",
            str(out_dir),
        ] + list(extra)
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def test_scan_microphysics_modes_and_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            priors_csv = td_path / "cmb.csv"
            out_none = td_path / "out_none"
            out_knobs = td_path / "out_knobs"
            self._write_priors(priors_csv)

            proc_none = self._run_scan(priors_csv=priors_csv, out_dir=out_none, microphysics="none", extra=[])
            output_none = (proc_none.stdout or "") + (proc_none.stderr or "")
            self.assertEqual(proc_none.returncode, 0, msg=output_none)

            proc_knobs = self._run_scan(
                priors_csv=priors_csv,
                out_dir=out_knobs,
                microphysics="knobs",
                extra=[
                    "--z-star-scale-min",
                    "1.01",
                    "--z-star-scale-max",
                    "1.01",
                    "--r-s-scale-min",
                    "0.99",
                    "--r-s-scale-max",
                    "0.99",
                    "--r-d-scale-min",
                    "1.02",
                    "--r-d-scale-max",
                    "1.02",
                ],
            )
            output_knobs = (proc_knobs.stdout or "") + (proc_knobs.stderr or "")
            self.assertEqual(proc_knobs.returncode, 0, msg=output_knobs)

            rows_none = [
                json.loads(line)
                for line in (out_none / "e2_scan_points.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            rows_knobs = [
                json.loads(line)
                for line in (out_knobs / "e2_scan_points.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(rows_none), 3)
            self.assertEqual(len(rows_knobs), 3)

            for row in rows_none:
                micro = row.get("microphysics") or {}
                self.assertEqual(micro.get("mode"), "none")
                self.assertAlmostEqual(float(micro.get("z_star_scale")), 1.0, places=12)
                self.assertAlmostEqual(float(micro.get("r_s_scale")), 1.0, places=12)
                self.assertAlmostEqual(float(micro.get("r_d_scale")), 1.0, places=12)
                self.assertIn("microphysics_knobs", row)
                self.assertIn("microphysics_plausible_ok", row)
                self.assertIn("microphysics_penalty", row)
                self.assertIn("microphysics_max_rel_dev", row)
                self.assertIn("microphysics_notes", row)
                self.assertTrue(bool(row["microphysics_plausible_ok"]))
                self.assertAlmostEqual(float(row["microphysics_penalty"]), 0.0, places=12)
                self.assertAlmostEqual(float(row["microphysics_max_rel_dev"]), 0.0, places=12)
                self.assertEqual(list(row["microphysics_notes"]), [])

            for row in rows_knobs:
                micro = row.get("microphysics") or {}
                self.assertEqual(micro.get("mode"), "knobs")
                self.assertAlmostEqual(float(micro.get("z_star_scale")), 1.01, places=12)
                self.assertAlmostEqual(float(micro.get("r_s_scale")), 0.99, places=12)
                self.assertAlmostEqual(float(micro.get("r_d_scale")), 1.02, places=12)
                self.assertIn("microphysics_knobs", row)
                self.assertIn("microphysics_plausible_ok", row)
                self.assertIn("microphysics_penalty", row)
                self.assertIn("microphysics_max_rel_dev", row)
                self.assertIn("microphysics_notes", row)
                self.assertTrue(bool(row["microphysics_plausible_ok"]))
                self.assertAlmostEqual(float(row["microphysics_penalty"]), 0.0, places=12)
                self.assertGreaterEqual(float(row["microphysics_max_rel_dev"]), 0.0)

            summary_none = json.loads((out_none / "e2_scan_summary.json").read_text(encoding="utf-8"))
            summary_knobs = json.loads((out_knobs / "e2_scan_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary_none["config"]["microphysics_mode"], "none")
            self.assertEqual(summary_knobs["config"]["microphysics_mode"], "knobs")
            self.assertNotEqual(
                summary_none["config"]["sampler_config"]["microphysics_mode"],
                summary_knobs["config"]["sampler_config"]["microphysics_mode"],
            )


if __name__ == "__main__":
    unittest.main()

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

from gsc.early_time.cmb_shift_params import compute_lcdm_shift_params  # noqa: E402


def _write_priors(path: Path, rows: list[tuple[str, float, float]]) -> None:
    lines = ["name,value,sigma"]
    for name, value, sigma in rows:
        lines.append(f"{name},{value:.16g},{sigma:.16g}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestEarlyTimeCMBPriorsCLI(unittest.TestCase):
    def test_cli_writes_json_and_csv_reports(self):
        script = ROOT / "scripts" / "early_time_cmb_priors_chi2.py"
        self.assertTrue(script.is_file())

        pred = compute_lcdm_shift_params(
            H0_km_s_Mpc=67.4,
            Omega_m=0.315,
            omega_b_h2=0.02237,
            omega_c_h2=0.1200,
            N_eff=3.046,
            Tcmb_K=2.7255,
        )
        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            csv_path = td_p / "cmb.csv"
            out_root = td_p / "out"
            _write_priors(
                csv_path,
                [
                    ("theta_star", float(pred["theta_star"]), 1e-5),
                    ("R", float(pred["R"]), 1e-3),
                ],
            )

            cmd = [
                sys.executable,
                str(script),
                "--cmb",
                str(csv_path),
                "--omega-b-h2",
                "0.02237",
                "--omega-c-h2",
                "0.1200",
                "--out-dir",
                str(out_root),
            ]
            proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
            out = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=out)

            report = out_root / "early_time" / "cmb_priors_report.json"
            table = out_root / "early_time" / "cmb_priors_table.csv"
            self.assertTrue(report.is_file())
            self.assertTrue(table.is_file())
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertAlmostEqual(float(payload["result"]["chi2"]), 0.0, places=10)
            self.assertEqual(int(payload["result"]["ndof"]), 2)

    def test_cli_supports_alias_key_100theta_star(self):
        script = ROOT / "scripts" / "early_time_cmb_priors_chi2.py"
        self.assertTrue(script.is_file())

        pred = compute_lcdm_shift_params(
            H0_km_s_Mpc=67.4,
            Omega_m=0.315,
            omega_b_h2=0.02237,
            omega_c_h2=0.1200,
            N_eff=3.046,
            Tcmb_K=2.7255,
        )
        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            csv_path = td_p / "cmb.csv"
            out_root = td_p / "out"
            _write_priors(
                csv_path,
                [
                    ("100theta_star", 100.0 * float(pred["theta_star"]), 1e-3),
                ],
            )

            cmd = [
                sys.executable,
                str(script),
                "--cmb",
                str(csv_path),
                "--omega-b-h2",
                "0.02237",
                "--omega-c-h2",
                "0.1200",
                "--out-dir",
                str(out_root),
            ]
            proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
            out = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=out)

            report = out_root / "early_time" / "cmb_priors_report.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertAlmostEqual(float(payload["result"]["chi2"]), 0.0, places=10)
            self.assertIn("100theta_star", payload["predicted"])


if __name__ == "__main__":
    unittest.main()

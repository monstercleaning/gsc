import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_sf_fsigma8_report.py"


class TestPhase2M91SFFSigma8ReportNsCliToy(unittest.TestCase):
    def _run_json(self, args: list[str], cwd: Path) -> dict:
        cmd = [sys.executable, str(SCRIPT), *args, "--format", "json"]
        run = subprocess.run(cmd, text=True, capture_output=True, cwd=str(cwd))
        out = (run.stdout or "") + (run.stderr or "")
        self.assertEqual(run.returncode, 0, msg=out)
        return json.loads(run.stdout)

    def test_ns_and_kpivot_are_reported_and_defaults_stay_stable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            common = [
                "--history",
                "lcdm",
                "--H0",
                "70",
                "--Omega-m",
                "0.3",
                "--Omega-lambda",
                "0.7",
                "--sigma8-mode",
                "derived_As",
                "--As",
                "2.1e-9",
                "--kmin",
                "1e-4",
                "--kmax",
                "1e1",
                "--nk",
                "768",
                "--z-start",
                "80",
                "--n-steps",
                "3200",
            ]

            payload_default = self._run_json(common, tmp)
            sigma_meta_default = payload_default.get("sigma8") or {}
            self.assertEqual(float(sigma_meta_default.get("primordial_ns")), 1.0)
            self.assertAlmostEqual(float(sigma_meta_default.get("primordial_k_pivot_mpc")), 0.05, delta=1.0e-15)

            payload_explicit = self._run_json(common + ["--ns", "1.0", "--k-pivot", "0.05"], tmp)
            sigma_meta_explicit = payload_explicit.get("sigma8") or {}
            self.assertAlmostEqual(
                float(sigma_meta_default.get("sigma8_0")),
                float(sigma_meta_explicit.get("sigma8_0")),
                delta=1.0e-12,
            )

            payload_tilted = self._run_json(common + ["--ns", "0.97", "--k-pivot", "0.05"], tmp)
            sigma_meta_tilted = payload_tilted.get("sigma8") or {}
            self.assertEqual(float(sigma_meta_tilted.get("primordial_ns")), 0.97)
            self.assertAlmostEqual(float(sigma_meta_tilted.get("primordial_k_pivot_mpc")), 0.05, delta=1.0e-15)
            self.assertNotEqual(
                float(sigma_meta_default.get("sigma8_0")),
                float(sigma_meta_tilted.get("sigma8_0")),
            )


if __name__ == "__main__":
    unittest.main()

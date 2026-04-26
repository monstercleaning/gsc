from pathlib import Path
import hashlib
import json
import math
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase4_epsilon_sensitivity_matrix_toy.py"
ABS_TOKENS = ("/Users/", "/home/", "/var/folders/", "C:\\\\Users\\\\")


class TestPhase4M149EpsilonSensitivityDeterminismToy(unittest.TestCase):
    def test_report_is_deterministic_and_self_check_passes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            out_a = td_path / "out_a"
            out_b = td_path / "out_b"

            base_args = [
                sys.executable,
                str(SCRIPT),
                "--repo-root",
                str(ROOT),
                "--deterministic",
                "1",
                "--created-utc",
                "946684800",
                "--format",
                "json",
                "--epsilon-em",
                "0.01",
                "--epsilon-qcd",
                "-0.02",
                "--epsilon-gr",
                "0.03",
                "--delta-eps",
                "1e-4",
                "--z-sn-pivot",
                "0.1",
                "--z-bao-pivot",
                "0.6",
                "--z-cmb-pivot",
                "1100.0",
                "--z-lensing-pivot",
                "0.5",
                "--h-exponent-p",
                "1.0",
                "--growth-exponent-gamma",
                "1.0",
            ]

            for outdir in (out_a, out_b):
                proc = subprocess.run(
                    [*base_args, "--outdir", str(outdir)],
                    cwd=str(ROOT.parent),
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))

            json_a = out_a / "EPSILON_SENSITIVITY_MATRIX_TOY.json"
            json_b = out_b / "EPSILON_SENSITIVITY_MATRIX_TOY.json"
            md_a = out_a / "EPSILON_SENSITIVITY_MATRIX_TOY.md"
            md_b = out_b / "EPSILON_SENSITIVITY_MATRIX_TOY.md"

            self.assertEqual(json_a.read_bytes(), json_b.read_bytes())
            self.assertEqual(md_a.read_bytes(), md_b.read_bytes())

            payload = json.loads(json_a.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "phase4_epsilon_sensitivity_matrix_report_v1")
            self.assertTrue(bool(payload.get("paths_redacted")))
            self.assertEqual(payload.get("status"), "ok")

            check = payload.get("self_check", {})
            self.assertTrue(bool(check.get("self_check_ok")))
            self.assertLessEqual(float(check.get("max_abs_diff_overall", 1.0)), 1.0e-10)

            # Baseline sanity lock: SN sensitivity to epsilon_em at z=0.1, p=1 is -ln(1.1).
            sn_h0 = float(
                payload["analytic_sensitivities"]["d_ln_H0_inferred_d_epsilon"]["SN"]["epsilon_em"]
            )
            self.assertAlmostEqual(sn_h0, -math.log(1.1), places=12)

            digest = hashlib.sha256(json_a.read_bytes()).hexdigest()
            self.assertRegex(digest, r"^[0-9a-f]{64}$")

            text = json_a.read_text(encoding="utf-8")
            self.assertNotIn(str(td_path.resolve()), text)
            for token in ABS_TOKENS:
                self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()

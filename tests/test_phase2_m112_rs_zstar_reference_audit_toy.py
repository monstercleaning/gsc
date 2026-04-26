import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M112RsZstarReferenceAuditToy(unittest.TestCase):
    def test_reference_audit_parses_mock_reference(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            candidate_path = base / "candidate.json"
            run_dir = base / "run"
            run_dir.mkdir(parents=True, exist_ok=True)
            report_path = base / "RS_ZSTAR_REFERENCE_AUDIT.json"

            candidate_payload = {
                "record": {
                    "params_hash": "m112_candidate_hash",
                    "predicted": {
                        "r_s_star_Mpc": 144.0,
                        "z_star": 1090.0,
                    },
                }
            }
            candidate_path.write_text(
                json.dumps(candidate_payload, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
            (run_dir / "class_derived.txt").write_text(
                "rs = 145.0\nz_star = 1089.0\n",
                encoding="utf-8",
            )

            script = ROOT / "scripts" / "phase2_cmb_rs_zstar_reference_audit.py"
            cmd = [
                sys.executable,
                str(script),
                "--candidate-record",
                str(candidate_path),
                "--run-dir",
                str(run_dir),
                "--created-utc",
                "2000-01-01T00:00:00Z",
                "--out",
                str(report_path),
                "--format",
                "json",
            ]
            proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)
            self.assertTrue(report_path.is_file())

            payload = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "phase2_cmb_rs_zstar_reference_audit_v1")
            reference = payload.get("reference") or {}
            self.assertTrue(bool(reference.get("available")))
            self.assertAlmostEqual(float(reference.get("rs_ref_mpc")), 145.0)
            self.assertAlmostEqual(float(reference.get("z_star_ref")), 1089.0)
            comparison = payload.get("comparison") or {}
            self.assertAlmostEqual(float(comparison.get("delta_rs_mpc")), -1.0)
            self.assertAlmostEqual(float(comparison.get("delta_z_star")), 1.0)


if __name__ == "__main__":
    unittest.main()


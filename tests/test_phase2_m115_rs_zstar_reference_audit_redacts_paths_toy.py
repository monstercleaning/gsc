import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_cmb_rs_zstar_reference_audit.py"


class TestPhase2M115RsZstarReferenceAuditRedactsPathsToy(unittest.TestCase):
    def test_default_audit_payload_redacts_absolute_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bundle = td_path / "bundle"
            bundle.mkdir(parents=True, exist_ok=True)
            run_dir = td_path / "run"
            run_dir.mkdir(parents=True, exist_ok=True)
            out_json = td_path / "audit.json"

            (bundle / "CANDIDATE_RECORD.json").write_text(
                json.dumps(
                    {
                        "record": {
                            "params_hash": "m115-rs-audit",
                            "predicted": {"r_s_star_Mpc": 144.0, "z_star": 1090.0},
                        }
                    },
                    sort_keys=True,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (run_dir / "class_derived.txt").write_text("rs = 145.0\nz_star = 1089.0\n", encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--bundle-dir",
                    str(bundle),
                    "--run-dir",
                    str(run_dir),
                    "--created-utc",
                    "2000-01-01T00:00:00Z",
                    "--out",
                    str(out_json),
                    "--format",
                    "json",
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertTrue(bool(payload.get("paths_redacted")))
            source = payload.get("source") or {}
            self.assertEqual(source.get("bundle_dir"), ".")
            self.assertEqual(source.get("run_dir"), ".")
            self.assertNotIn("bundle_dir_abs", source)
            self.assertNotIn("run_dir_abs", source)

            rendered = json.dumps(payload, sort_keys=True)
            self.assertNotIn("/Users/", rendered)
            self.assertNotIn("/home/", rendered)
            self.assertNotIn("/var/folders/", rendered)
            self.assertNotIn("C:\\Users\\", rendered)


if __name__ == "__main__":
    unittest.main()

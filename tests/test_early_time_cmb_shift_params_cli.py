import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.optional_deps import skip_module_unless_numpy  # noqa: E402

skip_module_unless_numpy("numpy not installed (skipping numpy-tier tests)")


class TestEarlyTimeCMBShiftParamsCLI(unittest.TestCase):
    def test_cli_writes_json_under_outdir(self):
        script = ROOT / "scripts" / "early_time_cmb_shift_params.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            out_root = Path(td) / "release"
            cmd = [
                sys.executable,
                str(script),
                "--out-dir",
                str(out_root),
                "--out",
                "early_time/run_a.json",
            ]
            proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
            out = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=out)
            self.assertIn(f"[info] OUTDIR={out_root.resolve()}", out)

            out_json = out_root / "early_time" / "run_a.json"
            self.assertTrue(out_json.is_file())
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("model"), "lcdm")
            predicted = payload.get("predicted") or {}
            for key in ("theta_star", "lA", "R", "z_star", "r_s_star_Mpc", "D_M_star_Mpc"):
                self.assertIn(key, predicted)

    def test_cli_uses_gsc_outdir_when_flag_missing(self):
        script = ROOT / "scripts" / "early_time_cmb_shift_params.py"
        self.assertTrue(script.is_file())

        with tempfile.TemporaryDirectory() as td:
            out_root = Path(td) / "env_out"
            env = os.environ.copy()
            env["GSC_OUTDIR"] = str(out_root)
            cmd = [
                sys.executable,
                str(script),
            ]
            proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True, env=env)
            out = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=out)
            self.assertIn(f"[info] OUTDIR={out_root.resolve()}", out)

            out_json = out_root / "early_time" / "cmb_shift_params.json"
            self.assertTrue(out_json.is_file())
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertIn("predicted", payload)


if __name__ == "__main__":
    unittest.main()

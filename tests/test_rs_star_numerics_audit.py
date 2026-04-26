import csv
import json
import math
import unittest
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from gsc.optional_deps import skip_module_unless_numpy, skip_testcase_unless_matplotlib  # noqa: E402

skip_module_unless_numpy("numpy not installed (skipping numpy-tier tests)")

import cmb_rs_star_numerics_audit as audit  # noqa: E402


def _walk_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_strings(k)
            yield from _walk_strings(v)
    elif isinstance(obj, (list, tuple)):
        for x in obj:
            yield from _walk_strings(x)


class TestRsStarNumericsAudit(unittest.TestCase):
    def setUp(self) -> None:
        skip_testcase_unless_matplotlib(self)

    def test_writes_outputs_and_shows_calibration_is_not_discretization(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            manifest = audit.run(
                out_dir=out,
                H0_km_s_Mpc=67.4,
                Omega_m=0.315,
                omega_b_h2=0.02237,
                omega_c_h2=0.1200,
                N_eff=3.046,
                Tcmb_K=2.7255,
                z_max=1.0e7,
                trap_n_list=[8192],
                gl_n_list=[256],
                gl_n_ref=1024,
            )

            self.assertEqual(manifest.get("kind"), "rs_star_numerics_audit")
            self.assertTrue((out / "manifest.json").is_file())
            self.assertTrue((out / "tables" / "rs_star_numerics_compare.csv").is_file())
            self.assertTrue((out / "tables" / "summary.txt").is_file())
            self.assertTrue((out / "figures" / "rs_star_rel_error.png").is_file())

            obj = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            s = json.dumps(obj, sort_keys=True)
            self.assertNotIn("/Users/", s)
            self.assertNotIn("C:\\\\", s)
            for v in _walk_strings(obj):
                self.assertNotIn("/Users/", v)
                self.assertNotIn("C:\\\\", v)

            # Verify numerics logic: trap_u integration error should be tiny compared to the ~0.29% calibration.
            trap_rel = None
            cal_rel = None
            with (out / "tables" / "rs_star_numerics_compare.csv").open("r", encoding="utf-8", newline="") as f:
                r = csv.DictReader(f)
                for row in r:
                    if row.get("method") == "trap_u" and int(row.get("n", "0")) == 8192:
                        trap_rel = float(row["rel_err_vs_ref"])
                    if row.get("method") == "trap_u_calibrated" and int(row.get("n", "0")) == 8192:
                        cal_rel = float(row["rel_err_vs_ref"])
            self.assertIsNotNone(trap_rel)
            self.assertIsNotNone(cal_rel)
            self.assertTrue(math.isfinite(trap_rel))
            self.assertTrue(math.isfinite(cal_rel))

            calib_rel = float(obj["calibration"]["calib_rel"])
            self.assertGreater(calib_rel, 0.0)
            self.assertLess(abs(trap_rel), 1e-2 * calib_rel)  # discretization is << 0.29%
            # Calibrated row should be close to the declared calibration factor (within loose tol).
            self.assertLess(abs(cal_rel - calib_rel), 5e-4)


if __name__ == "__main__":
    unittest.main()

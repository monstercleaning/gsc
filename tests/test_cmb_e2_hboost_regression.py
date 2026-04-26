import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from gsc.optional_deps import skip_module_unless_numpy  # noqa: E402

skip_module_unless_numpy("numpy not installed (skipping numpy-tier tests)")

import cmb_e2_distance_closure_to_hboost as hboost  # noqa: E402


class TestCMBE2HBoostRegression(unittest.TestCase):
    def test_hboost_mapping_is_sane_for_e22_dm_fit(self):
        # Baseline point used in E2.2 diagnostic summaries.
        dm_fit = 0.9290939714464278

        r = hboost.compute_effective_hboost_solution(
            model="gsc_transition",
            H0_km_s_Mpc=67.4,
            Omega_m=0.315,
            Omega_L=0.685,
            gsc_p=0.6,
            gsc_ztrans=1.8,
            cmb_bridge_z=5.0,
            dm_star_calibration=dm_fit,
            omega_b_h2=0.02237,
            omega_c_h2=0.1200,
            Neff=3.046,
            Tcmb_K=2.7255,
            z_boost_starts=[5.0],
        )

        sol = dict(r["solution_at_bridge_z"])
        A = float(sol["A"])

        # Sane-range assertions (do not lock exact floats; keep cross-platform stable).
        self.assertTrue(A > 1.0)
        self.assertTrue(A < 3.0)
        self.assertTrue(abs(A - 1.0) > 1e-3)


if __name__ == "__main__":
    unittest.main()

import importlib.util
import math
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.early_time import compute_lcdm_distance_priors  # noqa: E402
from gsc.early_time.cmb_microphysics_knobs import (  # noqa: E402
    MicrophysicsKnobs,
    knobs_from_dict,
    knobs_to_dict,
)


HAS_NUMPY = importlib.util.find_spec("numpy") is not None


class TestPhase2M23CMBMicrophysicsKnobs(unittest.TestCase):
    def test_knobs_validate_and_roundtrip(self):
        knobs = MicrophysicsKnobs()
        knobs.validate()
        data = knobs_to_dict(knobs)
        self.assertEqual(
            data,
            {
                "r_d_scale": 1.0,
                "r_s_scale": 1.0,
                "z_star_scale": 1.0,
            },
        )
        reconstructed = knobs_from_dict(data)
        self.assertEqual(reconstructed, knobs)

    def test_knobs_invalid_values_raise(self):
        with self.assertRaises(ValueError):
            knobs_from_dict({"z_star_scale": 0.0})
        with self.assertRaises(ValueError):
            knobs_from_dict({"r_s_scale": float("nan")})
        with self.assertRaises(ValueError):
            knobs_from_dict({"r_d_scale": float("inf")})

    @unittest.skipUnless(HAS_NUMPY, "numpy not installed (skipping numpy-tier tests)")
    def test_unit_scales_are_numerically_identical(self):
        base = compute_lcdm_distance_priors(
            H0_km_s_Mpc=67.4,
            Omega_m=0.315,
            omega_b_h2=0.02237,
            omega_c_h2=0.1200,
            N_eff=3.046,
            Tcmb_K=2.7255,
        )
        unit = compute_lcdm_distance_priors(
            H0_km_s_Mpc=67.4,
            Omega_m=0.315,
            omega_b_h2=0.02237,
            omega_c_h2=0.1200,
            N_eff=3.046,
            Tcmb_K=2.7255,
            microphysics={"z_star_scale": 1.0, "r_s_scale": 1.0, "r_d_scale": 1.0},
        )
        for key in ("theta_star", "lA", "R", "z_star", "rd_Mpc"):
            self.assertTrue(math.isfinite(float(base[key])))
            self.assertAlmostEqual(float(base[key]), float(unit[key]), places=15, msg=key)

    @unittest.skipUnless(HAS_NUMPY, "numpy not installed (skipping numpy-tier tests)")
    def test_microphysics_sensitivity_sanity(self):
        base = compute_lcdm_distance_priors(
            H0_km_s_Mpc=67.4,
            Omega_m=0.315,
            omega_b_h2=0.02237,
            omega_c_h2=0.1200,
            N_eff=3.046,
            Tcmb_K=2.7255,
        )
        rs_up = compute_lcdm_distance_priors(
            H0_km_s_Mpc=67.4,
            Omega_m=0.315,
            omega_b_h2=0.02237,
            omega_c_h2=0.1200,
            N_eff=3.046,
            Tcmb_K=2.7255,
            microphysics={"r_s_scale": 1.01},
        )
        z_up = compute_lcdm_distance_priors(
            H0_km_s_Mpc=67.4,
            Omega_m=0.315,
            omega_b_h2=0.02237,
            omega_c_h2=0.1200,
            N_eff=3.046,
            Tcmb_K=2.7255,
            microphysics={"z_star_scale": 1.01},
        )

        self.assertGreater(float(rs_up["theta_star"]), float(base["theta_star"]))
        self.assertLess(float(rs_up["lA"]), float(base["lA"]))
        self.assertAlmostEqual(float(z_up["z_star"]), 1.01 * float(base["z_star"]), places=12)


if __name__ == "__main__":
    unittest.main()

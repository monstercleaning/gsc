import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TestCHW2018RequiresCovCLI(unittest.TestCase):
    def test_scorecard_requires_cov_for_chw2018(self):
        script = ROOT / "scripts" / "late_time_scorecard.py"
        cmb_csv = ROOT / "data" / "cmb" / "planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv"

        r = subprocess.run(
            [
                sys.executable,
                str(script),
                "--model",
                "lcdm",
                "--Omega-m",
                "0.315",
                "--Omega-L",
                "0.685",
                "--cmb",
                str(cmb_csv),
                "--cmb-mode",
                "distance_priors",
                "--omega-b-h2",
                "0.02237",
                "--omega-c-h2",
                "0.1200",
            ],
            capture_output=True,
            text=True,
        )
        out = (r.stdout or "") + (r.stderr or "")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--cmb-cov", out)

    def test_scorecard_requires_distance_priors_mode_for_chw2018(self):
        script = ROOT / "scripts" / "late_time_scorecard.py"
        cmb_csv = ROOT / "data" / "cmb" / "planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv"
        cmb_cov = ROOT / "data" / "cmb" / "planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov"

        r = subprocess.run(
            [
                sys.executable,
                str(script),
                "--model",
                "lcdm",
                "--Omega-m",
                "0.315",
                "--Omega-L",
                "0.685",
                "--cmb",
                str(cmb_csv),
                "--cmb-cov",
                str(cmb_cov),
                # omit --cmb-mode (defaults to theta_star) -> must fail
                "--omega-b-h2",
                "0.02237",
                "--omega-c-h2",
                "0.1200",
            ],
            capture_output=True,
            text=True,
        )
        out = (r.stdout or "") + (r.stderr or "")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--cmb-mode distance_priors", out)

    def test_fit_grid_requires_cov_for_chw2018(self):
        script = ROOT / "scripts" / "late_time_fit_grid.py"
        cmb_csv = ROOT / "data" / "cmb" / "planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv"

        r = subprocess.run(
            [
                sys.executable,
                str(script),
                "--model",
                "lcdm",
                "--cmb",
                str(cmb_csv),
                "--cmb-mode",
                "distance_priors",
                "--omega-b-h2",
                "0.02237",
                "--omega-c-h2",
                "0.1200",
            ],
            capture_output=True,
            text=True,
        )
        out = (r.stdout or "") + (r.stderr or "")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--cmb-cov", out)

    def test_fit_grid_requires_distance_priors_mode_for_chw2018(self):
        script = ROOT / "scripts" / "late_time_fit_grid.py"
        cmb_csv = ROOT / "data" / "cmb" / "planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv"
        cmb_cov = ROOT / "data" / "cmb" / "planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov"

        r = subprocess.run(
            [
                sys.executable,
                str(script),
                "--model",
                "lcdm",
                "--cmb",
                str(cmb_csv),
                "--cmb-cov",
                str(cmb_cov),
                # omit --cmb-mode (defaults to theta_star) -> must fail
                "--omega-b-h2",
                "0.02237",
                "--omega-c-h2",
                "0.1200",
            ],
            capture_output=True,
            text=True,
        )
        out = (r.stdout or "") + (r.stderr or "")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--cmb-mode distance_priors", out)


if __name__ == "__main__":
    unittest.main()

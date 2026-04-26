import json
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from gsc.optional_deps import skip_module_unless_numpy, skip_testcase_unless_matplotlib  # noqa: E402

skip_module_unless_numpy("numpy not installed (skipping numpy-tier tests)")

import cmb_e2_neutrino_knob_diagnostic as nk  # noqa: E402


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


class TestCMBE2NeutrinoKnobDiagnostic(unittest.TestCase):
    def setUp(self) -> None:
        skip_testcase_unless_matplotlib(self)

    def test_script_writes_outputs_and_manifest_is_repo_relative(self):
        base = ROOT / "results" / "diagnostic_cmb_e2_neutrino_knob_test"
        out_dir = base / "out"
        out_dir.mkdir(parents=True, exist_ok=True)

        cmb_csv = ROOT / "data" / "cmb" / "planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE.csv"
        cmb_cov = ROOT / "data" / "cmb" / "planck2018_distance_priors_chw2018_base_plikHM_TTTEEE_lowE_cov.cov"
        self.assertTrue(cmb_csv.is_file())
        self.assertTrue(cmb_cov.is_file())

        manifest = nk.run(
            model="gsc_transition",
            cmb_csv=cmb_csv,
            cmb_cov=cmb_cov,
            out_dir=out_dir,
            bridge_zs=[5.0],
            delta_neff_grid=[0.0],
            H0_km_s_Mpc=67.4,
            Omega_m=0.315,
            Omega_L=0.685,
            gsc_p=0.6,
            gsc_ztrans=1.8,
            omega_b_h2=0.02237,
            omega_c_h2=0.1200,
            Neff_base=3.046,
            Tcmb_K=2.7255,
            baseline_rs=float(nk._RS_STAR_CALIB_CHW2018),
            baseline_dm=1.0,
            # Coarse grid for unit-test speed.
            rs_min=0.95,
            rs_max=1.05,
            rs_step=0.01,
        )

        out_csv = out_dir / "tables" / "cmb_e2_neutrino_knob_scan.csv"
        fig = out_dir / "figures" / "neutrino_knob_dm_rs_A_vs_delta_neff.png"
        out_manifest = out_dir / "manifest.json"
        self.assertTrue(out_csv.is_file())
        self.assertTrue(fig.is_file())
        self.assertTrue(out_manifest.is_file())

        # Must have at least 1 row.
        txt = out_csv.read_text(encoding="utf-8").strip().splitlines()
        self.assertGreaterEqual(len(txt), 2)  # header + 1 row

        # Portability: no machine-local paths.
        s = json.dumps(manifest, sort_keys=True)
        self.assertNotIn("/Users/", s)
        self.assertNotIn("C:\\\\", s)
        for v in _walk_strings(manifest):
            self.assertNotIn("/Users/", v)
            self.assertNotIn("C:\\\\", v)


if __name__ == "__main__":
    unittest.main()

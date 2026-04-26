import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCAN_SCRIPT = ROOT / "scripts" / "phase2_e2_scan.py"


def _load_scan_module():
    script_dir = str(SCAN_SCRIPT.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    root_dir = str(ROOT)
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
    spec = importlib.util.spec_from_file_location("phase2_e2_scan_m24_test", SCAN_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {SCAN_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestPhase2M24E2ScanMicrophysicsAuditFields(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scan = _load_scan_module()

    def test_payload_and_audit_defaults(self):
        payload, audit = self.scan._microphysics_payload_and_audit(  # pylint: disable=protected-access
            scales={"z_star_scale": 1.0, "r_s_scale": 1.0, "r_d_scale": 1.0},
            mode="none",
        )
        self.assertEqual(payload["mode"], "none")
        self.assertEqual(float(payload["z_star_scale"]), 1.0)
        self.assertTrue(bool(audit["microphysics_hard_ok"]))
        self.assertTrue(bool(audit["microphysics_plausible_ok"]))
        self.assertEqual(float(audit["microphysics_penalty"]), 0.0)
        self.assertEqual(float(audit["microphysics_max_rel_dev"]), 0.0)
        self.assertEqual(list(audit["microphysics_notes"]), [])

    def test_payload_and_audit_non_plausible(self):
        payload, audit = self.scan._microphysics_payload_and_audit(  # pylint: disable=protected-access
            scales={"z_star_scale": 1.06, "r_s_scale": 1.0, "r_d_scale": 1.0},
            mode="knobs",
        )
        self.assertEqual(payload["mode"], "knobs")
        self.assertTrue(bool(audit["microphysics_hard_ok"]))
        self.assertFalse(bool(audit["microphysics_plausible_ok"]))
        self.assertGreater(float(audit["microphysics_penalty"]), 0.0)
        self.assertGreater(len(list(audit["microphysics_notes"])), 0)

    def test_scales_from_params_none_mode_is_unity(self):
        scales = self.scan._microphysics_scales_from_params(  # pylint: disable=protected-access
            params={},
            mode="none",
        )
        self.assertEqual(
            scales,
            {
                "r_d_scale": 1.0,
                "r_s_scale": 1.0,
                "z_star_scale": 1.0,
            },
        )


if __name__ == "__main__":
    unittest.main()

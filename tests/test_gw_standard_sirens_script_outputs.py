import json
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import gw_standard_sirens_diagnostic as gwdiag  # noqa: E402


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


class TestGWStandardSirensScriptOutputs(unittest.TestCase):
    def setUp(self) -> None:
        try:
            import matplotlib  # noqa: F401
        except Exception:
            self.skipTest("matplotlib not installed")

    def test_script_writes_outputs_and_manifest_is_strict(self):
        base = ROOT / "results" / "diagnostic_gw_standard_sirens_test"
        out_dir = base / "out"
        out_dir.mkdir(parents=True, exist_ok=True)

        manifest = gwdiag.run(
            out_dir=out_dir,
            mode="xi0_n",
            z_max=0.2,
            dz=0.2,
            n_int=500,
            H0_km_s_Mpc=67.4,
            Omega_m=0.315,
            xi0=0.9,
            xi_n=2.0,
            delta0=0.0,
            alphaM0=0.0,
        )

        out_csv = out_dir / "tables" / "gw_xi_vs_z.csv"
        out_png = out_dir / "figures" / "gw_dL_ratio_vs_z.png"
        out_manifest = out_dir / "manifest.json"

        self.assertTrue(out_csv.is_file())
        self.assertTrue(out_png.is_file())
        self.assertTrue(out_manifest.is_file())

        # Ensure manifest is valid JSON and contains no machine-local paths.
        txt = out_manifest.read_text(encoding="utf-8")
        obj = json.loads(txt)
        s = json.dumps(obj, sort_keys=True)
        self.assertNotIn("/Users/", s)
        self.assertNotIn("C:\\\\", s)
        for v in _walk_strings(obj):
            self.assertNotIn("/Users/", v)
            self.assertNotIn("C:\\\\", v)

        # The returned manifest should match what's on disk.
        self.assertEqual(manifest.get("kind"), "gw_standard_sirens_diagnostic")


if __name__ == "__main__":
    unittest.main()


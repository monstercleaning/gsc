import json
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from gsc.optional_deps import skip_module_unless_numpy, skip_testcase_unless_matplotlib  # noqa: E402

skip_module_unless_numpy("numpy not installed (skipping numpy-tier tests)")

import cmb_e2_drift_cmb_correlation as corr  # noqa: E402


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


class TestCMBE2DriftCMBCorrelation(unittest.TestCase):
    def setUp(self) -> None:
        skip_testcase_unless_matplotlib(self)

    def test_script_writes_outputs_and_manifest_is_repo_relative(self):
        # Create a tiny E2.4-like scan CSV under the repo results/ (gitignored) so
        # manifest serialization can be repo-relative.
        base = ROOT / "results" / "diagnostic_drift_cmb_correlation_test"
        in_dir = base / "input"
        out_dir = base / "out"
        in_dir.mkdir(parents=True, exist_ok=True)
        out_dir.mkdir(parents=True, exist_ok=True)

        scan_csv = in_dir / "scan.csv"
        scan_manifest = in_dir / "scan_manifest.json"

        scan_csv.write_text(
            "\n".join(
                [
                    "model,p,z_transition,bridge_z_used,is_degenerate,dm_fit,rs_fit,chi2_min,chi2_base,pulls_R,pulls_lA,pulls_omega_b_h2",
                    "gsc_transition,0.6,1.8,5,False,0.9290939714464278,1.0045,0.0177,82500,0,0,0",
                    "gsc_transition,0.7,4.0,10,False,0.833194869664079,1.0045,0.0177,50000,0,0,0",
                    "gsc_transition,0.6,6.0,5,True,0.95,1.0045,0.0177,999,0,0,0",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        scan_manifest.write_text(
            json.dumps(
                {
                    "fixed_params": {
                        "H0_km_s_Mpc": 67.4,
                        "Omega_m": 0.315,
                        "Omega_L": 0.685,
                        "omega_b_h2": 0.02237,
                        "omega_c_h2": 0.1200,
                        "Neff": 3.046,
                        "Tcmb_K": 2.7255,
                    },
                    "grid": {
                        "bridge_z_used": [5.0, 10.0],
                        "p": [0.6, 0.7],
                        "z_transition": [1.8, 4.0],
                    },
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        manifest = corr.run(
            scan_csv=scan_csv,
            scan_manifest=scan_manifest,
            out_dir=out_dir,
            years=10.0,
            zs=[2.0, 3.0, 4.0, 5.0],
            top_n=2,
            powerlaw_n=2.0,
            logistic_zc=20.0,
            logistic_s=2.0,
            implausible_Amax_threshold=10.0,
        )

        out_csv = out_dir / "tables" / "e2_drift_cmb_correlation.csv"
        top_csv = out_dir / "tables" / "e2_drift_cmb_correlation_topN.csv"
        summary_csv = out_dir / "tables" / "drift_cmb_closure_summary.csv"
        shapes_csv = out_dir / "tables" / "cmb_drift_cmb_correlation_shapes.csv"
        fig1 = out_dir / "figures" / "A_required_vs_drift_z4.png"
        fig2 = out_dir / "figures" / "dm_fit_vs_drift_z4.png"
        fig3 = out_dir / "figures" / "Amax_required_logistic_vs_bridge_z.png"
        fig4 = out_dir / "figures" / "Amax_required_logistic_vs_drift_z4.png"
        fig5 = out_dir / "figures" / "A_required_by_shape.png"
        out_manifest_path = out_dir / "manifest.json"

        self.assertTrue(out_csv.is_file())
        self.assertTrue(top_csv.is_file())
        self.assertTrue(summary_csv.is_file())
        self.assertTrue(shapes_csv.is_file())
        self.assertTrue(fig1.is_file())
        self.assertTrue(fig2.is_file())
        self.assertTrue(fig3.is_file())
        self.assertTrue(fig4.is_file())
        self.assertTrue(fig5.is_file())
        self.assertTrue(out_manifest_path.is_file())

        # Must have at least one non-degenerate point.
        self.assertGreater(int(manifest.get("summary", {}).get("num_points_non_degenerate", 0)), 0)

        # Portability: no machine-local paths.
        s = json.dumps(manifest, sort_keys=True)
        self.assertNotIn("/Users/", s)
        self.assertNotIn("C:\\\\", s)

        for v in _walk_strings(manifest):
            self.assertNotIn("/Users/", v)
            self.assertNotIn("C:\\\\", v)


if __name__ == "__main__":
    unittest.main()

import csv
import json
import tempfile
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))


class TestSnTwoPassSensitivityDiagnostic(unittest.TestCase):
    def test_writes_outputs_and_manifest_is_portable(self):
        try:
            import numpy  # noqa: F401
            import matplotlib  # noqa: F401
            import scipy  # noqa: F401
        except Exception:
            self.skipTest("numpy/scipy/matplotlib not installed")

        import sn_two_pass_sensitivity_diagnostic as mod  # noqa: E402
        from gsc.measurement_model import (  # noqa: E402
            FlatLambdaCDMHistory,
            H0_to_SI,
            distance_modulus_flat,
        )

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            out_dir = td_path / "out"
            data_dir = td_path / "data"
            data_dir.mkdir(parents=True, exist_ok=True)

            sn_csv = data_dir / "sn.csv"
            sn_cov = data_dir / "sn.cov"
            bao_csv = data_dir / "bao.csv"

            H0 = H0_to_SI(67.4)
            hist = FlatLambdaCDMHistory(H0=H0, Omega_m=0.315, Omega_Lambda=0.685)
            zs = [0.05, 0.2, 0.6]
            mus = [distance_modulus_flat(z=z, H_of_z=hist.H, n=1000) + 0.1 for z in zs]
            sig = [0.2, 0.2, 0.2]

            with sn_csv.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["z", "mu", "sigma_mu"])
                for z, m, s in zip(zs, mus, sig):
                    w.writerow([f"{z:.10g}", f"{m:.10g}", f"{s:.10g}"])

            # Full 3x3 covariance (row-major), with optional leading N.
            vals = [0.04, 0.0, 0.0, 0.0, 0.04, 0.0, 0.0, 0.0, 0.04]
            with sn_cov.open("w", encoding="utf-8") as f:
                f.write("3\n")
                f.write(" ".join(str(v) for v in vals) + "\n")

            with bao_csv.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["type", "z", "dv_over_rd", "sigma_dv_over_rd", "survey", "label"])
                w.writerow(["DV_over_rd", "0.1", "3.0", "0.2", "T", "DV1"])
                w.writerow(["DV_over_rd", "0.2", "4.0", "0.2", "T", "DV2"])

            manifest = mod.run(
                out_dir=out_dir,
                models=["lcdm"],
                two_pass_top_list=[1, 2, 3],
                sn_csv=sn_csv,
                sn_cov=sn_cov,
                bao_csv=bao_csv,
                drift_csv=None,
                drift_baseline_years=None,
                profile_h0=False,
                H0_grid=[66.0, 67.4, 69.0],
                Omega_m_grid=[0.28, 0.315, 0.35],
                p_grid=[0.6],
                ztrans_grid=[1.8],
                n_grid=800,
            )

            self.assertEqual(manifest.get("kind"), "sn_two_pass_sensitivity")
            self.assertTrue(bool(manifest.get("diagnostic_only")))

            table = out_dir / "tables/sn_two_pass_sensitivity.csv"
            points = out_dir / "tables/sn_two_pass_points.csv"
            fig1 = out_dir / "figures/chi2_best_vs_two_pass_top.png"
            fig2 = out_dir / "figures/best_rank_position_vs_two_pass_top.png"
            man = out_dir / "manifest.json"
            self.assertTrue(table.exists())
            self.assertTrue(points.exists())
            self.assertTrue(fig1.exists())
            self.assertTrue(fig2.exists())
            self.assertTrue(man.exists())

            with table.open("r", newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertGreaterEqual(len(rows), 1)

            obj = json.loads(man.read_text(encoding="utf-8"))

            def walk(x):
                if isinstance(x, dict):
                    for v in x.values():
                        yield from walk(v)
                elif isinstance(x, list):
                    for v in x:
                        yield from walk(v)
                elif isinstance(x, str):
                    yield x

            for s in walk(obj):
                self.assertNotIn("/Users/", s)
                self.assertNotIn(":\\", s)
                if s.startswith(str(REPO_ROOT)):
                    self.fail(f"unexpected absolute repo path in manifest: {s}")


if __name__ == "__main__":
    unittest.main()

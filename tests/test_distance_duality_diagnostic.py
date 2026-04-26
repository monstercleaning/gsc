import json
import math
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from gsc.optional_deps import skip_module_unless_numpy, skip_testcase_unless_matplotlib  # noqa: E402

skip_module_unless_numpy("numpy not installed (skipping numpy-tier tests)")

import distance_duality_diagnostic as dd  # noqa: E402

from gsc.datasets.bao import D_V_flat  # noqa: E402
from gsc.measurement_model import FlatLambdaCDMHistory, H0_to_SI, MPC_SI, distance_modulus_flat  # noqa: E402


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


class TestDistanceDualityDiagnostic(unittest.TestCase):
    def setUp(self) -> None:
        skip_testcase_unless_matplotlib(self)

    def test_recovers_injected_epsilon_in_synthetic_data(self):
        base = ROOT / "results" / "diagnostic_distance_duality_test"
        out_dir = base / "out"
        out_dir.mkdir(parents=True, exist_ok=True)

        # Synthetic data from LCDM with an injected epsilon_dd.
        eps_true = 0.02
        delta_M_true = 0.123

        H0 = H0_to_SI(67.4)
        model = FlatLambdaCDMHistory(H0=H0, Omega_m=0.315, Omega_Lambda=0.685)
        rd_m = 150.0 * float(MPC_SI)

        sn_csv = out_dir / "sn.csv"
        zs_sn = [0.05, 0.2, 0.7]
        sig_mu = 0.1
        with sn_csv.open("w", encoding="utf-8", newline="") as f:
            f.write("z,mu,sigma_mu\n")
            for z in zs_sn:
                mu0 = distance_modulus_flat(z=float(z), H_of_z=model.H, n=2000)
                mu = mu0 + dd._epsilon_mu_shift(float(z), eps_true) + float(delta_M_true)
                f.write(f"{z:.10g},{mu:.10g},{sig_mu:.10g}\n")

        bao_csv = out_dir / "bao.csv"
        zs_bao = [0.2, 0.5]
        sig_y = 0.05
        with bao_csv.open("w", encoding="utf-8", newline="") as f:
            f.write("type,z,dv_over_rd,sigma_dv_over_rd\n")
            for z in zs_bao:
                dv = float(D_V_flat(z=float(z), model=model, n=10_000))
                y = dv / float(rd_m)
                f.write(f"DV_over_rd,{z:.10g},{y:.10g},{sig_y:.10g}\n")

        manifest = dd.run(
            out_dir=out_dir,
            sn_csv=sn_csv,
            sn_cov=None,
            bao_csv=bao_csv,
            model_name="lcdm",
            H0_km_s_Mpc=67.4,
            Omega_m=0.315,
            p=0.6,
            z_transition=1.8,
            eps_min=-0.02,
            eps_max=0.06,
            eps_step=0.002,
            n_mu=1200,
            n_bao=4000,
        )

        out_manifest = out_dir / "manifest.json"
        self.assertTrue(out_manifest.is_file())
        obj = json.loads(out_manifest.read_text(encoding="utf-8"))

        eps_best = float(obj["best_fit"]["epsilon_dd"])
        self.assertTrue(math.isfinite(eps_best))
        self.assertAlmostEqual(eps_best, eps_true, places=6)

        # Portability: no machine-local paths in manifest (repo-relative expected).
        s = json.dumps(obj, sort_keys=True)
        self.assertNotIn("/Users/", s)
        self.assertNotIn("C:\\\\", s)
        for v in _walk_strings(obj):
            self.assertNotIn("/Users/", v)
            self.assertNotIn("C:\\\\", v)

        # Returned manifest should match on-disk kind.
        self.assertEqual(manifest.get("kind"), "distance_duality_diagnostic")


if __name__ == "__main__":
    unittest.main()

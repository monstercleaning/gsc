import tempfile
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.optional_deps import skip_module_unless_numpy  # noqa: E402

skip_module_unless_numpy("numpy not installed (skipping numpy-tier tests)")

from gsc.datasets.cmb_priors import CMBPriorsDataset  # noqa: E402
from gsc.early_time.cmb_priors_driver import (  # noqa: E402
    CMBPriorsDriverConfig,
    evaluate_cmb_priors_dataset,
    predict_cmb_observables,
)
from gsc.measurement_model import FlatLambdaCDMHistory, H0_to_SI  # noqa: E402


def _write_priors(path: Path, rows: list[tuple[str, float, float]]) -> None:
    lines = ["name,value,sigma"]
    for name, value, sigma in rows:
        lines.append(f"{name},{value:.16g},{sigma:.16g}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestCMBPriorsDriverChi2(unittest.TestCase):
    def setUp(self) -> None:
        self.model = FlatLambdaCDMHistory(
            H0=H0_to_SI(67.4),
            Omega_m=0.315,
            Omega_Lambda=0.685,
        )
        self.cfg = CMBPriorsDriverConfig(
            omega_b_h2=0.02237,
            omega_c_h2=0.1200,
            N_eff=3.046,
            Tcmb_K=2.7255,
            mode="distance_priors",
            H0_km_s_Mpc=67.4,
            Omega_m=0.315,
        )

    def test_chi2_near_zero_at_mean_values(self):
        pred = predict_cmb_observables(model=self.model, config=self.cfg)
        with tempfile.TemporaryDirectory() as td:
            csv_path = Path(td) / "cmb.csv"
            _write_priors(
                csv_path,
                [
                    ("theta_star", float(pred["theta_star"]), 1e-5),
                    ("R", float(pred["R"]), 1e-3),
                ],
            )
            ds = CMBPriorsDataset.from_csv(csv_path, name="cmb")
            ev = evaluate_cmb_priors_dataset(dataset=ds, model=self.model, config=self.cfg)

        self.assertAlmostEqual(float(ev.result.chi2), 0.0, places=12)
        self.assertEqual(int(ev.result.ndof), 2)

    def test_alias_key_100theta_star_is_supported(self):
        pred = predict_cmb_observables(model=self.model, config=self.cfg)
        with tempfile.TemporaryDirectory() as td:
            csv_path = Path(td) / "cmb.csv"
            _write_priors(
                csv_path,
                [
                    ("100theta_star", 100.0 * float(pred["theta_star"]), 1e-3),
                ],
            )
            ds = CMBPriorsDataset.from_csv(csv_path, name="cmb")
            ev = evaluate_cmb_priors_dataset(dataset=ds, model=self.model, config=self.cfg)

        self.assertAlmostEqual(float(ev.result.chi2), 0.0, places=12)
        self.assertIn("100theta_star", ev.predicted_for_keys)

    def test_missing_key_raises_clear_error(self):
        with tempfile.TemporaryDirectory() as td:
            csv_path = Path(td) / "cmb.csv"
            _write_priors(csv_path, [("unknown_key", 1.0, 0.1)])
            ds = CMBPriorsDataset.from_csv(csv_path, name="cmb")
            with self.assertRaisesRegex(ValueError, "Missing predicted CMB prior keys"):
                evaluate_cmb_priors_dataset(dataset=ds, model=self.model, config=self.cfg)


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.optional_deps import skip_module_unless_numpy  # noqa: E402

skip_module_unless_numpy("numpy not installed (skipping numpy-tier tests)")

from gsc.datasets.cmb_priors import CMBPriorsDataset  # noqa: E402
from gsc.datasets.cmb_priors_driver import CMBPriorsLikelihood  # noqa: E402
from gsc.early_time.cmb_priors_driver import (  # noqa: E402
    CMBPriorsDriverConfig,
    evaluate_cmb_priors_dataset,
    predict_cmb_observables,
)
from gsc.likelihood import chi2_total  # noqa: E402
from gsc.measurement_model import FlatLambdaCDMHistory, H0_to_SI  # noqa: E402


def _write_priors(path: Path, rows: list[tuple[str, float, float]]) -> None:
    lines = ["name,value,sigma"]
    for name, value, sigma in rows:
        lines.append(f"{name},{value:.16g},{sigma:.16g}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestCMBPriorsDatasetAdapter(unittest.TestCase):
    def test_adapter_matches_direct_dataset_evaluation(self):
        model = FlatLambdaCDMHistory(
            H0=H0_to_SI(67.4),
            Omega_m=0.315,
            Omega_Lambda=0.685,
        )
        cfg = CMBPriorsDriverConfig(
            omega_b_h2=0.02237,
            omega_c_h2=0.1200,
            N_eff=3.046,
            Tcmb_K=2.7255,
            mode="distance_priors",
            H0_km_s_Mpc=67.4,
            Omega_m=0.315,
        )
        pred = predict_cmb_observables(model=model, config=cfg)
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
            direct = evaluate_cmb_priors_dataset(dataset=ds, model=model, config=cfg)
            adapter = CMBPriorsLikelihood(priors=ds, driver_config=cfg)
            via_adapter = adapter.chi2(model)
            total = chi2_total(model=model, datasets=[adapter])

        self.assertAlmostEqual(float(via_adapter.chi2), float(direct.result.chi2), places=12)
        self.assertEqual(int(via_adapter.ndof), int(direct.result.ndof))
        self.assertEqual(via_adapter.meta.get("mode"), "distance_priors")
        self.assertAlmostEqual(float(total.chi2), float(via_adapter.chi2), places=12)


if __name__ == "__main__":
    unittest.main()

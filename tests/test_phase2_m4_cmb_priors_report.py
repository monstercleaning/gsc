import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]

import sys

sys.path.insert(0, str(ROOT))

from gsc.optional_deps import skip_module_unless_numpy  # noqa: E402

skip_module_unless_numpy("numpy not installed (skipping numpy-tier tests)")

from gsc.datasets.cmb_priors import CMBPriorsDataset  # noqa: E402
from gsc.early_time.cmb_priors_reporting import (  # noqa: E402
    CMBPriorsBatchConfig,
    SCHEMA_VERSION,
    evaluate_fit_dir_cmb_priors,
)
from gsc.early_time.cmb_shift_params import compute_lcdm_shift_params  # noqa: E402


def _write_bestfit(path: Path, *, h0: float = 67.4, omega_m: float = 0.315) -> None:
    payload = {
        "model": "lcdm",
        "cmb": {
            "mode": "theta_star",
            "path": "unused.csv",
            "cov_path": None,
            "bridge_z": None,
        },
        "best": {
            "params": {
                "H0": float(h0),
                "Omega_m": float(omega_m),
            },
            "parts": {},
        },
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_priors(path: Path, rows: list[tuple[str, float, float]]) -> None:
    lines = ["name,value,sigma"]
    for key, value, sigma in rows:
        lines.append(f"{key},{value:.16g},{sigma:.16g}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestPhase2M4CMBPriorsReport(unittest.TestCase):
    def test_batch_report_schema_and_rows(self):
        pred = compute_lcdm_shift_params(
            H0_km_s_Mpc=67.4,
            Omega_m=0.315,
            omega_b_h2=0.02237,
            omega_c_h2=0.1200,
            N_eff=3.046,
            Tcmb_K=2.7255,
        )

        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            fit_dir = td_p / "fit"
            fit_dir.mkdir(parents=True, exist_ok=True)
            _write_bestfit(fit_dir / "lcdm_bestfit.json")

            priors_csv = td_p / "cmb.csv"
            _write_priors(
                priors_csv,
                [
                    ("theta_star", float(pred["theta_star"]), 1e-5),
                    ("R", float(pred["R"]), 1e-3),
                ],
            )
            ds = CMBPriorsDataset.from_csv(priors_csv, name="cmb")
            report, rows = evaluate_fit_dir_cmb_priors(
                fit_dir=fit_dir,
                priors=ds,
                config=CMBPriorsBatchConfig(
                    omega_b_h2=0.02237,
                    omega_c_h2=0.1200,
                    N_eff=3.046,
                    Tcmb_K=2.7255,
                    mode=None,
                ),
                repo_root=ROOT.parent,
            )

        self.assertEqual(report["schema_version"], SCHEMA_VERSION)
        self.assertEqual(int(report["summary"]["model_count"]), 1)
        self.assertEqual(len(report["models"]), 1)
        self.assertAlmostEqual(float(report["models"][0]["chi2"]), 0.0, places=10)
        self.assertEqual(int(report["models"][0]["ndof"]), 2)
        self.assertEqual([r["key"] for r in rows], ["theta_star", "R"])

    def test_batch_report_supports_100theta_star_alias(self):
        pred = compute_lcdm_shift_params(
            H0_km_s_Mpc=67.4,
            Omega_m=0.315,
            omega_b_h2=0.02237,
            omega_c_h2=0.1200,
            N_eff=3.046,
            Tcmb_K=2.7255,
        )

        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            fit_dir = td_p / "fit"
            fit_dir.mkdir(parents=True, exist_ok=True)
            _write_bestfit(fit_dir / "lcdm_bestfit.json")

            priors_csv = td_p / "cmb_alias.csv"
            _write_priors(
                priors_csv,
                [
                    ("100theta_star", 100.0 * float(pred["theta_star"]), 1e-3),
                ],
            )
            ds = CMBPriorsDataset.from_csv(priors_csv, name="cmb")
            report, rows = evaluate_fit_dir_cmb_priors(
                fit_dir=fit_dir,
                priors=ds,
                config=CMBPriorsBatchConfig(
                    omega_b_h2=0.02237,
                    omega_c_h2=0.1200,
                    N_eff=3.046,
                    Tcmb_K=2.7255,
                ),
                repo_root=ROOT.parent,
            )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["key"], "100theta_star")
        self.assertAlmostEqual(float(report["models"][0]["chi2"]), 0.0, places=10)


if __name__ == "__main__":
    unittest.main()

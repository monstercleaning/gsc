import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.optional_deps import skip_module_unless_numpy  # noqa: E402

skip_module_unless_numpy("numpy not installed (skipping numpy-tier tests)")

from gsc.early_time.cmb_priors_reporting import SCHEMA_VERSION  # noqa: E402
from gsc.early_time.cmb_priors_reporting import INVARIANTS_SCHEMA_VERSION  # noqa: E402
from gsc.early_time.cmb_shift_params import compute_lcdm_shift_params  # noqa: E402
from gsc.early_time.numerics_invariants import (  # noqa: E402
    DEFAULT_REQUIRED_CHECK_IDS,
    INVARIANTS_SCHEMA_VERSION as MODEL_INVARIANTS_SCHEMA_VERSION,
)


def _write_bestfit(path: Path) -> None:
    payload = {
        "model": "lcdm",
        "cmb": {"mode": "theta_star", "bridge_z": None},
        "best": {
            "params": {"H0": 67.4, "Omega_m": 0.315},
            "parts": {},
        },
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_priors(path: Path, rows: list[tuple[str, float, float]]) -> None:
    lines = ["name,value,sigma"]
    for key, value, sigma in rows:
        lines.append(f"{key},{value:.16g},{sigma:.16g}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestPhase2M4CMBPriorsReportCLI(unittest.TestCase):
    def test_cli_writes_batch_json_and_csv(self):
        script = ROOT / "scripts" / "early_time_cmb_priors_report.py"
        self.assertTrue(script.is_file())

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
            out_root = td_p / "out"

            cmd = [
                sys.executable,
                str(script),
                "--fit-dir",
                str(fit_dir),
                "--cmb",
                str(priors_csv),
                "--omega-b-h2",
                "0.02237",
                "--omega-c-h2",
                "0.1200",
                "--out-dir",
                str(out_root),
            ]
            proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
            out = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=out)

            report = out_root / "early_time" / "cmb_priors_report.json"
            table = out_root / "early_time" / "cmb_priors_table.csv"
            invariants = out_root / "early_time" / "numerics_invariants_report.json"
            self.assertTrue(report.is_file())
            self.assertTrue(table.is_file())
            self.assertTrue(invariants.is_file())

            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema_version"), SCHEMA_VERSION)
            self.assertEqual(int(payload.get("summary", {}).get("model_count", -1)), 1)
            invariants_payload = json.loads(invariants.read_text(encoding="utf-8"))
            self.assertEqual(invariants_payload.get("schema_version"), INVARIANTS_SCHEMA_VERSION)
            self.assertTrue(bool(invariants_payload.get("ok")))
            self.assertIs(invariants_payload.get("strict"), True)
            self.assertEqual(
                int(invariants_payload.get("model_invariants_schema_version", -1)),
                int(MODEL_INVARIANTS_SCHEMA_VERSION),
            )
            self.assertEqual(
                set(str(x) for x in invariants_payload.get("required_check_ids", [])),
                set(str(x) for x in DEFAULT_REQUIRED_CHECK_IDS),
            )
            checks = invariants_payload.get("checks")
            self.assertIsInstance(checks, dict)
            self.assertIn("lcdm", checks)
            model_payload = checks["lcdm"]
            self.assertEqual(int(model_payload.get("schema_version", -1)), int(MODEL_INVARIANTS_SCHEMA_VERSION))
            self.assertIs(model_payload.get("strict"), True)
            model_checks = model_payload.get("checks")
            self.assertIsInstance(model_checks, dict)
            for check_id in DEFAULT_REQUIRED_CHECK_IDS:
                self.assertIn(check_id, model_checks)
                self.assertTrue(bool(model_checks[check_id].get("ok")), msg=model_checks[check_id])
                self.assertEqual(str(model_checks[check_id].get("status", "")).upper(), "PASS")

            table_lines = table.read_text(encoding="utf-8").strip().splitlines()
            self.assertGreaterEqual(len(table_lines), 2)


if __name__ == "__main__":
    unittest.main()

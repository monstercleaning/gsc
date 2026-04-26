import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCAN_SCRIPT = ROOT / "scripts" / "phase2_e2_scan.py"
RSD_DATASET = ROOT / "data" / "structure" / "fsigma8_gold2017_plus_zhao2018.csv"


class TestPhase2M95E2ScanRsdModelKnobsConfigSha(unittest.TestCase):
    def _run_scan(self, *, out_dir: Path, extra_args: list[str]) -> subprocess.CompletedProcess:
        cmd = [
            sys.executable,
            str(SCAN_SCRIPT),
            "--model",
            "lcdm",
            "--toy",
            "--grid",
            "H0=67.4",
            "--grid",
            "Omega_m=0.315",
            "--out-dir",
            str(out_dir),
            *extra_args,
        ]
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def _load_rows(self, jsonl_path: Path) -> list[dict]:
        rows: list[dict] = []
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            obj = json.loads(text)
            if isinstance(obj, dict):
                rows.append(obj)
        return rows

    def _first_sha(self, rows: list[dict]) -> str:
        self.assertTrue(rows)
        value = str(rows[0].get("scan_config_sha256", "")).strip()
        self.assertTrue(value)
        return value

    def test_effective_rsd_knobs_affect_sha_only_when_relevant(self) -> None:
        self.assertTrue(SCAN_SCRIPT.is_file())
        self.assertTrue(RSD_DATASET.is_file())
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)

            # derived_As mode: transfer/ns/k_pivot are effective and must change scan_config_sha256.
            out_d1 = tdp / "derived_1"
            out_d2 = tdp / "derived_2"
            p_d1 = self._run_scan(
                out_dir=out_d1,
                extra_args=[
                    "--rsd-overlay",
                    "--rsd-data",
                    str(RSD_DATASET),
                    "--rsd-mode",
                    "derived_As",
                    "--rsd-transfer-model",
                    "bbks",
                    "--rsd-ns",
                    "0.965",
                    "--rsd-k-pivot",
                    "0.05",
                ],
            )
            p_d2 = self._run_scan(
                out_dir=out_d2,
                extra_args=[
                    "--rsd-overlay",
                    "--rsd-data",
                    str(RSD_DATASET),
                    "--rsd-mode",
                    "derived_As",
                    "--rsd-transfer-model",
                    "eh98_nowiggle",
                    "--rsd-ns",
                    "0.965",
                    "--rsd-k-pivot",
                    "0.05",
                ],
            )
            self.assertEqual(p_d1.returncode, 0, msg=(p_d1.stdout or "") + (p_d1.stderr or ""))
            self.assertEqual(p_d2.returncode, 0, msg=(p_d2.stdout or "") + (p_d2.stderr or ""))

            rows_d1 = self._load_rows(out_d1 / "e2_scan_points.jsonl")
            rows_d2 = self._load_rows(out_d2 / "e2_scan_points.jsonl")
            sha_d1 = self._first_sha(rows_d1)
            sha_d2 = self._first_sha(rows_d2)
            self.assertNotEqual(sha_d1, sha_d2)

            ok_rows_d1 = [r for r in rows_d1 if str(r.get("status", "")).strip().lower() == "ok"]
            self.assertTrue(ok_rows_d1)
            row_d1 = ok_rows_d1[0]
            self.assertIn("rsd_transfer_model", row_d1)
            self.assertIn("rsd_primordial_ns", row_d1)
            self.assertIn("rsd_primordial_k_pivot_mpc", row_d1)
            self.assertEqual(str(row_d1.get("rsd_transfer_model")), "bbks")
            self.assertAlmostEqual(float(row_d1.get("rsd_primordial_ns")), 0.965, places=12)
            self.assertAlmostEqual(float(row_d1.get("rsd_primordial_k_pivot_mpc")), 0.05, places=12)

            # nuisance/profile mode: transfer/ns/k_pivot are irrelevant and must not perturb scan_config_sha256.
            out_n1 = tdp / "nuisance_1"
            out_n2 = tdp / "nuisance_2"
            p_n1 = self._run_scan(
                out_dir=out_n1,
                extra_args=[
                    "--rsd-overlay",
                    "--rsd-data",
                    str(RSD_DATASET),
                    "--rsd-mode",
                    "nuisance_sigma8",
                    "--rsd-transfer-model",
                    "bbks",
                    "--rsd-ns",
                    "0.91",
                    "--rsd-k-pivot",
                    "0.03",
                ],
            )
            p_n2 = self._run_scan(
                out_dir=out_n2,
                extra_args=[
                    "--rsd-overlay",
                    "--rsd-data",
                    str(RSD_DATASET),
                    "--rsd-mode",
                    "nuisance_sigma8",
                    "--rsd-transfer-model",
                    "eh98_nowiggle",
                    "--rsd-ns",
                    "1.08",
                    "--rsd-k-pivot",
                    "0.09",
                ],
            )
            self.assertEqual(p_n1.returncode, 0, msg=(p_n1.stdout or "") + (p_n1.stderr or ""))
            self.assertEqual(p_n2.returncode, 0, msg=(p_n2.stdout or "") + (p_n2.stderr or ""))

            rows_n1 = self._load_rows(out_n1 / "e2_scan_points.jsonl")
            rows_n2 = self._load_rows(out_n2 / "e2_scan_points.jsonl")
            sha_n1 = self._first_sha(rows_n1)
            sha_n2 = self._first_sha(rows_n2)
            self.assertEqual(sha_n1, sha_n2)

            ok_rows_n1 = [r for r in rows_n1 if str(r.get("status", "")).strip().lower() == "ok"]
            ok_rows_n2 = [r for r in rows_n2 if str(r.get("status", "")).strip().lower() == "ok"]
            self.assertTrue(ok_rows_n1)
            self.assertTrue(ok_rows_n2)
            row_n1 = ok_rows_n1[0]
            row_n2 = ok_rows_n2[0]
            self.assertEqual(row_n1.get("rsd_transfer_model"), None)
            self.assertEqual(row_n1.get("rsd_primordial_ns"), None)
            self.assertEqual(row_n1.get("rsd_primordial_k_pivot_mpc"), None)
            self.assertAlmostEqual(float(row_n1.get("rsd_chi2")), float(row_n2.get("rsd_chi2")), places=12)
            self.assertAlmostEqual(
                float(row_n1.get("rsd_sigma8_0_best")),
                float(row_n2.get("rsd_sigma8_0_best")),
                places=12,
            )

            # rsd-overlay off: all rsd knobs are don't-care for config SHA.
            out_o1 = tdp / "off_1"
            out_o2 = tdp / "off_2"
            p_o1 = self._run_scan(
                out_dir=out_o1,
                extra_args=[
                    "--rsd-mode",
                    "derived_As",
                    "--rsd-transfer-model",
                    "bbks",
                    "--rsd-ns",
                    "0.95",
                    "--rsd-k-pivot",
                    "0.05",
                ],
            )
            p_o2 = self._run_scan(
                out_dir=out_o2,
                extra_args=[
                    "--rsd-mode",
                    "derived_As",
                    "--rsd-transfer-model",
                    "eh98_nowiggle",
                    "--rsd-ns",
                    "1.02",
                    "--rsd-k-pivot",
                    "0.07",
                ],
            )
            self.assertEqual(p_o1.returncode, 0, msg=(p_o1.stdout or "") + (p_o1.stderr or ""))
            self.assertEqual(p_o2.returncode, 0, msg=(p_o2.stdout or "") + (p_o2.stderr or ""))

            rows_o1 = self._load_rows(out_o1 / "e2_scan_points.jsonl")
            rows_o2 = self._load_rows(out_o2 / "e2_scan_points.jsonl")
            sha_o1 = self._first_sha(rows_o1)
            sha_o2 = self._first_sha(rows_o2)
            self.assertEqual(sha_o1, sha_o2)

            self.assertNotIn("rsd_overlay_ok", rows_o1[0])
            self.assertNotIn("rsd_chi2", rows_o1[0])

            # chi2-objective=cmb: rsd chi2 field/weight are don't-care for config SHA.
            out_c1 = tdp / "cmb_obj_1"
            out_c2 = tdp / "cmb_obj_2"
            p_c1 = self._run_scan(
                out_dir=out_c1,
                extra_args=[
                    "--rsd-overlay",
                    "--rsd-data",
                    str(RSD_DATASET),
                    "--chi2-objective",
                    "cmb",
                    "--rsd-chi2-field",
                    "rsd_chi2_total",
                    "--rsd-chi2-weight",
                    "0.25",
                ],
            )
            p_c2 = self._run_scan(
                out_dir=out_c2,
                extra_args=[
                    "--rsd-overlay",
                    "--rsd-data",
                    str(RSD_DATASET),
                    "--chi2-objective",
                    "cmb",
                    "--rsd-chi2-field",
                    "rsd_chi2",
                    "--rsd-chi2-weight",
                    "2.0",
                ],
            )
            self.assertEqual(p_c1.returncode, 0, msg=(p_c1.stdout or "") + (p_c1.stderr or ""))
            self.assertEqual(p_c2.returncode, 0, msg=(p_c2.stdout or "") + (p_c2.stderr or ""))
            sha_c1 = self._first_sha(self._load_rows(out_c1 / "e2_scan_points.jsonl"))
            sha_c2 = self._first_sha(self._load_rows(out_c2 / "e2_scan_points.jsonl"))
            self.assertEqual(sha_c1, sha_c2)

            # chi2-objective=joint: rsd chi2 field/weight are effective and must perturb SHA.
            out_j1 = tdp / "joint_obj_1"
            out_j2 = tdp / "joint_obj_2"
            p_j1 = self._run_scan(
                out_dir=out_j1,
                extra_args=[
                    "--rsd-overlay",
                    "--rsd-data",
                    str(RSD_DATASET),
                    "--chi2-objective",
                    "joint",
                    "--rsd-chi2-field",
                    "rsd_chi2_total",
                    "--rsd-chi2-weight",
                    "1.0",
                ],
            )
            p_j2 = self._run_scan(
                out_dir=out_j2,
                extra_args=[
                    "--rsd-overlay",
                    "--rsd-data",
                    str(RSD_DATASET),
                    "--chi2-objective",
                    "joint",
                    "--rsd-chi2-field",
                    "rsd_chi2_total",
                    "--rsd-chi2-weight",
                    "0.5",
                ],
            )
            self.assertEqual(p_j1.returncode, 0, msg=(p_j1.stdout or "") + (p_j1.stderr or ""))
            self.assertEqual(p_j2.returncode, 0, msg=(p_j2.stdout or "") + (p_j2.stderr or ""))
            sha_j1 = self._first_sha(self._load_rows(out_j1 / "e2_scan_points.jsonl"))
            sha_j2 = self._first_sha(self._load_rows(out_j2 / "e2_scan_points.jsonl"))
            self.assertNotEqual(sha_j1, sha_j2)


if __name__ == "__main__":
    unittest.main()

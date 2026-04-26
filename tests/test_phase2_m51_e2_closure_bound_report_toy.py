import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_e2_closure_bound_report.py"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


class TestPhase2M51E2ClosureBoundReportToy(unittest.TestCase):
    def _write_fixture(self, path: Path) -> None:
        rows = [
            {
                "params_hash": "hash_a",
                "status": "ok",
                "chi2_cmb": 2.5,
                "chi2_total": 9.0,
                "drift_metric": 0.3,
                "drift_sign_z2_5": True,
                "microphysics_plausible_ok": True,
                "microphysics_penalty": 0.0,
                "microphysics_max_rel_dev": 0.01,
                "params": {"H0": 67.0, "Omega_m": 0.31},
            },
            {
                "params_hash": "hash_b",
                "status": "ok",
                "chi2_cmb": 1.2,
                "chi2_total": 8.0,
                "drift_metric": -0.4,
                "drift_sign_z2_5": False,
                "microphysics_plausible_ok": True,
                "params": {"H0": 68.0, "Omega_m": 0.30},
            },
            {
                "params_hash": "hash_c",
                "status": "ok",
                "chi2_cmb": 1.8,
                "chi2_total": 7.5,
                "drift_metric": 0.5,
                "drift_sign_z2_5": True,
                "microphysics_plausible_ok": False,
                "microphysics_penalty": 0.5,
                "params": {"H0": 66.4, "Omega_m": 0.32},
            },
            {
                "params_hash": "hash_d",
                "status": "error",
                "chi2_cmb": 0.8,
                "chi2_total": 6.0,
                "drift_metric": 0.6,
                "microphysics_plausible_ok": True,
                "params": {"H0": 65.4, "Omega_m": 0.34},
            },
            {
                "params_hash": "hash_e",
                "chi2_parts": {"cmb_priors": {"chi2": 2.0}, "late": {"chi2": 1.0}},
                "drift_metric": 0.1,
                "params": {"H0": 67.5, "Omega_m": 0.305},
            },
            {
                "params_hash": "hash_f",
                "status": "ok",
                "drift_metric": 0.2,
                "microphysics_plausible_ok": True,
                "params": {"H0": 67.8, "Omega_m": 0.299},
            },
        ]
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        cmd = [sys.executable, str(SCRIPT), *args]
        return subprocess.run(cmd, cwd=str(ROOT.parent), text=True, capture_output=True)

    def test_schema_best_selection_and_determinism(self):
        self.assertTrue(SCRIPT.is_file())
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            in_jsonl = td_path / "scan.jsonl"
            out_a = td_path / "out_a"
            out_b = td_path / "out_b"
            self._write_fixture(in_jsonl)

            proc_a = self._run("--in-jsonl", str(in_jsonl), "--out-dir", str(out_a), "--top-n", "3")
            out_a_log = (proc_a.stdout or "") + (proc_a.stderr or "")
            self.assertEqual(proc_a.returncode, 0, msg=out_a_log)

            proc_b = self._run("--in-jsonl", str(in_jsonl), "--out-dir", str(out_b), "--top-n", "3")
            out_b_log = (proc_b.stdout or "") + (proc_b.stderr or "")
            self.assertEqual(proc_b.returncode, 0, msg=out_b_log)

            json_a = out_a / "phase2_e2_closure_bound_report.json"
            md_a = out_a / "phase2_e2_closure_bound_report.md"
            tex_a = out_a / "phase2_e2_closure_bound_report.tex"
            csv_a = out_a / "phase2_e2_closure_bound_candidates.csv"
            for path in (json_a, md_a, tex_a, csv_a):
                self.assertTrue(path.is_file(), msg=str(path))

            payload = json.loads(json_a.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "phase2_e2_closure_bound_report_v1")
            self.assertIsInstance(payload.get("input_sha256"), str)

            counts = payload.get("counts") or {}
            self.assertEqual(counts.get("n_total"), 6)
            self.assertEqual(counts.get("n_status_ok"), 5)
            self.assertEqual(counts.get("n_eligible"), 4)
            self.assertEqual(counts.get("n_drift_positive"), 3)
            self.assertEqual(counts.get("n_plausible"), 3)
            self.assertEqual(counts.get("n_candidate_pool"), 3)
            self.assertEqual(counts.get("n_incomplete"), 2)

            best = payload.get("best") or {}
            self.assertEqual((best.get("overall") or {}).get("params_hash"), "hash_b")
            self.assertEqual((best.get("drift_positive") or {}).get("params_hash"), "hash_c")
            self.assertEqual((best.get("drift_positive_plausible_only") or {}).get("params_hash"), "hash_e")

            top_rows = _read_csv(csv_a)
            self.assertEqual(len(top_rows), 3)
            self.assertEqual(top_rows[0].get("params_hash"), "hash_c")
            self.assertEqual(top_rows[1].get("params_hash"), "hash_e")
            self.assertEqual(top_rows[2].get("params_hash"), "hash_a")

            json_b = out_b / "phase2_e2_closure_bound_report.json"
            md_b = out_b / "phase2_e2_closure_bound_report.md"
            tex_b = out_b / "phase2_e2_closure_bound_report.tex"
            csv_b = out_b / "phase2_e2_closure_bound_candidates.csv"
            self.assertEqual(_sha256(json_a), _sha256(json_b))
            self.assertEqual(_sha256(md_a), _sha256(md_b))
            self.assertEqual(_sha256(tex_a), _sha256(tex_b))
            self.assertEqual(_sha256(csv_a), _sha256(csv_b))


if __name__ == "__main__":
    unittest.main()

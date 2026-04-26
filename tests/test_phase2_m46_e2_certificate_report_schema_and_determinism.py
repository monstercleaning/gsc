import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_e2_certificate_report.py"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestPhase2M46E2CertificateReport(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        cmd = [sys.executable, str(SCRIPT), *args]
        return subprocess.run(cmd, cwd=str(ROOT.parent), text=True, capture_output=True)

    def _write_fixture(self, path: Path) -> None:
        rows = [
            {
                "params_hash": "h1",
                "status": "ok",
                "chi2_total": 8.0,
                "chi2_cmb": 2.0,
                "drift_metric": 0.4,
                "drift_sign_z2_5": True,
                "microphysics_plausible_ok": True,
                "microphysics_penalty": 0.0,
                "microphysics_max_rel_dev": 0.01,
                "params": {"H0": 67.0, "Omega_m": 0.31},
            },
            {
                "params_hash": "h2",
                "status": "ok",
                "chi2_total": 7.0,
                "chi2_cmb": 1.5,
                "drift_metric": 0.2,
                "drift_sign_z2_5": True,
                "microphysics_plausible_ok": False,
                "microphysics_penalty": 0.4,
                "microphysics_max_rel_dev": 0.2,
                "params": {"H0": 66.5, "Omega_m": 0.32},
            },
            {
                "params_hash": "h3",
                "status": "ok",
                "chi2_total": 7.0,
                "chi2_cmb": 1.0,
                "drift_metric": -0.1,
                "drift_sign_z2_5": False,
                "microphysics_plausible_ok": True,
                "microphysics_penalty": 0.0,
                "microphysics_max_rel_dev": 0.02,
                "params": {"H0": 66.8, "Omega_m": 0.30},
            },
            {
                "params_hash": "h4",
                "status": "error",
                "chi2_total": 6.0,
                "chi2_cmb": 0.8,
                "drift_metric": 0.3,
                "drift_sign_z2_5": True,
                "microphysics_plausible_ok": True,
                "params": {"H0": 65.9, "Omega_m": 0.34},
            },
            {
                "params_hash": "h5",
                "status": "ok",
                "chi2_total": 9.2,
                "drift_metric": 0.5,
                "drift_sign_z2_5": True,
                "microphysics_plausible_ok": True,
                "params": {"H0": 67.4, "Omega_m": 0.28},
            },
            {
                "params_hash": "h6",
                "status": "ok",
                "chi2_total": 11.0,
                "chi2_cmb": 5.0,
                "drift_metric": 0.7,
                "drift_sign_z2_5": True,
                "microphysics_plausible_ok": True,
                "params": {"H0": 68.0, "Omega_m": 0.29},
            },
            {
                "params_hash": "h7",
                "chi2_total": 9.0,
                "chi2_cmb": 2.5,
                "drift_metric": 0.35,
                "drift_sign_z2_5": True,
                "params": {"H0": 67.3, "Omega_m": 0.305},
            },
            {
                "params_hash": "h8",
                "status": "skipped_drift",
                "chi2_total": 1.0e99,
                "chi2_cmb": 1.0e99,
                "drift_metric": -1.0,
                "drift_precheck_ok": False,
                "params": {"H0": 71.0, "Omega_m": 0.20},
            },
        ]
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")

    def test_schema_counts_and_determinism(self) -> None:
        self.assertTrue(SCRIPT.is_file())
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            jsonl = td_path / "merged.jsonl"
            out_a = td_path / "cert_a"
            out_b = td_path / "cert_b"
            self._write_fixture(jsonl)

            common = [
                "--jsonl",
                str(jsonl),
                "--status-filter",
                "ok_only",
                "--plausibility",
                "plausible_only",
                "--cmb-chi2-threshold",
                "4.0",
                "--late-chi2-threshold",
                "10.0",
                "--require-drift",
                "positive",
                "--top-k",
                "3",
                "--created-utc",
                "2000-01-01T00:00:00Z",
            ]

            proc_a = self._run(*common, "--outdir", str(out_a))
            proc_b = self._run(*common, "--outdir", str(out_b))
            self.assertEqual(proc_a.returncode, 0, msg=(proc_a.stdout or "") + (proc_a.stderr or ""))
            self.assertEqual(proc_b.returncode, 0, msg=(proc_b.stdout or "") + (proc_b.stderr or ""))

            cert_a = out_a / "e2_certificate.json"
            cert_md_a = out_a / "e2_certificate.md"
            cert_b = out_b / "e2_certificate.json"
            cert_md_b = out_b / "e2_certificate.md"
            self.assertTrue(cert_a.is_file())
            self.assertTrue(cert_md_a.is_file())
            self.assertTrue(cert_b.is_file())
            self.assertTrue(cert_md_b.is_file())

            payload = json.loads(cert_a.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "phase2_e2_certificate_v1")
            counts = payload.get("counts") or {}
            self.assertEqual(counts.get("n_total_records"), 8)
            self.assertEqual(counts.get("n_records_invalid_json"), 0)
            self.assertEqual(counts.get("n_ok"), 5)
            self.assertEqual(counts.get("n_eligible"), 4)
            self.assertEqual(counts.get("n_plausible"), 3)
            self.assertEqual(counts.get("n_drift_ok"), 3)
            self.assertEqual(counts.get("n_cmb_ok"), 3)
            self.assertEqual(counts.get("n_joint_ok"), 1)

            best = payload.get("best") or {}
            self.assertEqual((best.get("best_overall") or {}).get("params_hash"), "h2")
            self.assertEqual((best.get("best_plausible") or {}).get("params_hash"), "h3")
            self.assertEqual((best.get("best_drift_ok") or {}).get("params_hash"), "h2")
            self.assertEqual((best.get("best_cmb_ok") or {}).get("params_hash"), "h2")
            self.assertEqual((best.get("best_joint_ok") or {}).get("params_hash"), "h1")

            warnings = payload.get("warnings") or []
            self.assertTrue(any("missing status" in str(w).lower() and "unknown" in str(w).lower() for w in warnings))
            self.assertTrue(any("missing microphysics_plausible_ok" in str(w).lower() for w in warnings))

            top_overall = (payload.get("top_k") or {}).get("overall") or []
            self.assertEqual([row.get("params_hash") for row in top_overall], ["h2", "h3", "h1"])

            self.assertEqual(_sha256(cert_a), _sha256(cert_b))
            self.assertEqual(_sha256(cert_md_a), _sha256(cert_md_b))


if __name__ == "__main__":
    unittest.main()

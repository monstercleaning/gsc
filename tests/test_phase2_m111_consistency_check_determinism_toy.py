import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_consistency_check.py"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestPhase2M111ConsistencyCheckDeterminismToy(unittest.TestCase):
    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    def test_report_is_deterministic(self) -> None:
        self.assertTrue(SCRIPT.is_file())
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bundle_dir = td_path / "bundle"
            bundle_dir.mkdir(parents=True, exist_ok=True)

            self._write_json(
                bundle_dir / "CANDIDATE_RECORD.json",
                {
                    "params_hash": "h_consistency",
                    "plan_point_id": "p0",
                    "params": {"H0": 67.4, "Omega_m": 0.315, "omega_b_h2": 0.0224, "omega_c_h2": 0.12},
                    "rsd_chi2_total": 9.5,
                },
            )
            (bundle_dir / "phase2_sf_rsd_summary.md").write_text(
                "phase2_sf_rsd_summary_snippet_v1\n",
                encoding="utf-8",
            )
            self._write_json(
                bundle_dir / "boltzmann_results" / "RESULTS_SUMMARY.json",
                {
                    "schema": "phase2_pt_boltzmann_results_pack_v1",
                    "spectra_detected": {"has_tt": True},
                },
            )
            (bundle_dir / "boltzmann_results" / "outputs" / "tt_mock.dat").parent.mkdir(parents=True, exist_ok=True)
            (bundle_dir / "boltzmann_results" / "outputs" / "tt_mock.dat").write_text(
                "# ell C_ell\n2 1000\n3 900\n4 800\n",
                encoding="utf-8",
            )

            out_a = td_path / "consistency_a"
            out_b = td_path / "consistency_b"
            cmd_base = [
                sys.executable,
                str(SCRIPT),
                "--bundle-dir",
                str(bundle_dir),
                "--created-utc",
                "2000-01-01T00:00:00Z",
                "--format",
                "json",
            ]

            first = subprocess.run(cmd_base + ["--outdir", str(out_a)], cwd=str(ROOT), text=True, capture_output=True)
            self.assertEqual(first.returncode, 0, msg=(first.stdout or "") + (first.stderr or ""))
            second = subprocess.run(cmd_base + ["--outdir", str(out_b)], cwd=str(ROOT), text=True, capture_output=True)
            self.assertEqual(second.returncode, 0, msg=(second.stdout or "") + (second.stderr or ""))

            json_a = out_a / "CONSISTENCY_REPORT.json"
            json_b = out_b / "CONSISTENCY_REPORT.json"
            md_a = out_a / "CONSISTENCY_REPORT.md"
            md_b = out_b / "CONSISTENCY_REPORT.md"
            for path in (json_a, json_b, md_a, md_b):
                self.assertTrue(path.is_file(), msg=str(path))

            self.assertEqual(_sha256(json_a), _sha256(json_b))
            self.assertEqual(_sha256(md_a), _sha256(md_b))

            payload = json.loads(json_a.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "phase2_consistency_report_v1")
            self.assertEqual(payload.get("status"), "ok")
            presence = payload.get("presence") or {}
            self.assertTrue(bool(presence.get("candidate_present")))
            self.assertTrue(bool(presence.get("rsd_expected")))
            self.assertTrue(bool(presence.get("pt_results_present")))


if __name__ == "__main__":
    unittest.main()

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_e2_best_candidates_report.py"


class TestPhase2M85E2BestCandidatesReportRsdOverlayToy(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        cmd = [sys.executable, str(SCRIPT), *args]
        return subprocess.run(cmd, cwd=str(ROOT.parent), text=True, capture_output=True)

    def _write_fixture(self, path: Path) -> None:
        rows = [
            {
                "params_hash": "cand_sf_a",
                "plan_point_id": "sf_p1",
                "status": "ok",
                "chi2_total": 8.0,
                "chi2_cmb": 2.0,
                "params": {"H0": 67.4, "Omega_m": 0.315, "Omega_Lambda": 0.685},
                "microphysics_plausible_ok": True,
                "model": "lcdm",
            },
            {
                "params_hash": "cand_sf_b",
                "plan_point_id": "sf_p2",
                "status": "ok",
                "chi2_total": 7.7,
                "chi2_cmb": 2.3,
                "params": {"H0": 68.0, "Omega_m": 0.33, "Omega_Lambda": 0.67},
                "microphysics_plausible_ok": True,
                "model": "lcdm",
            },
            {
                "params_hash": "cand_sf_missing",
                "plan_point_id": "sf_p3",
                "status": "ok",
                "chi2_total": 9.1,
                "chi2_cmb": 2.8,
                "model": "lcdm",
            },
        ]
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")

    def test_overlay_is_additive_and_emits_sf_snippets(self) -> None:
        self.assertTrue(SCRIPT.is_file())
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            in_jsonl = td_path / "scan.jsonl"
            sf_md = td_path / "phase2_sf_rsd_summary.md"
            sf_tex = td_path / "phase2_sf_rsd_summary.tex"
            self._write_fixture(in_jsonl)

            baseline = self._run(
                "--input",
                str(in_jsonl),
                "--format",
                "json",
                "--top-n",
                "3",
            )
            self.assertEqual(baseline.returncode, 0, msg=(baseline.stdout or "") + (baseline.stderr or ""))
            base_payload = json.loads(baseline.stdout)
            self.assertNotIn("sf_rsd_overlay", base_payload)
            top_rows_base = base_payload.get("top_candidates") or []
            self.assertTrue(top_rows_base)
            self.assertNotIn("chi2_rsd", top_rows_base[0])

            overlay = self._run(
                "--input",
                str(in_jsonl),
                "--format",
                "json",
                "--top-n",
                "3",
                "--sf-rsd",
                "--sf-snippet-md-out",
                str(sf_md),
                "--sf-snippet-tex-out",
                str(sf_tex),
            )
            out_text = (overlay.stdout or "") + (overlay.stderr or "")
            self.assertEqual(overlay.returncode, 0, msg=out_text)
            payload = json.loads(overlay.stdout)
            self.assertIn("sf_rsd_overlay", payload)
            sf_overlay = payload.get("sf_rsd_overlay") or {}
            self.assertTrue(sf_overlay.get("enabled"))
            self.assertGreater(int(sf_overlay.get("n_points", 0)), 0)

            top_rows = payload.get("top_candidates") or []
            self.assertTrue(top_rows)
            self.assertIn("chi2_rsd", top_rows[0])
            self.assertIn("sigma8_0_best", top_rows[0])
            self.assertIn("chi2_total_plus_rsd", top_rows[0])

            self.assertTrue(sf_md.is_file())
            self.assertTrue(sf_tex.is_file())
            md_text = sf_md.read_text(encoding="utf-8")
            tex_text = sf_tex.read_text(encoding="utf-8")
            self.assertIn("phase2_sf_rsd_summary_snippet_v1", md_text)
            self.assertIn("phase2_sf_rsd_summary_snippet_v1", tex_text)


if __name__ == "__main__":
    unittest.main()

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_e2_best_candidates_report.py"


class TestPhase2M90E2BestCandidatesReportJointRankToy(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        cmd = [sys.executable, str(SCRIPT), *args]
        return subprocess.run(cmd, cwd=str(ROOT.parent), text=True, capture_output=True)

    def _write_rows(self, path: Path, rows: list[dict]) -> None:
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")

    def test_joint_ranking_and_marker_outputs(self) -> None:
        self.assertTrue(SCRIPT.is_file())
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            src = td_path / "scan.jsonl"
            md_out = td_path / "best.md"
            tex_out = td_path / "best.tex"
            rows = [
                {
                    "params_hash": "cand_cmb",
                    "plan_point_id": "p1",
                    "status": "ok",
                    "chi2_total": 4.0,
                    "microphysics_plausible_ok": True,
                },
                {
                    "params_hash": "cand_joint",
                    "plan_point_id": "p2",
                    "status": "ok",
                    "chi2_total": 6.0,
                    "rsd_overlay_ok": True,
                    "rsd_chi2": 1.0,
                    "rsd_sigma8_0_best": 0.82,
                    "rsd_n": 22,
                    "rsd_dataset_sha256": "a" * 64,
                    "rsd_dataset_id": "gold2017_plus_zhao2018",
                    "rsd_mode": "profile_sigma8_0",
                    "rsd_ap_correction": "none",
                    "microphysics_plausible_ok": True,
                },
                {
                    "params_hash": "cand_worse_joint",
                    "plan_point_id": "p3",
                    "status": "ok",
                    "chi2_total": 5.0,
                    "rsd_overlay_ok": True,
                    "rsd_chi2": 8.0,
                    "rsd_sigma8_0_best": 0.77,
                    "rsd_n": 22,
                    "rsd_dataset_sha256": "a" * 64,
                    "rsd_dataset_id": "gold2017_plus_zhao2018",
                    "rsd_mode": "profile_sigma8_0",
                    "rsd_ap_correction": "none",
                    "microphysics_plausible_ok": False,
                },
                {
                    "params_hash": "cand_error",
                    "status": "error",
                    "chi2_total": 2.0,
                },
            ]
            self._write_rows(src, rows)

            proc_cmb = self._run(
                "--input",
                str(src),
                "--format",
                "json",
                "--rank-by",
                "cmb",
                "--top-n",
                "3",
            )
            self.assertEqual(proc_cmb.returncode, 0, msg=(proc_cmb.stdout or "") + (proc_cmb.stderr or ""))
            payload_cmb = json.loads(proc_cmb.stdout)
            self.assertEqual((payload_cmb.get("best_by_cmb") or {}).get("params_hash"), "cand_cmb")

            proc_joint = self._run(
                "--input",
                str(src),
                "--format",
                "json",
                "--rank-by",
                "joint",
                "--top-n",
                "3",
                "--md-out",
                str(md_out),
                "--tex-out",
                str(tex_out),
            )
            self.assertEqual(proc_joint.returncode, 0, msg=(proc_joint.stdout or "") + (proc_joint.stderr or ""))
            payload_joint = json.loads(proc_joint.stdout)
            self.assertEqual((payload_joint.get("best_by_cmb") or {}).get("params_hash"), "cand_cmb")
            self.assertEqual((payload_joint.get("best_by_joint") or {}).get("params_hash"), "cand_joint")

            top = payload_joint.get("top_candidates") or []
            self.assertTrue(top)
            self.assertEqual(top[0].get("params_hash"), "cand_joint")
            self.assertEqual(top[0].get("sf_status"), "ok")
            self.assertAlmostEqual(float(top[0].get("joint_score")), 7.0, places=9)

            self.assertTrue(md_out.is_file())
            self.assertTrue(tex_out.is_file())
            md_text = md_out.read_text(encoding="utf-8")
            tex_text = tex_out.read_text(encoding="utf-8")
            self.assertIn("phase2_e2_best_candidates_snippet_v2", md_text)
            self.assertIn("phase2_e2_best_candidates_snippet_v2", tex_text)
            self.assertIn("Best by CMB (eligible)", md_text)
            self.assertIn("Best by joint CMB+RSD (eligible)", md_text)

    def test_joint_rank_requires_rsd_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            src = td_path / "scan_no_rsd.jsonl"
            rows = [
                {"params_hash": "a", "status": "ok", "chi2_total": 4.0},
                {"params_hash": "b", "status": "ok", "chi2_total": 4.5},
            ]
            self._write_rows(src, rows)

            proc = self._run(
                "--input",
                str(src),
                "--format",
                "json",
                "--rank-by",
                "joint",
            )
            self.assertEqual(proc.returncode, 2, msg=(proc.stdout or "") + (proc.stderr or ""))
            self.assertIn("missing required RSD fields for joint ranking", (proc.stderr or ""))


if __name__ == "__main__":
    unittest.main()

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_e2_best_candidates_report.py"
ASSETS_SCRIPT = ROOT / "scripts" / "phase2_e2_make_paper_assets.py"
KNOBS_DIR = "paper_assets_cmb_e2_closure_to_physical_knobs"


class TestPhase2M65E2BestCandidatesReport(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        cmd = [sys.executable, str(SCRIPT), *args]
        return subprocess.run(cmd, cwd=str(ROOT.parent), text=True, capture_output=True)

    def _run_assets(self, *args: str) -> subprocess.CompletedProcess:
        cmd = [sys.executable, str(ASSETS_SCRIPT), *args]
        return subprocess.run(cmd, cwd=str(ROOT.parent), text=True, capture_output=True)

    def _write_fixture(self, shard_a: Path, shard_b: Path) -> None:
        rows_a = [
            {
                "params_hash": "cand_a",
                "plan_point_id": "p1",
                "status": "ok",
                "chi2_total": 8.0,
                "chi2_cmb": 2.2,
                "drift_metric": 0.21,
                "microphysics_plausible_ok": True,
                "model": "lcdm",
            },
            {
                "params_hash": "cand_b",
                "plan_point_id": "p2",
                "status": "ok",
                "chi2_total": 7.5,
                "chi2_parts": {"cmb_priors": {"chi2": 2.0}, "late": {"chi2": 5.5}},
                "drift_precheck_ok": True,
                "microphysics_plausible_ok": False,
                "deformation_family": "logh_two_window",
            },
            {
                "params_hash": "cand_err",
                "plan_point_id": "p3",
                "status": "error",
                "chi2_total": 6.0,
                "error": "ValueError: boom",
            },
        ]
        rows_b = [
            {
                "plan_point_id": "p4",
                "chi2_total": 7.8,
                "chi2_cmb": 2.1,
                "params": {"H0": 67.3, "Omega_m": 0.31},
                "drift_sign_z2_5": True,
                "model": "lcdm",
            },
            {
                "params_hash": "cand_skip",
                "plan_point_id": "p5",
                "status": "skipped_drift",
                "chi2_total": 1.0e99,
                "microphysics_plausible_ok": True,
            },
            {
                "params_hash": "cand_missing_chi2",
                "status": "ok",
                "chi2_cmb": 9.0,
                "microphysics_plausible_ok": True,
            },
        ]

        with shard_a.open("w", encoding="utf-8") as fh:
            for row in rows_a:
                fh.write(json.dumps(row, sort_keys=True) + "\n")
            fh.write("{broken json\n")
            fh.write("\n")

        with shard_b.open("w", encoding="utf-8") as fh:
            for row in rows_b:
                fh.write(json.dumps(row, sort_keys=True) + "\n")

    def test_json_topn_tex_and_exit_codes(self) -> None:
        self.assertTrue(SCRIPT.is_file())
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            shard_a = td_path / "shard_a.jsonl"
            shard_b = td_path / "shard_b.jsonl"
            tex_out = td_path / "best.tex"
            self._write_fixture(shard_a, shard_b)

            proc = self._run(
                "--input",
                str(shard_a),
                "--input",
                str(shard_b),
                "--format",
                "json",
                "--top-n",
                "3",
            )
            out_text = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=out_text)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload.get("schema"), "phase2_e2_best_candidates_report_v1")
            header = payload.get("header") or {}
            self.assertEqual(int(header.get("n_records_parsed", -1)), 6)
            self.assertEqual(int(header.get("n_invalid_lines", -1)), 1)
            self.assertEqual(int(header.get("n_missing_chi2", -1)), 1)

            status_counts = payload.get("status_counts") or {}
            self.assertEqual(int(status_counts.get("ok", 0)), 3)
            self.assertEqual(int(status_counts.get("error", 0)), 1)
            self.assertEqual(int(status_counts.get("unknown", 0)), 1)
            self.assertEqual(int(status_counts.get("skipped_drift", 0)), 1)

            best = payload.get("best_overall_eligible") or {}
            self.assertEqual(best.get("params_hash"), "cand_b")
            self.assertEqual(best.get("status"), "ok")

            best_plausible = payload.get("best_plausible_eligible") or {}
            self.assertEqual(best_plausible.get("params_hash"), "cand_a")

            top = payload.get("top_candidates") or []
            self.assertEqual([row.get("params_hash") for row in top], ["cand_b", "cand_a"])

            # Deterministic JSON stdout for identical inputs.
            proc_repeat = self._run(
                "--input",
                str(shard_a),
                "--input",
                str(shard_b),
                "--format",
                "json",
                "--top-n",
                "3",
            )
            self.assertEqual(proc_repeat.returncode, 0, msg=(proc_repeat.stdout or "") + (proc_repeat.stderr or ""))
            self.assertEqual(proc.stdout, proc_repeat.stdout)

            proc_any = self._run(
                "--input",
                str(shard_a),
                "--input",
                str(shard_b),
                "--status-filter",
                "any_eligible",
                "--format",
                "json",
                "--top-n",
                "3",
            )
            self.assertEqual(proc_any.returncode, 0, msg=(proc_any.stdout or "") + (proc_any.stderr or ""))
            payload_any = json.loads(proc_any.stdout)
            top_any = payload_any.get("top_candidates") or []
            self.assertEqual([row.get("plan_point_id") for row in top_any[:3]], ["p2", "p4", "p1"])
            self.assertNotEqual((top_any[1] or {}).get("params_hash_source"), "params_hash")

            proc_tex = self._run(
                "--input",
                str(shard_a),
                "--input",
                str(shard_b),
                "--format",
                "tex",
                "--top-n",
                "3",
                "--tex-out",
                str(tex_out),
            )
            self.assertEqual(proc_tex.returncode, 0, msg=(proc_tex.stdout or "") + (proc_tex.stderr or ""))
            tex_text = tex_out.read_text(encoding="utf-8")
            self.assertIn("\\begin{tabular}", tex_text)
            self.assertIn("logh\\_two\\_window", tex_text)
            self.assertIn("p2", tex_text)
            self.assertIn("p1", tex_text)

            missing = self._run("--input", str(td_path / "does_not_exist.jsonl"), "--format", "json")
            self.assertEqual(missing.returncode, 1)

    def test_make_paper_assets_includes_best_candidates_snippets(self) -> None:
        self.assertTrue(ASSETS_SCRIPT.is_file())
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            shard_a = td_path / "shard_a.jsonl"
            shard_b = td_path / "shard_b.jsonl"
            outdir = td_path / "assets"
            self._write_fixture(shard_a, shard_b)

            proc = self._run_assets(
                "--jsonl",
                str(shard_a),
                "--jsonl",
                str(shard_b),
                "--mode",
                "all",
                "--outdir",
                str(outdir),
                "--created-utc",
                "2000-01-01T00:00:00Z",
            )
            out_text = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=out_text)

            knobs_dir = outdir / KNOBS_DIR
            report_json = knobs_dir / "phase2_e2_best_candidates_report.json"
            report_md = knobs_dir / "phase2_e2_best_candidates.md"
            report_tex = knobs_dir / "phase2_e2_best_candidates.tex"
            sf_rsd_md = knobs_dir / "phase2_sf_rsd_summary.md"
            sf_rsd_tex = knobs_dir / "phase2_sf_rsd_summary.tex"
            snippet_md = knobs_dir / "snippets" / "phase2_e2_best_candidates.md"
            snippet_tex = knobs_dir / "snippets" / "phase2_e2_best_candidates.tex"
            sf_snippet_md = knobs_dir / "snippets" / "phase2_sf_rsd_summary.md"
            sf_snippet_tex = knobs_dir / "snippets" / "phase2_sf_rsd_summary.tex"
            for path in (
                report_json,
                report_md,
                report_tex,
                sf_rsd_md,
                sf_rsd_tex,
                snippet_md,
                snippet_tex,
                sf_snippet_md,
                sf_snippet_tex,
            ):
                self.assertTrue(path.is_file(), msg=str(path))

            report_md_text = report_md.read_text(encoding="utf-8")
            report_tex_text = report_tex.read_text(encoding="utf-8")
            self.assertIn("phase2_e2_best_candidates_snippet_v2", report_md_text)
            self.assertIn("phase2_e2_best_candidates_snippet_v2", report_tex_text)
            self.assertIn("Best by CMB (eligible)", report_md_text)
            self.assertIn("Best by joint CMB+RSD (eligible)", report_md_text)

            manifest = json.loads((outdir / "paper_assets_manifest.json").read_text(encoding="utf-8"))
            files = {str(row.get("relpath")) for row in (manifest.get("files") or [])}
            snippets = {str(row.get("relpath")) for row in (manifest.get("snippets") or [])}
            self.assertIn(f"{KNOBS_DIR}/phase2_e2_best_candidates_report.json", files)
            self.assertIn(f"{KNOBS_DIR}/phase2_e2_best_candidates.md", files)
            self.assertIn(f"{KNOBS_DIR}/phase2_e2_best_candidates.tex", files)
            self.assertIn(f"{KNOBS_DIR}/phase2_sf_rsd_summary.md", files)
            self.assertIn(f"{KNOBS_DIR}/phase2_sf_rsd_summary.tex", files)
            self.assertIn(f"{KNOBS_DIR}/snippets/phase2_e2_best_candidates.md", snippets)
            self.assertIn(f"{KNOBS_DIR}/snippets/phase2_e2_best_candidates.tex", snippets)
            self.assertIn(f"{KNOBS_DIR}/snippets/phase2_sf_rsd_summary.md", snippets)
            self.assertIn(f"{KNOBS_DIR}/snippets/phase2_sf_rsd_summary.tex", snippets)


if __name__ == "__main__":
    unittest.main()

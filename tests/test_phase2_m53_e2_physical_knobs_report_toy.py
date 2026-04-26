import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
REPORT_SCRIPT = ROOT / "scripts" / "phase2_e2_physical_knobs_report.py"
ASSETS_SCRIPT = ROOT / "scripts" / "phase2_e2_make_paper_assets.py"
KNOBS_DIR = "paper_assets_cmb_e2_closure_to_physical_knobs"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestPhase2M53E2PhysicalKnobsReportToy(unittest.TestCase):
    def _run_report(self, *args: str) -> subprocess.CompletedProcess:
        cmd = [sys.executable, str(REPORT_SCRIPT), *args]
        return subprocess.run(cmd, cwd=str(ROOT.parent), text=True, capture_output=True)

    def _run_assets(self, *args: str) -> subprocess.CompletedProcess:
        cmd = [sys.executable, str(ASSETS_SCRIPT), *args]
        return subprocess.run(cmd, cwd=str(ROOT.parent), text=True, capture_output=True)

    def _write_fixture(self, path: Path) -> None:
        rows = [
            {
                "params_hash": "m53_a",
                "status": "ok",
                "chi2_cmb": 2.0,
                "chi2_total": 8.2,
                "drift_precheck_ok": True,
                "drift_metric": 0.41,
                "drift_sign_z3": True,
                "microphysics_plausible_ok": True,
                "microphysics_penalty": 0.0,
                "microphysics_max_rel_dev": 0.01,
                "params": {
                    "omega_b_h2": 0.02235,
                    "omega_c_h2": 0.1202,
                    "N_eff": 3.046,
                    "H0": 67.4,
                    "Omega_m": 0.315,
                },
                "microphysics_knobs": {
                    "z_star_scale": 1.0,
                    "r_s_scale": 1.02,
                    "r_d_scale": 1.0,
                },
            },
            {
                "params_hash": "m53_b",
                "status": "ok",
                "chi2_parts": {"cmb_priors": {"chi2": 2.6}, "sn": {"chi2": 7.1}},
                "drift_precheck_ok": True,
                "drift_metric": 0.28,
                "drift_sign_z3": True,
                "microphysics_plausible_ok": False,
                "microphysics_penalty": 1.3,
                "microphysics_max_rel_dev": 0.07,
                "params": {
                    "omega_b_h2": 0.02210,
                    "omega_c_h2": 0.1210,
                    "N_eff": 3.18,
                    "H0": 68.0,
                    "Omega_m": 0.305,
                },
                "microphysics_knobs": {
                    "z_star_scale": 1.03,
                    "r_s_scale": 1.07,
                    "r_d_scale": 0.95,
                },
            },
            {
                "params_hash": "m53_c",
                "status": "skipped_drift",
                "chi2_cmb": 1.0e99,
                "chi2_total": 1.0e99,
                "drift_precheck_ok": False,
                "drift_metric": -0.05,
                "drift_sign_z3": False,
                "params": {
                    "omega_b_h2": 0.02250,
                    "omega_c_h2": 0.1190,
                    "N_eff": 2.95,
                    "H0": 66.7,
                    "Omega_m": 0.325,
                },
            },
        ]
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")

    def test_report_toy_outputs_and_determinism(self):
        self.assertTrue(REPORT_SCRIPT.is_file())
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            out_a = td_path / "report_a"
            out_b = td_path / "report_b"

            proc_a = self._run_report("--toy", "--outdir", str(out_a), "--top-k", "5")
            proc_b = self._run_report("--toy", "--outdir", str(out_b), "--top-k", "5")
            out_text_a = (proc_a.stdout or "") + (proc_a.stderr or "")
            out_text_b = (proc_b.stdout or "") + (proc_b.stderr or "")
            self.assertEqual(proc_a.returncode, 0, msg=out_text_a)
            self.assertEqual(proc_b.returncode, 0, msg=out_text_b)

            json_a = out_a / "phase2_e2_physical_knobs_report.json"
            md_a = out_a / "phase2_e2_physical_knobs.md"
            tex_a = out_a / "phase2_e2_physical_knobs.tex"
            for path in (json_a, md_a, tex_a):
                self.assertTrue(path.is_file(), msg=str(path))

            payload = json.loads(json_a.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema_id"), "phase2_e2_physical_knobs_report_v1")
            self.assertGreaterEqual(int(payload.get("n_records_total", 0)), 1)
            self.assertIn("table", payload)

            for rel in (
                "phase2_e2_physical_knobs_report.json",
                "phase2_e2_physical_knobs.md",
                "phase2_e2_physical_knobs.tex",
            ):
                self.assertEqual(_sha256(out_a / rel), _sha256(out_b / rel), msg=rel)

    def test_make_paper_assets_includes_physical_knobs_outputs_and_manifest_entries(self):
        self.assertTrue(ASSETS_SCRIPT.is_file())
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            jsonl = td_path / "scan.jsonl"
            outdir = td_path / "assets"
            self._write_fixture(jsonl)

            proc = self._run_assets(
                "--jsonl",
                str(jsonl),
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
            report_json = knobs_dir / "phase2_e2_physical_knobs_report.json"
            report_md = knobs_dir / "phase2_e2_physical_knobs.md"
            report_tex = knobs_dir / "phase2_e2_physical_knobs.tex"
            for path in (report_json, report_md, report_tex):
                self.assertTrue(path.is_file(), msg=str(path))

            snippet_md = knobs_dir / "snippets" / "phase2_e2_physical_knobs.md"
            snippet_tex = knobs_dir / "snippets" / "phase2_e2_physical_knobs.tex"
            best_md = knobs_dir / "snippets" / "phase2_e2_best_candidates.md"
            best_tex = knobs_dir / "snippets" / "phase2_e2_best_candidates.tex"
            best_json = knobs_dir / "phase2_e2_best_candidates_report.json"
            self.assertTrue(snippet_md.is_file())
            self.assertTrue(snippet_tex.is_file())
            self.assertTrue(best_md.is_file())
            self.assertTrue(best_tex.is_file())
            self.assertTrue(best_json.is_file())

            manifest = json.loads((outdir / "paper_assets_manifest.json").read_text(encoding="utf-8"))
            files = {str(row.get("relpath")) for row in (manifest.get("files") or [])}
            snippets = {str(row.get("relpath")) for row in (manifest.get("snippets") or [])}
            self.assertIn(f"{KNOBS_DIR}/phase2_e2_physical_knobs_report.json", files)
            self.assertIn(f"{KNOBS_DIR}/phase2_e2_physical_knobs.md", files)
            self.assertIn(f"{KNOBS_DIR}/phase2_e2_physical_knobs.tex", files)
            self.assertIn(f"{KNOBS_DIR}/phase2_e2_best_candidates_report.json", files)
            self.assertIn(f"{KNOBS_DIR}/phase2_e2_best_candidates.md", files)
            self.assertIn(f"{KNOBS_DIR}/phase2_e2_best_candidates.tex", files)
            self.assertIn(f"{KNOBS_DIR}/snippets/phase2_e2_physical_knobs.md", snippets)
            self.assertIn(f"{KNOBS_DIR}/snippets/phase2_e2_physical_knobs.tex", snippets)
            self.assertIn(f"{KNOBS_DIR}/snippets/phase2_e2_best_candidates.md", snippets)
            self.assertIn(f"{KNOBS_DIR}/snippets/phase2_e2_best_candidates.tex", snippets)


if __name__ == "__main__":
    unittest.main()

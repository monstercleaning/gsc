import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_e2_make_paper_assets.py"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestPhase2M67MakePaperAssetsIncludesScanAuditSnippets(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        cmd = [sys.executable, str(SCRIPT), *args]
        return subprocess.run(cmd, cwd=str(ROOT.parent), text=True, capture_output=True)

    def _write_fixture(self, jsonl_path: Path, plan_path: Path) -> None:
        rows = [
            {
                "params_hash": "hash_a",
                "plan_point_id": "p0",
                "plan_source_sha256": "plan_sha_test",
                "scan_config_sha256": "cfg_sha_test",
                "status": "ok",
                "chi2_total": 6.0,
                "chi2_cmb": 2.0,
                "drift_metric": 0.2,
                "drift_sign_z2_5": True,
                "microphysics_plausible_ok": True,
                "params": {"H0": 67.0, "Omega_m": 0.3},
                "microphysics_knobs": {"z_star_scale": 1.0},
            },
            {
                "params_hash": "hash_b",
                "plan_point_id": "p1",
                "plan_source_sha256": "plan_sha_test",
                "scan_config_sha256": "cfg_sha_test",
                "status": "error",
                "error": "ValueError: synthetic",
                "chi2_total": 1.0e99,
                "chi2_cmb": 1.0e99,
                "drift_metric": -0.1,
                "drift_sign_z2_5": False,
                "params": {"H0": 68.0, "Omega_m": 0.31},
            },
            {
                "params_hash": "hash_c",
                "plan_point_id": "p2",
                "plan_source_sha256": "plan_sha_test",
                "scan_config_sha256": "cfg_sha_test",
                "status": "skipped_drift",
                "chi2_total": 1.0e99,
                "chi2_cmb": 1.0e99,
                "drift_metric": -0.2,
                "drift_sign_z2_5": False,
                "params": {"H0": 69.0, "Omega_m": 0.32},
            },
        ]
        with jsonl_path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")
            fh.write("{bad json\n")
            fh.write("\n")

        plan_payload = {
            "plan_version": "phase2_e2_refine_plan_v1",
            "plan_source_sha256": "plan_sha_test",
            "points": [
                {"point_id": "p0", "params": {"H0": 67.0, "Omega_m": 0.3}},
                {"point_id": "p1", "params": {"H0": 68.0, "Omega_m": 0.31}},
                {"point_id": "p2", "params": {"H0": 69.0, "Omega_m": 0.32}},
            ],
        }
        plan_path.write_text(json.dumps(plan_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def test_make_paper_assets_includes_scan_audit_snippets_and_manifest_entries(self) -> None:
        self.assertTrue(SCRIPT.is_file())
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            jsonl_path = td_path / "scan.jsonl"
            plan_path = td_path / "plan.json"
            out_a = td_path / "assets_a"
            out_b = td_path / "assets_b"
            self._write_fixture(jsonl_path, plan_path)

            common_args = [
                "--jsonl",
                str(jsonl_path),
                "--mode",
                "drift_closure_bound",
                "--certificate-plan",
                str(plan_path),
                "--created-utc",
                "2000-01-01T00:00:00Z",
            ]

            proc_a = self._run(*common_args, "--outdir", str(out_a))
            proc_b = self._run(*common_args, "--outdir", str(out_b))
            self.assertEqual(proc_a.returncode, 0, msg=(proc_a.stdout or "") + (proc_a.stderr or ""))
            self.assertEqual(proc_b.returncode, 0, msg=(proc_b.stdout or "") + (proc_b.stderr or ""))

            report_md_a = out_a / "phase2_e2_scan_audit.md"
            report_tex_a = out_a / "phase2_e2_scan_audit.tex"
            drift_table_md_a = out_a / "phase2_e2_drift_table.md"
            drift_table_tex_a = out_a / "phase2_e2_drift_table.tex"
            cmb_tension_md_a = out_a / "phase2_e2_cmb_tension.md"
            cmb_tension_tex_a = out_a / "phase2_e2_cmb_tension.tex"
            snippet_md_a = out_a / "snippets" / "phase2_e2_scan_audit.md"
            snippet_tex_a = out_a / "snippets" / "phase2_e2_scan_audit.tex"
            drift_table_snippet_md_a = out_a / "snippets" / "phase2_e2_drift_table.md"
            drift_table_snippet_tex_a = out_a / "snippets" / "phase2_e2_drift_table.tex"
            cmb_tension_snippet_md_a = out_a / "snippets" / "phase2_e2_cmb_tension.md"
            cmb_tension_snippet_tex_a = out_a / "snippets" / "phase2_e2_cmb_tension.tex"
            report_md_b = out_b / "phase2_e2_scan_audit.md"
            report_tex_b = out_b / "phase2_e2_scan_audit.tex"
            drift_table_md_b = out_b / "phase2_e2_drift_table.md"
            drift_table_tex_b = out_b / "phase2_e2_drift_table.tex"
            cmb_tension_md_b = out_b / "phase2_e2_cmb_tension.md"
            cmb_tension_tex_b = out_b / "phase2_e2_cmb_tension.tex"
            snippet_md_b = out_b / "snippets" / "phase2_e2_scan_audit.md"
            snippet_tex_b = out_b / "snippets" / "phase2_e2_scan_audit.tex"
            drift_table_snippet_md_b = out_b / "snippets" / "phase2_e2_drift_table.md"
            drift_table_snippet_tex_b = out_b / "snippets" / "phase2_e2_drift_table.tex"
            cmb_tension_snippet_md_b = out_b / "snippets" / "phase2_e2_cmb_tension.md"
            cmb_tension_snippet_tex_b = out_b / "snippets" / "phase2_e2_cmb_tension.tex"
            manifest_a = out_a / "paper_assets_manifest.json"
            manifest_b = out_b / "paper_assets_manifest.json"

            for path in (
                report_md_a,
                report_tex_a,
                drift_table_md_a,
                drift_table_tex_a,
                cmb_tension_md_a,
                cmb_tension_tex_a,
                snippet_md_a,
                snippet_tex_a,
                drift_table_snippet_md_a,
                drift_table_snippet_tex_a,
                cmb_tension_snippet_md_a,
                cmb_tension_snippet_tex_a,
                report_md_b,
                report_tex_b,
                drift_table_md_b,
                drift_table_tex_b,
                cmb_tension_md_b,
                cmb_tension_tex_b,
                snippet_md_b,
                snippet_tex_b,
                drift_table_snippet_md_b,
                drift_table_snippet_tex_b,
                cmb_tension_snippet_md_b,
                cmb_tension_snippet_tex_b,
                manifest_a,
                manifest_b,
            ):
                self.assertTrue(path.is_file(), msg=str(path))
                self.assertGreater(path.stat().st_size, 0, msg=str(path))

            md_text = report_md_a.read_text(encoding="utf-8")
            tex_text = report_tex_a.read_text(encoding="utf-8")
            self.assertIn("Status counts", md_text)
            self.assertIn("Plan coverage", md_text)
            self.assertIn("operational metrics", md_text)
            self.assertIn("Status counts", tex_text)
            self.assertIn("Plan coverage", tex_text)

            payload = json.loads(manifest_a.read_text(encoding="utf-8"))
            files = {str(row.get("relpath")) for row in (payload.get("files") or [])}
            snippets = {str(row.get("relpath")) for row in (payload.get("snippets") or [])}
            self.assertIn("phase2_e2_scan_audit.md", files)
            self.assertIn("phase2_e2_scan_audit.tex", files)
            self.assertIn("phase2_e2_drift_table.md", files)
            self.assertIn("phase2_e2_drift_table.tex", files)
            self.assertIn("phase2_e2_cmb_tension.md", files)
            self.assertIn("phase2_e2_cmb_tension.tex", files)
            self.assertIn("snippets/phase2_e2_scan_audit.md", snippets)
            self.assertIn("snippets/phase2_e2_scan_audit.tex", snippets)
            self.assertIn("snippets/phase2_e2_drift_table.md", snippets)
            self.assertIn("snippets/phase2_e2_drift_table.tex", snippets)
            self.assertIn("snippets/phase2_e2_cmb_tension.md", snippets)
            self.assertIn("snippets/phase2_e2_cmb_tension.tex", snippets)

            self.assertEqual(_sha256(report_md_a), _sha256(report_md_b))
            self.assertEqual(_sha256(report_tex_a), _sha256(report_tex_b))
            self.assertEqual(_sha256(drift_table_md_a), _sha256(drift_table_md_b))
            self.assertEqual(_sha256(drift_table_tex_a), _sha256(drift_table_tex_b))
            self.assertEqual(_sha256(cmb_tension_md_a), _sha256(cmb_tension_md_b))
            self.assertEqual(_sha256(cmb_tension_tex_a), _sha256(cmb_tension_tex_b))
            self.assertEqual(_sha256(snippet_md_a), _sha256(snippet_md_b))
            self.assertEqual(_sha256(snippet_tex_a), _sha256(snippet_tex_b))
            self.assertEqual(_sha256(drift_table_snippet_md_a), _sha256(drift_table_snippet_md_b))
            self.assertEqual(_sha256(drift_table_snippet_tex_a), _sha256(drift_table_snippet_tex_b))
            self.assertEqual(_sha256(cmb_tension_snippet_md_a), _sha256(cmb_tension_snippet_md_b))
            self.assertEqual(_sha256(cmb_tension_snippet_tex_a), _sha256(cmb_tension_snippet_tex_b))


if __name__ == "__main__":
    unittest.main()

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


class TestPhase2M48MakePaperAssetsGeneratesE2SummarySnippets(unittest.TestCase):
    def _write_fixture(self, path: Path) -> None:
        rows = [
            {
                "params_hash": "hash_a",
                "status": "ok",
                "chi2_cmb": 1.5,
                "chi2_total": 8.0,
                "drift_metric": 0.4,
                "drift_sign_z2_5": True,
                "microphysics_plausible_ok": True,
                "microphysics_penalty": 0.0,
                "microphysics_max_rel_dev": 0.01,
                "params": {"H0": 67.0, "Omega_m": 0.30},
                "microphysics_knobs": {"z_star_scale": 1.0, "r_s_scale": 1.01, "r_d_scale": 1.0},
            },
            {
                "params_hash": "hash_b",
                "status": "ok",
                "chi2_cmb": 1.2,
                "chi2_total": 9.0,
                "drift_metric": 0.2,
                "drift_sign_z2_5": True,
                "microphysics_plausible_ok": False,
                "microphysics_penalty": 2.0,
                "microphysics_max_rel_dev": 0.2,
                "params": {"H0": 68.0, "Omega_m": 0.31},
                "microphysics_knobs": {"z_star_scale": 1.03, "r_s_scale": 1.04, "r_d_scale": 1.01},
            },
            {
                "params_hash": "hash_c",
                "status": "error",
                "error": {"message": "synthetic"},
                "chi2_cmb": 0.9,
                "chi2_total": 5.0,
                "drift_metric": 0.8,
                "drift_sign_z2_5": True,
                "params": {"H0": 69.0, "Omega_m": 0.29},
            },
            {
                "params_hash": "hash_d",
                "status": "skipped_drift",
                "chi2_cmb": 1.0e99,
                "chi2_total": 1.0e99,
                "drift_metric": -0.1,
                "drift_sign_z2_5": False,
                "params": {"H0": 65.0, "Omega_m": 0.35},
            },
        ]
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        cmd = [sys.executable, str(SCRIPT), *args]
        return subprocess.run(cmd, cwd=str(ROOT.parent), text=True, capture_output=True)

    def test_generates_summary_snippets_and_manifest_entries_deterministically(self) -> None:
        self.assertTrue(SCRIPT.is_file())
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            jsonl = td_path / "scan.jsonl"
            self._write_fixture(jsonl)

            out_a = td_path / "assets_a"
            out_b = td_path / "assets_b"

            common_args = [
                "--jsonl",
                str(jsonl),
                "--mode",
                "drift_closure_bound",
                "--created-utc",
                "2000-01-01T00:00:00Z",
            ]
            proc_a = self._run(*common_args, "--outdir", str(out_a))
            proc_b = self._run(*common_args, "--outdir", str(out_b))
            self.assertEqual(proc_a.returncode, 0, msg=(proc_a.stdout or "") + (proc_a.stderr or ""))
            self.assertEqual(proc_b.returncode, 0, msg=(proc_b.stdout or "") + (proc_b.stderr or ""))

            summary_tex_a = out_a / "snippets" / "phase2_e2_summary.tex"
            summary_md_a = out_a / "snippets" / "phase2_e2_summary.md"
            summary_tex_b = out_b / "snippets" / "phase2_e2_summary.tex"
            summary_md_b = out_b / "snippets" / "phase2_e2_summary.md"
            manifest_a = out_a / "paper_assets_manifest.json"
            manifest_b = out_b / "paper_assets_manifest.json"

            for path in (summary_tex_a, summary_md_a, summary_tex_b, summary_md_b, manifest_a, manifest_b):
                self.assertTrue(path.is_file(), msg=str(path))

            summary_md_text = summary_md_a.read_text(encoding="utf-8")
            self.assertIn("N_total", summary_md_text)
            self.assertIn("best_overall_ok", summary_md_text)
            self.assertIn("hash_a", summary_md_text)
            self.assertIn("hash_b", summary_md_text)

            payload = json.loads(manifest_a.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "phase2_e2_paper_assets_manifest_v1")
            snippet_relpaths = {str(item.get("relpath")) for item in payload.get("snippets") or []}
            self.assertIn("snippets/phase2_e2_summary.tex", snippet_relpaths)
            self.assertIn("snippets/phase2_e2_summary.md", snippet_relpaths)

            self.assertEqual(_sha256(summary_tex_a), _sha256(summary_tex_b))
            self.assertEqual(_sha256(summary_md_a), _sha256(summary_md_b))
            self.assertEqual(_sha256(manifest_a), _sha256(manifest_b))


if __name__ == "__main__":
    unittest.main()

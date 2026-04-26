import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_e2_make_paper_assets.py"
DRIFT_DIR = "paper_assets_cmb_e2_drift_constrained_closure_bound"
KNOBS_DIR = "paper_assets_cmb_e2_closure_to_physical_knobs"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestPhase2M51MakePaperAssetsIncludesClosureBoundSnippets(unittest.TestCase):
    def _write_fixture(self, path: Path) -> None:
        rows = [
            {
                "params_hash": "a1",
                "status": "ok",
                "chi2_cmb": 2.2,
                "chi2_total": 8.7,
                "drift_metric": 0.4,
                "drift_sign_z2_5": True,
                "microphysics_plausible_ok": True,
                "params": {"omega_b_h2": 0.0223, "omega_c_h2": 0.1201, "N_eff": 3.046},
                "microphysics_knobs": {"z_star_scale": 1.0, "r_s_scale": 1.02},
            },
            {
                "params_hash": "a2",
                "status": "ok",
                "chi2_parts": {"cmb_priors": {"chi2": 2.8}, "sn": {"chi2": 1.2}},
                "drift_metric": 0.7,
                "drift_sign_z2_5": True,
                "microphysics_plausible_ok": True,
                "params": {"omega_b_h2": 0.0221, "omega_c_h2": 0.1199, "N_eff": 3.1},
                "microphysics_knobs": {"z_star_scale": 1.01, "r_s_scale": 1.03},
            },
        ]
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        cmd = [sys.executable, str(SCRIPT), *args]
        return subprocess.run(cmd, cwd=str(ROOT.parent), text=True, capture_output=True)

    def test_includes_closure_bound_snippets_and_manifest_entries(self):
        self.assertTrue(SCRIPT.is_file())
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            in_jsonl = td_path / "scan.jsonl"
            out_a = td_path / "assets_a"
            out_b = td_path / "assets_b"
            self._write_fixture(in_jsonl)

            common_args = [
                "--jsonl",
                str(in_jsonl),
                "--mode",
                "all",
                "--emit-snippets",
                "--snippets-format",
                "both",
                "--created-utc",
                "2000-01-01T00:00:00Z",
            ]
            proc_a = self._run(*common_args, "--outdir", str(out_a))
            proc_b = self._run(*common_args, "--outdir", str(out_b))
            self.assertEqual(proc_a.returncode, 0, msg=(proc_a.stdout or "") + (proc_a.stderr or ""))
            self.assertEqual(proc_b.returncode, 0, msg=(proc_b.stdout or "") + (proc_b.stderr or ""))

            closure_json_a = out_a / DRIFT_DIR / "phase2_e2_closure_bound_report.json"
            closure_md_snippet_a = out_a / DRIFT_DIR / "snippets" / "phase2_e2_closure_bound.md"
            closure_tex_snippet_a = out_a / DRIFT_DIR / "snippets" / "phase2_e2_closure_bound.tex"
            for path in (closure_json_a, closure_md_snippet_a, closure_tex_snippet_a):
                self.assertTrue(path.is_file(), msg=str(path))

            manifest_a = out_a / "paper_assets_manifest.json"
            payload = json.loads(manifest_a.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "phase2_e2_paper_assets_manifest_v1")
            snippet_paths = {str(row.get("relpath")) for row in (payload.get("snippets") or [])}
            self.assertIn(f"{DRIFT_DIR}/snippets/phase2_e2_closure_bound.md", snippet_paths)
            self.assertIn(f"{DRIFT_DIR}/snippets/phase2_e2_closure_bound.tex", snippet_paths)

            comparable = [
                "paper_assets_manifest.json",
                f"{DRIFT_DIR}/phase2_e2_closure_bound_report.json",
                f"{DRIFT_DIR}/phase2_e2_closure_bound_report.md",
                f"{DRIFT_DIR}/phase2_e2_closure_bound_report.tex",
                f"{DRIFT_DIR}/snippets/phase2_e2_closure_bound.md",
                f"{DRIFT_DIR}/snippets/phase2_e2_closure_bound.tex",
                f"{KNOBS_DIR}/tables/top_models_knobs.csv",
            ]
            for rel in comparable:
                self.assertEqual(_sha256(out_a / rel), _sha256(out_b / rel), msg=rel)


if __name__ == "__main__":
    unittest.main()

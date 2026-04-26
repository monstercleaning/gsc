import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_e2_make_paper_assets.py"
DRIFT_DIR_NAME = "paper_assets_cmb_e2_drift_constrained_closure_bound"
KNOBS_DIR_NAME = "paper_assets_cmb_e2_closure_to_physical_knobs"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestPhase2M43MakePaperAssetsSnippetsManifest(unittest.TestCase):
    def _write_fixture(self, path: Path) -> None:
        rows = [
            {
                "params_hash": "h1",
                "status": "ok",
                "chi2_cmb": 2.1,
                "chi2_total": 9.1,
                "drift_metric": 0.4,
                "drift_sign_z2_5": True,
                "microphysics_plausible_ok": True,
                "robust_ok": True,
                "params": {"omega_b_h2": 0.0223, "omega_c_h2": 0.1201, "N_eff": 3.046},
                "microphysics_knobs": {"z_star_scale": 1.0, "r_s_scale": 1.02, "r_d_scale": 1.0},
            },
            {
                "params_hash": "h2",
                "status": "ok",
                "chi2_parts": {"cmb_priors": 2.5, "sn": 1.0},
                "chi2": 10.2,
                "drift_metric": 0.6,
                "drift_sign_z2_5": True,
                "microphysics_plausible_ok": True,
                "robust_ok": True,
                "params": {"omega_b_h2": 0.0221, "omega_c_h2": 0.1195, "N_eff": 3.1},
                "microphysics_knobs": {"z_star_scale": 1.01, "r_s_scale": 1.03, "r_d_scale": 1.01},
            },
        ]
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        cmd = [sys.executable, str(SCRIPT), *args]
        return subprocess.run(cmd, cwd=str(ROOT.parent), text=True, capture_output=True)

    def test_emit_snippets_and_paper_assets_manifest_are_deterministic(self):
        self.assertTrue(SCRIPT.is_file())
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            jsonl = td_path / "scan.jsonl"
            out_a = td_path / "assets_a"
            out_b = td_path / "assets_b"
            self._write_fixture(jsonl)

            common_args = [
                "--jsonl",
                str(jsonl),
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

            manifest_a = out_a / "paper_assets_manifest.json"
            manifest_b = out_b / "paper_assets_manifest.json"
            self.assertTrue(manifest_a.is_file())
            self.assertTrue(manifest_b.is_file())

            payload = json.loads(manifest_a.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "phase2_e2_paper_assets_manifest_v1")
            snippets = payload.get("snippets") or []
            self.assertGreaterEqual(len(snippets), 4)

            drift_md_a = out_a / DRIFT_DIR_NAME / "snippets" / "drift_closure_bound.md"
            drift_tex_a = out_a / DRIFT_DIR_NAME / "snippets" / "drift_closure_bound.tex"
            knobs_md_a = out_a / KNOBS_DIR_NAME / "snippets" / "closure_to_knobs.md"
            knobs_tex_a = out_a / KNOBS_DIR_NAME / "snippets" / "closure_to_knobs.tex"
            for path in (drift_md_a, drift_tex_a, knobs_md_a, knobs_tex_a):
                self.assertTrue(path.is_file(), msg=str(path))

            comparable = [
                "paper_assets_manifest.json",
                f"{DRIFT_DIR_NAME}/snippets/drift_closure_bound.md",
                f"{DRIFT_DIR_NAME}/snippets/drift_closure_bound.tex",
                f"{KNOBS_DIR_NAME}/snippets/closure_to_knobs.md",
                f"{KNOBS_DIR_NAME}/snippets/closure_to_knobs.tex",
            ]
            for rel in comparable:
                self.assertEqual(_sha256(out_a / rel), _sha256(out_b / rel), msg=rel)


if __name__ == "__main__":
    unittest.main()


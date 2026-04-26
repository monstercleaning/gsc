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

CANONICAL_STEMS = (
    "phase2_e2_summary",
    "phase2_e2_scan_audit",
    "phase2_e2_best_candidates",
    "phase2_sf_rsd_summary",
    "phase2_sf_fsigma8",
    "phase2_rg_flow_table",
    "phase2_rg_pade_fit",
    "phase2_e2_drift_table",
    "phase2_e2_cmb_tension",
    "phase2_e2_closure_bound",
    "phase2_e2_physical_knobs",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestPhase2M70MakePaperAssetsGeneratesPhase2E2AllAggregatorToy(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        cmd = [sys.executable, str(SCRIPT), *args]
        return subprocess.run(cmd, cwd=str(ROOT.parent), text=True, capture_output=True)

    def _write_fixture(self, path: Path) -> None:
        rows = [
            {
                "params_hash": "h_a",
                "status": "ok",
                "chi2_cmb": 2.2,
                "chi2_total": 8.9,
                "drift_metric": 0.4,
                "drift_sign_z2_5": True,
                "microphysics_plausible_ok": True,
                "microphysics_penalty": 0.0,
                "microphysics_max_rel_dev": 0.01,
                "params": {"H0": 67.0, "Omega_m": 0.30, "omega_b_h2": 0.0223, "omega_c_h2": 0.12, "N_eff": 3.046},
                "microphysics_knobs": {"z_star_scale": 1.0, "r_s_scale": 1.01, "r_d_scale": 1.0},
            },
            {
                "params_hash": "h_b",
                "status": "ok",
                "chi2_parts": {"cmb_priors": {"chi2": 2.4}, "sn": {"chi2": 1.1}},
                "chi2_total": 9.2,
                "drift_metric": 0.2,
                "drift_sign_z2_5": True,
                "microphysics_plausible_ok": False,
                "microphysics_penalty": 1.2,
                "microphysics_max_rel_dev": 0.15,
                "params": {"H0": 68.0, "Omega_m": 0.31, "omega_b_h2": 0.0221, "omega_c_h2": 0.121, "N_eff": 3.1},
                "microphysics_knobs": {"z_star_scale": 1.02, "r_s_scale": 1.04, "r_d_scale": 1.01},
            },
        ]
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")

    def test_generates_phase2_e2_all_aggregator_and_is_deterministic(self) -> None:
        self.assertTrue(SCRIPT.is_file())
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            in_jsonl = td_path / "scan.jsonl"
            self._write_fixture(in_jsonl)

            out_a = td_path / "assets_a"
            out_b = td_path / "assets_b"
            common_args = [
                "--jsonl",
                str(in_jsonl),
                "--mode",
                "all",
                "--created-utc",
                "2000-01-01T00:00:00Z",
            ]
            proc_a = self._run(*common_args, "--outdir", str(out_a))
            proc_b = self._run(*common_args, "--outdir", str(out_b))
            self.assertEqual(proc_a.returncode, 0, msg=(proc_a.stdout or "") + (proc_a.stderr or ""))
            self.assertEqual(proc_b.returncode, 0, msg=(proc_b.stdout or "") + (proc_b.stderr or ""))

            tex_a = out_a / DRIFT_DIR / "snippets" / "phase2_e2_all.tex"
            md_a = out_a / DRIFT_DIR / "snippets" / "phase2_e2_all.md"
            tex_b = out_b / DRIFT_DIR / "snippets" / "phase2_e2_all.tex"
            md_b = out_b / DRIFT_DIR / "snippets" / "phase2_e2_all.md"
            manifest_a = out_a / "paper_assets_manifest.json"

            for path in (tex_a, md_a, tex_b, md_b, manifest_a):
                self.assertTrue(path.is_file(), msg=str(path))
                self.assertGreater(path.stat().st_size, 0, msg=str(path))

            tex_text = tex_a.read_text(encoding="utf-8")
            md_text = md_a.read_text(encoding="utf-8")
            self.assertIn("phase2_e2_all_snippet_v1", tex_text)
            self.assertIn("phase2_e2_all_snippet_v1", md_text)
            for stem in CANONICAL_STEMS:
                self.assertIn(f"\\input{{{stem}.tex}}", tex_text)
                self.assertIn(f"BEGIN {stem}.md", md_text)

            payload = json.loads(manifest_a.read_text(encoding="utf-8"))
            snippet_paths = {str(row.get("relpath")) for row in (payload.get("snippets") or [])}
            self.assertIn(f"{DRIFT_DIR}/snippets/phase2_e2_all.tex", snippet_paths)
            self.assertIn(f"{DRIFT_DIR}/snippets/phase2_e2_all.md", snippet_paths)

            self.assertEqual(_sha256(tex_a), _sha256(tex_b))
            self.assertEqual(_sha256(md_a), _sha256(md_b))


if __name__ == "__main__":
    unittest.main()

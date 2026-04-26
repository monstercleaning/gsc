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


class TestPhase2M98MakePaperAssetsIncludesRgSnippetsToy(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        cmd = [sys.executable, str(SCRIPT), *args]
        return subprocess.run(cmd, cwd=str(ROOT.parent), text=True, capture_output=True)

    def _write_fixture(self, path: Path) -> None:
        rows = [
            {
                "params_hash": "h_m98_a",
                "status": "ok",
                "chi2_cmb": 2.2,
                "chi2_total": 8.8,
                "drift_metric": 0.4,
                "drift_sign_z2_5": True,
                "microphysics_plausible_ok": True,
                "microphysics_penalty": 0.0,
                "microphysics_max_rel_dev": 0.01,
                "params": {"H0": 67.0, "Omega_m": 0.30, "omega_b_h2": 0.0223, "omega_c_h2": 0.12, "N_eff": 3.046},
                "microphysics_knobs": {"z_star_scale": 1.0, "r_s_scale": 1.01, "r_d_scale": 1.0},
            },
            {
                "params_hash": "h_m98_b",
                "status": "ok",
                "chi2_parts": {"cmb_priors": {"chi2": 2.4}, "sn": {"chi2": 1.0}},
                "chi2_total": 9.1,
                "drift_metric": 0.2,
                "drift_sign_z2_5": True,
                "microphysics_plausible_ok": True,
                "microphysics_penalty": 0.2,
                "microphysics_max_rel_dev": 0.03,
                "params": {"H0": 68.0, "Omega_m": 0.31, "omega_b_h2": 0.0221, "omega_c_h2": 0.121, "N_eff": 3.1},
                "microphysics_knobs": {"z_star_scale": 1.01, "r_s_scale": 1.02, "r_d_scale": 1.01},
            },
        ]
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")

    def test_mode_all_includes_rg_snippets_and_manifest_entries(self) -> None:
        self.assertTrue(SCRIPT.is_file())
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            in_jsonl = td_path / "scan.jsonl"
            self._write_fixture(in_jsonl)

            outdir = td_path / "assets"
            proc = self._run(
                "--jsonl",
                str(in_jsonl),
                "--mode",
                "all",
                "--outdir",
                str(outdir),
                "--created-utc",
                "2000-01-01T00:00:00Z",
            )
            out = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=out)

            knobs_snip_dir = outdir / KNOBS_DIR / "snippets"
            drift_snip_dir = outdir / DRIFT_DIR / "snippets"

            flow_md = knobs_snip_dir / "phase2_rg_flow_table.md"
            flow_tex = knobs_snip_dir / "phase2_rg_flow_table.tex"
            pade_md = knobs_snip_dir / "phase2_rg_pade_fit.md"
            pade_tex = knobs_snip_dir / "phase2_rg_pade_fit.tex"
            sf_md = knobs_snip_dir / "phase2_sf_fsigma8.md"
            sf_tex = knobs_snip_dir / "phase2_sf_fsigma8.tex"
            for path in (flow_md, flow_tex, pade_md, pade_tex, sf_md, sf_tex):
                self.assertTrue(path.is_file(), msg=str(path))

            self.assertIn("phase2_rg_flow_table_snippet_v1", flow_md.read_text(encoding="utf-8"))
            self.assertIn("phase2_rg_flow_table_snippet_v1", flow_tex.read_text(encoding="utf-8"))
            self.assertIn("phase2_rg_pade_fit_snippet_v1", pade_md.read_text(encoding="utf-8"))
            self.assertIn("phase2_rg_pade_fit_snippet_v1", pade_tex.read_text(encoding="utf-8"))
            self.assertIn("phase2_sf_fsigma8_snippet_v1", sf_md.read_text(encoding="utf-8"))
            self.assertIn("phase2_sf_fsigma8_snippet_v1", sf_tex.read_text(encoding="utf-8"))

            # Aggregator mirroring in drift snippets directory.
            self.assertTrue((drift_snip_dir / "phase2_rg_flow_table.tex").is_file())
            self.assertTrue((drift_snip_dir / "phase2_rg_pade_fit.tex").is_file())
            self.assertTrue((drift_snip_dir / "phase2_sf_fsigma8.tex").is_file())

            manifest = json.loads((outdir / "paper_assets_manifest.json").read_text(encoding="utf-8"))
            snippet_paths = {str(row.get("relpath")) for row in (manifest.get("snippets") or [])}
            self.assertIn(f"{KNOBS_DIR}/snippets/phase2_rg_flow_table.md", snippet_paths)
            self.assertIn(f"{KNOBS_DIR}/snippets/phase2_rg_flow_table.tex", snippet_paths)
            self.assertIn(f"{KNOBS_DIR}/snippets/phase2_rg_pade_fit.md", snippet_paths)
            self.assertIn(f"{KNOBS_DIR}/snippets/phase2_rg_pade_fit.tex", snippet_paths)
            self.assertIn(f"{KNOBS_DIR}/snippets/phase2_sf_fsigma8.md", snippet_paths)
            self.assertIn(f"{KNOBS_DIR}/snippets/phase2_sf_fsigma8.tex", snippet_paths)


if __name__ == "__main__":
    unittest.main()

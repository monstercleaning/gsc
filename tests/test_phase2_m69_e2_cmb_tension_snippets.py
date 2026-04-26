import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase2_e2_cmb_tension_report.py"


class TestPhase2M69E2CmbTensionSnippets(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        cmd = [sys.executable, str(SCRIPT), *args]
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def _write_fixture(self, path: Path) -> None:
        rows = [
            {
                "status": "ok",
                "params_hash": "m69_non_plausible",
                "plan_point_id": "p0",
                "chi2_total": 1.0,
                "chi2_parts": {"cmb": {"chi2": 0.9, "pulls": {"R": 2.1, "lA": -1.2, "omega_b_h2": 0.4}}},
                "cmb_pred": {"R": 1.80, "lA": 302.0, "omega_b_h2": 0.0226},
                "cmb_tension": {
                    "dR_sigma_diag": 2.1,
                    "dlA_sigma_diag": -1.2,
                    "domega_sigma_diag": 0.4,
                    "delta_D_pct": 2.3,
                    "delta_rs_pct": -1.0,
                },
                "microphysics_plausible_ok": False,
            },
            {
                "status": "ok",
                "params_hash": "m69_plausible",
                "plan_point_id": "p1",
                "chi2_total": 2.0,
                "chi2_parts": {"cmb": {"chi2": 1.4, "pulls": {"R": 0.3, "lA": 0.1, "omega_b_h2": -0.2}}},
                "cmb_pred": {"R": 1.75, "lA": 301.1, "omega_b_h2": 0.0223},
                "cmb_tension": {
                    "dR_sigma_diag": 0.3,
                    "dlA_sigma_diag": 0.1,
                    "domega_sigma_diag": -0.2,
                    "delta_D_pct": 0.3,
                    "delta_rs_pct": 0.1,
                },
                "microphysics_plausible_ok": True,
            },
            {
                "status": "error",
                "params_hash": "m69_error",
                "chi2_total": 99.0,
                "cmb_pred": {"R": 1.7, "lA": 300.0, "omega_b_h2": 0.0221},
                "cmb_tension": {"dR_sigma_diag": -10.0, "dlA_sigma_diag": 8.0, "domega_sigma_diag": 5.0},
                "error": "ValueError: synthetic",
            },
        ]
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")
            fh.write("{invalid json\n")

    def test_emit_snippets_outputs_md_and_tex(self) -> None:
        self.assertTrue(SCRIPT.is_file())
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            jsonl_path = td_path / "scan.jsonl"
            outdir = td_path / "out"
            outdir.mkdir(parents=True, exist_ok=True)
            self._write_fixture(jsonl_path)

            proc = self._run(
                "--input",
                str(jsonl_path),
                "--outdir",
                str(outdir),
                "--emit-snippets",
                "--snippets-outdir",
                str(outdir),
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            snippet_md = outdir / "phase2_e2_cmb_tension.md"
            snippet_tex = outdir / "phase2_e2_cmb_tension.tex"
            self.assertTrue(snippet_md.is_file(), msg=str(snippet_md))
            self.assertTrue(snippet_tex.is_file(), msg=str(snippet_tex))

            md_text = snippet_md.read_text(encoding="utf-8")
            tex_text = snippet_tex.read_text(encoding="utf-8")
            self.assertIn("phase2_e2_cmb_tension_snippet_v1", md_text)
            self.assertIn("phase2_e2_cmb_tension_snippet_v1", tex_text)
            self.assertIn("R", md_text)
            self.assertIn("lA", md_text)
            self.assertIn("Best eligible (plausible_only)", md_text)


if __name__ == "__main__":
    unittest.main()


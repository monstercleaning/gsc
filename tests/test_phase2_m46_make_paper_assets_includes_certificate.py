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


class TestPhase2M46MakePaperAssetsIncludesCertificate(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        cmd = [sys.executable, str(SCRIPT), *args]
        return subprocess.run(cmd, cwd=str(ROOT.parent), text=True, capture_output=True)

    def _write_fixture(self, path: Path) -> None:
        rows = [
            {
                "params_hash": "h1",
                "status": "ok",
                "chi2_cmb": 2.2,
                "chi2_total": 8.4,
                "drift_metric": 0.4,
                "drift_sign_z2_5": True,
                "microphysics_plausible_ok": True,
                "params": {"omega_b_h2": 0.0223, "omega_c_h2": 0.1202, "N_eff": 3.046},
                "microphysics_knobs": {"z_star_scale": 1.0, "r_s_scale": 1.02, "r_d_scale": 1.0},
            },
            {
                "params_hash": "h2",
                "status": "ok",
                "chi2_cmb": 2.8,
                "chi2_total": 9.5,
                "drift_metric": 0.6,
                "drift_sign_z2_5": True,
                "microphysics_plausible_ok": True,
                "params": {"omega_b_h2": 0.0221, "omega_c_h2": 0.1198, "N_eff": 3.10},
                "microphysics_knobs": {"z_star_scale": 1.01, "r_s_scale": 1.03, "r_d_scale": 1.01},
            },
        ]
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")

    def test_paper_assets_manifest_includes_certificate_outputs(self) -> None:
        self.assertTrue(SCRIPT.is_file())
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            jsonl = td_path / "scan.jsonl"
            outdir = td_path / "assets"
            self._write_fixture(jsonl)

            proc = self._run(
                "--jsonl",
                str(jsonl),
                "--mode",
                "all",
                "--outdir",
                str(outdir),
                "--created-utc",
                "2000-01-01T00:00:00Z",
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            drift_cert_json = outdir / DRIFT_DIR_NAME / "e2_certificate.json"
            drift_cert_md = outdir / DRIFT_DIR_NAME / "e2_certificate.md"
            knobs_cert_json = outdir / KNOBS_DIR_NAME / "e2_certificate.json"
            knobs_cert_md = outdir / KNOBS_DIR_NAME / "e2_certificate.md"
            for path in (drift_cert_json, drift_cert_md, knobs_cert_json, knobs_cert_md):
                self.assertTrue(path.is_file(), msg=str(path))

            top_manifest = json.loads((outdir / "paper_assets_manifest.json").read_text(encoding="utf-8"))
            relpaths = {str(item.get("relpath")) for item in (top_manifest.get("files") or [])}
            self.assertIn(f"{DRIFT_DIR_NAME}/e2_certificate.json", relpaths)
            self.assertIn(f"{DRIFT_DIR_NAME}/e2_certificate.md", relpaths)
            self.assertIn(f"{KNOBS_DIR_NAME}/e2_certificate.json", relpaths)
            self.assertIn(f"{KNOBS_DIR_NAME}/e2_certificate.md", relpaths)

            drift_manifest = json.loads((outdir / DRIFT_DIR_NAME / "manifest.json").read_text(encoding="utf-8"))
            drift_outputs = {str(item.get("relpath")) for item in (drift_manifest.get("outputs") or [])}
            self.assertIn("e2_certificate.json", drift_outputs)
            self.assertIn("e2_certificate.md", drift_outputs)


if __name__ == "__main__":
    unittest.main()

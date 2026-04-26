import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M98VerifyBundleRequiresRgSnippets(unittest.TestCase):
    def _run(self, cmd: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def _write_jsonl(self, path: Path) -> None:
        rows = [
            {"type": "header", "schema": "gsc.phase2.e2.scan.v1"},
            {
                "params_hash": "h_rg",
                "status": "ok",
                "model": "lcdm",
                "chi2_total": 4.1,
                "chi2_cmb": 2.1,
                "drift_metric": 0.5,
                "drift_sign_z2_5": True,
                "microphysics_plausible_ok": True,
                "params": {"H0": 67.0, "Omega_m": 0.30},
                "microphysics_knobs": {"z_star_scale": 1.0, "r_s_scale": 1.01, "r_d_scale": 1.0},
            },
        ]
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")

    def _build_bundle_dir(self, td_path: Path) -> Path:
        shard = td_path / "scan.jsonl"
        self._write_jsonl(shard)

        outdir = td_path / "bundle_dir"
        script = ROOT / "scripts" / "phase2_e2_bundle.py"
        proc = self._run(
            [
                sys.executable,
                str(script),
                "--in",
                str(shard),
                "--outdir",
                str(outdir),
                "--steps",
                "merge,pareto,paper_assets,manifest,meta",
                "--paper-assets",
                "data",
            ]
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        self.assertEqual(proc.returncode, 0, msg=out)
        return outdir

    def test_verify_fails_when_rg_snippet_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bundle_dir = self._build_bundle_dir(td_path)

            removed = 0
            for candidate in sorted(bundle_dir.rglob("phase2_rg_flow_table.tex")):
                candidate.unlink()
                removed += 1
            self.assertGreater(removed, 0, msg="expected RG flow-table snippet files in bundle")

            verify_script = ROOT / "scripts" / "phase2_e2_verify_bundle.py"
            proc = self._run(
                [
                    sys.executable,
                    str(verify_script),
                    "--bundle",
                    str(bundle_dir),
                    "--paper-assets",
                    "require",
                ]
            )
            out = (proc.stdout or "") + (proc.stderr or "")
            self.assertNotEqual(proc.returncode, 0, msg=out)
            self.assertIn("phase2_rg_flow_table", out)


if __name__ == "__main__":
    unittest.main()

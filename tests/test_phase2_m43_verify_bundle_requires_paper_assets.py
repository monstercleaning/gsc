import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M43VerifyBundleRequiresPaperAssets(unittest.TestCase):
    def _write_jsonl(self, path: Path, rows: list[str]) -> None:
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    def _run(self, cmd: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def test_require_fails_when_paper_assets_are_missing(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            shard = td_path / "scan.jsonl"
            self._write_jsonl(
                shard,
                [
                    json.dumps({"type": "header", "schema": "gsc.phase2.e2.scan.v1"}),
                    json.dumps(
                        {
                            "params_hash": "h1",
                            "status": "ok",
                            "chi2_total": 4.0,
                            "chi2_cmb": 2.0,
                            "drift_metric": 0.5,
                            "drift_sign_z2_5": True,
                            "params": {"H0": 67.0, "Omega_m": 0.3},
                        }
                    ),
                ],
            )

            bundle_script = ROOT / "scripts" / "phase2_e2_bundle.py"
            bundle_dir = td_path / "bundle_no_paper"
            proc_bundle = self._run(
                [
                    sys.executable,
                    str(bundle_script),
                    "--in",
                    str(shard),
                    "--outdir",
                    str(bundle_dir),
                    "--steps",
                    "merge,pareto,manifest,meta",
                ]
            )
            self.assertEqual(proc_bundle.returncode, 0, msg=(proc_bundle.stdout or "") + (proc_bundle.stderr or ""))

            verify_script = ROOT / "scripts" / "phase2_e2_verify_bundle.py"
            proc_verify = self._run(
                [
                    sys.executable,
                    str(verify_script),
                    "--bundle",
                    str(bundle_dir),
                    "--paper-assets",
                    "require",
                ]
            )
            combined = (proc_verify.stdout or "") + (proc_verify.stderr or "")
            self.assertNotEqual(proc_verify.returncode, 0, msg=combined)
            self.assertIn("paper_assets_manifest.json", combined)


if __name__ == "__main__":
    unittest.main()


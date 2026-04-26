import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BUNDLE_SCRIPT = ROOT / "scripts" / "phase2_e2_bundle.py"
VERIFY_SCRIPT = ROOT / "scripts" / "phase2_e2_verify_bundle.py"


class TestPhase2M109VerifyBundleChecksLineageHashesToy(unittest.TestCase):
    def _write_jsonl(self, path: Path, rows: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")

    def test_verify_fails_on_lineage_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            shard_a = td_path / "shard_a.jsonl"
            shard_b = td_path / "shard_b.jsonl"
            outdir = td_path / "bundle"

            self._write_jsonl(
                shard_a,
                [
                    {"type": "header", "schema": "gsc.phase2.e2.scan.v1"},
                    {
                        "params_hash": "h1",
                        "status": "ok",
                        "model": "lcdm",
                        "chi2_total": 4.0,
                        "chi2_cmb": 2.0,
                        "params": {"H0": 67.0, "Omega_m": 0.30},
                    },
                ],
            )
            self._write_jsonl(
                shard_b,
                [
                    {
                        "params_hash": "h2",
                        "status": "ok",
                        "model": "lcdm",
                        "chi2_total": 4.8,
                        "chi2_cmb": 2.4,
                        "params": {"H0": 68.0, "Omega_m": 0.31},
                    }
                ],
            )

            build = subprocess.run(
                [
                    sys.executable,
                    str(BUNDLE_SCRIPT),
                    "--in",
                    str(shard_a),
                    "--in",
                    str(shard_b),
                    "--outdir",
                    str(outdir),
                    "--steps",
                    "merge,pareto,manifest,meta",
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            self.assertEqual(build.returncode, 0, msg=(build.stdout or "") + (build.stderr or ""))
            self.assertTrue((outdir / "LINEAGE.json").is_file())
            self.assertTrue((outdir / "bundle_meta.json").is_file())

            # bundle_meta is referenced by LINEAGE.json but not by bundle manifest,
            # so this isolates lineage-hash validation instead of manifest-hash validation.
            with (outdir / "bundle_meta.json").open("a", encoding="utf-8") as fh:
                fh.write("\nTAMPER_M109\n")

            verify = subprocess.run(
                [
                    sys.executable,
                    str(VERIFY_SCRIPT),
                    "--bundle",
                    str(outdir),
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            combined = (verify.stdout or "") + (verify.stderr or "")
            self.assertEqual(verify.returncode, 2, msg=combined)
            self.assertIn("LINEAGE_HASH_MISMATCH", combined)


if __name__ == "__main__":
    unittest.main()

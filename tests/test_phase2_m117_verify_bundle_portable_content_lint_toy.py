import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BUNDLE_SCRIPT = ROOT / "scripts" / "phase2_e2_bundle.py"
VERIFY_SCRIPT = ROOT / "scripts" / "phase2_e2_verify_bundle.py"


class TestPhase2M117VerifyBundlePortableContentLintToy(unittest.TestCase):
    def _write_jsonl(self, path: Path, rows: list[dict[str, object]]) -> None:
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")

    def test_verify_bundle_fails_when_portable_content_lint_detects_absolute_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            shard_a = td_path / "shard_a.jsonl"
            shard_b = td_path / "shard_b.jsonl"
            outdir = td_path / "bundle"
            report_json = td_path / "verify.json"

            self._write_jsonl(
                shard_a,
                [
                    {"type": "header", "schema": "gsc.phase2.e2.scan.v1"},
                    {
                        "params_hash": "hash_a",
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
                        "params_hash": "hash_b",
                        "status": "ok",
                        "model": "lcdm",
                        "chi2_total": 4.5,
                        "chi2_cmb": 2.1,
                        "params": {"H0": 68.0, "Omega_m": 0.31},
                    },
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

            leak = outdir / "portable_leak.json"
            leak.write_text(json.dumps({"source": "/var/folders/demo/leak"}, sort_keys=True), encoding="utf-8")

            verify = subprocess.run(
                [
                    sys.executable,
                    str(VERIFY_SCRIPT),
                    "--bundle",
                    str(outdir),
                    "--lint-portable-content",
                    "--json-out",
                    str(report_json),
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
            )
            output = (verify.stdout or "") + (verify.stderr or "")
            self.assertEqual(verify.returncode, 2, msg=output)
            self.assertIn("PORTABLE_CONTENT_LINT_FAILED", output)

            self.assertTrue(report_json.is_file())
            report = json.loads(report_json.read_text(encoding="utf-8"))
            self.assertFalse(bool(report.get("ok")), msg=output)


if __name__ == "__main__":
    unittest.main()

import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
REVIEWER_PACK_SCRIPT = ROOT / "scripts" / "phase2_e2_make_reviewer_pack.py"
BUNDLE_SCRIPT = ROOT / "scripts" / "phase2_e2_bundle.py"


class TestPhase2M119ReviewerPackDoesNotDependOnOriginalBundleAfterCopy(unittest.TestCase):
    def _write_jsonl(self, path: Path, rows: list[dict[str, object]]) -> None:
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")

    def _make_bundle_zip(self, base_dir: Path) -> Path:
        shard_a = base_dir / "shard_a.jsonl"
        shard_b = base_dir / "shard_b.jsonl"
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
                    "drift_metric": 0.5,
                    "drift_sign_z2_5": True,
                    "microphysics_plausible_ok": True,
                    "params": {"H0": 67.0, "Omega_m": 0.30},
                    "microphysics_knobs": {"z_star_scale": 1.0, "r_s_scale": 1.01, "r_d_scale": 1.0},
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
                    "chi2_total": 4.8,
                    "chi2_cmb": 2.3,
                    "drift_metric": 0.6,
                    "drift_sign_z2_5": True,
                    "microphysics_plausible_ok": True,
                    "params": {"H0": 68.0, "Omega_m": 0.31},
                    "microphysics_knobs": {"z_star_scale": 1.01, "r_s_scale": 1.02, "r_d_scale": 1.01},
                },
            ],
        )

        bundle_dir = base_dir / "bundle_dir"
        proc = subprocess.run(
            [
                sys.executable,
                str(BUNDLE_SCRIPT),
                "--in",
                str(shard_a),
                "--in",
                str(shard_b),
                "--outdir",
                str(bundle_dir),
                "--steps",
                "merge,pareto,manifest,meta",
            ],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))

        bundle_zip = base_dir / "bundle.zip"
        with zipfile.ZipFile(bundle_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(bundle_dir.rglob("*")):
                if not path.is_file():
                    continue
                rel = path.relative_to(bundle_dir).as_posix()
                zf.write(path, arcname=str(PurePosixPath("bundle") / rel))
        return bundle_zip

    def test_subtools_run_against_staged_bundle_copy_after_original_removed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            original_root = td_path / "ORIGINAL_TOKEN"
            original_root.mkdir(parents=True, exist_ok=True)
            bundle_zip = self._make_bundle_zip(original_root)

            outdir = td_path / "reviewer_pack_out"
            summary_json = td_path / "summary.json"
            cmd = [
                sys.executable,
                str(REVIEWER_PACK_SCRIPT),
                "--bundle",
                str(bundle_zip),
                "--outdir",
                str(outdir),
                "--include-repo-snapshot",
                "0",
                "--include-paper-assets",
                "1",
                "--include-verify",
                "1",
                "--skip-portable-content-lint",
                "--format",
                "json",
                "--json-out",
                str(summary_json),
            ]
            proc = subprocess.Popen(
                cmd,
                cwd=str(ROOT),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            staged_bundle = outdir / "bundle" / "bundle.zip"
            deleted_original = False
            deadline = time.monotonic() + 30.0
            while time.monotonic() < deadline:
                if staged_bundle.is_file():
                    shutil.rmtree(original_root)
                    deleted_original = True
                    break
                if proc.poll() is not None:
                    break
                time.sleep(0.05)

            self.assertTrue(deleted_original, msg="staged bundle copy was not observed before process ended")

            stdout, stderr = proc.communicate(timeout=180)
            output = (stdout or "") + (stderr or "")
            self.assertEqual(proc.returncode, 0, msg=output)

            verify_txt = (outdir / "verify" / "verify.txt").read_text(encoding="utf-8")
            self.assertNotIn("ORIGINAL_TOKEN", verify_txt)

            summary = json.loads(summary_json.read_text(encoding="utf-8"))
            subtools = summary.get("subtools")
            self.assertIsInstance(subtools, list)
            by_name = {
                str(row.get("name")): row
                for row in subtools
                if isinstance(row, dict) and isinstance(row.get("name"), str)
            }

            staged_bundle_text = str(staged_bundle)
            for name in ("phase2_e2_make_paper_assets", "phase2_e2_verify_bundle"):
                self.assertIn(name, by_name)
                command = [str(x) for x in by_name[name].get("command", [])]
                command_text = " ".join(command)
                self.assertIn(staged_bundle_text, command_text, msg=f"{name} command should use staged bundle")
                self.assertNotIn("ORIGINAL_TOKEN", command_text, msg=f"{name} command leaked original bundle path")


if __name__ == "__main__":
    unittest.main()

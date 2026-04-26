import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]


class TestPhase2M38E2VerifyBundle(unittest.TestCase):
    def _write_jsonl(self, path: Path, rows: list[str]) -> None:
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    def _run(self, cmd: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)

    def _build_bundle_dir(self, root: Path) -> Path:
        shard_a = root / "shard_a.jsonl"
        shard_b = root / "shard_b.jsonl"
        self._write_jsonl(
            shard_a,
            [
                json.dumps({"type": "header", "schema": "gsc.phase2.e2.scan.v1"}),
                json.dumps(
                    {
                        "params_hash": "hash_a",
                        "status": "ok",
                        "model": "lcdm",
                        "chi2_total": 4.0,
                        "chi2_cmb": 2.0,
                        "drift": {"min_z_dot": 1.0e-12},
                        "microphysics_plausible_ok": True,
                        "params": {"H0": 67.0, "Omega_m": 0.30},
                    }
                ),
                json.dumps(
                    {
                        "params_hash": "hash_b",
                        "status": "ok",
                        "model": "lcdm",
                        "chi2_total": 5.0,
                        "chi2_cmb": 3.0,
                        "drift": {"min_z_dot": 5.0e-13},
                        "microphysics_plausible_ok": True,
                        "params": {"H0": 68.0, "Omega_m": 0.31},
                    }
                ),
            ],
        )
        self._write_jsonl(
            shard_b,
            [
                json.dumps(
                    {
                        "params_hash": "hash_b",
                        "status": "ok",
                        "model": "lcdm",
                        "chi2_total": 4.5,
                        "chi2_cmb": 1.5,
                        "drift": {"min_z_dot": 7.0e-13},
                        "microphysics_plausible_ok": True,
                        "params": {"H0": 68.0, "Omega_m": 0.31},
                    }
                ),
                json.dumps(
                    {
                        "params_hash": "hash_c",
                        "status": "error",
                        "model": "lcdm",
                        "chi2_total": 99.0,
                        "chi2_cmb": 88.0,
                        "params": {"H0": 69.0, "Omega_m": 0.32},
                    }
                ),
            ],
        )

        outdir = root / "bundle_out"
        bundle_script = ROOT / "scripts" / "phase2_e2_bundle.py"
        proc = self._run(
            [
                sys.executable,
                str(bundle_script),
                "--in",
                str(shard_a),
                "--in",
                str(shard_b),
                "--outdir",
                str(outdir),
                "--steps",
                "merge,pareto,meta,manifest",
            ]
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        self.assertEqual(proc.returncode, 0, msg=output)
        self.assertTrue((outdir / "manifest.json").is_file())
        return outdir

    def _make_zip_bundle(self, source_dir: Path, zip_path: Path, *, root_name: str) -> None:
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(source_dir.rglob("*")):
                if not path.is_file():
                    continue
                rel = path.relative_to(source_dir).as_posix()
                arcname = str(PurePosixPath(root_name) / rel)
                zf.write(path, arcname=arcname)

    def _make_tar_bundle(self, source_dir: Path, tar_path: Path, *, root_name: str) -> None:
        with tarfile.open(tar_path, "w:gz") as tf:
            for path in sorted(source_dir.rglob("*")):
                if not path.is_file():
                    continue
                rel = path.relative_to(source_dir).as_posix()
                arcname = str(PurePosixPath(root_name) / rel)
                tf.add(path, arcname=arcname, recursive=False)

    def test_verify_bundle_archive_and_unpacked_dir(self):
        verify_script = ROOT / "scripts" / "phase2_e2_verify_bundle.py"
        self.assertTrue(verify_script.is_file())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            outdir = self._build_bundle_dir(td_path)

            zip_bundle = td_path / "e2_bundle.zip"
            tar_bundle = td_path / "e2_bundle.tar.gz"
            self._make_zip_bundle(outdir, zip_bundle, root_name="bundle")
            self._make_tar_bundle(outdir, tar_bundle, root_name="bundle")

            proc_zip = self._run([sys.executable, str(verify_script), "--bundle", str(zip_bundle)])
            self.assertEqual(proc_zip.returncode, 0, msg=(proc_zip.stdout or "") + (proc_zip.stderr or ""))

            proc_tar = self._run([sys.executable, str(verify_script), "--bundle", str(tar_bundle)])
            self.assertEqual(proc_tar.returncode, 0, msg=(proc_tar.stdout or "") + (proc_tar.stderr or ""))

            extract_dir = td_path / "extract"
            with zipfile.ZipFile(zip_bundle, "r") as zf:
                zf.extractall(extract_dir)
            unpacked_bundle = extract_dir / "bundle"
            self.assertTrue((unpacked_bundle / "manifest.json").is_file())

            proc_dir = self._run([sys.executable, str(verify_script), "--bundle", str(unpacked_bundle)])
            self.assertEqual(proc_dir.returncode, 0, msg=(proc_dir.stdout or "") + (proc_dir.stderr or ""))

    def test_tamper_detected_on_directory(self):
        verify_script = ROOT / "scripts" / "phase2_e2_verify_bundle.py"

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            outdir = self._build_bundle_dir(td_path)
            work_dir = td_path / "work_bundle"
            shutil.copytree(outdir, work_dir)

            manifest = json.loads((work_dir / "manifest.json").read_text(encoding="utf-8"))
            artifacts = list(manifest.get("artifacts", []))
            self.assertTrue(len(artifacts) > 0)
            first_path = None
            for item in artifacts:
                if not isinstance(item, dict):
                    continue
                rel = str(item.get("path", "")).strip()
                if rel and rel != "manifest.json":
                    first_path = rel
                    break
            self.assertIsNotNone(first_path)
            target = work_dir / str(first_path)
            with target.open("ab") as fh:
                fh.write(b"\nTAMPER\n")

            proc = self._run([sys.executable, str(verify_script), "--bundle", str(work_dir)])
            combined = (proc.stdout or "") + (proc.stderr or "")
            self.assertNotEqual(proc.returncode, 0, msg=combined)
            self.assertIn("mismatch", combined.lower())

    def test_json_report_schema(self):
        verify_script = ROOT / "scripts" / "phase2_e2_verify_bundle.py"

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            outdir = self._build_bundle_dir(td_path)
            report_path = td_path / "verify_report.json"
            proc = self._run(
                [
                    sys.executable,
                    str(verify_script),
                    "--bundle",
                    str(outdir),
                    "--json-out",
                    str(report_path),
                ]
            )
            self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))
            self.assertTrue(report_path.is_file())
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertIn("ok", report)
            self.assertIsInstance(report.get("ok"), bool)
            self.assertIn("n_files_manifest", report)
            self.assertIsInstance(report.get("n_files_manifest"), int)


if __name__ == "__main__":
    unittest.main()

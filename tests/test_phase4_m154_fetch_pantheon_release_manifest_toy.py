from pathlib import Path
import json
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fetch_pantheon_plus_release.py"
SRC_DATASET = ROOT / "tests" / "fixtures" / "phase4_m154" / "pantheon_toy_mu_fullcov.csv"
SRC_COV = ROOT / "tests" / "fixtures" / "phase4_m154" / "pantheon_toy_cov.txt"
ABS_TOKENS = ("/Users/", "/home/", "/var/folders/", "C:\\\\Users\\\\")


class TestPhase4M154FetchPantheonReleaseManifestToy(unittest.TestCase):
    def test_manifest_is_deterministic_and_portable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            source_dir = td_path / "source"
            source_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SRC_DATASET, source_dir / "pantheon_plus_shoes_mu.csv")
            shutil.copy2(SRC_COV, source_dir / "pantheon_plus_shoes_cov.cov")

            outdir = td_path / "out"
            manifest = outdir / "PANTHEON_FETCH_MANIFEST.json"
            common = [
                sys.executable,
                str(SCRIPT),
                "--source",
                str(source_dir),
                "--outdir",
                str(outdir),
                "--manifest-out",
                str(manifest),
                "--deterministic",
                "1",
                "--created-utc",
                "946684800",
                "--format",
                "json",
            ]

            proc_a = subprocess.run(common, cwd=str(ROOT.parent), text=True, capture_output=True)
            self.assertEqual(proc_a.returncode, 0, msg=(proc_a.stdout or "") + (proc_a.stderr or ""))
            bytes_a = manifest.read_bytes()

            proc_b = subprocess.run(common, cwd=str(ROOT.parent), text=True, capture_output=True)
            self.assertEqual(proc_b.returncode, 0, msg=(proc_b.stdout or "") + (proc_b.stderr or ""))
            bytes_b = manifest.read_bytes()

            self.assertEqual(bytes_a, bytes_b)
            payload = json.loads(bytes_b.decode("utf-8"))
            self.assertEqual(payload.get("schema"), "phase4_pantheon_plus_fetch_manifest_v1")
            self.assertTrue(bool(payload.get("paths_redacted")))
            files = payload.get("files", {})
            self.assertIn("mu", files)
            self.assertIn("cov", files)
            self.assertRegex(str(files["mu"].get("sha256", "")), r"^[0-9a-f]{64}$")
            self.assertRegex(str(files["cov"].get("sha256", "")), r"^[0-9a-f]{64}$")

            text = bytes_b.decode("utf-8")
            self.assertNotIn(str(td_path.resolve()), text)
            for token in ABS_TOKENS:
                self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()

from pathlib import Path
import hashlib
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONVERT = ROOT / "scripts" / "phase4_desi_bao_convert_gaussian_to_internal.py"
MEAN = ROOT / "tests" / "fixtures" / "phase4_m157" / "desi_gaussian_mean_toy.txt"
COV = ROOT / "tests" / "fixtures" / "phase4_m157" / "desi_gaussian_cov_toy.txt"


class TestPhase4M157BaoFullcovLoaderToy(unittest.TestCase):
    def test_converter_outputs_loadable_vector_dataset_and_deterministic_hashes(self) -> None:
        try:
            import numpy  # noqa: F401
        except Exception:
            self.skipTest("numpy not installed")

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            out_a = td_path / "a"
            out_b = td_path / "b"

            for outdir in (out_a, out_b):
                proc = subprocess.run(
                    [
                        sys.executable,
                        str(CONVERT),
                        "--repo-root",
                        str(ROOT),
                        "--outdir",
                        str(outdir),
                        "--mean-txt",
                        str(MEAN),
                        "--cov-txt",
                        str(COV),
                        "--deterministic",
                        "1",
                        "--created-utc",
                        "946684800",
                        "--format",
                        "text",
                    ],
                    cwd=str(ROOT.parent),
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(proc.returncode, 0, msg=(proc.stdout or "") + (proc.stderr or ""))

            values_a = out_a / "values.csv"
            values_b = out_b / "values.csv"
            cov_a = out_a / "cov.txt"
            cov_b = out_b / "cov.txt"
            ds_a = out_a / "dataset.csv"

            self.assertEqual(values_a.read_bytes(), values_b.read_bytes())
            self.assertEqual(cov_a.read_bytes(), cov_b.read_bytes())

            sys.path.insert(0, str(ROOT))
            try:
                from gsc.datasets.bao import BAODataset, BAOBlockND  # type: ignore
            finally:
                if sys.path and sys.path[0] == str(ROOT):
                    sys.path.pop(0)

            ds = BAODataset.from_csv(ds_a)
            self.assertEqual(len(ds.blocks), 1)
            self.assertIsInstance(ds.blocks[0], BAOBlockND)
            block = ds.blocks[0]
            self.assertEqual(len(block.y), 3)
            self.assertEqual(block.cov.shape, (3, 3))
            self.assertGreater(float(block.cov[0, 0]), 0.0)
            self.assertGreater(float(block.cov[1, 1]), 0.0)
            self.assertGreater(float(block.cov[2, 2]), 0.0)

            self.assertEqual(hashlib.sha256(values_a.read_bytes()).hexdigest(), hashlib.sha256(values_b.read_bytes()).hexdigest())
            self.assertEqual(hashlib.sha256(cov_a.read_bytes()).hexdigest(), hashlib.sha256(cov_b.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()

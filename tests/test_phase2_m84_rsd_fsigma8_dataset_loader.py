from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gsc.structure.rsd_fsigma8_data import load_fsigma8_csv  # noqa: E402


class TestPhase2M84RsdFsigma8DatasetLoader(unittest.TestCase):
    def test_default_dataset_shape_and_pinned_rows(self) -> None:
        dataset = ROOT / "data" / "structure" / "fsigma8_gold2017_plus_zhao2018.csv"
        rows = load_fsigma8_csv(str(dataset))

        self.assertEqual(len(rows), 22)

        first = rows[0]
        self.assertAlmostEqual(float(first["z"]), 0.02, delta=1.0e-12)
        self.assertAlmostEqual(float(first["fsigma8"]), 0.428, delta=1.0e-12)
        self.assertAlmostEqual(float(first["sigma"]), 0.0465, delta=1.0e-12)
        self.assertAlmostEqual(float(first["omega_m_ref"]), 0.3, delta=1.0e-12)
        self.assertEqual(str(first["ref_key"]), "Huterer2016")

        last = rows[-1]
        self.assertAlmostEqual(float(last["z"]), 1.944, delta=1.0e-12)
        self.assertAlmostEqual(float(last["fsigma8"]), 0.364, delta=1.0e-12)
        self.assertAlmostEqual(float(last["sigma"]), 0.106, delta=1.0e-12)
        self.assertAlmostEqual(float(last["omega_m_ref"]), 0.31, delta=1.0e-12)
        self.assertEqual(str(last["ref_key"]), "Zhao2018_z1944")

        for row in rows:
            self.assertGreater(float(row["z"]), 0.0)
            self.assertGreater(float(row["sigma"]), 0.0)
            self.assertGreaterEqual(float(row["omega_m_ref"]), 0.0)
            self.assertLessEqual(float(row["omega_m_ref"]), 1.0)


if __name__ == "__main__":
    unittest.main()

import math
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.search_sampling import iter_halton_points, iter_lhs_points  # noqa: E402


class TestSearchSamplingHaltonLHS(unittest.TestCase):
    def test_halton_dim1_matches_expected_base2_prefix(self):
        points = list(iter_halton_points({"x": (0.0, 1.0)}, n=5, seed=0, scramble=False, skip=0))
        got = [float(p["x"]) for p in points]
        expected = [0.5, 0.25, 0.75, 0.125, 0.625]
        self.assertEqual(len(got), len(expected))
        for g, e in zip(got, expected):
            self.assertAlmostEqual(g, e, places=12)

    def test_halton_scramble_is_deterministic_and_changes_sequence(self):
        bounds = {"x": (0.0, 1.0), "y": (0.0, 1.0)}
        plain = list(iter_halton_points(bounds, n=8, seed=7, scramble=False, skip=2))
        scr_a = list(iter_halton_points(bounds, n=8, seed=7, scramble=True, skip=2))
        scr_b = list(iter_halton_points(bounds, n=8, seed=7, scramble=True, skip=2))
        self.assertEqual(scr_a, scr_b)
        self.assertNotEqual(plain, scr_a)
        for row in scr_a:
            for key in ("x", "y"):
                self.assertGreaterEqual(float(row[key]), 0.0)
                self.assertLess(float(row[key]), 1.0)

    def test_lhs_center_stratifies_each_dimension(self):
        n = 10
        bounds = {"a": (0.0, 1.0), "b": (0.0, 1.0), "c": (0.0, 1.0)}
        a = list(iter_lhs_points(bounds, n=n, seed=11))
        b = list(iter_lhs_points(bounds, n=n, seed=11))
        c = list(iter_lhs_points(bounds, n=n, seed=12))

        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertEqual(len(a), n)

        for key in ("a", "b", "c"):
            bins = [int(math.floor(float(row[key]) * n)) for row in a]
            self.assertEqual(sorted(bins), list(range(n)))


if __name__ == "__main__":
    unittest.main()

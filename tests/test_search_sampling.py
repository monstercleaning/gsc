import math
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.search_sampling import iter_random_points, run_metropolis_hastings  # noqa: E402


class TestSearchSampling(unittest.TestCase):
    def test_iter_random_points_is_seed_deterministic(self):
        bounds = {"x": (0.0, 1.0), "y": (-2.0, 2.0)}
        a = list(iter_random_points(bounds, n=5, seed=1234))
        b = list(iter_random_points(bounds, n=5, seed=1234))
        c = list(iter_random_points(bounds, n=5, seed=999))
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        for row in a:
            self.assertGreaterEqual(row["x"], 0.0)
            self.assertLessEqual(row["x"], 1.0)
            self.assertGreaterEqual(row["y"], -2.0)
            self.assertLessEqual(row["y"], 2.0)

    def test_mh_is_deterministic_and_reports_acceptance_rate(self):
        def logp(p):
            x = float(p["x"])
            y = float(p["y"])
            return -0.5 * (x * x + y * y)

        start = {"x": 0.5, "y": -0.25}
        step = {"x": 0.4, "y": 0.3}
        bounds = {"x": (-2.0, 2.0), "y": (-2.0, 2.0)}

        a = run_metropolis_hastings(
            logp=logp,
            start=start,
            step_scales=step,
            n_steps=40,
            seed=42,
            burn=10,
            thin=3,
            bounds=bounds,
        )
        b = run_metropolis_hastings(
            logp=logp,
            start=start,
            step_scales=step,
            n_steps=40,
            seed=42,
            burn=10,
            thin=3,
            bounds=bounds,
        )
        self.assertEqual(a.samples, b.samples)
        self.assertGreater(len(a.samples), 0)
        self.assertTrue(math.isfinite(a.acceptance_rate))
        self.assertGreaterEqual(a.acceptance_rate, 0.0)
        self.assertLessEqual(a.acceptance_rate, 1.0)
        for row in a.samples:
            self.assertGreaterEqual(float(row["x"]), -2.0)
            self.assertLessEqual(float(row["x"]), 2.0)
            self.assertGreaterEqual(float(row["y"]), -2.0)
            self.assertLessEqual(float(row["y"]), 2.0)


if __name__ == "__main__":
    unittest.main()

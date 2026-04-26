from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.search_optimize import nelder_mead_minimize


class TestSearchOptimizeNelderMead(unittest.TestCase):
    def test_quadratic_minimize_in_bounds(self) -> None:
        def objective(x):
            xx = float(x[0])
            yy = float(x[1])
            return (xx - 1.0) ** 2 + 10.0 * (yy + 2.0) ** 2

        result = nelder_mead_minimize(
            objective,
            [4.0, -4.0],
            bounds=[(-5.0, 5.0), (-5.0, 5.0)],
            step=[0.8, 0.8],
            max_eval=300,
            tol_f=1e-12,
            tol_x=1e-12,
        )
        self.assertIn(result.get("stop_reason"), {"tol_f", "tol_x", "max_eval"})
        self.assertTrue(isinstance(result.get("n_eval"), int))
        self.assertLess(float(result.get("f_best", float("inf"))), 1e-6)
        best = result.get("x_best") or []
        self.assertEqual(len(best), 2)
        self.assertLess(abs(float(best[0]) - 1.0), 5e-3)
        self.assertLess(abs(float(best[1]) + 2.0), 5e-3)

    def test_deterministic_repeat(self) -> None:
        def objective(x):
            xx = float(x[0])
            yy = float(x[1])
            return (xx - 1.0) ** 2 + 10.0 * (yy + 2.0) ** 2

        r1 = nelder_mead_minimize(
            objective,
            [4.0, -4.0],
            bounds=[(-5.0, 5.0), (-5.0, 5.0)],
            step=[0.8, 0.8],
            max_eval=300,
            tol_f=1e-12,
            tol_x=1e-12,
        )
        r2 = nelder_mead_minimize(
            objective,
            [4.0, -4.0],
            bounds=[(-5.0, 5.0), (-5.0, 5.0)],
            step=[0.8, 0.8],
            max_eval=300,
            tol_f=1e-12,
            tol_x=1e-12,
        )
        self.assertEqual(int(r1["n_eval"]), int(r2["n_eval"]))
        self.assertEqual(bool(r1["converged"]), bool(r2["converged"]))
        self.assertEqual(str(r1["stop_reason"]), str(r2["stop_reason"]))
        x1 = [float(v) for v in (r1.get("x_best") or [])]
        x2 = [float(v) for v in (r2.get("x_best") or [])]
        self.assertEqual(len(x1), len(x2))
        for a, b in zip(x1, x2):
            self.assertLess(abs(float(a) - float(b)), 1e-12)
        self.assertLess(abs(float(r1["f_best"]) - float(r2["f_best"])), 1e-12)


if __name__ == "__main__":
    unittest.main()

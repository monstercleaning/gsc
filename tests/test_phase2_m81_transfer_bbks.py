import math
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gsc.structure.transfer_bbks import (  # noqa: E402
    sample_k_grid,
    shape_parameter_sugiyama,
    transfer_bbks,
)


class TestPhase2M81TransferBBKS(unittest.TestCase):
    def test_shape_parameter_sanity(self) -> None:
        gamma_eff = shape_parameter_sugiyama(Omega_m0=0.315, Omega_b0=0.049, h=0.674)
        self.assertTrue(math.isfinite(gamma_eff))
        self.assertGreater(gamma_eff, 0.0)
        self.assertLess(gamma_eff, 0.315 * 0.674)

    def test_transfer_small_k_limit_and_monotonic_drop(self) -> None:
        params = {"Omega_m0": 0.315, "Omega_b0": 0.049, "h": 0.674}
        t_small = transfer_bbks(1.0e-6, **params)
        self.assertAlmostEqual(t_small, 1.0, delta=5.0e-5)

        t_lo = transfer_bbks(1.0e-3, **params)
        t_hi = transfer_bbks(1.0, **params)
        self.assertGreater(t_lo, t_hi)
        self.assertGreater(t_hi, 0.0)

    def test_deterministic_pinned_values(self) -> None:
        params = {"Omega_m0": 0.315, "Omega_b0": 0.049, "h": 0.674}
        self.assertAlmostEqual(transfer_bbks(1.0e-4, **params), 0.9980330845218074, places=12)
        self.assertAlmostEqual(transfer_bbks(1.0e-2, **params), 0.6556274189544086, places=12)
        self.assertAlmostEqual(transfer_bbks(1.0, **params), 0.0024450746866542597, places=12)

    def test_log_grid_helper(self) -> None:
        grid = sample_k_grid(kmin=1.0e-4, kmax=1.0, n=5)
        self.assertEqual(len(grid), 5)
        self.assertAlmostEqual(grid[0], 1.0e-4)
        self.assertAlmostEqual(grid[-1], 1.0)
        self.assertTrue(all(grid[i] < grid[i + 1] for i in range(len(grid) - 1)))


if __name__ == "__main__":
    unittest.main()

import math
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from gsc.optional_deps import skip_module_unless_numpy  # noqa: E402

skip_module_unless_numpy("numpy not installed (skipping numpy-tier tests)")

import cmb_e2_drift_cmb_correlation as corr  # noqa: E402


class TestCMBE2ClosureDeformationSolvers(unittest.TestCase):
    def test_bump_solver_reduces_to_constant_when_interval_covers_all(self):
        import numpy as np

        z0 = 5.0
        z1 = 100.0
        z = np.linspace(z0, z1, 2048, dtype=float)
        w = np.ones_like(z, dtype=float)
        trap = getattr(np, "trapezoid", None) or np.trapz
        I0 = float(trap(w, z))

        r_target = 0.8
        A = corr.solve_bump_A_for_ratio(r_target=r_target, z=z, w=w, I0=I0, z1=z0, z2=z1)
        self.assertIsNotNone(A)
        self.assertTrue(math.isfinite(float(A)))
        self.assertAlmostEqual(float(A), 1.0 / float(r_target), places=10)

    def test_bump_solver_returns_none_if_required_closure_is_too_strong_for_small_window(self):
        import numpy as np

        z0 = 5.0
        z1 = 100.0
        z = np.linspace(z0, z1, 4096, dtype=float)
        w = np.ones_like(z, dtype=float)
        trap = getattr(np, "trapezoid", None) or np.trapz
        I0 = float(trap(w, z))

        # Bump interval is tiny, so the minimum achievable ratio is close to 1.
        # Requesting r_target well below that should be impossible.
        r_target = 0.95
        A = corr.solve_bump_A_for_ratio(r_target=r_target, z=z, w=w, I0=I0, z1=5.0, z2=6.0)
        self.assertIsNone(A)


if __name__ == "__main__":
    unittest.main()

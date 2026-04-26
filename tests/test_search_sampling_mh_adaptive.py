import math
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsc.search_sampling import (  # noqa: E402
    AdaptiveRWMHSampler,
    bounded_logit_inverse,
    bounded_logit_transform,
)


class TestSearchSamplingMHAdaptive(unittest.TestCase):
    def test_bounded_logit_round_trip(self):
        lo, hi = 0.1, 3.4
        xs = [lo, lo + 1e-12, 0.4, 1.2, hi - 1e-12, hi]
        for x in xs:
            y = bounded_logit_transform(x, lo, hi)
            x2 = bounded_logit_inverse(y, lo, hi)
            self.assertTrue(math.isfinite(y))
            self.assertTrue(math.isfinite(x2))
            self.assertGreaterEqual(x2, lo)
            self.assertLessEqual(x2, hi)
            self.assertAlmostEqual(x2, x, places=10)

    def test_proposals_are_seed_deterministic(self):
        bounds = {"x": (0.0, 1.0), "y": (1.0, 2.0)}
        start = {"x": 0.3, "y": 1.4}
        sampler_a = AdaptiveRWMHSampler(
            bounds=bounds,
            start=start,
            seed=123,
            init_scale=0.15,
            adapt_every=1000,
        )
        sampler_b = AdaptiveRWMHSampler(
            bounds=bounds,
            start=start,
            seed=123,
            init_scale=0.15,
            adapt_every=1000,
        )

        seq_a = []
        seq_b = []
        for accepted in (False, True, False, True, True):
            pa = sampler_a.propose()
            pb = sampler_b.propose()
            seq_a.append(pa.proposal)
            seq_b.append(pb.proposal)
            sampler_a.record_acceptance(accepted)
            sampler_b.record_acceptance(accepted)

        self.assertEqual(seq_a, seq_b)

    def test_adaptation_stays_bounded(self):
        bounds = {"x": (0.0, 1.0), "y": (-2.0, 2.0)}
        start = {"x": 0.5, "y": 0.0}
        sampler = AdaptiveRWMHSampler(
            bounds=bounds,
            start=start,
            seed=7,
            init_scale=0.1,
            target_accept=0.25,
            adapt_every=2,
            min_scale=1e-6,
            max_scale=1e2,
        )

        accepted_pattern = [True, True, False, False, True, False, False, False]
        for accepted in accepted_pattern:
            sampler.propose()
            sampler.record_acceptance(accepted)

        state = sampler.transform_state()
        self.assertGreaterEqual(state.adaptation_round, 1)
        for _, scale in sorted(state.scales.items()):
            self.assertTrue(math.isfinite(float(scale)))
            self.assertGreaterEqual(float(scale), 1e-6)
            self.assertLessEqual(float(scale), 1e2)


if __name__ == "__main__":
    unittest.main()

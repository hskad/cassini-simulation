import copy
import random
import unittest

from experiments.strided_lcm_experiment import build_case
from src.analysis.periodic_traffic import periodic_traffic
from src.core.models import Link
from src.math_engine.optimizer import get_strided_windows, optimize_link, score_link


class TestRandomWindows(unittest.TestCase):
    def test_exact_budget_strata_reproducibility_and_rng_isolation(self):
        jobs = build_case("coprime_pair", 42)
        state = random.getstate()
        windows = get_strided_windows(jobs, num_windows=5, sampling_seed=11)
        self.assertEqual(random.getstate(), state)
        self.assertEqual(windows, get_strided_windows(jobs, num_windows=5, sampling_seed=11))
        self.assertNotEqual(windows, get_strided_windows(jobs, num_windows=5, sampling_seed=23))
        self.assertEqual(sum(d for _, d in windows), 600)
        for k, (start, duration) in enumerate(windows):
            self.assertGreaterEqual(start, k * 10100 // 5)
            self.assertLessEqual(start + duration, (k + 1) * 10100 // 5)

    def test_short_common_period_uses_exact_full_period(self):
        jobs = build_case("short_pair", 42)
        self.assertEqual(get_strided_windows(jobs, num_windows=5, sampling_seed=11), [(0, 120)])

    def test_selected_sample_score_matches_independent_phase_integration(self):
        jobs = build_case("near_shared_three", 42)
        link = Link("L", 50)
        kwargs = dict(num_windows=5, sampling_seed=11)
        optimize_link(jobs, link, **kwargs)
        windows = get_strided_windows(jobs, **kwargs)
        checked = sum(periodic_traffic(jobs, 50, s, d)["score"] * d for s, d in windows) / 600
        self.assertAlmostEqual(score_link(jobs, link, **kwargs), checked, places=5)
        repeated = copy.deepcopy(jobs)
        optimize_link(repeated, link, **kwargs)
        self.assertEqual([j.time_shift for j in jobs], [j.time_shift for j in repeated])

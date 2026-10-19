import unittest
from unittest.mock import patch

from experiments.lcm_scoring_experiment import evaluate_case
from src.core.models import Job, Phase


class TestLCMExperiment(unittest.TestCase):
    def test_short_window_optimism_is_checked_on_a_later_full_period(self):
        jobs = [Job("a", "a", [Phase("compute", 2, 0), Phase("communicate", 1, 50)]),
                Job("b", "b", [Phase("compute", 4, 0), Phase("communicate", 1, 50)])]
        result = evaluate_case("coprime_pair", 42, jobs, [4], repetitions=1)
        prefix, full = result["runs"]
        self.assertEqual(result["lcm_ms"], 15)
        self.assertEqual(result["validation_start_ms"], 15)
        self.assertEqual(prefix["estimated_score"], 1)
        self.assertAlmostEqual(prefix["validation"]["score"], 14 / 15)
        self.assertAlmostEqual(prefix["score_optimism_pp"], 100 / 15)
        self.assertEqual(prefix["validated_gain_vs_zero_pp"], 0)
        self.assertEqual(prefix["gap_to_full_window_search_pp"], 0)
        self.assertAlmostEqual(full["score_optimism_pp"], 0, places=4)
        self.assertTrue(all(job.time_shift == 0 for job in jobs))

    def test_exact_reference_limit_is_checked_before_optimization(self):
        jobs = [Job(str(p), str(p), [Phase("compute", p, 0)]) for p in (101, 103, 107)]
        with patch("experiments.lcm_scoring_experiment.optimize_link") as optimize:
            with self.assertRaisesRegex(ValueError, "exceeds the exact-reference limit"):
                evaluate_case("large", 42, jobs, [600], max_lcm_ms=100000)
            optimize.assert_not_called()

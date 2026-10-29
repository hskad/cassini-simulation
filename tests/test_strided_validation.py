import copy
import unittest
from unittest.mock import patch

from experiments.strided_validation import evaluate_case
from experiments.strided_lcm_experiment import build_case
from src.core.models import Job, Phase


class TestStridedValidation(unittest.TestCase):
    def test_same_reference_and_independent_samples_for_all_methods(self):
        jobs = build_case("coprime_pair", 42)
        original = copy.deepcopy(jobs)
        result = evaluate_case("coprime_pair", 42, jobs, repetitions=1)
        self.assertEqual(result["validation_interval_ms"], [10100, 20200])
        self.assertEqual(jobs, original)
        for row in result["runs"]:
            self.assertLessEqual(row["actual_samples"], row["budget_ms"])
            self.assertAlmostEqual(row["estimated_score"], row["independent_sample_score"], places=5)
            self.assertAlmostEqual(row["gain_vs_zero_pp"], 0, places=8)
            self.assertAlmostEqual(row["quality_gain_vs_prefix_pp"], 0, places=8)

    def test_guard_prevents_expensive_reference_search(self):
        jobs = [Job(str(p), str(p), [Phase("compute", p, 0)]) for p in (101, 103, 107)]
        with patch("experiments.strided_validation.optimize_link") as search:
            with self.assertRaisesRegex(ValueError, "exact-reference limit"):
                evaluate_case("large", 42, jobs)
            search.assert_not_called()

    def test_incorrect_sample_score_is_rejected_by_independent_check(self):
        with patch("experiments.strided_validation.score_link", return_value=-10):
            with self.assertRaisesRegex(ValueError, "independent window integration"):
                evaluate_case("coprime_pair", 42, build_case("coprime_pair", 42), repetitions=1)

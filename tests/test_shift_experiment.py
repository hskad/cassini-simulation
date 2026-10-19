import unittest

from experiments.shift_policy_experiment import POLICIES, aggregate, run_case
from src.core.models import Cluster, Job, Link, Phase
from unittest.mock import patch


class TestShiftExperiment(unittest.TestCase):
    def test_aggregation_uses_paired_seed_percentages(self):
        runs = []
        for seed, vanilla, candidate in ((1, 100, 90), (2, 200, 160)):
            for policy in POLICIES:
                value = vanilla if policy == "compatibility" else candidate
                runs.append(dict(workload="case", policy=policy, mean_jct_ms=value,
                                 mean_jct_gain_percent=100 * (vanilla - value) / vanilla,
                                 p95_jct_ms=value, mean_wait_ms=0, shift_changes=0,
                                 simulation_seconds=0))
        row = aggregate(runs)["case"]["benefit"]
        self.assertEqual(row["mean_gain_percent"], 15)
        self.assertEqual(row["min_gain_percent"], 10)
        self.assertEqual(row["max_gain_percent"], 20)
        self.assertEqual(row["seeds"], 2)

    def test_runner_preserves_inputs_and_pairs_all_four_policies(self):
        jobs = [Job(name, name, [Phase("compute", 50, 0), Phase("communicate", 50, 50)])
                for name in ("a", "b")]
        with patch("experiments.shift_policy_experiment.build_workload",
                   return_value=(jobs, Cluster([], [Link("link", 50)]), True)):
            metrics, completed = run_case("short", 42)
        self.assertEqual(set(metrics), set(POLICIES))
        self.assertEqual(len({row["placement_sha256"] for row in metrics.values()}), 1)
        self.assertEqual(len({row["input_sha256"] for row in metrics.values()}), 1)
        self.assertTrue(all(job.time_shift == 0 for job in jobs))
        self.assertTrue(all(len(rows) == 2 for rows in completed.values()))
        self.assertEqual(metrics["uncoordinated"]["mean_wait_ms"], 0)

import unittest

from src.core.models import Cluster, Job, Link, Phase
from src.math_engine import optimizer
from src.scheduler.evaluator import PlacementCandidate, evaluate_placements, score_candidate
from src.scheduler.simulator import Simulator, eval_link_compatibility


def pair():
    return [
        Job("a", "Period 61", [Phase("compute", 20, 0), Phase("communicate", 41, 50)]),
        Job("b", "Period 67", [Phase("compute", 30, 0), Phase("communicate", 37, 50)]),
    ]


def reference_score(window, optimized):
    # Count overlap directly from the two periods, without sampled arrays.
    overlaps = [sum(time % 61 >= 20 and (time - shift) % 67 >= 30
                    for time in range(window))
                for shift in (range(67) if optimized else [0])]
    return 1 - min(overlaps) / window


class TestScoringWindow(unittest.TestCase):
    def test_default_scores_use_optimizer_window(self):
        link = Link("link", 50)
        for optimized in (False, True):
            with self.subTest(optimized=optimized):
                expected = reference_score(600, optimized)
                jobs = pair()
                candidate = PlacementCandidate("one", Cluster([], [link], {"link": jobs}))
                placement_score, _ = score_candidate(candidate, optimize=optimized)
                runtime_score, _ = eval_link_compatibility(jobs, link, optimize=optimized)
                self.assertAlmostEqual(placement_score, expected, places=6)
                self.assertAlmostEqual(runtime_score, expected, places=6)

    def test_custom_window_reaches_every_scoring_path(self):
        link = Link("link", 50)
        for window in (37, 600, 1200):
            with self.subTest(window=window):
                jobs = pair()
                candidate = PlacementCandidate("one", Cluster([], [link], {"link": jobs}))
                expected = reference_score(window, True)
                optimizer.optimize_link(jobs, link, score_window_ms=window)
                score = optimizer.score_link(jobs, link, score_window_ms=window)
                placement_score, _ = score_candidate(candidate, score_window_ms=window)
                runtime_score, _ = eval_link_compatibility(jobs, link, score_window_ms=window)
                winner, _ = evaluate_placements([candidate], score_window_ms=window)
                for actual in (score, placement_score, runtime_score, winner.compatibility_score):
                    self.assertAlmostEqual(actual, expected, places=6)

    def test_short_common_period_and_window_limit(self):
        jobs = [Job("a", "Period 40", [Phase("compute", 40, 0)]),
                Job("b", "Period 60", [Phase("compute", 60, 0)])]
        self.assertEqual(optimizer.get_score_window(jobs), 120)
        self.assertEqual(optimizer.get_score_window(pair()), 600)
        self.assertEqual(optimizer.get_score_window(pair(), score_window_ms=1200), 1200)

    def test_limit_is_in_ms_at_different_resolutions(self):
        for resolution in (0.5, 1, 2):
            with self.subTest(resolution=resolution):
                self.assertEqual(optimizer.get_score_window(
                    pair(), resolution=resolution), 600)

    def test_invalid_window_is_rejected(self):
        for window in (0, -1, float("nan"), float("inf")):
            with self.subTest(window=window):
                with self.assertRaises(ValueError):
                    optimizer.get_score_window(pair(), score_window_ms=window)
                with self.assertRaises(ValueError):
                    Simulator(Cluster([], [Link("link", 50)]), score_window_ms=window)

    def test_simulator_passes_window_in_both_modes_and_policies(self):
        for window in (37, 600, 1200):
            for incremental in (False, True):
                for enabled in (False, True):
                    with self.subTest(window=window, incremental=incremental, cassini=enabled):
                        sim = Simulator(Cluster([], [Link("link", 50)]), penalty_factor=1.5,
                                        use_cassini=enabled, incremental=incremental,
                                        score_window_ms=window)
                        for job in pair():
                            sim.add_job_arrival(job)
                        sim.run_simulation()
                        times = {r["job_id"]: r["turnaround_time"] for r in sim.completed_jobs}
                        # Both jobs share one slowdown until a completes. Then
                        # b's remaining six milliseconds run without contention.
                        first_finish = 61 * (1 + 1.5 * (1 - reference_score(window, enabled)))
                        self.assertAlmostEqual(times["a"], first_finish, delta=1e-4)
                        self.assertAlmostEqual(times["b"], first_finish + 6, delta=1e-4)


if __name__ == "__main__":
    unittest.main()

import unittest
import numpy as np

from src.core.models import Job, Phase, Link
from src.math_engine.optimizer import (
    discretize_phases,
    calculate_score,
    get_strided_windows,
    score_link,
    optimize_link,
    DEFAULT_SCORE_WINDOW_MS
)


class TestStridedSampling(unittest.TestCase):
    def setUp(self):
        self.job100 = Job("j100", "Period 100", [
            Phase("compute", 60.0, 0.0), Phase("communicate", 40.0, 50.0)
        ])
        self.job101 = Job("j101", "Period 101", [
            Phase("compute", 60.0, 0.0), Phase("communicate", 41.0, 50.0)
        ])
        self.link = Link("l1", capacity=50.0)

    def test_discretize_phases_with_start_time(self):
        # A 10ms period job: 6ms compute, 4ms comm.
        job = Job("j10", "Period 10", [
            Phase("compute", 6.0, 0.0), Phase("communicate", 4.0, 50.0)
        ], time_shift=0.0)

        # Sampling at start_time=0 for 10ms -> [0,0,0,0,0,0, 50,50,50,50]
        arr0 = discretize_phases(job, 10.0, resolution=1.0, start_time=0.0)
        self.assertEqual(arr0, [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 50.0, 50.0, 50.0, 50.0])

        # Sampling at start_time=4 for 10ms -> offset starts at point 4 of cycle:
        # [0, 0, 50, 50, 50, 50, 0, 0, 0, 0]
        arr4 = discretize_phases(job, 10.0, resolution=1.0, start_time=4.0)
        self.assertEqual(arr4, [0.0, 0.0, 50.0, 50.0, 50.0, 50.0, 0.0, 0.0, 0.0, 0.0])

    def test_get_strided_windows_budget_and_coverage(self):
        # For jobs with LCM <= budget (e.g. 40 and 60 -> LCM 120 <= 600)
        j40 = Job("j40", "Period 40", [Phase("compute", 40.0, 0.0)])
        j60 = Job("j60", "Period 60", [Phase("compute", 60.0, 0.0)])
        windows_small = get_strided_windows([j40, j60], score_window_ms=600.0, num_windows=3)
        self.assertEqual(windows_small, [(0.0, 120.0)])

        # For coprime jobs (100 and 101 -> LCM 10,100 > 600)
        windows = get_strided_windows([self.job100, self.job101], score_window_ms=600.0, num_windows=3)
        self.assertEqual(len(windows), 3)
        # Each segment duration should be 600 // 3 = 200 ms
        for _, dur in windows:
            self.assertEqual(dur, 200.0)
        # First window starts at 0, last window starts at 10,100 - 200 = 9,900
        self.assertEqual(windows[0][0], 0.0)
        self.assertEqual(windows[-1][0], 9900.0)
        self.assertEqual(windows[1][0], 4950.0)

    def test_strided_sampling_accuracy_on_coprime_pair(self):
        # True full LCM score over 10,100 ms
        full_score = score_link([self.job100, self.job101], self.link, score_window_ms=10100.0)
        
        # Contiguous 600 ms score
        contig_score = score_link([self.job100, self.job101], self.link, score_window_ms=600.0, num_windows=1)

        # Strided 3-window score (600 ms total budget: 3 x 200 ms)
        strided_score = score_link([self.job100, self.job101], self.link, score_window_ms=600.0, num_windows=3)

        # Strided score should be substantially closer to the true full LCM score
        error_contig = abs(contig_score - full_score)
        error_strided = abs(strided_score - full_score)

        self.assertLess(error_strided, error_contig)
        # Error should be reduced by more than 50%
        self.assertLess(error_strided, error_contig * 0.6)

    def test_optimize_link_strided(self):
        # Optimize using 3 strided windows
        self.job100.time_shift = 0.0
        self.job101.time_shift = 0.0
        score_before = score_link([self.job100, self.job101], self.link, score_window_ms=600.0, num_windows=3)

        optimize_link([self.job100, self.job101], self.link, score_window_ms=600.0, num_windows=3)
        score_after = score_link([self.job100, self.job101], self.link, score_window_ms=600.0, num_windows=3)

        self.assertGreater(score_after, score_before)
        self.assertGreater(self.job101.time_shift, 0.0)


if __name__ == '__main__':
    unittest.main()

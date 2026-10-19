import unittest
import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core.models import Phase, Job, Link
from src.math_engine.optimizer import discretize_phases, calculate_score, optimize_link

class TestOptimizer(unittest.TestCase):
    def setUp(self):
        # Two identical VGG16 jobs
        self.job1 = Job(job_id="j1", name="VGG16_1", phases=[
            Phase("compute", duration=141.0, bandwidth_demand=0.0),
            Phase("communicate", duration=114.0, bandwidth_demand=25.0)
        ])
        
        self.job2 = Job(job_id="j2", name="VGG16_2", phases=[
            Phase("compute", duration=141.0, bandwidth_demand=0.0),
            Phase("communicate", duration=114.0, bandwidth_demand=25.0)
        ])
        
        self.link = Link(link_id="l1", capacity=25.0)

    def test_discretize_phases(self):
        arr = discretize_phases(self.job1, 255.0, resolution=1.0)
        self.assertEqual(len(arr), 255)
        self.assertEqual(arr[0], 0.0) # compute phase
        self.assertEqual(arr[150], 25.0) # communicate phase

    def test_optimize_link(self):
        # Before optimization, they both communicate at the same time (141 to 255)
        # Capacity is 25, total demand is 50, so excess is 25 for 114 steps.
        # Average excess = 25 * 114 / 255 = 11.17
        # Score = 1 - (11.17 / 25) = 1 - 0.447 = 0.553
        arr1 = discretize_phases(self.job1, 255.0, resolution=1.0)
        arr2 = discretize_phases(self.job2, 255.0, resolution=1.0)
        score_before = calculate_score([arr1, arr2], self.link.capacity)
        
        # Now optimize
        optimize_link([self.job1, self.job2], self.link, resolution=1.0)
        
        # After optimization, they should be shifted to not overlap
        arr1_after = discretize_phases(self.job1, 255.0, resolution=1.0)
        arr2_after = discretize_phases(self.job2, 255.0, resolution=1.0)
        score_after = calculate_score([arr1_after, arr2_after], self.link.capacity)
        
        self.assertGreater(score_after, score_before)
        self.assertEqual(score_after, 1.0) # 100% compatible if perfectly shifted
        self.assertGreater(self.job2.time_shift, 0.0)

    def test_shift_before_truncating_periodic_profile(self):
        job = Job("short", "Seven-ms cycle", [
            Phase("compute", 5, 0), Phase("communicate", 2, 50)
        ], time_shift=3)

        # Communication wraps into samples 1 and 2 from the preceding cycle.
        self.assertEqual(discretize_phases(job, 10),
                         [0, 50, 50, 0, 0, 0, 0, 0, 50, 50])

    def test_shifted_profile_matches_periodic_time_at_each_sample(self):
        for resolution in (0.5, 1.0):
            for window_steps in (1, 3, 7, 10, 14, 21):
                for shift_steps in (-25, -3, 0, 3, 7, 38):
                    with self.subTest(resolution=resolution, window=window_steps,
                                      shift=shift_steps):
                        job = Job("periodic", "Periodic profile", [
                            Phase("compute", 5 * resolution, 0),
                            Phase("communicate", 2 * resolution, 50)
                        ], time_shift=shift_steps * resolution)
                        expected = [50 if (step - shift_steps) % 7 >= 5 else 0
                                    for step in range(window_steps)]
                        self.assertEqual(discretize_phases(
                            job, window_steps * resolution, resolution), expected)

    def test_optimizer_uses_periodic_shifts_in_capped_window(self):
        job_a = Job("a", "Period 61", [
            Phase("compute", 20, 0), Phase("communicate", 41, 50)
        ])
        job_b = Job("b", "Period 67", [
            Phase("compute", 30, 0), Phase("communicate", 37, 50)
        ])
        # The common period is 4087 ms; this optimizer searches a 600-ms window.
        # Calculate overlap directly from time modulo each job's period.
        overlaps = [sum(50 for time in range(600)
                        if time % 61 >= 20 and (time - shift) % 67 >= 30)
                    for shift in range(67)]

        optimize_link([job_a, job_b], Link("link", 50))

        self.assertEqual(job_a.time_shift, 0)
        self.assertEqual(job_b.time_shift, overlaps.index(min(overlaps)))
        self.assertEqual(min(overlaps), 10300)

if __name__ == '__main__':
    unittest.main()

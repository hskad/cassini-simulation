import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.models import Phase, Job, Link
from src.optimizer import discretize_phases, calculate_score, optimize_link

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

if __name__ == '__main__':
    unittest.main()

import unittest

from src.analysis.periodic_traffic import periodic_traffic
from src.core.models import Job, Phase


class TestPeriodicTraffic(unittest.TestCase):
    def test_fractional_intervals_and_boundary_clipping(self):
        a = Job("a", "a", [Phase("compute", 0.5, 0), Phase("communicate", 1.5, 50)])
        b = Job("b", "b", a.phases, time_shift=0.5)
        # a communicates on [.5,2); b on [1,2.5), with previous b on [-1,.5).
        result = periodic_traffic([a, b], 50, 0, 2)
        self.assertEqual(result["excess_area_gbps_ms"], 50)
        self.assertEqual(result["overloaded_fraction"], 0.5)
        self.assertEqual(result["score"], 0.5)
        self.assertEqual(periodic_traffic([a, b], 50, 2, 2), result)

    def test_aggregate_capacity_detects_three_way_overload(self):
        jobs = [Job(str(i), "job", [Phase("communicate", 10, 20)]) for i in range(3)]
        self.assertEqual(periodic_traffic(jobs[:2], 50, 0, 10)["score"], 1)
        result = periodic_traffic(jobs, 50, 0, 10)
        self.assertEqual(result["score"], 0.8)
        self.assertEqual(result["peak_demand_gbps"], 60)

    def test_coprime_pair_full_period_is_shift_invariant(self):
        # With integer slots and coprime periods, every pair of residues appears
        # once per full period. One busy slot each therefore overlaps once.
        a = Job("a", "a", [Phase("compute", 2, 0), Phase("communicate", 1, 50)])
        b = Job("b", "b", [Phase("compute", 4, 0), Phase("communicate", 1, 50)])
        for shift in range(5):
            b.time_shift = shift
            self.assertAlmostEqual(periodic_traffic([a, b], 50, 15, 15)["score"], 14 / 15)

    def test_invalid_intervals_and_profiles(self):
        for start, duration in ((0, 0), (0, -1), (float("nan"), 1), (0, float("inf"))):
            with self.assertRaises(ValueError):
                periodic_traffic([], 50, start, duration)
        for phase in (Phase("x", 0, 0), Phase("x", -1, 0), Phase("x", 1, -1)):
            with self.assertRaises(ValueError):
                periodic_traffic([Job("a", "a", [phase])], 50, 0, 1)

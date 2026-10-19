import copy
import unittest
from src.core.models import Cluster, Link
from src.scheduler.simulator import Simulator
from test_phase_execution import make_job


class TestDriftCorrection(unittest.TestCase):
    def run_pair(self, threshold=0.05, extra_compute=0, **options):
        jobs = [make_job("A", iterations=3), make_job("B", iterations=3)]
        sim = Simulator(Cluster([], [Link("L", 50)]), record_history=True,
                        drift_threshold=threshold, **options)
        original = sim._compute_duration
        sim._compute_duration = lambda state: original(state) + (
            extra_compute if state.job.job_id == "A" and state.phase_index == 0 else 0)
        for job in copy.deepcopy(jobs):
            sim.add_job_arrival(job)
        sim.run_simulation()
        return sim

    def test_no_noise_needs_no_correction(self):
        self.assertEqual(self.run_pair().adjustments, [])

    def test_above_threshold_delays_to_next_slot(self):
        sim = self.run_pair(extra_compute=10)
        first = sim.adjustments[0]
        self.assertEqual(first["job_id"], "A")
        self.assertEqual(first["phase_error_ms"], 10)
        self.assertEqual(first["delay_ms"], 90)
        comm = [r for r in sim.phase_history if r["job_id"] == "A"
                and r["iteration"] == 0 and r["type"] == "communicate"]
        self.assertEqual(comm[0]["start"], 150)
        self.assertGreaterEqual(sim.completed_jobs[-1]["wait_time"], 90)

    def test_exact_threshold_does_not_trigger(self):
        sim = self.run_pair(extra_compute=5)
        self.assertFalse(any(r["iteration"] == 0 and r["job_id"] == "A" for r in sim.adjustments))

    def test_correction_can_be_disabled(self):
        self.assertEqual(self.run_pair(threshold=None, extra_compute=10).adjustments, [])

    def test_compute_noise_matches_across_policies(self):
        results = []
        for policy in [False, True]:
            sim = self.run_pair(compute_jitter=0.04, seed=7, use_cassini=policy)
            durations = {}
            for row in sim.phase_history:
                if row["type"] == "compute":
                    key = (row["job_id"], row["iteration"])
                    durations[key] = durations.get(key, 0) + row["end"] - row["start"]
            results.append(durations)
        self.assertEqual(results[0].keys(), results[1].keys())
        for key in results[0]:
            self.assertAlmostEqual(results[0][key], results[1][key])

    def test_invalid_jitter_is_rejected(self):
        with self.assertRaises(ValueError):
            self.run_pair(compute_jitter=1.1)


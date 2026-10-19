"""Check the constructed workload against known transfer and delay costs."""
import copy
import unittest
from dataclasses import asdict

from src.benchmark import BenchmarkCase, audit_run
from src.core.models import Cluster
from src.scheduler.simulator import Simulator
from src.workloads import compatible_workload, check_compatible_completion


class TestCompatibleWorkload(unittest.TestCase):
    def test_input_is_reproducible_and_explicitly_synthetic(self):
        jobs, cluster, metadata = compatible_workload()
        other, _, _ = compatible_workload()
        self.assertEqual([asdict(job) for job in jobs], [asdict(job) for job in other])
        self.assertEqual(metadata["kind"], "synthetic")
        self.assertEqual(len(jobs), 56)
        self.assertEqual(len(cluster.links), 7)
        for members in cluster.link_jobs.values():
            self.assertEqual(len(members), 8)
            for job in members:
                self.assertEqual(job.arrival_time, 0)
                self.assertEqual(job.phases[0].duration, 7 * job.phases[1].duration)
                self.assertGreaterEqual(job.total_iterations, 200)
                self.assertLessEqual(job.total_iterations, 400)

    def test_varied_job_lengths_match_analytical_times_and_conserve_work(self):
        jobs, original, _ = compatible_workload(iterations=5)
        jobs = jobs[:8]
        for index, job in enumerate(jobs):
            job.total_iterations += index
        cluster = Cluster([], original.links[:1], {"L1": jobs})
        means = []
        for enabled in [False, True]:
            sim = Simulator(cluster, use_cassini=enabled, record_history=True)
            for job in copy.deepcopy(jobs):
                sim.add_job_arrival(job)
            sim.run_simulation()
            check_compatible_completion(cluster, sim, enabled)
            audit_run(BenchmarkCase("compatible", jobs, cluster), sim)
            means.append(sum(row["turnaround_time"] for row in sim.completed_jobs) / len(jobs))
        self.assertLess(means[1], means[0])

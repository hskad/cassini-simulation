import unittest
from unittest.mock import patch
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core.models import Phase, Job, Link, Cluster
from src.scheduler.simulator import Simulator, Event

class TestSimulator(unittest.TestCase):
    def test_simulator_single_job(self):
        job = Job(job_id="j1", name="test_job", phases=[Phase("compute", 100, 0)], arrival_time=0.0, total_iterations=5)
        link = Link("l1", 50)
        cluster = Cluster([], [link])
        
        sim = Simulator(cluster)
        sim.add_job_arrival(job)
        sim.run_simulation()
        
        self.assertEqual(len(sim.completed_jobs), 1)
        completed = sim.completed_jobs[0]
        self.assertEqual(completed["job_id"], "j1")
        # 5 iterations of 100ms each = 500ms
        self.assertAlmostEqual(completed["turnaround_time"], 500.0)
        
    def test_simulator_two_jobs(self):
        # Two jobs that can't fit on the same link (50+50 > 50 link capacity)
        # They will be forced onto separate links by the mock evaluator (since there are 2 links available)
        job1 = Job("j1", "test_job1", phases=[Phase("compute", 100, 50)], arrival_time=0.0, total_iterations=10)
        job2 = Job("j2", "test_job2", phases=[Phase("compute", 100, 50)], arrival_time=100.0, total_iterations=5)
        
        link1 = Link("l1", 50)
        link2 = Link("l2", 50)
        cluster = Cluster([], [link1, link2])
        
        sim = Simulator(cluster)
        sim.add_job_arrival(job1)
        sim.add_job_arrival(job2)
        sim.run_simulation()
        
        self.assertEqual(len(sim.completed_jobs), 2)

    def test_heavy_traffic_matches_runtime_formula(self):
        # Constant traffic has score 2 - job_count on one 50-Gbps link.
        # With four jobs and penalty=1, each job must take 400 ms.
        for count in (4, 8):
            for penalty in (1.0, 1.5):
                for enabled in (False, True):
                    for incremental in (False, True):
                        with self.subTest(jobs=count, penalty=penalty,
                                          cassini=enabled, incremental=incremental):
                            sim = Simulator(Cluster([], [Link("link", 50)]),
                                            penalty_factor=penalty, use_cassini=enabled,
                                            incremental=incremental)
                            for index in range(count):
                                sim.add_job_arrival(Job(str(index), "Constant traffic", [
                                    Phase("communicate", 100, 50)
                                ]))
                            sim.run_simulation()
                            expected = 100 * (1 + penalty * (count - 1))
                            self.assertEqual(len(sim.completed_jobs), count)
                            for row in sim.completed_jobs:
                                self.assertAlmostEqual(row["turnaround_time"], expected)

    def test_choose_best_link_when_all_candidate_scores_below_minus_one(self):
        # After seven arrivals, the links hold three and four jobs. The eighth
        # arrival gives scores -2 (50 Gbps) and -1.125 (80 Gbps). It must use
        # the 80-Gbps link even though neither candidate has a score above -1.
        for enabled in (False, True):
            with self.subTest(cassini=enabled):
                sim = Simulator(Cluster([], [Link("small", 50), Link("large", 80)]),
                                penalty_factor=1, use_cassini=enabled, incremental=True)
                for index in range(8):
                    sim.add_job_arrival(Job(str(index), "Constant traffic", [
                        Phase("communicate", 100, 50)
                    ]))
                sim.run_simulation()
                # Three jobs share 50 Gbps; five share 80 Gbps. Under this
                # model their completion times are 300 and 312.5 ms.
                times = sorted(row["turnaround_time"] for row in sim.completed_jobs)
                self.assertEqual(times, [300.0] * 3 + [312.5] * 5)

    def test_shift_is_one_wait_not_one_wait_per_iteration(self):
        for incremental in (False, True):
            for enabled in (False, True):
                for iterations in (1, 100):
                    with self.subTest(incremental=incremental, cassini=enabled, iterations=iterations):
                        sim = Simulator(Cluster([], [Link("link", 50)]),
                                        use_cassini=enabled, incremental=incremental)
                        for name in ("a", "b"):
                            sim.add_job_arrival(Job(name, name, [
                                Phase("compute", 10, 0), Phase("communicate", 10, 50)
                            ], total_iterations=iterations))
                        sim.run_simulation()
                        rows = {r["job_id"]: r for r in sim.completed_jobs}
                        if enabled:
                            self.assertEqual(rows["a"]["turnaround_time"], 20 * iterations)
                            self.assertEqual(rows["b"]["turnaround_time"], 20 * iterations + 10)
                            self.assertEqual(rows["b"]["shift_wait_ms"], 10)
                        else:
                            self.assertTrue(all(r["shift_wait_ms"] == 0 for r in rows.values()))
                            self.assertTrue(all(r["turnaround_time"] == 30 * iterations for r in rows.values()))

    def test_pending_wait_survives_arrivals_and_reoptimization(self):
        # Prescribe shift plans to isolate accounting from the search algorithm.
        # A third job arrives at t=10 and leaves at t=15, during b's wait.
        for incremental in (False, True):
            for target, expected_wait, arrival in ((40, 40, 10), (70, 70, 10),
                                                  (20, 120, 10), (70, 70, 60)):
                with self.subTest(incremental=incremental, target=target, arrival=arrival):
                    changed = False
                    def plan(jobs, link, *args, **kwargs):
                        nonlocal changed
                        if len(jobs) < 2:
                            return
                        if any(j.job_id == "trigger" for j in jobs):
                            changed = True
                        for job in jobs:
                            job.time_shift = (target if changed else 40) if job.job_id == "b" else 0
                    sim = Simulator(Cluster([], [Link("link", 50)]), incremental=incremental)
                    for name in ("a", "b"):
                        sim.add_job_arrival(Job(name, name, [Phase("compute", 100, 0)]))
                    sim.add_job_arrival(Job("trigger", "trigger", [Phase("compute", 5, 0)], arrival_time=arrival))
                    with patch("src.scheduler.simulator.optimize_link", side_effect=plan), \
                         patch("src.scheduler.evaluator.optimize_link", side_effect=plan):
                        sim.run_simulation()
                    rows = {r["job_id"]: r for r in sim.completed_jobs}
                    self.assertEqual(rows["a"]["turnaround_time"], 100)
                    self.assertEqual(rows["trigger"]["turnaround_time"], 5)
                    self.assertEqual(rows["b"]["shift_wait_ms"], expected_wait)
                    self.assertEqual(rows["b"]["turnaround_time"], 100 + expected_wait)

if __name__ == '__main__':
    unittest.main()

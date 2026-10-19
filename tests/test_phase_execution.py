"""Analytical checks for phase execution and conservation of network work."""
import copy
import unittest

from src.core.models import Cluster, Job, Link, Phase
from src.scheduler.simulator import Simulator, eval_link_compatibility


def make_job(jid, arrival=0, shift=0, iterations=1, compute=50, comm=50, demand=50):
    return Job(jid, jid, [Phase("compute", compute, 0), Phase("communicate", comm, demand)],
               time_shift=shift, arrival_time=arrival, total_iterations=iterations)


class TestPhaseExecution(unittest.TestCase):
    def run_jobs(self, jobs, cassini=False, routes=None, links=None, **kwargs):
        links = links or [Link("L", 50)]
        cluster = Cluster([], links, routes or {})
        sim = Simulator(cluster, use_cassini=cassini, record_history=True, **kwargs)
        for job in copy.deepcopy(jobs):
            sim.add_job_arrival(job)
        sim.run_simulation()
        return sim

    def test_synchronized_transfers_share_capacity(self):
        sim = self.run_jobs([make_job("A"), make_job("B")])
        self.assertEqual([r["completion_time"] for r in sim.completed_jobs], [150, 150])
        for row in sim.link_history:
            self.assertLessEqual(row["served_gbps"], row["capacity_gbps"] + 1e-9)

    def test_alignment_delay_is_charged(self):
        sim = self.run_jobs([make_job("A"), make_job("B")], cassini=True)
        rows = {r["job_id"]: r for r in sim.completed_jobs}
        self.assertEqual(rows["A"]["completion_time"], 100)
        self.assertEqual(rows["B"]["completion_time"], 150)
        self.assertEqual(rows["B"]["wait_time"], 50)

    def test_staggered_arrivals_do_not_collide(self):
        sim = self.run_jobs([make_job("A", iterations=10), make_job("B", arrival=50, iterations=10)])
        self.assertEqual([r["turnaround_time"] for r in sim.completed_jobs], [1000, 1000])

    def test_manual_initial_shift_is_charged_once(self):
        sim = self.run_jobs([make_job("A", shift=500, iterations=3)])
        self.assertEqual(sim.completed_jobs[0]["turnaround_time"], 800)
        self.assertEqual(sim.completed_jobs[0]["wait_time"], 500)

    def test_one_job_cannot_exceed_capacity(self):
        job = Job("A", "A", [Phase("communicate", 100, 100)])
        sim = self.run_jobs([job])
        self.assertEqual(sim.completed_jobs[0]["turnaround_time"], 200)

    def test_bandwidth_is_reallocated_when_a_job_finishes(self):
        a = Job("A", "A", [Phase("communicate", 100, 50)])
        b = Job("B", "B", [Phase("communicate", 200, 50)])
        sim = self.run_jobs([a, b])
        self.assertEqual([r["completion_time"] for r in sim.completed_jobs], [200, 300])

    def test_demand_caps_do_not_waste_spare_bandwidth(self):
        a = Job("A", "A", [Phase("communicate", 100, 10)])
        b = Job("B", "B", [Phase("communicate", 100, 50)])
        sim = self.run_jobs([a, b])
        self.assertAlmostEqual(sim.completed_jobs[0]["completion_time"], 100)
        self.assertAlmostEqual(sim.completed_jobs[1]["completion_time"], 120)

    def test_multiple_links_constrain_the_same_transfer(self):
        a = Job("A", "A", [Phase("communicate", 100, 50)])
        b = Job("B", "B", [Phase("communicate", 100, 50)])
        links = [Link("L1", 50), Link("L2", 25)]
        sim = self.run_jobs([a, b], links=links, routes={"L1": [a, b], "L2": [a]})
        self.assertEqual([r["completion_time"] for r in sim.completed_jobs], [200, 200])
        delivered = {jid: sum((r["end"] - r["start"]) * r["rate_gbps"]
                              for r in sim.phase_history if r["job_id"] == jid) for jid in ["A", "B"]}
        self.assertEqual(delivered, {"A": 5000, "B": 5000})

    def test_fractional_phase_times_are_executed(self):
        sim = self.run_jobs([make_job("A", compute=0.25, comm=0.125, iterations=3)])
        self.assertAlmostEqual(sim.completed_jobs[0]["completion_time"], 1.125)

    def test_arrival_at_completion_does_not_add_contention(self):
        sim = self.run_jobs([make_job("A"), make_job("B", arrival=100)])
        self.assertEqual([r["turnaround_time"] for r in sim.completed_jobs], [100, 100])

    def test_incoming_shift_preserves_incumbent_shift(self):
        a, b = make_job("A", shift=50), make_job("B")
        score, shift = eval_link_compatibility([a, b], Link("L", 50))
        self.assertEqual(a.time_shift, 50)
        self.assertEqual(shift, 0)
        self.assertEqual(score, 1)

    def test_invalid_jobs_are_rejected(self):
        sim = Simulator(Cluster([], [Link("L", 50)]))
        sim.add_job_arrival(make_job("A"))
        with self.assertRaises(ValueError):
            sim.add_job_arrival(make_job("A"))
        with self.assertRaises(ValueError):
            sim.add_job_arrival(make_job("B", iterations=0))



class TestWorkConservation(unittest.TestCase):
    def test_dynamic_jobs_preserve_work_and_respect_every_link(self):
        import random
        rng = random.Random(8)
        for policy in [False, True]:
            jobs = [make_job(str(i), arrival=3.5*i, iterations=4,
                             compute=rng.choice([10,20,30]), comm=10, demand=50)
                    for i in range(6)]
            routes = {"X":jobs[:3], "Y":jobs[2:]}
            sim = Simulator(Cluster([],[Link("X",50),Link("Y",35)],routes),
                            use_cassini=policy,record_history=True)
            for job in copy.deepcopy(jobs):
                sim.add_job_arrival(job)
            sim.run_simulation()
            self.assertEqual(len(sim.completed_jobs),len(jobs))
            for job in jobs:
                rows = [r for r in sim.phase_history if r["job_id"]==job.job_id]
                work = sum((r["end"]-r["start"])*r["rate_gbps"] for r in rows)
                self.assertAlmostEqual(work,2000)
                completed = next(r for r in sim.completed_jobs if r["job_id"]==job.job_id)
                self.assertAlmostEqual(sum(r["end"]-r["start"] for r in rows),completed["turnaround_time"])
            for row in sim.link_history:
                self.assertLessEqual(row["served_gbps"],row["capacity_gbps"]+1e-8)
            for lid in routes:
                expected = 2000*len(routes[lid])
                self.assertAlmostEqual(sim.link_totals[lid]["served_work_gbps_ms"],expected)

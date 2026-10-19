import copy
import random
import unittest
from unittest.mock import patch

from src.core.models import Cluster, Job, Link, Phase
from src.scheduler.evaluator import make_fixed_placement
from src.scheduler.simulator import Simulator


class TestFixedPlacement(unittest.TestCase):
    def test_map_is_reproducible_and_uses_its_own_rng(self):
        jobs = [Job(str(i), str(i), [Phase("compute", 20, 0)], arrival_time=i % 3)
                for i in range(20)]
        links = [Link("left", 50), Link("right", 50)]
        state = random.getstate()
        placement = make_fixed_placement(jobs, links, seed=42)
        self.assertEqual(random.getstate(), state)
        self.assertEqual(placement, make_fixed_placement(jobs[::-1], links[::-1], seed=42))
        self.assertNotEqual(placement, make_fixed_placement(jobs, links, seed=7))

    def test_pair_has_identical_routes_despite_different_completion_events(self):
        jobs = [Job(name, name, [Phase("compute", 10, 0), Phase("communicate", 10, 50)])
                for name in ("a", "b")]
        jobs.append(Job("c", "c", [Phase("compute", 20, 0)], arrival_time=25))
        placement = {"a": "left", "b": "left", "c": "right"}
        for incremental in (False, True):
            results = {}
            for enabled in (False, True):
                sim = Simulator(Cluster([], [Link("left", 50), Link("right", 50)]),
                                incremental=incremental, use_cassini=enabled,
                                fixed_placement=placement)
                for job in jobs:
                    sim.add_job_arrival(copy.deepcopy(job))
                with patch("src.scheduler.simulator.generate_mock_candidates",
                           side_effect=AssertionError("Fixed routes must not be randomized")):
                    sim.run_simulation()
                rows = {r["job_id"]: r for r in sim.completed_jobs}
                self.assertEqual({j: r["link_id"] for j, r in rows.items()}, placement)
                self.assertEqual(rows["a"]["completion_time"], 20 if enabled else 30)
                self.assertEqual(rows["b"]["shift_wait_ms"], 10 if enabled else 0)
                results[enabled] = rows
            # Job c arrives after a finishes only under Cassini. Its route
            # remains the same; current load cannot change the paired map.
            self.assertLess(results[True]["a"]["completion_time"], jobs[-1].arrival_time)
            self.assertGreater(results[False]["a"]["completion_time"], jobs[-1].arrival_time)

    def test_no_contention_gives_equal_results(self):
        for incremental in (False, True):
            results = []
            for enabled in (False, True):
                sim = Simulator(Cluster([], [Link("left", 50), Link("right", 50)]),
                                incremental=incremental, use_cassini=enabled,
                                fixed_placement={"a": "left", "b": "right"})
                for name in ("a", "b"):
                    sim.add_job_arrival(Job(name, name, [Phase("compute", 10, 0),
                                                          Phase("communicate", 10, 50)]))
                sim.run_simulation()
                results.append(sorted(sim.completed_jobs, key=lambda row: row["job_id"]))
            self.assertEqual(results[0], results[1])

    def test_invalid_maps_are_rejected_and_input_is_copied(self):
        cluster = Cluster([], [Link("left", 50)])
        with self.assertRaises(ValueError):
            Simulator(cluster, fixed_placement={"a": "missing"})
        sim = Simulator(cluster, fixed_placement={})
        with self.assertRaises(ValueError):
            sim.add_job_arrival(Job("a", "a", [Phase("compute", 20, 0)]))
        placement = {"a": "left"}
        sim = Simulator(cluster, fixed_placement=placement)
        placement["a"] = "missing"
        self.assertEqual(sim.fixed_placement, {"a": "left"})
        job = Job("a", "a", [Phase("compute", 20, 0)])
        for jobs, links in (([job, job], cluster.links), ([job], []),
                            ([job], [Link("left", 50), Link("left", 50)])):
            with self.assertRaises(ValueError):
                make_fixed_placement(jobs, links)

import unittest
from unittest.mock import patch

from src.core.models import Cluster, Job, Link, Phase
from src.scheduler.shift_policy import estimate_shift_change
from src.scheduler.simulator import Simulator


class TestShiftPolicy(unittest.TestCase):
    def test_estimate_counts_all_jobs_and_pending_waits(self):
        estimate = estimate_shift_change({"a": 100, "b": 200}, {"a": 30, "b": 40},
                                         {"b": 50}, current_score=0.5, proposed_score=1,
                                         penalty=1)
        self.assertEqual(estimate.keep_mean_ms, 260)
        self.assertEqual(estimate.change_mean_ms, 210)
        self.assertEqual(estimate.gain_ms, 50)
        self.assertEqual(estimate_shift_change({}, {}, {}, current_score=1,
                                              proposed_score=1, penalty=1).gain_ms, 0)

    def test_short_jobs_reject_wait_and_keep_the_correct_score(self):
        # Each job has 100 ms nominal work. Zero shifts give score .5 and
        # factor 1.125; a 50-ms offset gives perfect compatibility but costs
        # more than it saves in mean completion time.
        for incremental in (False, True):
            outcomes = {}
            for policy in ("compatibility", "benefit"):
                sim = self.run_pair(policy, incremental=incremental, iterations=1, penalty=0.25)
                outcomes[policy] = sim
            old = sorted(row["turnaround_time"] for row in outcomes["compatibility"].completed_jobs)
            new = outcomes["benefit"]
            self.assertEqual(old, [100, 150])
            self.assertEqual([row["turnaround_time"] for row in new.completed_jobs], [112.5, 112.5])
            self.assertTrue(all(row["shift_wait_ms"] == 0 for row in new.completed_jobs))
            self.assertTrue(all(row["shift_changes"] == 0 for row in new.completed_jobs))
            self.assertEqual(new.shift_stats, {"proposed": 1, "accepted": 0, "rejected": 1})

    def test_score_control_separates_score_retention_from_wait_cost(self):
        for incremental in (False, True):
            score = self.run_pair("score", incremental=incremental, penalty=0.25)
            benefit = self.run_pair("benefit", incremental=incremental, penalty=0.25)
            self.assertEqual(sorted(r["turnaround_time"] for r in score.completed_jobs), [100, 150])
            self.assertEqual(sorted(r["turnaround_time"] for r in benefit.completed_jobs), [112.5, 112.5])

    def test_long_jobs_accept_the_same_shift(self):
        for incremental in (False, True):
            old = self.run_pair("compatibility", incremental=incremental, iterations=10, penalty=0.25)
            new = self.run_pair("benefit", incremental=incremental, iterations=10, penalty=0.25)
            self.assertEqual(new.completed_jobs, old.completed_jobs)
            self.assertEqual(new.shift_stats["accepted"], 1)
            self.assertEqual(sorted(r["turnaround_time"] for r in new.completed_jobs), [1000, 1050])

    def test_margin_is_a_minimum_mean_gain(self):
        for incremental in (False, True):
            # At penalty=1, changing saves an estimated mean of 25 ms.
            accept = self.run_pair("benefit", incremental=incremental, penalty=1, min_gain_ms=24)
            reject = self.run_pair("benefit", incremental=incremental, penalty=1, min_gain_ms=25)
            self.assertEqual(accept.shift_stats["accepted"], 1)
            self.assertEqual(reject.shift_stats["rejected"], 1)
            self.assertEqual(sorted(r["turnaround_time"] for r in reject.completed_jobs), [150, 150])

    def test_cooldown_is_independent_of_the_benefit_rule(self):
        for incremental in (False, True):
            changed = False
            def plan(jobs, link, *args, **kwargs):
                nonlocal changed
                if len(jobs) < 2:
                    return
                changed = changed or any(j.job_id == "trigger" for j in jobs)
                for job in jobs:
                    job.time_shift = (70 if changed else 40) if job.job_id == "b" else 0
            sim = Simulator(Cluster([], [Link("link", 50)]), incremental=incremental,
                            fixed_placement={name: "link" for name in ("a", "b", "trigger")},
                            shift_policy="cooldown", cooldown_ms=100)
            for name in ("a", "b"):
                sim.add_job_arrival(Job(name, name, [Phase("compute", 100, 0)]))
            sim.add_job_arrival(Job("trigger", "trigger", [Phase("compute", 5, 0)], arrival_time=10))
            with patch("src.scheduler.simulator.optimize_link", side_effect=plan), \
                 patch("src.scheduler.evaluator.optimize_link", side_effect=plan):
                sim.run_simulation()
            rows = {r["job_id"]: r for r in sim.completed_jobs}
            self.assertEqual(rows["b"]["turnaround_time"], 140)
            self.assertEqual(rows["b"]["shift_wait_ms"], 40)
            self.assertEqual(rows["b"]["shift_changes"], 1)
            self.assertGreaterEqual(sim.shift_stats["rejected"], 1)

    def test_invalid_options(self):
        cluster = Cluster([], [Link("link", 50)])
        for kwargs in ({"shift_policy": "bad"}, {"shift_policy": "benefit"},
                       {"shift_policy": "cooldown"},
                       {"shift_policy": "benefit", "fixed_placement": {}, "use_cassini": False},
                       *({"min_gain_ms": n} for n in (-1, float("nan"), float("inf"))),
                       *({"cooldown_ms": n} for n in (-1, float("nan"), float("inf")))):
            with self.subTest(options=kwargs):
                with self.assertRaises(ValueError):
                    Simulator(cluster, **kwargs)

    @staticmethod
    def run_pair(policy, incremental=False, iterations=1, penalty=0.25, **kwargs):
        sim = Simulator(Cluster([], [Link("link", 50)]), penalty_factor=penalty,
                        incremental=incremental, fixed_placement={"a": "link", "b": "link"},
                        shift_policy=policy, **kwargs)
        for name in ("a", "b"):
            sim.add_job_arrival(Job(name, name, [Phase("compute", 50, 0),
                                                  Phase("communicate", 50, 50)],
                                    total_iterations=iterations))
        sim.run_simulation()
        return sim

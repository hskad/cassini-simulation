"""Check the analytical cases and reject invalid performance evidence."""
import copy
import contextlib
import io
import unittest

from src.benchmark import audit_run, benchmark_cases, run_benchmarks
from src.scheduler.simulator import Simulator


class TestBenchmarks(unittest.TestCase):
    def test_known_completion_times_include_startup_cost(self):
        for iterations in [1, 10]:
            with contextlib.redirect_stdout(io.StringIO()):
                rows, workloads, runs = run_benchmarks(iterations, [7])
            aligned = {row["policy"]: row for row in rows if row["case"] == "aligned-pair"}
            self.assertEqual(aligned["uncoordinated"]["mean_jct_ms"], 150 * iterations)
            self.assertEqual(aligned["cassini"]["mean_jct_ms"], 100 * iterations + 25)
            self.assertEqual(aligned["cassini"]["alignment_wait_ms"], 25)
            self.assertGreater(aligned["cassini"]["jct_reduction_percent"], 0)
            self.assertEqual(len(rows), 24)
            self.assertEqual(len(workloads), 8)
            self.assertEqual(len(runs), len(rows))
            for case in workloads:
                paired = [row for row in rows if row["case"] == case["case"]
                          and row["seed"] == case["seed"]]
                self.assertEqual({row["workload_sha256"] for row in paired}, {case["workload_sha256"]})

    def test_work_audit_rejects_missing_delivered_work(self):
        case = next(benchmark_cases(2, [0]))
        sim = Simulator(case.cluster, record_history=True)
        for job in copy.deepcopy(case.jobs):
            sim.add_job_arrival(job)
        sim.run_simulation()
        audit_run(case, sim)
        transfer = next(row for row in sim.phase_history if row["rate_gbps"] > 0)
        transfer["rate_gbps"] = 0
        with self.assertRaisesRegex(ValueError, "network work"):
            audit_run(case, sim)

    def test_empty_or_duplicate_seeds_are_rejected(self):
        for seeds in [[], [2, 2]]:
            with self.assertRaises(ValueError):
                list(benchmark_cases(10, seeds))

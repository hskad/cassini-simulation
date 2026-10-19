import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from experiments.remaining_work_experiment import run_sweep, summarize
from src.core.models import Cluster, Job, Link, Phase


class TestRemainingWorkExperiment(unittest.TestCase):
    def test_sweep_reuses_actual_jobs_and_saves_each_error_setting(self):
        jobs = [Job(name, name, [Phase("compute", 50, 0), Phase("communicate", 50, 50)])
                for name in ("a", "b")]
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()), \
             patch("experiments.shift_policy_experiment.build_workload",
                   return_value=(jobs, Cluster([], [Link("link", 50)]), True)):
            runs = run_sweep(["short"], [42], [0.5, 1, 1.5], output_dir=tmp)
            for scale in (0.5, 1, 1.5):
                saved = json.loads((Path(tmp) / f"scale-{scale:g}/short-seed42-compatibility.json").read_text())
                self.assertEqual(saved["remaining_work_scale"], scale)
                self.assertEqual(sorted(r["turnaround_time"] for r in saved["completions"]), [100, 150])
        self.assertEqual(len(runs), 6)
        self.assertEqual(len({row["input_sha256"] for row in runs}), 1)
        self.assertEqual(len({row["placement_sha256"] for row in runs}), 1)
        self.assertTrue(all(j.total_iterations == 1 and j.iteration_time == 100
                            and j.time_shift == 0 for j in jobs))

    def test_summary_keeps_seed_pairing_for_error_and_vanilla_comparisons(self):
        rows = []
        for seed, vanilla, accurate, biased in ((7, 100, 90, 90), (19, 200, 160, 140)):
            for scale, value in ((1, accurate), (0.5, biased)):
                rows.append(dict(workload="case", seed=seed, policy="benefit", jobs=2,
                                 remaining_work_scale=scale,
                                 mean_jct_gain_percent=100 * (vanilla - value) / vanilla,
                                 p95_jct_gain_percent=100 * (vanilla - value) / vanilla,
                                 mean_jct_change_vs_accurate_percent=100 * (value - accurate) / accurate,
                                 mean_wait_ms=1, shift_changes=1))
        low = summarize(rows)["case"][0]
        self.assertEqual(low["estimate_error_percent"], -50)
        self.assertEqual(low["mean_jct_gain_percent"], 20)
        self.assertEqual(low["min_mean_jct_gain_percent"], 10)
        self.assertEqual(low["max_mean_jct_gain_percent"], 30)
        self.assertEqual(low["mean_jct_change_vs_accurate_percent"], -6.25)

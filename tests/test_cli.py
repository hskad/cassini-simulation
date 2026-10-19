import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TestCommandLine(unittest.TestCase):
    def invoke(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "cassini.py"), *args],
                              cwd=ROOT, text=True, capture_output=True, timeout=60)

    def test_demo_saves_data_and_plots_and_clears_stale_history(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.invoke("demo", "--iterations", "3", "--out", folder)
            self.assertEqual(result.returncode, 0, result.stderr)
            out = Path(folder)
            rows = json.loads((out / "data" / "summary.json").read_text())
            self.assertEqual([r["mean_jct_ms"] for r in rows], [450, 325])
            for name in ["timeline.png", "bandwidth.png", "jct.png", "drift.png"]:
                self.assertGreater((out / "plots" / name).stat().st_size, 1000)
                self.assertFalse((out / name).exists())
            self.assertTrue((out / "data" / "cassini" / "phases.csv").is_file())
            self.assertEqual({p.name for p in out.iterdir()}, {"status.json", "data", "plots"})
            (out / "keep.txt").write_text("user file")
            (out / "plots" / "keep.txt").write_text("user plot note")
            # A repeated run also clears known files from the previous layout.
            (out / "timeline.png").write_text("old plot")
            (out / "summary.json").write_text("old summary")
            (out / "cassini").mkdir()
            (out / "cassini" / "phases.csv").write_text("old history")
            (out / "cassini" / "keep.txt").write_text("user policy note")
            result = self.invoke("demo", "--iterations", "3", "--no-history", "--out", folder)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((out / "timeline.png").exists())
            self.assertFalse((out / "summary.json").exists())
            self.assertFalse((out / "cassini" / "phases.csv").exists())
            self.assertFalse((out / "plots" / "timeline.png").exists())
            self.assertFalse((out / "data" / "cassini" / "phases.csv").exists())
            self.assertGreater((out / "plots" / "jct.png").stat().st_size, 1000)
            self.assertEqual((out / "keep.txt").read_text(), "user file")
            self.assertEqual((out / "plots" / "keep.txt").read_text(), "user plot note")
            self.assertEqual((out / "cassini" / "keep.txt").read_text(), "user policy note")
            self.assertEqual(json.loads((out / "status.json").read_text())["status"], "complete")
            before = (out / "data" / "summary.json").read_bytes()
            result = self.invoke("demo", "--iterations", "3", "--no-history", "--out", folder)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(before, (out / "data" / "summary.json").read_bytes())

    def test_invalid_input_has_nonzero_exit(self):
        result = self.invoke("demo", "--jitter", "1.5")
        self.assertEqual(result.returncode, 2)
        self.assertIn("jitter", result.stderr.lower())
        self.assertNotIn("Traceback", result.stderr)

    def test_benchmark_saves_all_cases_and_audit_results(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.invoke("benchmark", "--iterations", "3", "--seeds", "7", "--out", folder)
            self.assertEqual(result.returncode, 0, result.stderr)
            out = Path(folder)
            rows = json.loads((out / "data" / "summary.json").read_text())
            self.assertEqual(len(rows), 24)
            self.assertEqual(json.loads((out / "status.json").read_text())["validated_runs"], 24)
            self.assertTrue((out / "data" / "runs.json").is_file())
            self.assertGreater((out / "plots" / "benchmark.png").stat().st_size, 1000)
            self.assertIn("Negative reduction", result.stdout)

    def test_experiment_policies_use_the_saved_input_routes(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.invoke("experiment", "--jobs", "6", "--links", "2",
                "--iterations", "3", "--no-history", "--include-static", "--out", folder)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = Path(folder) / "data"
            parameters = json.loads((data / "parameters.json").read_text())
            expected = parameters["input_routes"]
            self.assertEqual(len(expected), 6)
            for policy in ["uncoordinated", "static-shifts", "cassini"]:
                self.assertEqual(json.loads((data / policy / "routes.json").read_text()), expected)

    def test_showcase_saves_synthetic_inputs_and_charges_waits(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.invoke("showcase", "--iterations", "3", "--no-history", "--out", folder)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = Path(folder) / "data"
            parameters = json.loads((data / "parameters.json").read_text())
            self.assertEqual(parameters["provenance"]["kind"], "synthetic")
            rows = json.loads((data / "summary.json").read_text())
            self.assertEqual([row["jobs"] for row in rows], [56, 56])
            self.assertLess(rows[1]["mean_jct_ms"], rows[0]["mean_jct_ms"])
            self.assertGreater(rows[1]["mean_wait_ms"], 0)
            for policy in ["uncoordinated", "cassini"]:
                self.assertEqual(json.loads((data / policy / "routes.json").read_text()), parameters["input_routes"])

    def test_python_entry_from_another_folder(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "cassini.py"), "--help"],
            cwd=ROOT.parent, text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("experiment", result.stdout)


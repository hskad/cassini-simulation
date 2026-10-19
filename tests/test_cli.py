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
            rows = json.loads((out / "summary.json").read_text())
            self.assertEqual([r["mean_jct_ms"] for r in rows], [450, 325])
            for name in ["timeline.png", "bandwidth.png", "jct.png", "drift.png"]:
                self.assertGreater((out / name).stat().st_size, 1000)
            (out / "keep.txt").write_text("user file")
            result = self.invoke("demo", "--iterations", "3", "--no-history", "--out", folder)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((out / "timeline.png").exists())
            self.assertFalse((out / "cassini" / "phases.csv").exists())
            self.assertEqual((out / "keep.txt").read_text(), "user file")
            self.assertEqual(json.loads((out / "status.json").read_text())["status"], "complete")
            before = (out / "summary.json").read_bytes()
            result = self.invoke("demo", "--iterations", "3", "--no-history", "--out", folder)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(before, (out / "summary.json").read_bytes())

    def test_invalid_input_has_nonzero_exit(self):
        result = self.invoke("demo", "--jitter", "1.5")
        self.assertEqual(result.returncode, 2)
        self.assertIn("jitter", result.stderr.lower())
        self.assertNotIn("Traceback", result.stderr)

    def test_python_entry_from_another_folder(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "cassini.py"), "--help"],
            cwd=ROOT.parent, text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("experiment", result.stdout)


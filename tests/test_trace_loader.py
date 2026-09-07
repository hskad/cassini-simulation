import unittest
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core.trace_loader import TraceLoader, ModelProfile
from src.core.models import Job

class TestTraceLoader(unittest.TestCase):
    def setUp(self):
        self.loader = TraceLoader()

    def test_load_models_catalog(self):
        self.assertIn("ResNet-50", self.loader.models)
        self.assertIn("VGG-16", self.loader.models)
        self.assertIn("BERT-Base", self.loader.models)
        self.assertIn("BERT-Large", self.loader.models)
        self.assertIn("GPT-2-Medium", self.loader.models)
        self.assertIn("ViT-Base", self.loader.models)
        self.assertIn("DLRM", self.loader.models)

        # Check VGG-16 values against NSDI '24 Fig 16
        vgg = self.loader.models["VGG-16"]
        self.assertEqual(vgg.compute_time_ms, 141.0)
        self.assertEqual(vgg.default_comm_time_ms, 114.0)
        self.assertEqual(vgg.default_bandwidth_gbps, 25.0)

    def test_bandwidth_scaling(self):
        vgg = self.loader.models["VGG-16"]
        # At 25 Gbps: 114ms
        self.assertEqual(vgg.get_comm_time(25.0), 114.0)
        # At 50 Gbps: should cut in half to 57ms
        self.assertAlmostEqual(vgg.get_comm_time(50.0), 57.0)
        # At 100 Gbps: 28.5ms
        self.assertAlmostEqual(vgg.get_comm_time(100.0), 28.5)

    def test_profile_to_job(self):
        resnet = self.loader.models["ResNet-50"]
        job = resnet.to_job(job_id="j_test", arrival_time=10.0, total_iterations=5, bandwidth_gbps=25.0)
        self.assertEqual(job.job_id, "j_test")
        self.assertEqual(job.name, "ResNet-50")
        self.assertEqual(job.arrival_time, 10.0)
        self.assertEqual(job.total_iterations, 5)
        self.assertEqual(len(job.phases), 2)
        self.assertEqual(job.phases[0].type, "compute")
        self.assertEqual(job.phases[0].duration, 82.0)
        self.assertEqual(job.phases[1].type, "communicate")
        self.assertEqual(job.phases[1].duration, 35.0)
        self.assertEqual(job.iteration_time, 117.0)

    def test_load_philly_trace(self):
        jobs = self.loader.load_trace(bandwidth_gbps=25.0, max_jobs=10)
        self.assertEqual(len(jobs), 10)
        self.assertEqual(jobs[0].job_id, "job_01")
        self.assertEqual(jobs[0].name, "ResNet-50")
        self.assertGreater(jobs[1].arrival_time, jobs[0].arrival_time)

    def test_generate_synthetic_philly_workload(self):
        jobs = self.loader.generate_synthetic_philly_workload(num_jobs=20, seed=42)
        self.assertEqual(len(jobs), 20)
        for job in jobs:
            self.assertIn(job.name, self.loader.models)
            self.assertGreater(job.iteration_time, 0)
            self.assertGreater(job.total_iterations, 0)

if __name__ == '__main__':
    unittest.main()

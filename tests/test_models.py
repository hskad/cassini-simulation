import unittest
import sys
import os

# Add parent directory to path so we can import src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.models import Phase, Job, Link, Server, Cluster

class TestModels(unittest.TestCase):
    def test_job_iteration_time(self):
        # Create a mock VGG16 job with a compute and communicate phase
        compute_phase = Phase(type="compute", duration=141.0, bandwidth_demand=0.0)
        comm_phase = Phase(type="communicate", duration=114.0, bandwidth_demand=25.0)
        
        job = Job(job_id="j1", name="VGG16", phases=[compute_phase, comm_phase])
        
        # 141 + 114 = 255 (From Figure 16 in the paper)
        self.assertEqual(job.iteration_time, 255.0)
        self.assertEqual(job.time_shift, 0.0)

    def test_cluster_topology(self):
        server1 = Server(server_id="s1", gpu_count=1)
        server2 = Server(server_id="s2", gpu_count=1)
        link1 = Link(link_id="l1", capacity=50.0)
        
        job1 = Job(job_id="j1", name="VGG16", phases=[
            Phase(type="compute", duration=141.0, bandwidth_demand=0.0),
            Phase(type="communicate", duration=114.0, bandwidth_demand=25.0)
        ])
        
        cluster = Cluster(servers=[server1, server2], links=[link1], link_jobs={"l1": [job1]})
        
        self.assertEqual(len(cluster.servers), 2)
        self.assertEqual(len(cluster.links), 1)
        self.assertIn("l1", cluster.link_jobs)
        self.assertEqual(cluster.link_jobs["l1"][0].job_id, "j1")

if __name__ == '__main__':
    unittest.main()

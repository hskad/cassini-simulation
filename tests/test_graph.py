import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.models import Phase, Job, Link, Cluster, Server
from src.graph import build_affinity_graph, traverse_affinity_graph, AffinityGraph

class TestGraph(unittest.TestCase):
    def test_affinity_graph_traversal(self):
        # Create jobs and links mimicking a simple multi-link setup
        job1 = Job("j1", "Job1", [Phase("compute", 100, 0)], iteration_time=100) # Mock time
        job2 = Job("j2", "Job2", [Phase("compute", 100, 0)], iteration_time=100)
        job3 = Job("j3", "Job3", [Phase("compute", 100, 0)], iteration_time=100)
        
        # We manually craft the AffinityGraph to test Algorithm 1 (BFS)
        # Graph structure: j1 - l1 - j2 - l2 - j3
        # Weights:
        # l1: j1=0, j2=30
        # l2: j2=0, j3=40
        
        graph = AffinityGraph()
        graph.add_edge("j1", "l1", 0.0)
        graph.add_edge("j2", "l1", 30.0)
        
        graph.add_edge("j2", "l2", 0.0)
        graph.add_edge("j3", "l2", 40.0)
        
        jobs_map = {"j1": job1, "j2": job2, "j3": job3}
        
        # Traverse
        global_shifts = traverse_affinity_graph(graph, jobs_map)
        
        # Let's say j1 is the root, so it gets 0.0
        # j2 shift: (tj1 - w(j1,l1) + w(l1,j2)) % 100 = (0 - 0 + 30) = 30.0
        # j3 shift: (tj2 - w(j2,l2) + w(l2,j3)) % 100 = (30 - 0 + 40) = 70.0
        
        # Note: Since the BFS starts from an arbitrary node in a set, the absolute shifts might differ
        # But the relative difference must be correct.
        
        # Let's verify relative differences
        diff_j2_j1 = (global_shifts["j2"] - global_shifts["j1"]) % 100
        self.assertEqual(diff_j2_j1, 30.0)
        
        diff_j3_j2 = (global_shifts["j3"] - global_shifts["j2"]) % 100
        self.assertEqual(diff_j3_j2, 40.0)

if __name__ == '__main__':
    unittest.main()

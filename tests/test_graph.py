import unittest
import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core.models import Phase, Job, Link, Cluster, Server
from src.math_engine.graph import build_affinity_graph, traverse_affinity_graph, AffinityGraph, has_cycle

class TestGraph(unittest.TestCase):
    def test_affinity_graph_traversal(self):
        # Create jobs and links mimicking a simple multi-link setup
        job1 = Job("j1", "Job1", [Phase("compute", 100, 0)]) # Mock time
        job2 = Job("j2", "Job2", [Phase("compute", 100, 0)])
        job3 = Job("j3", "Job3", [Phase("compute", 100, 0)])
        
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
        
        # Placement order chooses the reference deterministically, so waiting
        # costs cannot change with Python's randomized string hashes.
        self.assertEqual(global_shifts, {"j1": 0.0, "j2": 30.0, "j3": 70.0})
        
        # Let's verify relative differences
        diff_j2_j1 = (global_shifts["j2"] - global_shifts["j1"]) % 100
        self.assertEqual(diff_j2_j1, 30.0)
        
        diff_j3_j2 = (global_shifts["j3"] - global_shifts["j2"]) % 100
        self.assertEqual(diff_j3_j2, 40.0)

    def test_cyclic_input_is_rejected(self):
        graph = AffinityGraph()
        jobs = {name: Job(name, name, [Phase("compute", 100, 0)]) for name in ("a", "b")}
        for job, link, weight in (("a", "x", 0), ("b", "x", 10),
                                  ("a", "y", 0), ("b", "y", 20)):
            graph.add_edge(job, link, weight)
        self.assertTrue(has_cycle(graph))
        with self.assertRaisesRegex(ValueError, "acyclic"):
            traverse_affinity_graph(graph, jobs)
        from src.utils.graph_animator import trace_bfs
        with self.assertRaisesRegex(ValueError, "acyclic"):
            list(trace_bfs(graph, jobs))

    def test_job_and_link_ids_have_separate_identities(self):
        graph = AffinityGraph()
        graph.add_edge("a", "b", 10)
        graph.add_edge("b", "a", 20)
        graph.add_edge("b", "b", 30)
        jobs = {name: Job(name, name, [Phase("compute", 100, 0)]) for name in ("a", "b")}
        self.assertFalse(has_cycle(graph))
        self.assertEqual(graph.weights[("a", "b")], 10)
        self.assertEqual(graph.weights[("b", "a")], 20)
        self.assertEqual(traverse_affinity_graph(graph, jobs), {"a": 0, "b": 20})
        graph.add_edge("a", "a", 0)
        self.assertTrue(has_cycle(graph))

    def test_disconnected_forest_and_missing_job(self):
        graph = AffinityGraph()
        for job, link in (("a", "x"), ("b", "x"), ("c", "y"), ("d", "y")):
            graph.add_edge(job, link, 10 if job in ("b", "d") else 0)
        jobs = {name: Job(name, name, [Phase("compute", 100, 0)]) for name in "abcde"}
        self.assertFalse(has_cycle(graph))
        self.assertEqual(traverse_affinity_graph(graph, jobs), {"a": 0, "b": 10, "c": 0, "d": 10})
        with self.assertRaisesRegex(ValueError, "every job"):
            traverse_affinity_graph(graph, {})

    def test_duplicate_edge_is_rejected(self):
        graph = AffinityGraph()
        graph.add_edge("a", "x", 10)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            graph.add_edge("a", "x", 20)

    def test_demo_and_animation_use_a_valid_shift_plan(self):
        from examples.affinity_scenario import build_demo_scenario
        from src.utils.graph_animator import trace_bfs
        graph, jobs = build_demo_scenario()
        self.assertFalse(has_cycle(graph))
        shifts = traverse_affinity_graph(graph, jobs)
        self.assertEqual(shifts, {"j1": 0, "j2": 10, "j3": 20, "j4": 40, "j5": 60})
        # Every pair sharing each link must retain its prescribed difference.
        for link, members in graph.edges_V_to_U.items():
            for a in members:
                for b in members:
                    self.assertEqual((shifts[b] - shifts[a]) % 100,
                                     (graph.weights[(b, link)] - graph.weights[(a, link)]) % 100)
        final = list(trace_bfs(graph, jobs))[-1]
        self.assertEqual(final[0], graph.U)
        self.assertEqual(final[1], graph.V)
        self.assertEqual(final[4], shifts)

if __name__ == '__main__':
    unittest.main()

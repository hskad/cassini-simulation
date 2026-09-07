import unittest
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core.models import Phase, Job, Link, Cluster
from src.math_engine.graph import AffinityGraph
from src.scheduler.evaluator import has_cycle, PlacementCandidate, generate_mock_candidates, evaluate_placements

class TestEvaluator(unittest.TestCase):
    def test_has_cycle(self):
        graph = AffinityGraph()
        # Create a simple line: j1 - l1 - j2 - l2 - j3
        graph.add_edge("j1", "l1")
        graph.add_edge("j2", "l1")
        graph.add_edge("j2", "l2")
        graph.add_edge("j3", "l2")
        self.assertFalse(has_cycle(graph))
        
        # Create a cycle: j3 - l3 - j1
        graph.add_edge("j3", "l3")
        graph.add_edge("j1", "l3")
        self.assertTrue(has_cycle(graph))
        
    def test_generate_mock_candidates(self):
        job1 = Job("j1", "test", [Phase("compute", 10, 0)])
        link1 = Link("l1", 50)
        cluster = Cluster([], [link1])
        
        candidates = generate_mock_candidates(cluster, [job1], num_candidates=3)
        self.assertEqual(len(candidates), 3)
        
    def test_evaluate_placements(self):
        # A simple scenario where 2 jobs on 1 link have a score, but 2 jobs on separate links have a better score.
        job1 = Job("j1", "test1", [Phase("compute", 10, 50), Phase("communicate", 10, 50)])
        job2 = Job("j2", "test2", [Phase("compute", 10, 50), Phase("communicate", 10, 50)])
        
        link1 = Link("l1", 50)
        link2 = Link("l2", 50)
        
        # Candidate 1: Both on link 1
        c1 = PlacementCandidate("c1", Cluster([], [link1, link2], {"l1": [job1, job2], "l2": []}))
        
        # Candidate 2: Separate links (perfect score)
        c2 = PlacementCandidate("c2", Cluster([], [link1, link2], {"l1": [job1], "l2": [job2]}))
        
        winning_candidate, shifts = evaluate_placements([c1, c2])
        
        # c2 should win because there are no collisions
        self.assertEqual(winning_candidate.candidate_id, "c2")
        self.assertEqual(winning_candidate.compatibility_score, 1.0)
        
if __name__ == '__main__':
    unittest.main()

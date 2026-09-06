import unittest
from src.models import Phase, Job, Link, Cluster
from src.simulator import Simulator, Event

class TestSimulator(unittest.TestCase):
    def test_simulator_single_job(self):
        job = Job(job_id="j1", name="test_job", phases=[Phase("compute", 100, 0)], arrival_time=0.0, total_iterations=5)
        link = Link("l1", 50)
        cluster = Cluster([], [link])
        
        sim = Simulator(cluster)
        sim.add_job_arrival(job)
        sim.run_simulation()
        
        self.assertEqual(len(sim.completed_jobs), 1)
        completed = sim.completed_jobs[0]
        self.assertEqual(completed["job_id"], "j1")
        # 5 iterations of 100ms each = 500ms
        self.assertAlmostEqual(completed["turnaround_time"], 500.0)
        
    def test_simulator_two_jobs(self):
        # Two jobs that can't fit on the same link (50+50 > 50 link capacity)
        # They will be forced onto separate links by the mock evaluator (since there are 2 links available)
        job1 = Job("j1", "test_job1", phases=[Phase("compute", 100, 50)], arrival_time=0.0, total_iterations=10)
        job2 = Job("j2", "test_job2", phases=[Phase("compute", 100, 50)], arrival_time=100.0, total_iterations=5)
        
        link1 = Link("l1", 50)
        link2 = Link("l2", 50)
        cluster = Cluster([], [link1, link2])
        
        sim = Simulator(cluster)
        sim.add_job_arrival(job1)
        sim.add_job_arrival(job2)
        sim.run_simulation()
        
        self.assertEqual(len(sim.completed_jobs), 2)

if __name__ == '__main__':
    unittest.main()

from src.core.models import Phase, Job, Link, Cluster
from src.scheduler.evaluator import generate_mock_candidates, evaluate_placements

def main():
    print("--- CASSINI Placement Evaluator Demo ---")
    
    # 1. Setup Jobs and Cluster
    job1 = Job(job_id="j1", name="VGG16", phases=[Phase("compute", 100, 20), Phase("communicate", 50, 40)])
    job2 = Job(job_id="j2", name="ResNet50", phases=[Phase("compute", 80, 10), Phase("communicate", 40, 30)])
    job3 = Job(job_id="j3", name="GPT2", phases=[Phase("compute", 120, 25), Phase("communicate", 60, 45)])
    
    link1 = Link(link_id="l1", capacity=50)
    link2 = Link(link_id="l2", capacity=50)
    link3 = Link(link_id="l3", capacity=50)
    
    cluster = Cluster(servers=[], links=[link1, link2, link3])
    
    print("\nGenerating Mock Candidates...")
    candidates = generate_mock_candidates(cluster, [job1, job2, job3], num_candidates=5)
    
    for c in candidates:
        print(f"\n{c.candidate_id}:")
        for link_id, jobs in c.cluster.link_jobs.items():
            job_names = [j.name for j in jobs]
            print(f"  Link {link_id}: {job_names}")
            
    print("\nEvaluating Placements...")
    winning_candidate, global_shifts = evaluate_placements(candidates)
    
    print(f"\nWINNING CANDIDATE: {winning_candidate.candidate_id}")
    print(f"Score: {winning_candidate.compatibility_score:.4f}")
    print("Placement:")
    for link_id, jobs in winning_candidate.cluster.link_jobs.items():
        job_names = [j.name for j in jobs]
        print(f"  Link {link_id}: {job_names}")
    
    print("\nGlobal Time-Shifts applied:")
    for jid, shift in global_shifts.items():
        print(f"  Job {jid}: delayed by {shift}ms")
        
if __name__ == '__main__':
    main()

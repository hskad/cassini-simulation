"""Synthetic workload figures in the repository's cyan and magenta style."""
import copy
import hashlib
import json
import random
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src.core.models import Cluster, Link
from src.core.trace_loader import TraceLoader
from src.scheduler.simulator import Simulator
from src.visualization.plot_style import (POLICY_COLORS, CYAN, MAGENTA, TEXT, MUTED,
                                  dark_figure)


@dark_figure
def build_workload_figures(out):
    loader = TraceLoader()
    rng = random.Random(42)
    names = list(loader.models)*8
    rng.shuffle(names)
    jobs = [loader.models[name].to_job(
        f"sample-{i+1:03}", arrival_time=round(rng.uniform(0, 7000), 3),
        total_iterations=rng.randint(12, 40), bandwidth_gbps=50)
        for i,name in enumerate(names)]
    links = [Link(f"L{i+1}", 50) for i in range(6)]
    routes = {link.link_id: [] for link in links}
    for index,job in enumerate(sorted(jobs, key=lambda j: (j.arrival_time, j.job_id))):
        routes[links[index % len(links)].link_id].append(job)
    cluster = Cluster([],links,routes)
    simulations, summaries, per_model = {}, {}, {}
    for name, enabled in [("uncoordinated",False),("cassini",True)]:
        print(f"Building 56-job workload: {name}...",flush=True)
        sim = Simulator(cluster,use_cassini=enabled,record_history=False,
                        solver="greedy",score_horizon=2000,seed=42)
        for job in copy.deepcopy(jobs):
            sim.add_job_arrival(job)
        sim.run_simulation()
        assert len(sim.completed_jobs) == len(jobs)
        for link in links:
            expected = sum(j.total_iterations*sum(p.duration*p.bandwidth_demand for p in j.phases)
                           for j in routes[link.link_id])
            assert np.isclose(sim.link_totals[link.link_id]["served_work_gbps_ms"],expected)
        simulations[name] = sim
        times = [row["turnaround_time"] for row in sim.completed_jobs]
        summaries[name] = {"mean_jct_ms":float(np.mean(times)),
                           "p95_jct_ms":float(np.percentile(times,95)),
                           "mean_wait_ms":float(np.mean([r["wait_time"] for r in sim.completed_jobs])),
                           "adjustments":len(sim.adjustments)}
        per_model[name] = {model:float(np.mean([r["turnaround_time"] for r in sim.completed_jobs
                                               if r["name"] == model])) for model in loader.models}
    assert simulations["uncoordinated"].job_to_links == simulations["cassini"].job_to_links

    fig, ax = plt.subplots(figsize=(11,6.4))
    fig.subplots_adjust(left=0.11,right=0.97,bottom=0.13,top=0.80)
    fig.text(0.065,0.94,"SYNTHETIC WORKLOAD  |  COMPLETION TIME",fontsize=17,weight="bold")
    fig.text(0.065,0.885,"56 jobs / 7 illustrative profiles / 6 links / seed 42",
             fontsize=11,color=MUTED)
    for name,sim in simulations.items():
        seconds=np.sort([r["turnaround_time"]/1000 for r in sim.completed_jobs])
        probability=np.arange(1,len(seconds)+1)/len(seconds)
        label=(f"{name}  |  mean {summaries[name]['mean_jct_ms']/1000:.2f} s"
               f"  |  P95 {summaries[name]['p95_jct_ms']/1000:.2f} s")
        ax.step(np.r_[0,seconds],np.r_[0,probability],where="post",
                color=POLICY_COLORS[name],linestyle="--" if name=="uncoordinated" else "-",
                linewidth=2.8,label=label)
    ax.set(xlabel="Job completion time (seconds)",ylabel="Cumulative fraction of jobs",
           ylim=(0,1.04),xlim=(0,None))
    ax.grid(linestyle=":",alpha=0.65)
    ax.legend(loc="lower right",fontsize=10)
    fig.savefig(out/"workload-cdf.png",dpi=160)
    plt.close(fig)

    models=sorted(loader.models,key=lambda model:per_model["uncoordinated"][model])
    y=np.arange(len(models))
    fig,ax=plt.subplots(figsize=(11,6.4))
    fig.subplots_adjust(left=0.19,right=0.97,bottom=0.13,top=0.77)
    fig.text(0.065,0.94,"MEAN COMPLETION TIME  |  BY MODEL PROFILE",fontsize=17,weight="bold")
    fig.text(0.065,0.885,"Eight synthetic jobs per profile / labels show JCT reduction",
             fontsize=11,color=MUTED)
    for index,name in enumerate(simulations):
        values=[per_model[name][model]/1000 for model in models]
        ax.barh(y+(-0.18 if index==0 else 0.18),values,height=0.33,
                color=POLICY_COLORS[name],label=name,alpha=0.9)
    maximum=max(value for values in per_model.values() for value in values.values())/1000
    for index,model in enumerate(models):
        baseline=per_model["uncoordinated"][model]
        cassini=per_model["cassini"][model]
        reduction=100*(baseline-cassini)/baseline
        end=max(baseline,cassini)/1000
        ax.text(end+maximum*0.025,index,f"{reduction:+.1f}%",va="center",fontsize=10,
                color=CYAN if reduction>=0 else MAGENTA,weight="bold")
    ax.set(yticks=y,yticklabels=models,xlabel="Mean job completion time (seconds)",
           xlim=(0,maximum*1.23))
    ax.grid(axis="x",linestyle=":",alpha=0.45)
    fig.legend(*ax.get_legend_handles_labels(),loc="upper right",
               bbox_to_anchor=(0.97,0.87),ncol=2,fontsize=10)
    fig.savefig(out/"model-breakdown.png",dpi=160)
    plt.close(fig)
    snapshot={"jobs":[asdict(job) for job in jobs],
              "routes":{lid:[j.job_id for j in members] for lid,members in routes.items()}}
    return {"kind":"synthetic","jobs":len(jobs),"links":6,"capacity_gbps":50,
            "seed":42,"compute_jitter":0,"arrival_span_ms":7000,"iteration_range":[12,40],
            "solver":"greedy","score_horizon_ms":2000,"resolution_ms":1,
            "routing":"fixed before either policy runs; identical across policies",
            "profile_source":"data/models/real_models.json; source limits apply",
            "model_counts":dict(Counter(job.name for job in jobs)),
            "workload_sha256":hashlib.sha256(json.dumps(snapshot,sort_keys=True).encode()).hexdigest(),
            "summaries":summaries,"mean_jct_ms_by_model":per_model}

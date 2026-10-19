"""Plots from measured simulator events. Display limits do not change execution."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np

COLORS = {"compute": "#3677B5", "communicate": "#DD8841", "wait": "#B6B9BE"}


def _save(fig, path):
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def plot_comparison(simulations, out, window=600, max_jobs=8):
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False})
    names = list(simulations)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), layout="constrained")
    for name, sim in simulations.items():
        values = np.sort([r["turnaround_time"] for r in sim.completed_jobs])
        axes[0].step(np.r_[values[0], values], np.r_[0, np.arange(1, len(values)+1) / len(values)], where="post", label=name)
    axes[0].set(xlabel="Job completion time (ms)", ylabel="Cumulative fraction of jobs",
                title="Completion time includes all waits", ylim=(0, 1.05))
    axes[0].legend()
    waits = [np.mean([r["wait_time"] for r in sim.completed_jobs]) for sim in simulations.values()]
    axes[1].bar(names, waits, color=["#3677B5", "#DD8841", "#4A8A61"][:len(names)])
    axes[1].set(ylabel="Mean waiting time per job (ms)", title="Cost of alignment and correction")
    axes[1].tick_params(axis="x", labelsize=9)
    for ax in axes:
        ax.grid(axis="y", alpha=0.2)
    _save(fig, out / "jct.png")
    if not any(sim.phase_history for sim in simulations.values()):
        return

    all_jobs = {}
    for sim in simulations.values():
        for row in sim.completed_jobs:
            all_jobs[row["job_id"]] = row["arrival_time"]
    jobs = sorted(all_jobs, key=lambda j: (all_jobs[j], j))[:max_jobs]
    start = min(all_jobs.values())
    stop = min(start + window, max(sim.current_time for sim in simulations.values()))
    if stop <= start:
        stop = start + window
    fig, axes = plt.subplots(len(names), 1, figsize=(12, max(4, len(names) * (1.5 + len(jobs)*0.25))),
                             sharex=True, layout="constrained", squeeze=False)
    for ax, (name, sim) in zip(axes[:, 0], simulations.items()):
        for row in sim.phase_history:
            if row["job_id"] not in jobs or row["end"] <= start or row["start"] >= stop:
                continue
            left, right = max(start, row["start"]), min(stop, row["end"])
            color = COLORS.get(row["type"], "#DD8841")
            ax.broken_barh([(left, right-left)], (jobs.index(row["job_id"])-0.3, 0.6),
                          facecolors=color, edgecolors="white", linewidth=0.3)
        ax.set(yticks=range(len(jobs)), yticklabels=jobs, title=name, xlim=(start, stop))
        ax.invert_yaxis()
        ax.grid(axis="x", alpha=0.15)
    axes[-1, 0].set_xlabel("Time (ms)")
    fig.suptitle(f"Executed phases and waits | first {len(jobs)} jobs")
    handles = [Patch(color=color, label=kind) for kind, color in COLORS.items()]
    fig.legend(handles=handles, loc="outside lower center", ncol=3, fontsize=9)
    _save(fig, out / "timeline.png")

    # Show the same link under all policies.
    first = next(iter(simulations.values()))
    if first.link_totals:
        lid = max(first.link_totals, key=lambda l: first.link_totals[l]["served_work_gbps_ms"])
        fig, axes = plt.subplots(len(names), 1, figsize=(12, 2.5*len(names)), sharex=True, sharey=True,
                                 layout="constrained", squeeze=False)
        for ax, (name, sim) in zip(axes[:, 0], simulations.items()):
            rows = [r for r in sim.link_history if r["link_id"] == lid
                    and r["end"] > start and r["start"] < stop]
            xs, demand, served = [], [], []
            for row in rows:
                xs.extend([max(start, row["start"]), min(stop, row["end"])])
                demand.extend([row["demand_gbps"]]*2)
                served.extend([row["served_gbps"]]*2)
            ax.plot(xs, demand, "--", color="#C85050", label="Requested")
            ax.plot(xs, served, color="#3677B5", label="Served")
            ax.axhline(first.capacities[lid], linestyle=":", color="#222222", label="Capacity")
            ax.set(title=name, ylabel="Bandwidth (Gbps)", xlim=(start, stop), ylim=(0, None))
            ax.grid(alpha=0.15)
        axes[0, 0].legend(loc="upper right", ncol=3, fontsize=8)
        axes[-1, 0].set_xlabel("Time (ms)")
        fig.suptitle(f"Requested and served bandwidth | link {lid}")
        _save(fig, out / "bandwidth.png")

    fig, axes = plt.subplots(len(names), 1, figsize=(12, 2.5*len(names)), sharex=True,
                             layout="constrained", squeeze=False)
    for ax, (name, sim) in zip(axes[:, 0], simulations.items()):
        for jid in jobs:
            rows = [r for r in sim.drift_history if r["job_id"] == jid
                    and start <= r["time"] <= stop]
            if rows:
                ax.plot([r["time"] for r in rows],
                        [100*r["phase_error_ms"]/r["period_ms"] for r in rows],
                        ".-", markersize=4, label=jid)
        if sim.drift_threshold is not None:
            for sign in [-1, 1]:
                ax.axhline(sign * 100 * sim.drift_threshold, color="#555555", linestyle=":", linewidth=1)
        adjustments = [r for r in sim.adjustments if start <= r["time"] <= stop]
        if adjustments:
            ax.scatter([r["time"] for r in adjustments],
                       [100*r["phase_error_ms"]/r["period_ms"] for r in adjustments],
                       marker="x", color="black", s=45, zorder=5, label="Correction")
        ax.set(title=name, ylabel="Phase error (%)", xlim=(start, stop))
        ax.grid(alpha=0.15)
        if ax.get_legend_handles_labels()[0]:
            ax.legend(loc="upper right", fontsize=8, ncol=min(5, len(jobs)+1))
    axes[-1, 0].set_xlabel("Time (ms)")
    fig.suptitle("Communication start error | percent of nominal iteration time")
    _save(fig, out / "drift.png")


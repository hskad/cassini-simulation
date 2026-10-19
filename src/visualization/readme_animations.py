"""Dark geometric rotation and BFS animations driven by calculated shifts."""
import copy
from collections import deque

import matplotlib
matplotlib.use("Agg")
import matplotlib.animation as animation
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import networkx as nx
import numpy as np

from src.core.models import Cluster, Job, Link, Phase
from src.math_engine.graph import build_affinity_graph, traverse_affinity_graph
from src.math_engine.optimizer import discretize_phases, optimize_link, score_link, hyperperiod
from src.scheduler.evaluator import PlacementCandidate, score_candidate
from src.visualization.plot_style import (BACKGROUND, PANEL, TEXT, MUTED, CYAN, MAGENTA,
                                  YELLOW, GRID, dark_figure)


def _area_vertices(x, top, bottom):
    return np.column_stack((np.r_[x, x[::-1]], np.r_[top, np.broadcast_to(bottom, top.shape)[::-1]]))


@dark_figure
def geometric_animation(filename):
    jobs = [Job(name, name, [Phase("compute", 141, 0), Phase("communicate", 114, 50)])
            for name in ["A", "B"]]
    link = Link("L1", 50)
    period = hyperperiod(jobs)
    initial_score = score_link(jobs, link)
    optimize_link(jobs, link, resolution=1, method="exact")
    target = jobs[1].time_shift
    final_score = score_link(jobs, link)
    x = np.arange(0, period, 0.5)
    theta = x / period * 2*np.pi
    first = np.array(discretize_phases(jobs[0], period, 0.5))
    jobs[1].time_shift = 0
    second = np.array(discretize_phases(jobs[1], period, 0.5))
    fig = plt.figure(figsize=(10.5, 6.3))
    fig.text(0.055, 0.935, "CASSINI  |  GEOMETRIC ALIGNMENT", fontsize=17, weight="bold")
    fig.text(0.055, 0.885, "Rotate one profile to separate communication bursts.",
             fontsize=11, color=MUTED)
    polar = fig.add_axes([0.035, 0.17, 0.51, 0.65], projection="polar")
    polar.set_theta_zero_location("N")
    polar.set_theta_direction(-1)
    polar.set_ylim(0, 1.05)
    polar.set_yticks([])
    polar.set_xticks(np.linspace(0, 2*np.pi, 8, endpoint=False))
    polar.set_xticklabels([f"{t:g} ms" for t in np.arange(8)*period/8], fontsize=9)
    polar.grid(color=GRID, alpha=0.6, linestyle=":")
    polar.spines["polar"].set_color(MUTED)
    polar.fill_between(theta, 0, first/50, color=CYAN, alpha=0.67)
    moving = polar.fill_between(theta, 0, second/50, color=MAGENTA, alpha=0.62)
    polar.plot(np.linspace(0, 2*np.pi, 200), np.ones(200), color=TEXT, alpha=0.6,
               linewidth=1, linestyle="--")
    fig.text(0.62, 0.79, "COMPATIBILITY", fontsize=10, color=MUTED, weight="bold")
    score_text = fig.text(0.62, 0.70, "", fontsize=31, weight="bold")
    shift_text = fig.text(0.62, 0.62, "", fontsize=12)
    fig.text(0.62, 0.565, f"Period: {period:g} ms   |   Link: 50 Gbps", fontsize=10, color=MUTED)
    demand_ax = fig.add_axes([0.62, 0.22, 0.335, 0.235], facecolor=PANEL)
    total = first + second
    demand_line, = demand_ax.plot(x, total, color=YELLOW, drawstyle="steps-post")
    excess = demand_ax.fill_between(x, 50, np.maximum(total, 50), color=MAGENTA, alpha=0.3)
    demand_ax.axhline(50, color=TEXT, linestyle="--", linewidth=1.2)
    demand_ax.set(xlim=(0, period), ylim=(0, 110), xticks=[0, 127.5, 255], yticks=[0, 50, 100],
                  xlabel="Time in period (ms)", ylabel="Gbps", title="Total requested bandwidth")
    demand_ax.tick_params(labelsize=9)
    demand_ax.set_title("Total requested bandwidth", fontsize=10)
    demand_ax.grid(alpha=0.3)
    fig.legend(handles=[Patch(color=CYAN, label="Job A communication"),
                        Patch(color=MAGENTA, label="Job B communication"),
                        Patch(color=YELLOW, label="Combined demand")],
               loc="lower center", ncol=3, frameon=False, fontsize=10, bbox_to_anchor=(0.5, 0.08))
    fig.text(0.5, 0.035, "Periodic profiles  |  Full-period score  |  Computed offset",
             color=MUTED, fontsize=9, ha="center")

    def update(shift):
        jobs[1].time_shift = float(shift)
        second = np.array(discretize_phases(jobs[1], period, 0.5))
        moving.set_verts([_area_vertices(theta, second/50, np.zeros_like(second))])
        total = first + second
        demand_line.set_ydata(total)
        excess.set_verts([_area_vertices(x, np.maximum(total, 50), np.full_like(total, 50))])
        score = score_link(jobs, link)
        score_text.set_text(f"{100*score:.1f}%")
        score_text.set_color(CYAN if score >= 1-1e-9 else MAGENTA)
        shift_text.set_text(f"Shift B: {shift:.1f} ms  |  {360*shift/period:.1f} degrees")

    frames = [0.0]*5 + list(np.linspace(0, target, 43)) + [target]*20
    clip = animation.FuncAnimation(fig, update, frames=frames, interval=1000/12)
    clip.save(filename, writer=animation.PillowWriter(fps=12), dpi=110)
    plt.close(fig)
    return {"compute_ms": 141, "communication_ms": 114, "period_ms": period,
            "capacity_gbps": 50, "shift_b_ms": target,
            "score_before": initial_score, "score_after": final_score}


def _trace(graph, jobs):
    assigned, visited_links = {}, set()
    def snapshot(node=None, edge=None, message=""):
        return dict(assigned=assigned.copy(), links=visited_links.copy(),
                    node=node, edge=edge, message=message)
    yield snapshot(message="Jobs are circles. Shared links are squares.")
    for root in sorted(graph.U):
        if root in assigned:
            continue
        assigned[root] = 0.0
        queue = deque([root])
        yield snapshot(("job", root), message=f"Choose {root} as the reference: 0 ms.")
        while queue:
            current = queue.popleft()
            for lid in graph.edges_U_to_V[current]:
                if lid in visited_links:
                    continue
                visited_links.add(lid)
                yield snapshot(("link", lid), (current, lid), f"Follow {current} to shared link {lid}.")
                for neighbor in graph.edges_V_to_U[lid]:
                    if neighbor in assigned:
                        continue
                    left, right = graph.weights[(current, lid)], graph.weights[(neighbor, lid)]
                    period = jobs[neighbor].iteration_time
                    assigned[neighbor] = (assigned[current]-left+right) % period
                    queue.append(neighbor)
                    message = (f"{neighbor}: ({assigned[current]:g} - {left:g} + {right:g}) "
                               f"mod {period:g} = {assigned[neighbor]:g} ms")
                    yield snapshot(("job", neighbor), (neighbor, lid), message)
    assert assigned == traverse_affinity_graph(graph, jobs)
    yield snapshot(message="All jobs now have one consistent shift across their shared links.")


@dark_figure
def affinity_animation(filename):
    jobs = [Job(f"j{i}", f"j{i}", [Phase("compute", 80, 0), Phase("communicate", 20, 50)])
            for i in range(1, 6)]
    cluster = Cluster([], [Link(f"L{i}", 50) for i in range(1, 4)],
                      {"L1": jobs[:3], "L2": [jobs[1], jobs[3]], "L3": [jobs[2], jobs[4]]})
    score, weights = score_candidate(PlacementCandidate("tree", cluster), solver="exact")
    graph = build_affinity_graph(cluster, weights)
    jobs_map = {j.job_id: j for j in jobs}
    shifts = traverse_affinity_graph(graph, jobs_map)
    planned = {jid: copy.copy(job) for jid, job in jobs_map.items()}
    for jid, job in planned.items():
        job.time_shift = shifts[jid]
    for link in cluster.links:
        assert abs(score_link([planned[j.job_id] for j in cluster.link_jobs[link.link_id]], link)-1) < 1e-9
    fig, ax = plt.subplots(figsize=(10.5, 6))
    fig.subplots_adjust(left=0.04, right=0.96, top=0.83, bottom=0.20)
    fig.text(0.055, 0.935, "CASSINI  |  AFFINITY GRAPH TRAVERSAL", fontsize=17, weight="bold")
    fig.text(0.055, 0.88, "Five jobs. Three shared links. One global shift per job.",
             fontsize=11, color=MUTED)
    network = nx.Graph()
    job_nodes = [("job", jid) for jid in sorted(graph.U)]
    link_nodes = [("link", lid) for lid in sorted(graph.V)]
    positions = {node: (i, 1.0) for i, node in enumerate(job_nodes)}
    positions.update({node: (x, 0.0) for node, x in zip(link_nodes, [0.5, 2, 3.5])})
    edges = []
    for jid in sorted(graph.U):
        for lid in graph.edges_U_to_V[jid]:
            edge = (("job", jid), ("link", lid))
            network.add_edge(*edge)
            edges.append(edge)
    lines = nx.draw_networkx_edges(network, positions, edgelist=edges, edge_color=GRID, width=1.4, ax=ax)
    job_marks = nx.draw_networkx_nodes(network, positions, nodelist=job_nodes, node_color=GRID,
                                      node_size=1250, edgecolors=TEXT, linewidths=0.7, ax=ax)
    link_marks = nx.draw_networkx_nodes(network, positions, nodelist=link_nodes, node_color=GRID,
                                       node_shape="s", node_size=1450, edgecolors=TEXT, linewidths=0.7, ax=ax)
    labels = nx.draw_networkx_labels(network, positions,
                                    labels={node: node[1] for node in network},
                                    font_color=TEXT, font_size=12, font_weight="bold", ax=ax)
    label_positions = []
    for (job_node, link_node) in edges:
        x1,y1 = positions[job_node]
        x2,y2 = positions[link_node]
        for fraction in [0.45, 0.65, 0.25, 0.8]:
            label_x, label_y = x1+(x2-x1)*fraction, y1+(y2-y1)*fraction
            if all(np.hypot(label_x-x, label_y-y) > 0.24 for x,y in label_positions):
                break
        label_positions.append((label_x, label_y))
        ax.text(label_x, label_y, f"{weights[link_node[1]][job_node[1]]:g}",
                fontsize=9, color=MUTED, ha="center",
                bbox={"facecolor": BACKGROUND, "edgecolor": "none", "pad": 1.5})
    shift_labels = {jid: ax.text(i, 1.30, "--", ha="center", color=MUTED, fontsize=11)
                    for i, jid in enumerate(sorted(graph.U))}
    ax.set(xlim=(-0.5, 4.5), ylim=(-0.3, 1.5))
    ax.axis("off")
    caption = fig.text(0.5, 0.115, "", ha="center", fontsize=12)
    fig.text(0.5, 0.055, "Yellow: current step   |   Magenta: job   |   Cyan: shared link   |   Edge values: local shifts (ms)",
             ha="center", color=MUTED, fontsize=9)
    stages = list(_trace(graph, jobs_map))

    def update(index):
        state = stages[index]
        job_marks.set_facecolors([YELLOW if state["node"] == node else
                                  MAGENTA if node[1] in state["assigned"] else GRID for node in job_nodes])
        link_marks.set_facecolors([YELLOW if state["node"] == node else
                                   CYAN if node[1] in state["links"] else GRID for node in link_nodes])
        colors, widths = [], []
        for job_node, link_node in edges:
            active = state["edge"] == (job_node[1], link_node[1])
            colors.append(YELLOW if active else MUTED if job_node[1] in state["assigned"]
                          and link_node[1] in state["links"] else GRID)
            widths.append(3.5 if active else 1.4)
        lines.set_color(colors)
        lines.set_linewidth(widths)
        for node, label in labels.items():
            label.set_color(BACKGROUND if state["node"] == node or
                            node[0] == "link" and node[1] in state["links"] else TEXT)
        for jid, label in shift_labels.items():
            label.set_text(f"{state['assigned'][jid]:g} ms" if jid in state["assigned"] else "--")
            label.set_color(CYAN if jid in state["assigned"] else MUTED)
        caption.set_text(state["message"])

    frames = [index for index in range(len(stages)) for _ in range(5)] + [len(stages)-1]*15
    clip = animation.FuncAnimation(fig, update, frames=frames, interval=100)
    clip.save(filename, writer=animation.PillowWriter(fps=10), dpi=110)
    plt.close(fig)
    return {"jobs": 5, "links": 3, "compute_ms": 80, "communication_ms": 20,
            "period_ms": 100, "compatibility_score": score,
            "link_shifts_ms": weights, "global_shifts_ms": shifts}

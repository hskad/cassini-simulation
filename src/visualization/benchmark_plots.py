"""Show every benchmark case, including ties and regressions."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src.visualization.plot_style import POLICY_COLORS, MUTED, dark_figure


@dark_figure
def plot_benchmarks(rows, filename):
    cases = list(dict.fromkeys(row["case"] for row in rows))
    fig, ax = plt.subplots(figsize=(11, 6.5))
    fig.subplots_adjust(left=0.23, right=0.94, bottom=0.14, top=0.77)
    fig.text(0.07, 0.94, "MATCHED BENCHMARKS  |  COMPLETION TIME", fontsize=17, weight="bold")
    fig.text(0.07, 0.885, "Same inputs and routes / all waits charged / dots show individual runs",
             fontsize=10.5, color=MUTED)
    for index, policy in enumerate(["static-shifts", "cassini"]):
        offset = -0.18 if index == 0 else 0.18
        values = [[row["jct_reduction_percent"] for row in rows
                   if row["case"] == case and row["policy"] == policy] for case in cases]
        means = [float(np.mean(group)) for group in values]
        y = np.arange(len(cases)) + offset
        ax.barh(y, means, height=0.32, color=POLICY_COLORS[policy], alpha=0.65, label=policy)
        for position, group, mean in zip(y, values, means):
            ax.scatter(group, [position] * len(group), s=22, color=POLICY_COLORS[policy], zorder=3)
            label_at = max(group) if mean >= 0 else min(group)
            ax.annotate(f"{mean:+.1f}%", (label_at, position),
                        xytext=(6 if mean >= 0 else -6, 0), textcoords="offset points",
                        va="center", ha="left" if mean >= 0 else "right", fontsize=9)
    flat = [row["jct_reduction_percent"] for row in rows]
    ax.set(yticks=range(len(cases)), yticklabels=[case.replace("-", " ") for case in cases],
           xlabel="Mean JCT reduction relative to uncoordinated (%)",
           xlim=(min(-5, min(flat) - 8), max(10, max(flat) + 10)))
    ax.invert_yaxis()
    ax.axvline(0, color=MUTED, linewidth=1)
    ax.grid(axis="x", linestyle=":", alpha=0.4)
    ax.legend(loc="upper right", bbox_to_anchor=(1, 1.18), ncol=2, fontsize=10)
    fig.text(0.23, 0.035, "Bars and labels show mean reductions across runs. Dots show each run.",
             fontsize=9, color=MUTED)
    fig.savefig(filename, dpi=160)
    plt.close(fig)

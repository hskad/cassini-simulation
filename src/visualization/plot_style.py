"""Shared colours and typography for simulator plots and README figures."""
from functools import wraps
import matplotlib.pyplot as plt

BACKGROUND = "#101216"
PANEL = "#171B23"
TEXT = "#F2F5FA"
MUTED = "#A4AFBF"
CYAN = "#00FFCC"
MAGENTA = "#FF007F"
YELLOW = "#FFD166"
GRID = "#394353"

POLICY_COLORS = {"uncoordinated": MAGENTA, "static-shifts": YELLOW, "cassini": CYAN}
PHASE_COLORS = {"compute": "#526781", "communicate": CYAN, "wait": YELLOW}
STYLE = {
    "figure.facecolor": BACKGROUND, "axes.facecolor": BACKGROUND,
    "savefig.facecolor": BACKGROUND, "savefig.edgecolor": BACKGROUND,
    "text.color": TEXT, "axes.labelcolor": TEXT, "axes.edgecolor": MUTED,
    "xtick.color": MUTED, "ytick.color": MUTED, "grid.color": GRID,
    "font.family": "DejaVu Sans", "font.size": 11,
    "axes.titlesize": 13, "axes.titleweight": "bold",
    "axes.spines.top": False, "axes.spines.right": False,
    "legend.facecolor": PANEL, "legend.edgecolor": GRID, "legend.labelcolor": TEXT,
    "lines.linewidth": 2.2, "axes.prop_cycle": plt.cycler(color=[CYAN, MAGENTA, YELLOW, "#91A7FF"]),
}


def dark_figure(function):
    @wraps(function)
    def draw(*args, **kwargs):
        with plt.rc_context(STYLE):
            return function(*args, **kwargs)
    return draw

"""Worker functions for stability analysis."""
import io
import math

import matplotlib as mpl

mpl.use("Agg")  # Use non-interactive backend for multiprocessing

import matplotlib.pyplot as plt
from pymatgen.analysis.pourbaix_diagram import PourbaixEntry, PourbaixPlotter

_worker_diagrams: dict = {}

def figure_worker_init(diagrams: dict):
    """Call once per worker process — store diagrams in process memory."""
    global _worker_diagrams  # noqa: PLW0603
    _worker_diagrams = diagrams

def figure_worker(args: tuple) -> tuple[str, str, str, bytes]:
    """Figure worker function to generate stability figure for a given entry and operating condition."""  # noqa: E501
    chemsys, database, material_id, entry, identifier, ph, u, decomp_energy = args
    fig = None
    try:
        diagram = _worker_diagrams[chemsys][identifier]
        plotter = PourbaixPlotter(diagram)

        fig, _ = create_entry_stability_figure(material_id, entry, plotter, decomp_energy, ph, u)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        buf.seek(0)
        return chemsys, database, material_id, buf.getvalue()
    finally:
        if fig is not None:
            plt.close(fig)


def create_entry_stability_figure(material_id: str,
                                  entry: PourbaixEntry,
                                  plotter: PourbaixPlotter,
                                  decomposition_energy_per_atom: float,
                                  ph: float,
                                  u: float) -> tuple[plt.Figure, plt.Axes]:
    """Create a Pourbaix stability figure for a given entry and operating condition."""
    mpl.rcParams['font.family'] = 'sans-serif'
    mpl.rcParams['font.sans-serif'] = ['Droid Sans', 'Open Sans', 'DejaVu Sans']
    # Sanity check: clip ph and U
    ph = max(-2, min(16, ph))
    u = max(-3, min(3, u))
    # Compute the bounds for y-axis
    u_min_axis = min(-3, math.floor(u))
    u_max_axis = max(3, math.ceil(u))
    # Compute the bounds for the x-axis
    ph_min_axis = min(-2, math.floor(ph))
    ph_max_axis = max(16, math.ceil(ph))
    # Plot
    fig, ax = plt.subplots(figsize=(12, 8))
    plotter.plot_entry_stability(entry,
                                ax=ax,
                                pH_range=(ph_min_axis, ph_max_axis),
                                V_range=(u_min_axis, u_max_axis),
                                pH_resolution=100,
                                V_resolution=100,
                                show_neutral_axes=False,
                                cmap="YlOrRd",
                                e_hull_max=1.0,
                                )

    # Fix hairlines in PDF export
    for collection in ax.collections:
        collection.set_linewidth(0)
        collection.set_edgecolor("none")
        collection.set_rasterized(True)

    # Dynamic axis limits
    ax.set_xlim([ph_min_axis, ph_max_axis])
    ax.set_ylim([u_min_axis, u_max_axis])
    # Ticks
    ph_ticks = range(ph_min_axis, ph_max_axis + 1, 2)
    u_ticks = range(u_min_axis, u_max_axis + 1, 1)
    ax.set_yticks(u_ticks)
    ax.set_xticks(ph_ticks)
    # Labels
    ax.set_xlabel("pH", fontsize=20)
    ax.set_ylabel("Applied Potential (V vs. SHE)", fontsize=20)
    ax.tick_params(axis="both", which="major", labelsize=18)
    for txt in ax.texts:
        txt.set_visible(False)
    for i, line in enumerate(ax.get_lines()):
        if i == 0:
            line.set_color("#AE86E2")
            line.set_alpha(0.8)
            line.set_linestyle("-")
            line.set_label("Hydrogen Stability Line")
            line.set_linewidth(4)
        elif i == 1:
            line.set_color("#86E2DD")
            line.set_alpha(0.8)
            line.set_linestyle("-")
            line.set_label("Oxygen Stability Line")
            line.set_linewidth(4)
        else:
            line.set_visible(False)
    # Dot marking the (pH, U) operating condition
    ax.plot(ph, u,
            marker="o",
            markersize=8,
            color="white",
            markeredgecolor="black",
            markeredgewidth=1.5,
            zorder=5,
            label=f"Operating point (pH={ph:.1f}, U={u:.1f} V)")
    # Add decomposition energy annotation
    # Smart offset to flip to left if pH is in the right half of the axis
    ph_mid = (ph_min_axis + ph_max_axis) / 2
    offset_x = -7.0 if ph > ph_mid else 0.5
    offset_y = 0.0

    ax.annotate(
        f"$\\Delta G_\\mathrm{{decomp}}$ = {decomposition_energy_per_atom:.2f} eV atom$^{{-1}}$",
        xy=(ph, u),
        xytext=(ph + offset_x, u + offset_y),
        fontsize=16,
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "alpha": 0.7},
    )
    ax.legend(fontsize=16, loc="lower right")
    cbar = ax.collections[0].colorbar
    cbar.ax.tick_params(labelsize=18)
    cbar.ax.set_yticks([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
    cbar.set_label(f"Stability of {material_id} (eV atom$^{{-1}}$)", fontsize=20)
    fig.tight_layout()
    return fig, ax

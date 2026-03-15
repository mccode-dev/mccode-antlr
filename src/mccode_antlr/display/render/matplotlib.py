"""Matplotlib 3-D renderer for McCode display geometry.

Example::

    from mccode_antlr.display import InstrumentDisplay
    from mccode_antlr.display.render.matplotlib import plot_geometry
    import matplotlib.pyplot as plt

    disp = InstrumentDisplay(instr)
    polylines = disp.to_polylines({'E_i': 5.0})

    fig, ax = plot_geometry(polylines)
    plt.show()
"""
from __future__ import annotations

from typing import Any

import numpy as np


def plot_geometry(
    geometry: dict[str, list[np.ndarray]],
    ax=None,
    colors: dict[str, Any] | None = None,
    *,
    show_labels: bool = True,
    label_offset: float = 0.02,
    linewidth: float = 1.0,
    alpha: float = 1.0,
) -> tuple[Any, Any]:
    """Draw instrument geometry using matplotlib's 3-D axes.

    Parameters
    ----------
    geometry:
        Output from :meth:`~mccode_antlr.display.InstrumentDisplay.to_polylines`
        — a dict mapping component names to lists of ``(N, 3)`` numpy arrays.
    ax:
        An existing ``Axes3D`` instance to draw onto.  If ``None`` a new
        figure and axes are created.
    colors:
        Optional mapping from component name to a matplotlib colour spec.
        Components not present in this dict receive auto-assigned colours.
    show_labels:
        If ``True`` (default) annotate each component with its name at the
        centroid of its geometry.
    label_offset:
        Fractional offset applied to the label position (relative to the
        overall scene bounding box diagonal).
    linewidth:
        Line width for all polylines.
    alpha:
        Opacity for all lines.

    Returns
    -------
    (fig, ax):
        The matplotlib Figure and Axes3D objects.
    """
    try:
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 — registers 3d projection
    except ImportError as exc:
        raise ImportError(
            "matplotlib is required for the matplotlib renderer. "
            "Install it with: pip install matplotlib"
        ) from exc

    if ax is None:
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
    else:
        fig = ax.figure

    prop_cycle = plt.rcParams['axes.prop_cycle']
    auto_colors = [c['color'] for c in prop_cycle]
    colors = dict(colors or {})

    all_pts: list[np.ndarray] = []

    for i, (name, polylines) in enumerate(geometry.items()):
        color = colors.get(name, auto_colors[i % len(auto_colors)])
        centroid_pts: list[np.ndarray] = []
        for pts in polylines:
            if pts.ndim != 2 or pts.shape[1] != 3 or len(pts) < 2:
                continue
            ax.plot3D(pts[:, 0], pts[:, 1], pts[:, 2],
                      color=color, linewidth=linewidth, alpha=alpha)
            centroid_pts.append(pts)
            all_pts.append(pts)

        if show_labels and centroid_pts:
            concat = np.vstack(centroid_pts)
            cx, cy, cz = concat.mean(axis=0)
            ax.text(cx, cy, cz, name, fontsize=7, color=color)

    ax.set_xlabel('x (m)')
    ax.set_ylabel('z (m)')
    ax.set_zlabel('y (m)')

    if all_pts:
        all_data = np.vstack(all_pts)
        _set_equal_aspect(ax, all_data)

    return fig, ax


def _set_equal_aspect(ax, pts: np.ndarray) -> None:
    """Set equal aspect ratio on a 3-D axes by adjusting limits."""
    mins = pts.min(axis=0)
    maxs = pts.max(axis=0)
    ranges = maxs - mins
    max_range = ranges.max()
    if max_range < 1e-12:
        return
    centres = (mins + maxs) / 2
    ax.set_xlim(centres[0] - max_range / 2, centres[0] + max_range / 2)
    ax.set_ylim(centres[1] - max_range / 2, centres[1] + max_range / 2)
    ax.set_zlim(centres[2] - max_range / 2, centres[2] + max_range / 2)

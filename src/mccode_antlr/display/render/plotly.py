"""Plotly 3-D renderer for McCode display geometry (optional dependency).

This renderer requires ``plotly`` to be installed and returns a
:class:`plotly.graph_objects.Figure` that can be displayed directly in a
Jupyter notebook cell or saved as HTML.

It renders:

- **Polylines** — one ``Scatter3d(mode='lines')`` trace per component, with
  ``NaN`` row separators so all segments are batched into a single trace.
- **Solid surfaces** — one ``Mesh3d`` trace per component when any primitive
  exposes a :meth:`~mccode_antlr.display.primitives.Primitive.to_mesh` result.

Example::

    from mccode_antlr.display import InstrumentDisplay
    from mccode_antlr.display.render.plotly import show_geometry

    disp = InstrumentDisplay(instr)
    geometry = disp.to_polylines({'E_i': 5.0})
    fig = show_geometry(geometry, disp)
    fig                        # last expression in a Jupyter cell renders inline
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from ..instrument_display import InstrumentDisplay


def show_geometry(
    geometry: dict[str, list[np.ndarray]],
    instrument_display: 'InstrumentDisplay | None' = None,
    *,
    use_mesh: bool = True,
    params: dict | None = None,
    width: int = 900,
    height: int = 700,
    background: str = '#111111',
    opacity: float = 0.6,
) -> 'plotly.graph_objects.Figure':  # noqa: F821
    """Render instrument geometry as an interactive Plotly 3-D figure.

    Parameters
    ----------
    geometry:
        Output from :meth:`~mccode_antlr.display.InstrumentDisplay.to_polylines`
        — a dict mapping component names to lists of ``(N, 3)`` numpy arrays.
    instrument_display:
        The :class:`~mccode_antlr.display.InstrumentDisplay` instance.  When
        provided and *use_mesh* is ``True``, the renderer calls ``to_mesh`` on
        each component's primitives to obtain surface geometry.
    use_mesh:
        If ``True`` (default) and *instrument_display* is supplied, solid
        surface meshes are drawn in addition to the wire polylines.
    params:
        Parameter dict forwarded to ``to_mesh``; defaults to ``{}``.
    width, height:
        Figure dimensions in pixels.
    background:
        Background colour (CSS colour string).
    opacity:
        Opacity for mesh surfaces.

    Returns
    -------
    plotly.graph_objects.Figure
    """
    try:
        import plotly.graph_objects as go
    except ImportError as exc:
        raise ImportError(
            "plotly is not installed. Install it with: pip install plotly"
        ) from exc

    import matplotlib.pyplot as plt
    prop_cycle = plt.rcParams['axes.prop_cycle']
    auto_colors = [c['color'] for c in prop_cycle]

    p = params or {}
    traces = []

    # Pre-build orient lookup: name → (rotation, translation) for mesh transform
    _orient_map: dict = {}
    if use_mesh and instrument_display is not None:
        from ..instrument_display import _transform_polyline
        for instance in instrument_display._instr.components:
            if instance.orientation is not None:
                try:
                    _orient_map[instance.name] = (
                        instance.orientation.rotation(),
                        instance.orientation.position(),
                    )
                except Exception:
                    pass

    for i, (name, polylines) in enumerate(geometry.items()):
        color = auto_colors[i % len(auto_colors)]

        # --- wire trace ---
        xs, ys, zs = [], [], []
        for pts in polylines:
            if pts.ndim != 2 or pts.shape[1] != 3 or len(pts) < 2:
                continue
            xs.extend(pts[:, 0].tolist() + [None])
            ys.extend(pts[:, 1].tolist() + [None])
            zs.extend(pts[:, 2].tolist() + [None])
        if xs:
            traces.append(go.Scatter3d(
                x=xs, y=ys, z=zs,
                mode='lines',
                line=dict(color=color, width=2),
                name=name,
                legendgroup=name,
                showlegend=True,
            ))

        # --- mesh trace ---
        if use_mesh and instrument_display is not None:
            all_verts, all_faces_list = [], []
            offset = 0
            comp_disp = instrument_display._components.get(name)
            if comp_disp is not None:
                for prim in comp_disp.primitives:
                    result = prim.to_mesh(p)
                    if result is None:
                        continue
                    verts, faces = result
                    # transform mesh vertices to global instrument frame
                    orient = _orient_map.get(name)
                    if orient is not None:
                        try:
                            verts = _transform_polyline(verts, orient[0], orient[1], p)
                        except Exception:
                            pass
                    all_verts.append(verts)
                    all_faces_list.append(faces + offset)
                    offset += len(verts)
            if all_verts:
                v = np.vstack(all_verts)
                f = np.vstack(all_faces_list)
                traces.append(go.Mesh3d(
                    x=v[:, 0], y=v[:, 1], z=v[:, 2],
                    i=f[:, 0], j=f[:, 1], k=f[:, 2],
                    color=color,
                    opacity=opacity,
                    name=name,
                    legendgroup=name,
                    showlegend=False,
                    lighting=dict(ambient=0.5, diffuse=0.8, specular=0.2),
                    lightposition=dict(x=100, y=200, z=0),
                ))

    fig = go.Figure(data=traces)
    fig.update_layout(
        width=width,
        height=height,
        paper_bgcolor=background,
        scene=dict(
            xaxis=dict(title='x (m)', backgroundcolor=background,
                       gridcolor='#444', zerolinecolor='#888'),
            yaxis=dict(title='z (m)', backgroundcolor=background,
                       gridcolor='#444', zerolinecolor='#888'),
            zaxis=dict(title='y (m)', backgroundcolor=background,
                       gridcolor='#444', zerolinecolor='#888'),
            bgcolor=background,
            aspectmode='data',
        ),
        legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(color='white')),
        margin=dict(l=0, r=0, b=0, t=30),
    )
    return fig

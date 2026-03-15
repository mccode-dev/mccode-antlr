"""pythreejs / K3D renderer for McCode display geometry (optional dependency).

This renderer requires either ``pythreejs`` or ``k3d`` to be installed.
It returns an ``ipywidget`` that can be displayed directly in a Jupyter
notebook cell.

The pythreejs backend renders:

- **Polylines** — as ``THREE.Line`` objects (wire geometry).
- **Solid surfaces** — as ``THREE.Mesh`` objects with ``MeshStandardMaterial``
  and ``BufferGeometry`` (index + position attributes) when primitives expose a
  :meth:`~mccode_antlr.display.primitives.Primitive.to_mesh` result.

Example (pythreejs)::

    from mccode_antlr.display import InstrumentDisplay
    from mccode_antlr.display.render.threejs import show_geometry

    disp = InstrumentDisplay(instr)
    geometry = disp.to_polylines({'E_i': 5.0})
    show_geometry(geometry)                          # wire only
    show_geometry(geometry, disp, use_mesh=True)     # wire + surfaces

Example (K3D)::

    show_geometry(geometry, backend='k3d')
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
    backend: str = 'auto',
    use_mesh: bool = True,
    params: dict | None = None,
    width: int = 800,
    height: int = 600,
    background: str = '#111111',
    opacity: float = 0.6,
):
    """Display instrument geometry in a Jupyter notebook using WebGL.

    Parameters
    ----------
    geometry:
        Output from :meth:`~mccode_antlr.display.InstrumentDisplay.to_polylines`.
    instrument_display:
        The :class:`~mccode_antlr.display.InstrumentDisplay` instance.  When
        provided and *use_mesh* is ``True``, solid surface meshes are drawn.
    backend:
        ``'pythreejs'``, ``'k3d'``, or ``'auto'`` (tries pythreejs first).
    use_mesh:
        If ``True`` (default) and *instrument_display* is supplied, solid
        surface meshes are drawn alongside the wire representation.
    params:
        Parameter dict forwarded to ``to_mesh``; defaults to ``{}``.
    width, height:
        Widget dimensions in pixels.
    background:
        Background colour (CSS colour string, used by pythreejs backend).
    opacity:
        Opacity for mesh surfaces.

    Returns
    -------
    widget
        An ``ipywidget`` renderable in a Jupyter cell.  Call ``display(widget)``
        or simply return it as the last expression in a cell.
    """
    if backend == 'auto':
        for b in ('pythreejs', 'k3d'):
            try:
                return _show(geometry, b, instrument_display=instrument_display,
                             use_mesh=use_mesh, params=params,
                             width=width, height=height,
                             background=background, opacity=opacity)
            except ImportError:
                pass
        raise ImportError(
            "No WebGL backend found. Install one of:\n"
            "  pip install pythreejs\n"
            "  pip install k3d"
        )
    return _show(geometry, backend, instrument_display=instrument_display,
                 use_mesh=use_mesh, params=params,
                 width=width, height=height,
                 background=background, opacity=opacity)


def _show(geometry, backend, *, instrument_display, use_mesh, params,
          width, height, background, opacity):
    if backend == 'pythreejs':
        return _show_pythreejs(geometry, instrument_display=instrument_display,
                               use_mesh=use_mesh, params=params,
                               width=width, height=height,
                               background=background, opacity=opacity)
    if backend == 'k3d':
        return _show_k3d(geometry)
    raise ValueError(f"Unknown backend {backend!r}; choose 'pythreejs' or 'k3d'")


def _show_pythreejs(geometry, *, instrument_display, use_mesh, params,
                    width, height, background, opacity):
    try:
        import pythreejs as three
    except ImportError as exc:
        raise ImportError(
            "pythreejs is not installed. Install it with: pip install pythreejs"
        ) from exc

    import matplotlib.pyplot as plt
    prop_cycle = plt.rcParams['axes.prop_cycle']
    auto_colors = [c['color'] for c in prop_cycle]

    p = params or {}
    scene = three.Scene(background=background)
    scene.add(three.AmbientLight(color='white', intensity=0.6))
    scene.add(three.DirectionalLight(color='white', position=[5, 10, 5], intensity=0.8))

    for i, (name, polylines) in enumerate(geometry.items()):
        color = auto_colors[i % len(auto_colors)]

        # --- wire geometry ---
        for pts in polylines:
            if pts.ndim != 2 or pts.shape[1] != 3 or len(pts) < 2:
                continue
            positions = pts.astype(np.float32).flatten().tolist()
            geom = three.BufferGeometry(
                attributes={
                    'position': three.BufferAttribute(
                        array=np.array(positions, dtype=np.float32).reshape(-1, 3)
                    )
                }
            )
            material = three.LineBasicMaterial(color=color)
            scene.add(three.Line(geometry=geom, material=material))

        # --- mesh geometry ---
        if use_mesh and instrument_display is not None:
            comp_disp = instrument_display.component_displays.get(name)
            if comp_disp is not None:
                all_verts, all_faces_list = [], []
                offset = 0
                for prim in comp_disp.primitives:
                    result = prim.to_mesh(p)
                    if result is None:
                        continue
                    verts, faces = result
                    if hasattr(comp_disp, '_transform_points'):
                        verts = comp_disp._transform_points(verts)
                    all_verts.append(verts)
                    all_faces_list.append(faces + offset)
                    offset += len(verts)
                if all_verts:
                    v = np.vstack(all_verts).astype(np.float32)
                    f = np.vstack(all_faces_list).astype(np.uint32)
                    geom = three.BufferGeometry(
                        attributes={
                            'position': three.BufferAttribute(array=v),
                        },
                        index=three.BufferAttribute(
                            array=f.flatten(), dtype=np.uint32
                        ),
                    )
                    mat = three.MeshStandardMaterial(
                        color=color,
                        opacity=opacity,
                        transparent=opacity < 1.0,
                        side='DoubleSide',
                    )
                    scene.add(three.Mesh(geometry=geom, material=mat))

    camera = three.PerspectiveCamera(fov=50, aspect=width / height,
                                     near=0.01, far=1000)
    camera.position = [0, -5, 2]
    camera.lookAt([0, 0, 0])

    controls = three.OrbitControls(controlling=camera)
    renderer = three.Renderer(
        camera=camera, scene=scene, controls=[controls],
        width=width, height=height,
    )
    return renderer


def _show_k3d(geometry):
    try:
        import k3d
    except ImportError as exc:
        raise ImportError(
            "k3d is not installed. Install it with: pip install k3d"
        ) from exc

    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    prop_cycle = plt.rcParams['axes.prop_cycle']
    auto_colors = [c['color'] for c in prop_cycle]

    plot = k3d.plot()

    for i, (name, polylines) in enumerate(geometry.items()):
        hex_color = auto_colors[i % len(auto_colors)]
        rgb = mcolors.to_rgb(hex_color)
        k3d_color = int(rgb[0] * 255) << 16 | int(rgb[1] * 255) << 8 | int(rgb[2] * 255)
        for pts in polylines:
            if pts.ndim != 2 or pts.shape[1] != 3 or len(pts) < 2:
                continue
            plot += k3d.line(pts.astype(np.float32), color=k3d_color, name=name)

    return plot

"""pythreejs / K3D renderer for McCode display geometry (optional dependency).

This renderer requires either ``pythreejs`` or ``k3d`` to be installed.
It returns an ``ipywidget`` that can be displayed directly in a Jupyter
notebook cell.

Example (pythreejs)::

    from mccode_antlr.display import InstrumentDisplay
    from mccode_antlr.display.render.threejs import show_geometry

    disp = InstrumentDisplay(instr)
    polylines = disp.to_polylines({'E_i': 5.0})
    show_geometry(polylines)   # displays inline in Jupyter

Example (K3D)::

    show_geometry(polylines, backend='k3d')
"""
from __future__ import annotations

import numpy as np


def show_geometry(
    geometry: dict[str, list[np.ndarray]],
    *,
    backend: str = 'auto',
    width: int = 800,
    height: int = 600,
    background: str = '#111111',
):
    """Display instrument geometry in a Jupyter notebook using WebGL.

    Parameters
    ----------
    geometry:
        Output from :meth:`~mccode_antlr.display.InstrumentDisplay.to_polylines`.
    backend:
        ``'pythreejs'``, ``'k3d'``, or ``'auto'`` (tries pythreejs first).
    width, height:
        Widget dimensions in pixels.
    background:
        Background colour (CSS colour string, used by pythreejs backend).

    Returns
    -------
    widget
        An ``ipywidget`` renderable in a Jupyter cell.  Call ``display(widget)``
        or simply return it as the last expression in a cell.
    """
    if backend == 'auto':
        for b in ('pythreejs', 'k3d'):
            try:
                return _show(geometry, b, width=width, height=height, background=background)
            except ImportError:
                pass
        raise ImportError(
            "No WebGL backend found. Install one of:\n"
            "  pip install pythreejs\n"
            "  pip install k3d"
        )
    return _show(geometry, backend, width=width, height=height, background=background)


def _show(geometry, backend, *, width, height, background):
    if backend == 'pythreejs':
        return _show_pythreejs(geometry, width=width, height=height, background=background)
    if backend == 'k3d':
        return _show_k3d(geometry)
    raise ValueError(f"Unknown backend {backend!r}; choose 'pythreejs' or 'k3d'")


def _show_pythreejs(geometry, *, width, height, background):
    try:
        import pythreejs as three
    except ImportError as exc:
        raise ImportError(
            "pythreejs is not installed. Install it with: pip install pythreejs"
        ) from exc

    import matplotlib.pyplot as plt
    prop_cycle = plt.rcParams['axes.prop_cycle']
    auto_colors = [c['color'] for c in prop_cycle]

    scene = three.Scene(background=background)
    scene.add(three.AmbientLight(color='white'))

    for i, (name, polylines) in enumerate(geometry.items()):
        color = auto_colors[i % len(auto_colors)]
        for pts in polylines:
            if pts.ndim != 2 or pts.shape[1] != 3 or len(pts) < 2:
                continue
            positions = pts.astype(np.float32).flatten().tolist()
            geometry_obj = three.BufferGeometry(
                attributes={
                    'position': three.BufferAttribute(
                        array=np.array(positions, dtype=np.float32).reshape(-1, 3)
                    )
                }
            )
            material = three.LineBasicMaterial(color=color)
            line = three.Line(geometry=geometry_obj, material=material)
            scene.add(line)

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

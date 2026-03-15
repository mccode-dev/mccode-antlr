"""build123d / OCCT B-rep renderer for McCode display geometry (optional dependency).

Converts McCode instrument geometry to solid boundary-representation (B-rep) shapes
and exports them as STEP files via the build123d library (which wraps OpenCASCADE
Technology, OCCT).

Rendering pipeline
------------------
1. :func:`primitive_to_brep` dispatches a single
   :class:`~mccode_antlr.display.primitives.Primitive` to the appropriate
   build123d solid or wire shape.
2. :func:`component_to_brep` collects all primitives for one
   :class:`~mccode_antlr.display.ComponentDisplay` into a single ``bd.Compound``.
3. :func:`instrument_to_assembly` places every component in the global instrument
   frame and returns a labelled ``bd.Compound``.
4. :func:`save_step` writes the compound to a STEP file.

Override hooks
--------------
:class:`BRepRegistry` lets you register custom shape-building callables for
specific component type names.  Components without a registered override fall
back to the primitive-based B-rep.

Example::

    from mccode_antlr.display import InstrumentDisplay
    from mccode_antlr.display.render.brep import (
        BRepRegistry, instrument_to_assembly, save_step,
    )

    registry = BRepRegistry()

    @registry.register("Lens_simple")
    def lens_brep(instance, params):
        import build123d as bd
        r = float(instance.parameters['R'].evaluate(params))
        return bd.Sphere(r)

    disp = InstrumentDisplay(instr)
    assembly = instrument_to_assembly(disp, params={'E_i': 5.0}, registry=registry)
    save_step(assembly, 'instrument.step')
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable

import numpy as np

if TYPE_CHECKING:
    import build123d as bd
    from ..instrument_display import InstrumentDisplay
    from ..component_display import ComponentDisplay

__all__ = [
    'BRepRegistry',
    'primitive_to_brep',
    'component_to_brep',
    'instrument_to_assembly',
    'save_step',
]


# ---------------------------------------------------------------------------
# Override registry
# ---------------------------------------------------------------------------

class BRepRegistry:
    """Registry of per-component-type B-rep override callables.

    Override callables receive the raw ``ComponentInstance`` and the evaluated
    parameter dict and should return a build123d shape (or ``None`` to skip).

    Example::

        registry = BRepRegistry()

        @registry.register("Lens_simple")
        def lens_brep(instance, params):
            import build123d as bd
            r = float(instance.parameters['R'].evaluate(params))
            return bd.Sphere(r)
    """

    def __init__(self) -> None:
        self._overrides: dict[str, Callable] = {}

    def register(self, comp_type_name: str):
        """Decorator: register *func* as the B-rep builder for *comp_type_name*."""
        def decorator(func: Callable) -> Callable:
            self._overrides[comp_type_name] = func
            return func
        return decorator

    def get(self, comp_type_name: str) -> Callable | None:
        """Return the registered callable for *comp_type_name*, or ``None``."""
        return self._overrides.get(comp_type_name)

    def __repr__(self) -> str:
        return f'BRepRegistry({list(self._overrides)!r})'


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _require_bd():
    try:
        import build123d as bd
        return bd
    except ImportError as exc:
        raise ImportError(
            "build123d is not installed. Install it with: pip install build123d"
        ) from exc


def _eval(e, params: dict) -> float:
    from ...common.expression import Expr
    if isinstance(e, Expr):
        result = e.evaluate(params).simplify()
        v = result.value
        if v is None:
            raise ValueError(
                f"Cannot evaluate {e!r} to a number with params {params!r}"
            )
        return float(v)
    return float(e)


def _axis_frame(nx: float, ny: float, nz: float) -> tuple[tuple, tuple]:
    """Return (x_dir, z_dir) for a local frame whose Z aligns with (nx,ny,nz)."""
    normal = np.array([nx, ny, nz], dtype=float)
    norm = np.linalg.norm(normal)
    if norm < 1e-10:
        return (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)
    normal /= norm
    ref = [1.0, 0.0, 0.0] if abs(normal[0]) < 0.9 else [0.0, 1.0, 0.0]
    perp = np.cross(normal, ref)
    perp /= np.linalg.norm(perp)
    return tuple(perp.tolist()), tuple(normal.tolist())


def _orient(shape, cx, cy, cz, nx, ny, nz):
    """Locate *shape* at (cx,cy,cz) with its Z axis along (nx,ny,nz)."""
    import build123d as bd
    x_dir, z_dir = _axis_frame(nx, ny, nz)
    return shape.locate(bd.Location(bd.Plane(origin=(cx, cy, cz),
                                             x_dir=x_dir, z_dir=z_dir)))


def _plane_from_name(name: str, cx, cy, cz):
    import build123d as bd
    n = name.lower()
    if n == 'xy':
        return bd.Plane(origin=(cx, cy, cz), x_dir=(1,0,0), z_dir=(0,0,1))
    if n == 'xz':
        return bd.Plane(origin=(cx, cy, cz), x_dir=(1,0,0), z_dir=(0,1,0))
    if n == 'yz':
        return bd.Plane(origin=(cx, cy, cz), x_dir=(0,1,0), z_dir=(1,0,0))
    return bd.Plane(origin=(cx, cy, cz))


# ---------------------------------------------------------------------------
# Per-type B-rep builders
# ---------------------------------------------------------------------------

def _brep_line(prim, p):
    import build123d as bd
    return bd.Edge.make_line(
        (_eval(prim.x1,p), _eval(prim.y1,p), _eval(prim.z1,p)),
        (_eval(prim.x2,p), _eval(prim.y2,p), _eval(prim.z2,p)),
    )


def _brep_multiline(prim, p):
    import build123d as bd
    pts = [(_eval(x,p), _eval(y,p), _eval(z,p)) for x,y,z in prim.points]
    edges = [bd.Edge.make_line(pts[i], pts[i+1]) for i in range(len(pts)-1)]
    return bd.Wire(edges) if edges else None


def _brep_circle(prim, p):
    import build123d as bd
    cx, cy, cz = _eval(prim.cx,p), _eval(prim.cy,p), _eval(prim.cz,p)
    return bd.Wire.make_circle(_eval(prim.r,p), _plane_from_name(prim.plane, cx,cy,cz))


def _brep_circle_normal(prim, p):
    import build123d as bd
    cx, cy, cz = _eval(prim.cx,p), _eval(prim.cy,p), _eval(prim.cz,p)
    nx, ny, nz = _eval(prim.nx,p), _eval(prim.ny,p), _eval(prim.nz,p)
    x_dir, z_dir = _axis_frame(nx, ny, nz)
    plane = bd.Plane(origin=(cx,cy,cz), x_dir=x_dir, z_dir=z_dir)
    return bd.Wire.make_circle(_eval(prim.r,p), plane)


def _brep_rectangle(prim, p):
    import build123d as bd
    cx, cy, cz = _eval(prim.cx,p), _eval(prim.cy,p), _eval(prim.cz,p)
    plane = _plane_from_name(prim.plane, cx, cy, cz)
    return bd.Face(bd.Wire.make_rect(_eval(prim.w,p), _eval(prim.h,p), plane))


def _brep_box(prim, p):
    import build123d as bd
    cx, cy, cz = _eval(prim.cx,p), _eval(prim.cy,p), _eval(prim.cz,p)
    xw, yh, zd = _eval(prim.xw,p), _eval(prim.yh,p), _eval(prim.zd,p)
    nx, ny, nz = _eval(prim.nx,p), _eval(prim.ny,p), _eval(prim.nz,p)
    box = bd.Box(xw, yh, zd)
    return _orient(box, cx, cy, cz, nx, ny, nz)


def _brep_sphere(prim, p):
    import build123d as bd
    cx, cy, cz = _eval(prim.cx,p), _eval(prim.cy,p), _eval(prim.cz,p)
    return bd.Sphere(_eval(prim.r,p)).locate(bd.Location((cx, cy, cz)))


def _brep_cylinder(prim, p):
    import build123d as bd
    cx, cy, cz = _eval(prim.cx,p), _eval(prim.cy,p), _eval(prim.cz,p)
    nx, ny, nz = _eval(prim.nx,p), _eval(prim.ny,p), _eval(prim.nz,p)
    cyl = bd.Cylinder(_eval(prim.r,p), _eval(prim.h,p))
    return _orient(cyl, cx, cy, cz, nx, ny, nz)


def _brep_cone(prim, p):
    import build123d as bd
    cx, cy, cz = _eval(prim.cx,p), _eval(prim.cy,p), _eval(prim.cz,p)
    nx, ny, nz = _eval(prim.nx,p), _eval(prim.ny,p), _eval(prim.nz,p)
    cone = bd.Cone(_eval(prim.r,p), 0, _eval(prim.h,p))
    return _orient(cone, cx, cy, cz, nx, ny, nz)


def _brep_disc(prim, p):
    """Disc has no thickness field — render as a thin cylinder (1 mm)."""
    import build123d as bd
    cx, cy, cz = _eval(prim.cx,p), _eval(prim.cy,p), _eval(prim.cz,p)
    nx, ny, nz = _eval(prim.nx,p), _eval(prim.ny,p), _eval(prim.nz,p)
    disc = bd.Cylinder(_eval(prim.r,p), 1e-3)
    return _orient(disc, cx, cy, cz, nx, ny, nz)


def _brep_annulus(prim, p):
    import build123d as bd
    cx, cy, cz = _eval(prim.cx,p), _eval(prim.cy,p), _eval(prim.cz,p)
    nx, ny, nz = _eval(prim.nx,p), _eval(prim.ny,p), _eval(prim.nz,p)
    r_outer = _eval(prim.r_outer, p)
    r_inner = _eval(prim.r_inner, p)
    outer = bd.Cylinder(r_outer, 1e-3)
    inner = bd.Cylinder(r_inner, 1e-3)
    ring = outer - inner
    return _orient(ring, cx, cy, cz, nx, ny, nz)


def _brep_from_mesh(prim, p):
    """Build a solid from any primitive that implements to_mesh()."""
    import build123d as bd
    mesh = prim.to_mesh(p)
    if mesh is None:
        return None
    verts, faces = mesh
    tri_faces = [
        bd.Face(bd.Wire.make_polygon([tuple(verts[i].tolist()) for i in f], close=True))
        for f in faces
    ]
    if not tri_faces:
        return None
    if len(tri_faces) == 1:
        return tri_faces[0]
    shell = bd.Shell(tri_faces)
    try:
        return bd.Solid(shell)
    except Exception:
        return bd.Compound(tri_faces)


# ---------------------------------------------------------------------------
# Public dispatch
# ---------------------------------------------------------------------------

def primitive_to_brep(prim, params: dict | None = None):
    """Convert a single :class:`~mccode_antlr.display.primitives.Primitive` to a
    build123d shape.

    Parameters
    ----------
    prim:
        Any ``Primitive`` subclass, ``ConditionalBlock``, or ``LoopBlock``.
    params:
        Parameter values for evaluating symbolic ``Expr`` fields.

    Returns
    -------
    build123d shape, list of shapes, or ``None``
    """
    _require_bd()
    from ..primitives import (
        Magnify, Line, DashedLine, Multiline, Circle, Rectangle,
        Box, Sphere, Cylinder, Cone, CircleNormal,
        Disc, Annulus, Polygon, Polyhedron,
        ConditionalBlock, LoopBlock,
    )

    p = params or {}

    if isinstance(prim, Magnify):
        return None
    if isinstance(prim, (Line, DashedLine)):
        return _brep_line(prim, p)
    if isinstance(prim, Multiline):
        return _brep_multiline(prim, p)
    if isinstance(prim, Circle):
        return _brep_circle(prim, p)
    if isinstance(prim, CircleNormal):
        return _brep_circle_normal(prim, p)
    if isinstance(prim, Rectangle):
        return _brep_rectangle(prim, p)
    if isinstance(prim, Box):
        return _brep_box(prim, p)
    if isinstance(prim, Sphere):
        return _brep_sphere(prim, p)
    if isinstance(prim, Cylinder):
        return _brep_cylinder(prim, p)
    if isinstance(prim, Cone):
        return _brep_cone(prim, p)
    if isinstance(prim, Disc):
        return _brep_disc(prim, p)
    if isinstance(prim, Annulus):
        return _brep_annulus(prim, p)
    if isinstance(prim, (Polygon, Polyhedron)):
        return _brep_from_mesh(prim, p)

    if isinstance(prim, ConditionalBlock):
        try:
            val = prim.condition.evaluate(p).simplify().value
        except Exception:
            val = None
        if val:
            results = [r for sub in prim.body
                       if (r := primitive_to_brep(sub, p)) is not None]
            flat = []
            for r in results:
                (flat.extend(r) if isinstance(r, list) else flat.append(r))
            return flat or None
        return None

    if isinstance(prim, LoopBlock):
        try:
            start = int(_eval(prim.start, p))
            stop  = int(_eval(prim.stop,  p))
            step  = int(_eval(prim.step,  p)) if hasattr(prim, 'step') else 1
        except Exception:
            return None
        results = []
        for i in range(start, stop, step):
            lp = dict(p, **{prim.var: float(i)})
            for sub in prim.body:
                r = primitive_to_brep(sub, lp)
                if r is None:
                    continue
                (results.extend(r) if isinstance(r, list) else results.append(r))
        return results or None

    return None


# ---------------------------------------------------------------------------
# Component-level aggregation
# ---------------------------------------------------------------------------

def component_to_brep(
    comp_display: 'ComponentDisplay',
    params: dict | None = None,
) -> 'bd.Compound | None':
    """Convert all primitives of a :class:`~mccode_antlr.display.ComponentDisplay`
    to a single build123d ``Compound``, or ``None`` if no shapes result.
    """
    import build123d as bd
    p = params or {}
    shapes: list = []
    for prim in comp_display.primitives:
        try:
            result = primitive_to_brep(prim, p)
        except Exception:
            continue
        if result is None:
            continue
        (shapes.extend(result) if isinstance(result, list) else shapes.append(result))
    if not shapes:
        return None
    return bd.Compound(shapes)


# ---------------------------------------------------------------------------
# Instrument-level assembly
# ---------------------------------------------------------------------------

def instrument_to_assembly(
    instr_display: 'InstrumentDisplay',
    params: dict | None = None,
    registry: BRepRegistry | None = None,
) -> 'bd.Compound':
    """Build a labelled build123d ``Compound`` with every component placed in the
    global instrument frame.

    Parameters
    ----------
    instr_display:
        The :class:`~mccode_antlr.display.InstrumentDisplay` for the instrument.
    params:
        Instrument-level parameter values.
    registry:
        Optional :class:`BRepRegistry`; registered overrides take precedence over
        the primitive fallback for their component type names.

    Returns
    -------
    ``bd.Compound``
    """
    import build123d as bd
    from ..instrument_display import _eval_expr

    p = params or {}
    placed: list = []

    for instance in instr_display._instr.components:
        name = instance.name
        comp_type = getattr(instance.type, 'name', str(instance.type))

        # Build merged parameter dict
        comp_params = dict(p)
        for cp in instance.parameters:
            try:
                val = cp.value.evaluate(p).simplify()
                comp_params[cp.name] = float(val)
            except Exception:
                pass

        # Determine shape: override → primitive fallback
        shape = None
        if registry is not None:
            override = registry.get(comp_type)
            if override is not None:
                try:
                    shape = override(instance, comp_params)
                except Exception:
                    shape = None

        if shape is None:
            comp_disp = instr_display._components.get(name)
            if comp_disp is not None:
                shape = component_to_brep(comp_disp, comp_params)

        if shape is None:
            continue

        # Apply global-frame placement
        if instance.orientation is not None:
            try:
                orient = instance.orientation
                rotation = orient.rotation()
                translation = orient.position()
                tx = _eval_expr(translation.x, p)
                ty = _eval_expr(translation.y, p)
                tz = _eval_expr(translation.z, p)
                R = np.array([
                    [_eval_expr(rotation.xx, p), _eval_expr(rotation.xy, p), _eval_expr(rotation.xz, p)],
                    [_eval_expr(rotation.yx, p), _eval_expr(rotation.yy, p), _eval_expr(rotation.yz, p)],
                    [_eval_expr(rotation.zx, p), _eval_expr(rotation.zy, p), _eval_expr(rotation.zz, p)],
                ], dtype=float)
                t = np.array([tx, ty, tz], dtype=float)
                x_dir = tuple(R[:, 0].tolist())
                z_dir = tuple(R[:, 2].tolist())
                loc = bd.Location(bd.Plane(origin=tuple(t.tolist()),
                                           x_dir=x_dir, z_dir=z_dir))
                shape = shape.locate(loc)
            except Exception:
                pass

        shape.label = name
        placed.append(shape)

    if not placed:
        return bd.Compound([bd.Box(1e-3, 1e-3, 1e-3)])
    return bd.Compound(placed)


# ---------------------------------------------------------------------------
# STEP export
# ---------------------------------------------------------------------------

def save_step(assembly: 'bd.Compound', path: str | Path) -> None:
    """Write *assembly* to a STEP file at *path*.

    Parameters
    ----------
    assembly:
        A build123d ``Compound`` (e.g. from :func:`instrument_to_assembly`).
    path:
        Output file path (``.step`` extension is conventional).
    """
    from build123d import export_step
    export_step(assembly, str(path))

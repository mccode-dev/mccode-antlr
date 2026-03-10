"""Geometry primitives for the McCode MCDISPLAY section.

Each primitive stores its arguments as :class:`~mccode_antlr.common.expression.Expr`
objects and can:

- :meth:`evaluate` — substitute a parameter dict and return a resolved copy
  with all :class:`~mccode_antlr.common.expression.Expr` values replaced by
  ``float``.
- :meth:`to_polylines` — return a list of ``(N, 3)`` numpy arrays (open or
  closed polylines) suitable for 3-D rendering.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from ..common.expression import Expr


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _eval(e: Expr | float, params: dict) -> float:
    """Evaluate an Expr or pass through a bare float."""
    if isinstance(e, Expr):
        result = e.evaluate(params).simplify()
        v = result.value
        if v is None:
            raise ValueError(
                f"Cannot evaluate expression {e!r} to a number with params {params!r}"
            )
        return float(v)
    return float(e)


def _circle_points(cx, cy, cz, r, plane: str, n: int = 24) -> np.ndarray:
    """Return (n+1, 3) points for a closed circle in the given plane."""
    t = np.linspace(0, 2 * math.pi, n + 1)
    cos_t = np.cos(t)
    sin_t = np.sin(t)
    if plane == 'xy':
        return np.column_stack([cx + r * cos_t, cy + r * sin_t, np.full(n + 1, cz)])
    if plane == 'xz':
        return np.column_stack([cx + r * cos_t, np.full(n + 1, cy), cz + r * sin_t])
    if plane == 'yz':
        return np.column_stack([np.full(n + 1, cx), cy + r * cos_t, cz + r * sin_t])
    raise ValueError(f"Unknown plane '{plane}'; expected 'xy', 'xz', or 'yz'")


def _circle_with_normal(cx, cy, cz, r, nx, ny, nz, n: int = 24) -> np.ndarray:
    """Return (n+1, 3) points for a circle with an arbitrary normal vector."""
    normal = np.array([nx, ny, nz], dtype=float)
    norm = np.linalg.norm(normal)
    if norm < 1e-10:
        return np.zeros((n + 1, 3))
    normal /= norm
    # Find a perpendicular vector
    if abs(normal[0]) < 0.9:
        perp = np.cross(normal, [1, 0, 0])
    else:
        perp = np.cross(normal, [0, 1, 0])
    perp /= np.linalg.norm(perp)
    binorm = np.cross(normal, perp)
    t = np.linspace(0, 2 * math.pi, n + 1)
    pts = (np.array([cx, cy, cz])
           + r * np.outer(np.cos(t), perp)
           + r * np.outer(np.sin(t), binorm))
    return pts


# ---------------------------------------------------------------------------
# Base primitive
# ---------------------------------------------------------------------------

@dataclass
class Primitive:
    """Abstract base for all MCDISPLAY geometry primitives."""
    condition: Optional[Expr] = field(default=None, compare=False, kw_only=True)

    def evaluate(self, params: dict) -> 'Primitive':
        """Return a copy with all :class:`Expr` arguments resolved to floats."""
        raise NotImplementedError

    def to_polylines(self, params: dict | None = None) -> list[np.ndarray]:
        """Return a list of ``(N, 3)`` polyline arrays in component-local coordinates."""
        raise NotImplementedError

    def is_active(self, params: dict) -> bool:
        """Return ``True`` if this primitive's condition is satisfied (or absent)."""
        if self.condition is None:
            return True
        val = _eval(self.condition, params or {})
        return bool(val)


# ---------------------------------------------------------------------------
# Individual primitives
# ---------------------------------------------------------------------------

@dataclass
class Magnify(Primitive):
    """``magnify(what)`` — sets the magnification scale (metadata only)."""
    what: str = ''

    def evaluate(self, params):
        return Magnify(what=self.what, condition=self.condition)

    def to_polylines(self, params=None):
        return []


@dataclass
class Line(Primitive):
    """``line(x1,y1,z1, x2,y2,z2)`` — a single line segment."""
    x1: Expr = field(default_factory=Expr._null)
    y1: Expr = field(default_factory=Expr._null)
    z1: Expr = field(default_factory=Expr._null)
    x2: Expr = field(default_factory=Expr._null)
    y2: Expr = field(default_factory=Expr._null)
    z2: Expr = field(default_factory=Expr._null)

    def evaluate(self, params):
        return Line(
            _eval(self.x1, params), _eval(self.y1, params), _eval(self.z1, params),
            _eval(self.x2, params), _eval(self.y2, params), _eval(self.z2, params),
            condition=self.condition,
        )

    def to_polylines(self, params=None):
        p = params or {}
        return [np.array([
            [_eval(self.x1, p), _eval(self.y1, p), _eval(self.z1, p)],
            [_eval(self.x2, p), _eval(self.y2, p), _eval(self.z2, p)],
        ])]


@dataclass
class DashedLine(Primitive):
    """``dashed_line(x1,y1,z1, x2,y2,z2, n)`` — dashed line with *n* gaps."""
    x1: Expr = field(default_factory=Expr._null)
    y1: Expr = field(default_factory=Expr._null)
    z1: Expr = field(default_factory=Expr._null)
    x2: Expr = field(default_factory=Expr._null)
    y2: Expr = field(default_factory=Expr._null)
    z2: Expr = field(default_factory=Expr._null)
    n: Expr = field(default_factory=lambda: Expr.integer(4))

    def evaluate(self, params):
        return DashedLine(
            _eval(self.x1, params), _eval(self.y1, params), _eval(self.z1, params),
            _eval(self.x2, params), _eval(self.y2, params), _eval(self.z2, params),
            _eval(self.n, params), condition=self.condition,
        )

    def to_polylines(self, params=None):
        p = params or {}
        p1 = np.array([_eval(self.x1, p), _eval(self.y1, p), _eval(self.z1, p)])
        p2 = np.array([_eval(self.x2, p), _eval(self.y2, p), _eval(self.z2, p)])
        n = max(1, int(round(_eval(self.n, p))))
        segments = []
        for i in range(n):
            t0, t1 = i / n, (i + 0.5) / n
            segments.append(np.array([p1 + t0 * (p2 - p1), p1 + t1 * (p2 - p1)]))
        return segments


@dataclass
class Multiline(Primitive):
    """``multiline(count, x1,y1,z1,...)`` — open polyline with *count* vertices."""
    points: list[tuple[Expr, Expr, Expr]] = field(default_factory=list)

    def evaluate(self, params):
        return Multiline(
            [(_eval(x, params), _eval(y, params), _eval(z, params)) for x, y, z in self.points],
            condition=self.condition,
        )

    def to_polylines(self, params=None):
        p = params or {}
        if not self.points:
            return []
        pts = np.array([(_eval(x, p), _eval(y, p), _eval(z, p)) for x, y, z in self.points])
        return [pts]


@dataclass
class Circle(Primitive):
    """``circle(plane, cx,cy,cz, r)`` — circle in a coordinate plane."""
    plane: str = 'xy'
    cx: Expr = field(default_factory=Expr._null)
    cy: Expr = field(default_factory=Expr._null)
    cz: Expr = field(default_factory=Expr._null)
    r: Expr = field(default_factory=Expr._null)

    def evaluate(self, params):
        return Circle(self.plane,
                      _eval(self.cx, params), _eval(self.cy, params), _eval(self.cz, params),
                      _eval(self.r, params), condition=self.condition)

    def to_polylines(self, params=None):
        p = params or {}
        cx, cy, cz = _eval(self.cx, p), _eval(self.cy, p), _eval(self.cz, p)
        r = _eval(self.r, p)
        return [_circle_points(cx, cy, cz, r, self.plane)]


@dataclass
class Rectangle(Primitive):
    """``rectangle(plane, cx,cy,cz, w,h)`` — filled (closed) rectangle."""
    plane: str = 'xy'
    cx: Expr = field(default_factory=Expr._null)
    cy: Expr = field(default_factory=Expr._null)
    cz: Expr = field(default_factory=Expr._null)
    w: Expr = field(default_factory=Expr._null)
    h: Expr = field(default_factory=Expr._null)

    def evaluate(self, params):
        return Rectangle(self.plane,
                         _eval(self.cx, params), _eval(self.cy, params), _eval(self.cz, params),
                         _eval(self.w, params), _eval(self.h, params),
                         condition=self.condition)

    def to_polylines(self, params=None):
        p = params or {}
        cx, cy, cz = _eval(self.cx, p), _eval(self.cy, p), _eval(self.cz, p)
        w2, h2 = _eval(self.w, p) / 2, _eval(self.h, p) / 2
        if self.plane == 'xy':
            pts = np.array([(cx-w2,cy-h2,cz),(cx+w2,cy-h2,cz),(cx+w2,cy+h2,cz),(cx-w2,cy+h2,cz),(cx-w2,cy-h2,cz)])
        elif self.plane == 'xz':
            pts = np.array([(cx-w2,cy,cz-h2),(cx+w2,cy,cz-h2),(cx+w2,cy,cz+h2),(cx-w2,cy,cz+h2),(cx-w2,cy,cz-h2)])
        elif self.plane == 'yz':
            pts = np.array([(cx,cy-w2,cz-h2),(cx,cy+w2,cz-h2),(cx,cy+w2,cz+h2),(cx,cy-w2,cz+h2),(cx,cy-w2,cz-h2)])
        else:
            raise ValueError(f"Unknown plane '{self.plane}'")
        return [pts]


@dataclass
class Box(Primitive):
    """``box(cx,cy,cz, xw,yh,zd[, thickness, nx,ny,nz])`` — rectangular box."""
    cx: Expr = field(default_factory=Expr._null)
    cy: Expr = field(default_factory=Expr._null)
    cz: Expr = field(default_factory=Expr._null)
    xw: Expr = field(default_factory=Expr._null)
    yh: Expr = field(default_factory=Expr._null)
    zd: Expr = field(default_factory=Expr._null)

    def evaluate(self, params):
        return Box(
            _eval(self.cx, params), _eval(self.cy, params), _eval(self.cz, params),
            _eval(self.xw, params), _eval(self.yh, params), _eval(self.zd, params),
            condition=self.condition,
        )

    def to_polylines(self, params=None):
        p = params or {}
        cx, cy, cz = _eval(self.cx, p), _eval(self.cy, p), _eval(self.cz, p)
        dx, dy, dz = _eval(self.xw, p)/2, _eval(self.yh, p)/2, _eval(self.zd, p)/2
        corners = np.array([
            (cx-dx, cy-dy, cz-dz), (cx+dx, cy-dy, cz-dz),
            (cx+dx, cy+dy, cz-dz), (cx-dx, cy+dy, cz-dz),
            (cx-dx, cy-dy, cz+dz), (cx+dx, cy-dy, cz+dz),
            (cx+dx, cy+dy, cz+dz), (cx-dx, cy+dy, cz+dz),
        ])
        edges = [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]
        return [corners[list(e)] for e in edges]


@dataclass
class Sphere(Primitive):
    """``sphere(cx,cy,cz, r)`` — sphere rendered as three great circles."""
    cx: Expr = field(default_factory=Expr._null)
    cy: Expr = field(default_factory=Expr._null)
    cz: Expr = field(default_factory=Expr._null)
    r: Expr = field(default_factory=Expr._null)

    def evaluate(self, params):
        return Sphere(
            _eval(self.cx, params), _eval(self.cy, params), _eval(self.cz, params),
            _eval(self.r, params), condition=self.condition,
        )

    def to_polylines(self, params=None):
        p = params or {}
        cx, cy, cz = _eval(self.cx, p), _eval(self.cy, p), _eval(self.cz, p)
        r = _eval(self.r, p)
        return [
            _circle_points(cx, cy, cz, r, 'xy'),
            _circle_points(cx, cy, cz, r, 'xz'),
            _circle_points(cx, cy, cz, r, 'yz'),
        ]


@dataclass
class Cylinder(Primitive):
    """``cylinder(cx,cy,cz, r,h[, nx,ny,nz])`` — cylinder."""
    cx: Expr = field(default_factory=Expr._null)
    cy: Expr = field(default_factory=Expr._null)
    cz: Expr = field(default_factory=Expr._null)
    r: Expr = field(default_factory=Expr._null)
    h: Expr = field(default_factory=Expr._null)
    nx: Expr = field(default_factory=lambda: Expr.float(0))
    ny: Expr = field(default_factory=lambda: Expr.float(1))
    nz: Expr = field(default_factory=lambda: Expr.float(0))

    def evaluate(self, params):
        return Cylinder(
            _eval(self.cx, params), _eval(self.cy, params), _eval(self.cz, params),
            _eval(self.r, params), _eval(self.h, params),
            _eval(self.nx, params), _eval(self.ny, params), _eval(self.nz, params),
            condition=self.condition,
        )

    def to_polylines(self, params=None):
        p = params or {}
        cx, cy, cz = _eval(self.cx, p), _eval(self.cy, p), _eval(self.cz, p)
        r, h = _eval(self.r, p), _eval(self.h, p)
        nx, ny, nz = _eval(self.nx, p), _eval(self.ny, p), _eval(self.nz, p)
        normal = np.array([nx, ny, nz], dtype=float)
        norm = np.linalg.norm(normal)
        if norm < 1e-10:
            normal = np.array([0.0, 1.0, 0.0])
        else:
            normal /= norm
        half = 0.5 * h * normal
        c1 = np.array([cx, cy, cz]) - half
        c2 = np.array([cx, cy, cz]) + half
        cap1 = _circle_with_normal(*c1, r, *normal)
        cap2 = _circle_with_normal(*c2, r, *normal)
        # Find 4 evenly spaced points on cap1 and draw lines to cap2
        n_pts = cap1.shape[0] - 1
        lines = [np.array([cap1[i * n_pts // 4], cap2[i * n_pts // 4]]) for i in range(4)]
        return [cap1, cap2] + lines


@dataclass
class Cone(Primitive):
    """``cone(cx,cy,cz, r,h[, nx,ny,nz])`` — cone."""
    cx: Expr = field(default_factory=Expr._null)
    cy: Expr = field(default_factory=Expr._null)
    cz: Expr = field(default_factory=Expr._null)
    r: Expr = field(default_factory=Expr._null)
    h: Expr = field(default_factory=Expr._null)
    nx: Expr = field(default_factory=lambda: Expr.float(0))
    ny: Expr = field(default_factory=lambda: Expr.float(1))
    nz: Expr = field(default_factory=lambda: Expr.float(0))

    def evaluate(self, params):
        return Cone(
            _eval(self.cx, params), _eval(self.cy, params), _eval(self.cz, params),
            _eval(self.r, params), _eval(self.h, params),
            _eval(self.nx, params), _eval(self.ny, params), _eval(self.nz, params),
            condition=self.condition,
        )

    def to_polylines(self, params=None):
        p = params or {}
        cx, cy, cz = _eval(self.cx, p), _eval(self.cy, p), _eval(self.cz, p)
        r, h = _eval(self.r, p), _eval(self.h, p)
        nx, ny, nz = _eval(self.nx, p), _eval(self.ny, p), _eval(self.nz, p)
        normal = np.array([nx, ny, nz], dtype=float)
        norm = np.linalg.norm(normal)
        if norm < 1e-10:
            normal = np.array([0.0, 1.0, 0.0])
        else:
            normal /= norm
        base = np.array([cx, cy, cz])
        apex = base + h * normal
        base_ring = _circle_with_normal(*base, r, *normal)
        n_pts = base_ring.shape[0] - 1
        lines = [np.array([base_ring[i * n_pts // 4], apex]) for i in range(4)]
        return [base_ring] + lines


# ---------------------------------------------------------------------------
# Structural wrappers
# ---------------------------------------------------------------------------

@dataclass
class ConditionalBlock:
    """A group of primitives guarded by a C ``if`` condition expression."""
    condition: Expr
    body: list[Primitive | 'ConditionalBlock' | 'LoopBlock'] = field(default_factory=list)

    def to_polylines(self, params: dict | None = None) -> list[np.ndarray]:
        p = params or {}
        try:
            active = bool(_eval(self.condition, p))
        except Exception:
            active = True  # unknown condition — include by default
        if not active:
            return []
        result = []
        for prim in self.body:
            result.extend(prim.to_polylines(p))
        return result


@dataclass
class LoopBlock:
    """A ``for``/``while`` loop containing display primitives (not yet unrolled)."""
    loop_text: str
    body: list[Primitive | ConditionalBlock | 'LoopBlock'] = field(default_factory=list)

    def to_polylines(self, params: dict | None = None) -> list[np.ndarray]:
        # Best-effort: emit all body primitives without loop evaluation
        p = params or {}
        result = []
        for prim in self.body:
            result.extend(prim.to_polylines(p))
        return result

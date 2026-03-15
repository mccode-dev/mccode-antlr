"""Geometry primitives for the McCode MCDISPLAY section.

Each primitive stores its arguments as :class:`~mccode_antlr.common.expression.Expr`
objects and can:

- :meth:`evaluate` — substitute a parameter dict and return a resolved copy
  with all :class:`~mccode_antlr.common.expression.Expr` values replaced by
  ``float``.
- :meth:`to_polylines` — return a list of ``(N, 3)`` numpy arrays (open or
  closed polylines) suitable for 3-D rendering.
- :meth:`to_mesh` — return ``(vertices, faces)`` arrays for solid-surface
  rendering, or ``None`` for wire-only primitives.
"""
from __future__ import annotations

import json
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

    def to_mesh(self, params: dict | None = None) -> tuple[np.ndarray, np.ndarray] | None:
        """Return ``(vertices, faces)`` for solid-surface rendering, or ``None``.

        vertices : (V, 3) float32 array of 3-D positions.
        faces    : (F, 3) int32 array of triangle vertex indices.
        Wire-only primitives return ``None``.
        """
        return None

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
    """``box(cx,cy,cz, xw,yh,zd[, thickness[, nx,ny,nz]])`` — rectangular box.

    The new McCode overhaul adds an optional *thickness* (hollow-wall depth) and an
    orientation normal (*nx*, *ny*, *nz*).  When *thickness* is zero or absent the
    box is rendered as 12 wire edges, otherwise a second inner box is also drawn.
    The normal is currently used only by the 3-D renderer; the wire representation
    always uses the legacy axis-aligned form.
    """
    cx: Expr = field(default_factory=Expr._null)
    cy: Expr = field(default_factory=Expr._null)
    cz: Expr = field(default_factory=Expr._null)
    xw: Expr = field(default_factory=Expr._null)
    yh: Expr = field(default_factory=Expr._null)
    zd: Expr = field(default_factory=Expr._null)
    thickness: Expr = field(default_factory=lambda: Expr.float(0))
    nx: Expr = field(default_factory=lambda: Expr.float(0))
    ny: Expr = field(default_factory=lambda: Expr.float(1))
    nz: Expr = field(default_factory=lambda: Expr.float(0))

    def evaluate(self, params):
        return Box(
            _eval(self.cx, params), _eval(self.cy, params), _eval(self.cz, params),
            _eval(self.xw, params), _eval(self.yh, params), _eval(self.zd, params),
            _eval(self.thickness, params),
            _eval(self.nx, params), _eval(self.ny, params), _eval(self.nz, params),
            condition=self.condition,
        )

    def _corners(self, cx, cy, cz, dx, dy, dz):
        return np.array([
            (cx-dx, cy-dy, cz-dz), (cx+dx, cy-dy, cz-dz),
            (cx+dx, cy+dy, cz-dz), (cx-dx, cy+dy, cz-dz),
            (cx-dx, cy-dy, cz+dz), (cx+dx, cy-dy, cz+dz),
            (cx+dx, cy+dy, cz+dz), (cx-dx, cy+dy, cz+dz),
        ])

    def to_polylines(self, params=None):
        p = params or {}
        cx, cy, cz = _eval(self.cx, p), _eval(self.cy, p), _eval(self.cz, p)
        dx, dy, dz = _eval(self.xw, p)/2, _eval(self.yh, p)/2, _eval(self.zd, p)/2
        edges = [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]
        result = [self._corners(cx, cy, cz, dx, dy, dz)[list(e)] for e in edges]
        t = _eval(self.thickness, p)
        if t:
            inner = self._corners(cx, cy, cz, max(0, dx-t/2), max(0, dy-t/2), max(0, dz-t/2))
            result += [inner[list(e)] for e in edges]
        return result

    def to_mesh(self, params=None):
        p = params or {}
        cx, cy, cz = _eval(self.cx, p), _eval(self.cy, p), _eval(self.cz, p)
        dx, dy, dz = _eval(self.xw, p)/2, _eval(self.yh, p)/2, _eval(self.zd, p)/2
        verts = self._corners(cx, cy, cz, dx, dy, dz).astype(np.float32)
        # 6 faces, each split into 2 triangles
        faces = np.array([
            [0,1,2],[0,2,3],  # -z face
            [4,6,5],[4,7,6],  # +z face
            [0,4,5],[0,5,1],  # -y face
            [2,6,7],[2,7,3],  # +y face
            [0,3,7],[0,7,4],  # -x face
            [1,5,6],[1,6,2],  # +x face
        ], dtype=np.int32)
        return verts, faces


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

    def to_mesh(self, params=None):
        p = params or {}
        cx, cy, cz = _eval(self.cx, p), _eval(self.cy, p), _eval(self.cz, p)
        r = _eval(self.r, p)
        stacks, slices = 16, 32
        verts = []
        for i in range(stacks + 1):
            phi = math.pi * i / stacks
            for j in range(slices):
                theta = 2 * math.pi * j / slices
                x = cx + r * math.sin(phi) * math.cos(theta)
                y = cy + r * math.cos(phi)
                z = cz + r * math.sin(phi) * math.sin(theta)
                verts.append((x, y, z))
        faces = []
        for i in range(stacks):
            for j in range(slices):
                a = i * slices + j
                b = i * slices + (j + 1) % slices
                c = (i + 1) * slices + (j + 1) % slices
                d = (i + 1) * slices + j
                faces.append((a, b, c))
                faces.append((a, c, d))
        return np.array(verts, dtype=np.float32), np.array(faces, dtype=np.int32)


@dataclass
class Cylinder(Primitive):
    """``cylinder(cx,cy,cz, r,h[, thickness[, nx,ny,nz]])`` — cylinder.

    The new McCode overhaul adds an optional *thickness* for hollow cylinders.
    The axis orientation (*nx*, *ny*, *nz*) was already supported.
    """
    cx: Expr = field(default_factory=Expr._null)
    cy: Expr = field(default_factory=Expr._null)
    cz: Expr = field(default_factory=Expr._null)
    r: Expr = field(default_factory=Expr._null)
    h: Expr = field(default_factory=Expr._null)
    thickness: Expr = field(default_factory=lambda: Expr.float(0))
    nx: Expr = field(default_factory=lambda: Expr.float(0))
    ny: Expr = field(default_factory=lambda: Expr.float(1))
    nz: Expr = field(default_factory=lambda: Expr.float(0))

    def evaluate(self, params):
        return Cylinder(
            _eval(self.cx, params), _eval(self.cy, params), _eval(self.cz, params),
            _eval(self.r, params), _eval(self.h, params),
            _eval(self.thickness, params),
            _eval(self.nx, params), _eval(self.ny, params), _eval(self.nz, params),
            condition=self.condition,
        )

    def _axis_frame(self, nx, ny, nz):
        normal = np.array([nx, ny, nz], dtype=float)
        norm = np.linalg.norm(normal)
        if norm < 1e-10:
            normal = np.array([0.0, 1.0, 0.0])
        else:
            normal /= norm
        return normal

    def to_polylines(self, params=None):
        p = params or {}
        cx, cy, cz = _eval(self.cx, p), _eval(self.cy, p), _eval(self.cz, p)
        r, h = _eval(self.r, p), _eval(self.h, p)
        nx, ny, nz = _eval(self.nx, p), _eval(self.ny, p), _eval(self.nz, p)
        normal = self._axis_frame(nx, ny, nz)
        half = 0.5 * h * normal
        c1 = np.array([cx, cy, cz]) - half
        c2 = np.array([cx, cy, cz]) + half
        cap1 = _circle_with_normal(*c1, r, *normal)
        cap2 = _circle_with_normal(*c2, r, *normal)
        n_pts = cap1.shape[0] - 1
        lines = [np.array([cap1[i * n_pts // 4], cap2[i * n_pts // 4]]) for i in range(4)]
        return [cap1, cap2] + lines

    def to_mesh(self, params=None):
        p = params or {}
        cx, cy, cz = _eval(self.cx, p), _eval(self.cy, p), _eval(self.cz, p)
        r, h = _eval(self.r, p), _eval(self.h, p)
        nx, ny, nz = _eval(self.nx, p), _eval(self.ny, p), _eval(self.nz, p)
        normal = self._axis_frame(nx, ny, nz)
        half = 0.5 * h * normal
        centre = np.array([cx, cy, cz])
        c1, c2 = centre - half, centre + half
        slices = 32
        # Build perimeter points for both caps (without the closing duplicate)
        ring1 = _circle_with_normal(*c1, r, *normal, n=slices)[:-1]
        ring2 = _circle_with_normal(*c2, r, *normal, n=slices)[:-1]
        verts = np.vstack([ring1, ring2, [c1], [c2]]).astype(np.float32)
        cap1_centre = slices * 2      # index of c1
        cap2_centre = slices * 2 + 1  # index of c2
        faces = []
        for i in range(slices):
            j = (i + 1) % slices
            # lateral quad → 2 triangles
            faces.append((i, j, slices + j))
            faces.append((i, slices + j, slices + i))
            # bottom cap (winding inward)
            faces.append((cap1_centre, j, i))
            # top cap
            faces.append((cap2_centre, slices + i, slices + j))
        return verts, np.array(faces, dtype=np.int32)


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

    def to_mesh(self, params=None):
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
        slices = 32
        base = np.array([cx, cy, cz])
        apex = base + h * normal
        ring = _circle_with_normal(*base, r, *normal, n=slices)[:-1]
        verts = np.vstack([ring, [apex], [base]]).astype(np.float32)
        apex_idx = slices
        base_centre_idx = slices + 1
        faces = []
        for i in range(slices):
            j = (i + 1) % slices
            faces.append((i, j, apex_idx))          # lateral
            faces.append((base_centre_idx, j, i))   # base cap
        return verts, np.array(faces, dtype=np.int32)


# ---------------------------------------------------------------------------
# New primitives (McDisplay overhaul)
# ---------------------------------------------------------------------------

@dataclass
class CircleNormal(Primitive):
    """``Circle(x,y,z,r,nx,ny,nz)`` / ``new_circle(…)`` — circle with arbitrary normal.

    Unlike :class:`Circle`, the plane is specified by a normal vector rather than
    a plane string.  Corresponds to ``mcdis_Circle`` / ``mcdis_new_circle`` in C.
    """
    cx: Expr = field(default_factory=Expr._null)
    cy: Expr = field(default_factory=Expr._null)
    cz: Expr = field(default_factory=Expr._null)
    r: Expr = field(default_factory=Expr._null)
    nx: Expr = field(default_factory=lambda: Expr.float(0))
    ny: Expr = field(default_factory=lambda: Expr.float(1))
    nz: Expr = field(default_factory=lambda: Expr.float(0))

    def evaluate(self, params):
        return CircleNormal(
            _eval(self.cx, params), _eval(self.cy, params), _eval(self.cz, params),
            _eval(self.r, params),
            _eval(self.nx, params), _eval(self.ny, params), _eval(self.nz, params),
            condition=self.condition,
        )

    def to_polylines(self, params=None):
        p = params or {}
        cx, cy, cz = _eval(self.cx, p), _eval(self.cy, p), _eval(self.cz, p)
        r = _eval(self.r, p)
        nx, ny, nz = _eval(self.nx, p), _eval(self.ny, p), _eval(self.nz, p)
        return [_circle_with_normal(cx, cy, cz, r, nx, ny, nz)]


@dataclass
class Disc(Primitive):
    """``disc(x,y,z,r,nx,ny,nz)`` — filled disc with an arbitrary normal.

    Corresponds to ``mcdis_disc`` in C.  Wire representation is the perimeter
    circle; mesh representation is a fan-triangulated flat disc.
    """
    cx: Expr = field(default_factory=Expr._null)
    cy: Expr = field(default_factory=Expr._null)
    cz: Expr = field(default_factory=Expr._null)
    r: Expr = field(default_factory=Expr._null)
    nx: Expr = field(default_factory=lambda: Expr.float(0))
    ny: Expr = field(default_factory=lambda: Expr.float(1))
    nz: Expr = field(default_factory=lambda: Expr.float(0))

    def evaluate(self, params):
        return Disc(
            _eval(self.cx, params), _eval(self.cy, params), _eval(self.cz, params),
            _eval(self.r, params),
            _eval(self.nx, params), _eval(self.ny, params), _eval(self.nz, params),
            condition=self.condition,
        )

    def to_polylines(self, params=None):
        p = params or {}
        cx, cy, cz = _eval(self.cx, p), _eval(self.cy, p), _eval(self.cz, p)
        r = _eval(self.r, p)
        nx, ny, nz = _eval(self.nx, p), _eval(self.ny, p), _eval(self.nz, p)
        return [_circle_with_normal(cx, cy, cz, r, nx, ny, nz)]

    def to_mesh(self, params=None):
        p = params or {}
        cx, cy, cz = _eval(self.cx, p), _eval(self.cy, p), _eval(self.cz, p)
        r = _eval(self.r, p)
        nx, ny, nz = _eval(self.nx, p), _eval(self.ny, p), _eval(self.nz, p)
        slices = 32
        ring = _circle_with_normal(cx, cy, cz, r, nx, ny, nz, n=slices)[:-1]
        centre_idx = slices
        verts = np.vstack([ring, [[cx, cy, cz]]]).astype(np.float32)
        faces = [(centre_idx, (i + 1) % slices, i) for i in range(slices)]
        return verts, np.array(faces, dtype=np.int32)


@dataclass
class Annulus(Primitive):
    """``annulus(x,y,z,r_outer,r_inner,nx,ny,nz)`` — annular disc with arbitrary normal.

    Corresponds to ``mcdis_annulus`` in C.  Wire representation is two concentric
    circles; mesh representation is a ring of quads.
    """
    cx: Expr = field(default_factory=Expr._null)
    cy: Expr = field(default_factory=Expr._null)
    cz: Expr = field(default_factory=Expr._null)
    r_outer: Expr = field(default_factory=Expr._null)
    r_inner: Expr = field(default_factory=Expr._null)
    nx: Expr = field(default_factory=lambda: Expr.float(0))
    ny: Expr = field(default_factory=lambda: Expr.float(1))
    nz: Expr = field(default_factory=lambda: Expr.float(0))

    def evaluate(self, params):
        return Annulus(
            _eval(self.cx, params), _eval(self.cy, params), _eval(self.cz, params),
            _eval(self.r_outer, params), _eval(self.r_inner, params),
            _eval(self.nx, params), _eval(self.ny, params), _eval(self.nz, params),
            condition=self.condition,
        )

    def to_polylines(self, params=None):
        p = params or {}
        cx, cy, cz = _eval(self.cx, p), _eval(self.cy, p), _eval(self.cz, p)
        ro = _eval(self.r_outer, p)
        ri = _eval(self.r_inner, p)
        nx, ny, nz = _eval(self.nx, p), _eval(self.ny, p), _eval(self.nz, p)
        return [
            _circle_with_normal(cx, cy, cz, ro, nx, ny, nz),
            _circle_with_normal(cx, cy, cz, ri, nx, ny, nz),
        ]

    def to_mesh(self, params=None):
        p = params or {}
        cx, cy, cz = _eval(self.cx, p), _eval(self.cy, p), _eval(self.cz, p)
        ro = _eval(self.r_outer, p)
        ri = _eval(self.r_inner, p)
        nx, ny, nz = _eval(self.nx, p), _eval(self.ny, p), _eval(self.nz, p)
        slices = 32
        outer = _circle_with_normal(cx, cy, cz, ro, nx, ny, nz, n=slices)[:-1]
        inner = _circle_with_normal(cx, cy, cz, ri, nx, ny, nz, n=slices)[:-1]
        verts = np.vstack([outer, inner]).astype(np.float32)
        faces = []
        for i in range(slices):
            j = (i + 1) % slices
            # outer[i], outer[j], inner[j], inner[i] → 2 triangles
            faces.append((i, j, slices + j))
            faces.append((i, slices + j, slices + i))
        return verts, np.array(faces, dtype=np.int32)


@dataclass
class Polygon(Primitive):
    """``polygon(count, x1,y1,z1,…)`` — closed flat polygon.

    Corresponds to ``mcdis_polygon`` in C.  Wire representation closes the path;
    mesh representation is fan-triangulated from the centroid.
    """
    points: list[tuple[Expr, Expr, Expr]] = field(default_factory=list)

    def evaluate(self, params):
        return Polygon(
            [(_eval(x, params), _eval(y, params), _eval(z, params)) for x, y, z in self.points],
            condition=self.condition,
        )

    def to_polylines(self, params=None):
        p = params or {}
        if not self.points:
            return []
        pts = np.array([(_eval(x, p), _eval(y, p), _eval(z, p)) for x, y, z in self.points])
        # close the polygon
        return [np.vstack([pts, pts[:1]])]

    def to_mesh(self, params=None):
        p = params or {}
        if len(self.points) < 3:
            return None
        pts = np.array([(_eval(x, p), _eval(y, p), _eval(z, p)) for x, y, z in self.points],
                       dtype=np.float32)
        centroid = pts.mean(axis=0)
        n = len(pts)
        verts = np.vstack([pts, [centroid]]).astype(np.float32)
        centre_idx = n
        faces = [(centre_idx, (i + 1) % n, i) for i in range(n)]
        return verts, np.array(faces, dtype=np.int32)


@dataclass
class Polyhedron(Primitive):
    """``polyhedron(json_str)`` — 3-D polyhedron defined by a JSON string.

    The JSON format produced by ``mcdis_polygon`` (and usable directly) is::

        { "vertices": [[x,y,z], ...],
          "faces":    [{"face": [i, j, k]}, ...] }

    Corresponds to ``mcdis_polyhedron`` in C.
    """
    json_str: str = ''
    _vertices: np.ndarray = field(default=None, init=False, compare=False, repr=False)
    _faces: np.ndarray = field(default=None, init=False, compare=False, repr=False)

    def __post_init__(self):
        self._parse()

    def _parse(self):
        if not self.json_str:
            self._vertices = np.zeros((0, 3), dtype=np.float32)
            self._faces = np.zeros((0, 3), dtype=np.int32)
            return
        try:
            # Unescape C-style \" → " that ANTLR preserves from string literals
            json_text = self.json_str.replace('\\"', '"')
            data = json.loads(json_text)
            self._vertices = np.array(data['vertices'], dtype=np.float32)
            self._faces = np.array(
                [f['face'] for f in data['faces']], dtype=np.int32
            )
        except Exception:
            self._vertices = np.zeros((0, 3), dtype=np.float32)
            self._faces = np.zeros((0, 3), dtype=np.int32)

    def evaluate(self, params):
        result = Polyhedron(self.json_str, condition=self.condition)
        return result

    def to_polylines(self, params=None):
        if self._vertices is None or len(self._faces) == 0:
            return []
        lines = []
        for face in self._faces:
            pts = self._vertices[list(face) + [face[0]]]
            lines.append(pts)
        return lines

    def to_mesh(self, params=None):
        if self._vertices is None or len(self._vertices) == 0:
            return None
        return self._vertices.copy(), self._faces.copy()


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

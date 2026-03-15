"""Tests for the mccode_antlr.display submodule.

Covers:
- parse_display_source() for all key primitive types
- Local variable resolution inside DISPLAY source
- Conditional block parsing
- Numeric polyline output (to_polylines)
- ComponentDisplay on a hand-crafted Comp
- InstrumentDisplay (basic smoke test)
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from mccode_antlr.common import RawC
from mccode_antlr.common.expression import Expr
from mccode_antlr.comp import Comp
from mccode_antlr.display import (
    Box,
    Circle,
    ComponentDisplay,
    ConditionalBlock,
    Cylinder,
    DashedLine,
    Line,
    Multiline,
    Rectangle,
    Sphere,
    parse_display_source,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rawc(src: str) -> RawC:
    return RawC(filename=None, line=0, source=src)


def _comp_with_display(src: str) -> Comp:
    return Comp(name='TestComp', display=(_rawc(src),))


# ---------------------------------------------------------------------------
# parse_display_source — individual primitive parsing
# ---------------------------------------------------------------------------

class TestParseCircle:
    def test_literal(self):
        prims = parse_display_source('circle("xy", 0, 0, 0, 0.1);')
        assert len(prims) == 1
        c = prims[0]
        assert isinstance(c, Circle)
        assert c.plane == 'xy'
        pls = c.to_polylines()
        assert len(pls) == 1
        arr = pls[0]
        assert arr.shape == (25, 3)
        # All z values should be 0
        np.testing.assert_allclose(arr[:, 2], 0.0)
        # All points at radius 0.1 from centre
        dists = np.sqrt(arr[:, 0] ** 2 + arr[:, 1] ** 2)
        np.testing.assert_allclose(dists, 0.1, atol=1e-10)
        # First and last point coincide (closed)
        np.testing.assert_allclose(arr[0], arr[-1], atol=1e-14)

    def test_symbolic_r(self):
        prims = parse_display_source('circle("xz", 0, 0, 0, r);')
        c = prims[0]
        assert isinstance(c, Circle)
        assert c.plane == 'xz'
        pls = c.to_polylines({'r': 0.2})
        dists = np.sqrt(pls[0][:, 0] ** 2 + pls[0][:, 2] ** 2)
        np.testing.assert_allclose(dists, 0.2, atol=1e-10)

    def test_yz_plane(self):
        prims = parse_display_source('circle("yz", 0, 0, 0, 0.05);')
        c = prims[0]
        pls = c.to_polylines()
        # x coords all zero
        np.testing.assert_allclose(pls[0][:, 0], 0.0)


class TestParseLine:
    def test_literal(self):
        prims = parse_display_source('line(0, 0, -0.5, 0, 0, 0.5);')
        assert len(prims) == 1
        ln = prims[0]
        assert isinstance(ln, Line)
        pls = ln.to_polylines()
        assert len(pls) == 1
        assert pls[0].shape == (2, 3)
        np.testing.assert_allclose(pls[0][0], [0, 0, -0.5])
        np.testing.assert_allclose(pls[0][1], [0, 0, 0.5])

    def test_symbolic(self):
        prims = parse_display_source('line(-xw/2, 0, 0, xw/2, 0, 0);')
        ln = prims[0]
        pls = ln.to_polylines({'xw': 0.1})
        np.testing.assert_allclose(pls[0][0, 0], -0.05, atol=1e-10)
        np.testing.assert_allclose(pls[0][1, 0], 0.05, atol=1e-10)


class TestParseDashedLine:
    def test_literal(self):
        prims = parse_display_source('dashed_line(0, 0, -1, 0, 0, 1, 4);')
        assert len(prims) == 1
        dl = prims[0]
        assert isinstance(dl, DashedLine)
        pls = dl.to_polylines()
        # 4 dashes → 4 segments → 4 polylines of 2 pts each
        assert len(pls) == 4
        for seg in pls:
            assert seg.shape == (2, 3)


class TestParseMultiline:
    def test_literal(self):
        src = 'multiline(3, 0,0,0, 1,0,0, 1,1,0);'
        prims = parse_display_source(src)
        assert len(prims) == 1
        ml = prims[0]
        assert isinstance(ml, Multiline)
        pls = ml.to_polylines()
        assert len(pls) == 1
        assert pls[0].shape == (3, 3)
        np.testing.assert_allclose(pls[0][2], [1, 1, 0])


class TestParseBox:
    def test_literal(self):
        prims = parse_display_source('box(0, 0, 0, 0.1, 0.2, 0.3);')
        assert len(prims) == 1
        b = prims[0]
        assert isinstance(b, Box)
        pls = b.to_polylines()
        assert len(pls) == 12  # 12 edges


class TestParseRectangle:
    def test_xy_plane(self):
        prims = parse_display_source('rectangle("xy", 0, 0, 0, 0.1, 0.2);')
        r = prims[0]
        assert isinstance(r, Rectangle)
        pls = r.to_polylines()
        assert len(pls) == 1
        assert pls[0].shape == (5, 3)  # closed rect


class TestParseSphere:
    def test_literal(self):
        prims = parse_display_source('sphere(0, 0, 0, 0.1);')
        s = prims[0]
        assert isinstance(s, Sphere)
        pls = s.to_polylines()
        assert len(pls) == 3  # 3 great circles


class TestParseCylinder:
    def test_literal(self):
        # cylinder(cx, cy, cz, r, h, nx, ny, nz)
        prims = parse_display_source('cylinder(0, 0, 0, 0.1, 0.5, 0, 1, 0);')
        c = prims[0]
        assert isinstance(c, Cylinder)
        pls = c.to_polylines()
        # 2 end caps + 4 connecting lines
        assert len(pls) == 6


# ---------------------------------------------------------------------------
# Local variable resolution
# ---------------------------------------------------------------------------

class TestLocalVariables:
    def test_simple_local(self):
        src = 'double t = 0.5; line(0, 0, -t, 0, 0, t);'
        prims = parse_display_source(src)
        assert len(prims) == 1
        pls = prims[0].to_polylines()
        np.testing.assert_allclose(pls[0][0, 2], -0.5, atol=1e-10)
        np.testing.assert_allclose(pls[0][1, 2], 0.5, atol=1e-10)

    def test_expression_local(self):
        src = 'double h2 = yh/2; line(0, -h2, 0, 0, h2, 0);'
        prims = parse_display_source(src)
        assert len(prims) == 1
        pls = prims[0].to_polylines({'yh': 0.4})
        np.testing.assert_allclose(pls[0][0, 1], -0.2, atol=1e-10)
        np.testing.assert_allclose(pls[0][1, 1], 0.2, atol=1e-10)

    def test_multiple_primitives_share_local(self):
        src = 'double r = 0.05; circle("xy", 0, 0, -r, r); circle("xy", 0, 0, r, r);'
        prims = parse_display_source(src)
        assert len(prims) == 2
        # Both circles should evaluate without error
        for p in prims:
            pls = p.to_polylines()
            assert pls[0].shape == (25, 3)


# ---------------------------------------------------------------------------
# Conditional blocks
# ---------------------------------------------------------------------------

class TestConditionalBlock:
    def test_parsed_as_conditional(self):
        src = 'if (show) { circle("xy", 0, 0, 0, 0.1); }'
        prims = parse_display_source(src)
        assert len(prims) == 1
        blk = prims[0]
        assert isinstance(blk, ConditionalBlock)
        assert len(blk.body) == 1
        assert isinstance(blk.body[0], Circle)

    def test_condition_expr(self):
        src = 'if (show) { circle("xy", 0, 0, 0, 0.1); }'
        prims = parse_display_source(src)
        cond = prims[0].condition
        assert isinstance(cond, Expr)
        assert cond.is_id  # symbolic variable 'show'


# ---------------------------------------------------------------------------
# ComponentDisplay
# ---------------------------------------------------------------------------

class TestComponentDisplay:
    def test_parse_single_primitive(self):
        comp = _comp_with_display('circle("xy", 0, 0, 0, r);')
        cd = ComponentDisplay(comp)
        primitives = cd.primitives
        assert len(primitives) == 1
        assert isinstance(primitives[0], Circle)

    def test_to_polylines_no_params(self):
        comp = _comp_with_display('circle("xy", 0, 0, 0, 0.1);')
        cd = ComponentDisplay(comp)
        pls = cd.to_polylines()
        assert len(pls) == 1
        assert pls[0].shape == (25, 3)

    def test_to_polylines_with_params(self):
        comp = _comp_with_display('line(-xw/2, 0, 0, xw/2, 0, 0);')
        cd = ComponentDisplay(comp)
        pls = cd.to_polylines({'xw': 0.06})
        assert len(pls) == 1
        np.testing.assert_allclose(pls[0][0, 0], -0.03, atol=1e-10)

    def test_multiple_raw_blocks(self):
        comp = Comp(
            name='TestComp',
            display=(
                _rawc('circle("xy", 0, 0, -0.5, 0.1);'),
                _rawc('circle("xy", 0, 0,  0.5, 0.1);'),
            ),
        )
        cd = ComponentDisplay(comp)
        assert len(cd.primitives) == 2

    def test_empty_display(self):
        comp = Comp(name='Empty')
        cd = ComponentDisplay(comp)
        assert cd.primitives == []
        assert cd.to_polylines() == []


# ---------------------------------------------------------------------------
# New imports needed for new tests
# ---------------------------------------------------------------------------
# (imported at module level so pytest can collect them)
from mccode_antlr.display import (
    Annulus,
    CircleNormal,
    Cone,
    Disc,
    Magnify,
    Polygon,
    Polyhedron,
)


# ===========================================================================
# Dual-name parity: shorthand macro == mcdis_* direct call
# ===========================================================================

class TestDualNameParity:
    """Every primitive recognised by its shorthand name must also be parsed
    identically when prefixed with ``mcdis_``."""

    def test_line(self):
        a = parse_display_source('line(0,0,0, 1,1,1);')
        b = parse_display_source('mcdis_line(0,0,0, 1,1,1);')
        assert len(a) == len(b) == 1
        assert type(a[0]) is type(b[0])
        np.testing.assert_allclose(
            a[0].to_polylines(), b[0].to_polylines()
        )

    def test_circle(self):
        a = parse_display_source('circle("xy", 0, 0, 0, 0.1);')
        b = parse_display_source('mcdis_circle("xy", 0, 0, 0, 0.1);')
        assert type(a[0]) is type(b[0])
        np.testing.assert_allclose(
            a[0].to_polylines(), b[0].to_polylines()
        )

    def test_Circle_normal(self):
        a = parse_display_source('Circle(0, 0, 0, 0.1, 0, 1, 0);')
        b = parse_display_source('mcdis_Circle(0, 0, 0, 0.1, 0, 1, 0);')
        assert type(a[0]) is type(b[0]) is CircleNormal
        np.testing.assert_allclose(
            a[0].to_polylines(), b[0].to_polylines()
        )

    def test_new_circle(self):
        a = parse_display_source('new_circle(0, 0, 0, 0.1, 0, 1, 0);')
        b = parse_display_source('mcdis_new_circle(0, 0, 0, 0.1, 0, 1, 0);')
        assert type(a[0]) is type(b[0]) is CircleNormal

    def test_disc(self):
        a = parse_display_source('disc(0, 0, 0, 0.1, 0, 1, 0);')
        b = parse_display_source('mcdis_disc(0, 0, 0, 0.1, 0, 1, 0);')
        assert type(a[0]) is type(b[0]) is Disc

    def test_annulus(self):
        a = parse_display_source('annulus(0, 0, 0, 0.2, 0.1, 0, 1, 0);')
        b = parse_display_source('mcdis_annulus(0, 0, 0, 0.2, 0.1, 0, 1, 0);')
        assert type(a[0]) is type(b[0]) is Annulus

    def test_box(self):
        a = parse_display_source('box(0,0,0, 0.1,0.2,0.3);')
        b = parse_display_source('mcdis_box(0,0,0, 0.1,0.2,0.3, 0, 0,1,0);')
        assert type(a[0]) is type(b[0]) is Box

    def test_sphere(self):
        a = parse_display_source('sphere(0,0,0, 0.1);')
        b = parse_display_source('mcdis_sphere(0,0,0, 0.1);')
        assert type(a[0]) is type(b[0])

    def test_cylinder(self):
        a = parse_display_source('cylinder(0,0,0, 0.1,0.5, 0,1,0);')
        b = parse_display_source('mcdis_cylinder(0,0,0, 0.1,0.5, 0, 0,1,0);')
        assert type(a[0]) is type(b[0]) is Cylinder

    def test_cone(self):
        a = parse_display_source('cone(0,0,0, 0.1,0.5, 0,1,0);')
        b = parse_display_source('mcdis_cone(0,0,0, 0.1,0.5, 0,1,0);')
        assert type(a[0]) is type(b[0])

    def test_polygon(self):
        src_short = 'polygon(3, 0,0,0, 1,0,0, 0,1,0);'
        src_full  = 'mcdis_polygon(3, 0,0,0, 1,0,0, 0,1,0);'
        a = parse_display_source(src_short)
        b = parse_display_source(src_full)
        assert type(a[0]) is type(b[0]) is Polygon


# ===========================================================================
# New primitives — round-trip parse + to_polylines + to_mesh
# ===========================================================================

class TestCircleNormal:
    def test_parse_Circle(self):
        prims = parse_display_source('Circle(0, 0, 0, 0.5, 0, 1, 0);')
        assert len(prims) == 1
        c = prims[0]
        assert isinstance(c, CircleNormal)

    def test_parse_new_circle(self):
        prims = parse_display_source('new_circle(0, 0, 0, 0.5, 1, 0, 0);')
        assert isinstance(prims[0], CircleNormal)

    def test_to_polylines_shape(self):
        c = CircleNormal(0, 0, 0, 0.5, 0, 1, 0)
        pls = c.to_polylines()
        assert len(pls) == 1
        assert pls[0].shape == (25, 3)  # n=24 + 1 closing point

    def test_to_mesh_returns_none(self):
        c = CircleNormal(0, 0, 0, 0.5, 0, 1, 0)
        assert c.to_mesh() is None


class TestDisc:
    def test_parse(self):
        prims = parse_display_source('disc(0, 0, 0, 0.3, 0, 1, 0);')
        assert isinstance(prims[0], Disc)

    def test_to_polylines_is_circle(self):
        d = Disc(0, 0, 0, 0.3, 0, 1, 0)
        pls = d.to_polylines()
        assert len(pls) == 1

    def test_to_mesh(self):
        d = Disc(0, 0, 0, 0.3, 0, 1, 0)
        result = d.to_mesh()
        assert result is not None
        verts, faces = result
        assert verts.shape[1] == 3
        assert faces.shape[1] == 3
        assert verts.dtype == np.float32
        assert faces.dtype == np.int32
        # fan triangulation: slices triangles, each sharing the centre vertex
        assert len(faces) == 32


class TestAnnulus:
    def test_parse(self):
        prims = parse_display_source('annulus(0, 0, 0, 0.4, 0.2, 0, 1, 0);')
        a = prims[0]
        assert isinstance(a, Annulus)

    def test_to_polylines_two_circles(self):
        a = Annulus(0, 0, 0, 0.4, 0.2, 0, 1, 0)
        pls = a.to_polylines()
        assert len(pls) == 2  # outer + inner

    def test_to_mesh(self):
        a = Annulus(0, 0, 0, 0.4, 0.2, 0, 1, 0)
        verts, faces = a.to_mesh()
        assert verts.shape[1] == 3
        assert faces.shape[1] == 3
        # ring mesh: 2 * slices quads → 2 * 2 * slices triangles
        assert len(faces) == 2 * 32


class TestPolygon:
    def test_parse(self):
        src = 'polygon(3, 0,0,0, 1,0,0, 0.5,1,0);'
        prims = parse_display_source(src)
        p = prims[0]
        assert isinstance(p, Polygon)
        assert len(p.points) == 3

    def test_to_polylines_closed(self):
        p = Polygon([(0,0,0), (1,0,0), (0,1,0)])
        pls = p.to_polylines()
        assert len(pls) == 1
        arr = pls[0]
        # closed: last row == first row
        np.testing.assert_allclose(arr[0], arr[-1])

    def test_to_mesh_triangle(self):
        p = Polygon([(0,0,0), (1,0,0), (0,1,0)])
        verts, faces = p.to_mesh()
        # 3 points + 1 centroid
        assert len(verts) == 4
        assert len(faces) == 3  # 3 fan triangles


class TestPolyhedron:
    # JSON with C-style escaped inner quotes, as ANTLR extracts from a string literal
    _JSON = (
        '{"vertices": [[0,0,0],[1,0,0],[0,1,0],[0,0,1]],'
        ' "faces": [{"face": [0,1,2]}, {"face": [0,1,3]},'
        '           {"face": [0,2,3]}, {"face": [1,2,3]}]}'
    )
    # C-source form: inner " are escaped as \" so the lexer sees a valid string literal
    _C_JSON = _JSON.replace('"', '\\"')

    def test_parse(self):
        prims = parse_display_source(f'polyhedron("{self._C_JSON}");')
        p = prims[0]
        assert isinstance(p, Polyhedron)

    def test_to_mesh_shape(self):
        p = Polyhedron(self._JSON)
        verts, faces = p.to_mesh()
        assert verts.shape == (4, 3)
        assert faces.shape == (4, 3)

    def test_to_polylines_count(self):
        p = Polyhedron(self._JSON)
        pls = p.to_polylines()
        # one closed loop per face
        assert len(pls) == 4

    def test_invalid_json_graceful(self):
        p = Polyhedron('not json')
        assert p.to_mesh() is None
        assert p.to_polylines() == []


# ===========================================================================
# Updated Box signature — backward and forward compatibility
# ===========================================================================

class TestBoxSignatureCompat:
    def test_6_arg_old_form(self):
        """Old 6-arg form still works and produces 12 wire edges."""
        prims = parse_display_source('box(0, 0, 0, 0.1, 0.2, 0.3);')
        b = prims[0]
        assert isinstance(b, Box)
        assert len(b.to_polylines()) == 12

    def test_10_arg_new_form(self):
        """New 10-arg form with thickness and normal is parsed."""
        prims = parse_display_source('box(0, 0, 0, 0.1, 0.2, 0.3, 0.01, 0, 1, 0);')
        b = prims[0]
        assert isinstance(b, Box)
        # With non-zero thickness the inner box is also drawn: 24 edges
        assert len(b.to_polylines()) == 24

    def test_to_mesh(self):
        b = Box(0, 0, 0, 0.1, 0.2, 0.3)
        verts, faces = b.to_mesh()
        assert verts.shape == (8, 3)
        assert faces.shape == (12, 3)  # 6 faces × 2 triangles

    def test_legacy_box_parse(self):
        prims = parse_display_source('legacy_box(0, 0, 0, 0.1, 0.2, 0.3);')
        assert isinstance(prims[0], Box)

    def test_mcdis_legacy_box_parse(self):
        prims = parse_display_source('mcdis_legacy_box(0, 0, 0, 0.1, 0.2, 0.3);')
        assert isinstance(prims[0], Box)


# ===========================================================================
# Updated Cylinder signature — backward and forward compatibility
# ===========================================================================

class TestCylinderSignatureCompat:
    def test_5_arg_old_form(self):
        """Old 5-arg form (no normal) still parses."""
        prims = parse_display_source('cylinder(0, 0, 0, 0.05, 0.5);')
        assert isinstance(prims[0], Cylinder)

    def test_8_arg_old_form_with_normal(self):
        """Old 8-arg form with nx,ny,nz still parses."""
        prims = parse_display_source('cylinder(0, 0, 0, 0.05, 0.5, 0, 1, 0);')
        assert isinstance(prims[0], Cylinder)

    def test_9_arg_new_form(self):
        """New 9-arg form with thickness between h and normal."""
        prims = parse_display_source('cylinder(0, 0, 0, 0.05, 0.5, 0.005, 0, 1, 0);')
        assert isinstance(prims[0], Cylinder)

    def test_to_mesh(self):
        c = Cylinder(0, 0, 0, 0.05, 0.5, 0, 0, 1, 0)
        verts, faces = c.to_mesh()
        assert verts.shape[1] == 3
        assert faces.shape[1] == 3

    def test_legacy_cylinder_parse(self):
        # legacy_cylinder(x,y,z,r,h,N,nx,ny,nz) — N is discarded
        prims = parse_display_source('legacy_cylinder(0,0,0, 0.05,0.5, 12, 0,1,0);')
        assert isinstance(prims[0], Cylinder)

    def test_mcdis_legacy_cylinder_parse(self):
        prims = parse_display_source('mcdis_legacy_cylinder(0,0,0, 0.05,0.5, 12, 0,1,0);')
        assert isinstance(prims[0], Cylinder)


# ===========================================================================
# to_mesh for existing solid primitives
# ===========================================================================

class TestSolidMesh:
    def test_sphere_mesh(self):
        from mccode_antlr.display import Sphere
        s = Sphere(0, 0, 0, 1.0)
        verts, faces = s.to_mesh()
        assert verts.dtype == np.float32
        assert faces.dtype == np.int32
        # All vertices on unit sphere
        radii = np.linalg.norm(verts, axis=1)
        np.testing.assert_allclose(radii, 1.0, atol=1e-5)

    def test_cone_mesh(self):
        from mccode_antlr.display import Cone
        c = Cone(0, 0, 0, 0.5, 1.0, 0, 1, 0)
        verts, faces = c.to_mesh()
        assert verts.shape[1] == 3
        assert faces.shape[1] == 3

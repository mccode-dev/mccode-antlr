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

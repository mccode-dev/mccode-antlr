"""Tests for the build123d B-rep renderer (display/render/brep.py).

All tests are skipped when build123d is not installed.
"""
from __future__ import annotations

import os
import tempfile

import numpy as np
import pytest

bd = pytest.importorskip("build123d", reason="build123d not installed")

from mccode_antlr.common.expression import Expr
from mccode_antlr.display import parse_display_source
from mccode_antlr.display.primitives import (
    Annulus, Box, Circle, CircleNormal, Cone, Cylinder, DashedLine,
    Disc, Line, Multiline, Polygon, Polyhedron, Rectangle, Sphere,
    ConditionalBlock, LoopBlock,
)
from mccode_antlr.display.render.brep import (
    BRepRegistry, component_to_brep, instrument_to_assembly,
    primitive_to_brep, save_step,
)

E = Expr.float
Ei = Expr.integer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_one(src: str):
    return parse_display_source(src)[0]


def _check_shape(shape):
    assert shape is not None, "Expected a shape, got None"
    assert hasattr(shape, 'bounding_box'), f"Not a build123d shape: {type(shape)}"


# ---------------------------------------------------------------------------
# Wire / edge primitives
# ---------------------------------------------------------------------------

class TestWirePrimitives:
    def test_line(self):
        prim = _parse_one('line(0,0,0, 1,0,0);')
        shape = primitive_to_brep(prim)
        assert isinstance(shape, bd.Edge)

    def test_dashed_line(self):
        prim = _parse_one('dashed_line(0,0,0, 1,0,0, 5);')
        shape = primitive_to_brep(prim)
        assert isinstance(shape, bd.Edge)

    def test_multiline(self):
        prim = _parse_one('multiline(3, 0,0,0, 1,0,0, 1,1,0);')
        shape = primitive_to_brep(prim)
        assert isinstance(shape, bd.Wire)

    def test_circle_xy(self):
        prim = _parse_one('circle("xy", 0,0,0, 0.1);')
        shape = primitive_to_brep(prim)
        assert isinstance(shape, bd.Wire)

    def test_circle_xz(self):
        prim = _parse_one('circle("xz", 0,0,0, 0.1);')
        shape = primitive_to_brep(prim)
        assert isinstance(shape, bd.Wire)

    def test_circle_yz(self):
        prim = _parse_one('circle("yz", 0,0,0, 0.1);')
        shape = primitive_to_brep(prim)
        assert isinstance(shape, bd.Wire)

    def test_circle_normal(self):
        prim = CircleNormal(cx=E(0), cy=E(0), cz=E(0), r=E(0.05),
                            nx=E(0), ny=E(1), nz=E(0))
        shape = primitive_to_brep(prim)
        assert isinstance(shape, bd.Wire)

    def test_rectangle(self):
        prim = _parse_one('rectangle("xy", 0,0,0, 0.1, 0.05);')
        shape = primitive_to_brep(prim)
        assert isinstance(shape, bd.Face)


# ---------------------------------------------------------------------------
# Solid primitives
# ---------------------------------------------------------------------------

class TestSolidPrimitives:
    def test_box(self):
        prim = _parse_one('box(0,0,0, 0.1,0.1,0.05, 0, 0,1,0);')
        shape = primitive_to_brep(prim)
        _check_shape(shape)

    def test_sphere(self):
        prim = _parse_one('sphere(0,0,0.5, 0.1);')
        shape = primitive_to_brep(prim)
        _check_shape(shape)
        bb = shape.bounding_box()
        assert pytest.approx(bb.center().Z, abs=1e-6) == 0.5

    def test_cylinder_default_axis(self):
        prim = _parse_one('cylinder(0,0,0, 0.05,0.2, 0, 0,1,0);')
        shape = primitive_to_brep(prim)
        _check_shape(shape)

    def test_cylinder_tilted_axis(self):
        prim = _parse_one('cylinder(0,0,0, 0.05,0.2, 0, 1,0,0);')
        shape = primitive_to_brep(prim)
        _check_shape(shape)

    def test_cone(self):
        prim = _parse_one('cone(0,0,0, 0.05,0.1, 0,1,0);')
        shape = primitive_to_brep(prim)
        _check_shape(shape)

    def test_disc(self):
        prim = Disc(cx=E(0), cy=E(0), cz=E(0), r=E(0.05),
                    nx=E(0), ny=E(1), nz=E(0))
        shape = primitive_to_brep(prim)
        _check_shape(shape)

    def test_annulus(self):
        prim = Annulus(cx=E(0), cy=E(0), cz=E(0),
                       r_outer=E(0.1), r_inner=E(0.05),
                       nx=E(0), ny=E(1), nz=E(0))
        shape = primitive_to_brep(prim)
        _check_shape(shape)


# ---------------------------------------------------------------------------
# Symbolic Expr evaluation
# ---------------------------------------------------------------------------

class TestSymbolicParams:
    def test_sphere_symbolic_radius(self):
        prims = parse_display_source('sphere(0,0,0, r);')
        shape = primitive_to_brep(prims[0], {'r': 0.05})
        _check_shape(shape)
        bb = shape.bounding_box()
        assert pytest.approx(bb.diagonal, abs=1e-4) == 2 * 0.05 * (3 ** 0.5)

    def test_box_symbolic_dims(self):
        prims = parse_display_source('box(0,0,0, xw,yh,zd, 0, 0,1,0);')
        shape = primitive_to_brep(prims[0], {'xw': 0.1, 'yh': 0.2, 'zd': 0.05})
        _check_shape(shape)

    def test_missing_param_raises(self):
        prims = parse_display_source('sphere(0,0,0, r);')
        with pytest.raises((ValueError, Exception)):
            primitive_to_brep(prims[0], {})


# ---------------------------------------------------------------------------
# ConditionalBlock / LoopBlock
# ---------------------------------------------------------------------------

class TestControlFlow:
    def test_conditional_true(self):
        src = 'if (use_it) { sphere(0,0,0, 0.05); }'
        prims = parse_display_source(src)
        result = primitive_to_brep(prims[0], {'use_it': 1})
        assert result is not None

    def test_conditional_false_returns_none(self):
        src = 'if (use_it) { sphere(0,0,0, 0.05); }'
        prims = parse_display_source(src)
        result = primitive_to_brep(prims[0], {'use_it': 0})
        assert result is None


# ---------------------------------------------------------------------------
# BRepRegistry
# ---------------------------------------------------------------------------

class TestBRepRegistry:
    def test_register_and_get(self):
        reg = BRepRegistry()
        called = []

        @reg.register("TestComp")
        def builder(instance, params):
            called.append(True)
            return bd.Sphere(0.1)

        fn = reg.get("TestComp")
        assert fn is not None
        result = fn(None, {})
        assert isinstance(result, bd.Sphere)
        assert called == [True]

    def test_unregistered_returns_none(self):
        reg = BRepRegistry()
        assert reg.get("Unknown") is None

    def test_repr(self):
        reg = BRepRegistry()
        reg.register("A")(lambda i, p: None)
        assert "A" in repr(reg)


# ---------------------------------------------------------------------------
# component_to_brep
# ---------------------------------------------------------------------------

class TestComponentToBrep:
    def test_arm_component(self):
        from mccode_antlr.display import ComponentDisplay
        from mccode_antlr.comp import Comp
        from mccode_antlr.common import RawC

        src = 'sphere(0,0,0, 0.05); cylinder(0,0,0, 0.02,0.2, 0,1,0);'
        comp = Comp(name='Tst', display=(RawC(filename=None, line=0, source=src),))
        cd = ComponentDisplay(comp)
        result = component_to_brep(cd, {})
        assert result is not None
        assert isinstance(result, bd.Compound)

    def test_empty_component_returns_none(self):
        from mccode_antlr.display import ComponentDisplay
        from mccode_antlr.comp import Comp
        comp = Comp(name='Empty', display=())
        cd = ComponentDisplay(comp)
        result = component_to_brep(cd, {})
        assert result is None


# ---------------------------------------------------------------------------
# instrument_to_assembly + save_step
# ---------------------------------------------------------------------------

class TestInstrumentToAssembly:
    @pytest.fixture
    def demo_disp(self, tmp_path):
        import tempfile, os
        from mccode_antlr.loader import load_mcstas_instr
        from mccode_antlr.display import InstrumentDisplay

        src = '''
DEFINE INSTRUMENT demo(xw=0.05, yh=0.1)
TRACE
COMPONENT origin = Arm()
AT (0,0,0) ABSOLUTE
COMPONENT sample = Arm()
AT (0,0,5) RELATIVE origin
ROTATED (0, 45, 0) RELATIVE origin
END
'''
        p = tmp_path / "demo.instr"
        p.write_text(src)
        instr = load_mcstas_instr(str(p))
        return InstrumentDisplay(instr)

    def test_returns_compound(self, demo_disp):
        assembly = instrument_to_assembly(demo_disp, {})
        assert isinstance(assembly, bd.Compound)

    def test_save_step_creates_file(self, demo_disp, tmp_path):
        assembly = instrument_to_assembly(demo_disp, {})
        out = tmp_path / "demo.step"
        save_step(assembly, out)
        assert out.exists()
        assert out.stat().st_size > 1000

    def test_registry_override_used(self, demo_disp):
        reg = BRepRegistry()
        called = []

        @reg.register("Arm")
        def arm_override(instance, params):
            called.append(instance.name)
            return bd.Box(0.1, 0.1, 0.1)

        assembly = instrument_to_assembly(demo_disp, {}, registry=reg)
        assert isinstance(assembly, bd.Compound)
        assert len(called) == 2  # origin + sample both overridden

    def test_registry_fallback_when_no_override(self, demo_disp):
        reg = BRepRegistry()  # empty — no overrides
        assembly = instrument_to_assembly(demo_disp, {}, registry=reg)
        assert isinstance(assembly, bd.Compound)


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------

class TestCLI:
    def test_cli_produces_step(self, tmp_path):
        from mccode_antlr.cli.step import main

        src = '''
DEFINE INSTRUMENT cli_test()
TRACE
COMPONENT o = Arm()
AT (0,0,0) ABSOLUTE
END
'''
        instr_path = tmp_path / "cli_test.instr"
        instr_path.write_text(src)
        out_path = tmp_path / "out.step"

        rc = main([str(instr_path), '-o', str(out_path)])
        assert rc == 0
        assert out_path.exists()
        assert out_path.stat().st_size > 500

    def test_cli_missing_instr_returns_nonzero(self, tmp_path):
        from mccode_antlr.cli.step import main
        rc = main([str(tmp_path / "nonexistent.instr")])
        assert rc != 0

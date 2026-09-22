"""RotationPart honours its own `degrees` flag.

`RotationPart.degrees` says what unit `v` is already expressed in. The rotation
built from it has to be the same rotation either way -- 30 degrees and pi/6
radians name one angle. `_cos_sin_one_zero` used to convert `v` with
`degree_to_radian` and then call cos_value/sin_value on their degrees=True
default, applying a conversion twice in the wrong direction, so a radian-valued
part produced a rotation of roughly 0.0167 degrees instead of 30.
"""
import math

import pytest

from mccode_antlr.common.expression import Expr
from mccode_antlr.instr.orientation import (
    Angles, Parts, RotationX, RotationY, RotationZ, Vector,
)

ROTATIONS = (RotationX, RotationY, RotationZ)
DEG, RAD = 30.0, math.pi / 6


@pytest.mark.parametrize('cls', ROTATIONS, ids=lambda c: c.__name__)
def test_cos_sin_agree_between_unit_conventions(cls):
    c_deg, s_deg, *_ = cls(v=Expr.float(DEG), degrees=True)._cos_sin_one_zero()
    c_rad, s_rad, *_ = cls(v=Expr.float(RAD), degrees=False)._cos_sin_one_zero()

    assert float(str(c_rad)) == pytest.approx(math.cos(RAD), abs=1e-12)
    assert float(str(s_rad)) == pytest.approx(math.sin(RAD), abs=1e-12)
    assert float(str(c_rad)) == pytest.approx(float(str(c_deg)), abs=1e-12)
    assert float(str(s_rad)) == pytest.approx(float(str(s_deg)), abs=1e-12)


@pytest.mark.parametrize('cls', ROTATIONS, ids=lambda c: c.__name__)
def test_rotation_matrices_agree_between_unit_conventions(cls):
    deg = cls(v=Expr.float(DEG), degrees=True).rotation()
    rad = cls(v=Expr.float(RAD), degrees=False).rotation()
    for a, b in zip(deg, rad):
        assert float(str(a)) == pytest.approx(float(str(b)), abs=1e-12)


def test_from_at_rotated_agrees_between_unit_conventions():
    """The public entry point that threads the flag through to RotationPart."""
    at = Vector(Expr.float(0), Expr.float(0), Expr.float(1))
    deg = Parts.from_at_rotated(at, Angles(Expr.float(0), Expr.float(DEG), Expr.float(0)),
                                degrees=True)
    rad = Parts.from_at_rotated(at, Angles(Expr.float(0), Expr.float(RAD), Expr.float(0)),
                                degrees=False)
    for a, b in zip(deg.rotation(), rad.rotation()):
        assert float(str(a)) == pytest.approx(float(str(b)), abs=1e-12)


@pytest.mark.parametrize('cls', ROTATIONS, ids=lambda c: c.__name__)
def test_radian_symbolic_angle_gets_no_conversion_factor(cls):
    """A symbolic angle already in radians must reach sympy untouched."""
    c, s, *_ = cls(v=Expr.parse('a'), degrees=False)._cos_sin_one_zero()
    assert str(c) == 'cos(a)'
    assert str(s) == 'sin(a)'

# The mirror case -- a symbolic angle in *degrees* -- is #350's territory rather
# than this fix's, and is covered by tests/instr/test_symbolic_rotation.py there.

"""resolve_orientations must agree with itself whether an angle is spelled as a
literal or as a parameter.

McCode ROTATED angles are degrees. sin_value/cos_value fold a *constant* angle
with a degree-aware Python function, but the symbolic branch of unary_expr is
built from the C function name alone -- sympy.sin takes radians, and nothing in
the resulting expression records that degrees were meant. The conversion has to
be baked in while that is still known, or the two spellings of one instrument
disagree: ROTATED (0, 30, 0) resolved correctly while ROTATED (0, TT, 0) with
TT=30 put the component metres away.

acos_value and atan2_value have the mirror-image problem: sympy returns radians
where the caller asked for degrees.
"""
import math

import pytest

from mccode_antlr.common.expression import Expr
from mccode_antlr.instr.orientation import acos_value, atan2_value, cos_value, sin_value
from mccode_antlr.loader.loader import parse_mccode_instr
from mccode_antlr.reader.registry import InMemoryRegistry

THING = 'DEFINE COMPONENT Thing\nTRACE %{\nSCATTER;\n%}\nEND\n'

SYMBOLIC = """DEFINE INSTRUMENT rot(TT=30)
TRACE
COMPONENT base = Thing() AT (0, 0, 0) ABSOLUTE
COMPONENT arm  = Thing() AT (0, 0, 0) RELATIVE base ROTATED (0, TT, 0) RELATIVE base
COMPONENT tip  = Thing() AT (0, 0, 10) RELATIVE arm
END
"""

LITERAL = SYMBOLIC.replace('rot(TT=30)', 'rot()').replace('(0, TT, 0)', '(0, 30, 0)')


def _registry():
    reg = InMemoryRegistry('symbolic_rotation')
    reg.add_comp('Thing', THING)
    return reg


def _tip(source):
    instr = parse_mccode_instr(source, [_registry()])
    return instr.resolve_orientations()['tip'].position()


def test_symbolic_and_literal_angles_agree():
    sym, lit = _tip(SYMBOLIC), _tip(LITERAL)
    got = [float(str(c.evaluate({'TT': 30.0}).simplify())) for c in (sym.x, sym.y, sym.z)]
    want = [float(str(c)) for c in (lit.x, lit.y, lit.z)]
    assert got == pytest.approx(want, abs=1e-9)
    # and that is the geometry the instrument actually describes
    assert got == pytest.approx([10 * math.sin(math.radians(30)), 0.0,
                                 10 * math.cos(math.radians(30))], abs=1e-9)


def test_symbolic_position_reduces_to_a_number():
    """A leftover free symbol (e.g. PI) would leave consumers -- display, BREP
    export, Instr.split -- with an expression they cannot turn into a position."""
    x = _tip(SYMBOLIC).x
    assert not x.is_constant           # still symbolic before substitution
    evaluated = x.evaluate({'TT': 30.0}).simplify()
    assert evaluated.is_constant and evaluated.has_value


@pytest.mark.parametrize('angle', [0.0, 30.0, 45.0, 90.0, 180.0, -90.0, 123.456])
def test_symbolic_trig_matches_the_constant_fold(angle):
    """The symbolic branch must agree with the constant branch it bypasses."""
    sym = Expr.parse('theta')
    for fn, ref in ((sin_value, math.sin), (cos_value, math.cos)):
        folded = float(str(fn(Expr.float(angle))))
        substituted = float(str(fn(sym).evaluate({'theta': angle}).simplify()))
        assert substituted == pytest.approx(folded, abs=1e-12)
        assert substituted == pytest.approx(ref(math.radians(angle)), abs=1e-12)


def test_atan2_value_returns_degrees_when_symbolic():
    r = atan2_value(Expr.parse('sy'), Expr.parse('sx'), degrees=True)[0]
    got = float(str(r.evaluate({'sy': 1.0, 'sx': 1.0}).simplify()))
    assert got == pytest.approx(45.0)
    # agrees with the constant branch
    assert got == pytest.approx(float(str(atan2_value(Expr.float(1), Expr.float(1))[0])))


def test_acos_value_handles_a_symbolic_argument():
    """The out-of-domain clamps compare against 1 and -1; a symbolic Expr used to
    satisfy both, so every symbolic arccosine collapsed to 0."""
    a = acos_value(Expr.parse('q'))
    assert str(a) != '0.0'
    got = float(str(a.evaluate({'q': 0.5}).simplify()))
    assert got == pytest.approx(math.degrees(math.acos(0.5)))
    assert got == pytest.approx(float(str(acos_value(Expr.float(0.5)))))


def test_acos_value_still_clamps_real_constants():
    assert float(str(acos_value(Expr.float(2)))) == pytest.approx(0.0)
    assert float(str(acos_value(Expr.float(-2)))) == pytest.approx(180.0)


def test_radian_callers_are_untouched():
    """degrees=False must not acquire a conversion factor."""
    assert str(sin_value(Expr.parse('x'), degrees=False)) == 'sin(x)'
    assert str(cos_value(Expr.parse('x'), degrees=False)) == 'cos(x)'


FORWARD_REF = """DEFINE INSTRUMENT fwd(TT=30)
TRACE
COMPONENT a = Thing() AT (0, 0, 0) ABSOLUTE
COMPONENT b = Thing() AT (0, 0, 1) RELATIVE a
COMPONENT c = Thing() AT (0, 0, 2) RELATIVE a
END
"""


@pytest.mark.parametrize('angle', [0.0, 30.0, 45.0, 90.0, -60.0])
def test_rotation_from_angles_agrees_symbolic_and_literal(angle):
    """Rotation.from_angles built its trig with unary_expr directly, bypassing
    sin_value/cos_value and so also bypassing the degrees conversion."""
    from mccode_antlr.instr.orientation import Angles, Rotation

    z = Expr.float(0)
    literal = Rotation.from_angles(Angles(z, Expr.float(angle), z))
    symbolic = Rotation.from_angles(Angles(z, Expr.parse('TT'), z))
    for a, b in zip(literal, symbolic):
        got = float(str(b.evaluate({'TT': angle}).simplify()))
        assert got == pytest.approx(float(str(a)), abs=1e-12)


def test_insert_component_keeps_a_symbolic_rotation():
    """The live path onto Rotation.from_angles: inserting a component whose
    ROTATED refers forward makes _fix_forward_ref_rotation re-express it, which
    used to return -81.13 degrees where TT=30 was asked for."""
    from mccode_antlr.instr.orientation import Angles

    instr = parse_mccode_instr(FORWARD_REF, [_registry()])
    z = Expr.float(0)
    inserted = instr.insert_component(
        'n', instr.components[0].type, before='b',
        at_relative=((0, 0, 0.5), instr.get_component('a')),
        rotate_relative=(Angles(z, Expr.parse('TT'), z), instr.get_component('c')),
    )
    angles = inserted.rotate_relative[0]
    got = [float(str(x.evaluate({'TT': 30.0}).simplify()))
           for x in (angles.x, angles.y, angles.z)]
    # c carries no rotation of its own, so re-expressing must give back TT about y
    assert got == pytest.approx([0.0, 30.0, 0.0], abs=1e-9)

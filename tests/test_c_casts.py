"""C casts in McCode expressions, carried through without being interpreted.

Classic McCode accepts `nx=((int)NX)` because its instrument expressions are
token soup -- instrument.y's `topatexp` takes any balanced token sequence and
copies it into the generated C verbatim, never assigning it meaning. mccode-antlr
parses expressions for real, so a cast needs a representation: CCast reproduces
it on output and blocks constant folding, rather than committing to C conversion
semantics that would then have to match whatever the compiled code does.

Five shipped instruments need this: mcxtrace-comps/examples/AstroX_ESA/ATHENA_*.
"""
import pytest

from mccode_antlr.common.expression import Expr


@pytest.mark.parametrize('source, printed', [
    ('(int)NX', '((int)NX)'),
    ('((int)NX)', '((int)NX)'),
    ('(double)n', '((double)n)'),
    ('(char*)p', '((char*)p)'),
])
def test_cast_round_trips_to_c(source, printed):
    assert str(Expr.parse(source)) == printed


@pytest.mark.parametrize('source, printed', [
    ('(int)(a*b)', '((int)(a*b))'),
    ('(int)(a+b)', '((int)(a + b))'),
    ('(int)f(x)', '((int)(f(x)))'),
])
def test_compound_operand_keeps_its_parentheses(source, printed):
    """A cast binds tighter than any binary operator: (int)a*b is not (int)(a*b)."""
    assert str(Expr.parse(source)) == printed


def test_cast_does_not_fold():
    """Deliberate: the cast's value is the C compiler's business, not ours."""
    expr = Expr.parse('(int)NX')
    assert not expr.is_constant
    # substituting the operand leaves the cast in place rather than evaluating it
    assert 'int' in str(expr.evaluate({'NX': 3.7}))


def test_cast_operand_is_still_a_free_symbol():
    """The type name must not leak into free_symbols, but the operand must."""
    names = {str(s) for e in Expr.parse('(int)NX')._exprs for s in e.free_symbols}
    assert names == {'NX'}


def test_grouping_is_unaffected():
    """'(' expr ')' must still win for an ordinary parenthesised expression."""
    assert str(Expr.parse('(a+b)*c')) == 'c*(a + b)'
    assert str(Expr.parse('(NX)')) == 'NX'


def test_athena_style_parameter_value():
    """The expression that made five ATHENA examples fail to parse."""
    assert str(Expr.parse('((int)NX)')) == '((int)NX)'

"""``_eval_expr`` reduces an expression to a number.

It used to call ``float()`` on the result of ``Expr.evaluate(params).simplify()``, which
is an ``Expr``. ``Expr`` defines no ``__float__``, so that raised ``TypeError`` for every
expression it was ever given -- including the constant ones, where the number was
sitting under ``.value``.

Nothing noticed because the two callers wrap it in ``try: ... except Exception: pass``.
``instrument_to_assembly`` uses it to place each component of a CAD export in the global
frame, so the failure showed up as every solid being exported at the origin: a 162 m
instrument came out 4.4 m long, and a STEP file of it was a heap of parts at one point.
"""
import pytest

from mccode_antlr.common.expression import Expr
from mccode_antlr.display.instrument_display import _eval_expr


def test_a_constant_expression_reduces():
    assert _eval_expr(Expr.float(6.76), {}) == pytest.approx(6.76)


def test_a_plain_number_passes_through():
    assert _eval_expr(2.5, {}) == pytest.approx(2.5)
    assert _eval_expr(3, {}) == pytest.approx(3.0)


def test_something_that_does_not_reduce_says_so():
    """Rather than raising TypeError from float(), which reads like a type confusion.

    Note this also covers a parameter that *was* given a value: Expr.evaluate builds its
    substitution map from plain sympy.Symbol while an identifier may be a
    McCodeParameter, so the substitution silently does nothing and the expression stays
    symbolic. That is a separate bug from this one -- it is why niess.tof carries a
    `_fold` helper that prints an expression and re-parses it -- and it is not what this
    change fixes. What changes here is that the failure now says what it is.
    """
    expression = Expr.parameter('unknown')
    with pytest.raises(ValueError, match='does not reduce to a number'):
        _eval_expr(expression, {})


def test_a_resolved_orientation_places_a_component():
    """The case that was broken: reading a placement out of a built instrument."""
    from mccode_antlr import Flavor
    from mccode_antlr.assembler import Assembler

    assembler = Assembler('placed', flavor=Flavor.MCSTAS)
    assembler.component('origin', 'Arm', at=((0, 0, 0), 'ABSOLUTE'))
    assembler.component('downstream', 'Arm', at=((0, 0, 7.5), 'origin'))

    where = assembler.instrument.resolve_orientations()['downstream'].position()
    assert _eval_expr(where.z, {}) == pytest.approx(7.5)

"""Reproduce Expr.evaluate silently not substituting a McCodeParameter.

See BUG-expr-evaluate-mccodeparameter.md for the write-up. In short:
verify_parameters promotes an expression's free symbols from sympy.Symbol to
McCodeParameter, and Expr.evaluate builds its substitution map out of sympy.Symbol
only -- so from that point on, giving a parameter a value does nothing and the
expression stays symbolic, with no error.

Fixed in Expr.evaluate by mapping both spellings, the way depends_on already does.
"""
import pytest
import sympy

from mccode_antlr.common.expression import Expr
from mccode_antlr.common.expression.sympy_classes import McCodeParameter


def a_component_parameter():
    from mccode_antlr import Flavor
    from mccode_antlr.assembler import Assembler

    assembler = Assembler('reproducer', flavor=Flavor.MCSTAS)
    assembler.parameter('double gap = 0.03;')
    assembler.component('slit', 'Slit', at=((0, 0, 1), 'ABSOLUTE'), parameters={'xwidth': 'gap'})
    instance = assembler.instrument.components[0]
    return next(p for p in instance.parameters if p.name == 'xwidth').value


def free_symbol_types(expression):
    symbols = set().union(*[e.free_symbols for e in expression._exprs])
    return {type(symbol).__name__ for symbol in symbols}


def test_a_parsed_parameter_evaluates():
    """Before anything promotes it, the symbol is a plain Symbol and this works."""
    expression = a_component_parameter()
    assert free_symbol_types(expression) == {'Symbol'}
    assert float(expression.evaluate({'gap': 0.03}).value) == pytest.approx(0.03)


def test_verify_parameters_promotes_the_symbol():
    """Which is the trigger, and is not itself wrong."""
    expression = a_component_parameter()
    expression.verify_parameters(['gap'])
    assert free_symbol_types(expression) == {'McCodeParameter'}


def test_a_verified_parameter_still_evaluates():
    """The bug: the same expression, after verify_parameters, no longer evaluates.

    Nothing raises. The expression comes back unchanged, and a caller that expected a
    number gets a symbol -- which downstream then either crashes on or, worse, formats
    into generated code.
    """
    expression = a_component_parameter()
    expression.verify_parameters(['gap'])
    assert float(expression.evaluate({'gap': 0.03}).value) == pytest.approx(0.03)


def test_expr_parameter_evaluates():
    """Expr.parameter builds a McCodeParameter directly, so it never evaluates."""
    expression = Expr.parameter('length')
    assert free_symbol_types(expression) == {'McCodeParameter'}
    assert float(expression.evaluate({'length': 4.0}).value) == pytest.approx(4.0)


def test_depends_on_gets_this_right():
    """Which is what makes the fix obvious: the same class already handles both.

    depends_on builds ``{sympy.Symbol(name), McCodeParameter(name)}`` and tests against
    both. evaluate, sixteen lines earlier, builds only the first.
    """
    expression = Expr.parameter('length')
    assert expression.depends_on('length')


def test_substituting_by_hand_shows_the_cause():
    """A McCodeParameter is a Symbol subclass, but sympy does not treat them as equal.

    So a substitution map keyed on Symbol misses an expression holding the subclass,
    and ``subs`` returns the expression untouched rather than complaining.
    """
    assert issubclass(McCodeParameter, sympy.Symbol)
    assert sympy.Symbol('length') != McCodeParameter('length')

    expression = Expr.parameter('length')
    by_symbol = [e.subs({sympy.Symbol('length'): sympy.sympify(4.0)}) for e in expression._exprs]
    by_parameter = [e.subs({McCodeParameter('length'): sympy.sympify(4.0)}) for e in expression._exprs]

    assert str(by_symbol[0]) == 'length', 'missed, silently'
    assert float(by_parameter[0]) == pytest.approx(4.0)


def test_mapping_both_spellings_would_fix_it():
    """What depends_on already does, applied to evaluate."""
    expression = Expr.parameter('length')
    assert float(expression.evaluate({'length': 4.0}).value) == pytest.approx(4.0)

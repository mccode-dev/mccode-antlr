"""McCode C and Python code printers built on SymPy's printer framework."""
from __future__ import annotations

import sympy
from sympy.printing.c import C99CodePrinter
from sympy.printing.pycode import PythonCodePrinter

from .sympy_classes import (
    McCodeParameter, CStructAccess, CPointerAccess, CTernary,
    CArrayIndex, CIntDiv, CLeftShift, CRightShift, CRound,
    CFunctionCall, CInitializerList, CAnd, COr, CNot, UNSET_SYMPY,
)


class McCodeCPrinter(C99CodePrinter):
    """SymPy printer that emits McCode-compatible C expressions.

    When *parameter_prefix* is ``True``, :class:`McCodeParameter` symbols are
    printed as ``_instrument_var._parameters.<name>``; otherwise they print as
    plain ``<name>``.
    """

    def __init__(self, *args, parameter_prefix: bool = False, prefix: str = '_instrument_var._parameters.', **kwargs):
        super().__init__(*args, **kwargs)
        self._parameter_prefix = parameter_prefix
        self._prefix = prefix

    # --- McCode-specific symbols ---

    def _print_McCodeParameter(self, expr):
        if self._parameter_prefix:
            return f'{self._prefix}{expr.name}'
        return expr.name

    def _print_Symbol(self, expr):
        if expr is UNSET_SYMPY:
            return ''
        return expr.name

    # --- C-specific constructs ---

    def _print_CStructAccess(self, expr):
        return f'{self._print(expr.args[0])}.{expr.args[1]}'

    def _print_CPointerAccess(self, expr):
        return f'{self._print(expr.args[0])}->{expr.args[1]}'

    def _print_CTernary(self, expr):
        c, t, f = (self._print(a) for a in expr.args)
        return f'({c} ? {t} : {f})'

    def _print_CArrayIndex(self, expr):
        return f'{self._print(expr.args[0])}[{self._print(expr.args[1])}]'

    def _print_CIntDiv(self, expr):
        return f'{self._print(expr.args[0])} / {self._print(expr.args[1])}'

    def _print_CLeftShift(self, expr):
        return f'({self._print(expr.args[0])} << {self._print(expr.args[1])})'

    def _print_CRightShift(self, expr):
        return f'({self._print(expr.args[0])} >> {self._print(expr.args[1])})'

    def _print_CRound(self, expr):
        return f'round({self._print(expr.args[0])})'

    def _print_CFunctionCall(self, expr):
        func_name = expr.args[0].name
        call_args = ', '.join(self._print(a) for a in expr.args[1:])
        return f'{func_name}({call_args})'

    def _print_CInitializerList(self, expr):
        items = ', '.join(self._print(a) for a in expr.args)
        return f'{{{items}}}'

    # --- Override boolean/logical operators for C style ---

    def _print_Not(self, expr):
        return f'!({self._print(expr.args[0])})'

    def _print_And(self, expr):
        return ' && '.join(self._print(a) for a in expr.args)

    def _print_Or(self, expr):
        return ' || '.join(self._print(a) for a in expr.args)

    def _print_CAnd(self, expr):
        return ' && '.join(self._print(a) for a in expr.args)

    def _print_COr(self, expr):
        return ' || '.join(self._print(a) for a in expr.args)

    def _print_CNot(self, expr):
        return f'!({self._print(expr.args[0])})'

    # --- Compact relational operators (no spaces, matching McCode convention) ---

    def _print_Relational(self, expr):
        ops = {
            sympy.Eq: '==', sympy.Ne: '!=',
            sympy.Lt: '<',  sympy.Gt: '>',
            sympy.Le: '<=', sympy.Ge: '>=',
        }
        op = ops.get(type(expr), None)
        if op is not None:
            return f'{self._print(expr.lhs)}{op}{self._print(expr.rhs)}'
        return super()._print_Relational(expr)

    # --- Suppress SymPy's piecewise in favour of our CTernary ---

    def _print_Piecewise(self, expr):
        # Fall back to a ternary chain for simple two-branch cases
        if len(expr.args) == 2 and expr.args[1].cond is sympy.true:
            cond = self._print(expr.args[0].cond)
            t = self._print(expr.args[0].expr)
            f = self._print(expr.args[1].expr)
            return f'({cond} ? {t} : {f})'
        return super()._print_Piecewise(expr)

    # --- Numeric output: use Python's shortest-repr float format ---

    def _print_Float(self, expr):
        # Use Python's float repr (shortest round-trip representation)
        # to avoid SymPy's %.17g format giving e.g. '0.050000000000000003' for 0.05.
        return repr(float(expr))


class McCodePyPrinter(PythonCodePrinter):
    """SymPy printer that emits McCode Python-style expressions."""

    def _print_McCodeParameter(self, expr):
        return expr.name

    def _print_Symbol(self, expr):
        if expr is UNSET_SYMPY:
            return ''
        return expr.name

    def _print_CStructAccess(self, expr):
        return f'getattr({self._print(expr.args[0])}, "{expr.args[1]}")'

    def _print_CPointerAccess(self, expr):
        return f'getattr({self._print(expr.args[0])}, "{expr.args[1]}")'

    def _print_CTernary(self, expr):
        c, t, f = (self._print(a) for a in expr.args)
        return f'({t} if {c} else {f})'

    def _print_CArrayIndex(self, expr):
        return f'{self._print(expr.args[0])}[{self._print(expr.args[1])}]'

    def _print_CIntDiv(self, expr):
        return f'{self._print(expr.args[0])} // {self._print(expr.args[1])}'

    def _print_CLeftShift(self, expr):
        return f'({self._print(expr.args[0])} << {self._print(expr.args[1])})'

    def _print_CRightShift(self, expr):
        return f'({self._print(expr.args[0])} >> {self._print(expr.args[1])})'

    def _print_CRound(self, expr):
        return f'round({self._print(expr.args[0])})'

    def _print_CFunctionCall(self, expr):
        func_name = expr.args[0].name
        call_args = ', '.join(self._print(a) for a in expr.args[1:])
        return f'{func_name}({call_args})'

    def _print_CInitializerList(self, expr):
        items = ', '.join(self._print(a) for a in expr.args)
        return f'[{items}]'

    def _print_Not(self, expr):
        return f'not ({self._print(expr.args[0])})'

    def _print_And(self, expr):
        return ' and '.join(self._print(a) for a in expr.args)

    def _print_Or(self, expr):
        return ' or '.join(self._print(a) for a in expr.args)


# Module-level singletons to avoid repeated construction
_C_PRINTER = McCodeCPrinter()
_P_PRINTER = McCodeCPrinter(parameter_prefix=True)
_PY_PRINTER = McCodePyPrinter()

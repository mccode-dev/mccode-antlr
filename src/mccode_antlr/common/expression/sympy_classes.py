"""Custom SymPy classes for McCode C expression trees.

These supplement SymPy's built-in expression types with constructs that are
specific to C code (struct/pointer access, ternary, array index, integer
division, bit-shifts) and McCode's instrument parameter convention.
"""
from __future__ import annotations

import sympy
from sympy import Symbol, Function, Integer


# ---------------------------------------------------------------------------
# McCode-specific Symbol subclasses
# ---------------------------------------------------------------------------

class McCodeParameter(Symbol):
    """A symbol that refers to a McCode instrument parameter.

    Printed as ``_instrument_var._parameters.<name>`` when the 'p' format
    spec is used; printed as plain ``<name>`` otherwise.
    """


# ---------------------------------------------------------------------------
# C-specific Function subclasses (non-mathematical operations)
# ---------------------------------------------------------------------------

class CStructAccess(Function):
    """C struct member access: ``obj.field``."""
    @classmethod
    def eval(cls, *args):
        return None  # never auto-reduce


class CPointerAccess(Function):
    """C pointer member access: ``obj->field``."""
    @classmethod
    def eval(cls, *args):
        return None


class CTernary(Function):
    """C ternary expression: ``cond ? true_val : false_val``."""
    @classmethod
    def eval(cls, *args):
        return None


class CArrayIndex(Function):
    """C array subscript: ``arr[idx]``."""
    @classmethod
    def eval(cls, *args):
        return None


class CIntDiv(Function):
    """C integer division: ``a / b`` (both operands are integers)."""
    @classmethod
    def eval(cls, lhs, rhs):
        if (lhs.is_integer and lhs.is_number
                and rhs.is_integer and rhs.is_number and rhs != sympy.Integer(0)):
            return sympy.Integer(int(lhs) // int(rhs))
        return None


class CLeftShift(Function):
    """C left-shift: ``a << b``."""
    @classmethod
    def eval(cls, *args):
        return None


class CRightShift(Function):
    """C right-shift: ``a >> b``."""
    @classmethod
    def eval(cls, *args):
        return None


class CRound(Function):
    """C ``round(x)`` — distinct from Python's banker's rounding."""
    @classmethod
    def eval(cls, *args):
        return None


class CFunctionCall(Function):
    """Arbitrary C function call: ``func(arg1, arg2, ...)``.

    ``args[0]`` is the function name as a :class:`sympy.Symbol`;
    ``args[1:]`` are the call arguments.
    """
    @classmethod
    def eval(cls, *args):
        return None

    @property
    def free_symbols(self):
        # Exclude args[0] (the function name Symbol) from free symbols;
        # it is a fixed identifier, not a variable.
        result = set()
        for a in self.args[1:]:
            result |= a.free_symbols
        return result


class CInitializerList(Function):
    """C initializer list ``{a, b, c}`` used for array/vector literals."""
    @classmethod
    def eval(cls, *args):
        return None


class CAnd(Function):
    """C logical AND operator: ``a && b``."""
    @classmethod
    def eval(cls, *args):
        return None  # no automatic simplification


class COr(Function):
    """C logical OR operator: ``a || b``."""
    @classmethod
    def eval(cls, *args):
        return None


class CNot(Function):
    """C logical NOT operator: ``!a``."""
    @classmethod
    def eval(cls, *args):
        return None


class CBitwiseAnd(Function):
    """C bitwise AND operator: ``a & b``."""
    @classmethod
    def eval(cls, *args):
        return None


class CBitwiseOr(Function):
    """C bitwise OR operator: ``a | b``."""
    @classmethod
    def eval(cls, *args):
        return None


class CBitwiseXor(Function):
    """C bitwise XOR operator: ``a ^ b``."""
    @classmethod
    def eval(cls, *args):
        return None


class CBitwiseNot(Function):
    """C bitwise NOT operator: ``~a``."""
    @classmethod
    def eval(cls, *args):
        return None


# ---------------------------------------------------------------------------
# Sentinel for "no value" (represents Value(None) from the old system)
# ---------------------------------------------------------------------------

UNSET_SYMPY: sympy.Basic = Symbol('_mccode_unset_')

# ---------------------------------------------------------------------------
# Namespace used by eval(srepr(...)) to reconstruct expressions
# ---------------------------------------------------------------------------

SYMPY_NAMESPACE: dict = {
    **{name: getattr(sympy, name) for name in dir(sympy) if not name.startswith('_')},
    # Custom classes must be explicitly present
    'McCodeParameter': McCodeParameter,
    'CStructAccess': CStructAccess,
    'CPointerAccess': CPointerAccess,
    'CTernary': CTernary,
    'CArrayIndex': CArrayIndex,
    'CIntDiv': CIntDiv,
    'CLeftShift': CLeftShift,
    'CRightShift': CRightShift,
    'CRound': CRound,
    'CFunctionCall': CFunctionCall,
    'CInitializerList': CInitializerList,
    'CAnd': CAnd,
    'COr': COr,
    'CNot': CNot,
    'CBitwiseAnd': CBitwiseAnd,
    'CBitwiseOr': CBitwiseOr,
    'CBitwiseXor': CBitwiseXor,
    'CBitwiseNot': CBitwiseNot,
    'UNSET_SYMPY': UNSET_SYMPY,
}

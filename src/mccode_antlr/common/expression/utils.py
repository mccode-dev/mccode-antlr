"""Utility functions for McCode expressions.

The public API (unary_expr / binary_expr) is preserved unchanged.
The legacy deserialization helper is kept for migration.
"""
from __future__ import annotations

import math

import sympy

from .types import DataType

# Map operation names to SymPy functions used in orientation.py / unary_expr / binary_expr
_SYMPY_FUNC_MAP: dict = {
    'sin': sympy.sin,
    'cos': sympy.cos,
    'tan': sympy.tan,
    'asin': sympy.asin,
    'acos': sympy.acos,
    'atan': sympy.atan,
    'atan2': sympy.atan2,
    'sqrt': sympy.sqrt,
    'exp': sympy.exp,
    'log': sympy.log,
    'abs': sympy.Abs,
    'fabs': sympy.Abs,
    'pow': sympy.Pow,
    'fmod': sympy.Mod,
    'floor': sympy.floor,
    'ceil': sympy.ceiling,
}


def unary_expr(func, name: str, v):
    """Apply a unary math function to an Expr (or ExprNode-like) argument.

    Performs constant folding when *v* is a constant; otherwise builds a
    SymPy expression using the function mapped from *name*.

    Parameters
    ----------
    func:
        Python math function (e.g. ``math.sin``) for constant folding.
    name:
        McCode/C function name string (e.g. ``'sin'``).
    v:
        An :class:`Expr` instance.

    Returns
    -------
    Expr
    """
    from .expr import Expr
    if not isinstance(v, Expr):
        # Shouldn't happen in normal usage, but be defensive
        v = Expr.best(v)
    if v.is_constant and v.has_value:
        try:
            result = func(v.value)
            return Expr.float(float(result))
        except Exception:
            pass
    sym_func = _SYMPY_FUNC_MAP.get(name, sympy.Function(name))
    result = sym_func(v._exprs[0])
    # SymPy auto-simplifies sin(asin(x)) → x, etc.
    return Expr(result, DataType.float)


def binary_expr(func, name: str, left, right):
    """Apply a binary math function to two Expr arguments.

    Performs constant folding when both arguments are constants; otherwise
    builds a SymPy expression.

    Parameters
    ----------
    func:
        Python math function (e.g. ``math.atan2``) for constant folding.
    name:
        McCode/C function name string (e.g. ``'atan2'``).
    left, right:
        :class:`Expr` instances.

    Returns
    -------
    Expr
    """
    from .expr import Expr
    if not isinstance(left, Expr):
        left = Expr.best(left)
    if not isinstance(right, Expr):
        right = Expr.best(right)
    if left.is_constant and left.has_value and right.is_constant and right.has_value:
        try:
            result = func(left.value, right.value)
            return Expr.float(float(result))
        except Exception:
            pass
    sym_func = _SYMPY_FUNC_MAP.get(name, sympy.Function(name))
    result = sym_func(left._exprs[0], right._exprs[0])
    # Apply trigsimp to catch atan2(sin(x), cos(x)) → x and similar
    try:
        simplified = sympy.trigsimp(result)
        if simplified != result:
            result = simplified
    except Exception:
        pass
    return Expr(result, DataType.float)


# ---------------------------------------------------------------------------
# Legacy deserialization (kept for io migration)
# ---------------------------------------------------------------------------

def value_or_op_from_dict(args: dict):
    """Legacy: deserialise an ExprNode dict (old msgspec format) — no longer supported."""
    raise RuntimeError(
        "Old ExprNode serialization format (Value/UnaryOp/BinaryOp/TrinaryOp) is no longer supported. "
        "Regenerate cached files with the current version of mccode-antlr."
    )


def value_or_op_from_dict_legacy(args: dict):
    """Legacy stub — old ExprNode format no longer supported."""
    raise RuntimeError(
        "Old ExprNode serialization format is no longer supported. "
        "Regenerate cached files with the current version of mccode-antlr."
    )


def op_node_from_obj(obj):
    raise RuntimeError("Old ExprNode format no longer supported. Regenerate cached files.")


def op_post_init(obj, props: list[str], special: dict):
    """Legacy post-init helper — no longer supported."""
    raise RuntimeError("Old ExprNode format no longer supported. Regenerate cached files.")


def _from_legacy_expr_dict(args: dict):
    """Convert old msgspec Expr dict (with 'expr' key) to new Expr."""
    raise RuntimeError(
        "Old Expr serialization format (with 'expr' key containing ExprNode list) is no longer supported. "
        "Regenerate cached files with the current version of mccode-antlr."
    )

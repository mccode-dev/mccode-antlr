"""ANTLR visitor functions that build SymPy-backed Expr objects from parse trees."""
from .expression import Expr, ObjectType, ShapeType, DataType
from .expression.sympy_classes import (
    CPointerAccess, CStructAccess, CArrayIndex, CFunctionCall,
    CLeftShift, CRightShift, CTernary, CAnd, COr, CNot,
)
import sympy

# Known C math functions that have direct SymPy equivalents.
# For these, we use native SymPy objects so that SymPy can apply algebraic
# simplifications (e.g. sin²+cos²→1, sin(0)→0, sqrt(4)→2).
# All other C function calls fall back to CFunctionCall, which is opaque to SymPy.
# Each entry is (sympy_callable, return_DataType).  Using an explicit return type
# makes it straightforward to add integer-returning functions (isnan, isinf, …)
# in the future without misclassifying them as DataType.float.
_MATH_FUNCS: dict[str, tuple] = {
    # Trigonometric → float
    'sin':     (sympy.sin,      DataType.float),
    'cos':     (sympy.cos,      DataType.float),
    'tan':     (sympy.tan,      DataType.float),
    'asin':    (sympy.asin,     DataType.float),
    'acos':    (sympy.acos,     DataType.float),
    'atan':    (sympy.atan,     DataType.float),
    'atan2':   (sympy.atan2,    DataType.float),
    # Exponential / logarithm → float
    'exp':     (sympy.exp,      DataType.float),
    'log':     (sympy.log,      DataType.float),
    'sqrt':    (sympy.sqrt,     DataType.float),
    'cbrt':    (sympy.cbrt,     DataType.float),
    'pow':     (sympy.Pow,      DataType.float),
    # Absolute value — C99 printer renders sympy.Abs as fabs() → float
    'abs':     (sympy.Abs,      DataType.float),
    'fabs':    (sympy.Abs,      DataType.float),
    # Rounding — C99 printer renders floor/ceiling correctly → float (C returns double)
    'floor':   (sympy.floor,    DataType.float),
    'ceil':    (sympy.ceiling,  DataType.float),
    'ceiling': (sympy.ceiling,  DataType.float),
    # Remainder — C99 printer renders sympy.Mod as fmod() → float
    'fmod':    (sympy.Mod,      DataType.float),
}

def visitSomething(obj, ctx):
    pass

def getExpr(obj, ctx):
    return obj.visit(ctx)

def visitExpressionUnaryPM(obj, ctx):
    right = obj.visit(ctx.expr())
    if isinstance(right, str):
        return '-' + right if ctx.Plus() is None else right
    return -right if ctx.Plus() is None else right

def visitExpressionGrouping(obj, ctx):
    # Parentheses are implicit in SymPy tree; just return inner expression
    return obj.visit(ctx.expr())

def visitExpressionFloat(obj, ctx):
    return Expr.float(str(ctx.FloatingLiteral()))

def visitExpressionPointerAccess(obj, ctx):
    name = str(ctx.Identifier())
    obj_sym = sympy.Symbol(name)
    field = obj.visit(ctx.expr())
    field_sym = field._exprs[0] if isinstance(field, Expr) else sympy.Symbol(str(field))
    return Expr(CPointerAccess(obj_sym, field_sym), DataType.undefined)

def visitExpressionStructAccess(obj, ctx):
    name = str(ctx.Identifier())
    obj_sym = sympy.Symbol(name)
    field = obj.visit(ctx.expr())
    field_sym = field._exprs[0] if isinstance(field, Expr) else sympy.Symbol(str(field))
    return Expr(CStructAccess(obj_sym, field_sym), DataType.undefined)

def visitExpressionArrayAccess(obj, ctx):
    name = str(ctx.Identifier())
    arr_sym = sympy.Symbol(name)
    idx = obj.visit(ctx.expr())
    idx_sym = idx._exprs[0] if isinstance(idx, Expr) else sympy.sympify(idx)
    return Expr(CArrayIndex(arr_sym, idx_sym), DataType.undefined,
                ShapeType.scalar, ObjectType.identifier)

def visitExpressionIdentifier(obj, ctx):
    name = str(ctx.Identifier())
    inst_par = obj.state.get_parameter(name, None)
    if inst_par is not None:
        dat = inst_par.value.data_type
        return Expr.parameter(name, dat)
    return Expr.id(name)

def visitExpressionInteger(obj, ctx):
    return Expr.int(str(ctx.IntegerLiteral()))

def visitExpressionZero(obj, ctx):
    return Expr.int(0)

def visitExpressionExponentiation(obj, ctx):
    base, exponent = [obj.visit(ex) for ex in ctx.expr()]
    return base ** exponent

def visitExpressionBinaryPM(obj, ctx):
    left, right = [obj.visit(ex) for ex in ctx.expr()]
    return left + right if ctx.Minus() is None else left - right

def visitExpressionFunctionCall(obj, ctx):
    name = str(ctx.Identifier())
    args = [obj.visit(arg) for arg in ctx.expr()]
    arg_syms = [a._exprs[0] if isinstance(a, Expr) else sympy.sympify(a) for a in args]
    if name in _MATH_FUNCS:
        fn, dtype = _MATH_FUNCS[name]
        return Expr(fn(*arg_syms), dtype)
    return Expr(CFunctionCall(sympy.Symbol(name), *arg_syms), DataType.undefined)

def visitExpressionBinaryMD(obj, ctx):
    left, right = [obj.visit(ex) for ex in ctx.expr()]
    return left * right if ctx.Div() is None else left / right

def visitExpressionBinaryMod(obj, ctx):
    left, right = [obj.visit(ex) for ex in ctx.expr()]
    return left % right

def visitExpressionBinaryLeftShift(obj, ctx):
    left, right = [obj.visit(ex) for ex in ctx.expr()]
    l_sym = left._exprs[0] if isinstance(left, Expr) else sympy.sympify(left)
    r_sym = right._exprs[0] if isinstance(right, Expr) else sympy.sympify(right)
    return Expr(CLeftShift(l_sym, r_sym), DataType.int)

def visitExpressionBinaryRightShift(obj, ctx):
    left, right = [obj.visit(ex) for ex in ctx.expr()]
    l_sym = left._exprs[0] if isinstance(left, Expr) else sympy.sympify(left)
    r_sym = right._exprs[0] if isinstance(right, Expr) else sympy.sympify(right)
    return Expr(CRightShift(l_sym, r_sym), DataType.int)

def visitInitializerlist(obj, ctx):
    args = [obj.visit(x) for x in ctx.expr()]
    exprs = [a._exprs[0] if isinstance(a, Expr) else sympy.sympify(a) for a in args]
    return Expr(exprs, DataType.float, ShapeType.vector, ObjectType.initializer_list)

def visitExpressionUnaryLogic(obj, ctx):
    expr = obj.visit(ctx.expr())
    e_sym = expr._exprs[0] if isinstance(expr, Expr) else sympy.sympify(expr)
    result = CNot(e_sym)
    return Expr(result, DataType.int)

def visitExpressionBinaryLogic(obj, ctx):
    left, right = [obj.visit(ex) for ex in ctx.expr()]
    l_sym = left._exprs[0] if isinstance(left, Expr) else sympy.sympify(left)
    r_sym = right._exprs[0] if isinstance(right, Expr) else sympy.sympify(right)
    if ctx.AndAnd() is not None:
        result = CAnd(l_sym, r_sym)
    elif ctx.OrOr() is not None:
        result = COr(l_sym, r_sym)
    else:
        result = sympy.Symbol('unknown_logic')
    return Expr(result, DataType.int)

def visitExpressionTrinaryLogic(obj, ctx):
    test, true, false = [obj.visit(x) for x in ctx.expr()]
    t_sym = test._exprs[0] if isinstance(test, Expr) else sympy.sympify(test)
    tr_sym = true._exprs[0] if isinstance(true, Expr) else sympy.sympify(true)
    f_sym = false._exprs[0] if isinstance(false, Expr) else sympy.sympify(false)
    return Expr(CTernary(t_sym, tr_sym, f_sym), DataType.undefined)

def visitExpressionBinaryNotEqual(obj, ctx):
    left, right = [obj.visit(ex) for ex in ctx.expr()]
    return left.ne(right)

def visitExpressionBinaryEqual(obj, ctx):
    left, right = [obj.visit(ex) for ex in ctx.expr()]
    return left.eq(right)

def visitExpressionBinaryLessEqual(obj, ctx):
    left, right = [obj.visit(ex) for ex in ctx.expr()]
    return left.le(right)

def visitExpressionBinaryGreaterEqual(obj, ctx):
    left, right = [obj.visit(ex) for ex in ctx.expr()]
    return left.ge(right)

def visitExpressionBinaryLess(obj, ctx):
    left, right = [obj.visit(ex) for ex in ctx.expr()]
    return left.lt(right)

def visitExpressionBinaryGreater(obj, ctx):
    left, right = [obj.visit(ex) for ex in ctx.expr()]
    return left.gt(right)

def visitExpressionString(obj, ctx):
    strings = ''.join(str(sl).strip('"') for sl in ctx.StringLiteral())
    return Expr.str(f'"{strings}"')


common_visitors = (
    ('getExpr', getExpr),
    ('visitExpressionUnaryPM', visitExpressionUnaryPM),
    ('visitExpressionGrouping', visitExpressionGrouping),
    ('visitExpressionFloat', visitExpressionFloat),
    ('visitExpressionPointerAccess', visitExpressionPointerAccess),
    ('visitExpressionStructAccess', visitExpressionStructAccess),
    ('visitExpressionArrayAccess', visitExpressionArrayAccess),
    ('visitExpressionIdentifier', visitExpressionIdentifier),
    ('visitExpressionInteger', visitExpressionInteger),
    ('visitExpressionZero', visitExpressionZero),
    ('visitExpressionExponentiation', visitExpressionExponentiation),
    ('visitExpressionBinaryPM', visitExpressionBinaryPM),
    ('visitExpressionFunctionCall', visitExpressionFunctionCall),
    ('visitExpressionBinaryMD', visitExpressionBinaryMD),
    ('visitExpressionBinaryMod', visitExpressionBinaryMod),
    ('visitExpressionBinaryLeftShift', visitExpressionBinaryLeftShift),
    ('visitExpressionBinaryRightShift', visitExpressionBinaryRightShift),
    ('visitInitializerlist', visitInitializerlist),
    ('visitExpressionUnaryLogic', visitExpressionUnaryLogic),
    ('visitExpressionBinaryLogic', visitExpressionBinaryLogic),
    ('visitExpressionTrinaryLogic', visitExpressionTrinaryLogic),
    ('visitExpressionBinaryNotEqual', visitExpressionBinaryNotEqual),
    ('visitExpressionBinaryEqual', visitExpressionBinaryEqual),
    ('visitExpressionBinaryLessEqual', visitExpressionBinaryLessEqual),
    ('visitExpressionBinaryGreaterEqual', visitExpressionBinaryGreaterEqual),
    ('visitExpressionBinaryLess', visitExpressionBinaryLess),
    ('visitExpressionBinaryGreater', visitExpressionBinaryGreater),
    ('visitExpressionString', visitExpressionString),
)

def add_common_visitors(grammar_visitor):
    for name, func in common_visitors:
        setattr(grammar_visitor, name, func)

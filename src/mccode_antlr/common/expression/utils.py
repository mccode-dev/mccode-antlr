from __future__ import annotations

from .nodes import Value, UnaryOp, BinaryOp, TrinaryOp
from .types import DataType, OpStyle


def value_or_op_from_dict(args: dict):
    # Strip the msgspec tag discriminator if present (added by tag_field='type')
    args = {k: v for k, v in args.items() if k != 'type'}
    # Value: _value, _data, _object, _shape,
    if all(x in args for x in ('_value', '_data', '_object', '_shape')):
        return Value(**args)
    # UnaryOp, BinaryOp, TrinaryOp
    if all(x in args for x in ('data_type', 'style', 'op')):
        if all(x in args for x in ('value',)):
            return UnaryOp(**args)
        if all(x in args for x in ('left', 'right')):
            return BinaryOp(**args)
        if all(x in args for x in ('first', 'second', 'third')):
            return TrinaryOp(**args)
    print(f'{args=}')
    raise ValueError("Not a valid expression node element")


def op_node_from_obj(obj):
    if not hasattr(obj, '__len__'):
        raise ValueError('Op nodes should have length')
    return [value_or_op_from_dict(d) for d in obj]


def op_post_init(obj, props: list[str], special: dict):
    from .expr import Expr
    for prop in props:
        if isinstance(getattr(obj, prop), Expr):
            setattr(obj, prop, getattr(obj, prop).expr)
        if not isinstance(getattr(obj, prop), list):
            setattr(obj, prop, [getattr(obj, prop)])

    def data_type_set_list(i):
        return list(dict.fromkeys(x.data_type for x in getattr(obj, props[i])))

    for prop in props:
        if any(isinstance(x, dict) for x in getattr(obj, prop)):
            setattr(obj, prop, op_node_from_obj(getattr(obj, prop)))

    if obj.op in special:
        obj.data_type = special[obj.op]
    else:
        a = data_type_set_list(-1)
        b = data_type_set_list(-2) if len(props) > 1 else a
        if len(a) != 1 or len(b) != 1:
            raise RuntimeError('Multiple data types in one value not supported')
        obj.data_type = a[0] + b[0]

    for prop, typ in (('data_type', DataType), ('style', OpStyle)):
        if not isinstance(p := getattr(obj, prop), typ):
            setattr(obj, prop, typ(p))


def unary_expr(func, name, v):
    from .expr import Expr
    ops = {'cos': 'acos', 'sin': 'asin', 'tan': 'atan'}
    if isinstance(v, Expr):
        v = v.expr
    if len(v) == 1:
        v = v[0]
    if isinstance(v, UnaryOp) and ((name in ops and v.op == ops[name]) or (v.op in ops and name == ops[v.op])):
        return Expr(v.value)
    if isinstance(v, Value) and not v.is_id:
        if v.is_str or isinstance(v.value, str):
            raise RuntimeError(f'How is a _string_ valued parameter, {v} not an identifier?')
        return Expr(Value.best(func(v.value)))
    return Expr(UnaryOp(DataType.float, OpStyle.C, name, v))


def binary_expr(func, name, left, right):
    from .expr import Expr
    ops = {'atan2': ('sin', 'cos')}
    if isinstance(left, Expr):
        left = left.expr
    if isinstance(right, Expr):
        right = right.expr
    if len(left) == 1:
        left = left[0]
    if len(right) == 1:
        right = right[0]
    if isinstance(left, UnaryOp) and isinstance(right, UnaryOp) and name in ops:
        left_func, right_func = ops[name]
        if left.op == left_func and right.op == right_func and left.value == right.value:
            return Expr(left.value)
    if isinstance(left, Value) and isinstance(right, Value) and not left.is_id and not right.is_id:
        return Expr(Value.best(func(left.value, right.value)))
    return Expr(BinaryOp(DataType.float, OpStyle.C, name, left, right))

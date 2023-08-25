import ast
from dataclasses import dataclass
from typing import Union
from enum import Enum
from zenlog import log

# class NameReplacer(ast.NodeTransformer):
#     def __init__(self, **values):
#         self.values = values
#
#     def visit_Name(self, node):
#         if node.id in self.values:
#             return ast.Constant(self.values[node.id])
#         return node
#
#
# @dataclass
# class Expr:
#     expr: str = ""
#
#     @property
#     def ids(self):
#         from ast import walk, parse, Name
#         tree = parse(self.expr)
#         return list(set(x.id for x in walk(tree) if isinstance(x, Name)))
#
#     def eval(self, **values):
#         from ast import parse, fix_missing_locations, dump, literal_eval
#         if any(name not in values for name in self.ids):
#             raise RuntimeError(f"Not all of {self.ids} provided as keyword=value arguments")
#         tree = NameReplacer(**values).visit(parse(self.expr))
#         fixed = fix_missing_locations(tree)
#         print(eval(fixed))
#         print(dump(fixed))
#         obj = compile(fixed, '', 'exec')
#         eval(obj)


class ObjectType(Enum):
    value = 1
    initializer_list = 2
    identifier = 3
    function = 4
    parameter = 5

    @property
    def is_id(self):
        return self == ObjectType.identifier

    @property
    def is_parameter(self):
        return self == ObjectType.parameter

    @property
    def is_function(self):
        return self == ObjectType.function


class ShapeType(Enum):
    scalar = 1
    vector = 2

    @property
    def mccode_c_type(self):
        return '' if self == ShapeType.scalar else '*'

    def compatible(self, other):
        return self == other

    @property
    def is_scalar(self):
        return self == ShapeType.scalar

    @property
    def is_vector(self):
        return self == ShapeType.vector


class DataType(Enum):
    undefined = 0
    float = 1
    int = 2
    str = 3

    def compatible(self, other):
        if self == DataType.undefined or other == DataType.undefined or self == other:
            return True
        if (self == DataType.float and other == DataType.int) or (self == DataType.int and other == DataType.float):
            return True
        return False

    # promotion rules:
    def __add__(self, other):
        if self == DataType.undefined:
            return other
        if other == DataType.undefined:
            return self
        if self == other:
            return self
        if (self == DataType.float and other == DataType.int) or (self == DataType.int and other == DataType.float):
            return DataType.int
        return DataType.str

    __sub__ = __add__
    __mul__ = __add__
    __truediv__ = __add__

    @property
    def is_str(self):
        return self == DataType.str

    @property
    def mccode_c_type(self):
        if self == DataType.float:
            return "double"
        if self == DataType.int:
            return "int"
        if self == DataType.str:
            return "char *"
        raise RuntimeError("No known conversion from non-enumerated data type")


class BinaryOp:
    def __init__(self, op, left, right):
        if isinstance(left, Expr):
            left = left.expr
        if isinstance(right, Expr):
            right = right.expr
        self.op = op
        self.left = left
        self.right = right
        self.data_type = left.data_type + right.data_type
        self.style = 'C'  # there should be a better way to do this

    def _str_repr_(self, lstr, rstr):
        if '__call__' == self.op:
            return f'{lstr}({rstr})'
        if '__getitem__' == self.op:
            return f'{lstr}[{rstr}]'
        if '__pow__' == self.op:
            return f'{lstr}^{rstr}' if 'C' == self.style else f'{lstr}**{rstr}'
        if '__lt__' == self.op:
            return f'{lstr}<{rstr}'
        if '__gt__' == self.op:
            return f'{lstr}>{rstr}'
        if '__le__' == self.op:
            return f'{lstr}<={rstr}'
        if '__ge__' == self.op:
            return f'{lstr}>={rstr}'
        if '__eq__' == self.op:
            return f'{lstr}=={rstr}'
        if '__or__' == self.op:
            return f'{lstr} || {rstr}' if 'C' == self.style else f'{lstr} or {rstr}'
        if '__and__' == self.op:
            return f'{lstr} && {rstr}' if 'C' == self.style else f'{lstr} and {rstr}'
        if any(x in self.op for x in '+-'):
            return f'({lstr} {self.op} {rstr})'
        if any(x in self.op for x in '*/'):
            return f'{lstr} {self.op} {rstr}'
        return f'{self.op}({lstr}, {rstr})'

    def __str__(self):
        return self._str_repr_(str(self.left), str(self.right))

    def __repr__(self):
        return self._str_repr_(repr(self.left), repr(self.right))

    def __hash__(self):
        return hash(str(self))

    def __add__(self, other):
        if other.is_zero:
            return self
        return BinaryOp('+', self, other)

    def __sub__(self, other):
        if other.is_zero:
            return self
        return BinaryOp('-', self, other)

    def __mul__(self, other):
        if other.is_zero:
            return other
        if other.is_value(1):
            return self
        if other.is_value(-1):
            return -self
        return BinaryOp('*', self, other)

    def __truediv__(self, other):
        if other.is_zero:
            raise RuntimeError('Division by zero')
        if other.is_value(1):
            return self
        if other.is_value(-1):
            return -self
        return BinaryOp('/', self, other)

    def __neg__(self):
        return UnaryOp('-', self)

    def __pos__(self):
        return self

    def __abs__(self):
        return UnaryOp('abs', self)


    @property
    def is_zero(self):
        return False

    @property
    def is_op(self):
        return True

    @property
    def is_id(self):
        return False

    @property
    def is_parameter(self):
        return False

    @property
    def is_str(self):
        return False

    def __eq__(self, other):
        if not isinstance(other, BinaryOp):
            return False
        return self.op == other.op and self.left == other.left and self.right == other.right

    def is_value(self, other):
        return self == other

    @property
    def is_scalar(self):
        return self.left.is_scalar and self.right.is_scalar

    @property
    def is_vector(self):
        return self.left.is_vector or self.right.is_vector

    @property
    def vector_known(self):
        return self.left.vector_known and self.right.vector_known

    def __len__(self):
        return max(len(self.left), len(self.right))


class UnaryOp:
    def __init__(self, op, value):
        if isinstance(value, Expr):
            value = value.expr
        self.op = op
        self.value = value
        self.data_type = value.data_type

    def _str_repr_(self, vstr):
        if '__group__' == self.op:
            return f'({vstr})'
        if any(x in self.op for x in '+-'):
            return f'{self.op}{vstr}'
        return f'{self.op}({self.value})'

    def __str__(self):
        return self._str_repr_(str(self.value))

    def __repr__(self):
        return self._str_repr_(repr(self.value))

    def __hash__(self):
        return hash(str(self))

    def __add__(self, other):
        if other.is_zero:
            return self
        return BinaryOp('+', self, other)

    def __sub__(self, other):
        if other.is_zero:
            return self
        return BinaryOp('-', self, other)

    def __mul__(self, other):
        if other.is_zero:
            return other
        if other.is_value(1):
            return self
        if other.is_value(-1):
            return -self
        return BinaryOp('*', self, other)

    def __truediv__(self, other):
        if other.is_zero:
            raise RuntimeError('Division by zero')
        if other.is_value(1):
            return self
        if other.is_value(-1):
            return -self
        return BinaryOp('/', self, other)

    def __neg__(self):
        if self.op == '-':
            return self.value
        return UnaryOp('-', self)

    def __pos__(self):
        return self

    def __abs__(self):
        if self.op == 'abs':
            # abs(abs(x)) is abs(x)
            return self
        return UnaryOp('abs', self)

    @property
    def is_zero(self):
        return False

    @property
    def is_op(self):
        return True

    @property
    def is_id(self):
        return False

    @property
    def is_parameter(self):
        return False

    @property
    def is_str(self):
        return False

    def __eq__(self, other):
        if not isinstance(other, UnaryOp):
            return False
        return self.op == other.op and self.value == other.value

    @property
    def is_scalar(self):
        return self.value.is_scalar

    @property
    def is_vector(self):
        return self.value.is_vector

    @property
    def vector_known(self):
        return self.value.vector_known

    def is_value(self, value):
        return self == value

    def __len__(self):
        return len(self.value)

    def __gt__(self, other):
        log.debug(f'{self} > {other}')
        return False


class Value:
    def __init__(self, value, data_type=None, object_type=None, shape_type=None):
        self._value = value
        if data_type is None or not isinstance(data_type, DataType):
            data_type = DataType.undefined
        if object_type is None or not isinstance(object_type, ObjectType):
            object_type = ObjectType.identifier if data_type != DataType.str and isinstance(value, str) else ObjectType.value
        if shape_type is None or not isinstance(shape_type, ShapeType):
            shape_type = ShapeType.vector if not isinstance(value, str) and hasattr(value, '__len__') else ShapeType.scalar
        self._object = object_type
        self._data = data_type
        self._shape = shape_type

    @property
    def value(self):
        return self._value

    @property
    def object_type(self):
        return self._object

    @property
    def data_type(self):
        return self._data

    @property
    def shape_type(self):
        return self._shape

    @value.setter
    def value(self, value):
        log.debug(f'Updating Value from {self._value} to {value}')
        self._object = self.data_type != DataType.str and isinstance(value, str)
        self._value = value

    @data_type.setter
    def data_type(self, dt):
        self._data = dt

    @property
    def has_value(self):
        return self.value is not None

    @property
    def vector_known(self):
        return self.is_vector and self.has_value and not isinstance(self.value, str)

    def _str_repr_(self):
        return f'_instrument_var._parameters.{self.value}' if self.is_parameter else f'{self.value}'

    def __str__(self):
        return self._str_repr_()

    def __repr__(self):
        return f'{self.shape_type} {self.data_type} {self._str_repr_()}'

    def __hash__(self):
        return hash(str(self))

    def compatible(self, other, id_ok=False):
        if isinstance(other, (UnaryOp, BinaryOp)):
            return id_ok
        value = other if isinstance(other, Value) else Value.best(other)
        return (id_ok and value.is_str) or (self.data_type.compatible(value.data_type) and self.shape_type.compatible(value.shape_type))

    @classmethod
    def float(cls, value):
        try:
            v = float(value) if value is not None else None
        except ValueError:
            v = value
        return cls(v, DataType.float)

    @classmethod
    def int(cls, value):
        try:
            v = int(value) if value is not None else None
        except ValueError:
            v = value
        return cls(v, DataType.int)

    @classmethod
    def str(cls, value):
        return cls(value, DataType.str)

    @classmethod
    def id(cls, value):
        return cls(value, DataType.str)

    @classmethod
    def array(cls, value, dt=None):
        return cls(value, data_type=dt, object_type=None, shape_type=ShapeType.vector)

    @classmethod
    def function(cls, value, dt=None):
        return cls(value, object_type=ObjectType.function)

    @classmethod
    def best(cls, value):
        if isinstance(value, str):
            return cls(value, DataType.str)
        if isinstance(value, int) or (isinstance(value, float) and value.is_integer()):
            return cls(value, DataType.int)
        return cls(value, DataType.float)

    @property
    def is_id(self):
        return self.data_type != DataType.str and isinstance(self.value, str)

    @property
    def is_parameter(self):
        return self.object_type.is_parameter

    @property
    def is_str(self):
        return self.data_type.is_str

    @property
    def is_op(self):
        return False

    @property
    def is_zero(self):
        return not self.is_id and self.value == 0

    def is_value(self, v):
        return not self.is_id and v.is_value(self.value) if hasattr(v, 'is_value') else self.value == v

    @property
    def is_scalar(self):
        return self.shape_type.is_scalar

    @property
    def is_vector(self):
        return self.shape_type.is_vector

    def __len__(self):
        return len(self.value) if self.is_vector else 1

    def __add__(self, other):
        other = other if isinstance(other, (Value, UnaryOp, BinaryOp)) else Value.best(other)
        if self.is_zero:
            return other
        if other.is_zero:
            return self
        if other.is_op and isinstance(other, UnaryOp) and other.op == '-':
            return self - other.value
        if self.is_id and (isinstance(other, Value) and not isinstance(other.value, str) and other < 0):
            return self - (-other.value)
        if other.is_op or self.is_id or other.is_id or isinstance(other, BinaryOp):
            return BinaryOp('+', self, other)
        pdt = self.data_type + other.data_type
        return BinaryOp('+', self, other) if pdt.is_str else Value(self.value + other.value, pdt)

    def __sub__(self, other):
        other = other if isinstance(other, (Value, UnaryOp, BinaryOp)) else Value.best(other)
        if self.is_zero:
            return -other
        if other.is_zero:
            return self
        if other.is_op and isinstance(other, UnaryOp) and other.op == '-':
            return self + other.value
        if self.is_id and (isinstance(other, Value) and not isinstance(other.value, str) and other < 0):
            return self + (-other.value)
        if other.is_op or self.is_id or other.is_id or isinstance(other, BinaryOp):
            return BinaryOp('-', self, other)
        pdt = self.data_type - other.data_type
        return BinaryOp('-', self, other) if pdt.is_str else Value(self.value - other.value, pdt)

    def __mul__(self, other):
        other = other if isinstance(other, (Value, UnaryOp, BinaryOp)) else Value.best(other)
        pdt = self.data_type * other.data_type
        if self.is_zero or other.is_zero:
            return Value(0, DataType.int if pdt.is_str else pdt)
        if self.is_value(1):
            return other
        if self.is_value(-1):
            return -other
        if other.is_op or self.is_id or other.is_id:
            return BinaryOp('*', self, other)
        return BinaryOp('*', self, other) if pdt.is_str else Value(self.value * other.value, pdt)

    def __truediv__(self, other):
        other = other if isinstance(other, (Value, UnaryOp, BinaryOp)) else Value.best(other)
        pdt = self.data_type / other.data_type
        if self.is_zero:
            return Value(0, DataType.int if pdt.is_str else pdt)
        if other.is_value(1):
            return self
        if other.is_value(-1):
            return -self
        if other.is_zero:
            raise RuntimeError('Division by zero!')
        if other.is_op or self.is_id or other.is_id:
            return BinaryOp('/', self, other)
        return BinaryOp('/', self, other) if pdt.is_str else Value(self.value / other.value, pdt)

    def __neg__(self):
        return UnaryOp('-', self) if self.is_id or self.data_type.is_str else Value(-self.value, self.data_type)

    def __pos__(self):
        return Value(self.value, self.data_type)

    def __abs__(self):
        return UnaryOp('abs', self) if self.is_id or self.data_type.is_str else Value(abs(self.value), self.data_type)

    def __eq__(self, other):
        other = other if isinstance(other, (Value, UnaryOp, BinaryOp)) else Value.best(other)
        if other.is_op:
            return False
        return self.value == other.value

    def __lt__(self, other):
        other = other if isinstance(other, (Value, UnaryOp, BinaryOp)) else Value.best(other)
        if self.is_id or other.is_op or other.is_id:
            return BinaryOp('__lt__', self, other)
        return self.value < other.value

    def __gt__(self, other):
        other = other if isinstance(other, (Value, UnaryOp, BinaryOp)) else Value.best(other)
        if self.is_id or other.is_op or other.is_id:
            return BinaryOp('__gt__', self, other)
        return self.value > other.value

    def __pow__(self, power):
        if not isinstance(power, (Value, UnaryOp, BinaryOp)):
            power = Value.best(power)
        if self.is_zero or self.is_value(1):
            return self
        if power.is_zero:
            return Value(1, data_type=self.data_type)
        return BinaryOp('__pow__', self, power)

    @property
    def mccode_c_type(self):
        return self.data_type.mccode_c_type + self.shape_type.mccode_c_type

    @property
    def mccode_c_type_name(self):
        if self.data_type == DataType.float and self.shape_type == ShapeType.scalar:
            return "instr_type_double"
        if self.data_type == DataType.int and self.shape_type == ShapeType.scalar:
            return "instr_type_int"
        if self.data_type == DataType.str and self.shape_type == ShapeType.scalar:
            return "instr_type_string"
        if self.data_type == DataType.float and self.shape_type == ShapeType.vector:
            return "instr_type_vector"
        if self.data_type == DataType.int and self.shape_type == ShapeType.vector:
            return "instr_type_vector"
        raise RuntimeError("No known conversion from non-enumerated data type")


class Expr:
    def __init__(self, expr: Union[Value, UnaryOp, BinaryOp]):
        self.expr = expr

    def __str__(self):
        return str(self.expr)

    def __repr__(self):
        return repr(self.expr)

    def __hash__(self):
        return hash(self.expr)

    @classmethod
    def float(cls, value):
        if isinstance(value, cls):
            # Make sure the held expression *thinks* it's a float:
            if value.expr.data_type != DataType.float:
                value.expr.data_type = DataType.float
            return value
        return cls(Value.float(value))

    @classmethod
    def int(cls, value):
        if isinstance(value, cls):
            # Make sure the held expression *thinks* it's a float:
            if value.expr.data_type != DataType.int:
                log.error(f'Why does {value} think it is a {value.expr.data_type} and not {DataType.int}?')
                value.expr.data_type = DataType.int
            return value
        return cls(Value.int(value))

    @classmethod
    def str(cls, value):
        if isinstance(value, cls):
            # Make sure the held expression *thinks* it's a float:
            if value.expr.data_type != DataType.str:
                log.error(f'Why does {value} think it is a {value.expr.data_type} and not {DataType.str}?')
                value.expr.data_type = DataType.str
            return value
        return cls(Value.str(value))

    @classmethod
    def id(cls, value):
        if isinstance(value, cls):
            return value
        return cls(Value.id(value))

    @classmethod
    def array(cls, value):
        return cls(Value.array(value))

    @classmethod
    def function(cls, value):
        return cls(Value.function(value))

    @classmethod
    def best(cls, value):
        return cls(Value.best(value))

    @property
    def is_op(self):
        return self.expr.is_op

    @property
    def is_zero(self):
        return self.expr.is_zero

    @property
    def is_id(self):
        return self.expr.is_id

    @property
    def is_parameter(self):
        return self.expr.is_parameter

    @property
    def is_str(self):
        return self.expr.is_str

    @property
    def is_scalar(self):
        return self.expr.is_scalar

    def is_value(self, value):
        return self.expr.is_value(value)

    @property
    def is_vector(self):
        return self.expr.is_vector

    def __len__(self):
        return len(self.expr)

    @property
    def is_constant(self):
        return isinstance(self.expr, Value) and not self.expr.is_id

    @property
    def has_value(self):
        return self.is_constant and self.expr.has_value

    @property
    def vector_known(self):
        return self.is_constant and self.expr.vector_known

    @property
    def value(self):
        if not self.is_constant:
            raise NotImplementedError("No conversion from expressions to constants ... yet")
        return self.expr.value

    def compatible(self, other, id_ok=False):
        other_expr = other.expr if isinstance(other, Expr) else other
        return self.expr.compatible(other_expr, id_ok)

    def __add__(self, other):
        other_expr = other.expr if isinstance(other, Expr) else other
        return Expr(self.expr + other_expr)

    def __sub__(self, other):
        other_expr = other.expr if isinstance(other, Expr) else other
        return Expr(self.expr - other_expr)

    def __mul__(self, other):
        other_expr = other.expr if isinstance(other, Expr) else other
        return Expr(self.expr * other_expr)

    def __truediv__(self, other):
        other_expr = other.expr if isinstance(other, Expr) else other
        return Expr(self.expr / other_expr)

    def __neg__(self):
        return Expr(-self.expr)

    def __pos__(self):
        return self

    def __abs__(self):
        return Expr(abs(self.expr))

    def __eq__(self, other):
        other_expr = other.expr if isinstance(other, Expr) else other
        return self.expr == other_expr

    def __lt__(self, other):
        other_expr = other.expr if isinstance(other, Expr) else other
        return self.expr < other_expr

    def __gt__(self, other):
        other_expr = other.expr if isinstance(other, Expr) else other
        return self.expr > other_expr

    @property
    def mccode_c_type(self):
        return self.expr.mccode_c_type

    @property
    def mccode_c_type_name(self):
        return self.expr.mccode_c_type_name


def unary_expr(func, name, v):
    ops = {'cos': 'acos', 'sin': 'asin', 'tan': 'atan'}
    if isinstance(v, Expr):
        v = v.expr
    if isinstance(v, UnaryOp) and ((name in ops and v.op == ops[name]) or (v.op in ops and name == ops[v.op])):
        return Expr(v.value)
    if isinstance(v, Value) and not v.is_id:
        if v.is_str or isinstance(v.value, str):
            raise RuntimeError(f'How is a _string_ valued parameter, {v} not an identifier?')
        return Expr(Value.best(func(v.value)))
    return Expr(UnaryOp(name, v))


def binary_expr(func, name, left, right):
    ops = {'atan2': ('sin', 'cos')}
    if isinstance(left, Expr):
        left = left.expr
    if isinstance(right, Expr):
        right = right.expr
    if isinstance(left, UnaryOp) and isinstance(right, UnaryOp) and name in ops:
        left_func, right_func = ops[name]
        if left.op == left_func and right.op == right_func and left.value == right.value:
            return Expr(left.value)
    if isinstance(left, Value) and isinstance(right, Value) and not left.is_id and not right.is_id:
        return Expr(Value.best(func(left.value, right.value)))
    return Expr(BinaryOp(name, left, right))

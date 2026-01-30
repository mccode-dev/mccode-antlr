from __future__ import annotations

from typing import Union, Optional

from enum import Enum, IntEnum

from loguru import logger

from msgspec import Struct

class ObjectType(Enum):
    value = 1
    initializer_list = 2
    identifier = 3
    function = 4
    parameter = 5

    def __str__(self):
        return self.name

    @staticmethod
    def from_name(name):
        if 'value' in name:
            return ObjectType.value
        if 'initializer_list' in name:
            return ObjectType.initializer_list
        if 'identifier' in name:
            return ObjectType.identifier
        if 'function' in name:
            return ObjectType.function
        if 'parameter' in name:
            return ObjectType.parameter
        raise RuntimeError(f"No known conversion from non-enumerated object type {name}")

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
    unknown = 0
    scalar = 1
    vector = 2

    @property
    def mccode_c_type(self):
        return '*' if self.is_vector else ''

    def compatible(self, other):
        return self == ShapeType.unknown or other == ShapeType.unknown or self == other

    @property
    def is_scalar(self):
        return self == ShapeType.scalar

    @property
    def is_vector(self):
        return self == ShapeType.vector

    def __str__(self):
        return self.name

    @staticmethod
    def from_name(name):
        if 'vector' in name:
            return ShapeType.vector
        if 'scalar' in name:
            return ShapeType.scalar
        return ShapeType.unknown


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
            return DataType.float
        return DataType.str

    __sub__ = __add__
    __mul__ = __add__

    def __truediv__(self, other):
        if self == DataType.str or other == DataType.str:
            raise RuntimeError('Division of strings is undefined')
        return DataType.float

    def __floordiv__(self, other):
        return DataType.int

    @classmethod
    def from_name(cls, name):
        if 'double' in name or 'float' in name:
            return cls.float
        if 'int' in name:
            return cls.int
        if 'char' in name or 'string' in name or 'str' in name:
            return cls.str
        return cls.undefined

    @property
    def name(self):
        if self == DataType.int:
            return 'int'
        if self == DataType.float:
            return 'float'
        if self == DataType.str:
            return 'str'
        return 'undefined'

    @property
    def is_int(self):
        return self == DataType.int

    @property
    def is_float(self):
        return self == DataType.float

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
        raise RuntimeError(f"No known conversion from non-enumerated data type {self}")


def _comb(f, s: list):
    return ','.join(f(x) for x in s)


def _fmt_comb(fmt, s: list):
    return ','.join(f'{x:{fmt}}' for x in s)


class OpStyle (IntEnum):
    C = 1
    PYTHON = 2


# @dataclass
class Op(Struct):
    data_type: DataType
    style: OpStyle

    def __hash__(self):
        return hash(str(self))

    def __int__(self):
        raise RuntimeError('No conversion to int for operations')

    @property
    def is_op(self):
        return True

    @property
    def is_zero(self):
        return False

    @property
    def is_id(self):
        return False

    @property
    def is_constant(self):
        return False

    @property
    def is_parameter(self):
        return False

    @property
    def is_str(self):
        return self.data_type.is_str

    def is_value(self, other):
        return self == other

    @property
    def is_scalar(self):
        return False

    @property
    def is_vector(self):
        return False

    @property
    def vector_known(self):
        return False

    def __add__(self, other):
        if other.is_zero:
            return self
        return BinaryOp(self.data_type, self.style, '+', [self], other)

    def __sub__(self, other):
        if other.is_zero:
            return self
        return BinaryOp(self.data_type, self.style, '-', [self], other)

    def __mul__(self, other):
        if other.is_zero:
            return other
        if other.is_value(1):
            return self
        if other.is_value(-1):
            return -self
        return BinaryOp(self.data_type, self.style, '*', [self], other)

    def __truediv__(self, other):
        if other.is_zero:
            raise RuntimeError('Division by zero')
        if other.is_value(1):
            return self
        if other.is_value(-1):
            return -self
        return BinaryOp(self.data_type, self.style, '/', [self], other)

    def __floordiv__(self, other):
        if other.is_zero:
            raise RuntimeError('Division by zero')
        if other.is_value(1):
            return self
        if other.is_value(-1):
            return -self
        return BinaryOp(self.data_type, self.style, '//', [self], other)

    def __neg__(self):
        return UnaryOp(self.data_type, self.style, '-', [self])

    def __pos__(self):
        return self

    def __abs__(self):
        return UnaryOp(self.data_type, self.style, 'abs', [self])

    def as_type(self, pdt):
        raise NotImplementedError()

# @dataclass
class TrinaryOp(Op):
    op: str
    first: OpNode
    second: OpNode
    third: OpNode

    def __post_init__(self):
        op_post_init(self, ['first', 'second', 'third'], {})

    def as_type(self, pdt):
        first = [x.as_type(pdt) for x in self.first]
        second = [x.as_type(pdt) for x in self.second]
        third = [x.as_type(pdt) for x in self.third]
        return TrinaryOp(self.data_type, self.style, self.op, first, second, third)

    def _str_repr_(self, first, second, third):
        if '__trinary__' == self.op:
            if self.style == OpStyle.C:
                return f'{first} ? {second} : {third}'
            return f'{second} if {first} else {third}'
        raise ValueError('Only trinary three-argument operators are supported')

    def __str__(self):
        return self._str_repr_(_comb(str, self.first), _comb(str, self.second), _comb(str, self.third))

    def __format__(self, format_spec):
        return self._str_repr_(_fmt_comb(format_spec, self.first), _fmt_comb(format_spec, self.second), _fmt_comb(format_spec, self.third))

    def __repr__(self):
        return self._str_repr_(_comb(repr, self.first), _comb(repr, self.second), _comb(repr, self.third))

    def __eq__(self, other):
        if not isinstance(other, TrinaryOp):
            return False
        return self.op == other.op and self.first == other.first and self.second == other.second and self.third == other.third

    @property
    def is_scalar(self):
        return len(self.first) == 1 and len(self.second) == 1 and len(self.third) == 1\
            and self.first[0].is_scalar and self.second[0].is_scalar and self.third[0].is_scalar

    @property
    def is_vector(self):
        return len(self.first) == 1 and len(self.second) == 1 and len(self.third) == 1 \
            and self.first[0].is_vector and self.second[0].is_vector and self.third[0].is_vector

    @property
    def vector_known(self):
        return len(self.first) == 1 and len(self.second) == 1 and len(self.third) == 1 \
            and self.first[0].vector_known and self.second[0].vector_known and self.third[0].vector_known

    def simplify(self):
        f, s, t = [[x.simplify() for x in y] for y in (self.first, self.second, self.third)]
        if self.op == '__trinary__' and len(f) == 1:
            if f[0].is_value(True) and not f[0].is_value(False):
                return s
            if f[0].is_value(False) and not f[0].is_value(True):
                return t
        return TrinaryOp(self.data_type, self.style, self.op, f, s, t)

    def evaluate(self, known: dict):
        def evaluate_to_single(node):
            v = node.evaluate(known)
            return v[0] if hasattr(v, '__len__') and len(v) == 1 else v
        first, second, third = [[evaluate_to_single(x) for x in y] for y in (self.first, self.second, self.third)]
        return TrinaryOp(self.data_type, self.style, self.op, first, second, third).simplify()

    def depends_on(self, name: str):
        return any(any(x.depends_on(name) for x in y) for y in (self.first, self.second, self.third))

    def copy(self):
        return TrinaryOp(self.data_type, self.style, self.op, self.first, self.second, self.third)

    def __contains__(self, value):
        # first, second, and third are lists, so we need to check each element to avoid using __eq__
        return any([any(value in x for x in y) for y in (self.first, self.second, self.third)])

    def verify_parameters(self, instrument_parameter_names: list[str]):
        for lr in (self.first, self.second, self.third):
            for x in lr:
                x.verify_parameters(instrument_parameter_names)


# @dataclass
class BinaryOp(Op):
    op: str
    left: OpNode
    right: OpNode

    def __post_init__(self):
        special = {k: DataType.undefined for k in (
            '__call__', '__struct_access__', '__pointer_access__', '__getitem__')}
        op_post_init(self, ['left', 'right'], special)

    def as_type(self, pdt):
        left = [x.as_type(pdt) for x in self.left]
        right = [x.as_type(pdt) for x in self.right]
        return BinaryOp(self.data_type, self.style, self.op, left, right)

    def _str_repr_(self, lstr, rstr):
        c_style = self.style == OpStyle.C
        if '__call__' == self.op:
            return f'{lstr}({rstr})'
        if '__struct_access__' == self.op:
            return f'{lstr}.{rstr}' if c_style else f'getattr({lstr}, "{rstr}")'
        if '__pointer_access__' == self.op:
            return f'{lstr}->{rstr}' if c_style else f'getattr({lstr}, "{rstr}")'
        if '__getitem__' == self.op:
            return f'{lstr}[{rstr}]'
        if '__pow__' == self.op:
            return f'{lstr}^{rstr}' if c_style else f'{lstr}**{rstr}'
        if '__lt__' == self.op:
            return f'{lstr}<{rstr}'
        if '__gt__' == self.op:
            return f'{lstr}>{rstr}'
        if '__le__' == self.op:
            return f'{lstr}<={rstr}'
        if '__ge__' == self.op:
            return f'{lstr}>={rstr}'
        if '__neq__' == self.op:
            return f'{lstr}!={rstr}'
        if '__eq__' == self.op:
            return f'{lstr}=={rstr}'
        if '__or__' == self.op:
            return f'{lstr} || {rstr}' if c_style else f'{lstr} or {rstr}'
        if '__and__' == self.op:
            return f'{lstr} && {rstr}' if c_style else f'{lstr} and {rstr}'
        if any(x == self.op for x in ('+', '-', '%', '<<', '>>')):
            return f'({lstr} {self.op} {rstr})'
        if self.op == '//' and c_style:
            # Verify that the operands are integers before reducing to a single slash?
            return f'{lstr} / {rstr}'
        if any(x in self.op for x in '*/'):
            return f'{lstr} {self.op} {rstr}'
        return f'{self.op}({lstr}, {rstr})'

    def __str__(self):
        return self._str_repr_(_comb(str, self.left), _comb(str, self.right))

    def __format__(self, format_spec):
        return self._str_repr_(_fmt_comb(format_spec, self.left), _fmt_comb(format_spec, self.right))

    def __repr__(self):
        return self._str_repr_(_comb(repr, self.left), _comb(repr, self.right))

    def __eq__(self, other):
        if not isinstance(other, BinaryOp):
            return False
        if self.op != other.op:
            return False
        if self.op == '*' or self.op == '+':
            # Have we implemented any other commutative operations?
            if self.left == other.right and self.right == other.left:
                return True
        return self.left == other.left and self.right == other.right

    def __round__(self, n=None):
        return self if self.data_type.is_int else UnaryOp(self.data_type, self.style, 'round', [self])

    @property
    def is_scalar(self):
        return len(self.left) == 1 and len(self.right) == 1 and self.left[0].is_scalar and self.right[0].is_scalar

    @property
    def is_vector(self):
        if len(self.left) == 1 and len(self.right) == 1:
            lv = self.left[0].is_vector
            rv = self.right[0].is_vector
            rs = self.right[0].is_scalar
            if lv and rs and self.op == '__getitem__':
                return False
            return lv and rv
        return False

    @property
    def vector_known(self):
        return len(self.left) == 1 and len(self.right) == 1 and self.left[0].vector_known and self.right[0].vector_known
    #
    # def __len__(self):
    #     return max(len(self.left), len(self.right))

    def simplify(self):
        left = [x.simplify() for x in self.left]
        right = [x.simplify() for x in self.right]
        if len(left) == 1 and ((left[0].is_zero and self.op == '+') or (left[0].is_value(1) and self.op == '*')):
            return right
        if len(right) == 1 and (
                (right[0].is_zero and any(x == self.op for x in '+-')) or
                (right[0].is_value(1) and any(x == self.op for x in '*/'))
        ):
            return left
        if len(left) == 1 and len(right) == 1 and left[0].is_constant and right[0].is_constant:
            if self.op == '+':
                return left[0] + right[0]
            if self.op == '-':
                return left[0] - right[0]
            if self.op == '*':
                return left[0] * right[0]
            if self.op == '/':
                return left[0] / right[0]
            if self.op == '__pow__':
                return left[0] ** right[0]
        # punt!
        return BinaryOp(self.data_type, self.style, self.op, left, right)

    def evaluate(self, known: dict):
        def evaluate_to_single(node):
            v = node.evaluate(known)
            return v[0] if hasattr(v, '__len__') and len(v) == 1 else v
        left, right = [[evaluate_to_single(x) for x in y] for y in (self.left, self.right)]
        return BinaryOp(self.data_type, self.style, self.op, left, right).simplify()

    def depends_on(self, name: str):
        return any(any(x.depends_on(name) for x in y) for y in (self.left, self.right))

    def copy(self):
        return BinaryOp(self.data_type, self.style, self.op, self.left.copy(), self.right.copy())

    def __contains__(self, value):
        # left and right are lists, so we need to check each element to avoid using __eq__
        return any(value in x for x in self.left) or any(value in x for x in self.right)

    def verify_parameters(self, instrument_parameter_names: list[str]):
        for lr in (self.left, self.right):
            for x in lr:
                x.verify_parameters(instrument_parameter_names)


# @dataclass
class UnaryOp(Op):
    op: str
    value: OpNode

    def __post_init__(self):
        op_post_init(self, ['value'], {})

    def as_type(self, pdt):
        value = [x.as_type(pdt) for x in self.value]
        return UnaryOp(data_type=self.data_type, style=self.style, op=self.op, value=value)

    def _str_repr_(self, vstr):
        c_style = self.style == OpStyle.C
        if '__group__' == self.op:
            return f'({vstr})'
        if '__not__' == self.op:
            return f'!{vstr}' if c_style else f'not {vstr}'
        if any(x in self.op for x in '+-'):
            return f'{self.op}{vstr}'
        return f'{self.op}({vstr})'

    def __str__(self):
        return self._str_repr_(_comb(str, self.value))

    def __format__(self, format_spec):
        return self._str_repr_(_fmt_comb(format_spec, self.value))

    def __repr__(self):
        return self._str_repr_(_comb(repr, self.value))

    def __neg__(self):
        if self.op == '-':
            # Avoid returning a list unless we need to
            return self.value if len(self.value) != 1 else self.value[0]
        return UnaryOp(self.data_type, self.style, '-', [self])

    def __abs__(self):
        if self.op == 'abs':
            # abs(abs(x)) is abs(x)
            return self
        return UnaryOp(self.data_type, self.style, 'abs', [self])

    def __eq__(self, other):
        if not isinstance(other, UnaryOp):
            return False
        return self.op == other.op and self.value == other.value

    def __round__(self, n=None):
        return self if self.data_type.is_int else UnaryOp(self.data_type, self.style, 'round', [self])

    @property
    def is_scalar(self):
        return len(self.value) == 1 and self.value[0].is_scalar

    @property
    def is_vector(self):
        return len(self.value) == 1 and self.value[0].is_vector

    @property
    def vector_known(self):
        return len(self.value) == 1 and self.value[0].vector_known

    # def __len__(self):
    #     return len(self.value)

    def __gt__(self, other):
        logger.debug(f'{self} > {other} has been called (but probably should not have been!)')
        return False

    def simplify(self):
        value = [v.simplify() for v in self.value]
        if self.op == '__group__' and len(value) == 1 and isinstance(value[0], Value):
            return value[0]  # Expr(value)
        elif self.op == '-' and len(value) == 1 and isinstance(value[0], Value):
            return -value[0]
        elif self.op == '+' and len(value) == 1 and isinstance(value[0], Value):
            return value[0]
        return UnaryOp(self.data_type, self.style, self.op, value)

    def evaluate(self, known: dict):
        def evaluate_to_single(node):
            v = node.evaluate(known)
            return v[0] if hasattr(v, '__len__') and len(v) == 1 else v
        value = [evaluate_to_single(x) for x in self.value]
        return UnaryOp(self.data_type, self.style, self.op, value).simplify()

    def depends_on(self, name: str):
        return any(x.depends_on(name) for x in self.value)

    def copy(self):
        return UnaryOp(self.data_type, self.style, self.op, [v.copy() for v in self.value])

    def __contains__(self, value):
        # value is a list
        return any(value in x for x in self.value)

    def verify_parameters(self, instrument_parameter_names: list[str]):
        for x in self.value:
            x.verify_parameters(instrument_parameter_names)


# @dataclass
class Value(Struct):
    _value: int | float | str | list[int] | list[float] | list[str]
    _data: DataType = DataType.undefined
    _object: Optional[ObjectType] = None
    _shape: Optional[ShapeType] = None

    def __post_init__(self):
        if self._object is None:
            self._object = ObjectType.identifier if self._data != DataType.str and isinstance(self._value, str) else ObjectType.value
        if self._shape is None:
            self._shape = ShapeType.vector if not isinstance(self._value, str) and hasattr(self._value, '__len__') else ShapeType.scalar

        for prop, typ in zip(('_data', '_object', '_shape'), (DataType, ObjectType, ShapeType)):
            if not isinstance(getattr(self, prop), typ):
                setattr(self, prop, typ(getattr(self, prop)))


    def __int__(self):
        if self.data_type != DataType.int:
            raise RuntimeError('Non-integer data type Value; round first')
        return self._value

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

    @shape_type.setter
    def shape_type(self, st):
        if not isinstance(st, ShapeType):
            raise RuntimeError('Non ShapeType value set for shape_type')
        if st.is_vector:
            if self.is_str:
                raise RuntimeError('No support for vectors of strings, e.g. char**')
            if not self.is_id or not hasattr(self.value, '__len__'):
                raise RuntimeError('Can not make a scalar value have vector type unless it is an identifier')
            self._shape = st
        else:
            if not (self.is_str or self.is_id) and hasattr(self.value, '__len__'):
                raise RuntimeError('Can not make vector value have scalar type')
            self._shape = st

    @value.setter
    def value(self, value):
        logger.debug(f'Updating Value from {self._value} to {value}')
        # self._object = self.data_type != DataType.str and isinstance(value, str)
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

    def special_str(self, prefix=None):
        if prefix is None:
            prefix = "_instrument_var._parameters."
        return f'{prefix}{self.value}' if self.is_parameter else f'{self.value}'

    def _str_repr_(self):
        return str(self.value)

    def __str__(self):
        return self._str_repr_()

    def __format__(self, format_spec):
        """Abuse string format specifications to prepend the _instrument_var._parameters. prefix to parameters"""
        if format_spec == 'p':
            return self.special_str()
        elif format_spec.startswith('prefix:'):
            return self.special_str(format_spec[7:])
        return self._str_repr_()

    def __repr__(self):
        return f'{self.shape_type} {self.data_type} {self._str_repr_()}'

    def __hash__(self):
        return hash(str(self))

    def compatible(self, other, id_ok=False):
        if isinstance(other, Expr) and other.is_singular:
            other = other.expr[0]
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
        return cls(v, DataType.float, ObjectType.value, ShapeType.scalar)

    @classmethod
    def int(cls, value):
        try:
            v = int(value) if value is not None else None
        except ValueError:
            v = value
        return cls(v, DataType.int, ObjectType.value, ShapeType.scalar)

    @classmethod
    def str(cls, value):
        return cls(value, DataType.str, ObjectType.value, ShapeType.scalar)

    @classmethod
    def id(cls, value):
        return cls(value, DataType.undefined, ObjectType.identifier, ShapeType.scalar)

    @classmethod
    def array(cls, value, dt:DataType|None=None):
        return cls(value, dt if dt is not None else DataType.undefined, None, ShapeType.vector)

    @classmethod
    def function(cls, value, dt:DataType|None=None):
        return cls(value, dt if dt is not None else DataType.undefined, ObjectType.function)

    @classmethod
    def best(cls, value):
        if isinstance(value, str) and value[0] == '"' and value[-1] == '"':
            return cls(value, DataType.str)
        elif isinstance(value, str):
            # Any string value which is not wrapped in double quotes must(?) be an identifier
            return cls(value, DataType.undefined, ObjectType.identifier, ShapeType.unknown)
        if isinstance(value, int) or (isinstance(value, float) and value.is_integer()):
            return cls(value, DataType.int)
        return cls(value, DataType.float)

    @property
    def is_id(self):
        # FIXME 2023-10-16 Should instrument parameters not also be identifiers?
        return self.object_type == ObjectType.identifier or self.object_type == ObjectType.parameter

    @property
    def is_constant(self):
        return not self.is_id

    @property
    def is_parameter(self):
        return self.object_type.is_parameter

    @property
    def is_str(self):
        return self.object_type == ObjectType.value and self.data_type.is_str

    @property
    def is_float(self):
        return self.data_type == DataType.float

    @property
    def is_int(self):
        return self.data_type == DataType.int

    @property
    def is_op(self):
        return False

    @property
    def is_zero(self):
        if self.is_id:
            return False
        if self.is_str:
            # This is not great, but captures a case where, e.g., -1 is interpreted as an empty string minus 1
            return len(self.value.strip('"')) == 0
        return self.value == 0

    def is_value(self, v):
        return not self.is_id and (v.is_value(self.value) if hasattr(v, 'is_value') else self.value == v)

    @property
    def is_scalar(self):
        return self.shape_type.is_scalar

    @property
    def is_vector(self):
        return self.shape_type.is_vector

    # def __len__(self):
    #     return len(self.value) if self.is_vector else 1

    @property
    def vector_len(self):
        return len(self.value) if self.is_vector else 1

    def as_type(self, dt: DataType):
        return Value(self.value, dt, self.object_type, self.shape_type)

    def __add__(self, other):
        other = other if isinstance(other, (Value, Op)) else Value.best(other)
        if self.is_zero:
            return other
        if other.is_zero:
            return self
        if other.is_op and isinstance(other, UnaryOp) and other.op == '-' and len(other.value) == 1:
            return self - other.value[0]
        if self.is_id and (isinstance(other, Value) and not isinstance(other.value, str) and other < 0):
            return self - (-other.value)
        if other.is_op or self.is_id or other.is_id or not self.is_constant or not other.is_constant:
            return BinaryOp(self.data_type, OpStyle.C, '+', [self], [other])
        pdt = self.data_type + other.data_type
        return BinaryOp(self.data_type, OpStyle.C, '+', [self], [other]) if pdt.is_str else Value(self.value + other.value, pdt)

    def __sub__(self, other):
        other = other if isinstance(other, (Value, Op)) else Value.best(other)
        if self.is_zero:
            return -other
        if other.is_zero:
            return self
        if other.is_op and isinstance(other, UnaryOp) and other.op == '-' and len(other.value) == 1:
            return self + other.value[0]
        if self.is_id and (isinstance(other, Value) and not isinstance(other.value, str) and other < 0):
            return self + (-other.value)
        if other.is_op or self.is_id or other.is_id or not self.is_constant or not other.is_constant:
            return BinaryOp(self.data_type, OpStyle.C, '-', [self], [other])
        pdt = self.data_type - other.data_type
        return BinaryOp(self.data_type, OpStyle.C, '-', [self], [other]) if pdt.is_str else Value(self.value - other.value, pdt)

    def __mul__(self, other):
        other = other if isinstance(other, (Value, Op)) else Value.best(other)
        pdt = self.data_type * other.data_type
        if self.is_zero or other.is_zero:
            return Value(0, DataType.int if pdt.is_str else pdt)
        if self.is_value(1):
            return other.as_type(pdt)
        if self.is_value(-1):
            return (-other).as_type(pdt)
        if other.is_value(1):
            return self.as_type(pdt)
        if other.is_value(-1):
            return (-self).as_type(pdt)
        if other.is_op or self.is_id or other.is_id:
            return BinaryOp(self.data_type, OpStyle.C, '*', [self], [other])
        return BinaryOp(self.data_type, OpStyle.C, '*', [self], [other]) if pdt.is_str else Value(self.value * other.value, pdt)

    def __mod__(self, other):
        other = other if isinstance(other, (Value, Op)) else Value.best(other)
        pdt = self.data_type
        if other.is_op or self.is_id or other.is_id or pdt.is_str:
            return BinaryOp(self.data_type, OpStyle.C, '%', [self], [other])
        # This is neither consistent with the Python or C definition
        #   Python -- the result takes the sign of the divisor
        #   C      -- the sign is always positive for positive numerator
        #             but compiler-dependent for negative numerator
        # return Value(self.value - (self.value // other.value) * other.value, pdt)
        return Value(self.value % other.value, pdt)

    def __truediv__(self, other):
        other = other if isinstance(other, (Value, Op)) else Value.best(other)
        pdt = self.data_type / other.data_type
        if self.is_zero:
            return Value(0, DataType.int if pdt.is_str else pdt)
        if other.is_value(1):
            return self.as_type(pdt)
        if other.is_value(-1):
            return (-self).as_type(pdt)
        if other.is_zero:
            raise RuntimeError('Division by zero!')
        if other.is_op or self.is_id or other.is_id:
            return BinaryOp(self.data_type, OpStyle.C, '/', [self], [other])
        return BinaryOp(self.data_type, OpStyle.C, '/', [self], [other]) if pdt.is_str else Value(self.value / other.value, pdt)

    def __floordiv__(self, other):
        other = other if isinstance(other, (Value, Op)) else Value.best(other)
        pdt = self.data_type // other.data_type
        if self.is_zero:
            return Value(0, DataType.int)
        if other.is_value(1):
            return Value.int(round(self.value))
        if other.is_value(-1):
            return -Value.int(round(self.value))
        if other.is_zero:
            raise RuntimeError('Division by zero!')
        if other.is_op or self.is_id or other.is_id:
            return BinaryOp(self.data_type, OpStyle.C, '//', [self], [other])
        return BinaryOp(self.data_type, OpStyle.C, '//', [self], [other]) if pdt.is_str else Value.int(self.value // other.value)

    def __neg__(self):
        return UnaryOp(self.data_type, OpStyle.C, '-', [self]) if self.is_id or self.data_type.is_str else Value(-self.value, self.data_type)

    def __pos__(self):
        return Value(self.value, self.data_type)

    def __abs__(self):
        return UnaryOp(self.data_type, OpStyle.C, 'abs', [self]) if self.is_id or self.data_type.is_str else Value(abs(self.value), self.data_type)

    def __round__(self, n=None):
        return UnaryOp(self.data_type, OpStyle.C, 'round', [self]) if self.is_id or self.data_type.is_str \
            else Value(round(self.value, n), self.data_type)

    def __eq__(self, other):
        other = other if isinstance(other, (Value, Op)) else Value.best(other)
        if other.is_op:
            return False
        return self.value == other.value

    def __lt__(self, other):
        other = other if isinstance(other, (Value, Op)) else Value.best(other)
        if self.is_id or other.is_op or other.is_id:
            return BinaryOp(self.data_type, OpStyle.C, '__lt__', [self], [other])
        return self.value < other.value

    def __gt__(self, other):
        other = other if isinstance(other, (Value, Op)) else Value.best(other)
        if self.is_id or other.is_op or other.is_id:
            return BinaryOp(self.data_type, OpStyle.C, '__gt__', [self], [other])
        return self.value > other.value

    def __le__(self, other):
        other = other if isinstance(other, (Value, Op)) else Value.best(other)
        if self.is_id or other.is_op or other.is_id:
            return BinaryOp(self.data_type, OpStyle.C, '__le__', [self], [other])
        return self.value <= other.value

    def __ge__(self, other):
        other = other if isinstance(other, (Value, Op)) else Value.best(other)
        if self.is_id or other.is_op or other.is_id:
            return BinaryOp(self.data_type, OpStyle.C, '__ge__', [self], [other])
        return self.value >= other.value

    def __pow__(self, power):
        if not isinstance(power, (Value, Op)):
            power = Value.best(power)
        if self.is_zero or self.is_value(1):
            return self
        if power.is_zero:
            return Value(1, self.data_type)
        if self.is_constant and power.is_constant:
            return Value(_value=self.value ** power.value, _data=self.data_type)
        return BinaryOp(self.data_type, OpStyle.C, '__pow__', [self], [power])

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
        raise RuntimeError(f"No known conversion from non-enumerated data type {self.data_type} + {self.shape_type}")

    def simplify(self):
        return self

    def evaluate(self, known: dict):
        if not self.is_constant and self.value in known:
            result = known[self.value]
            if isinstance(result, Expr) and result.is_singular:
                return result.expr[0]
            return result
        return self

    def depends_on(self, name: str):
        return not self.is_constant and self.value == name

    def copy(self):
        return Value(self.value, self.data_type, self.object_type, self.shape_type)

    def __contains__(self, value):
        if self.is_id and isinstance(value, (str, Value)):
            return self.value == value
        if self.is_vector:
            return value in self.value
        if self.is_str and isinstance(value, str) and (value[0] != '"' or value[-1] != '"'):
            # string Values are always wrapped in double quotes
            return self.value.strip('"') == value.strip('"')
        return self.value == value

    def verify_parameters(self, instrument_parameter_names: list[str]):
        if self.is_id and self.value in instrument_parameter_names:
            self._object = ObjectType.parameter


ExprNodeSingular = Union[Value, UnaryOp, BinaryOp, TrinaryOp]
ExprNodeList = list[ExprNodeSingular]
ExprNode = Union[ExprNodeSingular, ExprNodeList]
OpNode = list[Union[Value, UnaryOp, BinaryOp, TrinaryOp, Op]]


# @dataclass
class Expr(Struct):
    expr: ExprNode

    @classmethod
    def from_dict(cls, args: dict):
        expr = args['expr']
        if not hasattr(expr, '__len__'):
            expr = [expr]
        return cls([value_or_op_from_dict(x) for x in expr])

    def __post_init__(self):
        if not isinstance(self.expr, list):
            self.expr = [self.expr]
        if any(not isinstance(node, ExprNodeSingular) for node in self.expr):
            types = list(dict.fromkeys(type(node) for node in self.expr).keys())
            raise ValueError(f"An Expr can not be a list of {types}")

    def __str__(self):
        return ','.join(str(x) for x in self.expr)

    def __format__(self, format_spec):
        """Abuse string formatting to append the _instrument_var.parameters prefix to parameter names"""
        return ','.join(format(x, format_spec) for x in self.expr)

    def __repr__(self):
        return ','.join(repr(x) for x in self.expr)

    def __hash__(self):
        return hash(str(self))

    def __contains__(self, value):
        return any(value in x for x in self.expr)

    @staticmethod
    def parse(s: str):
        from antlr4 import InputStream
        from ..grammar import McInstr_parse
        from ..instr import InstrVisitor
        visitor = InstrVisitor(None, None)
        return visitor.getExpr(McInstr_parse(InputStream(s), 'expr'))

    @classmethod
    def float(cls, value):
        if isinstance(value, cls):
            # Make sure the held expression *thinks* it's a float:
            for expr in value.expr:
                if expr.data_type != DataType.float:
                    expr.data_type = DataType.float
            return value
        return cls(Value.float(value))

    @classmethod
    def int(cls, value):
        if isinstance(value, cls):
            # Make sure the held expression *thinks* it's a float:
            for expr in value.expr:
                if expr.data_type != DataType.int:
                    expr.data_type = DataType.int
            return value
        return cls(Value.int(value))

    @classmethod
    def str(cls, value):
        if isinstance(value, cls):
            # Make sure the held expression *thinks* it's a float:
            for expr in value.expr:
                if expr.data_type != DataType.str:
                    expr.data_type = DataType.str
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
    def is_singular(self):
        return len(self.expr) == 1

    @property
    def is_op(self):
        return len(self.expr) == 1 and self.expr[0].is_op

    @property
    def is_zero(self):
        return len(self.expr) == 1 and self.expr[0].is_zero

    @property
    def is_id(self):
        return len(self.expr) == 1 and self.expr[0].is_id

    @property
    def is_parameter(self):
        return len(self.expr) == 1 and self.expr[0].is_parameter

    @property
    def is_str(self):
        return len(self.expr) == 1 and self.expr[0].is_str

    @property
    def is_scalar(self):
        return len(self.expr) == 1 and self.expr[0].is_scalar

    def is_value(self, value):
        return len(self.expr) == 1 and self.expr[0].is_value(value)

    @property
    def is_vector(self):
        return len(self.expr) == 1 and self.expr[0].is_vector
    #
    # def __len__(self):
    #     return len(self.expr)
    @property
    def vector_len(self):
        if len(self.expr) != 1:
            raise RuntimeError('No vector_len for array Expr objects')
        return self.expr[0].vector_len

    @property
    def is_constant(self):
        return len(self.expr) == 1 and isinstance(self.expr[0], Value) and not self.expr[0].is_id

    @property
    def has_value(self):
        return self.is_constant and self.expr[0].has_value

    @property
    def vector_known(self):
        return self.is_constant and self.expr[0].vector_known

    @property
    def value(self):
        if not self.is_constant:
            raise NotImplementedError("No conversion from expressions to constants ... yet")
        return self.expr[0].value

    @property
    def first(self):
        return self.expr[0]

    @property
    def last(self):
        return self.expr[-1]

    def compatible(self, other, id_ok=False):
        other_expr = other.expr[0] if (isinstance(other, Expr) and len(other.expr) == 1) else other
        return len(self.expr) == 1 and self.expr[0].compatible(other_expr, id_ok)

    def _prep_numeric_operation(self, msg: str, other):
        if len(self.expr) != 1:
            raise RuntimeError(f'Can not {msg} array Expr')
        return other.expr[0] if (isinstance(other, Expr) and len(other.expr) == 1) else other

    def _prep_rev_numeric_operation(self, msg: str, other):
        r = self._prep_numeric_operation(msg, other)
        if not isinstance(r, (Expr, TrinaryOp, BinaryOp, UnaryOp, Value)):
            r = Value.best(r)
        return r

    def __add__(self, other):
        return Expr(self.expr[0] + self._prep_numeric_operation('add to', other))

    def __sub__(self, other):
        return Expr(self.expr[0] - self._prep_numeric_operation('subtract', other))

    def __mul__(self, other):
        return Expr(self.expr[0] * self._prep_numeric_operation('multiply', other))

    def __mod__(self, other):
        return Expr(self.expr[0] % self._prep_numeric_operation('mod', other))

    def __truediv__(self, other):
        return Expr(self.expr[0] / self._prep_numeric_operation('divide', other))

    def __floordiv__(self, other):
        return Expr(self.expr[0] // self._prep_numeric_operation('divide', other))

    def __pow__(self, other):
        return Expr(self.expr[0] ** self._prep_numeric_operation('raise', other))

    def __radd__(self, other):
        return Expr(self._prep_rev_numeric_operation('add to', other) + self.expr[0])

    def __rsub__(self, other):
        return Expr(self._prep_rev_numeric_operation('subtract', other) - self.expr[0])

    def __rmul__(self, other):
        return Expr(self._prep_rev_numeric_operation('multiply', other) * self.expr[0])

    def __rtruediv__(self, other):
        return Expr(self._prep_rev_numeric_operation('divide', other) / self.expr[0])

    def __rfloordiv__(self, other):
        return Expr(self._prep_rev_numeric_operation('divide', other) // self.expr[0])

    def __rpow__(self, other):
        return Expr(self._prep_rev_numeric_operation('raise', other) ** self.expr[0])

    def __neg__(self):
        return Expr([-x for x in self.expr])

    def __pos__(self):
        return self

    def __abs__(self):
        return Expr([abs(x) for x in self.expr])

    def __round__(self, n=None):
        return Expr([round(x, n) for x in self.expr])

    def __eq__(self, other):
        if isinstance(other, Expr):
            if len(other.expr) != len(self.expr):
                return False
            for o_expr, s_expr in zip(other.expr, self.expr):
                if o_expr != s_expr:
                    return False
            return True
        return len(self.expr) == 1 and self.expr[0] == other

    def __lt__(self, other):
        if isinstance(other, Expr):
            if len(other.expr) != len(self.expr):
                raise RuntimeError('Can not compare unequal-sized-array Expr objects')
            for o_expr, s_expr in zip(other.expr, self.expr):
                if o_expr <= s_expr:
                    return False
            return True
        return len(self.expr) == 1 and self.expr[0] < other

    def __gt__(self, other):
        if isinstance(other, Expr):
            if len(other.expr) != len(self.expr):
                raise RuntimeError('Can not compare unequal-sized-array Expr objects')
            for o_expr, s_expr in zip(other.expr, self.expr):
                if o_expr >= s_expr:
                    return False
            return True
        return len(self.expr) == 1 and self.expr[0] > other

    def __le__(self, other):
        if isinstance(other, Expr):
            if len(other.expr) != len(self.expr):
                raise RuntimeError('Can not compare unequal-sized-array Expr objects')
            for o_expr, s_expr in zip(other.expr, self.expr):
                if o_expr < s_expr:
                    return False
            return True
        return len(self.expr) == 1 and self.expr[0] <= other

    def __ge__(self, other):
        if isinstance(other, Expr):
            if len(other.expr) != len(self.expr):
                raise RuntimeError('Can not compare unequal-sized-array Expr objects')
            for o_expr, s_expr in zip(other.expr, self.expr):
                if o_expr > s_expr:
                    return False
            return True
        return len(self.expr) == 1 and self.expr[0] >= other

    def __int__(self):
        if not len(self.expr) == 1:
            raise RuntimeError('No conversion to int for array Expr objects')
        return int(self.expr[0])

    @property
    def mccode_c_type(self):
        if len(self.expr) != 1:
            raise RuntimeError('No McCode C type for array Expr objects')
        if not isinstance(self.expr[0], Value):
            logger.critical(f'Why is {self.expr[0]} not a Value?')
        return self.expr[0].mccode_c_type

    @property
    def mccode_c_type_name(self):
        if len(self.expr) != 1:
            raise RuntimeError('No McCode C type name for array Expr objects')
        return self.expr[0].mccode_c_type_name

    @property
    def data_type(self):
        if len(self.expr) != 1:
            raise RuntimeError('No data type for array Expr objects')
        return self.expr[0].data_type

    @data_type.setter
    def data_type(self, dt):
        if len(self.expr) != 1:
            raise RuntimeError('No data type for array Expr objects')
        self.expr[0].data_type = dt

    @property
    def shape_type(self):
        if len(self.expr) != 1:
            raise RuntimeError('No data type for array Expr objects')
        return self.expr[0].shape_type

    @shape_type.setter
    def shape_type(self, st):
        if len(self.expr) != 1:
            raise RuntimeError('No data type for array Expr objects')
        if not isinstance(self.expr[0], Value):
            raise RuntimeError('No data type for non-scalar-Value Expr objects')
        self.expr[0].shape_type = st

    def simplify(self):
        """Perform a very basic analysis to reduce the expression complexity"""
        def simplify_to_single_or_list(node):
            s = node.simplify()
            return s[0] if hasattr(s, '__len__') and len(s) == 1 else s
        return Expr([simplify_to_single_or_list(x) for x in self.expr])

    def evaluate(self, known: dict):
        def evaluate_to_single_or_list(node):
            s = node.evaluate(known)
            return s[0] if hasattr(s, '__len__') and len(s) == 1 else s
        return Expr([evaluate_to_single_or_list(x) for x in self.expr]).simplify()

    def depends_on(self, name: str):
        return any(x.depends_on(name) for x in self.expr)

    def copy(self):
        return Expr([x.copy() for x in self.expr])

    def verify_parameters(self, instrument_parameter_names: list[str]):
        for x in self.expr:
            x.verify_parameters(instrument_parameter_names)


def unary_expr(func, name, v):
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



def value_or_op_from_dict(args: dict):
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
        # In C the data types for `if_true` and `if_false` in
        #   `(logical test) ? if_true : if_false;`
        # _must_ be the same. Python is more flexible, but we need to at least have a promotable common type
        # for compatibility with C. (the type of the logical test can differ)
        a = data_type_set_list(-1)
        b = data_type_set_list(-2) if len(props) > 1 else a
        if len(a) != 1 or len(b) != 1:
            raise RuntimeError('Multiple data types in one value not supported')
        # datatype + datatype promotion preserves A+A=A
        obj.data_type = a[0] + b[0]

    # ensure that data_type is a DataType and style is an OpStyle?
    for prop, typ in (('data_type', DataType), ('style', OpStyle)):
        if not isinstance(p:=getattr(obj, prop), typ):
            setattr(obj, prop, typ(p))

from __future__ import annotations

from enum import IntEnum


class ObjectType(IntEnum):
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


class ShapeType(IntEnum):
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


class DataType(IntEnum):
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


class OpStyle(IntEnum):
    C = 1
    PYTHON = 2

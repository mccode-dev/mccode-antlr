from __future__ import annotations

from loguru import logger
from msgspec import Struct

from .nodes import Value, UnaryOp, BinaryOp, TrinaryOp, ExprNodeSingular, ExprNode
from .types import DataType
from .utils import value_or_op_from_dict


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
        from ...grammar import McInstr_parse
        from ...instr import InstrVisitor
        visitor = InstrVisitor(None, None)
        return visitor.getExpr(McInstr_parse(InputStream(s), 'expr'))

    @classmethod
    def float(cls, value):
        if isinstance(value, cls):
            for expr in value.expr:
                if expr.data_type != DataType.float:
                    expr.data_type = DataType.float
            return value
        return cls(Value.float(value))

    @classmethod
    def int(cls, value):
        if isinstance(value, cls):
            for expr in value.expr:
                if expr.data_type != DataType.int:
                    expr.data_type = DataType.int
            return value
        return cls(Value.int(value))

    @classmethod
    def str(cls, value):
        if isinstance(value, cls):
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
    def parameter(cls, value: str, dt=None) -> 'Expr':
        """Create an Expr for a known instrument parameter (ObjectType.parameter).

        Unlike Expr.id(), the parameter flag is set immediately so that the
        ``_instrument_var._parameters.`` prefix is used in C output without waiting
        for verify_parameters() to be called during instrument finalisation.

        Args:
            value: parameter name string, or an existing Expr (returned unchanged)
            dt: optional DataType hint (default: DataType.undefined)

        Returns:
            Expr wrapping a Value with ObjectType.parameter
        """
        if isinstance(value, cls):
            return value
        return cls(Value.parameter(value, dt))

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

    def _prep_cmp(self, other):
        """Normalise `other` to a single Value/Op node for comparison expression building."""
        if len(self.expr) != 1:
            raise RuntimeError('Can not build comparison expression for array Expr')
        if isinstance(other, Expr):
            if len(other.expr) != 1:
                raise RuntimeError('Can not build comparison expression against array Expr')
            return other.expr[0]
        if not isinstance(other, (Value, BinaryOp, UnaryOp, TrinaryOp)):
            return Value.best(other)
        return other

    def eq(self, other) -> 'Expr':
        """Return Expr for `self == other` (always an expression tree, never a bool)."""
        return Expr(self.expr[0].eq(self._prep_cmp(other)))

    def ne(self, other) -> 'Expr':
        """Return Expr for `self != other`."""
        return Expr(self.expr[0].ne(self._prep_cmp(other)))

    def lt(self, other) -> 'Expr':
        """Return Expr for `self < other`."""
        return Expr(self.expr[0] < self._prep_cmp(other))

    def gt(self, other) -> 'Expr':
        """Return Expr for `self > other`."""
        return Expr(self.expr[0] > self._prep_cmp(other))

    def le(self, other) -> 'Expr':
        """Return Expr for `self <= other`."""
        return Expr(self.expr[0] <= self._prep_cmp(other))

    def ge(self, other) -> 'Expr':
        """Return Expr for `self >= other`."""
        return Expr(self.expr[0] >= self._prep_cmp(other))

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

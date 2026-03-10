"""Expr — the public McCode expression wrapper, backed by SymPy."""
from __future__ import annotations

import sympy
import msgspec
from loguru import logger

from .sympy_classes import McCodeParameter, UNSET_SYMPY, SYMPY_NAMESPACE
from .types import DataType, ObjectType, ShapeType


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _infer_data_type(sym: sympy.Basic, hint: DataType = DataType.undefined) -> DataType:
    if hint != DataType.undefined:
        return hint
    if sym is UNSET_SYMPY:
        return DataType.undefined
    if isinstance(sym, sympy.Integer):
        return DataType.int
    if sym.is_integer is True:
        return DataType.int
    if sym.is_number:
        return DataType.float
    return DataType.undefined


def _promote(a: DataType, b: DataType, op: str) -> DataType:
    if op in ('/', 'truediv'):
        return DataType.float
    if op in ('//', 'floordiv'):
        return DataType.int
    return a + b


def _to_sympy(value) -> sympy.Basic:
    if isinstance(value, Expr):
        if len(value._exprs) != 1:
            raise RuntimeError("Cannot convert multi-element Expr to single SymPy expression")
        return value._exprs[0]
    if isinstance(value, sympy.Basic):
        return value
    if isinstance(value, int):
        return sympy.Integer(value)
    if isinstance(value, float):
        return sympy.Float(str(value))
    if isinstance(value, str):
        return sympy.Symbol(value)
    return sympy.sympify(value)


# ---------------------------------------------------------------------------
# Public Expr class
# ---------------------------------------------------------------------------

class Expr(msgspec.Struct, dict=True, eq=False):
    """Symbolic expression with McCode-specific metadata."""

    exprs: list[str]
    data_type: DataType = DataType.undefined
    shape_type: ShapeType = ShapeType.scalar
    object_type: ObjectType = ObjectType.value

    def __post_init__(self):
        # NOTE: __post_init__ is called by msgspec after setting struct fields.
        # The public struct constructor expects `exprs: list[str]` (srepr strings).
        # Internally, factory classmethods (float, integer, string, id, …) pass
        # sympy.Basic objects or lists thereof for convenience — this block
        # normalises those to srepr strings and pre-populates the SymPy cache.
        if isinstance(self.exprs, sympy.Basic):  # type: ignore[arg-type]
            sym = self.exprs
            self.__dict__['_cache'] = [sym]
            self.exprs = [sympy.srepr(sym)]  # type: ignore[assignment]
        elif isinstance(self.exprs, list):
            if self.exprs and isinstance(self.exprs[0], sympy.Basic):
                syms = list(self.exprs)
                self.__dict__['_cache'] = syms
                self.exprs = [sympy.srepr(e) for e in syms]
            # else: already list[str], nothing to do
        else:
            sym = sympy.sympify(self.exprs)
            self.__dict__['_cache'] = [sym]
            self.exprs = [sympy.srepr(sym)]  # type: ignore[assignment]

        # Auto-promote scalar → vector when multiple elements
        if len(self.exprs) > 1 and self.shape_type == ShapeType.scalar:
            self.shape_type = ShapeType.vector

    @property
    def _exprs(self) -> list[sympy.Basic]:
        if '_cache' not in self.__dict__:
            self.__dict__['_cache'] = [eval(s, SYMPY_NAMESPACE) for s in self.exprs]  # noqa: S307
        return self.__dict__['_cache']

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            'exprs': list(self.exprs),
            'data_type': int(self.data_type),
            'shape_type': int(self.shape_type),
            'object_type': int(self.object_type),
        }

    @classmethod
    def from_dict(cls, args: dict) -> 'Expr':
        if 'exprs' in args:
            exprs = [eval(s, SYMPY_NAMESPACE) for s in args['exprs']]  # noqa: S307
            dt = DataType(args.get('data_type', DataType.undefined.value))
            st = ShapeType(args.get('shape_type', ShapeType.scalar.value))
            ot = ObjectType(args.get('object_type', ObjectType.value.value))
            return cls(exprs, dt, st, ot)
        # Legacy ExprNode format — handled by io migration layer
        from .utils import _from_legacy_expr_dict
        return _from_legacy_expr_dict(args)

    # ------------------------------------------------------------------
    # Factory classmethods
    # ------------------------------------------------------------------

    @staticmethod
    def parse(s: str) -> 'Expr':
        from antlr4 import InputStream
        from ...grammar import McInstr_parse
        from ...instr import InstrVisitor
        visitor = InstrVisitor(None, None)
        return visitor.getExpr(McInstr_parse(InputStream(s), 'expr'))

    @classmethod
    def float(cls, value) -> 'Expr':
        if isinstance(value, cls):
            return cls(value._exprs, DataType.float, value.shape_type, value.object_type)
        if isinstance(value, str):
            # Preserve decimal string representation to avoid binary float imprecision
            return cls(sympy.Float(value), DataType.float) if value.lower() not in ('none', '') else cls(UNSET_SYMPY, DataType.float)
        try:
            v = float(value) if value is not None else None
        except (ValueError, TypeError):
            v = value
        if v is None:
            return cls(UNSET_SYMPY, DataType.float)
        # Use string conversion to preserve decimal precision (e.g. 0.05 → '0.05', not 0.050000000000000003)
        return cls(sympy.Float(str(v)), DataType.float)

    @classmethod
    def integer(cls, value) -> 'Expr':
        if isinstance(value, cls):
            return cls(value._exprs, DataType.int, value.shape_type, value.object_type)
        try:
            v = int(value) if value is not None else None
        except (ValueError, TypeError):
            v = value
        if v is None:
            return cls(UNSET_SYMPY, DataType.int)
        return cls(sympy.Integer(v), DataType.int)

    @classmethod
    def string(cls, value) -> 'Expr':
        if isinstance(value, cls):
            return cls(value._exprs, DataType.str, value.shape_type, value.object_type)
        if value is None:
            return cls(UNSET_SYMPY, DataType.str)
        sym = sympy.Symbol(str(value), commutative=False)
        return cls(sym, DataType.str, ShapeType.scalar, ObjectType.value)

    @classmethod
    def id(cls, value, data_type: DataType = DataType.undefined,
           shape_type: ShapeType = ShapeType.scalar) -> 'Expr':
        if isinstance(value, cls):
            return value
        sym = sympy.Symbol(str(value))
        return cls(sym, data_type, shape_type, ObjectType.identifier)

    @classmethod
    def parameter(cls, value: str, dt: DataType | None = None) -> 'Expr':
        if isinstance(value, cls):
            return value
        sym = McCodeParameter(str(value))
        return cls(sym, dt if dt is not None else DataType.undefined,
                   ShapeType.scalar, ObjectType.parameter)

    @classmethod
    def array(cls, value) -> 'Expr':
        if isinstance(value, (list, tuple)):
            exprs = []
            for v in value:
                if isinstance(v, float):
                    exprs.append(sympy.Float(v))
                elif isinstance(v, int):
                    exprs.append(sympy.Integer(v))
                else:
                    exprs.append(sympy.sympify(v))
            return cls(exprs, DataType.float, ShapeType.vector, ObjectType.value)
        sym = sympy.Symbol(str(value))
        return cls(sym, DataType.undefined, ShapeType.vector, ObjectType.identifier)

    @classmethod
    def function(cls, value) -> 'Expr':
        sym = sympy.Symbol(str(value))
        return cls(sym, DataType.undefined, ShapeType.scalar, ObjectType.function)

    @classmethod
    def best(cls, value) -> 'Expr':
        if isinstance(value, str):
            if value and value[0] == '"' and value[-1] == '"':
                sym = sympy.Symbol(value, commutative=False)
                return cls(sym, DataType.str, ShapeType.scalar, ObjectType.value)
            sym = sympy.Symbol(value)
            return cls(sym, DataType.undefined, ShapeType.unknown, ObjectType.identifier)
        if isinstance(value, bool):
            return cls(sympy.Integer(1 if value else 0), DataType.int)
        if isinstance(value, int) or (isinstance(value, float) and value == int(value)):
            return cls(sympy.Integer(int(value)), DataType.int)
        return cls(sympy.Float(str(value)), DataType.float)

    @classmethod
    def _null(cls) -> 'Expr':
        """Return a null/unset expression (equivalent to old Value(None))."""
        return cls(UNSET_SYMPY)

    # ------------------------------------------------------------------
    # Representation
    # ------------------------------------------------------------------

    def __str__(self):
        from .printer import _C_PRINTER
        from .sympy_classes import UNSET_SYMPY
        # Preserve old Value(None).__str__() = 'None' for null/unset expressions
        if len(self._exprs) == 1 and self._exprs[0] is UNSET_SYMPY:
            return 'None'
        return ','.join(_C_PRINTER.doprint(e) for e in self._exprs)

    def __format__(self, format_spec):
        from .printer import _C_PRINTER, _P_PRINTER
        from .sympy_classes import UNSET_SYMPY
        # Preserve 'None' for null/unset when used in format strings
        if len(self._exprs) == 1 and self._exprs[0] is UNSET_SYMPY and format_spec not in ('p',):
            return 'None'
        if format_spec == 'p':
            return ','.join(_P_PRINTER.doprint(e) for e in self._exprs)
        if format_spec.startswith('prefix:'):
            from .printer import McCodeCPrinter
            custom_prefix = format_spec[len('prefix:'):]
            p = McCodeCPrinter(parameter_prefix=True, prefix=custom_prefix)
            return ','.join(p.doprint(e) for e in self._exprs)
        return ','.join(_C_PRINTER.doprint(e) for e in self._exprs)

    def to_python(self) -> str:
        """Return a Python-syntax string representation of this expression."""
        from .printer import _PY_PRINTER
        from .sympy_classes import UNSET_SYMPY
        if len(self._exprs) == 1 and self._exprs[0] is UNSET_SYMPY:
            return 'None'
        return ','.join(_PY_PRINTER.doprint(e) for e in self._exprs)

    def __repr__(self):
        parts = [f'{self.shape_type} {self.data_type} {sympy.srepr(e)}' for e in self._exprs]
        return ','.join(parts)

    def __hash__(self):
        return hash(str(self))

    def __contains__(self, value):
        name = value if isinstance(value, str) else str(value)
        for e in self._exprs:
            if isinstance(e, sympy.Symbol) and e.name == name:
                return True
            if hasattr(e, 'free_symbols') and any(s.name == name for s in e.free_symbols):
                return True
        return False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_singular(self) -> bool:
        return len(self._exprs) == 1

    @property
    def is_op(self) -> bool:
        return self.is_singular and not self._exprs[0].is_Atom

    @property
    def is_zero(self) -> bool:
        return self.is_singular and (self._exprs[0].is_zero is True)

    @property
    def is_id(self) -> bool:
        return self.is_singular and self.object_type in (ObjectType.identifier, ObjectType.parameter)

    @property
    def is_parameter(self) -> bool:
        if not self.is_singular:
            return False
        return (self.object_type == ObjectType.parameter
                or isinstance(self._exprs[0], McCodeParameter))

    @property
    def is_float(self) -> bool:
        return self.data_type == DataType.float

    @property
    def is_int(self) -> bool:
        return self.data_type == DataType.int

    @property
    def is_str(self) -> bool:
        return self.is_singular and self.data_type == DataType.str

    @property
    def is_scalar(self) -> bool:
        return self.is_singular and self.shape_type in (ShapeType.scalar, ShapeType.unknown)

    def is_value(self, value) -> bool:
        if not self.is_singular or self.is_id:
            return False
        try:
            return bool(sympy.Eq(self._exprs[0], sympy.sympify(value)))
        except Exception:
            return False

    @property
    def is_vector(self) -> bool:
        return self.shape_type == ShapeType.vector

    @property
    def vector_len(self) -> int:
        if len(self._exprs) != 1:
            return len(self._exprs)
        return 1

    @property
    def is_constant(self) -> bool:
        if not self.is_singular or self.is_id:
            return False
        e = self._exprs[0]
        if self.data_type == DataType.str:
            return True
        return e.is_number or e is UNSET_SYMPY

    @property
    def has_value(self) -> bool:
        return self.is_constant and self._exprs[0] is not UNSET_SYMPY

    @property
    def vector_known(self) -> bool:
        return self.is_vector and len(self._exprs) > 1

    @property
    def value(self):
        if self.is_vector and not self.is_singular:
            # Return list of Python values for each element
            result = []
            for e in self._exprs:
                if e.is_number:
                    result.append(int(e) if (e.is_integer is True) else float(e))
                else:
                    from .printer import _C_PRINTER
                    result.append(_C_PRINTER.doprint(e))
            return result
        if not self.is_constant:
            raise NotImplementedError("No conversion from expressions to constants ... yet")
        e = self._exprs[0]
        if e is UNSET_SYMPY:
            return None
        if self.data_type == DataType.str:
            return e.name
        if self.data_type == DataType.int or (e.is_integer is True):
            return int(e)
        return float(e)

    @property
    def first(self):
        return self._exprs[0]

    @property
    def last(self):
        return self._exprs[-1]

    @property
    def mccode_c_type(self) -> str:
        if self.data_type == DataType.undefined:
            logger.critical(f'Why is data_type undefined for {self!r}?')
        return self.data_type.mccode_c_type + self.shape_type.mccode_c_type

    @property
    def mccode_c_type_name(self) -> str:
        dt, st = self.data_type, self.shape_type
        if dt == DataType.float and st == ShapeType.scalar:
            return "instr_type_double"
        if dt == DataType.int and st == ShapeType.scalar:
            return "instr_type_int"
        if dt == DataType.str and st == ShapeType.scalar:
            return "instr_type_string"
        if dt in (DataType.float, DataType.int) and st == ShapeType.vector:
            return "instr_type_vector"
        raise RuntimeError(f"No known conversion for {dt} + {st}")

    # ------------------------------------------------------------------
    # Compatibility check
    # ------------------------------------------------------------------

    def compatible(self, other, id_ok: bool = False) -> bool:
        if isinstance(other, Expr):
            if other.is_id or other.is_op:
                return id_ok
            # Vector parameters are compatible with vector values
            if self.shape_type == ShapeType.vector and other.shape_type == ShapeType.vector:
                return self.data_type.compatible(other.data_type)
            if self.shape_type == ShapeType.vector and not other.is_singular:
                return self.data_type.compatible(other.data_type)
            if not self.is_singular or not other.is_singular:
                return False
            return (self.data_type.compatible(other.data_type)
                    and self.shape_type.compatible(other.shape_type))
        try:
            o = Expr.best(other)
            return (self.data_type.compatible(o.data_type)
                    and self.shape_type.compatible(o.shape_type))
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Expression-tree comparison builders (return Expr, not bool)
    # ------------------------------------------------------------------

    def _prep_rhs(self, other):
        if len(self._exprs) != 1:
            raise RuntimeError('Cannot build comparison expression for array Expr')
        return _to_sympy(other)

    def eq(self, other) -> 'Expr':
        return Expr(sympy.Eq(self._exprs[0], self._prep_rhs(other)),
                    DataType.int, ShapeType.scalar, ObjectType.value)

    def ne(self, other) -> 'Expr':
        return Expr(sympy.Ne(self._exprs[0], self._prep_rhs(other)),
                    DataType.int, ShapeType.scalar, ObjectType.value)

    def lt(self, other) -> 'Expr':
        return Expr(sympy.Lt(self._exprs[0], self._prep_rhs(other)),
                    DataType.int, ShapeType.scalar, ObjectType.value)

    def gt(self, other) -> 'Expr':
        return Expr(sympy.Gt(self._exprs[0], self._prep_rhs(other)),
                    DataType.int, ShapeType.scalar, ObjectType.value)

    def le(self, other) -> 'Expr':
        return Expr(sympy.Le(self._exprs[0], self._prep_rhs(other)),
                    DataType.int, ShapeType.scalar, ObjectType.value)

    def ge(self, other) -> 'Expr':
        return Expr(sympy.Ge(self._exprs[0], self._prep_rhs(other)),
                    DataType.int, ShapeType.scalar, ObjectType.value)

    # ------------------------------------------------------------------
    # Arithmetic operators
    # ------------------------------------------------------------------

    def _prep_num_op(self, msg: str, other):
        if len(self._exprs) != 1:
            raise RuntimeError(f'Cannot {msg} array Expr')
        return _to_sympy(other)

    def _make_result(self, sym_result: sympy.Basic, op: str, other_dt: DataType) -> 'Expr':
        dt = _promote(self.data_type, other_dt, op)
        if dt == DataType.undefined:
            dt = _infer_data_type(sym_result)
        return Expr(sym_result, dt)

    def _get_dt(self, other) -> DataType:
        if isinstance(other, Expr):
            return other.data_type
        if isinstance(other, bool):
            return DataType.int
        if isinstance(other, int):
            return DataType.int
        if isinstance(other, float):
            return DataType.float
        return DataType.undefined

    def __add__(self, other):
        rhs = self._prep_num_op('add to', other)
        return self._make_result(self._exprs[0] + rhs, '+', self._get_dt(other))

    def __sub__(self, other):
        rhs = self._prep_num_op('subtract', other)
        return self._make_result(self._exprs[0] - rhs, '-', self._get_dt(other))

    def __mul__(self, other):
        if isinstance(other, Expr) and len(other._exprs) > 1:
            # Scalar * vector: distribute element-wise
            dt = _promote(self.data_type, other.data_type, '*')
            return Expr([self._exprs[0] * e for e in other._exprs], dt,
                        ShapeType.vector, other.object_type)
        if len(self._exprs) > 1:
            # Vector * scalar: distribute element-wise
            rhs = _to_sympy(other)
            dt = _promote(self.data_type, self._get_dt(other), '*')
            return Expr([e * rhs for e in self._exprs], dt,
                        ShapeType.vector, self.object_type)
        rhs = self._prep_num_op('multiply', other)
        return self._make_result(self._exprs[0] * rhs, '*', self._get_dt(other))

    def __mod__(self, other):
        rhs = self._prep_num_op('mod', other)
        return self._make_result(sympy.Mod(self._exprs[0], rhs), '%', self.data_type)

    def __truediv__(self, other):
        rhs = self._prep_num_op('divide', other)
        return self._make_result(self._exprs[0] / rhs, '/', DataType.float)

    def __floordiv__(self, other):
        from .sympy_classes import CIntDiv
        rhs = self._prep_num_op('floor-divide', other)
        return self._make_result(CIntDiv(self._exprs[0], rhs), '//', DataType.int)

    def __pow__(self, other):
        rhs = self._prep_num_op('raise', other)
        return self._make_result(self._exprs[0] ** rhs, '**', self._get_dt(other))

    def __radd__(self, other):
        return self._make_result(_to_sympy(other) + self._exprs[0], '+', self._get_dt(other))

    def __rsub__(self, other):
        return self._make_result(_to_sympy(other) - self._exprs[0], '-', self._get_dt(other))

    def __rmul__(self, other):
        return self._make_result(_to_sympy(other) * self._exprs[0], '*', self._get_dt(other))

    def __rtruediv__(self, other):
        return self._make_result(_to_sympy(other) / self._exprs[0], '/', DataType.float)

    def __rfloordiv__(self, other):
        from .sympy_classes import CIntDiv
        return self._make_result(CIntDiv(_to_sympy(other), self._exprs[0]), '//', DataType.int)

    def __rpow__(self, other):
        return self._make_result(_to_sympy(other) ** self._exprs[0], '**', self._get_dt(other))

    def __neg__(self):
        return Expr([-e for e in self._exprs], self.data_type, self.shape_type, self.object_type)

    def __pos__(self):
        return self

    def __abs__(self):
        return Expr([sympy.Abs(e) for e in self._exprs], self.data_type, self.shape_type, self.object_type)

    def __round__(self, n=None):
        from .sympy_classes import CRound
        if self.data_type == DataType.int:
            return self

        def _round_one(e):
            if e.is_number:
                v = float(e)
                rounded = round(v, n) if n is not None else round(v)
                return sympy.Float(str(rounded))
            return CRound(e)

        return Expr([_round_one(e) for e in self._exprs], self.data_type, self.shape_type, self.object_type)

    # ------------------------------------------------------------------
    # Python boolean comparisons (not expression-tree builders)
    # ------------------------------------------------------------------

    def __eq__(self, other):
        def _num_eq(s, o):
            try:
                # Convert to Python float for comparison with absolute+relative tolerance.
                # This handles Integer vs Float (e.g. Integer(0) vs Float('0.0')),
                # ULP differences in large floats, and tiny-vs-zero comparisons.
                # atol=1e-14 catches values rounded to 14 decimal places
                # rtol=1e-12 catches ULP differences in large computed floats
                fs, fo = float(s), float(o)
                return abs(fs - fo) < 1e-14 + 1e-12 * max(abs(fs), abs(fo))
            except Exception:
                diff = sympy.simplify(s - o)
                return diff.is_zero is True

        if isinstance(other, Expr):
            if len(other._exprs) != len(self._exprs):
                return False
            return all(
                (_num_eq(s, o) if (s.is_number and o.is_number)
                 else s == o or sympy.simplify(s - o).is_zero is True)
                for s, o in zip(self._exprs, other._exprs)
            )
        if len(self._exprs) == 1:
            try:
                o = sympy.sympify(other)
                s = self._exprs[0]
                if s.is_number and o.is_number:
                    return _num_eq(s, o)
                return s == o
            except Exception:
                return False
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        if isinstance(other, Expr):
            if len(other._exprs) != len(self._exprs):
                raise RuntimeError('Cannot compare unequal-sized array Exprs')
            return all(bool(s < o) for s, o in zip(self._exprs, other._exprs)
                       if s.is_number and o.is_number)
        return len(self._exprs) == 1 and bool(self._exprs[0] < sympy.sympify(other))

    def __gt__(self, other):
        if isinstance(other, Expr):
            if len(other._exprs) != len(self._exprs):
                raise RuntimeError('Cannot compare unequal-sized array Exprs')
            return all(bool(s > o) for s, o in zip(self._exprs, other._exprs)
                       if s.is_number and o.is_number)
        return len(self._exprs) == 1 and bool(self._exprs[0] > sympy.sympify(other))

    def __le__(self, other):
        if isinstance(other, Expr):
            if len(other._exprs) != len(self._exprs):
                raise RuntimeError('Cannot compare unequal-sized array Exprs')
            return all(bool(s <= o) for s, o in zip(self._exprs, other._exprs)
                       if s.is_number and o.is_number)
        return len(self._exprs) == 1 and bool(self._exprs[0] <= sympy.sympify(other))

    def __ge__(self, other):
        if isinstance(other, Expr):
            if len(other._exprs) != len(self._exprs):
                raise RuntimeError('Cannot compare unequal-sized array Exprs')
            return all(bool(s >= o) for s, o in zip(self._exprs, other._exprs)
                       if s.is_number and o.is_number)
        return len(self._exprs) == 1 and bool(self._exprs[0] >= sympy.sympify(other))

    def __int__(self):
        if len(self._exprs) != 1:
            raise RuntimeError('No conversion to int for array Expr objects')
        return int(self._exprs[0])

    # ------------------------------------------------------------------
    # Expression manipulation
    # ------------------------------------------------------------------

    def simplify(self) -> 'Expr':
        simplified = []
        for e in self._exprs:
            try:
                s = sympy.trigsimp(sympy.simplify(e))
            except Exception:
                s = e
            simplified.append(s)
        result = Expr(simplified, self.data_type, self.shape_type, self.object_type)
        # If all elements are now pure numbers, update object_type to value
        if (result.object_type in (ObjectType.identifier, ObjectType.parameter)
                and all(e.is_number for e in result._exprs)):
            result.object_type = ObjectType.value
        return result

    def evaluate(self, known: dict) -> 'Expr':
        sub_map = {}
        for name, val in known.items():
            sym = sympy.Symbol(name)
            if isinstance(val, Expr) and val.is_singular:
                sub_map[sym] = val._exprs[0]
            elif isinstance(val, (int, float)):
                sub_map[sym] = sympy.sympify(val)
        result = [e.subs(sub_map) for e in self._exprs]
        evaluated = Expr(result, self.data_type, self.shape_type, self.object_type).simplify()
        # After evaluation, if all free symbols are gone, it's now a value
        if (evaluated.object_type in (ObjectType.identifier, ObjectType.parameter)
                and all(not e.free_symbols for e in evaluated._exprs)):
            evaluated.object_type = ObjectType.value
        return evaluated

    def depends_on(self, name: str) -> bool:
        if not isinstance(name, str):
            return False  # numeric literals are never free symbols
        target = {sympy.Symbol(name), McCodeParameter(name)}
        return any(bool(target & e.free_symbols) for e in self._exprs)

    def copy(self) -> 'Expr':
        return Expr(list(self._exprs), self.data_type, self.shape_type, self.object_type)

    def verify_parameters(self, instrument_parameter_names: list[str]) -> None:
        cache = self._exprs  # ensure cache is populated
        changed = False
        for i, e in enumerate(cache):
            for name in instrument_parameter_names:
                plain = sympy.Symbol(name)
                if plain in e.free_symbols:
                    cache[i] = e.subs(plain, McCodeParameter(name))
                    if isinstance(cache[i], McCodeParameter):
                        self.object_type = ObjectType.parameter
                    changed = True
        if changed:
            self.exprs = [sympy.srepr(e) for e in cache]


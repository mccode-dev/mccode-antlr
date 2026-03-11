# Expression API

`mccode-antlr` represents instrument parameter values and component parameter
values as `Expr` objects — a thin wrapper around a [SymPy](https://www.sympy.org)
symbolic expression tree that can emit either C or Python source code.

## Quick reference

```python
from mccode_antlr.common.expression import Expr, DataType

# Literal constants
Expr.float(1.5)            # float constant
Expr.integer(0)            # integer constant
Expr.string('"hello"')     # C string literal (note inner quotes)

# Identifiers and parameters
Expr.id("my_variable")              # generic identifier
Expr.parameter("E_i")               # instrument parameter (prefixed in C output)
Expr.parameter("n", DataType.int)   # with type hint
Expr.best(42)                       # auto-infer type from Python value

# Parse from a C expression string
e = Expr.parse("2*PI*sin(a3*DEG2RAD)")

# Arithmetic (all standard Python operators work)
e = Expr.parameter("E_i") * 2 + Expr.float(0.1)
e = Expr.float(1.0) / (Expr.id("q") ** 2)

# Bitwise operators (C semantics)
flags = Expr.id("flags") & Expr.integer(0xFF)   # bitwise AND
mask  = Expr.id("a") | Expr.id("b")             # bitwise OR
xor   = Expr.id("a") ^ Expr.id("b")             # bitwise XOR
inv   = ~Expr.id("flags")                       # bitwise NOT

# Comparison expressions (for WHEN conditions — return Expr, not bool)
cond = Expr.parameter("verbose").eq(1)             # verbose == 1
cond = Expr.parameter("mode").ne(0)                # mode != 0
cond = Expr.parameter("n").lt(10)                  # n < 10
cond = Expr.parameter("n").gt(0)                   # n > 0
cond = Expr.parameter("n").le(Expr.integer(5))     # n <= 5
cond = Expr.parameter("n").ge(1)                   # n >= 1
```

## Why not Python's `==` operator?

Python's `==` is reserved for object identity comparison and returns a `bool`.
Use `.eq()` / `.ne()` instead when you want to build an expression tree:

```python
Expr.parameter("flag") == 1   # returns False (Python equality test)!
Expr.parameter("flag").eq(1)  # returns an Expr -- correct
```

## SymPy backing

`Expr` wraps one or more SymPy `Basic` objects internally. This means:

- Algebraic simplification is available via `.simplify()`
- Substitution of known values via `.evaluate(known_dict)`
- Free-symbol inspection via `.depends_on(name)`
- Constant-folding happens automatically for numeric arithmetic

The C and Python code printers extend SymPy's printer infrastructure, so custom
McCode constructs (integer division, ternary expressions, bitwise operators,
shift operators, etc.) are handled transparently.

## Expr

::: mccode_antlr.common.expression.Expr

## Data types

::: mccode_antlr.common.expression.DataType

::: mccode_antlr.common.expression.ShapeType

::: mccode_antlr.common.expression.ObjectType

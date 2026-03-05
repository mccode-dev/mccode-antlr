# Expression API

`mccode-antlr` represents instrument parameter values and component parameter
values as `Expr` objects — symbolic expression trees that emit either C or
Python source code.

## Quick reference

```python
from mccode_antlr.common.expression import Expr, Value, DataType

# Literal constants
Expr.float(1.5)         # float constant
Expr.int(0)             # integer constant
Expr.str('"hello"')     # C string literal (note inner quotes)

# Identifiers and parameters
Expr.id("my_variable")          # generic identifier
Expr.parameter("E_i")           # instrument parameter (with prefix in C output)
Expr.parameter("n", DataType.int)  # with type hint

# Arithmetic (all Python operators work)
e = Expr.parameter("E_i") * 2 + Expr.float(0.1)
e = Expr.float(1.0) / (Expr.id("q") ** 2)

# Comparison expressions (for WHEN conditions)
cond = Expr.parameter("verbose").eq(1)      # verbose == 1
cond = Expr.parameter("mode").ne(0)         # mode != 0
cond = Expr.parameter("n").lt(10)           # n < 10
cond = Expr.parameter("n").gt(0)            # n > 0
cond = Expr.parameter("n").le(Expr.int(5))  # n <= 5
cond = Expr.parameter("n").ge(1)            # n >= 1

# Parsing from a C expression string
e = Expr.parse("2*PI*sin(a3*DEG2RAD)")
```

## Why not Python's `==` operator?

Python's `==` is reserved for object identity comparison and returns a `bool`.
Use `.eq()` / `.ne()` instead when you want to build an expression tree:

```python
Expr.parameter("flag") == 1   # returns False (Python equality test)!
Expr.parameter("flag").eq(1)  # returns Expr(BinaryOp(...)) -- correct
```

## Expr

::: mccode_antlr.common.expression.Expr

## Value

::: mccode_antlr.common.expression.Value

## Data types

::: mccode_antlr.common.expression.DataType

::: mccode_antlr.common.expression.ShapeType

::: mccode_antlr.common.expression.ObjectType

# Core Concepts

Understanding five key concepts makes the `mccode-antlr` API straightforward.

---

## Flavor

```python
from mccode_antlr import Flavor
```

`Flavor` is an enum with three values:

| Value | Meaning |
|---|---|
| `Flavor.MCSTAS` | Neutron Monte Carlo simulation (McStas) |
| `Flavor.MCXTRACE` | X-ray Monte Carlo simulation (McXtrace) |
| `Flavor.BASE` | Flavor-agnostic base (rarely used directly) |

Almost every entry point in the API accepts a `Flavor` argument that determines
which component library to use and which C runtime to target.

---

## Registry

A **Registry** is a named collection of component (`.comp`) files, together with
the metadata needed to locate them. When `mccode-antlr` needs to look up a
component by name (e.g. `"Source_simple"`), it searches through the registered
registries in order.

```python
from mccode_antlr.reader import registry_from_specification

# A local directory of .comp files
reg = registry_from_specification("/path/to/my/components")

# GitHub owner/repo at a specific tag (short form)
reg = registry_from_specification("mccode/McCode@v3.5.15")

# Same but with an explicit registry hash file
reg = registry_from_specification("mccode/McCode@v3.5.15#pooch-registry.txt")

# git+ URL form (like pip)
reg = registry_from_specification(
    "git+https://github.com/mccode-dev/McCode@v3.5.15"
)
```

See [API: Registries](api/registry.md) for all Registry types and specification
formats.

---

## Instr

`Instr` is the **intermediate representation** of a complete instrument. It is a
data structure — not a builder. It holds:

- Instrument name and parameters
- Ordered list of component instances (the TRACE section)
- C code blocks (DECLARE, INITIALIZE, SAVE, FINALLY)
- References to the registries needed to resolve component definitions

You rarely construct `Instr` objects directly. Instead you:

- Build one via [`Assembler`](#assembler) (programmatic construction)
- Parse one from a `.instr` file via the reader functions
- Receive one as the result of instrument transformations

```python
# Reading
from mccode_antlr.loader import load_mcstas_instr
instr = load_mcstas_instr("my_instrument.instr")

# Inspecting
for comp in instr.components:
    print(comp.name, comp.type.name)

# Writing
instr.to_file("output.instr")
```

---

## Assembler

`Assembler` is the **builder** for `Instr` objects. It provides a fluent API
for constructing instruments in Python without writing raw McCode syntax:

```python
from mccode_antlr import Flavor
from mccode_antlr.assembler import Assembler

a = Assembler("MyInstrument", flavor=Flavor.MCSTAS)
a.parameter("double E_i = 5.0")
a.parameter("int flag = 0")

src = a.component("Source", "Source_simple",
                  at=(0, 0, 0),
                  parameters={"E0": "E_i"})

instr = a.instrument   # returns an Instr
```

The `at` argument accepts:
- a 3-tuple → placed `ABSOLUTE`
- a 2-tuple of `(position, reference)` → placed `RELATIVE` to the reference
  (either a component name string or an `Instance`)

```python
det = a.component("Detector", "Monitor_nD",
                  at=([0, 0, 2], "Source"),   # 2 m downstream of Source
                  parameters={"filename": '"det.dat"', "options": '"energy"'})
```

The key methods are:

| Method | Purpose |
|---|---|
| `a.parameter(spec)` | Add an instrument parameter |
| `a.component(name, type)` | Add a component, returns the `Instance` |
| `a.declare(c_code)` | Add to the DECLARE block |
| `a.initialize(c_code)` | Add to the INITIALIZE block |
| `a.save(c_code)` | Add to the SAVE block |
| `a.final(c_code)` | Add to the FINALLY block |
| `a.instrument` | The `Instr` being assembled |

See [API: Assembler](api/assembler.md) for the full method list.

---

## Instance

An `Instance` is a single placed component in the TRACE section — the result of
`a.component(name, type)`. It combines:

- The component *type* (from a `.comp` file via a Registry)
- A unique *name* within the instrument
- Placement: position (`AT`), orientation (`ROTATE`), reference frame (`RELATIVE`)
- Optional: `WHEN` condition, `EXTEND` code, `GROUP`, `JUMP`, `SPLIT`

```python
from mccode_antlr.common.expression import Expr

monitor = a.component("Monitor", "TOF_monitor",
                      at=([0, 0, 5], "Source"),
                      parameters={"filename": '"tof.dat"', "tmin": 0.0, "tmax": 0.01})

# Conditional component (only active when instrument parameter `flag` == 1)
monitor.WHEN(Expr.parameter("flag").eq(1))
```

---

## Expression (Expr)

Instrument parameters and component parameter values are represented as `Expr`
objects — symbolic expression trees that can be:

- **Constant values**: `Expr.float(1.5)`, `Expr.int(0)`
- **Identifiers**: `Expr.id("my_variable")` (resolved at runtime)
- **Instrument parameters**: `Expr.parameter("E_i")` (resolved with the
  `_instrument_var._parameters.` prefix in generated C)
- **Operations**: arithmetic, comparison, function calls

```python
from mccode_antlr.common.expression import Expr

# Simple arithmetic
e = Expr.parameter("E_i") * 2 + Expr.float(0.1)

# Comparison (for WHEN conditions)
cond = Expr.parameter("verbose").eq(1)   # verbose == 1
cond = Expr.parameter("mode").ne(Expr.parameter("other"))
```

See [API: Expressions](api/expression.md) for the full `Expr` API.

# Installation & Quick Start

## Prerequisites

- Python 3.10 or later
- Java 11+ (required by ANTLR4 grammar compilation — only needed if you modify grammars)

## Install

=== "pip"

    ```bash
    pip install mccode_antlr
    ```

=== "conda / mamba"

    ```bash
    conda install conda-forge::mccode-antlr
    # or
    mamba install -c conda-forge mccode-antlr
    ```

Or, for the latest development version:

```bash
pip install git+https://github.com/mccode-dev/mccode-antlr.git
```

## Verify the installation

```bash
mcstas-antlr --help
mcxtrace-antlr --help
mccode-antlr --help
```

---

## Command-line workflow

The primary use case is compiling `.instr` files into C source that the McCode
runtime can compile and run:

```bash
# Translate a McStas instrument to C
mcstas-antlr my_instrument.instr -o my_instrument.c

# Run a simulation (wraps mcstas-antlr + C compilation + execution)
mcrun-antlr my_instrument.instr -n 1e6 E_i=5.0
```

The `mccode-antlr` management command controls caches and configuration:

```bash
mccode-antlr cache list          # list cached component registries
mccode-antlr cache ir-build      # pre-build component intermediate representations
mccode-antlr config list         # display active configuration
```

---

## Python API workflow

The Python API is the focus of this documentation. The central object is
[`Assembler`](api/assembler.md) — a builder that constructs an
[`Instr`](api/instr.md) object step by step.

### Step 1 — Create an Assembler

```python
from mccode_antlr import Flavor
from mccode_antlr.assembler import Assembler

a = Assembler("MyInstrument", flavor=Flavor.MCSTAS)
```

[`Flavor`][mccode_antlr.Flavor] selects the target runtime:
`Flavor.MCSTAS` for neutron simulation, `Flavor.MCXTRACE` for X-ray.

### Step 2 — Declare instrument parameters

```python
a.parameter("double wavelength = 2.0")   # Angstrom
a.parameter("int verbose = 0")
```

Parameters become the command-line arguments of the compiled instrument.

### Step 3 — Add components

```python
origin = a.component("Origin", "Progress_bar", at=(0, 0, 0))

source = a.component("Source", "Source_simple",
                     at=(0, 0, 0),
                     parameters={"lambda0": "wavelength", "dlambda": 0.05, "radius": 0.05})
```

The `at` argument accepts:
- a 3-tuple → placed `ABSOLUTE`
- a 2-tuple of `(position, reference)` → placed `RELATIVE` to the named component or `Instance`

### Step 4 — Add C code blocks (optional)

```python
a.declare("double lambda_min, lambda_max;")
a.initialize("lambda_min = wavelength - 0.05; lambda_max = wavelength + 0.05;")
```

### Step 5 — Build and inspect the instrument

```python
instr = a.instrument

# Print as McCode text
print(instr)

# In Jupyter: just put `instr` on the last line of a cell for an interactive
# collapsible HTML view
```

### Step 6 — Write to file

```python
instr.to_file("MyInstrument.instr")
```

---

## Reading an existing instrument

```python
from mccode_antlr.loader import load_mcstas_instr

instr = load_mcstas_instr("path/to/existing.instr")
print(instr.components)
```

---

## Parsing instruments and components from strings

You can write McCode DSL directly inside Python using `dedent` and parse it
with `parse_mcstas_instr` / `parse_mcxtrace_instr`. This is useful for:

- Rapid prototyping — write McCode syntax, inspect the IR, no files on disk
- Testing — compare generated C against a known-good inline reference
- Mixing DSL and API — parse a skeleton instrument, then modify it programmatically

### Parsing a complete instrument string

```python
from textwrap import dedent
from mccode_antlr.loader import parse_mcstas_instr

instr = parse_mcstas_instr(dedent("""\
    DEFINE INSTRUMENT MySpec(double E_i = 5.0)
    TRACE
    COMPONENT Origin = Progress_bar() AT (0, 0, 0) ABSOLUTE
    COMPONENT Source = Source_simple(E0 = E_i, dE = 0.5, radius = 0.05)
      AT (0, 0, 0) ABSOLUTE
    END
"""))

for comp in instr.components:
    print(comp.name, comp.type.name)
```

The default McStas/McXtrace component registries are used automatically, so
component types are resolved the same way as when reading from a file.

### Defining an inline component type

Use `InMemoryRegistry` to define one-off component types as Python strings,
then pass the registry to the `Assembler`:

```python
from textwrap import dedent
from mccode_antlr import Flavor
from mccode_antlr.assembler import Assembler
from mccode_antlr.reader import InMemoryRegistry

my_comp = InMemoryRegistry("custom")
my_comp.add_comp("Shutter", dedent("""\
    DEFINE COMPONENT Shutter
    SETTING PARAMETERS (int open = 1)
    TRACE
    WHEN (open) ABSORB;
    END
"""))

a = Assembler("MyInstrument", registries=[my_comp], flavor=Flavor.MCSTAS)
shutter = a.component("S", "Shutter", at=(0, 0, 1), parameters={"open": "verbose"})
instr = a.instrument
```

Alternatively, inject a component string into an existing `Reader` via
`reader.inject_source(name, source)` — this is the approach used internally
by the language server for unsaved editor buffers.

---

## What next?

- [Core Concepts](core-concepts.md) — understand the Flavor/Instr/Assembler/Registry model
- [How-To: Build an instrument with the Assembler](how-to/assembler-instrument.md)
- [How-To: Compile and run from Python](how-to/compile-and-run.md)
- [API Reference: Assembler](api/assembler.md)

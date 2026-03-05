# How-To: Compile and run an instrument from Python

`mccode-antlr` can generate C source, compile it into a binary, and execute it
entirely from Python — no shell scripts required. This page covers all three
levels of the API, from lowest to highest.

---

## Prerequisites

The C compiler and McCode runtime must be available on your system (the same
prerequisites as for `mcstas-antlr` / `mcxtrace-antlr` on the command line).

---

## Level 1 — Generate C source from an Instr

`instrument_source` translates an `Instr` object into the C source string that
the McCode runtime would compile:

```python
from mccode_antlr import Flavor
from mccode_antlr.compiler.c import instrument_source

config = dict(
    default_main=True,
    enable_trace=False,
    portable=False,
    include_runtime=True,
    embed_instrument_file=False,
    verbose=False,
)

c_source = instrument_source(instr, Flavor.MCSTAS, config)

# Inspect it
print(c_source[:500])

# Write to disk
with open("MyInstrument.c", "w") as f:
    f.write(c_source)
```

This is useful for debugging the translation step, diffing against known-good
output in tests, or feeding the source to a custom build system.

---

## Level 2 — Compile to a binary

`mccode_compile` calls the system C compiler to produce an executable:

```python
from pathlib import Path
from mccode_antlr import Flavor
from mccode_antlr.run import mccode_compile

build_dir = Path("/tmp/my_build")
build_dir.mkdir(exist_ok=True)

binary, target = mccode_compile(instr, build_dir, flavor=Flavor.MCSTAS)
print("Binary at:", binary)
```

`binary` is a `Path` to the compiled executable; `target` is a `CBinaryTarget`
describing the compilation options used (standard C, MPI, OpenACC, etc.).

### Compiler options

Pass `target` and `config` dicts to control the build:

```python
binary, target = mccode_compile(
    instr, build_dir, flavor=Flavor.MCSTAS,
    target={"mpi": True, "count": 4},   # MPI with 4 processes
    config={"enable_trace": True},       # include TRACE visualisation support
)
```

---

## Level 3 — Run a compiled binary

`mccode_run_compiled` executes the binary, waits for it to finish, and returns
the detector data parsed from the output `.dat` files:

```python
from pathlib import Path
from mccode_antlr.run import mccode_run_compiled

# The output directory must NOT already exist — McCode creates it.
output_dir = Path("/tmp/my_run_001")

result, data = mccode_run_compiled(
    binary, target,
    output_dir,
    "-n 1000000 E_i=5.0 verbose=0",
)

# `data` is a dict mapping detector stem → McCodeDatData object
for name, det in data.items():
    print(name, det)
```

The parameters string is passed directly to the binary as command-line
arguments (the same syntax as `mcrun-antlr`). The output directory is passed
as `--dir` to the binary; McCode requires it to not already exist.

---

## Level 4 — Compile and run in one call (temp directory)

`compile_and_run` handles the complete pipeline in a temporary directory that
is cleaned up automatically. The `.dat` files are read and returned before
deletion:

```python
from mccode_antlr import Flavor
from mccode_antlr.utils import compile_and_run

result, data = compile_and_run(
    instr,
    parameters="-n 1000000 E_i=5.0",
    flavor=Flavor.MCSTAS,
)

for name, det in data.items():
    print(name, det)
```

Set `run=False` to compile only (still in a temp directory):

```python
compile_and_run(instr, parameters="", run=False, flavor=Flavor.MCSTAS)
```

`dump_source=True` is the default — `compile_and_run` writes the generated C
file into the current working directory alongside running. Set
`dump_source=False` to suppress this:

```python
result, data = compile_and_run(
    instr, "-n 1e5 E_i=5.0",
    dump_source=False,
    flavor=Flavor.MCSTAS,
)
```

---

## Putting it all together

```python
from textwrap import dedent
from mccode_antlr import Flavor
from mccode_antlr.assembler import Assembler
from mccode_antlr.utils import compile_and_run

# Build the instrument
a = Assembler("Quicktest", flavor=Flavor.MCSTAS)
a.parameter("double E_i = 5.0")
a.component("Origin", "Progress_bar", at=(0, 0, 0))
a.component("Source", "Source_simple",
            at=(0, 0, 0),
            parameters={"E0": "E_i", "dE": 0.5, "radius": 0.05,
                        "dist": 1.0, "focus_xw": 0.1, "focus_yh": 0.1})
a.component("Det", "E_monitor",
            at=([0, 0, 1], "Source"),
            parameters={"filename": '"energy.dat"', "Emin": 0.0, "Emax": 10.0,
                        "nchan": 100, "xwidth": 0.1, "yheight": 0.1})
instr = a.instrument()

# Compile and run
result, data = compile_and_run(instr, "-n 1e5 E_i=5.0", flavor=Flavor.MCSTAS)

# Inspect results
print(data.get("energy"))
```

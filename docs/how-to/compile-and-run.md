# How-To: Compile and run an instrument from Python

`mccode-antlr` can generate C source, compile it into a binary, and execute it
entirely from Python — no shell scripts required. This page covers all levels
of the API, from the recommended high-level `Simulation` class down to the
individual low-level functions.

---

## Prerequisites

The C compiler and McCode runtime must be available on your system (the same
prerequisites as for `mcstas-antlr` / `mcxtrace-antlr` on the command line).

---

## Recommended: the `Simulation` class

The `McStas` and `McXtrace` classes (both subclasses of `Simulation`) are the
simplest way to compile an instrument and run simulations from Python.

### Compile, run, inspect

```python
from mccode_antlr.loader import parse_mcstas_instr
from mccode_antlr.run import McStas

instr = parse_mcstas_instr("MyInstrument.instr")

# compile() creates a temporary directory automatically.
# The directory — and the binary inside it — live as long as `sim` does.
sim = McStas(instr).compile()

# Run a single simulation point.
result, out = sim.run({'E_i': 5.0, 'angle': 30.0}, ncount=1_000_000, seed=42)

# `out` is a SimulationOutput — a dict-like object keyed by detector stem.
print(out['energy'].data.shape)   # e.g. (3, 100) for a 1-D, 100-bin monitor
print(out.directory)              # Path to the output directory on disk
```

Method chaining is supported for compact one-liners:

```python
result, out = McStas(instr).compile().run({'E_i': 5.0}, ncount=1_000_000)
```

### Use default parameter values

Omit `parameters` (or pass `{}`) to run with the instrument's compiled-in
defaults, equivalent to `mcrun -y`:

```python
result, out = sim.run(ncount=1_000_000)
```

### Provide a persistent compile directory

Pass an explicit directory to `compile()` if you want the binary to outlive the
`Simulation` object, or to skip recompilation on subsequent runs:

```python
from pathlib import Path

sim = McStas(instr).compile(Path("/tmp/my_build"))
# Reuse the same binary without recompiling:
sim2 = McStas(instr).compile(Path("/tmp/my_build"))  # skips compile if binary exists
```

### Parameter scans

`scan()` iterates over one or more parameter ranges and returns a list of
`(result, SimulationOutput)` tuples — one per scan point.

```python
# 1-D scan: E_i steps from 1 to 5 in increments of 1 (5 points)
results = sim.scan({'E_i': '1:1:5', 'angle': 30.0}, ncount=100_000)

for result, out in results:
    print(out['energy'].data[0].sum())   # total intensity at this scan point
```

Use an explicit Python list for non-uniform steps:

```python
results = sim.scan({'E_i': [1.0, 2.5, 5.0, 10.0]}, ncount=100_000)
```

Grid (Cartesian product) scan:

```python
# 3 × 5 = 15 total simulations
results = sim.scan(
    {'E_i': '1:1:3', 'angle': '10:5:30'},
    grid=True, ncount=100_000,
)
```

### Working with `SimulationOutput`

`SimulationOutput` acts as a `Mapping` from detector stem to loaded data, so
existing code that expected a plain `dict` continues to work.  It also exposes
additional information about everything written to disk:

```python
result, out = sim.run({'E_i': 5.0}, ncount=1_000_000)

# Dict-like access (backward-compatible)
det = out['energy']      # DatFile1D / DatFile2D / DatFile0D
print(det['I'])          # intensity array
print(det['I_err'])      # uncertainty array
print(len(out))          # number of McCode-format detectors found

# All McCode-format files (any extension — catches Monitor_nD output)
for stem, dat in out.dats.items():
    print(stem, dat.data.shape)

# Files loaded by custom filters (see below)
print(out.other)

# Files that could not be loaded by any filter
for path in out.unrecognized:
    print("Unknown file:", path.name)

# Parsed simulation metadata (.sim file)
if out.sim_file is not None:
    print(out.sim_file)
```

### Registering custom output-file loaders

Some components write output in formats other than the McCode `.dat` format
(MCPL particle lists, HDF5 files, etc.).  Register a loader for a file
extension and it will be called automatically on every matching file:

```python
from mccode_antlr.run import register_output_filter
import h5py

register_output_filter('.h5', h5py.File)

result, out = sim.run({'E_i': 5.0}, ncount=1_000_000)
hdf5_data = out.other.get('nexus_output')   # loaded by h5py.File
```

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
the detector data parsed from the output files:

```python
from pathlib import Path
from mccode_antlr.run import mccode_run_compiled

# The output directory must NOT already exist — McCode creates it.
output_dir = Path("/tmp/my_run_001")

result, out = mccode_run_compiled(
    binary, target,
    output_dir,
    "-n 1000000 E_i=5.0 verbose=0",
)

# `out` is a SimulationOutput (dict-like, keyed by detector stem)
for name, det in out.items():
    print(name, det.data.shape)
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
from mccode_antlr.assembler import Assembler
from mccode_antlr import Flavor
from mccode_antlr.run import McStas

# Build the instrument programmatically
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
instr = a.instrument

# Compile once, run several times
sim = McStas(instr).compile()

# Single run at the default parameter values
result, out = sim.run(ncount=1_000_000)
print("Default run intensity:", out['energy']['I'].sum())

# Scan over E_i
for result, out in sim.scan({'E_i': '1:1:10'}, ncount=100_000):
    print(out['energy']['I'].sum())
```


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
instr = a.instrument

# Compile and run
result, data = compile_and_run(instr, "-n 1e5 E_i=5.0", flavor=Flavor.MCSTAS)

# Inspect results
print(data.get("energy"))
```

# How-To: Build an instrument with the Assembler

This guide walks through building a non-trivial instrument programmatically using
the [`Assembler`](../api/assembler.md) API.

## Goal

A simple time-of-flight spectrometer:

```
Source → Chopper → Sample → Monitor
```

with an instrument parameter for the chopper frequency.

---

## 1. Create the Assembler

```python
from mccode_antlr import Flavor
from mccode_antlr.assembler import Assembler

a = Assembler("SimpleTOF", flavor=Flavor.MCSTAS)
```

## 2. Declare parameters

```python
a.parameter("double frequency = 150")  # Hz
a.parameter("double E_i = 25")         # meV incident energy
a.parameter("int verbose = 0")
```

## 3. Optional: DECLARE block for computed C variables

```python
a.declare("double lambda_i;")
a.initialize("lambda_i = sqrt(81.81 / E_i);  /* Angstrom */")
```

## 4. Add components

```python
from mccode_antlr.common.expression import Expr

# Progress bar (mandatory origin marker)
origin = a.component("Origin", "Progress_bar", at=(0, 0, 0))

# Source
source = a.component("Source", "Source_simple",
                     at=(0, 0, 0),
                     parameters={"radius": 0.05, "E0": "E_i", "dE": 1.0,
                                 "dist": 10.0, "focus_xw": 0.05, "focus_yh": 0.05})

# Fermi chopper at 10 m
chopper = a.component("Chopper", "FermiChopper",
                      at=([0, 0, 10], source),
                      parameters={"nu": "frequency", "radius": 0.05, "yheight": 0.08})

# Sample position at 20 m
sample = a.component("Sample", "V_sample",
                     at=([0, 0, 20], source),
                     parameters={"radius": 0.005, "yheight": 0.04})

# Monitor at 25 m -- only active when verbose == 1
monitor = a.component("Monitor", "TOF_monitor",
                      at=([0, 0, 25], source),
                      parameters={"nchan": 1000, "tmin": 0.0, "tmax": 0.1,
                                  "filename": '"tof.dat"'},
                      when=Expr.parameter("verbose").eq(1))
```

## 5. Build and write to file

```python
instr = a.instrument
instr.to_file("SimpleTOF.instr")
print(instr)
```

## 6. Run (optional)

```bash
mcrun-antlr SimpleTOF.instr -n 1e6 --E_i=25 --frequency=150 --verbose=1
```

---

## Tips

- `a.component()` returns an `Instance` — keep the reference if you need to call
  `.WHEN()`, `.EXTEND()`, etc. after construction.
- The `at` argument's reference (`at=([0,0,10], source)`) accepts a component name
  string or an `Instance` reference.
- String component parameter values that are C string literals need inner quotes:
  `parameters={"filename": '"tof.dat"'}`.
- Use `Expr.parameter("name").eq(value)` for `WHEN` conditions rather than
  constructing `BinaryOp` objects manually.
- Pass `when=` directly to `a.component()` to set the condition at construction time,
  or call `.WHEN()` on the returned `Instance` afterwards.

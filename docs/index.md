# mccode-antlr

**ANTLR4-based compiler and Python API for the McStas and McXtrace Monte Carlo ray-tracing languages.**

`mccode-antlr` provides:

- A faithful re-implementation of the McStas/McXtrace instrument languages using ANTLR4 grammars
- Command-line tools (`mcstas-antlr`, `mcxtrace-antlr`, …) that replace the traditional lex/yacc translators
- A Python API for programmatically building, reading, and manipulating instruments

---

## Quick start

=== "Command line"

    ```bash
    pip install mccode_antlr

    # Compile a McStas instrument
    mcstas-antlr my_instrument.instr

    # Or the McXtrace variant
    mcxtrace-antlr my_experiment.instr
    ```

=== "Python API"

    ```python
    from mccode_antlr import Flavor
    from mccode_antlr.assembler import Assembler

    a = Assembler("BrillouinSpectrometer", flavor=Flavor.MCSTAS)
    a.parameter("double E_i = 5.0")   # meV
    a.parameter("int nmon = 1")

    origin = a.component("Origin", "Progress_bar", at=(0, 0, 0))

    source = a.component("Source", "Source_simple",
                         at=(0, 0, 0),
                         parameters={"radius": 0.05, "E0": "E_i", "dE": 0.1})

    instr = a.instrument()
    print(instr)   # or display in Jupyter: just put `instr` on the last line
    ```

---

## Why ANTLR4?

The traditional McCode translators mix language parsing and code generation
inside `lex`/`yacc` rules — making them hard to debug and impossible to
tool-integrate. ANTLR4 cleanly separates grammar from behaviour and integrates
with IDEs (including the free PyCharm Community edition) for live syntax
checking of `.comp` and `.instr` files.

See [Core Concepts](core-concepts.md) for a fuller explanation.

---

## Installation

=== "pip"

    ```bash
    pip install mccode_antlr          # latest release
    pip install git+https://github.com/mccode-dev/mccode-antlr.git  # dev
    ```

=== "conda / mamba"

    ```bash
    conda install conda-forge::mccode-antlr
    mamba install -c conda-forge mccode-antlr
    ```

Optional pip extras:

```bash
pip install "mccode_antlr[hdf5]"   # HDF5 output support
pip install "mccode_antlr[mcpl]"   # MCPL file support
pip install "mccode_antlr[docs]"   # build this documentation locally
```

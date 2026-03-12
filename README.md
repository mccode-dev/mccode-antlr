# mccode-antlr

[![PyPI](https://img.shields.io/pypi/v/mccode_antlr)](https://pypi.org/project/mccode_antlr/)
[![conda-forge](https://img.shields.io/conda/vn/conda-forge/mccode-antlr)](https://anaconda.org/conda-forge/mccode-antlr)
[![License](https://img.shields.io/badge/license-BSD--3--Clause-blue)](LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/mccode_antlr)](https://pypi.org/project/mccode_antlr/)

ANTLR4-based compiler and Python API for the McStas and McXtrace Monte Carlo
particle ray-tracing languages.

**[Documentation](https://mccode-dev.github.io/mccode-antlr/)** ·
[PyPI](https://pypi.org/project/mccode_antlr/) ·
[conda-forge](https://anaconda.org/conda-forge/mccode-antlr) ·
[Issues](https://github.com/mccode-dev/mccode-antlr/issues)

## Quick start

### Command line

```bash
pip install mccode_antlr

mcstas-antlr my_instrument.instr   # translate to C
mcrun-antlr  my_instrument.instr -n 1e6 E_i=5.0   # compile & run
```

### Python API

```python
from mccode_antlr import Flavor
from mccode_antlr.assembler import Assembler

a = Assembler("BrillouinSpec", flavor=Flavor.MCSTAS)
a.parameter("double E_i = 5.0")   # meV

src = a.component("Source", "Source_simple",
                  at=(0, 0, 0),
                  parameters={"E0": "E_i", "radius": 0.05})

instr = a.instrument()
instr.to_file("BrillouinSpec.instr")

# In Jupyter: just put `instr` on the last line of a cell for an interactive view
```

## Installation

```bash
# pip
pip install mccode_antlr                 # latest release
pip install "mccode_antlr[hdf5]"         # with HDF5 output
pip install "mccode_antlr[mcpl]"         # with MCPL file support
pip install "mccode_antlr[ipython]"      # with IPython/Jupyter matcher support

# conda / mamba (conda-forge)
conda install conda-forge::mccode-antlr
mamba install -c conda-forge mccode-antlr

# development version
pip install git+https://github.com/mccode-dev/mccode-antlr.git
```

## Documentation

Full documentation — including a getting-started guide, core concepts, how-to
guides, and API reference — is at:

**https://mccode-dev.github.io/mccode-antlr/**

## IPython / Jupyter completions

`mccode_antlr` can register an IPython matcher for Python authoring with
`Assembler` and `Simulation` objects:

```python
from mccode_antlr.integrations.ipython import register_ipython_matcher

register_ipython_matcher()
```

Or in IPython / Jupyter:

```python
%load_ext mccode_antlr.integrations.ipython
```

This matcher is intended for Python-side completions such as component names,
component parameter names, and simulation parameter names. It does not provide
raw McCode DSL completion inside notebook cells. The `%load_ext` path is the
recommended automatic registration mechanism; importing the module alone does
not register the matcher as a side effect.

## Why ANTLR4?


included in-rule code to implement some language features and called
the code-generator to construct the intermediate instrument source file.
The mixture of language parsing and multiple layers of generated functionality
made understanding the program operation, and debugging introduced errors,
difficult.
Worst of all, there is no easy-to-use tooling available to help the programmer
identify syntax errors on-the-fly.

This project reimplements the `McCode` language**s** using `ANTLR4`
which both tokenizes and parses the language into a recursive descent parse tree.
`ANTLR` can include extra in-rule parsing code, but since it can produce output
suited for multiple languages (and the extra code must be _in_ the targeted language)
this feature is not implemented in this project.

Other benefits of `ANTLR4` include integration with Integrated Development Environments,
including the freely available Community edition of PyCharm from JetBrains.
IDE integration can identify syntax mistakes in the language grammar files,
plus help to understand and debug language parsing.

## McCode languages

Traditionally, `McCode` identifies as a single language able to read, parse, and construct
programs to perform single particle statistical ray tracing.
While `McCode-3` uses a single `language.l` and `language.y` file pair for lexing and parsing, 
it actually implemented _at least two_ related languages: one for component definitions in `.comp` files,
one for instrument definitions in `.instr` files,
plus arguably more for other specialised tasks.
Notably the `mcdisplay` utilities of `McCode` make use of a special runtime output mode
to identify the positions and shapes of components, and the paths of particles, which
is then read by an independent `ply` parser to generated visualizations.

This project makes use of `ANTLR`'s language dependency feature to separate the languages
into `McComp` for components and `McInstr` for instruments, with common language features
defined in a `McCommon` grammar.

## Language translation
For use with the `McCode` runtimes (`McStas` and `McXtrace`), the input languages must be
translated to `C` following the `C99` standard.
This translation was previously performed *in* `C` since the `lex|flex`, `yacc|bison` 
workflow produced programs written in `C`.
The `C` programming language is a very good choice where execution speed is important,
as in the `McCode` runtimes, but less so if speed is not the main goal and memory safety
or cross-platform development is important.
The `McCode-3` translators do not always deallocate memory used in their runtime,
and newly developed features are likely to introduce unallocated, out-of-bounds, or double-free
memory errors which are then difficult to track down.

`ANTLR4` is a `Java` program, but produces parse-trees in multiple languages.
This project uses the `Python` target so that language-translation can proceed in a language
which is well suited to new-feature development, while removing memory handling issues and
making cross-platform development significantly easier.


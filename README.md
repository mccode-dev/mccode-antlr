# Monte Carlo Particle Ray Tracing compiler via ANTLR4

Implementing the `mccode-3` language and targeting the `mcstas` and `mcxtrace` runtimes.

# Installation
Install the latest development version from GitHub with
```Bash
$ python -m pip install git+https://github.com/mccode-dev/mccode-antlr.git
```
or the latest release from PyPI with
```Bash
$ python -m pip install mccode_antlr
```

# Use
The `mccode-antlr` package provides a command-line interface to the `McCode` language parsers
and translators. To avoid shadowing the `McCode-3` translators, the command-line interface
are suffixed with `-antlr`.

```Bash
$ mcstas-antlr --help
```

```Bash
$ mcxtrace-antlr --help
```

A local cache is used for storing instrument component files and
runtime library files obtained from [the McCode repository](https://github.com/mccode-dev/McCode.git).
The cache and configuration parameters for the whole `mccode-antlr` module can be
accessed via a third command-line interface:
```Bash
$ mccode-antlr --help
```

## Language parsing with ANTLR4
The traditional `McCode` `lex|flex` tokenizer and `yacc|bison` parser
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


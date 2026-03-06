# Simulation API

The `Simulation` class (and its `McStas` / `McXtrace` subclasses) is the
recommended Python API for compiling McCode instruments and running
single-point simulations or parameter scans.

The `SimulationOutput` class holds all files written to disk by a single run,
providing both backward-compatible dict-like access to McCode detector data
and richer information about every file the binary produced.

---

## `McStas` and `McXtrace`

Use these subclasses directly — they pre-set the instrument flavor so you
never have to import `Flavor` yourself:

::: mccode_antlr.run.simulation.McStas
    options:
      show_root_heading: true
      members: [__init__]

::: mccode_antlr.run.simulation.McXtrace
    options:
      show_root_heading: true
      members: [__init__]

---

## `Simulation`

::: mccode_antlr.run.simulation.Simulation
    options:
      show_root_heading: true
      members:
        - __init__
        - compile
        - run
        - scan

---

## `SimulationOutput`

::: mccode_antlr.run.output.SimulationOutput
    options:
      show_root_heading: true
      members:
        - dats
        - other
        - loaded
        - unrecognized
        - sim_file
        - directory

---

## `register_output_filter`

::: mccode_antlr.run.output.register_output_filter
    options:
      show_root_heading: true

# How-To: Work with component registries

A **Registry** tells `mccode-antlr` where to find `.comp` component definition
files. This guide covers the common registry patterns.

---

## Default registries

When you use `Assembler` with `Flavor.MCSTAS` or `Flavor.MCXTRACE`, the
appropriate McCode release registry is automatically loaded from the local cache
(populated the first time you install or explicitly with
`mccode-antlr cache populate`).

---

## Specifying a registry from a local directory

```python
from mccode_antlr.reader import registry_from_specification

reg = registry_from_specification("/path/to/my_components")
```

All `.comp` files in that directory are registered under their stem name (e.g.
`My_Detector.comp` → `"My_Detector"`).

You can also give it an explicit name:

```python
reg = registry_from_specification("mylib /path/to/my_components")
```

---

## Specifying a GitHub-hosted registry

```python
# Short form (like pip's git+ syntax)
reg = registry_from_specification(
    "git+https://github.com/mccode-dev/McCode@v3.5.15"
)

# Full form (name url version registry-filename)
reg = registry_from_specification(
    "mccode https://github.com/mccode-dev/McCode v3.5.15 pooch-registry.txt"
)

# Registry file in a separate repo (5-token form)
reg = registry_from_specification(
    "mylib https://github.com/myorg/mycomps v1.2 pooch-registry.txt "
    "https://github.com/myorg/mycomps-registry v1.2 registry.txt"
)
```

---

## Passing extra registries to the Assembler

```python
from mccode_antlr import Flavor
from mccode_antlr.assembler import Assembler
from mccode_antlr.reader import registry_from_specification

local = registry_from_specification("/path/to/my_components")

a = Assembler("MyInstrument", flavor=Flavor.MCSTAS)
a.reader.append_registry(local)
```

Registries are searched in order, so append local overrides after the defaults.

---

## In-memory registries

For testing or embedded use you can build a registry entirely in Python:

```python
from mccode_antlr.reader.registry import InMemoryRegistry

reg = InMemoryRegistry("test_lib")
reg.add_comp("My_Detector", comp_source_string)
```

---

## Registry round-trip

When an `Instr` is written to a `.instr` file via `instr.to_file()`, each
registry is serialised as a comment at the top of the file:

```
// Registry: mylib https://github.com/myorg/mycomps v1.2 pooch-registry.txt
```

When the file is read back, `mccode-antlr` reconstructs the registry
automatically so the component definitions are available.

---

## Cache management

```bash
mccode-antlr cache list          # show all cached registries
mccode-antlr cache populate      # download default McStas + McXtrace registries
mccode-antlr cache ir-build      # pre-build component IR (speeds up first parse)
mccode-antlr cache ir-clean      # remove stale IR cache entries
```

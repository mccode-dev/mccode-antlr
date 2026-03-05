# Registries API

Registries map component names to their source `.comp` files. `mccode-antlr`
supports local directories, remote (GitHub-hosted) releases, and in-memory
registries for testing.

## registry_from_specification

The most convenient entry point — accepts several specification formats:

```python
from mccode_antlr.reader import registry_from_specification

# Local directory
reg = registry_from_specification("/path/to/components")

# Local directory with explicit name
reg = registry_from_specification("mylib /path/to/components")

# GitHub release (short pip-style form)
reg = registry_from_specification("git+https://github.com/mccode-dev/McCode@v3.5.15")

# GitHub release (full form: name url version registry-file)
reg = registry_from_specification(
    "mccode https://github.com/mccode-dev/McCode v3.5.15 pooch-registry.txt"
)
```

::: mccode_antlr.reader.registry_from_specification

---

## Registry (base class)

::: mccode_antlr.reader.registry.Registry

---

## LocalRegistry

::: mccode_antlr.reader.registry.LocalRegistry

---

## GitHubRegistry

::: mccode_antlr.reader.registry.GitHubRegistry

---

## InMemoryRegistry

::: mccode_antlr.reader.registry.InMemoryRegistry

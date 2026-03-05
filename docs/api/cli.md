# CLI Reference

`mccode-antlr` installs eight command-line programs.

---

## Compiler commands

### `mcstas-antlr`

Translates a McStas `.instr` file to C source code.

```bash
mcstas-antlr [OPTIONS] INSTR_FILE
```

| Option | Description |
|---|---|
| `-o FILE` | Output C file (default: `<stem>.c`) |
| `-I DIR` | Add a component search directory |
| `--verbose` | Show progress messages |

### `mcxtrace-antlr`

McXtrace equivalent of `mcstas-antlr`.

---

## Run commands

### `mcrun-antlr`

Compile and run a McStas instrument simulation.

```bash
mcrun-antlr INSTR_FILE -n NPARTICLES [--PARAM=VALUE ...]
```

### `mxrun-antlr`

McXtrace equivalent of `mcrun-antlr`.

---

## Compile-only commands

### `mcc-antlr`

Compile a McStas instrument to a binary without running it.

### `mxc-antlr`

McXtrace equivalent of `mcc-antlr`.

---

## Format command

### `mcfmt`

Format a `.instr` or `.comp` file in canonical style.

```bash
mcfmt [OPTIONS] FILE [FILE ...]
```

---

## Management command

### `mccode-antlr`

Top-level management utility for caches, configuration, and diagnostics.

```bash
mccode-antlr SUBCOMMAND [OPTIONS]
```

**Subcommands:**

| Subcommand | Description |
|---|---|
| `cache list` | List cached component registries |
| `cache populate` | Download default McStas and McXtrace registries |
| `cache ir-build` | Pre-build component intermediate representations |
| `cache ir-clean` | Remove stale IR cache entries |
| `config show` | Display the active configuration |
| `config path` | Print the configuration file path |

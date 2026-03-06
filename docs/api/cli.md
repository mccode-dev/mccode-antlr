# CLI Reference

`mccode-antlr` installs eight command-line programs.

---

## Instrument translation

Translate a McCode `.instr` file to C source code.

=== "McStas"

    ```bash
    mcstas-antlr [OPTIONS] INSTR_FILE
    ```

=== "McXtrace"

    ```bash
    mcxtrace-antlr [OPTIONS] INSTR_FILE
    ```

| Flag | Default | Description |
|---|---|---|
| `INSTR_FILE` | *(required)* | `.instr` file to translate |
| `-o FILE`, `--output-file FILE` | `<stem>.c` | Output C file |
| `-I DIR`, `--search-dir DIR` | — | Extra component search directory (repeatable) |
| `-t` / `--trace` / `--no-trace` | off | Enable *trace* mode for instrument display |
| `-p` / `--portable` / `--no-portable` | off | Generate portable output for cross-platform compatibility |
| `--source` / `--no-source` | off | Embed the instrument source code in the generated C |
| `--main` / `--no-main` | on | Emit a `main()` entry point (`--no-main` for external embedding) |
| `--runtime` / `--no-runtime` | on | Embed McCode run-time libraries in the generated C |
| `--verbose` / `--no-verbose` | off | Verbose output during translation |
| `-L` / `--line-directives` / `--no-line-directives` | off | Emit `#line` directives in generated C (aids debugger source mapping) |
| `-v`, `--version` | — | Print the McCode version and exit |


---

## Run commands

Compile and run an instrument simulation.

=== "McStas"

    ```bash
    mcrun-antlr [OPTIONS] INSTR_FILE [PARAM=VALUE(S) ...]
    ```

=== "McXtrace"

    ```bash
    mxrun-antlr [OPTIONS] INSTR_FILE [PARAM=VALUE(S) ...]
    ```

| Flag | Description |
|---|---|
| `INSTR_FILE` | `.instr` file to compile and run |
| `PARAM=VALUE(S)` | Instrument parameters — see [Parameter syntax](#parameter-syntax) below |
| `-o FILE`, `--output-file FILE` | Output path for the compiled binary |
| `-d DIR`, `--directory DIR` | Output directory for simulation results (must not already exist) |
| `-I DIR`, `--search-dir DIR` | Extra component search directory (repeatable) |
| `-n N`, `--ncount N` | Number of rays to simulate |
| `-s N`, `--seed N` | Random number generator seed |
| `-t` / `--trace` / `--no-trace` | Enable *trace* mode for instrument display |
| `--source` / `--no-source` | Embed the instrument source code in the binary |
| `--verbose` / `--no-verbose` | Verbose output |
| `-g`, `--gravitation` | Enable gravitation for all trajectories |
| `-m`, `--mesh` | Treat multiple scanned parameters as a multidimensional grid scan |
| `--bufsiz N` | `Monitor_nD` list/buffer size |
| `--format FORMAT` | Output data format |
| `--dryrun` | Print scan commands without running any simulations |
| `--parallel` | Use MPI multi-process parallelism |
| `--gpu` | Use GPU OpenACC parallelism |
| `--process-count N` | Number of MPI processes (default: system default) |
| `--copyright` | Print the McCode copyright statement and exit |
| `-v`, `--version` | Print the McCode version and exit |

### Parameter syntax

Each instrument parameter is given as `PARAM=VALUE(S)` after the filename.
The value determines whether this parameter is held constant or scanned:

| Syntax | Type | Example | Meaning |
|---|---|---|---|
| `PARAM=value` | Scalar | `E_i=5.0` | Single value; constant across all scan steps |
| `PARAM=start:stop` | Range (step=1) | `angle=10:20` | 11 steps from 10 to 20 inclusive |
| `PARAM=start:step:stop` | Range (explicit step) | `angle=10:2:20` | 6 steps: 10, 12, 14, 16, 18, 20 |
| `PARAM=v1,v2,v3,...` | Explicit list | `E_i=1.0,2.5,5.0` | Exactly those values, in order |

**1-D scan** (default): all ranged parameters must have the same number of points and are stepped together in lock-step. Scalar parameters keep their fixed value at every step.

```bash
mcrun-antlr my.instr -n 1e6 a=1.0 b=10:20 c=100:10:200
#                              ^fixed  ^11pts   ^11pts — stepped together
```

**N-D mesh scan** (`-m` / `--mesh`): all ranged parameters are combined as a full Cartesian product. A scan with lengths `[P, Q, R]` runs `P × Q × R` simulations.

```bash
mcrun-antlr my.instr -n 1e6 -m E_i=1:2:5 angle=0:5:90
#                                 ^3pts      ^19pts → 57 simulations total
```

---

## Compile-only commands

Compile a McCode instrument to a binary without running it.

=== "McStas"

    ```bash
    mcc-antlr [OPTIONS] FILENAME
    ```

=== "McXtrace"

    ```bash
    mxc-antlr [OPTIONS] FILENAME
    ```

Accepts `.instr`, `.json`, `.h5`, or pre-generated `.c` files.

| Flag | Default | Description |
|---|---|---|
| `FILENAME` | *(required)* | `.instr` / `.json` / `.h5` / `.c` file to compile |
| `-o OUTPUT`, `--output OUTPUT` | CWD | Output path for the compiled binary (file or directory) |
| `-I DIR`, `--search-dir DIR` | — | Extra component search directory (may be given more than once) |
| `-t` / `--trace` / `--no-trace` | on | Enable *trace* mode for instrument display |
| `--source` / `--no-source` | off | Embed the instrument source in the executable |
| `--verbose` / `--no-verbose` | off | Verbose compiler/linker output |
| `--parallel` | off | Use MPI multi-process parallelism |
| `--gpu` | off | Use GPU OpenACC parallelism |
| `--nexus` | off | Enable NeXus output support |
| `-c`, `--dump-source` | off | Keep the generated C source file alongside the binary |
| `-v`, `--version` | — | Print version and exit |


---

## Format command

### `mcfmt`

Format `.instr` and `.comp` McCode DSL source files in canonical style.

```bash
mcfmt [OPTIONS] FILE [FILE ...]
```

| Flag | Description |
|---|---|
| `FILE …` | One or more `.instr` or `.comp` files to format |
| `-i`, `--inplace` | Modify files in place instead of printing to stdout |
| `--check` | Exit non-zero if any file would be reformatted; writes nothing (useful as a CI gate) |
| `--diff` | Show a unified diff of proposed changes instead of formatted output |
| `--clang-format` | Also format C-code blocks (`%{ … %}`) using clang-format with the official McCode style (fetched via pooch) |
| `--clang-format-config PATH` | Format C-code blocks using clang-format with a given `.clang-format` config file |
| `--clang-format-style STYLE` | Format C-code blocks using clang-format with a named style (e.g. `"LLVM"`, `"Google"`, or an inline `"{BasedOnStyle: …}"` map) |

The output mode flags (`-i`, `--check`, `--diff`) are mutually exclusive; the default (none given) prints formatted output to stdout.

---

## Management command

### `mccode-antlr`

Top-level management utility for caches, configuration, and data files.

```bash
mccode-antlr SUBCOMMAND [OPTIONS]
```

| Subcommand | Description |
|---|---|
| `cache` | Manage the component file cache |
| `config` | Manage the mccode-antlr configuration |
| `datafile` | Work with McCode data files (Bragg tables, SQW files, …) |

---

#### `mccode-antlr cache`

| Sub-subcommand | Description |
|---|---|
| `list [name]` | List named caches or the versions of one cache (`-l` for long format) |
| `remove [name] [version]` | Remove a named cache or specific version (`-f` to skip confirmation) |
| `populate` | Bulk-populate pooch caches from a McCode git tag or local checkout |
| `ir-list` | List component IR cache files (`*.comp.json`) (`-l` for paths, sizes, stale status) |
| `ir-clean` | Delete component IR cache files (`--stale` for stale-only; `-f` to skip confirmation) |
| `ir-build` | Pre-build component IR cache files for all known registries |

**`cache populate` options:**

| Flag | Description |
|---|---|
| `--tag TAG` | McCode version tag (e.g. `v3.5.31`); defaults to the configured version |
| `--from-path PATH` | Use an existing local McCode checkout instead of cloning |
| `--clone-url URL` | Git URL to clone (used when `--from-path` is not given) |
| `--flavor {mcstas,mcxtrace,both}` | Which flavor's registries to populate (default: `both`) |

**`cache ir-build` options:**

| Flag | Description |
|---|---|
| `--flavor {mcstas,mcxtrace,both}` | Which flavor's registries to build IR for (default: `both`) |
| `-j N`, `--jobs N` | Number of parallel workers (default: `os.cpu_count()`) |
| `--force` | Rebuild even if `.comp.json` is already up-to-date |
| `--download` | Bulk-populate the pooch cache via git clone before building (faster than individual fetches) |
| `-R SPEC`, `--registry SPEC` | Extra registry to include (repeatable); same `SPEC` formats as `registry_from_specification` |

---

#### `mccode-antlr config`

| Sub-subcommand | Description |
|---|---|
| `list [regex]` | Print configuration values to stdout, optionally filtered by a regex on the key |
| `get [key]` | Retrieve one value by `.`-separated key (default: full config) |
| `set key value [path]` | Update or insert one configuration value |
| `unset key [path]` | Remove one configuration value |
| `save [path]` | Create or update the configuration file on disk |

---

#### `mccode-antlr datafile`

| Sub-subcommand | Description |
|---|---|
| `list` | List available data files for a flavor |
| `fetch` | Download a data file into the local Pooch cache (no copy to working directory) |
| `get` | Download a data file and copy it to a directory |

Run `mccode-antlr SUBCOMMAND ACTION -h` for the full option list of any individual action.

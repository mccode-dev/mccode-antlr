# Investigation: always use UTF-8 for text files (mccode-dev/mccode-antlr#364)

Issue #364 reports that mccode-antlr opens text files with the locale's default
encoding, which is cp1252 on most Western-European Windows installations up to
and including Python 3.14 ([PEP 686](https://peps.python.org/pep-0686/) only
makes UTF-8 the default in 3.15). UTF-8 McCode sources are then read either as
mojibake or not at all.

This branch measures how big the change is, prototypes it, and lists the
pitfalls. **Short version:** the change itself is small and mechanical, about
30 call sites in 17 files. Files fetched through pooch are the *easy* part,
because pooch only handles bytes and they are guaranteed UTF-8. The real risks
are elsewhere: (1) changing reads without also changing writes, (2) user files
that are *not* UTF-8, (3) a UTF-8 byte-order mark, (4) subprocess I/O, and
(5) how non-ASCII text ends up in the generated C (string-literal escaping and
MSVC's source charset).

## How this was measured

1. **Static search** for `open(`, `read_text`/`write_text`, `text=True` and
   friends in `src/`.
2. **Runtime audit:** the whole test suite run with
   `python -X warn_default_encoding -W always::EncodingWarning`. Each call that
   falls back to the locale encoding emits an `EncodingWarning` with its
   location. On `main` this flagged **23 sites in `src/mccode_antlr`**, about
   130 lines in `tests/`, and one third-party site (`parso`, pulled in by
   IPython). `pooch`, `confuse` and `antlr4` raised none: pooch already opens
   its registry files with `encoding="utf-8"`, and confuse reads YAML as bytes.
3. **Reproduction on Linux:** a child interpreter started with
   `LC_ALL=C PYTHONCOERCECLOCALE=0 PYTHONUTF8=0` has an ASCII locale encoding,
   so any non-ASCII text that relies on the default encoding raises. On
   `main`, loading `Lens_simple` from the McCode mcxtrace library this way gives
   `'ascii' codec can't decode byte 0xe2`. Translating an instrument that uses
   it gives `UnicodeEncodeError ... '\u207b'` when the generated C is written.
   This is now `tests/test_text_encoding.py`. On Windows the same test runs
   with the runner's real ANSI code page.
4. **The McCode library itself**, `mcstas-comps`, `mcxtrace-comps` and
   `mccode/*lib/share`, scanned at tag `v3.8.8` (the version CI pins) and at
   `main` (`2692f5b`).

## What the McCode sources contain (v3.8.8)

| | count |
|---|---|
| `.comp`/`.instr`/`.c`/`.h`/`.cl` files scanned | 1321 |
| not valid UTF-8 | **0** (same at `main`) |
| with a UTF-8 BOM | 0 |
| containing non-ASCII text | 99 |
| … that **fail** to decode as cp1252 (bytes 0x81/0x8D/0x8F/0x90/0x9D) | 5: `Lens_simple.comp`, `Single_crystal.comp` (mcxtrace), `Monochromator_bent.comp`, `He3_spin_filter.instr`, `SOLEIL_DIFFABS.instr` |
| … that decode as cp1252 to **silent mojibake** | 94 |
| … containing characters **not representable in cp1252** (Δ, λ, ≥, ⁻, ∗, …) | 18 |

`Monochromator_2foc.comp` contains a literal U+FFFD, left over from a lossy
conversion upstream. It is valid UTF-8, but it suggests that legacy-encoded
files existed in McCode's history.

## The call sites

All of these are changed in the prototype commit on this branch.

| Kind | Location | Change |
|---|---|---|
| **McCode sources** (`.instr`, `.comp`, `.c`) | `reader/registry.py` `Registry.contents` (all registries: local, pooch, git); `reader/reader.py` `%include`; `loader/loader.py` `load_mccode_instr`; `cli/cache.py` component warm-up; `compiler/c.py` `compile_c_file`; `translators/c_header.py` embedded instrument source | `read_source_text()`: UTF-8, with BOM stripped and a legacy fallback (see pitfalls 2 and 3) |
| **Generated output** | `translators/target.py` `save` (the C file); `compiler/c.py` Windows `.c` and `--source` dump; `instr/instr.py` `to_files`; `cli/convert.py`; `io/python.py` (the generated Python *must* be UTF-8, see PEP 3120) | `encoding='utf-8'` |
| **Caches and indexes** | `reader/registry.py` pooch registry index and remote-tags JSON; `translators/c_listener.py` typedef cache; `cli/cache.py` `cache register` output | `encoding='utf-8'` (current contents are ASCII, so they stay compatible) |
| **Configuration** | `config/__init__.py` package YAML ×2; `cli/management.py` user `config.yaml` ×3 | `encoding='utf-8'` |
| **McCode runtime output** | `loader/datfile.py`, `loader/simfile.py` | read: `encoding='utf-8', errors='replace'`; write: `encoding='utf-8'` |
| **Subprocess stdin/stdout** | `compiler/c.py` `linux_compile` (C source → gcc stdin); `format/format.py` (clang-format) | `encoding='utf-8'` (plus `errors='replace'` for compiler messages) |
| Build-time only | `src/grammar/builder.py` | `encoding='utf-8'` |

Not changed (deliberately): `bytes.decode()` calls already default to UTF-8,
whatever the locale; `utils.py` `run(..., text=True)` reads other programs'
console output, which really is in the locale/OEM code page (see pitfall 6);
and every place that already reads or writes bytes (`pooch.fetch`, component
JSON sidecars, `io/portable.py`, `io/extract.py`, `InMemoryRegistry`, which
already requires UTF-8).

## Pitfalls

### 1. pooch-fetched components: safe, and the main beneficiary

* pooch downloads, hashes (`sha256` of the bytes) and stores files **as
  bytes**. Changing how mccode-antlr *decodes* a cached file cannot affect hash
  checks, cache paths or re-downloads.
* The cached files are byte-for-byte copies of the McCode repository, and all
  of them are valid UTF-8 (see the table above). So UTF-8 is unambiguously
  correct for them. The fallback in pitfall 2 is never triggered.
* The registry index files (`*-registry.txt`) are ASCII. pooch's own
  `load_registry` already uses `encoding="utf-8"`. When mccode-antlr fetches an
  index itself it uses `requests`' `r.text`, which takes the charset from the
  HTTP header (`text/plain; charset=utf-8` on raw.githubusercontent.com).
* Line endings are the one byte-level trap near pooch, and they are already
  handled: `cache populate` clones with `-c core.autocrlf=false`, so the hashes
  of the copied files match. (`cache populate --from-path` with a user's *own*
  Windows checkout made with `autocrlf=true` will still fail the hash check.
  That is unrelated to this change, but it will come up in the same bug
  reports.)

### 2. Changing reads without writes makes things *worse*

On a cp1252 system today, a UTF-8 file is decoded to mojibake. If nothing in
between alters it, the mojibake is encoded back to cp1252 on write, which
reproduces the original UTF-8 bytes, because cp1252 maps the bytes involved
one-to-one. So, by accident, the generated C for 94 of the 99 non-ASCII McCode
files is correct on Windows today. Only the 5 files with undefined cp1252 bytes
fail.

If reads switch to UTF-8 but writes stay on the locale, the text is now
*correct* Unicode, and writing it as cp1252 **raises** for the 18 files with
characters cp1252 lacks (e.g. `Lens_simple.comp`'s `AA⁻1`, `union-lib.c`).
Reads and writes must change together. The test on this branch checks the
whole round trip.

### 3. User files that are not UTF-8

Users' own `.instr`/`.comp` files may be in a legacy code page: Notepad saved
"ANSI" by default before Windows 10 1903, and so do many older editors.
Today those *work* on the machine that wrote them, because both sides use the
same code page. A strict UTF-8 read would turn that into a
`UnicodeDecodeError`, which is a regression for exactly the users the issue is
meant to help.

The prototype's `common/encoding.py:decode_source` tries, in order:
1. `utf-8-sig`
2. the legacy locale encoding (`locale.getencoding()`, which ignores UTF-8
   mode, so it stays meaningful on 3.15), with a warning naming the file
3. UTF-8 with replacement characters, also with a warning

`errors='surrogateescape'` looks attractive because it round-trips the
original bytes, but it is a trap here. The decoded text is later
`.encode('utf-8')`-ed for digests (`instr/digest.py`, `c_listener.py`) and
serialised by msgspec, and both **raise** on lone surrogates.

### 4. Byte-order marks

The McCode grammar has no token for U+FEFF. A file saved as "UTF-8 with BOM"
(the meaning of "UTF-8" in older Notepad) fails today **on every platform**
with `token recognition error at: '\ufeff'`. Reading with `utf-8-sig` fixes
this for free. Decoding with plain `'utf-8'` would quietly keep the bug.

### 5. Caches that hold decoded text

* Component IR sidecars (`*.comp` → JSON, `reader/reader.py`) store *parsed*
  components. On Windows, ones written before the fix hold mojibake. Their key
  includes the package version, so a release invalidates them. The prototype
  also bumps `_COMPONENT_CACHE_FORMAT` (2 → 3) for editable/dev installs.
  While testing, a warm sidecar cache hid the read-side bug completely: only the
  write failed.
* Other on-disk caches (typedef JSON, remote tags, pooch index) are written
  with `json.dump`'s default `ensure_ascii=True` or contain only paths and
  hashes. They are ASCII, so old and new versions can read each other's files.
* User `config.yaml`: `config_dump` uses `yaml.dump`'s default
  `allow_unicode=False`, so files written by mccode-antlr are ASCII and stay
  compatible. However, confuse *already* reads `config.yaml` as bytes, letting
  YAML detect the encoding (UTF-8), while `cli/management.py` read it with the
  locale encoding. A hand-edited, UTF-8 config with a non-ASCII path
  (`C:\Users\Jürgen\...`) was therefore read correctly by confuse, but garbled
  and written back escaped by `mccode-antlr config set`. The change fixes this
  inconsistency.

### 6. Subprocesses: don't blanket-replace `text=True`

* **Input we produce** (C source to `gcc -`, blocks to `clang-format`) should
  be UTF-8. Both tools assume UTF-8 input. With `text=True` this used the
  locale and would fail or garble non-ASCII on Windows.
* **Output of other programs** is in *their* encoding: the locale on POSIX,
  often the OEM code page (cp437/cp850) for Windows console programs.
  Compiler diagnostics are now decoded with `errors='replace'`.
  `simulation.py` uses `stdout.decode()`, i.e. strict UTF-8, and can already
  raise on a Windows path with non-ASCII characters in McCode output. It was
  left alone here, but `errors='replace'` is advisable.
* PEP 686 makes `text=True` UTF-8 on Python 3.15, so code that currently works
  by decoding console output with the locale will change behaviour then.
  Setting `errors=` explicitly everywhere now avoids surprises later.

### 7. McCode runtime output files (`.dat`, `.sim`, `mccode.dat`)

The C runtime copies instrument text, which is UTF-8 if the generated C is,
into the headers. It also writes paths and `getcwd()` results, which on
Windows are in the **ANSI code page**. One file can therefore contain *both*
encodings, so a strict UTF-8 read can fail where the cp1252 read used to
"work". The prototype reads these with `errors='replace'`, because only the
numeric data and the ASCII keys matter.

### 8. What the C compiler does with the UTF-8 we write

* **gcc/clang** assume UTF-8 source and copy it into narrow string literals
  unchanged.
* **MSVC** (`cl.exe`, the configured Windows compiler) reads a BOM-less file in
  the **ANSI code page** unless given `/utf-8`. On cp1252 that is harmless: the
  bytes pass through to string literals unchanged, just as they do today. On
  CJK code pages (932/936/949/950), multi-byte UTF-8 sequences can swallow the
  following newline or quote, so a `//` comment can eat the next line, and
  MSVC warns C4819. **Recommendation:** add `/utf-8` to `Windows.flags.cc` in
  `config/platforms.yaml` (VS2015 Update 2 and later). This is not in the
  prototype because it needs testing on a Windows machine.
* **`escape_str_for_c`** (`common/utilities.py`, used for the embedded
  instrument source and other strings copied into C literals) uses Python's
  `unicode-escape`. That produces `\xNN` (a **Latin-1** byte) for U+0080–U+00FF,
  but `\uXXXX` (UTF-8 in the binary) for everything else, so one string ends up
  in mixed encodings. A `\x` escape also absorbs any hex digits that follow it:
  `'Débye'` becomes `"D\xe9bye"`, and gcc reports *hex escape sequence out of
  range*. This is a pre-existing bug on all platforms, but it becomes more
  visible on Windows once text decodes correctly. Fix: `s.encode('utf-8')`
  and emit `\ooo` octal escapes for bytes ≥ 0x80. Not in the prototype,
  because it changes the generated C for every non-ASCII string.

### 9. Smaller things worth knowing

* **Newlines.** Text mode still writes `\r\n` on Windows. MSVC accepts that,
  but `cache register` will mint registry files with CRLF, and any digest of
  written files will differ by platform. If that matters, pass `newline='\n'`
  as well. This is a separate decision.
* **Console and pipe output.** `print()` of component documentation containing
  Δ to a *redirected* stdout on Windows still uses cp1252 and can raise. Until
  Python 3.15, the user-side workaround is `PYTHONUTF8=1` (or
  `PYTHONIOENCODING=utf-8`). The same `PYTHONUTF8=1` setting is also an
  immediate workaround for the whole issue.
* **Digests.** `instr/digest.py` hashes the *decoded* text. On Windows these
  digests will change once, and then match Linux. The effect is one rebuild
  per instrument.
* **Windows CI was already green.** The existing tests contain no non-ASCII
  sources, so mojibake was never noticed. `tests/test_text_encoding.py` closes
  that gap on every platform.

## Keeping it fixed

* In CI, set `PYTHONWARNDEFAULTENCODING=1` and add
  `filterwarnings = ["error::EncodingWarning:mccode_antlr"]` to the pytest
  configuration. Scoping the filter to the `mccode_antlr` module ignores the
  ~130 test-code lines, which only use ASCII, and `parso`. The prototype
  passes the full suite under exactly that filter. Converting the tests as well
  would allow a global `error::EncodingWarning`.
* Optionally enable ruff's `PLW1514` (unspecified-encoding) for a static check.

## Prototype status

The second commit on this branch makes all the changes in the call-site table
and adds `src/mccode_antlr/common/encoding.py` and
`tests/test_text_encoding.py`. Not done: MSVC `/utf-8`, `escape_str_for_c`,
`simulation.py` `errors='replace'`, `newline=` policy, and converting the test
suite's own `open()` calls.

"""Build information recorded inside a compiled instrument binary.

A compiled McCode binary should be able to say what it is without being run. This
module writes that statement into the generated C as an ordinary instrument-level
METADATA entry (mimetype ``application/json``), and reads it back out of a binary
by scanning for it.

The MPI/OpenACC/NeXus fields are *not* written by Python. They are spliced by the
C preprocessor from the same ``-DUSE_MPI`` / ``-DOPENACC`` / ``-DUSE_NEXUS`` flags
that decide whether the corresponding code is compiled in at all, using adjacent
string-literal concatenation. That keeps the record honest when a `.c` translated
for one target is later compiled for another::

    mcstas-antlr foo.instr -o foo.c   # target not yet decided
    mcc-antlr --parallel foo.c        # binary records "mpi": true

Because the entry lands in the normal ``metadata_table[]``, the compiled binary
answers ``--meta-data <instrument>:mccode_antlr_build`` with no runtime changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from loguru import logger

#: Name of the metadata entry. Must contain no ':' (the runtime splits keys on it)
#: and no space (a spaced name is re-quoted upstream, producing invalid C).
BUILD_INFO_NAME = 'mccode_antlr_build'
BUILD_INFO_MIMETYPE = 'application/json'

#: Schema version, and the first key of the payload so that it doubles as the
#: byte pattern to scan a binary for.
BUILD_INFO_SCHEMA = 1
MAGIC_KEY = 'mccode_antlr_build_info'
MAGIC = b'{"' + MAGIC_KEY.encode('ascii') + b'":'

_MPI_MACRO = 'MCCODE_ANTLR_BUILD_MPI'
_ACC_MACRO = 'MCCODE_ANTLR_BUILD_ACC'
_NEXUS_MACRO = 'MCCODE_ANTLR_BUILD_NEXUS'

#: Emitted by the McCode runtime under #ifdef USE_MPI / #ifdef OPENACC
#: (mccode-r.c). Being preprocessor-gated makes them sound markers for a binary
#: that carries no build-info entry -- including one built by classic mcstas.
HELP_MPI = b'This instrument has been compiled with MPI support.'
HELP_ACC = b'This instrument has been compiled with NVIDIA GPU support through OpenACC.'

#: Binary-name tags for each target combination, longest first so that stripping
#: a tag off a stem cannot leave a fragment behind.
TARGET_TAGS = ('mpiacc', 'mpi', 'acc')


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #

def build_info_macros() -> str:
    """The #ifdef-derived macros used by :func:`build_info_c_row`.

    Must be emitted before the DECLARE section that contains the metadata table.
    """
    def one(macro: str, guard: str) -> str:
        return (f'#ifdef {guard}\n'
                f'#  define {macro} "true"\n'
                f'#else\n'
                f'#  define {macro} "false"\n'
                f'#endif')

    return '\n'.join([
        '/* Build information: the recorded target is decided by the same -D flags',
        ' * that compile the MPI/OpenACC/NeXus code in, so a .c translated for one',
        ' * target and compiled for another still records the truth. */',
        one(_MPI_MACRO, 'USE_MPI'),
        one(_ACC_MACRO, 'OPENACC'),
        one(_NEXUS_MACRO, 'USE_NEXUS'),
    ])


def build_info_payload(source, flavor, config: dict) -> dict:
    """The Python-written half of the payload.

    ``mpi``, ``acc`` and ``nexus`` are absent here; they are appended by the
    preprocessor in :func:`build_info_c_row`.
    """
    from mccode_antlr.version import version
    from mccode_antlr.instr.digest import instrument_digest

    try:
        from mccode_antlr.reader.registry import mccode_registry_version
        mccode_version = str(mccode_registry_version())
    except Exception as error:  # offline, cold cache, ...
        logger.debug(f'Could not determine the McCode runtime version: {error}')
        mccode_version = None

    return {
        MAGIC_KEY: BUILD_INFO_SCHEMA,
        'generator': 'mccode-antlr',
        'generator_version': version(),
        'flavor': str(flavor).lower() if flavor is not None else None,
        'mccode_version': mccode_version,
        'instrument': source.name,
        'instrument_source': source.source,
        'source_hash': instrument_digest(source),
        'trace': bool(config.get('enable_trace')),
        'embed_source': bool(config.get('embed_instrument_file')),
        'default_main': bool(config.get('default_main')),
        'portable': bool(config.get('portable')),
        'runtime_embedded': bool(config.get('include_runtime')),
    }


def build_info_c_row(source, flavor, config: dict) -> str:
    """A complete ``metadata_table[]`` initializer line, ready to emit verbatim.

    The value is assembled from escaped Python-written fragments and bare macro
    names, relying on C adjacent string-literal concatenation.
    """
    import json
    from mccode_antlr.common.utilities import escape_str_for_c

    # ensure_ascii=True (the default) matters: escape_str_for_c runs
    # 'unicode-escape', which turns a raw non-ASCII byte into \xNN -- a greedy C
    # hex escape that would swallow the following hex digit. Keep this ASCII.
    head = json.dumps(build_info_payload(source, flavor, config),
                      separators=(',', ':'), ensure_ascii=True)
    if not (head.startswith('{') and head.endswith('}')):
        raise RuntimeError(f'Unexpected build-info payload encoding: {head[:40]}...')

    def literal(text: str) -> str:
        return '"' + escape_str_for_c(text) + '"'

    value = ' '.join([
        literal(head[:-1] + ',"mpi":'), _MPI_MACRO,
        literal(',"acc":'), _ACC_MACRO,
        literal(',"nexus":'), _NEXUS_MACRO,
        literal('}'),
    ])
    return f' {{"{source.name}", "{BUILD_INFO_NAME}", "{BUILD_INFO_MIMETYPE}", {value}}}, '


def expected_build_info(instr, flavor, config: dict, target=None) -> dict:
    """The payload a freshly compiled binary would carry, for cache comparison."""
    expected = build_info_payload(instr, flavor, config)
    if target is not None:
        from mccode_antlr.compiler.c import CBinaryTarget
        expected['mpi'] = bool(target.type & CBinaryTarget.Type.mpi)
        expected['acc'] = bool(target.type & CBinaryTarget.Type.acc)
        expected['nexus'] = bool(target.type & CBinaryTarget.Type.nexus)
    return expected


# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class BinaryProbe:
    """What could be determined about a compiled binary without trusting its name."""
    mpi: bool | None = None
    acc: bool | None = None
    nexus: bool | None = None
    info: dict | None = None
    origin: str = 'unknown'  # 'metadata' | 'help-strings' | 'exec-help' | 'unknown'

    @property
    def known(self) -> bool:
        return self.mpi is not None and self.acc is not None


def parse_build_info(blob: bytes) -> dict | None:
    """Extract the build-info payload from *blob*, or None if it carries none."""
    import json

    candidates = []
    start = blob.find(MAGIC)
    while start != -1:
        end = blob.find(b'}', start)
        if end != -1:
            try:
                found = json.loads(blob[start:end + 1].decode('utf-8'))
            except (ValueError, UnicodeDecodeError):
                found = None
            # Require the shape we write, so that an instrument which merely
            # quotes the magic (e.g. embedded via --source) is not mistaken for
            # a real entry.
            if (isinstance(found, dict) and found.get('generator') == 'mccode-antlr'
                    and 'source_hash' in found and found not in candidates):
                candidates.append(found)
        start = blob.find(MAGIC, start + len(MAGIC))

    if not candidates:
        return None
    if len(candidates) > 1:
        names = ', '.join(repr(c.get('instrument')) for c in candidates)
        logger.warning(f'Multiple build-info entries found ({names}); using the first')
    return candidates[0]


def read_build_info(binary: str | Path) -> dict | None:
    """Read the build-info payload out of a compiled binary, without running it."""
    import mmap
    try:
        with open(binary, 'rb') as file:
            with mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as blob:
                return parse_build_info(blob)
    except (IOError, OSError, ValueError) as error:
        logger.debug(f'Could not read build information from {binary}: {error}')
        return None


def _scan_help_markers(binary: Path) -> tuple[bool, bool] | None:
    import mmap
    try:
        with open(binary, 'rb') as file:
            with mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as blob:
                return blob.find(HELP_MPI) != -1, blob.find(HELP_ACC) != -1
    except (IOError, OSError, ValueError):
        return None


def _exec_help_markers(binary: Path, timeout: float = 30) -> tuple[bool, bool] | None:
    from subprocess import run, SubprocessError
    try:
        # mcshowhelp writes to stderr and exits 0, so a zero return code is not
        # evidence of anything; search both streams.
        result = run([str(Path(binary).resolve()), '--help'],
                     capture_output=True, timeout=timeout)
    except (OSError, SubprocessError) as error:
        logger.debug(f'Could not run {binary} --help: {error}')
        return None
    output = (result.stdout or b'') + (result.stderr or b'')
    if not output:
        return None
    return HELP_MPI in output, HELP_ACC in output


def probe_binary(binary: str | Path, *, allow_exec: bool = True) -> BinaryProbe:
    """Determine what a compiled binary was built with, strongest evidence first.

    1. the build-info metadata entry this module writes (exact, and complete)
    2. the preprocessor-gated help strings in the McCode runtime (exact for
       MPI/OpenACC; also works on binaries built by classic ``mcstas``)
    3. running ``binary --help`` and looking for the same strings
    4. nothing -- every field stays None, and callers must not invent one

    Deliberately absent: scanning for ``MPI_Init``/``acc_init`` symbol names. Those
    appear in any binary that merely *mentions* them -- e.g. a serial binary built
    with ``--source`` whose embedded instrument text contains an ``#ifdef USE_MPI``
    block -- and misreading that as an MPI binary is what this replaces.
    """
    binary = Path(binary)

    info = read_build_info(binary)
    if info is not None:
        return BinaryProbe(mpi=bool(info.get('mpi')), acc=bool(info.get('acc')),
                           nexus=bool(info.get('nexus')), info=info, origin='metadata')

    markers = _scan_help_markers(binary)
    if markers is not None and any(markers):
        return BinaryProbe(mpi=markers[0], acc=markers[1], origin='help-strings')

    if allow_exec:
        markers = _exec_help_markers(binary)
        if markers is not None:
            return BinaryProbe(mpi=markers[0], acc=markers[1], origin='exec-help')

    # A binary with neither marker is *probably* serial, but 'probably' is what
    # caused the bug this replaces; say nothing and let the caller decide.
    return BinaryProbe()


def query_binary_metadata(binary: str | Path, name: str, source: str) -> str | None:
    """Ask a compiled binary for one metadata entry via ``--meta-data``.

    Returns None when the binary does not define it. This is the authoritative
    reading, at the cost of running the binary.
    """
    from subprocess import run, SubprocessError
    if ':' in source or ':' in name:
        raise ValueError(f"Metadata keys cannot contain ':' (got {source!r}:{name!r})")
    try:
        result = run([str(Path(binary).resolve()), '--meta-data', f'{source}:{name}'],
                     capture_output=True, timeout=30)
    except (OSError, SubprocessError) as error:
        logger.debug(f'Could not query metadata from {binary}: {error}')
        return None
    if result.returncode:
        return None
    return result.stdout.decode('utf-8').rstrip('\n')


# --------------------------------------------------------------------------- #
# Cache comparison
# --------------------------------------------------------------------------- #

#: Payload keys which must match exactly for a cached binary to be reused.
CACHE_KEYS = (
    MAGIC_KEY, 'generator_version', 'flavor', 'mccode_version', 'instrument',
    'source_hash', 'trace', 'embed_source', 'default_main', 'portable',
    'runtime_embedded',
)


def build_info_matches(recorded: dict | None, expected: dict) -> tuple[bool, str]:
    """Whether a binary recording *recorded* can be reused for *expected*."""
    if recorded is None:
        return False, 'it carries no mccode-antlr build information'
    for key in CACHE_KEYS:
        want = expected.get(key)
        if key in expected and want is not None and recorded.get(key) != want:
            return False, f'{key} changed ({recorded.get(key)!r} -> {want!r})'
    # Asymmetric on purpose. An instrument whose DEPENDENCY flags carry -DUSE_MPI
    # honestly records mpi=true even for a nominally serial request; demanding
    # equality there would rebuild on every single run, forever. Requiring only
    # that what was asked for is present terminates, and the target-tagged
    # filenames already keep genuine target switches in separate files.
    for key in ('mpi', 'acc', 'nexus'):
        if expected.get(key) and not recorded.get(key):
            return False, f'{key} support was requested but is not present'
    return True, ''

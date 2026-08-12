"""Capture the local files an instrument needs, so a serialized one is portable.

Component *definitions* already travel: a Comp is parsed into Instr.components and
serialized in full, so a saved instrument reloads its components with no registry
involved. What does not travel is everything never parsed into the Instr --
%include'd headers and .c library files, share libraries, and data files. Those
are resolved from a registry at *translation* time, so an instrument saved on one
machine and translated on another fails with, e.g.

    RuntimeError: mylib.h not found in registries: libc,mcstas

This module finds those files at save time and packs the ones that came from a
LocalRegistry into an InMemoryRegistry, which serializes with the instrument.
Files from remote registries are left alone: they are already reachable anywhere
by name and content hash, and copying them would bloat every artifact.
"""
from __future__ import annotations

from loguru import logger

from mccode_antlr.reader.registry import (
    InMemoryRegistry, LocalRegistry, Registry,
    REGISTRY_PRIORITY_MEDIUM, ordered_registries
)
from mccode_antlr.translators.includes import included_names, source_blocks

EMBEDDED_REGISTRY_NAME = 'embedded'


def _config_flag(name: str, default):
    from mccode_antlr.config import config
    key = config['serialization'][name]
    return key.get() if key.exists() else default


def _resolve(registries, name: str):
    """First registry that both claims and can deliver *name*, or None."""
    for reg in registries:
        try:
            if not reg.known(name):
                continue
            return reg, reg.path(name)
        except Exception:
            # A registry that knows a name but cannot produce it is not fatal
            # here; capture is best-effort and translation will report properly.
            continue
    return None, None


def _data_file_candidates(instr) -> list[str]:
    """String-valued component parameters that name a file.

    Mirrors the shape test in TargetVisitor.prefetch_data_files, but without its
    `data/` containment rule: that exists to avoid prefetching arbitrary strings
    from the *shipped* registries, whereas a locally supplied data file will not
    live under a directory called data.
    """
    from pathlib import Path
    names = []
    for instance in instr.components:
        for param in instance.parameters:
            value = param.value
            if not (value.is_str and value.has_value):
                continue
            raw = value.value
            if not isinstance(raw, str):
                continue
            name = raw.strip('"').strip("'")
            if not name or name in ('0', 'NULL') or not Path(name).suffix:
                continue
            names.append(name)
    return list(dict.fromkeys(names))


def _getpath_candidates(instr) -> list[str]:
    import re
    names = []
    for flag in instr.dependency:
        names.extend(re.findall(r'GETPATH\(\s*([^)\s]+)\s*\)', flag or ''))
    return [n for n in dict.fromkeys(names) if n]


def embedded_registry(instr, size_limit_mb: float | None = None) -> InMemoryRegistry | None:
    """Pack the local files *instr* needs into an InMemoryRegistry, or None.

    Resolution runs against every registry so a remote header that includes a
    local file is still found, but only files that land in a LocalRegistry are
    embedded. Names are followed transitively, since share libraries include
    further files.
    """
    registries = [r for r in ordered_registries(list(instr.registries))
                  if not isinstance(r, InMemoryRegistry)]
    if not any(isinstance(r, LocalRegistry) for r in registries):
        return None

    if size_limit_mb is None:
        size_limit_mb = _config_flag('embed_size_limit_mb', 32)
    budget = int(float(size_limit_mb) * 1024 * 1024)

    pending: list[str] = []
    for _, text in source_blocks(instr):
        libraries, files = included_names(text)
        for library in libraries:
            # The translator fetches {lib}.h, and {lib}.c too when embedding the
            # runtime, so both have to travel.
            pending.extend((f'{library}.h', f'{library}.c'))
        pending.extend(files)
    pending.extend(_data_file_candidates(instr))
    pending.extend(_getpath_candidates(instr))

    embedded, seen, total = {}, set(), 0
    while pending:
        name = pending.pop(0)
        if name in seen:
            continue
        seen.add(name)
        reg, path = _resolve(registries, name)
        if reg is None:
            # Missing, or supplied by a remote registry: either way not ours to
            # carry. A genuinely missing file is reported at translation time.
            continue
        if not isinstance(reg, LocalRegistry):
            continue
        try:
            payload = path.read_bytes()
        except OSError as error:
            logger.warning(f'Could not embed {name} from {reg.name!r}: {error}')
            continue
        if total + len(payload) > budget:
            logger.warning(
                f'Not embedding {name} ({len(payload)} bytes): the serialized instrument '
                f'would exceed serialization.embed_size_limit_mb ({size_limit_mb} MB). '
                'Raise the limit, or supply the directory with -I/--search-dir when loading.'
            )
            continue
        embedded[name] = payload
        total += len(payload)
        # Followed transitively: a share library may %include further files.
        try:
            libraries, files = included_names(payload.decode('utf-8'))
        except UnicodeDecodeError:
            continue
        for library in libraries:
            pending.extend((f'{library}.h', f'{library}.c'))
        pending.extend(files)

    if not embedded:
        return None
    # Below -I (10) and the configured component directories (5) so a loading
    # user's own search directory still wins, above the remote registries (-10).
    registry = InMemoryRegistry(EMBEDDED_REGISTRY_NAME, priority=REGISTRY_PRIORITY_MEDIUM)
    for name, payload in embedded.items():
        registry.add(name, payload)
    logger.debug(f'Embedded {len(embedded)} local file(s) ({total} bytes) in {instr.name}')
    return registry


def _is_embedded(reg) -> bool:
    return isinstance(reg, InMemoryRegistry) and reg.name == EMBEDDED_REGISTRY_NAME


def with_embedded_files(registries, instr) -> tuple[Registry, ...]:
    """Registries to serialize for *instr*: its own, plus captured local files.

    A LocalRegistry is still written out -- the trust gate decides on *load*
    whether to honor it -- but the embedded copy means a consumer that ignores
    it can still translate.

    Anything already embedded is carried forward and merged with a fresh capture,
    never replaced by it. Re-saving a *loaded* instrument would otherwise lose the
    files: its LocalRegistry entries were dropped on load, so there is nothing
    left to capture from, and a save/load/save cycle would silently strip the
    portability it had.
    """
    if not _config_flag('embed_local_files', True):
        return tuple(registries)
    others = tuple(r for r in registries if not _is_embedded(r))
    carried = [r for r in registries if _is_embedded(r)]
    captured = embedded_registry(instr)
    if captured is None and not carried:
        return others
    merged = InMemoryRegistry(EMBEDDED_REGISTRY_NAME, priority=REGISTRY_PRIORITY_MEDIUM)
    for previous in carried:
        for name, payload in previous.files.items():
            merged.add(name, payload)
    if captured is not None:
        # A file still reachable locally is re-read, so an edited local copy wins
        # over the stale one an earlier save carried.
        for name, payload in captured.files.items():
            merged.add(name, payload)
    return others + (merged,)

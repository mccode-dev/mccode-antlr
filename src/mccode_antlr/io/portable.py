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
    REGISTRY_PRIORITY_MEDIUM, ordered_registries, origin_label,
)
from mccode_antlr.translators.includes import included_names, source_blocks

EMBEDDED_REGISTRY_NAME = 'embedded'


def _config_flag(name: str, default):
    from mccode_antlr.config import config
    key = config['serialization'][name]
    return key.get() if key.exists() else default


def resolve_registry_and_path(registries, name: str):
    """First registry that both claims and can deliver *name*, or (None, None).

    Shared by the embedding logic below and by `io/extract.py`, which needs the
    same "which registry actually supplies this name" answer to classify a
    dependency as local or remote at extraction time. *name* is always a fully
    qualified filename (extension included), so `known` is checked with
    strict=True: without it, a registry's unanchored substring fallback (e.g.
    matching 'ESS_butterfly.comp' inside an unrelated 'Masked_ESS_butterfly.comp')
    can claim a name it doesn't actually have an exact file for.
    """
    for reg in registries:
        try:
            if not reg.known(name, strict=True):
                continue
            return reg, reg.path(name)
        except Exception:
            # A registry that knows a name but cannot produce it is not fatal
            # here; capture is best-effort and translation will report properly.
            continue
    return None, None


def deposit_embedded_data_files(instr, destination) -> list:
    """Write embedded data files where the *compiled binary* will look.

    Translation reaches an embedded file through reg.path(), which materializes it
    into a cache directory -- but the runtime's Open_File does not search there. It
    tries the name as given, then the instrument source directory, then the
    executable's directory, then $HOME, then $FLAVOR/data and $FLAVOR/contrib.
    Rewriting the parameter to the cache path would work, but only by baking a
    machine-specific absolute path into the generated C -- exactly the portability
    problem this is meant to solve. So the file is placed beside the generated C
    (for a translate-only run) and beside the binary (when compiling), both of
    which the runtime searches.

    Only files an instrument *parameter* names are deposited: the rest of an
    embedded registry is headers and libraries, compiled in and never opened at
    run time.
    """
    from pathlib import Path
    embedded = [reg for reg in (instr.registries or []) if isinstance(reg, InMemoryRegistry)]
    if not embedded or destination is None:
        return []
    wanted = set(_data_file_candidates(instr))
    written = []
    for reg in embedded:
        for name in reg.filenames():
            if name not in wanted:
                continue
            target = Path(destination) / Path(name).name
            payload = reg.contents_bytes(name)
            if target.exists():
                if target.read_bytes() != payload:
                    logger.warning(
                        f'{instr.name}: not overwriting {target}, which differs from the copy '
                        'embedded in the instrument; the existing file will be used'
                    )
                continue
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)
            except OSError as error:
                logger.warning(f'{instr.name}: could not write {target}: {error}')
                continue
            logger.info(f'{instr.name}: deposited embedded data file {name!r} -> {target}')
            written.append(target)
    return written


def deposit_all_embedded_files(instr, destination) -> list:
    """Write every embedded/stashed file to *destination*, flat (basename only).

    Unlike `deposit_embedded_data_files`, which only writes files an instrument
    parameter names (so the compiled binary can find them at runtime), this
    writes the full contents of every InMemoryRegistry on the instrument --
    headers and libraries as well as data files -- for `io/extract.py`, which
    wants a complete, inspectable bundle rather than just what a compiled
    binary needs.
    """
    from pathlib import Path
    embedded = [reg for reg in (instr.registries or []) if isinstance(reg, InMemoryRegistry)]
    if not embedded or destination is None:
        return []
    written = []
    for reg in embedded:
        for name in reg.filenames():
            target = Path(destination) / Path(name).name
            payload = reg.contents_bytes(name)
            if target.exists():
                if target.read_bytes() != payload:
                    logger.warning(
                        f'{instr.name}: not overwriting {target}, which differs from the copy '
                        f'embedded in the instrument as {name!r}; the existing file will be used'
                    )
                continue
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)
            except OSError as error:
                logger.warning(f'{instr.name}: could not write {target}: {error}')
                continue
            logger.info(f'{instr.name}: deposited embedded file {name!r} -> {target}')
            written.append(target)
    return written


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


def collect_dependency_payloads(instr, registries, accept, budget: int | None = None):
    """BFS over the %include/data-file/GETPATH names *instr* depends on.

    Resolution runs against every registry so a remote header that includes a
    local file is still found, but a name is only read (and, transitively,
    followed into further %includes -- share libraries include further files)
    when ``accept(registry)`` is true for whichever registry resolved it.
    Everything else is left alone.

    Shared by `embedded_registry` (accept=LocalRegistry only, budget-limited,
    feeds the serialized-JSON embedding feature) and `io/extract.py`'s
    dependency writer (accept configurable via --include-remote, unbounded).

    Returns (payloads, origins, unresolved_include_names). `origins` maps each
    accepted name to `origin_label(reg)` for the registry that supplied it.
    Names are tracked with their provenance: only %include names are hard
    requirements -- the translator fails outright on one it cannot resolve.
    Data file and GETPATH names are heuristic guesses (filename="D0_Source.psd"
    names an *output*), so an unresolved one means nothing and must not be
    reported.
    """
    pending: list[tuple[str, str]] = []

    def queue_includes(text: str):
        libraries, files = included_names(text)
        for library in libraries:
            # A bare name is a library: the translator fetches {lib}.h, and
            # {lib}.c too when embedding the runtime, so both have to travel.
            # Only the header is required to exist.
            pending.append((f'{library}.h', 'include'))
            pending.append((f'{library}.c', 'optional'))
        pending.extend((name, 'include') for name in files)

    for _, text in source_blocks(instr):
        queue_includes(text)
    pending.extend((name, 'optional') for name in _data_file_candidates(instr))
    pending.extend((name, 'optional') for name in _getpath_candidates(instr))

    payloads, origins, seen, total, unresolved = {}, {}, set(), 0, []
    while pending:
        name, kind = pending.pop(0)
        if name in seen:
            continue
        seen.add(name)
        reg, path = resolve_registry_and_path(registries, name)
        if reg is None:
            if kind == 'include':
                unresolved.append(name)
            continue
        if not accept(reg):
            continue
        try:
            payload = path.read_bytes()
        except OSError as error:
            logger.warning(f'Could not read {name} from {reg.name!r}: {error}')
            continue
        if budget is not None and total + len(payload) > budget:
            logger.warning(
                f'Not embedding {name} ({len(payload)} bytes): the serialized instrument '
                f'would exceed serialization.embed_size_limit_mb ({budget / 1024 / 1024:.0f} MB). '
                'Raise the limit, or supply the directory with -I/--search-dir when loading.'
            )
            continue
        payloads[name] = payload
        origins[name] = origin_label(reg)
        total += len(payload)
        # Followed transitively: a share library may %include further files.
        try:
            queue_includes(payload.decode('utf-8'))
        except UnicodeDecodeError:
            pass

    return payloads, origins, unresolved


def embedded_registry(instr, size_limit_mb: float | None = None) -> InMemoryRegistry | None:
    """Pack the local files *instr* needs into an InMemoryRegistry, or None."""
    registries = [r for r in ordered_registries(list(instr.registries))
                  if not isinstance(r, InMemoryRegistry)]
    if not any(isinstance(r, LocalRegistry) for r in registries):
        return None

    if size_limit_mb is None:
        size_limit_mb = _config_flag('embed_size_limit_mb', 32)
    budget = int(float(size_limit_mb) * 1024 * 1024)

    embedded, origins, unresolved = collect_dependency_payloads(
        instr, registries, accept=lambda reg: isinstance(reg, LocalRegistry), budget=budget,
    )

    if unresolved:
        # Not an error: saving an instrument that does not yet translate is
        # legitimate, and the file may appear before it is translated. But the
        # alternative to saying so here is a failure much later, possibly on
        # someone else's machine.
        listed = ', '.join(sorted(unresolved))
        logger.warning(
            f'{instr.name}: %include of {listed} could not be resolved, so '
            f'{"they were" if len(unresolved) > 1 else "it was"} not embedded. '
            'Translating this instrument will fail unless the file is available '
            'wherever it is translated.'
        )

    if not embedded:
        return None
    # Below -I (10) and the configured component directories (5) so a loading
    # user's own search directory still wins, above the remote registries (-10).
    registry = InMemoryRegistry(EMBEDDED_REGISTRY_NAME, priority=REGISTRY_PRIORITY_MEDIUM)
    for name, payload in embedded.items():
        registry.add(name, payload, origin=origins.get(name))
    total = sum(len(v) for v in embedded.values())
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
            merged.add(name, payload, origin=previous.origins.get(name))
    if captured is not None:
        # A file still reachable locally is re-read, so an edited local copy wins
        # over the stale one an earlier save carried.
        for name, payload in captured.files.items():
            merged.add(name, payload, origin=captured.origins.get(name))
    return others + (merged,)

"""Reconstitute a portable Instr (loaded from .instr or .json) into a directory.

Writes the .instr hierarchy, every stashed/embedded file, and the component
definitions the instrument needs -- everything flat in one directory, so the
result is directly usable (e.g. `mcstas-antlr <name>.instr`) with no
-I/--search-dir. `%include` and component-name resolution both search by bare
filename, and `collect_local_registries` already adds an implicitly
non-recursive LocalRegistry for the current working directory, so a flat
layout is what makes that work without extra flags.

By default only "held" component definitions and dependency files are written:
ones not otherwise available from a remote registry, since those are already
fetchable elsewhere by name and content hash (mirroring the local-vs-remote
split `io/portable.py` uses for the embedding feature). Pass
include_remote=True for a fully self-contained bundle that also reconstructs
everything a remote registry would otherwise supply.
"""
from __future__ import annotations

from pathlib import Path

from loguru import logger

from mccode_antlr.reader.registry import (
    InMemoryRegistry, RemoteRegistry, ordered_registries,
)
from mccode_antlr.io.portable import (
    collect_dependency_payloads, deposit_all_embedded_files, resolve_registry_and_path,
)


def _is_remote(reg) -> bool:
    return isinstance(reg, RemoteRegistry)


def _write_flat(instr, directory: Path, name: str, payload: bytes) -> Path | None:
    target = directory / Path(name).name
    if target.exists():
        if target.read_bytes() != payload:
            logger.warning(
                f'{instr.name}: not overwriting {target}, which differs from the '
                f'copy resolved for {name!r}; the existing file will be used'
            )
        return None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    except OSError as error:
        logger.warning(f'{instr.name}: could not write {target}: {error}')
        return None
    return target


def _non_embedded_registries(instr):
    return [r for r in ordered_registries(list(instr.registries or []))
            if not isinstance(r, InMemoryRegistry)]


def write_component_definitions(instr, directory: Path, include_remote: bool = False) -> list[Path]:
    """Write one <name>.comp file per unique component type *instr* uses.

    Reconstructed from the parsed `Comp` (always fully present, regardless of
    where it came from) via `Comp.to_string()`. Classification of a component
    as local/held vs. remote is done by re-resolving its name against
    `instr.registries`, since a `Comp` carries no provenance of its own.
    """
    registries = _non_embedded_registries(instr)
    seen: set[str] = set()
    written = []
    for instance in instr.components:
        comp = instance.type
        if comp.name in seen:
            continue
        seen.add(comp.name)
        reg, _path = resolve_registry_and_path(registries, f'{comp.name}.comp')
        if reg is not None and _is_remote(reg) and not include_remote:
            continue
        target = _write_flat(instr, directory, f'{comp.name}.comp', comp.to_string().encode('utf-8'))
        if target is not None:
            written.append(target)
    return written


def write_dependency_files(instr, directory: Path, include_remote: bool = False) -> list[Path]:
    """Resolve and write %include headers/libraries, data files, and GETPATH targets.

    Runs the same dependency traversal `embedded_registry` uses to decide what
    to embed in a serialized JSON, but writes results straight to disk instead,
    with no size budget, and (with include_remote=True) also accepting names
    resolved from a remote registry.
    """
    registries = _non_embedded_registries(instr)
    if not registries:
        return []
    accept = (lambda reg: True) if include_remote else (lambda reg: not _is_remote(reg))
    payloads, _unresolved = collect_dependency_payloads(instr, registries, accept=accept, budget=None)
    written = []
    for name, payload in payloads.items():
        target = _write_flat(instr, directory, name, payload)
        if target is not None:
            written.append(target)
    return written


def extract_to_directory(instr, directory, include_remote: bool = False) -> Path:
    """Reconstitute *instr* into *directory*: .instr hierarchy, stashed files,
    and component definitions, all flat.

    With include_remote=False (default) only files not otherwise available
    from a remote registry are written -- what a consumer could not get any
    other way. With include_remote=True, remote-sourced component definitions
    and dependency files are written too, for a fully self-contained bundle.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    instr.to_files(directory)
    deposit_all_embedded_files(instr, directory)
    write_dependency_files(instr, directory, include_remote)
    write_component_definitions(instr, directory, include_remote)
    return directory

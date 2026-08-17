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

`build_manifest`/`select_members` split "what could be written" from "what a
given call actually writes", so `mccode_antlr.cli.extract`'s --list can preview
exactly what a real run (with the same include_remote/select/exclude) would
produce, without a second, separately-maintained resolution path.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from fnmatch import fnmatch
from pathlib import Path

from loguru import logger

from mccode_antlr.reader.registry import (
    InMemoryRegistry, LocalRegistry, RemoteRegistry, ordered_registries,
)
from mccode_antlr.io.portable import (
    collect_dependency_payloads, resolve_registry_and_path,
)


def _is_remote(reg) -> bool:
    return isinstance(reg, RemoteRegistry)


def _registry_identity(reg) -> tuple[str, str]:
    """(short display name, glob-match target) for *reg*; ('-', '-') if reg is None.

    The match target is what `-r/--repository` globs match against: a remote
    registry's URL (so e.g. '*/mcdotstar/*' matches a GitHubRegistry whose url
    is https://github.com/mcdotstar/...), a local registry's resolved root
    path, or just the registry name when neither applies.
    """
    if reg is None:
        return '-', '-'
    if isinstance(reg, RemoteRegistry):
        return reg.name, reg.url or reg.name
    if isinstance(reg, LocalRegistry):
        return reg.name, str(reg.root.resolve())
    return reg.name, reg.name


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


@dataclass(frozen=True)
class ExtractMember:
    """One file `extract_to_directory` could write for an Instr.

    `default_included` reflects membership in the *default* sweep (no
    explicit --list/select) for whichever `include_remote` `build_manifest`
    was called with -- `select_members` is what actually decides what a
    given call writes; do not filter on this field directly.
    """
    name: str
    category: str  # 'instr' | 'embedded' | 'dependency' | 'component'
    source: str  # 'generated' | 'embedded' | 'local' | 'remote'
    repository: str  # short display name, e.g. Registry.name, or 'generated'/'embedded'
    repository_match: str  # fuller identity matched by -r/--repository globs
    payload: bytes
    default_included: bool


def _instr_members(instr) -> list[ExtractMember]:
    return [
        ExtractMember(name, 'instr', 'generated', 'generated', 'generated', content.encode('utf-8'), True)
        for name, content in instr.to_strings().items()
    ]


def _embedded_members(instr) -> list[ExtractMember]:
    """Embedded (serialized-inline) files, attributed to their original source.

    `reg.origins` records where each file was captured from (e.g.
    'local:readout' for a LocalRegistry named 'readout') -- see
    `io.portable.collect_dependency_payloads`. Falls back to the embedded
    registry's own name ('embedded') for entries with no recorded origin
    (hand-built registries, or files embedded before origin tracking existed).
    """
    embedded = [reg for reg in (instr.registries or []) if isinstance(reg, InMemoryRegistry)]
    members = []
    for reg in embedded:
        for name in reg.filenames():
            repo = reg.origins.get(name, reg.name)
            members.append(
                ExtractMember(Path(name).name, 'embedded', 'embedded', repo, repo,
                               reg.contents_bytes(name), True)
            )
    return members


def _dependency_members(instr, registries) -> list[ExtractMember]:
    """Resolve %include headers/libraries, data files, and GETPATH targets.

    Runs the same dependency traversal `embedded_registry` uses to decide what
    to embed in a serialized JSON, accepting from every registry (local and
    remote) so the manifest can show remote-only dependencies too --
    `default_included` (not the accept filter) is what governs whether a
    remote one is in the default extraction sweep.
    """
    if not registries:
        return []
    payloads, _origins, _unresolved = collect_dependency_payloads(
        instr, registries, accept=lambda reg: True, budget=None,
    )
    members = []
    for name, payload in payloads.items():
        reg, _path = resolve_registry_and_path(registries, name)
        source = 'remote' if reg is not None and _is_remote(reg) else 'local'
        repo, repo_match = _registry_identity(reg)
        members.append(
            ExtractMember(Path(name).name, 'dependency', source, repo, repo_match, payload, source == 'local')
        )
    return members


def _component_members(instr, registries) -> list[ExtractMember]:
    """One <name>.comp member per unique component type *instr* uses.

    Reconstructed from the parsed `Comp` (always fully present, regardless of
    where it came from) via `Comp.to_string()`. A component's registry is
    re-resolved live against *registries* first; when that fails -- e.g. its
    LocalRegistry was dropped for want of --trust-local-registries -- fall
    back to `comp.origin`, the registry that resolved it when it was
    originally parsed (recorded by `Reader.add_component`).
    """
    seen: set[str] = set()
    members = []
    for instance in instr.components:
        comp = instance.type
        if comp.name in seen:
            continue
        seen.add(comp.name)
        reg, _path = resolve_registry_and_path(registries, f'{comp.name}.comp')
        if reg is not None:
            source = 'remote' if _is_remote(reg) else 'local'
            repo, repo_match = _registry_identity(reg)
        elif comp.origin is not None:
            source = 'remote' if comp.origin.startswith('remote:') else 'local'
            repo = repo_match = comp.origin
        else:
            source, repo, repo_match = 'local', '-', '-'
        members.append(
            ExtractMember(f'{comp.name}.comp', 'component', source, repo, repo_match,
                          comp.to_string().encode('utf-8'), source == 'local')
        )
    return members


def _dedupe_embedded_duplicates(members: list[ExtractMember]) -> list[ExtractMember]:
    """Drop an 'embedded' entry whenever a registry also resolves the same name.

    A file embedded at save time (so the instrument is portable without its
    original LocalRegistry) can become resolvable again -- e.g. once
    --trust-local-registries restores the registry it was embedded from.
    Keep the live, informatively-attributed copy over the frozen, generically
    labeled ('embedded') snapshot rather than listing/extracting both.
    """
    resolved_names = {m.name for m in members if m.source != 'embedded'}
    return [m for m in members if not (m.source == 'embedded' and m.name in resolved_names)]


def build_manifest(instr, include_remote: bool = False) -> list[ExtractMember]:
    """Every file `extract_to_directory` could write for *instr*, local and remote.

    With include_remote=False (default) only the .instr hierarchy, embedded
    files, and local component definitions/dependency files are marked
    `default_included`; remote-sourced entries are still present (so a caller
    can discover and select them by name) but excluded from the default sweep.
    With include_remote=True, remote-sourced entries are marked included too.

    A name embedded at save time that a currently active registry can also
    resolve appears once, attributed to that registry -- see
    `_dedupe_embedded_duplicates`.
    """
    registries = _non_embedded_registries(instr)
    members = (
        _instr_members(instr) + _embedded_members(instr)
        + _dependency_members(instr, registries) + _component_members(instr, registries)
    )
    members = _dedupe_embedded_duplicates(members)
    if include_remote:
        members = [replace(m, default_included=True) if m.source == 'remote' else m for m in members]
    return members


def select_members(
    manifest: list[ExtractMember],
    select: list[str] | None = None,
    exclude: list[str] | None = None,
    repository: list[str] | None = None,
) -> list[ExtractMember]:
    """The subset of *manifest* a given extract/list invocation would produce.

    With neither `select` nor `repository`, this is the default sweep
    (`default_included` entries, already reflecting whichever `include_remote`
    `build_manifest` was called with). An explicit `select` glob or
    `repository` glob bypasses that default sweep entirely -- naming a
    remote-only file, or a repository that only supplies remote-only files,
    extracts it even without `--include-remote`, since asking for it
    explicitly is unambiguous. When both `select` and `repository` are given
    they AND together: a member must match a `select` pattern (by name) *and*
    a `repository` pattern (against `repository_match`). `exclude` globs are
    then dropped from whichever set results, same as `unzip -x`.
    """
    if select or repository:
        chosen = manifest
        if select:
            chosen = [m for m in chosen if any(fnmatch(m.name, pattern) for pattern in select)]
        if repository:
            chosen = [m for m in chosen if any(fnmatch(m.repository_match, pattern) for pattern in repository)]
    else:
        chosen = [m for m in manifest if m.default_included]
    if exclude:
        chosen = [m for m in chosen if not any(fnmatch(m.name, pattern) for pattern in exclude)]
    return chosen


def extract_to_directory(
        instr, directory, include_remote: bool = False,
        select: list[str] | None = None, exclude: list[str] | None = None,
        repository: list[str] | None = None,
) -> Path:
    """Reconstitute *instr* into *directory*: .instr hierarchy, stashed files,
    and component definitions, all flat.

    With include_remote=False (default) and no select/exclude/repository,
    only files not otherwise available from a remote registry are written --
    what a consumer could not get any other way. See `select_members` for how
    include_remote, select, exclude, and repository interact.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(instr, include_remote)
    for member in select_members(manifest, select, exclude, repository=repository):
        _write_flat(instr, directory, member.name, member.payload)
    return directory

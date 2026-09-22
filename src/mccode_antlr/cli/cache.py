"""CLI sub-commands for managing the mccode-antlr caches.

Pooch-registered file caches
-----------------------------
- ``list``     – list known cache directories or the versions within one cache.
- ``remove``   – remove a named cache (or a specific version within it).
- ``populate`` – bulk-populate all pooch caches from a McCode git tag or a
                 local repository checkout (avoids individual file downloads).
- ``register`` – mint a pooch registry file (path + sha256 hash per line)
                 from a local directory tree.

Component intermediate-representation (IR) cache
-------------------------------------------------
The reader writes a ``{name}.comp.<salt>.json`` file alongside every ``.comp``
file it parses (the ``<salt>`` binds the sidecar to the mccode-antlr build that
wrote it).  These files persist across process restarts (acting as a fast disk
cache), but they accumulate and users may wish to inspect or clean them up.

- ``ir-list``  – find and list all component IR sidecars under the cache root.
- ``ir-clean`` – delete all (or only stale) component IR sidecars; a sidecar
                 from a different build counts as stale.
"""
from __future__ import annotations

import argparse
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers shared with the CI warm-cache script
# ---------------------------------------------------------------------------

def _cache_root() -> Path:
    """Return the root directory used by all mccode-antlr pooch caches."""
    from pooch import os_cache
    return os_cache('mccodeantlr')


def populate_from_clone(
    clone: Path, tag: str, flavor=None, strict: bool = True, check_hashes: bool = False,
) -> tuple[int, int]:
    """Copy registry files from a McCode repository clone into the pooch cache.

    Parameters
    ----------
    clone:
        Root of a McCode git checkout (or any directory with the same layout).
    tag:
        The McCode version tag the clone was made at (e.g. ``v3.5.31``).
        Used only for progress messages; the pooch cache paths are determined
        by the currently-configured registries.
    flavor:
        ``None`` → both flavors; otherwise one of ``Flavor.MCSTAS`` /
        ``Flavor.MCXTRACE``.
    strict:
        If ``True`` (default), a registry file missing from the clone (or,
        with ``check_hashes``, a content-hash mismatch) is printed with an
        ``ERROR`` tag. If ``False``, the same conditions are printed with a
        ``WARNING`` tag instead. Either way the miss/mismatch is counted in
        the returned ``error_count``.
    check_hashes:
        If ``True``, also verify each source file's sha256 hash against the
        registry-recorded hash before copying, flagging a mismatch the same
        way a missing file is flagged. ``False`` (default) skips this and
        only checks that the file exists, which is cheaper but will silently
        copy a locally-modified file whose content no longer matches the
        registry.

    Returns
    -------
    (total_copied, error_count)
    """
    import shutil
    from pooch import file_hash
    from mccode_antlr import Flavor
    from mccode_antlr.reader.registry import _mccode_pooch_registries, default_registry_names

    flavors = (Flavor.MCSTAS, Flavor.MCXTRACE) if flavor is None else (flavor,)

    total = errors = 0
    seen: set[Path] = set()

    for flv in flavors:
        for reg in _mccode_pooch_registries(default_registry_names(flv)):
            p = getattr(reg, 'pooch', None)
            if p is None or p.path in seen:
                continue
            seen.add(p.path)
            files = list(p.registry_files)
            print(f"  [{reg.name}] copying {len(files)} files into {p.path} …", flush=True)
            for fname in files:
                src = clone / fname
                dst = Path(p.path) / fname
                label = 'ERROR' if strict else 'WARNING'
                if not src.exists():
                    print(f"    {label}: {src} not in clone", flush=True)
                    errors += 1
                    continue
                if check_hashes:
                    expected = p.registry.get(fname)
                    actual = file_hash(str(src))
                    if expected is not None and actual != expected:
                        print(
                            f"    {label}: {src} hash mismatch "
                            f"(expected {expected}, got {actual})",
                            flush=True,
                        )
                        errors += 1
                        continue
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                total += 1

    return total, errors


def build_registry(
    root: Path, dirs: list[str], ext: list[str] | None = None, recursive: bool = True,
) -> dict[str, str]:
    """Hash every matching file under root/<dir> for each dir in dirs.

    Component IR sidecars are always skipped. A registry describes source files,
    and a sidecar is something mccode-antlr *generated* from one, so registering
    it promises a file that no source repository contains -- which is how
    ``mcstas-comps/optics/Collimator_linear.comp.json`` reached the published
    McCode registries and broke ``cache populate`` for every tag that carried it.
    There is deliberately no way to opt back in.

    Parameters
    ----------
    root:
        Root path; registry keys are POSIX paths relative to this root.
    dirs:
        Sub-directories (relative to root) to walk.
    ext:
        Optional list of filename-suffix filters (repeatable). A file is
        included if its name ends with any of them (matches literal
        suffixes like ``.comp`` or ``lib.c``, mirroring the reference
        scripts this replaces). ``None`` includes every file.
    recursive:
        Recurse into subdirectories of each ``dirs`` entry (default), or
        only look at their immediate contents if ``False``.

    Returns
    -------
    dict mapping POSIX relative path -> sha256 hex digest (``pooch.file_hash``).
    """
    from pooch import file_hash
    from mccode_antlr.reader.reader import is_component_ir_sidecar

    pattern_prefix = '**/*' if recursive else '*'
    suffixes = ext if ext else [None]

    hashes: dict[str, str] = {}
    skipped: set[str] = set()
    for d in dirs:
        base = root / d
        for suffix in suffixes:
            pattern = pattern_prefix + suffix if suffix else pattern_prefix
            for path in base.glob(pattern):
                if not path.is_file():
                    continue
                name = path.relative_to(root).as_posix()
                if is_component_ir_sidecar(path):
                    skipped.add(name)
                    continue
                hashes[name] = file_hash(str(path))
    if skipped:
        print(
            f"  skipped {len(skipped)} generated component IR sidecar(s), "
            f"e.g. {sorted(skipped)[0]}",
            flush=True,
        )
    return hashes


def seed_registry_manifests(names: list[str], tag: str, registry_dir: Path) -> list[str]:
    """Copy locally-minted "<name>-registry.txt" files into pooch's OS-cache
    path for each name+tag, so GitHubRegistry._build_pooch() finds them
    without any network access.

    Parameters
    ----------
    names:
        Registry names to seed (e.g. ``['libc', 'mcstas']``).
    tag:
        The McCode version tag currently in effect (e.g. ``v3.5.31``) — must
        match what ``_mccode_pooch_registries()`` will later resolve for this
        manifest to actually be found.
    registry_dir:
        Directory containing ``<name>-registry.txt`` files, e.g. produced by
        `cache register`.

    Returns
    -------
    The subset of ``names`` that were actually seeded. A name whose manifest
    file isn't found in ``registry_dir`` is left for the normal
    remote/already-cached resolution to handle instead (reported as a
    WARNING, not fatal — a user may only have minted some registries locally).
    """
    import shutil
    import pooch

    seeded = []
    for name in names:
        src = registry_dir / f'{name}-registry.txt'
        if not src.is_file():
            print(f"WARNING: {src} not found; {name} will use its normal remote/cached resolution", flush=True)
            continue
        dest = pooch.os_cache(f'mccodeantlr/{name}') / tag / f'{name}-registry.txt'
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        seeded.append(name)
    return seeded


def warm_registries_via_pooch(registries) -> tuple[int, int]:
    """Download every file of each pooch-backed registry in *registries*.

    One request per file, so this is the slow path.  For the McCode registries
    :func:`populate_from_clone` is far faster; this is what remains for registries
    that have no git-clone shortcut, such as those named with ``--registry``.
    Local registries are skipped: their files are already on disk.

    Returns
    -------
    (total_fetched, error_count)
    """
    total = errors = 0
    seen: set = set()

    for reg in registries:
        p = getattr(reg, 'pooch', None)
        if p is None or id(p) in seen:
            continue
        seen.add(id(p))
        # A registry manifest that lists itself cannot be re-fetched: the recorded
        # hash is of the file as it stood before that line was added, so pooch
        # rejects the download. We already hold the manifest, so skip it.
        own = getattr(reg, 'filename', None)
        own = own.name if isinstance(own, Path) else own
        files = [f for f in p.registry_files if f != own]
        print(f"  [{reg.name}] downloading {len(files)} files …", flush=True)
        for fname in files:
            try:
                p.fetch(fname)
                total += 1
            except Exception as exc:
                print(f"    WARNING: could not fetch {fname}: {exc}", flush=True)
                errors += 1

    return total, errors


def warm_via_pooch(flavor=None) -> tuple[int, int]:
    """Populate the default McCode pooch caches using individual file downloads.

    Parameters
    ----------
    flavor:
        ``None`` → both flavors; otherwise one of ``Flavor.MCSTAS`` /
        ``Flavor.MCXTRACE``.

    Returns
    -------
    (total_fetched, error_count)
    """
    from mccode_antlr import Flavor
    from mccode_antlr.reader import registry as _registry_mod
    from mccode_antlr.reader.registry import default_registry_names

    flavors = (Flavor.MCSTAS, Flavor.MCXTRACE) if flavor is None else (flavor,)

    total = errors = 0
    for flv in flavors:
        regs = _registry_mod._mccode_pooch_registries(default_registry_names(flv))
        t, e = warm_registries_via_pooch(regs)
        total += t
        errors += e

    return total, errors


# ---------------------------------------------------------------------------
# CLI action functions
# ---------------------------------------------------------------------------

def cache_path() -> Path:
    return _cache_root()


def cache_remove(name, version, force):
    from shutil import rmtree
    path = _cache_root()
    if name is not None:
        path = path / name
    if version is not None:
        path = path / version
    if not force:
        response = input(f'Remove {path} and all contents? [yN] ')
        force = response.lower() in ('y', 'yes')
    if force:
        rmtree(path)


def cache_list(name, long):
    path = _cache_root()
    if name is not None:
        path = path / name
    dirs = sorted([d for d in path.iterdir() if d.is_dir()], key=lambda x: x.name)
    dstr = '\n'.join(f'  {d if long else d.name}' for d in dirs)
    n = len(dirs)
    c = 'cache' if n == 1 else 'caches'
    print(f'{n} known {c} for {path.name}:\n{dstr}')


def _resolve_mccode_tag(tag: str | None) -> str:
    """Resolve *tag* to a concrete McCode version tag and make it effective.

    ``None`` keeps the currently-configured tag, ``'latest'`` resolves to the
    newest released one, anything else is taken as given.  The resolved value is
    written back to ``MCCODEANTLR_MCCODE_POOCH__TAG`` so that every registry this
    process builds afterwards points at the same version -- the pooch caches are
    laid out per tag (``.../mcstas/v3.7.22/``), so this is what selects which
    cached tree a command operates on.
    """
    import os

    if tag is None or tag.lower() == 'latest':
        from mccode_antlr.reader.registry import _source_registry_tag
        if tag is not None:
            os.environ['MCCODEANTLR_MCCODE_POOCH__TAG'] = tag
        _source_registry_tag.cache_clear()
        _, _, version = _source_registry_tag()
        tag = f'v{version}'

    os.environ['MCCODEANTLR_MCCODE_POOCH__TAG'] = tag
    return tag


def cache_populate(
    tag: str | None, from_path: str | None, clone_url: str, flavor: str,
    strict: bool = True, check_hashes: bool | None = None, registry_dir: str | None = None,
    registry: list[str] | None = None,
):
    """Bulk-populate the pooch caches from a McCode git tag or a local checkout.

    Registries named with ``--registry`` are populated too, file by file through
    pooch — they have no git-clone shortcut. This is the only command that
    downloads; ``cache ir-build`` parses whatever is already on disk.

    ``flavor='none'`` skips the McCode side entirely — no tag resolution, no
    clone, no checkout — so populating only ``--registry`` extras costs nothing
    else.
    """
    import os
    import tempfile
    import subprocess
    import sys

    from mccode_antlr import Flavor

    skip_mccode = bool(flavor) and flavor.lower() == 'none'
    resolved_flavor = None
    if flavor and flavor.lower() not in ('both', 'none'):
        resolved_flavor = Flavor[flavor.upper()]

    # check_hashes defaults to following --strict/--no-strict when not given explicitly.
    resolved_check_hashes = strict if check_hashes is None else check_hashes

    total = errors = 0

    if skip_mccode:
        if registry_dir is not None:
            print(
                'WARNING: --registry-dir seeds McCode registry manifests, which '
                '--flavor none skips — ignoring it.',
                flush=True,
            )
        if not registry:
            print(
                'Nothing to do: --flavor none skips McCode and no --registry was given.',
                flush=True,
            )
    else:
        tag = _resolve_mccode_tag(tag)
        print(f"Populating pooch caches for McCode {tag} …", flush=True)

        if registry_dir is not None:
            registry_dir_path = Path(registry_dir).resolve()
            if not registry_dir_path.is_dir():
                print(f"ERROR: --registry-dir {registry_dir_path} does not exist or is not a directory.", flush=True)
                sys.exit(1)
            from mccode_antlr.reader.registry import default_registry_names
            flavors_for_names = (Flavor.MCSTAS, Flavor.MCXTRACE) if resolved_flavor is None else (resolved_flavor,)
            names = []
            for flv in flavors_for_names:
                for n in default_registry_names(flv):
                    if n not in names:
                        names.append(n)
            seed_registry_manifests(names, tag, registry_dir_path)

        if from_path is not None:
            src = Path(from_path).resolve()
            if not src.is_dir():
                print(f"ERROR: --from-path {src} does not exist or is not a directory.", flush=True)
                sys.exit(1)
            print(f"Using local checkout: {src}", flush=True)
            total, errors = populate_from_clone(
                src, tag, flavor=resolved_flavor, strict=strict, check_hashes=resolved_check_hashes,
            )
        else:
            with tempfile.TemporaryDirectory() as tmp:
                dest = Path(tmp) / 'McCode'
                print(f"Cloning {clone_url} at {tag} …", flush=True)
                subprocess.run(
                    ['git', 'clone', '--depth=1', '-c', 'core.autocrlf=false',
                     '--branch', tag, '--', clone_url, str(dest)],
                    check=True,
                )
                total, errors = populate_from_clone(
                    dest, tag, flavor=resolved_flavor, strict=strict, check_hashes=resolved_check_hashes,
                )

    for extra in _registries_from_specs(registry):
        if getattr(extra, 'pooch', None) is None:
            print(f"  [{extra.name}] local registry — nothing to download", flush=True)
            continue
        t, e = warm_registries_via_pooch([extra])
        total += t
        errors += e

    print(f"\nDone. {total} files cached, {errors} errors.", flush=True)
    if errors and strict:
        sys.exit(1)


def cache_register(
    root: str, dirs: list[str], out: str = 'pooch-registry.txt',
    ext: list[str] | None = None, recursive: bool = True,
):
    """Mint a pooch registry file (path + sha256 hash per line) from a local directory tree."""
    import sys

    root_path = Path(root).resolve()
    if not root_path.is_dir():
        print(f"ERROR: root {root_path} does not exist or is not a directory.", flush=True)
        sys.exit(1)

    for d in dirs:
        if not (root_path / d).is_dir():
            print(f"WARNING: {root_path / d} does not exist or is not a directory.", flush=True)

    hashes = build_registry(root_path, dirs, ext=ext, recursive=recursive)

    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(''.join(f'{name} {hashes[name]}\n' for name in sorted(hashes)))

    print(f"Wrote {len(hashes)} entries to {out_path}", flush=True)


# ---------------------------------------------------------------------------
# Component IR cache helpers
# ---------------------------------------------------------------------------

def _iter_ir_files(root: Path):
    """Yield every component IR sidecar under *root* (any build, plus legacy)."""
    from mccode_antlr.reader.reader import iter_component_ir_paths
    return iter_component_ir_paths(root)


def _is_stale(json_path: Path) -> bool:
    """True if *json_path* is unusable: sibling ``.comp`` newer, or it was
    written by a different mccode-antlr build."""
    from mccode_antlr.reader.reader import component_ir_comp_path, component_ir_is_current
    if not component_ir_is_current(json_path):
        return True
    comp_path = component_ir_comp_path(json_path)
    try:
        return comp_path.stat().st_mtime_ns > json_path.stat().st_mtime_ns
    except OSError:
        return False


def cache_ir_list(long: bool):
    """List ``*.comp.json`` IR cache files under the mccode-antlr cache root."""
    root = _cache_root()
    files = sorted(_iter_ir_files(root))
    if not files:
        print("No component IR cache files found.")
        return
    for f in files:
        if long:
            size = f.stat().st_size
            stale = ' [stale]' if _is_stale(f) else ''
            print(f'{f}  ({size} B){stale}')
        else:
            print(f.name)
    print(f'\n{len(files)} component IR sidecar(s) found under {root}')


def cache_ir_clean(stale: bool, force: bool):
    """Delete ``.comp.json`` IR cache files under the mccode-antlr cache root."""
    root = _cache_root()
    candidates = sorted(_iter_ir_files(root))
    if stale:
        targets = [f for f in candidates if _is_stale(f)]
        description = 'stale'
    else:
        targets = candidates
        description = 'all'

    if not targets:
        print(f"No {description} component IR sidecars to remove.")
        return

    if not force:
        response = input(f'Remove {len(targets)} {description} component IR sidecar(s)? [yN] ')
        if response.lower() not in ('y', 'yes'):
            print("Aborted.")
            return

    removed = 0
    for f in targets:
        try:
            f.unlink()
            removed += 1
        except OSError as exc:
            print(f'WARNING: could not remove {f}: {exc}')

    print(f'Removed {removed} component IR sidecar(s).')


# ---------------------------------------------------------------------------
# Component IR cache build
# ---------------------------------------------------------------------------

# Per-process Reader used to resolve INHERIT/COPY parents while building IR.
# A component defined as `DEFINE COMPONENT b INHERIT a` cannot be parsed without
# something able to find `a`, so every worker needs a Reader over the same
# registries the paths were collected from.  Set by :func:`_ir_worker_init`,
# which runs once per pool worker (and once directly in the serial path).
_IR_READER = None


def _ir_worker_init(registries, flavor, tag=None) -> None:
    """Build this process's Reader once, for INHERIT/COPY parent lookups.

    *tag* is re-applied here rather than inherited: a worker started by the
    ``spawn`` or ``forkserver`` methods does not carry the parent's later
    ``os.environ`` edits, and a parent resolved against the wrong McCode version
    would silently write sidecars into the wrong cached tree.
    """
    global _IR_READER
    import os
    from mccode_antlr.reader.reader import Reader
    if tag is not None:
        os.environ['MCCODEANTLR_MCCODE_POOCH__TAG'] = tag
    _IR_READER = Reader(registries=list(registries), flavor=flavor)


def _build_one_ir(comp_path_str: str, force: bool) -> tuple[str, str]:
    """Parse one ``.comp`` file and write its ``.comp.json``.

    Module-level so it is picklable by ``ProcessPoolExecutor``.

    Returns ``(comp_path_str, status)`` where *status* is one of
    ``'hit'``, ``'built'``, or ``'error: <message>'``.
    """
    from pathlib import Path
    from mccode_antlr.reader.reader import component_cache, make_reader_error_listener
    from mccode_antlr.comp import Comp
    from mccode_antlr.grammar import McComp_ErrorListener

    from mccode_antlr.reader.reader import component_ir_path

    comp_path = Path(comp_path_str)
    json_path = component_ir_path(comp_path)

    if not force:
        try:
            if json_path.exists() and json_path.stat().st_mtime_ns >= comp_path.stat().st_mtime_ns:
                return (comp_path_str, 'hit')
        except OSError:
            pass

    try:
        source = comp_path.read_text()
        error_listener = make_reader_error_listener(
            McComp_ErrorListener, 'Component', comp_path.stem, source
        )
        comp = Comp.from_source(_IR_READER, error_listener, source, str(comp_path), str(comp_path))
        component_cache.put(comp_path, comp)
        return (comp_path_str, 'built')
    except Exception as exc:
        return (comp_path_str, f'error: {exc}')


_REGISTRY_SPEC_FORMS = (
    'Expected one of:\n'
    '  /path/to/dir\n'
    '  name /path/to/dir [non-recursive]\n'
    '  name url /path/to/pooch-registry.txt\n'
    '  name url version registry-file-name\n'
    '  owner/repo@version[#registry-file]\n'
    '  git+url@version[#registry-file]\n'
    'The compact git forms need an explicit @version (e.g. @main or @v1.2.3).'
)


def _registries_from_specs(specs) -> list:
    """Build Registry objects from ``--registry`` specification strings.

    An unparsable spec is reported with the accepted forms and skipped, rather
    than aborting a run that may still have useful work to do.
    """
    from mccode_antlr.reader.registry import registry_from_specification

    out = []
    for spec in (specs or []):
        try:
            extra = registry_from_specification(spec)
        except Exception as exc:
            print(f'WARNING: could not parse registry spec {spec!r}: {exc} — skipping.', flush=True)
            continue
        if extra is None:
            indented = '\n'.join(f'         {line}' for line in _REGISTRY_SPEC_FORMS.split('\n'))
            print(
                f'WARNING: could not parse registry spec {spec!r} — skipping.\n{indented}',
                flush=True,
            )
            continue
        out.append(extra)
    return out


def _collect_comp_paths(registries) -> tuple[list[Path], int]:
    """Find every locally-present ``.comp`` file in *registries*.

    Only files already on disk can be parsed, so a registry whose files have not
    been downloaded contributes nothing.  ``cache populate`` is what downloads
    them; the count of not-yet-present files is returned so the caller can say so
    rather than silently building a fraction of the registry.

    Parameters
    ----------
    registries:
        An iterable of :class:`~mccode_antlr.reader.registry.Registry` objects.

    Returns
    -------
    (deduplicated absolute paths, number of registered .comp files not on disk)
    """
    seen: set[Path] = set()
    paths: list[Path] = []
    missing = 0

    for reg in registries:
        if getattr(reg, 'pooch', None) is not None:
            # Pooch-backed (remote) registry — only include files already cached locally
            for fname in reg.pooch.registry_files:
                if not fname.endswith('.comp'):
                    continue
                local = Path(reg.pooch.path) / fname
                if local.exists():
                    key = local.resolve()
                    if key not in seen:
                        seen.add(key)
                        paths.append(key)
                else:
                    missing += 1
        else:
            # Local registry
            root = getattr(reg, 'root', None)
            if root is None:
                continue
            root = Path(root)
            for p in root.rglob('*.comp'):
                key = p.resolve()
                if key not in seen:
                    seen.add(key)
                    paths.append(key)

    return paths, missing


def _registries_for_flavors(flavor: str, registry: list[str] | None) -> tuple[list, list]:
    """Default registries for *flavor* plus any ``--registry`` extras.

    Returns ``(flavors, registries)``; both ``populate`` and ``ir-build`` need the
    same set, so they resolve it the same way.
    """
    from mccode_antlr import Flavor
    from mccode_antlr.reader.registry import default_registries

    if flavor == 'none':
        flavors = []
    elif flavor == 'both':
        flavors = [Flavor.MCSTAS, Flavor.MCXTRACE]
    else:
        flavors = [Flavor[flavor.upper()]]

    registries = []
    seen_regs: set = set()
    for flv in flavors:
        for reg in default_registries(flv):
            if id(reg) not in seen_regs:
                seen_regs.add(id(reg))
                registries.append(reg)

    registries.extend(_registries_from_specs(registry))
    return flavors, registries


def cache_ir_build(flavor: str, jobs: int, force: bool, registry: list[str] | None,
                   tag: str | None = None):
    """Pre-build component IR (``.comp.json``) files for all known registries.

    Builds IR from files already on disk and downloads nothing: ``cache populate``
    is the command that fills the caches, including any ``--registry`` extras.

    The pooch caches are laid out per McCode version, so *tag* selects which
    cached tree to build IR for when several have been populated.
    """
    import os
    from concurrent.futures import ProcessPoolExecutor, as_completed
    from functools import partial

    # Resolve the tag before the registries: it is what decides which versioned
    # cache directory they point at.
    resolved_tag = None
    if flavor != 'none':
        resolved_tag = _resolve_mccode_tag(tag)
        print(f'Building IR for McCode {resolved_tag} …', flush=True)
    elif tag is not None:
        print('WARNING: --tag selects a McCode version, which --flavor none skips — ignoring it.',
              flush=True)

    flavors, all_registries = _registries_for_flavors(flavor, registry)

    print('Collecting .comp files …', flush=True)
    comp_paths, missing = _collect_comp_paths(all_registries)
    if missing:
        print(
            f'  {missing} registered .comp file(s) are not downloaded and will be '
            f'skipped; run `mccode-antlr cache populate` to fetch them.',
            flush=True,
        )
    if not comp_paths:
        print('No .comp files found — run `mccode-antlr cache populate` first.')
        return

    n = len(comp_paths)
    print(f'Found {n} .comp file(s). Building IR cache …', flush=True)

    if jobs is None:
        jobs = os.cpu_count() or 1

    worker = partial(_build_one_ir, force=force)
    built = hits = errors = 0

    # The Reader that resolves INHERIT/COPY parents is built per process: once
    # here for the serial path, once per worker via the pool's initializer.
    #
    # Under --flavor none it must still see the McCode registries: --flavor
    # chooses what to build IR *for*, and a --registry component may well
    # INHERIT a McCode one. Listing a registry is free -- Reader only sorts them
    # by priority, and a registry builds its pooch index lazily -- so nothing is
    # fetched unless a parent lookup actually reaches that far.
    lookup_registries = list(all_registries)
    if not flavors:
        from mccode_antlr import Flavor
        from mccode_antlr.reader.registry import default_registries
        seen_ids = {id(r) for r in lookup_registries}
        for flv in (Flavor.MCSTAS, Flavor.MCXTRACE):
            for reg in default_registries(flv):
                if id(reg) not in seen_ids:
                    seen_ids.add(id(reg))
                    lookup_registries.append(reg)
    reader_args = (lookup_registries, flavors[0] if flavors else None, resolved_tag)

    if jobs == 1:
        _ir_worker_init(*reader_args)
        for path in comp_paths:
            _, status = worker(str(path))
            if status == 'built':
                built += 1
            elif status == 'hit':
                hits += 1
            else:
                errors += 1
                print(f'  {path.name}: {status}', flush=True)
    else:
        with ProcessPoolExecutor(
            max_workers=jobs, initializer=_ir_worker_init, initargs=reader_args,
        ) as pool:
            futures = {pool.submit(_build_one_ir, str(p), force): p for p in comp_paths}
            for future in as_completed(futures):
                _, status = future.result()
                if status == 'built':
                    built += 1
                elif status == 'hit':
                    hits += 1
                else:
                    errors += 1
                    print(f'  {futures[future].name}: {status}', flush=True)

    print(
        f'\nDone. {built} built, {hits} already up-to-date, {errors} error(s).',
        flush=True,
    )


def add_cache_management_parser(modes):
    parser = modes.add_parser(name='cache', help='Manage the mccode-antlr cache')
    actions = parser.add_subparsers(help='Action to perform', metavar='ACTION', required=True)

    # -- list --
    l = actions.add_parser(name='list', help='List named caches or the versions of one cache')
    l.add_argument('name', type=str, nargs='?')
    l.add_argument('-l', '--long', action='store_true')
    l.set_defaults(action=cache_list)

    # -- remove --
    r = actions.add_parser(name='remove', help='Remove a named cache')
    r.add_argument('name', type=str, nargs='?', help='cache to remove [default all caches]')
    r.add_argument('version', type=str, nargs='?', help='version to remove [default all versions]')
    r.add_argument('-f', '--force', action='store_true')
    r.set_defaults(action=cache_remove)

    # -- populate --
    p = actions.add_parser(
        name='populate',
        help='Bulk-populate pooch caches from a McCode git tag or local checkout',
    )
    p.add_argument(
        '--tag', default=None,
        help='McCode version tag (e.g. v3.5.31, latest); defaults to the currently-configured version',
    )
    p.add_argument(
        '--from-path', dest='from_path', default=None, metavar='PATH',
        help='Path to an existing local McCode repository checkout (skips network clone)',
    )
    p.add_argument(
        '--clone-url', dest='clone_url',
        default='https://github.com/mccode-dev/McCode.git',
        help='Git URL to clone when --from-path is not given',
    )
    p.add_argument(
        '--flavor', default='both', choices=['mcstas', 'mcxtrace', 'both', 'none'],
        help=(
            "Which flavor's registries to populate (default: both). Use 'none' to "
            "skip McCode entirely — no tag resolution and no clone — and populate "
            "only the registries given with --registry."
        ),
    )
    p.add_argument(
        '--strict', action=argparse.BooleanOptionalAction, default=True,
        help=(
            'Treat missing registry files as fatal errors (default). '
            'Use --no-strict to only warn and exit 0 when files are missing.'
        ),
    )
    p.add_argument(
        '--check-hashes', dest='check_hashes', action=argparse.BooleanOptionalAction, default=None,
        help=(
            'Verify each copied file against the registry-recorded sha256 hash '
            '(default: follows --strict/--no-strict, i.e. on when strict, off when lenient). '
            'A mismatch is reported the same way as a missing file.'
        ),
    )
    p.add_argument(
        '--registry-dir', dest='registry_dir', default=None, metavar='DIR',
        help=(
            'Directory containing locally-minted "<name>-registry.txt" manifests '
            '(e.g. produced by `cache register`). When given, these are used '
            'instead of fetching the manifest from mccode_pooch.registry, and '
            'seed pooch\'s cache so later cache populate / translation calls at '
            'the same tag also use them without any network access.'
        ),
    )
    p.add_argument(
        '-R', '--registry', action='append', default=None, metavar='SPEC',
        help=(
            'Also download this registry (repeatable); file by file, since only the '
            'McCode registries have a git-clone shortcut. ' + _REGISTRY_SPEC_FORMS.replace('\n', ' ')
        ),
    )
    p.set_defaults(action=cache_populate)

    # -- ir-list --
    il = actions.add_parser(
        name='ir-list',
        help='List component IR cache sidecars (*.comp.<build>.json) under the cache root',
    )
    il.add_argument('-l', '--long', action='store_true',
                    help='Show full path, size, and stale status')
    il.set_defaults(action=cache_ir_list)

    # -- ir-clean --
    ic = actions.add_parser(
        name='ir-clean',
        help='Delete component IR cache sidecars (*.comp.<build>.json) under the cache root',
    )
    ic.add_argument(
        '--stale', action='store_true',
        help='Only remove sidecars whose sibling .comp is newer, or that a different build wrote',
    )
    ic.add_argument('-f', '--force', action='store_true',
                    help='Skip confirmation prompt')
    ic.set_defaults(action=cache_ir_clean)

    # -- ir-build --
    ib = actions.add_parser(
        name='ir-build',
        help=(
            'Pre-build component IR cache sidecars from the .comp files already on '
            'disk (downloads nothing — see `cache populate`)'
        ),
    )
    ib.add_argument(
        '--tag', default=None,
        help=(
            'McCode version tag whose cached components to build IR for '
            '(e.g. v3.5.31, latest); defaults to the currently-configured version. '
            'The pooch caches are per version, so this picks between them when '
            'several have been populated.'
        ),
    )
    ib.add_argument(
        '--flavor', default='both', choices=['mcstas', 'mcxtrace', 'both', 'none'],
        help=(
            "Which flavor's registries to build IR for (default: both). Use 'none' "
            "to build only the registries given with --registry."
        ),
    )
    ib.add_argument(
        '-j', '--jobs', type=int, nargs='?', default=None, const=None, metavar='N',
        help='Number of parallel workers; bare -j or omitted means os.cpu_count()',
    )
    ib.add_argument(
        '--force', action='store_true',
        help='Rebuild even if the IR sidecar is already up-to-date',
    )
    ib.add_argument(
        '-R', '--registry', action='append', default=None, metavar='SPEC',
        help=(
            'Extra registry to build IR for (repeatable). Only files already on disk '
            'are built: pass the same specification to `cache populate` first to '
            'download them. ' + _REGISTRY_SPEC_FORMS.replace('\n', ' ')
        ),
    )
    ib.set_defaults(action=cache_ir_build)

    # -- register --
    reg = actions.add_parser(
        name='register',
        help=(
            'Mint a pooch registry file (path + sha256 hash per line) from a local '
            'directory tree. Component IR sidecars (*.comp.json, *.comp.<salt>.json) '
            'are always skipped: they are generated, so no source repository contains '
            'them and registering one promises a file that can never be fetched.'
        ),
    )
    reg.add_argument('root', type=str, help='Root path; registry entries are recorded relative to this')
    reg.add_argument('dirs', type=str, nargs='+', metavar='DIR', help='One or more directories under root to walk')
    reg.add_argument(
        '--out', '-o', dest='out', default='pooch-registry.txt', metavar='FILE',
        help='Registry output file path (default: pooch-registry.txt)',
    )
    reg.add_argument(
        '--ext', action='append', default=None, metavar='SUFFIX',
        help='Only include files whose name ends with this suffix (repeatable); default includes every file',
    )
    reg.add_argument(
        '--recursive', action=argparse.BooleanOptionalAction, default=True,
        help='Recurse into subdirectories of each DIR (default). Use --no-recursive to only look at their top level.',
    )
    reg.set_defaults(action=cache_register)

    return actions

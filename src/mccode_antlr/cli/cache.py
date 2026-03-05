"""CLI sub-commands for managing the mccode-antlr caches.

Pooch-registered file caches
-----------------------------
- ``list``     – list known cache directories or the versions within one cache.
- ``remove``   – remove a named cache (or a specific version within it).
- ``populate`` – bulk-populate all pooch caches from a McCode git tag or a
                 local repository checkout (avoids individual file downloads).

Component intermediate-representation (IR) cache
-------------------------------------------------
The reader writes a ``{name}.comp.json`` file alongside every ``.comp`` file it
parses.  These files persist across process restarts (acting as a fast disk
cache), but they accumulate and users may wish to inspect or clean them up.

- ``ir-list``  – find and list all ``*.comp.json`` files under the cache root.
- ``ir-clean`` – delete all (or only stale) ``*.comp.json`` files.
"""
from __future__ import annotations

from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers shared with the CI warm-cache script
# ---------------------------------------------------------------------------

def _cache_root() -> Path:
    """Return the root directory used by all mccode-antlr pooch caches."""
    from pooch import os_cache
    return os_cache('mccodeantlr')


def populate_from_clone(clone: Path, tag: str, flavor=None) -> tuple[int, int]:
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

    Returns
    -------
    (total_copied, error_count)
    """
    import shutil
    from mccode_antlr import Flavor
    from mccode_antlr.reader.registry import _mccode_pooch_registries

    flavors = (Flavor.MCSTAS, Flavor.MCXTRACE) if flavor is None else (flavor,)

    total = errors = 0
    seen: set[Path] = set()

    for flv in flavors:
        for reg in _mccode_pooch_registries(flv):
            p = getattr(reg, 'pooch', None)
            if p is None or p.path in seen:
                continue
            seen.add(p.path)
            files = list(p.registry_files)
            print(f"  [{reg.name}] copying {len(files)} files into {p.path} …", flush=True)
            for fname in files:
                src = clone / fname
                dst = Path(p.path) / fname
                if not src.exists():
                    print(f"    WARNING: {src} not in clone", flush=True)
                    errors += 1
                    continue
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                total += 1

    return total, errors


def warm_via_pooch(flavor=None) -> tuple[int, int]:
    """Populate the pooch caches using individual file downloads (slow fallback).

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
    from mccode_antlr.reader.registry import _mccode_pooch_registries

    flavors = (Flavor.MCSTAS, Flavor.MCXTRACE) if flavor is None else (flavor,)

    total = errors = 0
    seen: set = set()

    for flv in flavors:
        for reg in _mccode_pooch_registries(flv):
            p = getattr(reg, 'pooch', None)
            if p is None or id(p) in seen:
                continue
            seen.add(id(p))
            files = list(p.registry_files)
            print(f"  [{reg.name}] downloading {len(files)} files …", flush=True)
            for fname in files:
                try:
                    p.fetch(fname)
                    total += 1
                except Exception as exc:
                    print(f"    WARNING: could not fetch {fname}: {exc}", flush=True)
                    errors += 1

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


def cache_populate(tag: str | None, from_path: str | None, clone_url: str, flavor: str):
    """Bulk-populate the pooch caches from a McCode git tag or a local checkout."""
    import os
    import tempfile
    import subprocess
    import sys

    from mccode_antlr import Flavor

    resolved_flavor = None
    if flavor and flavor.lower() != 'both':
        resolved_flavor = Flavor[flavor.upper()]

    # Resolve the tag to use (default: currently-configured version)
    if tag is None:
        from mccode_antlr.reader.registry import _source_registry_tag
        _, _, version = _source_registry_tag()
        tag = f'v{version}'

    # Ensure the environment variable is set so _source_registry_tag() resolves
    # to the requested tag for *this* process.
    os.environ.setdefault('MCCODEANTLR_MCCODE_POOCH__TAG', tag)

    print(f"Populating pooch caches for McCode {tag} …", flush=True)

    if from_path is not None:
        src = Path(from_path).resolve()
        if not src.is_dir():
            print(f"ERROR: --from-path {src} does not exist or is not a directory.", flush=True)
            sys.exit(1)
        print(f"Using local checkout: {src}", flush=True)
        total, errors = populate_from_clone(src, tag, flavor=resolved_flavor)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / 'McCode'
            print(f"Cloning {clone_url} at {tag} …", flush=True)
            subprocess.run(
                ['git', 'clone', '--depth=1', '-c', 'core.autocrlf=false',
                 '--branch', tag, '--', clone_url, str(dest)],
                check=True,
            )
            total, errors = populate_from_clone(dest, tag, flavor=resolved_flavor)

    print(f"\nDone. {total} files cached, {errors} errors.", flush=True)
    if errors:
        sys.exit(1)


# ---------------------------------------------------------------------------
# Component IR cache helpers
# ---------------------------------------------------------------------------

def _iter_ir_files(root: Path):
    """Yield all ``*.comp.json`` paths under *root*."""
    return root.rglob('*.comp.json')


def _is_stale(json_path: Path) -> bool:
    """Return True if the sibling ``.comp`` file is newer than *json_path*."""
    comp_path = json_path.with_suffix('')  # removes .json → .comp
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
    print(f'\n{len(files)} .comp.json file(s) found under {root}')


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
        print(f"No {description} .comp.json files to remove.")
        return

    if not force:
        response = input(f'Remove {len(targets)} {description} .comp.json file(s)? [yN] ')
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

    print(f'Removed {removed} .comp.json file(s).')


# ---------------------------------------------------------------------------
# Argument-parser wiring
# ---------------------------------------------------------------------------

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
        help='McCode version tag (e.g. v3.5.31); defaults to the currently-configured version',
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
        '--flavor', default='both', choices=['mcstas', 'mcxtrace', 'both'],
        help="Which flavor's registries to populate (default: both)",
    )
    p.set_defaults(action=cache_populate)

    # -- ir-list --
    il = actions.add_parser(
        name='ir-list',
        help='List component IR cache files (*.comp.json) under the cache root',
    )
    il.add_argument('-l', '--long', action='store_true',
                    help='Show full path, size, and stale status')
    il.set_defaults(action=cache_ir_list)

    # -- ir-clean --
    ic = actions.add_parser(
        name='ir-clean',
        help='Delete component IR cache files (*.comp.json) under the cache root',
    )
    ic.add_argument(
        '--stale', action='store_true',
        help='Only remove files whose sibling .comp is newer (stale entries)',
    )
    ic.add_argument('-f', '--force', action='store_true',
                    help='Skip confirmation prompt')
    ic.set_defaults(action=cache_ir_clean)

    return actions

"""CLI sub-commands for working with McCode data files (Bragg tables, SQW files, etc.).

Data files are registered in Pooch-backed remote registries (e.g. under ``mcstas-comps/data/``
or ``mcxtrace-comps/data/``).  Components reference them by bare filename at *C runtime*, so
they must be discoverable on the McCode search path when the compiled instrument runs.

Sub-commands
------------
list   -- list available data files for a given flavor
fetch  -- populate the local Pooch cache for a named file (no copy)
get    -- populate the local Pooch cache *and* copy the file to a directory
"""
from __future__ import annotations

from pathlib import Path


def _is_data_file(registry_filename: str) -> bool:
    """Return True if the registry path sits inside a ``data/`` directory."""
    return 'data/' in registry_filename.replace('\\', '/')


def _data_registries(flavor_name: str):
    """Return default registries for *flavor_name* that contain data files."""
    from mccode_antlr import Flavor
    from mccode_antlr.reader.registry import default_registries
    flavor = Flavor[flavor_name.upper()]
    return default_registries(flavor)


def datafile_list(flavor: str, pattern: str | None):
    """List data files available in the registries for *flavor*."""
    import re
    registries = _data_registries(flavor)
    regex = re.compile(pattern, re.IGNORECASE) if pattern else None
    found = False
    for reg in registries:
        names = [n for n in reg.filenames() if _is_data_file(n)]
        if regex is not None:
            names = [n for n in names if regex.search(n)]
        for name in sorted(names):
            print(name)
            found = True
    if not found:
        msg = f'No data files found for flavor {flavor!r}'
        if pattern:
            msg += f' matching {pattern!r}'
        print(msg)


def _fetch_one(name: str, flavor: str) -> Path:
    """Fetch *name* into the Pooch cache and return the local path."""
    from mccode_antlr.reader.registry import ordered_registries
    registries = ordered_registries(_data_registries(flavor))
    for reg in registries:
        if reg.known(name):
            return reg.path(name)
    raise FileNotFoundError(
        f"Data file {name!r} not found in any {flavor} registry.\n"
        f"Use 'mccode-antlr datafile list --flavor {flavor}' to see available files."
    )


def datafile_fetch(name: str, flavor: str):
    """Populate the local Pooch cache for *name* and print the cache path."""
    cached = _fetch_one(name, flavor)
    print(cached)


def datafile_get(name: str, flavor: str, output: str | None):
    """Fetch *name* and copy it to *output* directory (default: current working directory)."""
    import shutil
    cached = _fetch_one(name, flavor)
    dest_dir = Path(output) if output else Path.cwd()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / cached.name
    shutil.copy2(cached, dest)
    print(dest)


# ---------------------------------------------------------------------------
# Argument-parser wiring
# ---------------------------------------------------------------------------

def add_datafile_management_parser(modes):
    parser = modes.add_parser(
        name='datafile',
        help='Work with McCode data files (Bragg tables, SQW files, …)',
    )
    actions = parser.add_subparsers(
        help='Action to perform', metavar='ACTION', required=True,
    )

    # -- list --
    p_list = actions.add_parser(
        name='list',
        help='List available data files for a flavor',
    )
    p_list.add_argument(
        'pattern', nargs='?',
        help='Optional regex pattern to filter file names',
    )
    p_list.add_argument(
        '--flavor', default='mcstas', choices=['mcstas', 'mcxtrace'],
        help='McCode flavor (default: mcstas)',
    )
    p_list.set_defaults(action=datafile_list)

    # -- fetch --
    p_fetch = actions.add_parser(
        name='fetch',
        help='Download a data file into the local Pooch cache (no copy)',
    )
    p_fetch.add_argument('name', help='Data file name (e.g. Al.laz)')
    p_fetch.add_argument(
        '--flavor', default='mcstas', choices=['mcstas', 'mcxtrace'],
        help='McCode flavor (default: mcstas)',
    )
    p_fetch.set_defaults(action=datafile_fetch)

    # -- get --
    p_get = actions.add_parser(
        name='get',
        help='Download a data file and copy it to a directory',
    )
    p_get.add_argument('name', help='Data file name (e.g. Al.laz)')
    p_get.add_argument(
        '--flavor', default='mcstas', choices=['mcstas', 'mcxtrace'],
        help='McCode flavor (default: mcstas)',
    )
    p_get.add_argument(
        '--output', '-o', default=None,
        help='Destination directory (default: current working directory)',
    )
    p_get.set_defaults(action=datafile_get)

    return actions

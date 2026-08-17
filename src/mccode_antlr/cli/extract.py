from __future__ import annotations

from pathlib import Path


def _default_output_directory(input_path: Path) -> Path:
    return input_path.parent / f'{input_path.stem}.extracted'


_SOURCE_STYLE = {
    'local': 'green',
    'remote': 'cyan',
    'embedded': 'yellow',
    'generated': 'magenta',
}


def _print_manifest(members):
    from rich.console import Console
    from rich.table import Table

    table = Table(box=None, pad_edge=False)
    table.add_column('CATEGORY')
    table.add_column('NAME')
    table.add_column('SOURCE')
    table.add_column('REPOSITORY')
    table.add_column('LOCATION')
    for member in members:
        style = _SOURCE_STYLE.get(member.source, '')
        table.add_row(member.category, member.name, member.source, member.repository,
                      member.repository_match, style=style)
    Console().print(table)


def extract(
        filename: str,
        output: str | None = None,
        flavor: str = 'mcstas',
        search_dir: list[Path] | None = None,
        trust_local_registries: bool | None = None,
        include_remote: bool = False,
        members: list[str] | None = None,
        exclude: list[str] | None = None,
        repository: list[str] | None = None,
        list_only: bool = False,
):
    from types import SimpleNamespace
    from mccode_antlr.cli._common import load_instr
    from mccode_antlr.cli.trust import apply_registry_trust
    from mccode_antlr.io.extract import build_manifest, extract_to_directory, select_members

    apply_registry_trust(SimpleNamespace(trust_local_registries=trust_local_registries))
    source = Path(filename).resolve()
    instr = load_instr(source, flavor, search_dir)

    if list_only:
        manifest = build_manifest(instr, include_remote=include_remote)
        _print_manifest(select_members(manifest, members or None, exclude, repository=repository))
        return

    destination = Path(output).resolve() if output is not None else _default_output_directory(source)
    extract_to_directory(
        instr, destination, include_remote=include_remote, select=members or None, exclude=exclude,
        repository=repository,
    )

    print(destination)


def add_extract_management_parser(modes):
    from argparse import BooleanOptionalAction
    parser = modes.add_parser(
        name='extract',
        help='Reconstitute a portable instrument (.instr or .json) into a directory',
    )
    parser.add_argument(
        'filename',
        type=str,
        help='Input file path (.instr or .json)',
    )
    parser.add_argument(
        'members',
        nargs='*',
        default=[],
        help='Only extract files matching these glob patterns (default: extract everything). '
             'Naming a remote-sourced file here extracts it even without --include-remote.',
    )
    parser.add_argument(
        '-o', '--output',
        default=None,
        help='Output directory (if omitted, inferred from the input filename)',
    )
    parser.add_argument(
        '--flavor',
        default='mcstas',
        choices=['mcstas', 'mcxtrace'],
        help='Flavor used when loading .instr input (default: mcstas)',
    )
    parser.add_argument(
        '-I', '--search-dir',
        action='append',
        type=lambda name: Path(name).resolve(),
        help='Extra component search directory for .instr input',
    )
    parser.add_argument(
        '--trust-local-registries',
        action=BooleanOptionalAction,
        default=None,
        help='Trust local registries from a serialized instrument',
    )
    parser.add_argument(
        '--include-remote',
        action=BooleanOptionalAction,
        default=False,
        help='Also extract component definitions and dependency files available '
             'from a remote registry, for a fully self-contained bundle',
    )
    parser.add_argument(
        '-x', '--exclude',
        action='append',
        default=None,
        help='Glob pattern to omit from extraction (repeatable)',
    )
    parser.add_argument(
        '-r', '--repository',
        action='append',
        default=None,
        help="Glob pattern to filter by source repository (repeatable). Matches a "
             "remote registry's URL (e.g. '*/mcdotstar/*' matches "
             "https://github.com/mcdotstar/...), a local registry's root path, or "
             "an embedded registry's name. Naming a repository extracts/lists its "
             "files even without --include-remote, like positional members.",
    )
    parser.add_argument(
        '-l', '--list',
        dest='list_only',
        action='store_true',
        help='List the files this invocation would extract, with their category, source, and '
             'repository, without writing anything; -o/--output is ignored',
    )
    parser.set_defaults(action=extract)
    return parser

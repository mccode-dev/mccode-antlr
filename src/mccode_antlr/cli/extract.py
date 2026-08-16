from __future__ import annotations

from pathlib import Path


def _default_output_directory(input_path: Path) -> Path:
    return input_path.parent / f'{input_path.stem}.extracted'


def extract(
        filename: str,
        output: str | None = None,
        flavor: str = 'mcstas',
        search_dir: list[Path] | None = None,
        trust_local_registries: bool | None = None,
        include_remote: bool = False,
        members: list[str] | None = None,
        exclude: list[str] | None = None,
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
        for member in select_members(manifest, members or None, exclude):
            print(f'{member.category:<10} {member.name:<30} ({member.source})')
        return

    destination = Path(output).resolve() if output is not None else _default_output_directory(source)
    extract_to_directory(
        instr, destination, include_remote=include_remote, select=members or None, exclude=exclude,
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
        '-l', '--list',
        dest='list_only',
        action='store_true',
        help='List the files this invocation would extract, with their category and source, '
             'without writing anything; -o/--output is ignored',
    )
    parser.set_defaults(action=extract)
    return parser

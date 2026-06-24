from __future__ import annotations

from pathlib import Path

from mccode_antlr import Flavor
from mccode_antlr.instr import Instr


_TARGET_EXTENSION = {
    'python': '.py',
    'json': '.json',
    'instr': '.instr',
}


def _resolve_target(to: str | None, output: str | None) -> str:
    if to is not None:
        target = to.lower()
    elif output is not None:
        target = {
            '.py': 'python',
            '.json': 'json',
            '.instr': 'instr',
        }.get(Path(output).suffix.lower(), 'python')
    else:
        target = 'python'
    if target not in _TARGET_EXTENSION:
        raise ValueError(f'Unknown conversion target {target!r}')
    return target


def _default_output_path(input_path: Path, target: str) -> Path:
    suffix = _TARGET_EXTENSION[target]
    if input_path.suffix.lower() == suffix:
        return input_path.with_name(f'{input_path.stem}.converted{suffix}')
    return input_path.with_suffix(suffix)


def _load_instr(path: Path, flavor: str, search_dir: list[Path] | None):
    if path.suffix.lower() == '.json':
        from mccode_antlr.io.json import load_json
        instr = load_json(path)
    elif path.suffix.lower() == '.instr':
        from mccode_antlr.reader import Reader, collect_local_registries
        registries = collect_local_registries(Flavor[flavor.upper()], search_dir)
        instr = Reader(registries=registries).get_instrument(path)
    else:
        raise ValueError(f"Unsupported input file type {path.suffix!r}; expected .instr or .json")
    if not isinstance(instr, Instr):
        raise RuntimeError(f'Input {path} did not resolve to an Instr object')
    return instr


def convert(
        filename: str,
        output: str | None = None,
        to: str | None = None,
        optimize: bool = False,
        flavor: str = 'mcstas',
        search_dir: list[Path] | None = None,
):
    source = Path(filename).resolve()
    target = _resolve_target(to, output)

    if optimize:
        raise NotImplementedError('--optimize is only supported by the future optimized Python exporter.')

    destination = Path(output).resolve() if output is not None else _default_output_path(source, target)

    instr = _load_instr(source, flavor, search_dir)

    if target == 'python':
        from mccode_antlr.export import save_instr_as_python
        save_instr_as_python(instr, destination)
    elif target == 'json':
        from mccode_antlr.io.json import save_json
        save_json(instr, destination)
    elif target == 'instr':
        with destination.open('w') as f:
            instr.to_file(output=f)
    else:
        raise ValueError(f'No output logic for target {target!r}')

    print(destination)


def add_convert_management_parser(modes):
    parser = modes.add_parser(
        name='convert',
        help='Convert instrument descriptions between file formats',
    )
    parser.add_argument(
        'filename',
        type=str,
        help='Input file path (.instr or .json)',
    )
    parser.add_argument(
        '-o', '--output',
        default=None,
        help='Output filename (if omitted, inferred from input and target)',
    )
    parser.add_argument(
        '--to',
        default=None,
        choices=['python', 'json', 'instr'],
        help='Target format (default: infer from --output extension, else python)',
    )
    parser.add_argument(
        '--optimize',
        action='store_true',
        help='Enable optimization of generated Python output (future)',
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
        type=Path,
        help='Extra component search directory for .instr input',
    )
    parser.set_defaults(action=convert)
    return parser

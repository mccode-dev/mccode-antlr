"""Compile-only CLI entry points for McCode (McStas / McXtrace) instruments.

``mcc-antlr``  – compile for McStas
``mxc-antlr``  – compile for McXtrace

Accepts ``.instr``, ``.json``, ``.h5`` (Instr objects), or pre-generated ``.c``
files and produces a compiled binary without running it.
"""
from __future__ import annotations


def compile_script_parser(prog: str):
    from argparse import ArgumentParser, BooleanOptionalAction
    from pathlib import Path
    from mccode_antlr import __version__

    def resolvable(name: str):
        return None if name is None else Path(name).resolve()

    parser = ArgumentParser(
        prog=prog,
        description=(
            f'Compile McCode instrument files to C binaries using {prog}.\n'
            'Accepts .instr, .json, .h5, or pre-generated .c files.'
        ),
    )
    aa = parser.add_argument

    aa('filename', type=resolvable, nargs=1, help='.instr / .json / .h5 / .c file to compile')
    aa('-v', '--version', action='version', version=__version__)
    aa('-o', '--output', type=resolvable, default=None,
       help='Output path for the compiled binary (file or directory; defaults to CWD)')
    aa('-I', '--search-dir', action='append', type=resolvable, dest='search_dir',
       help='Extra component search directory (may be given more than once)')
    aa('-t', '--trace', action=BooleanOptionalAction, default=True,
       help="Enable 'trace' mode for instrument display (default: on)")
    aa('--source', action=BooleanOptionalAction, default=False,
       help='Embed the instrument source code in the executable')
    aa('--verbose', action=BooleanOptionalAction, default=False,
       help='Verbose compiler/linker output')
    aa('--parallel', action='store_true', default=False,
       help='Use MPI multi-process parallelism')
    aa('--gpu', action='store_true', default=False,
       help='Use GPU OpenACC parallelism')
    aa('--nexus', action='store_true', default=False,
       help='Enable NeXus output support')
    aa('-c', '--dump-source', action='store_true', default=False, dest='dump_source',
       help='Keep the generated C source file alongside the binary')

    return parser


def mccode_compile_cmd(flavor, prog: str | None = None):
    """Entry point implementation shared by mcstas_compile and mcxtrace_compile."""
    import sys
    from pathlib import Path
    from os import R_OK, access
    from mccode_antlr import Flavor

    if prog is None:
        prog = str(flavor).lower() + 'c'
    args = compile_script_parser(prog).parse_args()
    filename: Path = args.filename if isinstance(args.filename, Path) else next(iter(args.filename))
    if not isinstance(filename, Path):
        raise ValueError(f'{filename} should be a Path but is {type(filename)}')

    if not filename.exists() or not access(filename, R_OK):
        print(f'Error: {filename} does not exist or is not readable', file=sys.stderr)
        sys.exit(1)

    output: Path | None = args.output  # may be None, a file, or a directory

    target_kwargs = dict(
        mpi=args.parallel,
        acc=args.gpu,
        count=1,
        nexus=args.nexus,
    )

    suffix = filename.suffix.lower()

    if suffix == '.c':
        # Pre-generated C file – compile directly without reading an Instr object.
        from mccode_antlr.compiler.c import CBinaryTarget, compile_c_file

        target = CBinaryTarget(**target_kwargs)
        binary = compile_c_file(filename, target, output=output or Path(), replace=True)
        print(f'Compiled binary: {binary}')

    else:
        # .instr / .json / .h5 – build an Instr object first, then compile.
        from mccode_antlr.reader.registry import collect_local_registries
        from mccode_antlr.run.runner import mccode_compile

        if suffix == '.h5':
            from mccode_antlr.io import load_hdf5
            instrument = load_hdf5(filename)
        elif suffix == '.json':
            from mccode_antlr.io.json import load_json
            instrument = load_json(filename)
        else:
            from mccode_antlr.reader import Reader
            reader = Reader(registries=collect_local_registries(flavor, args.search_dir))
            instrument = reader.get_instrument(filename)

        # Determine binary destination.
        if output is None:
            binary_path = Path() / instrument.name
        elif output.is_dir():
            binary_path = output / instrument.name
        else:
            binary_path = output

        config = dict(
            enable_trace=args.trace,
            embed_instrument_file=args.source,
            verbose=args.verbose,
            output=filename.with_suffix('.c') if args.dump_source else None,
        )
        binary, _ = mccode_compile(
            instrument,
            binary_path,
            flavor=flavor,
            target=target_kwargs,
            config=config,
            dump_source=args.dump_source,
        )
        print(f'Compiled binary: {binary}')


def mcstas_compile():
    from mccode_antlr import Flavor
    mccode_compile_cmd(Flavor.MCSTAS, prog='mcc-antlr')


def mcxtrace_compile():
    from mccode_antlr import Flavor
    mccode_compile_cmd(Flavor.MCXTRACE, prog='mxc-antlr')

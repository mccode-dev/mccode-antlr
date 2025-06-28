from __future__ import annotations
from pathlib import Path
from mccode_antlr import Flavor
from mccode_antlr.instr import Instr

def regular_mccode_runtime_dict(args: dict) -> dict:
    def insert_best_of(src: dict, snk: dict, names: tuple):
        def get_best_of():
            for name in names:
                if name in src:
                    return src[name]
            raise RuntimeError(f"None of {names} found in {src}")

        if any(x in src for x in names):
            snk[names[0]] = get_best_of()
        return snk

    t = insert_best_of(args, {}, ('seed', 's'))
    t = insert_best_of(args, t, ('ncount', 'n'))
    t = insert_best_of(args, t, ('dir', 'out_dir', 'd'))
    t = insert_best_of(args, t, ('trace', 't'))
    t = insert_best_of(args, t, ('gravitation', 'g'))
    t = insert_best_of(args, t, ('bufsiz',))
    t = insert_best_of(args, t, ('format',))
    return t


def mccode_runtime_dict_to_args_list(args: dict) -> list[str]:
    """Convert a dictionary of McCode runtime arguments to a string.

    :parameter args: A dictionary of McCode runtime arguments.
    :return: A list of arguments suitable for use in a command line call to a McCode compiled instrument.
    """
    # convert to a standardized string:
    out = []
    if 'seed' in args and args['seed'] is not None:
        out.append(f'--seed={args["seed"]}')
    if 'ncount' in args and args['ncount'] is not None:
        out.append(f'--ncount={args["ncount"]}')
    if 'dir' in args and args['dir'] is not None:
        out.append(f'--dir={args["dir"]}')
    if 'trace' in args and args['trace']:
        out.append('--trace')
    if 'gravitation' in args and args['gravitation']:
        out.append('--gravitation')
    if 'bufsiz' in args and args['bufsiz'] is not None:
        out.append(f'--bufsiz={args["bufsiz"]}')
    if 'format' in args and args['format'] is not None:
        out.append(f'--format={args["format"]}')
    return out


def mccode_runtime_parameters(args: dict, params: dict) -> str:
    first = ' '.join(mccode_runtime_dict_to_args_list(args))
    second = ' '.join(f'{k}={v}' for k, v in params.items())
    return f'{first} {second}'


def sort_args(args: list[str]) -> list[str]:
    """Take the list of arguments and sort them into the correct order for McCode run."""
    # TODO this is a bit of a hack, but it works for now
    first, last = [], []
    k = 0
    while k < len(args):
        if args[k].startswith('-'):
            first.append(args[k])
            k += 1
            if '=' not in first[-1] and k < len(args) and not args[k].startswith('-') and '=' not in args[k]:
                first.append(args[k])
                k += 1
        else:
            last.append(args[k])
            k += 1
    return first + last


def si_int(s: str) -> int:
    from loguru import logger
    suffix_value = {
        'k': 1000, 'M': 10 ** 6, 'G': 10 ** 9, 'T': 10 ** 12, 'P': 10 ** 15,
        'Ki': 2 ** 10, 'Mi': 2 ** 20, 'Gi': 2 ** 30, 'Ti': 2 ** 40, 'Pi': 2 ** 50
    }
    def int_mult(x: str, mult: int = 1):
        return int(x) * mult if x.isnumeric() else int(float(x) * mult)

    def do_parse():
        try:
            if suffix := next(k for k in suffix_value if s.endswith(k)):
                return int_mult(s[:-len(suffix)].strip(),  suffix_value[suffix])
        except StopIteration:
            pass
        return int_mult(s)
    value = do_parse()
    if value < 0:
        logger.info('Negative value encountered')
    elif value > 2**53:
        logger.info(
            'McStas/McXtrace parse integer inputs as doubles,'
            f' this requested {value=} will not be evaluated precisely'
            ' since it is more than 2^53'
        )
    return value


def mccode_run_script_parser(prog: str):
    from argparse import ArgumentParser, BooleanOptionalAction
    from pathlib import Path
    from mccode_antlr import __version__

    def resolvable(name: str):
        return None if name is None else Path(name).resolve()

    parser = ArgumentParser(prog=prog, description=f'Convert and run mccode_antlr-3 instr and comp files to {prog} runtime in C')
    aa = parser.add_argument

    aa('filename', type=resolvable, nargs=1, help='.instr file name to be converted')
    aa('parameters', nargs='*', help='Parameters to be passed to the instrument', type=str, default=None)
    aa('-v', '--version', action='version', version=__version__)
    aa('-o', '--output-file', type=str, help='Output filename for C runtime binary', default=None)
    aa('-d', '--directory', type=str, help='Output directory for C runtime artifacts')
    aa('-I', '--search-dir', action='append', type=resolvable, help='Extra component search directory')
    aa('-t', '--trace', action=BooleanOptionalAction, default=True, help="Enable 'trace' mode for instrument display")
    aa('--copyright', action='store_true', help='Print the McCode copyright statement')
    aa('--source', action=BooleanOptionalAction, default=False, help='Embed the instrument source code in the executable')
    aa('--verbose', action=BooleanOptionalAction, default=False, help='Verbose output')
    aa('-n', '--ncount', nargs=1, type=si_int, default=None, help='Number of neutrons to simulate')
    aa('-m', '--mesh', action='store_true', default=False, help='N-dimensional mesh scan')
    aa('-s', '--seed', nargs=1, type=int, default=None, help='Random number generator seed')
    aa('-g', '--gravitation', action='store_true', default=False,
       help='Enable gravitation for all trajectories')
    aa('--bufsiz', nargs=1, type=si_int, default=None, help='Monitor_nD list/buffer-size')
    aa('--format', nargs=1, type=str, default=None, help='Output data files using FORMAT')
    aa('--dryrun', action='store_true', default=False,
       help='Do not run any simulations, just print the commands')
    aa('--parallel', action='store_true', default=False, help='Use MPI multi-process parallelism')
    aa('--gpu', action='store_true', default=False, help='Use GPU OpenACC parallelism')
    aa('--process-count', nargs=1, type=int, default=0, help='MPI process count, 0 == System Default')

    return parser


def print_version_information():
    from mccode_antlr.version import version
    print(f'mccode_antlr code generator version {version()}')
    print(' Copyright (c) European Spallation Source ERIC, 2023-2024')
    print('Based on McStas/McXtrace version 3')
    print(' Copyright (c) DTU Physics and Risoe National Laboratory, 1997-2023')
    print(' Additions (c) Institut Laue Langevin, 2003-2019')
    print('All rights reserved\n\nComponents are (c) their authors, see component headers.')


def parse_mccode_run_script(prog: str):
    import sys
    from .range import parse_scan_parameters
    sys.argv[1:] = sort_args(sys.argv[1:])
    args = mccode_run_script_parser(prog).parse_args()
    parameters = parse_scan_parameters(args.parameters)
    return args, parameters


def mccode_compile(instr, directory, flavor: Flavor, target: dict | None = None, config: dict | None = None, **kwargs):
    from mccode_antlr.compiler.c import compile_instrument, CBinaryTarget
    from loguru import logger

    def_target = CBinaryTarget(mpi=False, acc=False, count=1, nexus=False)
    def_config = dict(default_main=True, enable_trace=False, portable=False, include_runtime=True,
                      embed_instrument_file=False, verbose=False)
    def_config.update(config or {})
    def_target.update(target or {})

    try:
        binary = compile_instrument(instr, def_target, directory, flavor=flavor, config=def_config, **kwargs)
    except RuntimeError as compilation_error:
        logger.error(f'Failed to compile instrument: {compilation_error}')
        raise compilation_error

    return binary, def_target


def mccode_run_compiled(binary, target, directory: Path | str, parameters: str, capture: bool = True, dry_run: bool = False):
    from mccode_antlr.compiler.c import run_compiled_instrument
    from mccode_antlr.loader import read_mccode_dat
    from pathlib import Path

    result = run_compiled_instrument(binary, target, f'--dir {directory} {parameters}', capture=capture, dry_run=dry_run)
    sim_files = list(Path(directory).glob('**/*.dat'))
    dats = {file.stem: read_mccode_dat(file) for file in sim_files}
    return result, dats


def mccode_run_scan(name: str, binary, target, parameters, directory, grid: bool, capture: bool = True, dry_run: bool = False, **r_args):
    from .range import parameters_to_scan
    n_pts, names, scan = parameters_to_scan(parameters, grid=grid)
    # n_zeros = len(str(n_pts))

    args = regular_mccode_runtime_dict(r_args)

    if directory is None:
        from datetime import datetime
        directory = Path(f'{name}{datetime.now().strftime("%Y%m%d_%H%M%S")}')

    # if there is only one point, we don't need to scan
    if n_pts > 1:
        directory.mkdir(parents=True, exist_ok=True)
        results = []
        for number, values in enumerate(scan):
            # TODO Use the following line instead of the one after it when McCode is fixed to use zero-padded folder names
            # # runtime_arguments['dir'] = args["dir"].joinpath(str(number).zfill(n_zeros))
            this_directory = directory.joinpath(str(number))
            pars = mccode_runtime_parameters(r_args, parameters)
            r, d = mccode_run_compiled(binary, target, this_directory, pars, capture=capture, dry_run=dry_run)
            results.append((r, d))
        return results
    else:
        directory.parent.mkdir(parents=True, exist_ok=True)
        print(parameters)
        pars = mccode_runtime_parameters(args, parameters)
        return mccode_run_compiled(binary, target, directory, pars, capture=capture, dry_run=dry_run)


def mccode_run(instrument: Instr,
               flavor: Flavor,
               parameters, directory: str | Path,
               binary_name: str | None = None,
               trace: bool = False, source: bool = False, verbose: bool = False,
               parallel: bool = False, gpu: bool = False, process_count: int = 0,
               mesh: bool = False, seed: int | None = None, ncount: int | None = None,
               gravitation: bool | None = None, bufsize: int | None = None, dryrun: bool = False, fmt: str | None = None,
               ):
    from os import access, R_OK
    from datetime import datetime
    if not isinstance(directory, Path):
        directory = Path(directory)
    if binary_name is not None:
        binary_path = directory.joinpath(binary_name)
    else:
        binary_path = directory.joinpath(instrument.name)

    if binary_path.exists() and not access(binary_path, R_OK):
        raise ValueError(f"{binary_path} exists but is not an executable")

    target = {'mpi': parallel, 'acc': gpu, 'count': process_count, 'nexus': False}
    if not binary_path.exists():
        config = {'enable_trace': trace, 'embed_instrument_file': source, 'verbose': verbose}
        binary_path, target = mccode_compile(instrument, binary_path, flavor=flavor, target=target, config=config)

    runtime = dict(
        seed=seed,
        ncount=ncount,
        trace=trace,
        gravitation=gravitation,
        bufsiz=bufsize,
        format=fmt,
        dry_run=dryrun,
        capture=(not verbose) if verbose is not None else False,
    )
    out_dir = directory.joinpath(f'{instrument.name}{datetime.now().strftime("%Y%m%d_%H%M%S")}')

    mccode_run_scan(instrument.name, binary_path, target, parameters, out_dir, mesh, **runtime)


def mccode_run_cmd(flavor: Flavor):
    from pathlib import Path
    from mccode_antlr.reader import Reader
    from mccode_antlr.reader.registry import collect_local_registries
    from os import X_OK, R_OK, access

    args, parameters = parse_mccode_run_script(str(flavor).lower())
    filename = args.filename if isinstance(args.filename, Path) else next(iter(args.filename))
    if not isinstance(filename, Path):
        raise ValueError(f'{filename} should be a Path but is {type(filename)}')
    config = dict(
        enable_trace=args.trace,
        embed_instrument_file=args.source,
        verbose=args.verbose,
        output=args.output_file if args.output_file is not None else filename.with_suffix('.c')
    )
    target = dict(
        mpi=args.parallel,
        acc=args.gpu,
        count=args.process_count,
        nexus=False
    )
    runtime = dict(
        seed=args.seed[0] if args.seed is not None else None,
        ncount=args.ncount[0] if args.ncount is not None else None,
        trace=args.trace,
        gravitation=args.gravitation,
        bufsiz=args.bufsiz[0] if args.bufsiz is not None else None,
        format=args.format[0] if args.format is not None else None,
        dry_run=args.dryrun,
        capture=(not args.verbose) if args.verbose is not None else False,
    )
    # check if the filename is actually a compiled instrument already:
    if args.output_file is None and filename.exists() and access(filename, X_OK):
        binary = filename
        name = filename.stem
    elif not filename.exists() or not access(filename, R_OK):
        raise RuntimeError(f'{filename} does not exist or is not readable')
    else:
        if filename.suffix.lower() == '.h5':
            from mccode_antlr.io import load_hdf5
            instrument = load_hdf5(filename)
        else:
            # Construct the object which will read the instrument and component files, producing Python objects
            reader = Reader(registries=collect_local_registries(flavor, args.search_dir))
            # Read the provided .instr file, including all specified .instr and .comp files along the way
            instrument = reader.get_instrument(filename)
        name = instrument.name
        # Generate the C binary for the instrument -- will output to, e.g., {instrument.name}.out, in the current directory
        # unless if output_file was specified
        binary, target = mccode_compile(instrument, args.output_file, flavor=flavor, target=target, config=config)

    if not len(parameters):
        from loguru import logger
        logger.error("Interactive parameter entry does not currently work")
        logger.info(f"Execute `{binary} --list-parameters` to check expected parameters")
        return

    mccode_run_scan(name, binary, target, parameters, args.directory, args.mesh, **runtime)


def mcstas_cmd():
    mccode_run_cmd(Flavor.MCSTAS)


def mcxtrace_cmd():
    mccode_run_cmd(Flavor.MCXTRACE)


def mcstas_run(instrument, parameters, directory, **kwargs):
    mccode_run(instrument, Flavor.MCSTAS, parameters, directory, **kwargs)


def mcxtrace_run(instrument, parameters, directory, **kwargs):
    mccode_run(instrument, Flavor.MCXTRACE, parameters, directory, **kwargs)

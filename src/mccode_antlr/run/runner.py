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


def mpi_process_count(s: str):
    """Parse an MPI process count: a positive integer, or 'auto'.

    'auto' leaves the choice to the launcher rather than naming a number. Values
    below one are accepted as synonyms for it, so that scripts written against
    the old `--process-count 0` ("system default") keep working.
    """
    from argparse import ArgumentTypeError
    text = str(s).strip().lower()
    if text == 'auto':
        return 'auto'
    try:
        count = int(text)
    except ValueError:
        raise ArgumentTypeError(f"expected a positive integer or 'auto', not {s!r}")
    return count if count >= 1 else 'auto'


def mccode_run_script_parser(prog: str):
    from argparse import ArgumentParser, BooleanOptionalAction
    from pathlib import Path
    from mccode_antlr import __version__
    from mccode_antlr.compiler.c import CAPTURE_MODES

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
    # This one flag drives both the compile-time trace support (MC_TRACE_ENABLED)
    # and the runtime --trace argument. Tracing every particle at every component
    # costs kilobytes of output per particle, which under MPI is funnelled through
    # the launcher and then captured here -- around 90x slower on a real
    # instrument -- so it is off unless asked for, as it is in classic mcrun.
    aa('-t', '--trace', action=BooleanOptionalAction, default=False,
       help="Trace particles through the instrument: compiles in trace support"
            " and enables it at runtime (default: off)")
    aa('--copyright', action='store_true', help='Print the McCode copyright statement')
    aa('--source', action=BooleanOptionalAction, default=False, help='Embed the instrument source code in the executable')
    aa('--verbose', action=BooleanOptionalAction, default=False,
       help='Verbose compiler and linker output')
    aa('--capture', choices=CAPTURE_MODES, default='no',
       help="What to do with the simulation's own output: stream it to the terminal"
            " ('no', the default), keep it hidden unless the run fails ('yes'), or"
            " stream it and also save it as <output directory>/mccode.out ('tee')")
    aa('-n', '--ncount', nargs=1, type=si_int, default=None, help='Number of neutrons to simulate')
    aa('-m', '--mesh', action='store_true', default=False, help='N-dimensional mesh scan')
    aa('-s', '--seed', nargs=1, type=int, default=None, help='Random number generator seed')
    aa('-g', '--gravitation', action='store_true', default=False,
       help='Enable gravitation for all trajectories')
    aa('--bufsiz', nargs=1, type=si_int, default=None, help='Monitor_nD list/buffer-size')
    aa('--format', nargs=1, type=str, default=None, help='Output data files using FORMAT')
    aa('--dryrun', action='store_true', default=False,
       help='Do not run any simulations, just print the commands')
    aa('-y', '--yes', action='store_true', default=False,
       help='Assume default values for all instrument parameters not explicitly specified')
    # Tri-state on purpose: None means 'not specified', so that a value read from
    # an already-compiled binary can fill it in without overriding an explicit choice
    aa('--parallel', action=BooleanOptionalAction, default=None,
       help='Use MPI multi-process parallelism')
    aa('--gpu', action=BooleanOptionalAction, default=None,
       help='Use GPU OpenACC parallelism')
    # nargs is deliberately absent: with nargs=1 this arrived as [4] rather than 4
    # and reached mpirun as '-np [4]'.
    aa('--mpi', '--process-count', dest='mpi', metavar='NB_CPU',
       type=mpi_process_count, default='auto',
       help="Number of MPI processes, or 'auto' to let the launcher decide"
            " (default: auto). --process-count is an alias.")
    aa('--build-info', action='store_true', default=False,
       help='Print what a compiled instrument binary was built from and with, then exit')
    aa('--trust-local-registries', action=BooleanOptionalAction, default=None,
       help='Trust local registries from a serialized instrument')

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


def print_binary_build_info(binary: Path) -> int:
    """Report what a compiled binary was built from and with; the --build-info flag."""
    import json
    from mccode_antlr.build_info import probe_binary, read_build_info
    info = read_build_info(binary)
    if info is not None:
        print(json.dumps(info, indent=2))
        return 0
    probe = probe_binary(binary)
    if probe.known:
        print(f'{binary} carries no mccode-antlr build information.')
        print(f'Inferred from {probe.origin}: mpi={probe.mpi} acc={probe.acc}')
        return 0
    print(f'Nothing could be determined about {binary}.')
    return 1


def resolve_target_flag(flag: str, name: str, requested, detected, binary) -> bool:
    """Reconcile an explicit CLI target flag with what a compiled binary reports.

    *requested* is None when the flag was not given at all, which is what lets an
    unspecified flag take the binary's value without a value of False -- which the
    user may well have meant -- being silently overridden.
    """
    from loguru import logger
    if requested is None:
        return bool(detected)
    if detected is None or bool(requested) == bool(detected):
        return bool(requested)
    if requested:
        raise RuntimeError(
            f'{flag} was requested but {Path(binary).name} was not built with {name}'
            f' support. Recompile the instrument with {flag}, or drop it.'
        )
    logger.warning(f'{Path(binary).name} was built with {name} support but {flag} was'
                   f' not requested; running without it')
    return False


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


def mccode_run_compiled(
        binary, target, directory: Path | str, parameters: str, capture: bool | str = True,
        dry_run: bool = False, use_defaults: bool = False, tmpdir: Path | None = None
):
    from mccode_antlr.compiler.c import CAPTURE_LOG_NAME, run_compiled_instrument
    from mccode_antlr.run.output import _collect_output
    from pathlib import Path

    yes_flag = '--yes ' if use_defaults else ''
    result = run_compiled_instrument(
        binary, target, f'--dir {directory} {yes_flag}{parameters}', capture=capture,
        dry_run=dry_run, log_file=Path(directory).joinpath(CAPTURE_LOG_NAME)
    )
    return result, _collect_output(Path(directory), tmpdir=tmpdir)


def mccode_run_scan(name: str, binary, target, parameters, directory, grid: bool, capture: bool | str = True, dry_run: bool = False, use_defaults: bool = False, **r_args):
    from .range import parameters_to_scan
    n_pts, names, scan = parameters_to_scan(parameters, grid=grid)
    # n_zeros = len(str(n_pts))

    args = regular_mccode_runtime_dict(r_args)

    if directory is None:
        from datetime import datetime
        directory = Path(f'{name}{datetime.now().strftime("%Y%m%d_%H%M%S")}')
    elif not isinstance(directory, Path):
        directory = Path(directory)

    # if there is only one point, we don't need to scan
    if n_pts > 1:
        directory.mkdir(parents=True, exist_ok=True)
        results = []
        for number, values in enumerate(scan):
            # TODO Use the following line instead of the one after it when McCode is fixed to use zero-padded folder names
            # # runtime_arguments['dir'] = args["dir"].joinpath(str(number).zfill(n_zeros))
            this_directory = directory.joinpath(str(number))
            pars = mccode_runtime_parameters(args, dict(zip(names, values)))
            r, d = mccode_run_compiled(binary, target, this_directory, pars, capture=capture, dry_run=dry_run, use_defaults=use_defaults)
            results.append((r, d))
        return results
    else:
        directory.parent.mkdir(parents=True, exist_ok=True)
        pars = mccode_runtime_parameters(args, parameters)
        return [mccode_run_compiled(binary, target, directory, pars, capture=capture, dry_run=dry_run, use_defaults=use_defaults)]


def mccode_run(instrument: Instr,
               flavor: Flavor,
               parameters, directory: str | Path,
               binary_name: str | None = None,
               trace: bool = False, source: bool = False, verbose: bool = False,
               capture: bool | str = True,
               parallel: bool | None = None, gpu: bool | None = None,
               process_count: int | str = 'auto',
               mesh: bool = False, seed: int | None = None, ncount: int | None = None,
               gravitation: bool | None = None, bufsize: int | None = None, dryrun: bool = False, fmt: str | None = None,
               ):
    from os import access, R_OK
    from datetime import datetime
    from mccode_antlr.compiler.c import CBinaryTarget, binary_path as target_binary_path
    if not isinstance(directory, Path):
        directory = Path(directory)
    target = {'mpi': bool(parallel), 'acc': bool(gpu), 'count': process_count, 'nexus': False}
    binary_path = target_binary_path(directory, binary_name or instrument.name,
                                     CBinaryTarget(**{k: target[k] for k in ('mpi', 'acc', 'nexus')}))

    if binary_path.exists() and not access(binary_path, R_OK):
        raise ValueError(f"{binary_path} exists but is not an executable")

    # Reuse is decided inside compile_instrument, which checks that an existing
    # binary was built from this instrument for this target rather than only that
    # something exists at the path.
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
        capture=capture,
    )
    out_dir = directory.joinpath(f'{instrument.name}{datetime.now().strftime("%Y%m%d_%H%M%S")}')

    return mccode_run_scan(instrument.name, binary_path, target, parameters, out_dir, mesh, **runtime)


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
        count=args.mpi,
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
        capture=args.capture,
        use_defaults=args.yes,
    )
    if args.build_info:
        # non-zero when nothing could be determined, so scripts can branch on it
        raise SystemExit(print_binary_build_info(filename))
    # check if the filename is actually a compiled instrument already:
    # os.access(path, X_OK) always returns True on Windows for any existing file (no POSIX execute bit),
    # so we must also exclude known source-file extensions to avoid treating .instr/.json as binaries.
    _source_suffixes = {'.instr', '.json', '.c'}
    if args.output_file is None and filename.exists() and access(filename, X_OK) \
            and filename.suffix.lower() not in _source_suffixes:
        from mccode_antlr.compiler.c import CBinaryTarget, strip_target_tag
        from mccode_antlr.build_info import probe_binary
        binary = filename
        name = strip_target_tag(filename.stem)
        has_parameters = None  # unknown for a pre-compiled binary
        # The binary may have been compiled elsewhere, so ask it what it is -- but
        # never let that override a choice the user made explicitly.
        probe = probe_binary(binary)
        resolved = {
            'mpi': resolve_target_flag('--parallel', 'MPI', args.parallel, probe.mpi, binary),
            'acc': resolve_target_flag('--gpu', 'OpenACC', args.gpu, probe.acc, binary),
        }
        target = CBinaryTarget(mpi=resolved['mpi'], acc=resolved['acc'],
                               nexus=bool(probe.nexus), count=target.get('count', 1))
    elif not filename.exists() or not access(filename, R_OK):
        raise RuntimeError(f'{filename} does not exist or is not readable')
    else:
        from mccode_antlr.cli.trust import apply_registry_trust
        apply_registry_trust(args)
        if filename.suffix.lower() == '.json':
            from mccode_antlr.io.json import load_json
            from mccode_antlr.reader.registry import with_local_registries
            instrument = with_local_registries(load_json(filename), flavor, args.search_dir)
        else:
            # Construct the object which will read the instrument and component files, producing Python objects
            reader = Reader(registries=collect_local_registries(flavor, args.search_dir))
            # Read the provided .instr file, including all specified .instr and .comp files along the way
            instrument = reader.get_instrument(filename)
        name = instrument.name
        has_parameters = len(instrument.parameters) > 0
        # Generate the C binary for the instrument -- will output to, e.g., {instrument.name}.out, in the current directory
        # unless if output_file was specified
        binary, target = mccode_compile(instrument, args.output_file, flavor=flavor, target=target, config=config)

    if not len(parameters):
        from loguru import logger
        if args.yes:
            # --yes was given: run with --yes so the binary uses all default values
            pass
        elif has_parameters is False:
            # instrument has no parameters at all — safe to run without any
            pass
        else:
            # No parameters, no --yes flag: would enter interactive mode in the binary
            logger.error(
                "No parameters provided. Pass -y/--yes to use instrument default values, "
                "or specify parameters explicitly."
            )
            logger.info(f"Execute `{binary} --list-parameters` to see the expected parameters")
            return

    mccode_run_scan(name, binary, target, parameters, args.directory, args.mesh, **runtime)


def mcstas_cmd():
    mccode_run_cmd(Flavor.MCSTAS)


def mcxtrace_cmd():
    mccode_run_cmd(Flavor.MCXTRACE)


def mcstas_run(instrument, parameters, directory, **kwargs):
    return mccode_run(instrument, Flavor.MCSTAS, parameters, directory, **kwargs)


def mcxtrace_run(instrument, parameters, directory, **kwargs):
    return mccode_run(instrument, Flavor.MCXTRACE, parameters, directory, **kwargs)

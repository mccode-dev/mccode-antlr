from mccode_antlr import Flavor


def mccode_script_parse(prog: str):
    from argparse import ArgumentParser, BooleanOptionalAction
    from pathlib import Path

    def resolvable(name: str):
        return None if name is None else Path(name).resolve()

    parser = ArgumentParser(prog=prog, description=f'Convert mccode_antlr-3 instr and comp files to {prog} runtime in C')
    parser.add_argument('filename', type=resolvable, nargs='?', help='.instr file name to be converted')

    parser.add_argument('-o', '--output-file', type=str, help='Output filename for C runtime file')
    parser.add_argument('-I', '--search-dir', action='append', type=resolvable, help='Extra component search directory')
    parser.add_argument('-t', '--trace', action=BooleanOptionalAction, default=True, help="Enable 'trace' mode for instrument display")
    parser.add_argument('-p', '--portable', action=BooleanOptionalAction, default=False, help='Generate portable output for cross-platform compatibility.')
    parser.add_argument('-v', '--version', action='store_true', help='Print the McCode version')
    parser.add_argument('--source', action=BooleanOptionalAction, default=False, help='Embed the instrument source code in the executable')
    parser.add_argument('--main', action=BooleanOptionalAction, default=True, help='Create main(), --no-main for external embedding')
    parser.add_argument('--runtime', action=BooleanOptionalAction, default=True, help='Embed run-time libraries')
    parser.add_argument('--verbose', action=BooleanOptionalAction, default=False, help='Verbose output during conversion')

    args = parser.parse_args()

    if args.version:
        from sys import exit
        from mccode_antlr.version import version
        print(f'mccode_antlr code generator version {version()}')
        print(' Copyright (c) European Spallation Source ERIC, 2023-2025')
        print('Based on McStas/McXtrace version 3')
        print(' Copyright (c) DTU Physics and Risoe National Laboratory, 1997-2023')
        print(' Additions (c) Institut Laue Langevin, 2003-2019')
        print('All rights reserved\n\nComponents are (c) their authors, see component headers.')
        exit(1)

    if args.filename is None:
        parser.error('No input file provided')

    return args


def mccode(flavor: Flavor):
    args = mccode_script_parse(str(flavor).lower() + '-antlr')
    from mccode_antlr.reader import Reader, collect_local_registries
    from mccode_antlr.translators.c import CTargetVisitor
    from mccode_antlr.common import Mode

    config = dict(default_main=args.main,
                  enable_trace=args.trace,
                  portable=args.portable,
                  include_runtime=args.runtime,
                  embed_instrument_file=args.source,
                  verbose=args.verbose,
                  output=args.output_file if args.output_file is not None else args.filename.with_suffix('.c')
                  )
    if args.filename.suffix.lower() == '.h5':
        from mccode_antlr.io import load_hdf5
        instrument = load_hdf5(args.filename)
    elif args.filename.suffix.lower() == '.json':
        from mccode_antlr.io.json import load_json
        instrument = load_json(args.filename)
    else:
        # Construct the object which will read the instrument and component files, producing Python objects
        reader = Reader(registries=collect_local_registries(flavor, args.search_dir))
        # Read the provided .instr file, including all specified .instr and .comp files along the way
        # In minimal mode, the component orientations are not resolved -- to speed up the process
        instrument = reader.get_instrument(args.filename, mode=Mode.minimal)

    # Construct the object which will translate the Python instrument to C
    visitor = CTargetVisitor(instrument, flavor=flavor, config=config, verbose=config['verbose'])
    # Go through the instrument, finish by writing the output file:
    visitor.save(filename=config['output'])


def mcstas():
    mccode(Flavor.MCSTAS)


def mcxtrace():
    mccode(Flavor.MCXTRACE)

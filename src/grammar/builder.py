from __future__ import annotations

from importlib.metadata import PackageNotFoundError

from loguru import logger
from enum import Enum
from functools import cache

@cache
def antlr4_version(version: str | None = None):
    """Query maven for the most recent antlr4 version.

    Note
    ----
    This method copies part of the antlr4-tools argument parser to allow
    overriding any discovery by specifying an environment variable
    `$ANTLR4_TOOLS_ANTLR_VERSION`. If that environment variable is unset,
    maven is queried for the most up-to-date antlr4 version. If the query
    times out, the local maven folders are checked to find a suitable version
    (presumably the most recent one there).
    Since the maven query takes time and could time out, and we only want
    one version for all generated files, this method is cached to always
    give the same output during a single runtime.
    """
    from os import environ
    from antlr4_tool_runner import latest_version
    return version or environ.get("ANTLR4_TOOLS_ANTLR_VERSION") or latest_version()


def antlr4_runtime_version():
    """Retrieve the ANTLR4 version used by the available antlr4-python3-runtime"""
    from importlib import metadata
    try:
        return metadata.metadata('antlr4-python3-runtime').get('version')
    except PackageNotFoundError:
        logger.warning(f'The ANTLR4 Python runtime must match the ANTLR4 version, but is not installed')
        logger.info(f'Install antlr4-python3-runtime=={antlr4_version()} to use the generated files')
    return None


class Target(Enum):
    python = 0
    cpp = 1
    def __str__(self):
        if self == Target.python:
            return 'Python3'
        elif self == Target.cpp:
            return 'Cpp'
        raise ValueError(f'Unknown target {self}')


class Feature(Enum):
    listener = 0
    visitor = 1


def rebuild_language(grammar_file,
                     target: Target,
                     features: list[Feature],
                     verbose=False,
                     output=None,
                     dryrun=False,
                     version: str | None = None,
                     ):
    from pathlib import Path
    from subprocess import Popen, PIPE
    from antlr4_tool_runner import initialize_paths, install_jre_and_antlr

    if not isinstance(grammar_file, Path):
        grammar_file = Path(grammar_file)

    args =[
        f'-Dlanguage={target}',
        '-visitor' if Feature.visitor in features else '-no-visitor',
        '-listener' if Feature.listener in features else '-no-listener',
        '-o', output or str(grammar_file.parent / str(target)),
        str(grammar_file)
    ]

    if verbose:
        logger.info(f'Building language files for {grammar_file}')

    # The following copies the implementation of antlr4_tool_runner.tool, which pulls `args` from the system argv list
    # Setup:
    initialize_paths()

    if dryrun:
        return

    jar, java = install_jre_and_antlr(antlr4_version(version))
    # Call antlr4
    p = Popen([java, '-cp', jar, 'org.antlr.v4.Tool'] + args, stdout=PIPE, stderr=PIPE)
    out, err = [x.decode('UTF-8') for x in p.communicate()]
    if err:
        print(err, end='')
    if out:
        print(out, end='')


def language_missing_or_outdated(grammar_file, newest, features, path,
                                 verbose=False,
                                 dryrun=False,
                                 version: str | None = None,
                                 ):
    from pathlib import Path
    import re
    if not isinstance(grammar_file, Path):
        grammar_file = Path(grammar_file)

    if not grammar_file.exists():
        raise RuntimeError(f"The grammar file {grammar_file} does not exist.")

    lexer_file = path.joinpath(f'{grammar_file.stem}Lexer.py')
    parser_file = path.joinpath(f'{grammar_file.stem}Parser.py')
    listener_file = path.joinpath(f'{grammar_file.stem}Listener.py')
    visitor_file = path.joinpath(f'{grammar_file.stem}Visitor.py')

    generated_files = (lexer_file, parser_file)
    if Feature.visitor in features:
        generated_files += (visitor_file, )
    if Feature.listener in features:
        generated_files += (listener_file, )

    if not all(x.exists() for x in generated_files):
        if verbose:
            logger.info(f'Not all language files exist for {grammar_file}')
        return True

    if any(x.stat().st_mtime < newest for x in generated_files):
        if verbose:
            logger.info(f'Not all language files up-to-date for {grammar_file}')
        return True

    # Finally check if the antlr4 version of the generated file is as requested
    version = antlr4_version(version)
    # some antlr components use `self.checkVersion("{hard coded version string}")
    # to verify that they correspond to the same version as the runtime.
    r_checkversion = r'checkVersion\(\"(?P<version>[0-9]+\.[0-9]+\.[0-9]+)\"\)'
    # others (all?) have a comment string on their first line with ANTLR {version}
    r_antlr_version = r'ANTLR (?P<version>[0-9]+\.[0-9]+\.[0-9]+)'
    for file in generated_files:
        with file.open('r') as f:
            contents = f.read()
            checkversion_matches = re.findall(r_checkversion, contents, re.MULTILINE)
            antlr_version_matches = re.findall(r_antlr_version, contents, re.MULTILINE)
        if any(v != version for v in checkversion_matches + antlr_version_matches):
            if verbose:
                logger.info(f'Not all language files match requested ANTLR version {version}')
            return True

    if verbose:
        logger.info(f'Language files for {grammar_file} are up-to-date')
    return False


# def rebuild_speedy_language(grammar_file, features: list[Feature], output: Path, verbose=False):
#     from speedy_antlr_tool import generate
#
#     cpp_output_dir = grammar_file.parent / str(Target.cpp)
#
#     rebuild_language(grammar_file, Target.cpp, features, verbose=verbose, output=cpp_output_dir)
#     rebuild_language(grammar_file, Target.python, features, verbose=verbose, output=output)
#
#     py_parser_path = output / f'{grammar_file.stem}Parser.py'
#     generate(str(py_parser_path), cpp_output_dir)


def ensure_language_up_to_date(
        grammar: str,
        *,
        target: Target,
        features: list[Feature],
        deps=None,
        **kwargs
):
    """Ensure the ANTLR parsed language files are up-to-date."""
    from pathlib import Path
    # This file is at src/grammar/builder.py, it's parent is src/grammar
    # which the grammar defining files are under
    grammar_file = Path(__file__).parent / f'{grammar}.g4'
    # and we want to put Python files under src/mccode_antlr/grammar
    output = Path(__file__).parent.parent / "mccode_antlr" / "grammar"

    newest = grammar_file.stat().st_mtime
    for dep in deps or []:
        newest = max(newest, Path(__file__).parent.joinpath(f'{dep}.g4').stat().st_mtime)

    if language_missing_or_outdated(grammar_file, newest, features, output, **kwargs):
        rebuild_language(grammar_file, target, features, output=output, **kwargs)


def main():
    from argparse import ArgumentParser

    parser = ArgumentParser(prog="mccode-antlr-build", description='Ensure ANTLR files are up-to-date', allow_abbrev=False)
    parser.add_argument('-v', '--version', type=str, default=None, help='Version of ANTLR to build with')
    parser.add_argument('--verbose', action='store_true', help='Print out more information')
    parser.add_argument('--dryrun', action='store_true', help='Setup but do not exectute build')
    args = parser.parse_args()
    kwargs = {
        'version': args.version, 'verbose' : args.verbose, 'dryrun' : args.dryrun
    }
    mc_kwargs = {
        'target': Target.python,
        'features': [Feature.visitor],
        'deps': ('McCommon', 'c99'),
    }
    c_kwargs = {
        'target': Target.python,
        'features': [Feature.visitor, Feature.listener],
    }
    if kwargs['version'] is None:
        kwargs['version'] = antlr4_runtime_version()

    mcdoc_kwargs = {
        'target': Target.python,
        'features': [Feature.visitor],
    }
    ensure_language_up_to_date('McComp', **mc_kwargs, **kwargs)
    ensure_language_up_to_date('McInstr', **mc_kwargs, **kwargs)
    ensure_language_up_to_date('C', **c_kwargs, **kwargs)
    ensure_language_up_to_date('McDoc', **mcdoc_kwargs, **kwargs)

if __name__ == '__main__':
    # __name__ = 'builder.py'
    main()

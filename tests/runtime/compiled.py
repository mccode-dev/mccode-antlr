from __future__ import annotations
from functools import cache
from mccode_antlr import Flavor
import pytest

from mccode_antlr.compiler.check import simple_instr_compiles


def compiled_test(method, compiler: str | None = None):
    if compiler is None:
        compiler = 'cc'
    if simple_instr_compiles(compiler):
        return method

    @pytest.mark.skip(reason=f"Skipping due to lack of working {compiler}")
    def skipped_method(*args, **kwargs):
        return method(*args, **kwargs)

    return skipped_method


def gpu_compiled_test(method):
    return compiled_test(method, 'acc')


def mpi_compiled_test(method):
    return compiled_test(method, 'mpi/cc')


@cache
def mcpl_config_available():
    from shutil import which
    return which('mcpl-config') is not None


def mcpl_compiled_test(method):
    if not mcpl_config_available():
        @pytest.mark.skip(reason='mcpl-config not available')
        def no_mcpl(*args, **kwargs):
            return method(*args, **kwargs)
        return no_mcpl
    if not simple_instr_compiles('cc'):
        @pytest.mark.skip(reason='no working compiler cc')
        def no_cc(*args, **kwargs):
            return method(*args, **kwargs)
    return method


def compile_and_run(instr,
                    parameters,
                    run=True,
                    dump_source=True,
                    target: dict | None = None,
                    config: dict | None = None,
                    flavor: Flavor = Flavor.MCSTAS):
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from mccode_antlr.run import mccode_compile, mccode_run_compiled

    kwargs = dict(target=target, config=config, dump_source=dump_source)

    with TemporaryDirectory() as directory:
        binary, target = mccode_compile(instr, directory, flavor=flavor, **kwargs)
        # The runtime output directory used *can not* exist for McStas/McXtrace to work properly.
        # So find a name inside this directory that doesn't exist (any name should work)
        return mccode_run_compiled(binary, target, Path(directory).joinpath('t'), parameters) if run else (None, None)

from __future__ import annotations
from functools import cache
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


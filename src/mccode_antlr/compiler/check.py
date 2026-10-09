from __future__ import annotations
from contextlib import contextmanager
from functools import cache

import logging

logger = logging.getLogger(__name__)


# Stores the human-readable reason the last compile check failed, keyed by compiler path.
# Used by the `compiled` decorator to surface a useful error message.
_compile_check_failure: dict[str, str] = {}


@cache
def check_for_mccode_antlr_compiler(path: str) -> bool:
    from shutil import which
    from ..config import config
    cc = config
    for key in path.split('/'):
        cc = cc[key]
    cc = cc.get(str)

    if not which(cc):
        logger.info(f"Compiler '{cc}' not found.")
        path = path.replace('/','_')
        logger.info(f'Provide alternate via MCCODE_ANTLR_{path} environment variable')
        return False
    return True


def compiles(compiler: str, instr):
    from os import access, R_OK
    from platform import system
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from mccode_antlr import Flavor
    from .c import (CBinaryTarget, instrument_source,
                    linux_split_flags, windows_split_flags,
                    linux_compile, windows_compile)
    from ..config import config as module_config

    def _rs(label, res):
        msg = res.decode(errors='replace') if isinstance(res, bytes) else str(res)
        return f'{label}:\n{msg}'

    target = CBinaryTarget(mpi='mpi' in compiler, acc=compiler == 'acc', count=1, nexus=False)

    compile_config = dict(default_main=True, enable_trace=False, portable=False,
                  include_runtime=True, embed_instrument_file=False, verbose=False)

    split_flags = windows_split_flags if 'Windows' == system() else linux_split_flags

    compiler_flags, linker_flags = split_flags(instr, target)

    with TemporaryDirectory() as directory:
        binary = Path(directory) / f"output{module_config['ext'].get(str)}"
        source = instrument_source(instr, flavor=Flavor.MCSTAS, config=compile_config)
        compile_func = windows_compile if 'Windows' == system() else linux_compile
        command, result = compile_func(target.compiler, compiler_flags, binary, linker_flags, source)

        if result.returncode:
            raise RuntimeError(f"C compiler exited with code {result.returncode}:\n{_rs('STDERR', result.stderr)}\n{_rs('STDOUT', result.stdout)}")
        if not binary.exists() or not binary.is_file() or not access(binary, R_OK):
            raise RuntimeError(f"Compilation produced no executable; check that {target.compiler} works")


@contextmanager
def _quiet():
    """Hide mccode_antlr's own output: its log messages, and anything printed."""
    from contextlib import redirect_stdout
    from io import StringIO
    package = logging.getLogger('mccode_antlr')
    level = package.level
    package.setLevel(logging.CRITICAL + 1)
    try:
        with redirect_stdout(StringIO()):
            yield
    finally:
        package.setLevel(level)


@cache
def simple_instr_compiles(which: str) -> bool:
    from subprocess import CalledProcessError
    if not check_for_mccode_antlr_compiler(which):
        from ..config import config
        cc = config
        for key in which.split('/'):
            cc = cc[key]
        _compile_check_failure[which] = f"compiler '{cc.get(str)}' not found in PATH"
        return False
    try:
        from mccode_antlr.loader import parse_mcstas_instr
        # Translating the check instrument says nothing about the user's; only a failure is reported, below
        with _quiet():
            instr = parse_mcstas_instr("define instrument check() trace component a = Arm() at (0,0,0) absolute end")
            compiles(which, instr)
        return True
    except RuntimeError as e:
        _compile_check_failure[which] = str(e)
        logger.warning(f"Compiler check failed: {e}")
        return False
    except FileNotFoundError as e:
        _compile_check_failure[which] = str(e)
        logger.warning(f"Compiler check failed, file not found: {e}")
        return False
    except CalledProcessError as e:
        _compile_check_failure[which] = str(e)
        logger.warning(f"Compiler check failed, process error: {e}")
        return False


def compiled(method, compiler: str | None = None):
    from unittest import TestCase
    if compiler is None:
        # Basic compiled instruments only need the 'cc' compiler specified in the config file
        compiler = 'cc'

    def wrapper(*args, **kwargs):
        if simple_instr_compiles(compiler):
            return method(*args, **kwargs)
        reason = _compile_check_failure.get(compiler, 'reason unknown — run with logging enabled')
        if isinstance(args[0], TestCase):
            args[0].skipTest(f'No working {compiler} compiler: {reason}')
        else:
            raise RuntimeError(f'No working {compiler} compiler for {method.__name__}: {reason}')

    return wrapper


def gpu_only(method):
    # GPU compiled instruments need the specific OpenACC compiler
    # **PLUS** they need to _actually_ have the openACC header (macOS and Windows don't use different compilers)
    return compiled(method, 'acc')


def mpi_only(method):
    # MPI compiled instruments need the specified compiler
    return compiled(method, 'mpi/cc')

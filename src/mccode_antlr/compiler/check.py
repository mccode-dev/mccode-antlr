from __future__ import annotations
from functools import cache

@cache
def check_for_mccode_antlr_compiler(path: str) -> bool:
    from shutil import which
    from loguru import logger
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
    from loguru import logger
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from mccode_antlr import Flavor
    from .c import (CBinaryTarget, instrument_source,
                    linux_split_flags, windows_split_flags,
                    linux_compile, windows_compile)
    from ..config import config as module_config

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
            logger.info(f'Failed compiling {command} with error: {result.stderr}')
            logger.info(f"Verify compiler {target.compiler} accepts {compiler_flags} and linker accepts {linker_flags}")
            return False
        if not binary.exists() or not binary.is_file() or not access(binary, R_OK):
            logger.info(f"Compilation did not produce an executable output file, check that {target.compiler} works")
            return False

    return True


@cache
def simple_instr_compiles(which: str) -> bool:
    from subprocess import CalledProcessError
    if not check_for_mccode_antlr_compiler(which):
        return False
    try:
        from mccode_antlr.loader import parse_mcstas_instr
        instr = parse_mcstas_instr("define instrument check() trace component a = Arm() at (0,0,0) absolute end")
        return compiles(which, instr)
    except RuntimeError:
        return False
    except FileNotFoundError:
        return False
    except CalledProcessError:
        return False


def compiled(method, compiler: str | None = None):
    from unittest import TestCase
    if compiler is None:
        # Basic compiled instruments only need the 'cc' compiler specified in the config file
        compiler = 'cc'

    def wrapper(*args, **kwargs):
        if simple_instr_compiles(compiler):
            return method(*args, **kwargs)
        elif isinstance(args[0], TestCase):
            args[0].skipTest(f'Skipping due to lack of working ${compiler}')
        else:
            raise RuntimeError(f'A working compiler is required to use function {method.__name__}')

    return wrapper


def gpu_only(method):
    from loguru import logger
    # GPU compiled instruments need the specific OpenACC compiler
    # **PLUS** they need to _actually_ have the openACC header (macOS and Windows don't use different compilers)
    return compiled(method, 'acc')


def mpi_only(method):
    # MPI compiled instruments need the specified compiler
    return compiled(method, 'mpi/cc')

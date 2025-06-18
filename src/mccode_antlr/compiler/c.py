"""Handles compilation of C translated instruments into usable binaries"""
from __future__ import annotations

from enum import Flag, auto
from typing import Union
from pathlib import Path
from mccode_antlr.instr import Instr
from mccode_antlr.translators.c import CTargetVisitor
from loguru import logger
from .check import compiled, gpu_only, mpi_only
from mccode_antlr import Flavor

class CBinaryTarget:
    class Type(Flag):
        single = auto()
        acc = auto()
        mpi = auto()
        nexus = auto()

    def __init__(self, mpi: bool = False, acc: bool = False, count: int = 1, nexus: bool = False):
        self.count = count
        if mpi and acc:
            self.type = CBinaryTarget.Type.acc | CBinaryTarget.Type.mpi
        elif mpi:
            self.type = CBinaryTarget.Type.mpi
        elif acc:
            self.type = CBinaryTarget.Type.acc
        else:
            self.type = CBinaryTarget.Type.single
        # completely orthogonal, probably a bad idea to include here at all:
        if nexus:
            self.type |= CBinaryTarget.Type.nexus

    def update(self, d: dict):
        self.count = d.get('count', self.count)
        d_mpi = d.get('mpi', self.type & CBinaryTarget.Type.mpi)
        d_acc = d.get('acc', self.type & CBinaryTarget.Type.acc)
        if d_mpi and d_acc:
            self.type = CBinaryTarget.Type.acc | CBinaryTarget.Type.mpi
        elif d_mpi:
            self.type = CBinaryTarget.Type.mpi
        elif d_acc:
            self.type = CBinaryTarget.Type.acc
        else:
            self.type = CBinaryTarget.Type.single
        if d.get('nexus', self.type & CBinaryTarget.Type.nexus):
            self.type |= CBinaryTarget.Type.nexus

    @property
    def compiler(self) -> str:
        from mccode_antlr.config import config
        if self.type & CBinaryTarget.Type.acc:
            # acc *or* acc + mpi uses the OpenACC compiler
            return config['acc'].as_str_expanded()
        elif self.type & CBinaryTarget.Type.mpi:
            # mpi (no-acc) uses the OpenMPI compiler
            return config['mpi']['cc'].as_str_expanded()
        # otherwise use the standard C compiler
        return config['cc'].as_str_expanded()

    @property
    def flags(self) -> list[str]:
        from mccode_antlr.config import config
        if self.type & CBinaryTarget.Type.acc:
            # acc *or* acc + mpi uses the OpenACC compiler *and* flags
            return config['flags']['acc'].as_str_expanded().split()
        # otherwise use the standard compiler flags
        return config['flags']['cc'].as_str_expanded().split()

    @property
    def linker_flags(self) -> list[str]:
        from mccode_antlr.config import config
        return config['flags']['ld'].as_str_expanded().split()

    @property
    def extra_flags(self) -> list[str]:
        """Only a little confusing ..."""
        from mccode_antlr.config import config
        extras = []
        if self.type & CBinaryTarget.Type.mpi:
            extras.extend(config['flags']['mpi'].as_str_expanded().split())
        if self.type & CBinaryTarget.Type.nexus:
            extras.extend(config['flags']['nexus'].as_str_expanded().split())
        return extras


def instrument_source(instrument: Instr, flavor: Flavor, config: dict, verbose: bool = None):
    if verbose is None:
        verbose = config.get('verbose', False)
    # TargetVisitor to uses instrument.registries (and the CTargetVisitor *appends* its LIBC_REGISTRY if necessary)
    visitor = CTargetVisitor(instrument, flavor=flavor, config=config, verbose=verbose)
    # Does the conversion by 'visiting' the instrument, then returns the full string of the generated source code
    return visitor.contents()


def linux_split_flags(instrument: Instr, target: CBinaryTarget):
    # the type of binary requested determines (some of) the required flags:
    compiler_flags = target.flags + target.extra_flags
    linker_flags = target.linker_flags
    # the instrument-defined flags are always(?) linker flags:
    # the flags in an instrument *might* contain ENV, CMD, GETPATH directives which need to be expanded via decode:
    linker_flags.extend(
        [word for flag in instrument.decoded_flags() for word in flag.split()])

    # Why is this addition necessary?
    if any('OPENACC' in word for word in compiler_flags) and any(
            'NeXus' in word for word in compiler_flags):
        compiler_flags.append('-D__GNUC__')
    return compiler_flags, linker_flags


def windows_split_flags(instrument: Instr, target: CBinaryTarget):
    # the type of binary requested determines (some of) the required flags:
    compiler_flags = target.flags + target.extra_flags
    linker_flags = target.linker_flags
    # instrument-defined flags may be for the compiler or linker.
    # cl.exe accepts a _wide_ array of flags, most of which we can't support
    # so, instead we are forced to handle things piecemeal.
    cl_flags = {
        'D': {'not': '/DYNAMICBASE',},
        'U': {},
        'p': {'has': '='},
        'std': {'has': '=', 'replace': ('=', ':')}
    }
    for flag in instrument.decoded_flags():
        flag = flag.strip()
        if not flag.startswith('/') and not flag.startswith('-'):
            # Not an actual flag? Punt for now
            linker_flags.append(flag)
        elif any(flag[1:].startswith(key) for key in cl_flags):
            d = next(d for key, d in cl_flags.items() if flag[1:].startswith(key))
            if ('not' in d and flag == d['not']) or ('has' in d and not d['has'] in flag):
                linker_flags.append(flag)
            else:
                if 'replace' in d:
                    flag = flag.replace(d['replace'][0], d['replace'][1])
                compiler_flags.append(flag)
        elif flag[1:].lower().startswith('l') or flag.lower().endswith('.lib'):
            linker_flags.append(flag)
        else:
            # Second punt; no match for our special (post / or -) strings
            linker_flags.append(flag)

    # Check for OpenACC or NeXus in flags?
    return compiler_flags, linker_flags


def linux_compile(compiler, compiler_flags, target, linker_flags, source):
    from subprocess import run
    # The solitary '-' specifies *where* the stdin source should be processed, which is critical for getting
    # linking flags right on (some) Linux systems
    command = [compiler, *compiler_flags, '-o', str(target), '-', *linker_flags]
    result = run(command, input=source, text=True, capture_output=True)
    return command, result


def windows_compile(compiler, compiler_flags, target, linker_flags, source):
    from subprocess import run
    parent = target.parent
    if not parent.is_dir():
        parent.mkdir(parents=True)
    write_to = target.with_suffix('.c')
    with write_to.open('w') as file:
        file.writelines(source)
    if '/link' not in linker_flags:
        linker_flags = ['/link'] + linker_flags
    # Specifying either of
    #   obj = [] if parent == Path() else [f'/Fo"{parent}\\"']
    # as *obj, would move generated object files next to the executable, but breaks
    # some aspect of compilation when done from Python (but not the command line)
    # FIXME Re-evaluate the need/advisability for no compiler warnings
    command = [compiler, *compiler_flags, str(write_to), '/W0', *linker_flags, f'/out:{target}']
    result = run(command, capture_output=True)
    return command, result


def _compile_instrument(
        instrument: Instr,
        target: CBinaryTarget,
        output: Union[str, Path] = None,
        replace: bool = False,
        dump_source: bool = False,
        source_file: str | None = None,
        **kwargs
):
    """Do the actual compilation -- should not be called directly by users

    Note
    ----
    If you are a user of the mccode-antlr module, call the `compile_instrument`
    gateway method instead to enable a cached check that your system compiler is
    configured correctly.
    """
    from os import R_OK, access
    from subprocess import run, CalledProcessError
    from platform import system
    from mccode_antlr.config import config
    logger.info(f'Compile {instrument.name}')
    # determine a name and location for the binary file
    if output is None:
        # use the current working directory if nothing provided
        output = Path()
    if not isinstance(output, Path):
        # allow for a string input to be interpreted as a path
        output = Path(output)
    if output.is_dir():
        # allow for the user to specify only the output *directory*
        output = output.joinpath(instrument.name).with_suffix(config['ext'].get(str))

    if output.exists() and not replace:
        return output

    source = instrument_source(instrument, **kwargs)
    if source_file or ('Windows' != system() and dump_source):
        source_file = source_file or Path().joinpath(output.parts[-1]).with_suffix('.c')
        logger.info(f'Source written in {source_file}')
        with open(source_file, 'w') as cfile:
            cfile.write(source)

    _compile = windows_compile if 'Windows' == system() else linux_compile
    _handle_flags = windows_split_flags if 'Windows' == system() else linux_split_flags
    compiler_flags, linker_flags = _handle_flags(instrument, target)
    command, result = _compile(target.compiler, compiler_flags, output, linker_flags, source)

    if result.returncode:
        stdout = result.stdout.decode() if isinstance(result.stdout, bytes) else result.stdout
        stderr = result.stderr.decode() if isinstance(result.stderr, bytes) else result.stderr
        raise RuntimeError(f"Compilation\n{' '.join(command)}\nfailed with output\n{stdout}\nand error\n{stderr}")
    if not output.exists():
        raise RuntimeError(f"Compilation should have produced {output}, but it does not appear to exist")
    if not access(output, R_OK):
        raise RuntimeError(f"{output} exists but is not an executable")
    return output


@gpu_only
def compile_acc_instrument(*args, **kwargs):
    return _compile_instrument(*args, **kwargs)


@mpi_only
def compile_mpi_instrument(*args, **kwargs):
    return _compile_instrument(*args, **kwargs)


@compiled
def compile_c_instrument(*args, **kwargs):
    return _compile_instrument(*args, **kwargs)


def compile_instrument(
        instrument: Instr,
        target: CBinaryTarget,
        output: Union[str, Path] = None,
        replace: bool = False,
        dump_source: bool = False,
        **kwargs
):
    """Compile an Instr object to one of the possible C targets

    Parameters
    ----------
    instrument: Instr
        The Instr to turn into a compiled binary
    target: CBinaryTarget
        The type of binary to produce: C99, OpenACC, MPI, etc.
    output:
        The path (and optionally name) where to store the produced binary
    replace:
        If true compilation will proceed even if a same-named path exists already
    dump_source:
        A diagnostic mode that outputs the generated C code into the current working
        directory
    """
    if target.type & CBinaryTarget.Type.acc:
        return compile_acc_instrument(instrument, target, output, replace, dump_source, **kwargs)
    if target.type & CBinaryTarget.Type.mpi:
        return compile_mpi_instrument(instrument, target, output, replace, dump_source, **kwargs)
    return compile_c_instrument(instrument, target, output, replace, dump_source, **kwargs)


def run_compiled_instrument(binary: Path, target: CBinaryTarget, options: str, capture=False, dry_run: bool = False):
    from subprocess import run, CalledProcessError
    from platform import system
    from mccode_antlr.config import config

    # If NeXus output is requested and the InstrumentDescriptionFile is needed, run a different script entirely...
    #   TODO think about actually doing this?
    # if target.flags & CBinaryTarget.Type.nexus and idf_required:
    #     run([config['idfgen'].get(str), str(binary), *options])

    command = []
    if target.type & CBinaryTarget.Type.mpi:
        # is the available MPI OpenMPI, mpich, or something else?
        res = run(['mpirun', '--version'], capture_output=True)
        if res.returncode != 0:
            raise RuntimeError(f"mpirun is not installed, MPI compilation failed")
        is_open_mpi = 'Open MPI' in res.stdout.decode()

        # we execute mpirun
        command.append(config['mpi']['run'].as_str_expanded())
        # which takes optional flags
        if target.count == 0 and not is_open_mpi:
            print("Using system default number of mpirun processes")
        else:
            # Even if zero, OpenMPI needs this to avoid interpreting options flags
            # for the binary as if they were for it.
            command.extend(['-np', str(target.count)])
        if config['machinefile'].exists():
            # --machinefile is only an OpenMPI option. mpich uses -f?
            machinefile = config['machinefile'].as_str_expanded()
            command.extend(['--machinefile' if is_open_mpi else '-f', machinefile])
        # and requires trickery if we want to restrict the GPU used
        if target.type & CBinaryTarget.Type.acc and 'Windows' != system():
            # Each worker should have the environment variable CUDA_VISIBLE_DEVICES defined as the value of
            # OMPI_COMM_WORLD_LOCAL_RANK, which gets sent by MPI to the worker. This assigment must take place
            # *on* the worker, which requires hijacking the executable that MPI runs
            command.append('acc_gpu_bind')
            raise NotImplementedError('CUDA GPU binding not yet implemented')
        if is_open_mpi:
            # mpich, at least, does not accept '--' between options and binary
            command.extend(['--'])

    binary = binary.resolve()
    if not binary.exists():
        raise RuntimeError(f'Can not execute {binary} since it does not exist.')

    # In normal operation, the binary is provided with options
    command.extend([str(binary), *options.split()])
    # which we then execute:
    if dry_run:
        logger.info(f'Would execute {command}')
        return ""
    result = run(command, capture_output=capture)
    if result.returncode and capture:
        raise RuntimeError(f'Execution of {command} failed with output\n{result.stdout}\n and error\n{result.stderr}')
    elif result.returncode:
        raise RuntimeError(f'Execution of {command} failed, see above for error message(s)')

    return (result.stdout + result.stderr) if capture else ""

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

    def __init__(self, mpi: bool = False, acc: bool = False, count: int | str = 1,
                 nexus: bool = False):
        # count is a positive integer, or 'auto' to leave the choice to the launcher
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
    def tag(self) -> str:
        """Filename tag distinguishing this target: '', 'mpi', 'acc' or 'mpiacc'.

        NeXus is deliberately not tagged: it is orthogonal to the parallelism
        choice and is recorded in the binary's build information instead.
        """
        return ('mpi' if self.type & CBinaryTarget.Type.mpi else '') \
             + ('acc' if self.type & CBinaryTarget.Type.acc else '')

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


def strip_target_tag(name: str) -> str:
    """Remove a trailing target tag from a binary or source stem.

    'straight_trex.mpi' -> 'straight_trex'. Needed so that recompiling a dumped
    'foo.mpi.c' for a different target does not produce a mislabelled name.
    """
    from mccode_antlr.build_info import TARGET_TAGS
    for tag in TARGET_TAGS:  # longest first
        if name.endswith(f'.{tag}'):
            return name[:-(len(tag) + 1)]
    return name


def binary_filename(name: str, target: CBinaryTarget | None = None) -> str:
    """'foo' for an MPI target -> 'foo.mpi.out' ('.exe' on Windows)."""
    from mccode_antlr.config import config
    tag = target.tag if target is not None else ''
    # Deliberately not Path.with_suffix: that would truncate an instrument named
    # 'TAS.v2' to 'TAS.out'.
    return f'{strip_target_tag(name)}{"." + tag if tag else ""}{config["ext"].get(str)}'


def binary_path(output, name: str, target: CBinaryTarget | None = None) -> Path:
    """Decide where a compiled binary goes -- the single place that rule lives.

    None            -> CWD / binary_filename(name, target)
    a directory     -> directory / binary_filename(name, target)
    a suffix-less   -> parent / binary_filename(that name, target)
    a full filename -> used verbatim; the user named the file, so do not argue
    """
    output = Path() if output is None else Path(output)
    if output.is_dir():
        return output.joinpath(binary_filename(name, target))
    if not output.suffix:
        return output.parent.joinpath(binary_filename(output.name, target))
    return output


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
    # Classify each token from decoded DEPENDENCY flag strings.
    # Linker tokens: -l<lib>, -L<dir>, -Wl,<linker-opts>, and bare library files.
    # Everything else (-I, -D, -std, -x, -fopenmp, -fPIC, …) is a compiler flag
    # and must appear before the stdin source marker ('-') in the command.
    _linker_starts = ('-l', '-L', '-Wl,')
    _lib_suffixes  = ('.so', '.a', '.dylib')
    for flag in instrument.decoded_flags():
       for word in flag.split():
           if word.startswith(_linker_starts) or word.endswith(_lib_suffixes):
               linker_flags.append(word)
           else:
               compiler_flags.append(word)

    # Workaround: NeXus headers on some systems require __GNUC__ to be defined,
    # but the OpenACC compiler (PGI/NVHPC) does not define it by default.
    # Check both lists: -DOPENACC lands in compiler_flags; -lNeXus lands in linker_flags.
    all_flags = compiler_flags + linker_flags
    if any('OPENACC' in w for w in all_flags) and any('NeXus' in w for w in all_flags):
       compiler_flags.append('-D__GNUC__')
    return compiler_flags, linker_flags


def windows_split_flags(instrument, target):
    compiler_flags = target.flags + target.extra_flags
    linker_flags = target.linker_flags

    linker_prefixes = ('link', 'LIBPATH', 'SUBSYSTEM', 'ENTRY', 'STACK', 'HEAP',
                        'MACHINE', 'MANIFEST', 'INCREMENTAL', 'NODEFAULTLIB',
                        'OPT', 'LTCG', 'DEBUG', 'PDB', 'NATVIS', 'DYNAMICBASE')

    for decoded in instrument.decoded_flags():
        for flag in decoded.split():
            flag = flag.strip()
            stem = flag[1:] if (flag.startswith('/') or flag.startswith('-')) else ''

            if not stem:  # bare path or .lib
                linker_flags.append(flag)
            elif flag.lower().endswith('.lib'):  # explicit .lib
                linker_flags.append(flag)
            elif stem.lower().startswith('l') or any(
                    stem.upper().startswith(p) for p in linker_prefixes):
                linker_flags.append(flag)  # linker options
            else:
                # std: needs /std:c11 → /std:c11 (replace = with :)
                if stem.lower().startswith('std') and '=' in flag:
                    flag = flag.replace('=', ':')
                compiler_flags.append(flag)  # default: compiler

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
    logger.info(f'Compile {instrument.name}')
    # determine a name and location for the binary file -- a directory or a bare
    # name picks up the target tag and platform extension, a full filename does not
    output = binary_path(output, instrument.name, target)

    # Data files carried inside the instrument have to sit somewhere the compiled
    # binary looks. It searches its own directory, so put them beside the binary:
    # the source is generated in memory here and never written, so the translator
    # has no output directory to deposit into. Done before the cached-binary
    # return, since an existing binary still needs its data files present.
    from mccode_antlr.io.portable import deposit_embedded_data_files
    deposit_embedded_data_files(instrument, output.parent)

    if output.exists() and not replace:
        from mccode_antlr.build_info import (build_info_matches, expected_build_info,
                                             read_build_info)
        expected = expected_build_info(instrument, kwargs.get('flavor'),
                                       kwargs.get('config') or {}, target)
        reusable, reason = build_info_matches(read_build_info(output), expected)
        if reusable:
            return output
        logger.info(f'Rebuilding {output} because {reason}')

    source = instrument_source(instrument, **kwargs)
    if source_file or ('Windows' != system() and dump_source):
        source_file = source_file or Path(strip_target_tag(Path(output.parts[-1]).stem) + '.c')
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


def cflags_from_c_source(source: str) -> list[str]:
    """Extract CFLAGS recorded in the header comment of a generated McCode C file.

    The translator writes::

        * CFLAGS=<space-separated flags>

    as part of the opening block comment.  Returns an empty list when the line
    is absent or contains no flags.
    """
    import re
    match = re.search(r'^\s*\*\s*CFLAGS=(.*)$', source, re.MULTILINE)
    if match:
        flags = match.group(1).strip()
        return flags.split() if flags else []
    return []


def _split_raw_flags(raw_flags: list[str], target: CBinaryTarget, *, windows: bool = False):
    """Like linux_split_flags / windows_split_flags but accepts a plain list instead of Instr."""
    compiler_flags = target.flags + target.extra_flags
    linker_flags = target.linker_flags
    if windows:
        linker_prefixes = ('link', 'LIBPATH', 'SUBSYSTEM', 'ENTRY', 'STACK', 'HEAP',
                           'MACHINE', 'MANIFEST', 'INCREMENTAL', 'NODEFAULTLIB',
                           'OPT', 'LTCG', 'DEBUG', 'PDB', 'NATVIS', 'DYNAMICBASE')
        for flag in raw_flags:
            for word in flag.split():
                word = word.strip()
                stem = word[1:] if (word.startswith('/') or word.startswith('-')) else ''
                if not stem or word.lower().endswith('.lib'):
                    linker_flags.append(word)
                elif stem.lower().startswith('l') or any(
                        stem.upper().startswith(p) for p in linker_prefixes):
                    linker_flags.append(word)
                else:
                    if stem.lower().startswith('std') and '=' in word:
                        word = word.replace('=', ':')
                    compiler_flags.append(word)
    else:
        _linker_starts = ('-l', '-L', '-Wl,')
        _lib_suffixes = ('.so', '.a', '.dylib')
        for flag in raw_flags:
            for word in flag.split():
                if word.startswith(_linker_starts) or word.endswith(_lib_suffixes):
                    linker_flags.append(word)
                else:
                    compiler_flags.append(word)
        all_flags = compiler_flags + linker_flags
        if any('OPENACC' in w for w in all_flags) and any('NeXus' in w for w in all_flags):
            compiler_flags.append('-D__GNUC__')
    return compiler_flags, linker_flags


@compiled
def compile_c_file(
        c_file: Union[str, Path],
        target: CBinaryTarget,
        output: Union[str, Path] = None,
        replace: bool = False,
):
    """Compile a pre-generated McCode C source file directly to a binary.

    This is the compile-only counterpart to :func:`compile_instrument` for the
    case where the C translation step has already been performed (e.g. by
    ``mcstas-antlr``).  CFLAGS are read from the ``* CFLAGS=`` line in the
    file's opening block comment.

    Parameters
    ----------
    c_file:
        Path to the ``.c`` source file.
    target:
        The type of binary to produce.
    output:
        Destination path or directory for the binary.  Defaults to the current
        working directory using the C file's stem as the binary name.
    replace:
        If ``True``, recompile even when the output already exists.
    """
    from os import R_OK, access
    from platform import system

    c_file = Path(c_file)
    source = c_file.read_text()
    name = c_file.stem

    # strip_target_tag inside binary_path keeps 'foo.mpi.c' compiled for OpenACC
    # from being named 'foo.mpi.out'
    output = binary_path(output, name, target)

    if output.exists() and not replace:
        return output

    logger.info(f'Compile {name} from {c_file}')
    raw_flags = cflags_from_c_source(source)
    is_windows = 'Windows' == system()
    _compile = windows_compile if is_windows else linux_compile
    compiler_flags, linker_flags = _split_raw_flags(raw_flags, target, windows=is_windows)
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


def infer_binary_target(binary: Path, count: int = 1,
                        default: CBinaryTarget | None = None,
                        allow_exec: bool = True) -> CBinaryTarget:
    """Determine a CBinaryTarget from what the compiled binary says about itself.

    Evidence is taken in descending order of authority: the build-information
    metadata entry mccode-antlr writes into the generated C, then the
    preprocessor-gated help strings in the McCode runtime (which also cover
    binaries built by classic ``mcstas``), then running ``binary --help``.

    Scanning for ``MPI_Init``/``acc_init`` symbol names, which this replaces, was
    unsound: those bytes appear in any binary that merely *mentions* them, so a
    serial binary built with ``--source`` whose embedded instrument text contains
    an ``#ifdef USE_MPI`` block was reported as an MPI binary.

    When nothing can be determined, *default* is returned unchanged rather than a
    guess, so that a caller's explicit choice survives.

    Parameters
    ----------
    binary:
        Path to the compiled instrument binary to inspect.
    count:
        Number of MPI processes to use; cannot be determined from the binary.
    default:
        Target to fall back on when the binary says nothing.
    allow_exec:
        Whether running the binary is acceptable as a last resort.
    """
    from mccode_antlr.build_info import probe_binary
    probe = probe_binary(binary, allow_exec=allow_exec)
    if not probe.known:
        logger.info(f'Could not determine the target of {Path(binary).name}; using '
                    f'{"the supplied" if default is not None else "single-process"} settings')
        return default if default is not None else CBinaryTarget(count=count)
    return CBinaryTarget(mpi=bool(probe.mpi), acc=bool(probe.acc),
                         nexus=bool(probe.nexus), count=count)


def mpi_process_flags(count: int | str) -> list[str]:
    """The '-np N' part of an mpirun command line, if one is needed.

    A positive integer is passed through. Anything else means 'auto': name no
    number and let the launcher -- or the batch scheduler that started it --
    decide. Passing '-np 0' instead, as this used to, is not a way of saying
    'default'; it is a request for zero processes that only OpenMPI happens to
    tolerate. Separating mpirun's flags from the binary's is the job of the '--'
    added after these, not of '-np'.
    """
    from platform import system
    if isinstance(count, int) and count >= 1:
        return ['-np', str(count)]
    if 'Windows' == system():
        # msmpi's mpiexec accepts neither the '--' separator nor a missing
        # process count, so it has to be given a number
        from os import cpu_count
        return ['-np', str(cpu_count() or 1)]
    logger.info('Letting mpirun choose the number of processes')
    return []


#: What to do with a running simulation's stdout/stderr.
#:   'no'   stream it to this process's own streams -- the user watches it happen
#:   'yes'  keep it to ourselves, and show it only if the run fails
#:   'tee'  stream it *and* keep a copy in <output directory>/mccode.out
CAPTURE_MODES = ('no', 'yes', 'tee')
CAPTURE_LOG_NAME = 'mccode.out'

#: Lines kept from a streamed run so that a failure can still be explained.
#: Bounded on purpose: a traced MPI run emits gigabytes.
_TAIL_LINES = 200


def normalise_capture(capture) -> str:
    """Accept a CAPTURE_MODES string, or the bool this argument used to be."""
    if isinstance(capture, str):
        if capture not in CAPTURE_MODES:
            raise ValueError(f'capture must be one of {CAPTURE_MODES}, got {capture!r}')
        return capture
    return 'yes' if capture else 'no'


def _stream_and_tee(command, log_file: Path | None):
    """Run *command*, copying its output to our stdout and to *log_file*.

    The output directory is created by the simulation itself, and McCode refuses
    to start if it already exists, so the copy is written somewhere neutral and
    moved into place afterwards.
    """
    import sys
    from collections import deque
    from shutil import move
    from subprocess import Popen, PIPE, STDOUT
    from tempfile import NamedTemporaryFile

    tail = deque(maxlen=_TAIL_LINES)
    with NamedTemporaryFile('wb', delete=False, suffix='.out') as scratch:
        scratch_name = Path(scratch.name)
        with Popen(command, stdout=PIPE, stderr=STDOUT) as process:
            for line in process.stdout:
                sys.stdout.buffer.write(line)
                sys.stdout.buffer.flush()
                scratch.write(line)
                tail.append(line)
            returncode = process.wait()

    if log_file is not None and log_file.parent.is_dir():
        move(str(scratch_name), str(log_file))
        logger.info(f'Simulation output copied to {log_file}')
    else:
        # no directory to move it into (a failed run, or none was named)
        logger.info(f'Simulation output kept in {scratch_name}')
    return returncode, b''.join(tail)


def run_compiled_instrument(binary: Path, target: CBinaryTarget, options: str, capture=False,
                            dry_run: bool = False, log_file: Path | None = None):
    from subprocess import run, CalledProcessError
    from platform import system
    from mccode_antlr.config import config

    if not isinstance(target, CBinaryTarget):
        _t = CBinaryTarget()
        if isinstance(target, dict):
            _t.update(target)
        else:
            raise TypeError(f"target must be a CBinaryTarget, got {type(target)}")
        target = _t

    # If NeXus output is requested and the InstrumentDescriptionFile is needed, run a different script entirely...
    #   TODO think about actually doing this?
    # if target.flags & CBinaryTarget.Type.nexus and idf_required:
    #     run([config['idfgen'].get(str), str(binary), *options])

    command = []
    if target.type & CBinaryTarget.Type.mpi:
        # Launching a non-MPI binary under mpirun starts N independent full-ncount
        # runs which race on the output directory; catch it before any process starts
        from mccode_antlr.build_info import probe_binary
        if probe_binary(binary, allow_exec=False).mpi is False:
            raise RuntimeError(
                f'{Path(binary).name} was not built with MPI support, so it cannot be run'
                ' under mpirun. Recompile the instrument with --parallel, or run it'
                ' without.'
            )
        # is the available MPI OpenMPI, mpich, or something else?
        res = run(['mpirun', '--version'], capture_output=True)
        if res.returncode != 0:
            raise RuntimeError(f"mpirun is not installed, MPI compilation failed")
        is_open_mpi = 'Open MPI' in res.stdout.decode()

        # we execute mpirun
        command.append(config['mpi']['run'].as_str_expanded())
        # which takes optional flags
        command.extend(mpi_process_flags(target.count))
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
    def decoded(raw):
        return raw.decode('utf-8', errors='replace') if isinstance(raw, bytes) else (raw or '')

    mode = normalise_capture(capture)
    if mode == 'tee':
        returncode, tail = _stream_and_tee(command, log_file)
        if returncode:
            raise RuntimeError(f'Execution of {" ".join(command)} failed. Last output was\n'
                               f'{decoded(tail)}')
        return ''
    if mode == 'yes':
        result = run(command, capture_output=True)
        if result.returncode:
            raise RuntimeError(f'Execution of {" ".join(command)} failed with output\n'
                               f'{decoded(result.stdout)}\nand error\n{decoded(result.stderr)}')
        # bytes, as this has always returned -- callers decode it themselves
        return result.stdout + result.stderr
    # 'no': the simulation writes straight to our stdout/stderr, so there is
    # nothing to report here that the user has not already seen
    result = run(command)
    if result.returncode:
        raise RuntimeError(f'Execution of {" ".join(command)} failed, see above for error message(s)')
    return ''

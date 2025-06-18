"""The McCode nightly test script implemented for mccode-antlr."""

from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import TypeVar
from loguru import logger

from numpy import nan

from mccode_antlr import Flavor
from mccode_antlr.reader import Registry

NightlyInstrExampleType = TypeVar('NightlyInstrExampleType', bound='NightlyInstrExample')


@dataclass
class NightlyInstrExample:
    """Holds parameters for a single instr file %Example: test case"""
    sourcefile: Path
    test_number: int
    parameter_values: str = ""
    detector: str = ""
    target_value: float = nan
    test_value: float = nan
    compiled: bool = False
    compile_time: timedelta = field(default_factory=timedelta)
    ran: bool = False
    run_time: timedelta = field(default_factory=timedelta)
    error_message: str = ""
    stdout: str = ""
    test_complete: bool = False

    def __post_init__(self):
        import re
        if '.instr' in self.parameter_values:
            rinstr = re.compile(r'[a-zA-Z][a-zA-Z0-9_\-]*\.instr')
            new_param = rinstr.sub('', self.parameter_values)
            logger.info(f'Removing .instr from {self.parameter_values} now {new_param}')
            self.parameter_values = new_param
        if self.sourcefile.stem in self.parameter_values:
            new_param = self.parameter_values
            self.parameter_values = new_param.replace(self.sourcefile.stem, '')
            logger.info(f'Removing {self.sourcefile.stem} from {new_param} now {self.parameter_values}')
        if '-n' in self.parameter_values:
            rn = re.compile(r'-n[0-9eE\.]*')
            new_param = rn.sub('', self.parameter_values)
            logger.info(f'Removing -n from {self.parameter_values}, now {new_param}')
            self.parameter_values = new_param

    @classmethod
    def list_from_file(cls, filename: Path) -> list[NightlyInstrExampleType]:
        import re
        rspec = re.compile(f'%Example:([^\n]*)Detector:([^\n]*)_I=([0-9.+-e]+)')
        with open(filename, 'r') as file:
            contents = file.read()
            matches = rspec.findall(contents)
        if len(matches):
            groups = [(m[0].strip(), m[1].strip(), float(m[2].strip())) for m in matches]
            return [cls(filename, i+1, p, d, t) for i, (p, d, t) in enumerate(groups)]
        return [cls(filename, -1)]

    def get_display_name(self):
        return f'{self.sourcefile.stem}_{self.test_number}' if self.test_number > 1 else self.sourcefile.stem

    def get_json_repr(self):
        jr = dict(displayname=self.get_display_name(),
                  sourcefile=self.sourcefile.as_posix(),
                  testnb=self.test_number,
                  parvals=self.parameter_values,
                  detector=self.detector,
                  targetval=self.target_value,
                  testval=self.test_value,
                  compiled=self.compiled,
                  compiletime=str(self.compile_time),
                  didrun=self.ran,
                  runtime=str(self.run_time),
                  errmsg=self.error_message,
                  stdout=self.stdout,
                  complete=self.test_complete
                  )
        return jr

    def save(self, path: Path):
        import json
        with open(path.joinpath(self.get_display_name() + '.json'), 'w') as file:
            json.dump(self.get_json_repr(), file)


@dataclass
class LineLogger:
    lines: list = field(default_factory=list)

    def logline(self, line: str):
        self.lines.append(line)

    def save(self, filename: Path):
        with open(filename, 'w') as file:
            file.write('\n'.join(self.lines))
            file.write('\n')

    def find(self, search: str):
        import re
        for line in self.lines:
            if re.search(search, line):
                return True
        return False


def get_cpu_name():
    from platform import system
    from subprocess import check_output
    if system() == "Windows":
        from platform import processor
        return processor()
    elif system() == "Darwin":
        from os import environ, pathsep
        environ['PATH'] = environ['PATH'] + pathsep + '/usr/sbin'
        command = "sysctl -n machdep.cpu.brand_string"
        return check_output(command).strip()
    elif system() == "Linux":
        command = "cat /proc/cpuinfo"
        all_info = check_output(command, shell=True).decode().strip()
        for line in all_info.split("\n"):
            if "model name" in line:
                from re import sub
                return sub(".*model name.*:", "", line, 1).strip()
    return ""


def get_nvidia_gpu_name():
    """Identify GPU (Uses GPUtil which only knows about Nvidia GPUs)"""
    from importlib import import_module
    from importlib.util import find_spec
    if find_spec('GPUtil') is None:
        return "none"
    gpus = import_module('GPUtil').getGPUs()
    names = ','.join(gpu.name for gpu in gpus)
    return names if len(names) else "none"


def get_hostname():
    import socket
    return socket.gethostname()


def get_username():
    import os
    import pwd
    info = pwd.getpwuid(os.getuid())
    # Return the full name 'pw_gecos' if present, otherwise the username 'pw_name'
    return info[4] if len(info[4]) else info[0]


def _monitor_name_file_name_match(folder, monitor_name):
    import re
    look_for_filename = False
    with open(folder.joinpath('mccode.sim'), 'r') as file:
        lines = file.readlines()
    for line in lines:
        if re.match(rf"\s*component:\s*{monitor_name}$", line):
            look_for_filename = True
        if look_for_filename:
            m = re.match(r'\s*filename:\s+(.+)', line)
            if m:
                filename = folder.joinpath(m.group(1))
                if filename.is_file():
                    return filename
            if re.match('end data', line):
                # try the monitor named dat file
                zero_d_filename = folder.joinpath(monitor_name + '.dat')
                if zero_d_filename.is_file():
                    return zero_d_filename
                return None
    return None


def mccode_test_compiler(work_dir, file_path, target, flavor, dump, **kwargs):
    from pathlib import Path
    from mccode_antlr.reader import Reader
    from mccode_antlr.compiler.c import compile_instrument
    from mccode_antlr.common import Mode
    # only the provided (remote) registry should be necessary for test instruments
    reader = Reader(flavor=flavor)
    inst = reader.get_instrument(file_path, mode=Mode.minimal)
    output = Path(work_dir)
    config = dict(default_main=True, enable_trace=False, portable=False, include_runtime=True,
                  embed_instrument_file=False, verbose=False)
    try:
        binary_path = compile_instrument(inst, target, output, flavor=flavor, config=config, dump_source=dump, **kwargs)
    except RuntimeError as err:
        logger.critical(f'Failed to produce a binary for {file_path}')
        logger.info(err)
        return False, Path()
    return True, binary_path


def mcstas_test_compiler(target, work_dir, file_path, dump, **kwargs):
    return mccode_test_compiler(work_dir, file_path, target, Flavor.MCSTAS, dump, **kwargs)


def mcxtrace_test_compiler(target, work_dir, file_path, dump, **kwargs):
    return mccode_test_compiler(work_dir, file_path, target, Flavor.MCXTRACE, dump, **kwargs)


def mccode_test_runner(target, binary_path, test_parameters: str, n_particles: int):
    import shutil
    from tempfile import mkdtemp
    from mccode_antlr.compiler.c import run_compiled_instrument

    output_path = Path(mkdtemp(prefix=binary_path.stem, dir=binary_path.parent.resolve()))
    # The McCode C runtime won't use an existing directory ...
    shutil.rmtree(output_path)
    # common default parameters: output directory, seed value, number of particles
    parameters = f'--dir {output_path} -s 1000 -n {n_particles} ' + test_parameters
    try:
        output = run_compiled_instrument(binary_path, target, parameters, capture=True)
    except RuntimeError as error:
        return False, str(error), output_path
    return True, output, output_path


def mcstas_test_runner(target, binary_path, test_parameters: str, n_particles: int):
    # If NeXus output is requested and the InstrumentDescriptionFile is needed, run a different script entirely...
    #   TODO think about actually doing this?
    # if target.flags & CBinaryTarget.Type.nexus and idf_required:
    #     run([config['idfgen'].get(str), str(binary), *options])
    return mccode_test_runner(target, binary_path, test_parameters, n_particles)


def mcxtrace_test_runner(target, binary_path, test_parameters: str, n_particles: int):
    return mccode_test_runner(target, binary_path, test_parameters, n_particles)


def mccode_test(compiler, runner, mpi: int = None, acc: bool = False, nexus: bool = False, **kwargs):
    """Specialize the compiler and runner based on requested number of processors and use of OpenACC, then test"""
    from functools import partial
    from mccode_antlr.compiler.c import CBinaryTarget
    target = CBinaryTarget(mpi=mpi is not None, acc=acc, count=1 if mpi is None else mpi, nexus=nexus)
    return _mccode_test(partial(compiler, target), partial(runner, target), **kwargs)


def mcstas_test(search_pattern=None, instr_count=None, skip_non_test: bool = False,
                mpi: int = None, acc: bool = False, nexus: bool = False, n_particles: int = 1000,
                dump: bool = False, workdir: Path = None):
    from mccode_antlr.reader import MCSTAS_REGISTRY as REGISTRY
    return mccode_test(mcstas_test_compiler, mcstas_test_runner, mpi, acc, nexus, registry=REGISTRY,
                       search_pattern=search_pattern, instr_count=instr_count, skip_non_test=skip_non_test,
                       n_particles=n_particles, dump=dump, workdir=workdir)


def mcxtrace_test(search_pattern=None, instr_count=None, skip_non_test: bool = False,
                  mpi: int = None, acc: bool = False, nexus: bool = False, n_particles: int = 1000,
                  dump: bool = False, workdir: Path = None):
    from mccode_antlr.reader import MCXTRACE_REGISTRY as REGISTRY
    return mccode_test(mcxtrace_test_compiler, mcxtrace_test_runner, mpi, acc, nexus, registry=REGISTRY,
                       search_pattern=search_pattern, instr_count=instr_count, skip_non_test=skip_non_test,
                       n_particles=n_particles, dump=dump, workdir=workdir)


def _mccode_test(compiler, runner, registry: Registry, search_pattern=None, instr_count=None,
                skip_non_test: bool = False, n_particles: int = 1000, workdir: Path = None, dump: bool=False):
    """Run McCode instrument test(s) using the provided `compiler` and `runner` functions to handle those tasks.

    Each takes the expected working directory name (a string) and the path to the instr file as input.
    The compiler should return only a boolean success indication.
    The runner should return a boolean success indicator, the contents of the run standard output, and the directory
    (if any) used to store run output files -- these files are intended to reside below the working directory and will
    be automatically removed by this function.

    Parameters:
        compiler: a function taking a string and Path and producing the necessary runtime executable
        runner: a function taking a string and Path and running the executable, storing its output
        registry: a Registry object which knows where to find all 'examples/*' instr files
        search_pattern: an optional positive filter for the registered 'examples/*' instr files
        instr_count: an optional positive count of filtered instr files to include
        skip_non_test: a flag to control whether instr files which do not specify test cases should be compiled and run
    """
    import re
    from loguru import logger as logging
    import tempfile
    from datetime import datetime
    logging.info(f"Finding test instruments in: {registry}")
    # we _require_ that all test instr files are in a folder called "examples" ...
    filenames = registry.match(re.compile(r'.*examples/.*\.instr'))
    # allow the user to limit which test cases can be found via a regular expression search
    if search_pattern is not None:
        if not isinstance(search_pattern, re.Pattern):
            search_pattern = re.compile(search_pattern)
        filenames = [x for x in filenames if search_pattern.search(x) is not None]
    # the examples folder has at least one script in it:
    filenames = [x for x in filenames if Path(x).suffix == '.instr']
    # optionally test case count limiter:
    if instr_count is not None and isinstance(instr_count, int) and instr_count > 0:
        filenames = filenames[:instr_count]
    # grab full paths to each file (in case this is a remote registry, they need to be fetched)
    filepaths = [registry.path(filename) for filename in filenames]

    longest_name = max(len(x.stem) for x in filepaths)

    # Build test objects from the '%Example:' line(s) in each file:
    tests = [x for filepath in filepaths for x in NightlyInstrExample.list_from_file(filepath)]

    binaries = dict()

    # By default, use a temporary directory -- but allow the user to specify someplace else:
    created = False
    if workdir is None:
        created = True
        workdir = tempfile.mkdtemp()
    if not isinstance(workdir, Path):
        workdir = Path(workdir)
    if not workdir.exists():
        created = True
        workdir.mkdir(parents=True)
    if not workdir.is_dir():
        raise RuntimeError(f'Expected {workdir} to be a directory, but it is not.')

    # Move into a temporary directory to ensure compilation/run times are from scratch

    logging.info("Compiling instruments")
    for test in tests:
        print(test)
        if test.sourcefile not in binaries and (test.test_number != 0 or not skip_non_test):
            t1 = datetime.now()
            binaries[test.sourcefile] = compiler(workdir, test.sourcefile, dump=dump, recompile=True, replace=False)
            test.compile_time = datetime.now() - t1
            test.compiled = True

            if binaries[test.sourcefile][0]:
                logging.info(f'%-{test.sourcefile.stem:>{longest_name}s}: {test.compile_time}')
            else:
                logging.info(f'%-{test.sourcefile.stem:>{longest_name}s}: COMPILE ERROR')
        else:
            logging.info(f'%-{test.sourcefile.stem:>{longest_name}s}: COMPILE skipped')

    logging.info("Running tests")
    for test in tests:
        if not binaries.get(test.sourcefile, (False, None))[0]:
            logging.info(f'%-{test.sourcefile.stem:>{longest_name}s}: No compile')
            continue
        if test.test_number < 1:
            logging.info(f'%-{test.sourcefile.stem:>{longest_name}s}: No test')
            continue

        t1 = datetime.now()
        logger.info(f'run {binaries[test.sourcefile][1]} -n {n_particles} {test.parameter_values}')
        test.ran, stdout, output_dir = runner(binaries[test.sourcefile][1], test.parameter_values, n_particles)
        test.run_time = datetime.now() - t1
        test.stdout = stdout.decode() if isinstance(stdout, bytes) else stdout

        if test.ran:
            logging.info(f'%-{test.sourcefile.stem:>{longest_name}s}: {test.run_time}')
        else:
            logging.info(f'%-{test.sourcefile.stem:>{longest_name}s}: RUNTIME ERROR')
            logging.debug(test.stdout)
            test.error_message = test.stdout
            continue

        detector_output = _monitor_name_file_name_match(output_dir, test.detector)
        logging.debug(f'Detector output stored in {detector_output}')
        test.test_value = - 1
        if detector_output is None or not detector_output.is_file():
            rdet = re.compile(f'{test.detector}_I= ([0-9+-eE.]+)')
            matches = rdet.findall(test.stdout)
            if len(matches):
                test.test_value = float(matches[0][0])
        else:
            with open(detector_output, 'r') as detector_file:
                detector_lines = detector_file.readlines()
            detector_pattern = re.compile('# values: ([0-9+-e.]+) ([0-9+-e.]+) ([0-9]+)')
            detector_matches = [detector_pattern.match(line) for line in detector_lines if detector_pattern.match(line)]
            if len(detector_matches):
                test.test_value = float(detector_matches[0].group(1))

        test.test_complete = True

    if created:
        import shutil
        shutil.rmtree(workdir)
    else:
        logging.info(f'Test compiled binaries and test case output directories are located under {workdir}.\n'
                     'You may wish to clean-up this directory to recover disk space.')

    # Since the output directories may no longer exist, save the test results ... here?
    for test in tests:
        test.save(Path())

    results = {t.get_display_name(): t.get_json_repr() for t in tests}
    # the 'ncount' and 'mpi' keys should be defined elsewhere
    results['_meta'] = {'date': datetime.now().isoformat(), 'hostname': get_hostname(),
                        'user': get_username(), 'cpu_type': get_cpu_name(), 'gpu_type': get_nvidia_gpu_name()}
    return results



def ispath(arg: str):
    from pathlib import Path
    return Path(arg)


def main(name, program):
    from argparse import ArgumentParser
    from loguru import logger
    parser = ArgumentParser(name, description=f'Test instrument compilation and runtime for {name}')
    parser.add_argument('-s', '--search', help='Regular expression positive filter for instrument names', default=None)
    parser.add_argument('-c', '--count', type=int, help='Maximum number of instruments to test', default=None)
    parser.add_argument('-k', '--skip', action='store_true', help='Skip instruments without test cases')
    parser.add_argument('--mpi', type=int, help='Number of mpi processes to use', default=None)
    parser.add_argument('--nexus', action='store_true', help='Whether to use NeXus output')
    parser.add_argument('-n', '--ncount', type=int, help='Number of particles to simulate per test', default=1000)
    parser.add_argument('-d','--dump', action='store_true', help='Output C source to file', default=False)
    parser.add_argument('-w','--workdir', type=ispath, help='Work directory, temporary if None', default=None)

    # logging.basicConfig(level=logging.DEBUG, format='{asctime} {levelname} {message}', style='{')
    # logging.basicConfig(level=logging.DEBUG)

    args = parser.parse_args()
    results = program(search_pattern=args.search, instr_count=args.count, skip_non_test=args.skip, mpi=args.mpi,
                      nexus=args.nexus, n_particles=args.ncount, dump=args.dump, workdir=args.workdir)
    results['_meta']['mpi'] = args.mpi
    results['_meta']['ncount'] = args.ncount

def mcstas_test_main():
    return main('mcstas_test', mcstas_test)

def mcxtract_test_main():
    return main('mcxtrace_test', mcxtrace_test)


if __name__ == '__main__':
    mcstas_test_main()
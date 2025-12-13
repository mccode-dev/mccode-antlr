from __future__ import annotations

from mccode_antlr import Flavor

def run_prog_message_output(prog: list[str]):
    """Run a program and return its output

    Parameters
    ----------
    prog : list[str]
        The program to run, prog[0] should be the binary name, findable by shutil.which

    Returns
    -------
    message: str
        None if the program ran successfully, or a message indicating what went wrong
    output: str
        The standard output of the program
    """
    from shutil import which
    from subprocess import run
    message, output = None, None
    if which(prog[0]):
        res = run(prog, capture_output=True, text=True)
        output = res.stdout
        if res.returncode or len(res.stderr):
            message = f'Evaluating "{" ".join(prog)}" produced error: {res.stderr}'
    else:
        message = f'{prog[0]} not found'

    return message, output


def make_assembler(name: str, flavor: Flavor = Flavor.MCSTAS):
    from mccode_antlr.assembler import Assembler
    from mccode_antlr.reader.registry import default_registries
    return Assembler(name, registries=default_registries(flavor))


def parse_instr_string(instr_source: str):
    from mccode_antlr.loader import parse_mcstas_instr
    return parse_mcstas_instr(instr_source)



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

"""Where a running simulation's output goes.

It used to be read into memory and discarded, so an ordinary `mcrun-antlr` run
showed the user nothing of the run itself -- no progress, no detector summary,
no component warnings -- and the only way to see any of it was `--verbose`,
which also turned on compiler verbosity.
"""
from pathlib import Path
from tempfile import TemporaryDirectory

from mccode_antlr import Flavor
from mccode_antlr.loader import parse_mcstas_instr
from mccode_antlr.test import compiled_test

INSTR = """DEFINE INSTRUMENT capt(dummy=0)
TRACE
COMPONENT o = Progress_bar() AT (0,0,0) ABSOLUTE
END
"""

# Progress_bar prints this at INITIALIZE, so it appears in any successful run
MARKER = '[capt] Initialize'


def build(directory):
    from mccode_antlr.run.runner import mccode_compile
    binary, _ = mccode_compile(parse_mcstas_instr(INSTR), Path(directory),
                               flavor=Flavor.MCSTAS)
    return binary


def run(binary, directory, capture):
    from mccode_antlr.run.runner import mccode_run_compiled
    return mccode_run_compiled(binary, {'mpi': False, 'acc': False}, directory,
                               '--ncount=1000 dummy=0', capture=capture,
                               use_defaults=True)


@compiled_test
def test_capture_yes_returns_the_output_and_shows_nothing(capfd):
    with TemporaryDirectory() as directory:
        binary = build(directory)
        result, _ = run(binary, Path(directory) / 'out', capture='yes')
        # bytes, as this has always returned -- callers decode it themselves
        assert MARKER in result.decode('utf-8')
        assert MARKER not in capfd.readouterr().out


@compiled_test
def test_capture_no_streams_to_the_terminal(capfd):
    with TemporaryDirectory() as directory:
        binary = build(directory)
        result, _ = run(binary, Path(directory) / 'out', capture='no')
        assert MARKER in capfd.readouterr().out
        assert result == ''


@compiled_test
def test_capture_tee_does_both_and_keeps_a_copy(capfd):
    from mccode_antlr.compiler.c import CAPTURE_LOG_NAME
    with TemporaryDirectory() as directory:
        binary = build(directory)
        out = Path(directory) / 'out'
        run(binary, out, capture='tee')
        assert MARKER in capfd.readouterr().out
        log = out / CAPTURE_LOG_NAME
        assert log.is_file(), f'{CAPTURE_LOG_NAME} was not written beside the results'
        assert MARKER in log.read_text()
        # beside mccode.sim, where the rest of the run's record already lives
        assert (out / 'mccode.sim').is_file()


@compiled_test
def test_a_boolean_still_selects_the_old_behaviour(capfd):
    """Simulation.run(capture=True) and the tests that predate --capture."""
    with TemporaryDirectory() as directory:
        binary = build(directory)
        result, _ = run(binary, Path(directory) / 'out', capture=True)
        assert MARKER in result.decode('utf-8')
        assert MARKER not in capfd.readouterr().out


@compiled_test
def test_a_failure_is_reported_in_readable_text():
    """The message used to interpolate raw bytes, so it read as b'...\\n...'."""
    import pytest
    from mccode_antlr.compiler.c import run_compiled_instrument
    with TemporaryDirectory() as directory:
        binary = build(directory)
        with pytest.raises(RuntimeError) as caught:
            run_compiled_instrument(binary, {'mpi': False, 'acc': False},
                                    f'--dir {Path(directory) / "out"} nosuchparam=1',
                                    capture='yes')
        message = str(caught.value)
        assert 'nosuchparam' in message
        assert "b'" not in message


@compiled_test
def test_tee_keeps_a_log_for_every_point_of_a_scan():
    from mccode_antlr.compiler.c import CAPTURE_LOG_NAME
    from mccode_antlr.run.range import parse_scan_parameters
    from mccode_antlr.run.runner import mccode_run_scan
    with TemporaryDirectory() as directory:
        binary = build(directory)
        out = Path(directory) / 'scan'
        mccode_run_scan('capt', binary, {'mpi': False, 'acc': False},
                        parse_scan_parameters(['dummy=0,1,2']), out, grid=False,
                        capture='tee', use_defaults=True, ncount=1000)
        logs = sorted(out.glob(f'*/{CAPTURE_LOG_NAME}'))
        assert len(logs) == 3, f'expected one log per scan point, found {logs}'
        assert all(MARKER in log.read_text() for log in logs)

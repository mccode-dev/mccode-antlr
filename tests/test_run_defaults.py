"""Defaults of the mcrun-antlr / mxrun-antlr command line.

Two of them used to make an ordinary run far slower than it needed to be:
tracing was on, so every particle's state at every component was printed,
funnelled through the MPI launcher and then captured; and the MPI process count
defaulted to a literal `-np 0`.
"""
import pytest


def parse(*argv):
    from mccode_antlr.run.runner import mccode_run_script_parser
    return mccode_run_script_parser('mcstas').parse_args(['dummy.instr', *argv])


class TestTraceDefault:
    def test_off_by_default(self):
        """Classic mcrun defaults -t to 0; this had it on."""
        assert parse().trace is False

    def test_turned_on_explicitly(self):
        assert parse('-t').trace is True
        assert parse('--trace').trace is True

    def test_no_trace_still_accepted(self):
        assert parse('--no-trace').trace is False

    def test_the_runtime_argument_follows_it(self):
        from mccode_antlr.run.runner import mccode_runtime_dict_to_args_list
        assert '--trace' not in mccode_runtime_dict_to_args_list({'trace': False})
        assert '--trace' in mccode_runtime_dict_to_args_list({'trace': True})


class TestProcessCount:
    def test_auto_by_default(self):
        assert parse().mpi == 'auto'

    def test_an_integer_is_kept(self):
        assert parse('--mpi', '4').mpi == 4

    def test_process_count_is_an_alias(self):
        """The flag this replaces, kept working for existing scripts."""
        assert parse('--process-count', '6').mpi == 6

    def test_zero_still_means_system_default(self):
        """--process-count 0 was the old spelling of 'let the system decide'."""
        assert parse('--process-count', '0').mpi == 'auto'
        assert parse('--mpi', '-1').mpi == 'auto'

    def test_auto_spelled_out(self):
        assert parse('--mpi', 'auto').mpi == 'auto'
        assert parse('--mpi', 'AUTO').mpi == 'auto'

    def test_a_bad_value_is_rejected(self):
        with pytest.raises(SystemExit):
            parse('--mpi', 'bogus')

    def test_it_is_not_wrapped_in_a_list(self):
        """With nargs=1 this arrived as [4] and reached mpirun as '-np [4]'."""
        assert not isinstance(parse('--mpi', '4').mpi, list)


class TestMpiProcessFlags:
    def test_a_count_is_passed_through(self):
        from mccode_antlr.compiler.c import mpi_process_flags
        assert mpi_process_flags(4) == ['-np', '4']

    def test_auto_names_no_number(self, monkeypatch):
        """'-np 0' is a request for zero processes, not a way to say 'default';
        only OpenMPI tolerated it. The '--' separator does the other job it was
        credited with."""
        import platform
        from mccode_antlr.compiler.c import mpi_process_flags
        monkeypatch.setattr(platform, 'system', lambda: 'Linux')
        assert mpi_process_flags('auto') == []
        assert mpi_process_flags(0) == []

    def test_windows_gets_an_explicit_count(self, monkeypatch):
        """msmpi's mpiexec accepts neither '--' nor a missing count."""
        import os
        import platform
        from mccode_antlr.compiler.c import mpi_process_flags
        monkeypatch.setattr(platform, 'system', lambda: 'Windows')
        monkeypatch.setattr(os, 'cpu_count', lambda: 8)
        assert mpi_process_flags('auto') == ['-np', '8']

    def test_windows_survives_an_unknown_cpu_count(self, monkeypatch):
        import os
        import platform
        from mccode_antlr.compiler.c import mpi_process_flags
        monkeypatch.setattr(platform, 'system', lambda: 'Windows')
        monkeypatch.setattr(os, 'cpu_count', lambda: None)
        assert mpi_process_flags('auto') == ['-np', '1']


class TestValueParser:
    @pytest.mark.parametrize('given,expected', [
        ('auto', 'auto'), (' Auto ', 'auto'), ('1', 1), ('12', 12),
        ('0', 'auto'), ('-3', 'auto'),
    ])
    def test_accepted(self, given, expected):
        from mccode_antlr.run.runner import mpi_process_count
        assert mpi_process_count(given) == expected

    @pytest.mark.parametrize('given', ['bogus', '', '2.5', 'four'])
    def test_rejected(self, given):
        from argparse import ArgumentTypeError
        from mccode_antlr.run.runner import mpi_process_count
        with pytest.raises(ArgumentTypeError):
            mpi_process_count(given)


class TestCaptureFlag:
    def test_streams_by_default(self):
        """The simulation's output is the user's progress indicator; it used to be
        captured and then dropped on the floor, so a plain run showed nothing."""
        assert parse().capture == 'no'

    @pytest.mark.parametrize('mode', ['no', 'yes', 'tee'])
    def test_modes_accepted(self, mode):
        assert parse('--capture', mode).capture == mode

    def test_a_bad_mode_is_rejected(self):
        with pytest.raises(SystemExit):
            parse('--capture', 'sometimes')

    def test_verbose_no_longer_decides_it(self):
        """--verbose is compiler and linker verbosity; it used to double as the
        only way to see the simulation at all."""
        assert parse('--verbose').capture == 'no'
        assert parse('--no-verbose').capture == 'no'


class TestNormaliseCapture:
    def test_the_modes_pass_through(self):
        from mccode_antlr.compiler.c import normalise_capture
        for mode in ('no', 'yes', 'tee'):
            assert normalise_capture(mode) == mode

    def test_booleans_still_work(self):
        """capture= was a bool, and Simulation.run still passes one."""
        from mccode_antlr.compiler.c import normalise_capture
        assert normalise_capture(True) == 'yes'
        assert normalise_capture(False) == 'no'

    def test_an_unknown_mode_is_refused(self):
        from mccode_antlr.compiler.c import normalise_capture
        with pytest.raises(ValueError, match='capture must be one of'):
            normalise_capture('maybe')

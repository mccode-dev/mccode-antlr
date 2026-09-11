"""Defaults of the mcrun-antlr / mxrun-antlr command line."""
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

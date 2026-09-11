"""The live scan display behind --capture=tui.

It summarises rather than echoes, so the parsing of the runtime's output is the
part worth pinning down: what it recognises, what it ignores, and what it does
when there is nothing to recognise.
"""
import pytest

from mccode_antlr.run.report import ScanReporter


def reporter(points=3, width=200):
    """A reporter rendering to a fixed-width buffer rather than a real terminal."""
    from rich.console import Console
    made = ScanReporter('demo', points)
    made.console = Console(file=__import__('io').StringIO(), width=width,
                           force_terminal=True)
    return made


def rendered(made):
    from rich.console import Console
    import io
    buffer = io.StringIO()
    Console(file=buffer, width=200, force_terminal=False).print(made._renderable())
    return buffer.getvalue()


class TestParsing:
    def test_a_percentage_moves_the_bar(self):
        made = reporter()
        made.start_point(0, {'a': 1})
        made.consume(b'40 %\n')
        assert made._within.tasks[0].completed == 40
        assert made._within.tasks[0].total == 100

    def test_percentages_are_clamped(self):
        """mcget_run_num can overshoot mcget_ncount slightly under MPI."""
        made = reporter()
        made.start_point(0)
        made.consume(b'103 %\n')
        assert made._within.tasks[0].completed == 100

    def test_a_detector_line_is_kept(self):
        made = reporter()
        made.start_point(0)
        made.consume(b'Detector: mon_I=1.234e-05 mon_ERR=1e-07 mon_N=4200\n')
        assert 'mon' in rendered(made) and '1.234e-05' in rendered(made)

    def test_errors_and_warnings_are_surfaced(self):
        made = reporter()
        made.start_point(0)
        made.consume(b'Error: unrecognized parameter nosuch (mcparseoptions)\n')
        assert 'unrecognized parameter' in rendered(made)

    def test_ordinary_output_is_not_shown(self):
        """It is in the log; the display is a summary, not a mirror."""
        made = reporter()
        made.start_point(0)
        made.consume(b'*** TRACE end ***\n')
        made.consume(b'Save [demo]\n')
        assert 'TRACE end' not in rendered(made)
        assert 'Save [demo]' not in rendered(made)

    def test_blank_lines_are_ignored(self):
        made = reporter()
        made.start_point(0)
        made.consume(b'\n')
        made.consume(b'   \r\n')  # no exception, nothing recorded

    def test_undecodable_bytes_do_not_raise(self):
        made = reporter()
        made.start_point(0)
        made.consume(b'Error: \xff\xfe bad bytes\n')
        assert 'bad bytes' in rendered(made)

    def test_only_the_most_recent_messages_are_kept(self):
        """A failing run can emit thousands; the display must stay a fixed size."""
        made = reporter()
        made.start_point(0)
        for i in range(50):
            made.consume(f'Error: number {i}\n'.encode())
        assert 'number 49' in rendered(made)
        assert 'number 0\n' not in rendered(made)


class TestPointProgress:
    def test_a_point_starts_indeterminate(self):
        """An instrument without Progress_bar prints no percentages, so the bar
        must not pretend to know how far along it is."""
        made = reporter()
        made.start_point(0)
        assert made._within.tasks[0].total is None

    def test_finishing_advances_the_scan(self):
        made = reporter(points=3)
        for number in range(3):
            made.start_point(number, {'a': number})
            made.finish_point(number)
        assert made._points.tasks[0].completed == 3

    def test_a_new_point_forgets_the_previous_one(self):
        made = reporter()
        made.start_point(0, {'a': 0})
        made.consume(b'Detector: mon_I=1 mon_ERR=0 mon_N=1\n')
        made.consume(b'Error: something\n')
        made.start_point(1, {'a': 1})
        shown = rendered(made)
        assert 'mon' not in shown and 'something' not in shown
        assert 'a=1' in shown

    def test_parameter_values_are_shown(self):
        made = reporter()
        made.start_point(0, {'angle': 30.0, 'E_i': 5})
        shown = rendered(made)
        assert 'angle=30.0' in shown and 'E_i=5' in shown


class TestModeResolution:
    def resolve(self, capture, **kwargs):
        from mccode_antlr.run.runner import resolve_scan_reporter
        return resolve_scan_reporter(capture, 'demo', kwargs.pop('points', 3), **kwargs)

    def test_other_modes_are_untouched(self):
        for mode in ('no', 'yes', 'tee'):
            assert self.resolve(mode) == (mode, None)

    def test_a_bool_is_untouched(self):
        assert self.resolve(True) == (True, None)

    def test_tui_falls_back_when_not_a_terminal(self, monkeypatch):
        """A pipe or a CI log would get control sequences nobody can act on."""
        import mccode_antlr.run.report as report
        monkeypatch.setattr(report, 'tui_is_usable', lambda: False)
        assert self.resolve('tui') == ('tee', None)

    def test_tui_falls_back_for_a_dry_run(self):
        """Nothing runs, so there is no output to summarise."""
        assert self.resolve('tui', dry_run=True) == ('tee', None)

    def test_tui_builds_a_reporter_on_a_terminal(self, monkeypatch):
        import mccode_antlr.run.report as report
        monkeypatch.setattr(report, 'tui_is_usable', lambda: True)
        mode, made = self.resolve('tui')
        assert mode == 'tui' and isinstance(made, ScanReporter)

    def test_an_unscanned_run_is_still_one_point(self, monkeypatch):
        """parameters_to_scan reports zero points when nothing is scanned."""
        import mccode_antlr.run.report as report
        monkeypatch.setattr(report, 'tui_is_usable', lambda: True)
        _, made = self.resolve('tui', points=0)
        assert made.total_points == 1


class TestCaptureMode:
    def test_tui_is_a_capture_mode(self):
        from mccode_antlr.compiler.c import CAPTURE_MODES, normalise_capture
        assert 'tui' in CAPTURE_MODES
        assert normalise_capture('tui') == 'tui'

    def test_the_cli_accepts_it(self):
        from mccode_antlr.run.runner import mccode_run_script_parser
        args = mccode_run_script_parser('mcstas').parse_args(
            ['dummy.instr', '--capture', 'tui'])
        assert args.capture == 'tui'

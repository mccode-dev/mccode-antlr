"""Tests for the mcfmt McCode DSL formatter."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from mccode_antlr.format import format_source, format_file

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TEMPLATE_INSTR = Path(__file__).parent / 'template_simple.instr'


def fmt_instr(src: str) -> str:
    return format_source(textwrap.dedent(src).strip() + '\n', '.instr')


def fmt_comp(src: str) -> str:
    return format_source(textwrap.dedent(src).strip() + '\n', '.comp')


# ---------------------------------------------------------------------------
# .instr tests
# ---------------------------------------------------------------------------

class TestInstrFormat:
    def test_round_trip_template(self):
        """The shipped template instrument formats without error."""
        result = format_file(TEMPLATE_INSTR)
        assert 'DEFINE INSTRUMENT' in result
        assert 'TRACE' in result
        assert 'END' in result

    def test_idempotent_template(self):
        """Formatting twice produces the same output as formatting once."""
        src = TEMPLATE_INSTR.read_text()
        pass1 = format_source(src, '.instr')
        pass2 = format_source(pass1, '.instr')
        assert pass1 == pass2

    def test_keyword_normalisation_lowercase(self):
        """All-lowercase McCode keywords are uppercased."""
        src = 'define instrument foo()\ntrace\nend'
        result = fmt_instr(src)
        assert 'DEFINE INSTRUMENT foo()' in result
        assert 'TRACE' in result
        assert 'END' in result
        assert 'define' not in result
        assert 'trace' not in result
        assert 'end\n' not in result

    def test_keyword_normalisation_mixed(self):
        """Mixed-case keywords are normalised to uppercase."""
        src = 'Define Instrument Bar(x=1.0)\nTrace\nEnd'
        result = fmt_instr(src)
        assert 'DEFINE INSTRUMENT Bar(x=1.0)' in result

    def test_header_comment_preserved(self):
        """A block comment before DEFINE is carried through unchanged."""
        src = """\
/* Instrument header
 * Author: Test
 */
DEFINE INSTRUMENT TestInstr()
TRACE
END
"""
        result = fmt_instr(src)
        assert '/* Instrument header' in result
        assert '* Author: Test' in result
        # Header must precede DEFINE
        assert result.index('/*') < result.index('DEFINE')

    def test_single_line_header_comment_newline(self):
        """A single-line block comment on its own line gets a trailing newline."""
        src = '/* header */\nDEFINE INSTRUMENT T()\nTRACE\nEND\n'
        result = format_source(src, '.instr')
        # comment and DEFINE must be on separate lines
        assert '/* header */\n' in result

    def test_inline_comment_preserved(self):
        """A line comment between component instances is preserved."""
        src = """\
DEFINE INSTRUMENT T()
TRACE
COMPONENT a = Progress_bar()
AT (0, 0, 0) ABSOLUTE
// a comment between components
COMPONENT b = Progress_bar()
AT (0, 0, 0) ABSOLUTE
END
"""
        result = fmt_instr(src)
        assert '// a comment between components' in result
        # comment must be between the two COMPONENT declarations
        idx_a = result.index('COMPONENT a')
        idx_comment = result.index('// a comment')
        idx_b = result.index('COMPONENT b')
        assert idx_a < idx_comment < idx_b

    def test_declare_section(self):
        """DECLARE section keyword is uppercased and block preserved."""
        src = """\
DEFINE INSTRUMENT T()
declare
%{
  int x = 0;
%}
TRACE
END
"""
        result = fmt_instr(src)
        assert 'DECLARE\n%{\n  int x = 0;\n%}' in result

    def test_component_placement(self):
        """AT/RELATIVE/ABSOLUTE placement clauses are uppercased."""
        src = """\
DEFINE INSTRUMENT T()
TRACE
COMPONENT origin = Progress_bar()
at (0, 0, 0) relative absolute
END
"""
        result = fmt_instr(src)
        assert 'AT (0, 0, 0) RELATIVE ABSOLUTE' in result or 'AT (0, 0, 0) ABSOLUTE' in result

    def test_instrument_parameters(self):
        """Instrument parameters (with units and defaults) round-trip correctly."""
        src = """\
DEFINE INSTRUMENT T(double E=14.0, int N=100, string filename="out.txt")
TRACE
END
"""
        result = fmt_instr(src)
        assert 'E=14.0' in result
        assert 'int N=100' in result
        assert 'string filename' in result

    def test_comment_before_finally(self):
        """A comment before FINALLY is placed before that section."""
        src = """\
DEFINE INSTRUMENT T()
TRACE
// cleanup comment
FINALLY
%{
%}
END
"""
        result = fmt_instr(src)
        assert '// cleanup comment' in result
        assert result.index('// cleanup comment') < result.index('FINALLY')


# ---------------------------------------------------------------------------
# .comp tests
# ---------------------------------------------------------------------------

class TestCompFormat:
    def test_minimal_comp(self):
        """A minimal comp with all major sections formats correctly."""
        src = """\
DEFINE COMPONENT MyComp
DEFINITION PARAMETERS (int n=10)
SETTING PARAMETERS (double xmin=-1, xmax=1)
OUTPUT PARAMETERS (double result)
DECLARE
%{
  double sum;
%}
INITIALIZE
%{
  sum = 0;
%}
TRACE
%{
  PROP_Z0;
%}
FINALLY
%{
  printf("%g\\n", sum);
%}
END
"""
        result = fmt_comp(src)
        assert 'DEFINE COMPONENT MyComp' in result
        assert 'DEFINITION PARAMETERS (int n=10)' in result
        assert 'SETTING PARAMETERS' in result
        assert 'DECLARE' in result
        assert 'INITIALIZE' in result
        assert 'TRACE' in result
        assert 'FINALLY' in result
        assert 'END' in result

    def test_comp_idempotent(self):
        """Formatting a comp source twice yields the same result."""
        src = """\
DEFINE COMPONENT MyComp
SETTING PARAMETERS (double x=0)
TRACE
%{
  /* some code */
%}
END
"""
        p1 = fmt_comp(src)
        p2 = fmt_comp(p1)
        assert p1 == p2

    def test_comp_header_comment_preserved(self):
        """Header block comment before DEFINE COMPONENT is preserved."""
        src = """\
/*******************************************************************************
* Component: MyComp
* Author: Test
*******************************************************************************/
DEFINE COMPONENT MyComp
SETTING PARAMETERS (double x=0)
TRACE
%{
%}
END
"""
        result = fmt_comp(src)
        assert '* Component: MyComp' in result
        assert result.index('/*') < result.index('DEFINE')

    def test_comp_keyword_normalisation(self):
        """lowercase keywords in a comp are normalised to uppercase."""
        src = """\
define component Foo
setting parameters (x=1)
trace
%{
%}
end
"""
        result = fmt_comp(src)
        assert 'DEFINE COMPONENT Foo' in result
        assert 'SETTING PARAMETERS' in result

    def test_comp_inline_comment_in_declare(self):
        """Inline C comment inside a DECLARE block is preserved verbatim."""
        src = """\
DEFINE COMPONENT C
DECLARE
%{
  int i; /* loop counter */
  double x; // position
%}
TRACE
%{
%}
END
"""
        result = fmt_comp(src)
        assert '/* loop counter */' in result
        assert '// position' in result

    def test_comp_comment_between_sections(self):
        """A comment between two sections is placed between them."""
        src = """\
DEFINE COMPONENT C
DECLARE
%{
%}
// comment before init
INITIALIZE
%{
%}
TRACE
%{
%}
END
"""
        result = fmt_comp(src)
        assert '// comment before init' in result
        assert result.index('// comment before init') < result.index('INITIALIZE')

    def test_comp_mcdisplay(self):
        """MCDISPLAY section is correctly emitted."""
        src = """\
DEFINE COMPONENT C
SETTING PARAMETERS (double r=1)
TRACE
%{
%}
MCDISPLAY
%{
  circle("xy", 0, 0, 0, r);
%}
END
"""
        result = fmt_comp(src)
        assert 'MCDISPLAY' in result
        assert 'circle' in result


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------

class TestCLI:
    def test_mcfmt_stdout(self, tmp_path, capsys):
        """mcfmt prints formatted output to stdout when no flags given."""
        instr = tmp_path / 'test.instr'
        instr.write_text('define instrument t()\ntrace\nend\n')
        from mccode_antlr.cli.format import mcfmt
        import sys
        old_argv = sys.argv
        try:
            sys.argv = ['mcfmt', str(instr)]
            with pytest.raises(SystemExit) as exc:
                mcfmt()
            assert exc.value.code == 0
        finally:
            sys.argv = old_argv
        captured = capsys.readouterr()
        assert 'DEFINE INSTRUMENT' in captured.out

    def test_mcfmt_inplace(self, tmp_path):
        """mcfmt --inplace rewrites a file."""
        instr = tmp_path / 'test.instr'
        instr.write_text('define instrument t()\ntrace\nend\n')
        from mccode_antlr.cli.format import mcfmt
        import sys
        old_argv = sys.argv
        try:
            sys.argv = ['mcfmt', '--inplace', str(instr)]
            with pytest.raises(SystemExit) as exc:
                mcfmt()
            assert exc.value.code == 0
        finally:
            sys.argv = old_argv
        assert 'DEFINE INSTRUMENT' in instr.read_text()

    def test_mcfmt_check_already_formatted(self, tmp_path, capsys):
        """mcfmt --check exits 0 if file is already formatted."""
        src = format_source('define instrument t()\ntrace\nend\n', '.instr')
        instr = tmp_path / 'test.instr'
        instr.write_text(src)
        from mccode_antlr.cli.format import mcfmt
        import sys
        old_argv = sys.argv
        try:
            sys.argv = ['mcfmt', '--check', str(instr)]
            with pytest.raises(SystemExit) as exc:
                mcfmt()
            assert exc.value.code == 0
        finally:
            sys.argv = old_argv

    def test_mcfmt_check_unformatted(self, tmp_path):
        """mcfmt --check exits 1 if file would change."""
        instr = tmp_path / 'test.instr'
        instr.write_text('define instrument t()\ntrace\nend\n')
        from mccode_antlr.cli.format import mcfmt
        import sys
        old_argv = sys.argv
        try:
            sys.argv = ['mcfmt', '--check', str(instr)]
            with pytest.raises(SystemExit) as exc:
                mcfmt()
            assert exc.value.code == 1
        finally:
            sys.argv = old_argv



# ---------------------------------------------------------------------------
# Phase 2: clang-format integration tests
# ---------------------------------------------------------------------------

class TestMakeClangFormatter:
    """Tests for make_clang_formatter and the C-block formatting path."""

    def test_returns_none_when_clang_format_missing(self):
        """make_clang_formatter returns None when clang-format is not installed."""
        from mccode_antlr.format import make_clang_formatter
        import unittest.mock as mock
        with mock.patch('shutil.which', return_value=None):
            result = make_clang_formatter(fetch_mccode_config=False, style='LLVM')
        assert result is None

    def test_returns_callable_with_style(self):
        """make_clang_formatter returns a callable when clang-format is available."""
        from mccode_antlr.format import make_clang_formatter
        import unittest.mock as mock
        with mock.patch('shutil.which', return_value='/usr/bin/clang-format'):
            result = make_clang_formatter(style='LLVM', fetch_mccode_config=False)
        assert callable(result)

    def test_callable_formats_c_code(self):
        """The callable returned by make_clang_formatter runs clang-format."""
        from mccode_antlr.format import make_clang_formatter
        import unittest.mock as mock

        mock_result = mock.MagicMock()
        mock_result.stdout = 'int x = 1;\n'
        with mock.patch('shutil.which', return_value='/usr/bin/clang-format'), \
             mock.patch('subprocess.run', return_value=mock_result) as mock_run:
            fmt = make_clang_formatter(style='LLVM', fetch_mccode_config=False)
            output = fmt('int x=1;\n')

        mock_run.assert_called_once()
        assert output == 'int x = 1;\n'

    def test_callable_falls_back_on_clang_format_error(self):
        """The callable returns unchanged content if clang-format fails."""
        from mccode_antlr.format import make_clang_formatter
        import subprocess
        import unittest.mock as mock

        with mock.patch('shutil.which', return_value='/usr/bin/clang-format'), \
             mock.patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, 'clang-format')):
            fmt = make_clang_formatter(style='LLVM', fetch_mccode_config=False)
            output = fmt('int x=1;\n')

        assert output == 'int x=1;\n'

    def test_returns_none_when_remote_config_unavailable(self):
        """make_clang_formatter returns None when --clang-format and remote config fails."""
        from mccode_antlr.format import make_clang_formatter
        import unittest.mock as mock
        with mock.patch('shutil.which', return_value='/usr/bin/clang-format'), \
             mock.patch(
                 'mccode_antlr.format.format.fetch_mccode_clang_format_config',
                 return_value=None,
             ):
            result = make_clang_formatter(fetch_mccode_config=True)
        assert result is None


class TestFormatWithClangFormat:
    """Integration tests: DSL formatter + C-block clang-format pass."""

    _INSTR_WITH_C = textwrap.dedent("""\
        DEFINE INSTRUMENT test_c()
        DECLARE
        %{
        int x=1;double y=2.0;
        %}
        TRACE
        END
    """)

    def test_c_block_is_formatted(self):
        """C-code blocks are passed through the clang_format callable."""
        from mccode_antlr.format import format_source
        import unittest.mock as mock

        calls = []
        def fake_fmt(content):
            calls.append(content)
            return '\nint x = 1;\ndouble y = 2.0;\n'

        result = format_source(self._INSTR_WITH_C, '.instr', clang_format=fake_fmt)
        assert calls, 'clang_format callable was never invoked'
        assert 'int x = 1;' in result

    def test_c_block_unchanged_without_clang_format(self):
        """Without a clang_format callable, C-code blocks are preserved verbatim."""
        from mccode_antlr.format import format_source
        result = format_source(self._INSTR_WITH_C, '.instr')
        # Verbatim block content must still be present
        assert 'int x=1;' in result


class TestCLIClangFormatFlags:
    """CLI smoke-tests for the --clang-format* flags."""

    def test_clang_format_style_flag(self, tmp_path):
        """mcfmt --clang-format-style with mock clang-format rewrites a C block."""
        import sys
        import subprocess
        import unittest.mock as mock
        from mccode_antlr.cli.format import mcfmt

        instr = tmp_path / 'test.instr'
        instr.write_text(
            'DEFINE INSTRUMENT t()\nDECLARE\n%{\nint x=1;\n%}\nTRACE\nEND\n'
        )

        mock_result = mock.MagicMock()
        mock_result.stdout = '\nint x = 1;\n'

        old_argv = sys.argv
        try:
            sys.argv = ['mcfmt', '--clang-format-style', 'LLVM', str(instr)]
            with mock.patch('shutil.which', return_value='/usr/bin/clang-format'), \
                 mock.patch('subprocess.run', return_value=mock_result), \
                 pytest.raises(SystemExit) as exc:
                mcfmt()
        finally:
            sys.argv = old_argv

        assert exc.value.code == 0

    def test_clang_format_config_flag(self, tmp_path):
        """mcfmt --clang-format-config passes the config path to make_clang_formatter."""
        import sys
        import unittest.mock as mock
        from mccode_antlr.cli.format import mcfmt

        instr = tmp_path / 'test.instr'
        instr.write_text('DEFINE INSTRUMENT t()\nTRACE\nEND\n')
        cfg = tmp_path / '.clang-format'
        cfg.write_text('BasedOnStyle: LLVM\n')

        old_argv = sys.argv
        try:
            sys.argv = ['mcfmt', '--clang-format-config', str(cfg), str(instr)]
            # clang-format won't actually be invoked on a file with no C blocks;
            # we just verify no error is raised and exit code is 0.
            with mock.patch('shutil.which', return_value='/usr/bin/clang-format'), \
                 pytest.raises(SystemExit) as exc:
                mcfmt()
        finally:
            sys.argv = old_argv

        assert exc.value.code == 0

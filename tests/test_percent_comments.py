"""McCode's `%`-to-end-of-line comments.

instrument.l has carried these since long before mccode-antlr:

    "%"{EOL}         instr_current_line++; /* Ignore comment. */
    "% "[^\n]*{EOL}  instr_current_line++; /* Ignore comment. */

The space after `%` is load-bearing. Without it the token is modulo, and the
rules are ordered so that `n%3` and `n %3` keep working while `n % 3` becomes a
comment -- a quirk of classic McCode that this reproduces rather than fixes,
verified against the mcstas 3.8.5 binary.
"""
import pytest
from antlr4 import InputStream
from antlr4.error.ErrorListener import ErrorListener

from mccode_antlr.grammar import McInstr_parse

INSTR = """DEFINE INSTRUMENT t(int n=7)
TRACE
COMPONENT a = Arm() AT (0, 0, 0) ABSOLUTE
{line}
COMPONENT b = Arm() AT (0, 0, {expr}) RELATIVE a
END
"""


class _Collect(ErrorListener):
    def __init__(self):
        self.errors = []

    def syntaxError(self, recognizer, offending, line, column, message, e):
        self.errors.append((line, column, message))


def _errors(line='', expr='1'):
    listener = _Collect()
    McInstr_parse(InputStream(INSTR.format(line=line, expr=expr)), 'prog', listener)
    return listener.errors


@pytest.mark.parametrize('line', [
    '% rotation along X, monochromator surface is in the XZ plane',
    '% ------------------------------------------------------------',
    '%',
    '%    leading whitespace in the comment body',
])
def test_percent_comment_lines_are_ignored(line):
    assert _errors(line=line) == []


@pytest.mark.parametrize('expr', ['n%3', 'n %3'])
def test_modulo_without_a_space_after_percent_still_parses(expr):
    """What matters is the character *after* `%`, not the one before it."""
    assert _errors(expr=expr) == []


@pytest.mark.parametrize('expr', ['n % 3', 'n% 3'])
def test_percent_then_space_is_a_comment_as_it_is_for_classic_mccode(expr):
    """Either spelling swallows the rest of the line, so the statement never closes.

    classic mcstas 3.8.5 reports `ERROR: syntax error` on both of these too --
    this is bug-compatibility, deliberate rather than accidental. Spaced modulo
    is unusable outside a %{ %} block in both implementations.
    """
    assert _errors(expr=expr), 'expected the comment to swallow the closing paren'


def test_percent_brace_block_is_not_a_comment():
    """UnparsedBlock must still win: `%{` is not followed by a space or newline."""
    source = """DEFINE INSTRUMENT t()
DECLARE %{
double x;
%}
TRACE
COMPONENT a = Arm() AT (0, 0, 0) ABSOLUTE
END
"""
    listener = _Collect()
    McInstr_parse(InputStream(source), 'prog', listener)
    assert listener.errors == []


def test_percent_include_is_not_a_comment():
    source = """DEFINE INSTRUMENT t()
TRACE
COMPONENT a = Arm() AT (0, 0, 0) ABSOLUTE
%include "other"
END
"""
    listener = _Collect()
    McInstr_parse(InputStream(source), 'prog', listener)
    assert listener.errors == []

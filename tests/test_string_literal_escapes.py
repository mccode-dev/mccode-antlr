"""String literals inside expressions must stay valid C wherever an expression's
*text* is itself written out as a C string.

mccode-dev/mccode-antlr#360: a numeric component parameter set by an expression
containing a string literal, e.g. ``blah=f("my choice", wavelength)``, was
recorded for NeXus by wrapping its text in quotes, producing the invalid
``"f("my choice", wavelength)"``. The instrument parameter table did the same with
default-value expressions. Both now escape the text instead of only quoting it.
"""
import re
from textwrap import dedent

import pytest

from mccode_antlr.common.expression import Expr
from mccode_antlr.loader import parse_mcstas_instr
from mccode_antlr.reader.registry import InMemoryRegistry

# One complete C string literal: no bare quote, backslash or newline inside.
C_STRING = r'"(?:[^"\\\n]|\\.)*"'


def c_string_value(literal: str) -> str:
    """Decode a C string literal (ASCII escapes only) back to its text."""
    assert re.fullmatch(C_STRING, literal), f'not a single C string literal: {literal}'
    return literal[1:-1].encode('latin-1').decode('unicode-escape')


REGISTRY = InMemoryRegistry('string_literal_escapes')
REGISTRY.add_comp('takes_double', dedent("""\
    DEFINE COMPONENT takes_double
    SETTING PARAMETERS (double blah=1, string name="none")
    TRACE
    %{
    %}
    END
    """))

INSTR = dedent(r'''
    DEFINE INSTRUMENT string_literal_escapes(double wavelength=1, double other=strlen("a\"b"),
                                             string quoted="x \"y\"")
    DECLARE %{
    double some_function_with_string_input(char * s, double x){return x;}
    %}
    TRACE
    COMPONENT origin = takes_double(
        blah=some_function_with_string_input("my choice", wavelength), name="a \"q\""
    ) AT (0, 0, 0) ABSOLUTE
    END
    ''')


@pytest.fixture(scope='module')
def instr():
    return parse_mcstas_instr(INSTR, registries=[REGISTRY])


def _lines(generated):
    return (generated if isinstance(generated, str) else '\n'.join(map(str, generated))).splitlines()


@pytest.mark.parametrize('source', [
    r'"a \"q\""',   # ends with an escaped quote
    r'"ab\""',
    r'"\\"',        # a lone escaped backslash
    r'"plain"',
])
def test_string_literal_round_trips(source):
    assert str(Expr.parse(source)) == source


def test_adjacent_string_literals_concatenate():
    assert str(Expr.parse(r'"a\"" "b"')) == r'"a\"b"'


def test_nexus_record_of_numeric_parameter_is_valid_c(instr):
    from mccode_antlr.translators.c_initialise import cogen_comp_setpos
    comp = instr.components[0]
    lines = _lines(cogen_comp_setpos(0, comp, None, instr, {comp.type.name: []}))
    pattern = rf'\s*mccomp_param_nexus\(nxhandle, ({C_STRING}), ({C_STRING}), ({C_STRING}), ({C_STRING}), ({C_STRING})\);'
    records = {}
    for line in lines:
        if 'mccomp_param_nexus' in line:
            match = re.fullmatch(pattern, line)
            assert match, f'invalid C: {line}'
            group, name, default, value, c_type = map(c_string_value, match.groups())
            records[name] = value
    assert records['blah'] == 'some_function_with_string_input("my choice", ' \
                              '_instrument_var._parameters.wavelength)'
    # a string parameter's value is passed as the literal itself
    assert records['name'] == 'a "q"'


def test_instrument_parameter_table_defaults_are_valid_c(instr):
    from mccode_antlr.translators.c_decls import declarations_pre_libraries
    comp = instr.components[0]
    tables = declarations_pre_libraries(instr, [], {comp.type.name: []})[0]
    pattern = rf'\s*\{{({C_STRING}), &\(_instrument_var\._parameters\.\w+\), \w+, ({C_STRING}), ({C_STRING})\}},'
    defaults = {}
    for line in _lines(tables):
        if '&(_instrument_var._parameters.' in line:
            match = re.fullmatch(pattern, line)
            assert match, f'invalid C: {line}'
            name, default, _ = map(c_string_value, match.groups())
            defaults[name] = default
    assert defaults == {'wavelength': '1', 'other': 'strlen("a\\"b")', 'quoted': 'x "y"'}

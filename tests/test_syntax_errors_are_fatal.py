"""A source file that does not parse must not yield an object.

ANTLR recovers from a syntax error by inventing or discarding tokens and carrying
on, so parsing "succeeds" and hands back something structurally wrong. Before
this was made fatal:

  - `vector N[4]={1000.0}` dropped the default, leaving N an unset vector;
  - a parameter named `vector` came back named `<missing Identifier>`;
  - Test_Mono.instr, 17 components long, parsed as 5 with no error raised.

Recovery is still worth having -- one parse reports every error in a file rather
than only the first -- but the result has to be rejected afterwards.
"""
import pytest

from mccode_antlr.comp import Comp
from mccode_antlr.grammar import McComp_ErrorListener
from mccode_antlr.loader.loader import parse_mccode_instr
from mccode_antlr.reader.reader import make_reader_error_listener
from mccode_antlr.reader.registry import InMemoryRegistry
from mccode_antlr.utils import McCodeSyntaxError

THING = 'DEFINE COMPONENT Thing\nTRACE %{\nSCATTER;\n%}\nEND\n'


def _comp(body: str) -> str:
    return f'DEFINE COMPONENT T\nSETTING PARAMETERS ({body})\nTRACE\n%{{\n%}}\nEND\n'


def _parse_comp(source: str):
    listener = make_reader_error_listener(McComp_ErrorListener, 'Component', 'T', source)
    return Comp.from_source(None, listener, source, 'T.comp', 'T.comp')


def _registry():
    reg = InMemoryRegistry('syntax_errors')
    reg.add_comp('Thing', THING)
    return reg


# ── components ───────────────────────────────────────────────────────────────

def test_valid_component_still_parses():
    comp = _parse_comp(_comp('vector N={1.0}'))
    assert [(p.name, str(p.value)) for p in comp.setting] == [('N', '1.0')]


@pytest.mark.parametrize('body, why', [
    ('vector N[4]={1000.0}', 'sized vector parameter: no McCode grammar accepts one'),
    ('vector={1.0}', "a parameter cannot be named `vector` -- it is the type keyword"),
    ('vector vector={1.0}', 'same, with the type spelled out too'),
])
def test_unparsable_component_raises(body, why):
    with pytest.raises(McCodeSyntaxError) as info:
        _parse_comp(_comp(body))
    assert info.value.errors, why
    line, column, message = info.value.errors[0]
    assert line > 0 and column >= 0 and message


def test_error_carries_position_and_message():
    with pytest.raises(McCodeSyntaxError) as info:
        _parse_comp(_comp('vector N[4]={1000.0}'))
    exc = info.value
    assert exc.filetype == 'Component' and exc.name == 'T'
    line, column, message = exc.errors[0]
    assert (line, column) == (2, 28)
    assert "'['" in message
    assert 'line 2:28' in str(exc)


def test_a_failed_parse_yields_no_component():
    """The old behaviour was to return a Comp whose N had lost its default."""
    try:
        comp = _parse_comp(_comp('vector N[4]={1000.0}'))
    except McCodeSyntaxError:
        return
    pytest.fail(f'expected McCodeSyntaxError, got a Comp with '
                f'setting={[(p.name, str(p.value)) for p in comp.setting]}')


# ── instruments ──────────────────────────────────────────────────────────────

VALID_INSTR = """DEFINE INSTRUMENT ok()
TRACE
COMPONENT a = Thing() AT (0, 0, 0) ABSOLUTE
COMPONENT b = Thing() AT (0, 0, 1) RELATIVE a
END
"""

# `%` starts nothing outside a %{ %} block. This is the Test_Mono.instr shape:
# everything after the stray line was silently dropped, and the parse "succeeded".
TRUNCATING_INSTR = """DEFINE INSTRUMENT trunc()
TRACE
COMPONENT a = Thing() AT (0, 0, 0) ABSOLUTE

% a comment written the wrong way

COMPONENT b = Thing() AT (0, 0, 1) RELATIVE a
COMPONENT c = Thing() AT (0, 0, 2) RELATIVE a
END
"""


def test_valid_instrument_still_parses():
    instr = parse_mccode_instr(VALID_INSTR, [_registry()])
    assert tuple(c.name for c in instr.components) == ('a', 'b')


def test_instrument_truncated_by_a_syntax_error_raises():
    """parse_mccode_instr passed no error listener at all, so ANTLR's default
    console listener printed to stderr and the caller got a short instrument."""
    with pytest.raises(McCodeSyntaxError):
        parse_mccode_instr(TRUNCATING_INSTR, [_registry()])


def test_instrument_parameters_parse_also_raises():
    from mccode_antlr.loader.loader import parse_mccode_instr_parameters
    with pytest.raises(McCodeSyntaxError):
        parse_mccode_instr_parameters(TRUNCATING_INSTR)


# The shape of mcstas-comps/sasmodels/SasView_rpa.comp, which reports one error
# per sized parameter rather than stopping at the first.
MULTI_ERROR_COMP = """DEFINE COMPONENT T
SETTING PARAMETERS (
        case_num=1,
        vector N[4]={1000.0},
        vector Phi[4]={0.25},
        vector v[4]={100.0},
        scale=1.0)
TRACE
%{
%}
END
"""


def test_all_errors_are_reported_not_just_the_first():
    """Recovery earns its keep by collecting the whole list before raising, so a
    user fixing a file sees every problem in it rather than one per run."""
    with pytest.raises(McCodeSyntaxError) as info:
        _parse_comp(MULTI_ERROR_COMP)
    errors = info.value.errors
    assert len(errors) == 3
    assert [line for line, _, _ in errors] == [4, 5, 6]
    assert str(info.value).startswith('3 syntax errors parsing Component T:')

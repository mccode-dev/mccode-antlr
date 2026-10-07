"""Behaviour fixed in the classic McCode code generator by ADR_20261007_GRAMMAR_FIXES
(McCode branch cogen-improve-comments-review). These pin the same behaviour here."""
from textwrap import dedent

import pytest

from mccode_antlr import Flavor
from mccode_antlr.compiler.c import instrument_source
from mccode_antlr.loader import parse_mcstas_instr
from mccode_antlr.test import compiled_test
from mccode_antlr.utils import compile_and_run


def translate(contents: str):
    return instrument_source(parse_mcstas_instr(dedent(contents)), Flavor.MCSTAS, {}, False)


def run_lines(contents: str, parameters: str = '-n 1 -y'):
    output, _ = compile_and_run(parse_mcstas_instr(dedent(contents)), parameters)
    return [line.strip() for line in output.decode('utf-8').splitlines()]


# ADR item 2: JUMP PREVIOUS[(n)] / NEXT[(n)] are relative to the jumping component
SKIP_NEXT = """\
    DEFINE INSTRUMENT jump_next_{n}(dummy=0)
    TRACE
    COMPONENT a = Arm() AT (0,0,0) ABSOLUTE
    COMPONENT b = Arm() AT (0,0,1) ABSOLUTE {jump}
    COMPONENT c = Arm() AT (0,0,2) ABSOLUTE EXTEND %{{printf("visited c\\n");%}}
    COMPONENT d = Arm() AT (0,0,3) ABSOLUTE EXTEND %{{printf("visited d\\n");%}}
    COMPONENT e = Arm() AT (0,0,4) ABSOLUTE EXTEND %{{printf("visited e\\n");%}}
    END
    """


@compiled_test
def test_jump_next_skips_one():
    lines = run_lines(SKIP_NEXT.format(n=1, jump='JUMP NEXT WHEN (1)'))
    # NEXT from b is c: an unconditional jump to the following component changes nothing
    assert lines.count('visited c') == 1
    assert lines.count('visited d') == 1


@compiled_test
def test_jump_next_n_is_relative():
    lines = run_lines(SKIP_NEXT.format(n=2, jump='JUMP NEXT(2) WHEN (1)'))
    assert 'visited c' not in lines
    assert lines.count('visited d') == 1
    assert lines.count('visited e') == 1


ITERATE_PREVIOUS = """\
    DEFINE INSTRUMENT jump_previous(int iter=3)
    USERVARS %{{int passes;%}}
    TRACE
    COMPONENT o = Arm() AT (0,0,0) ABSOLUTE EXTEND %{{passes=0;%}}
    COMPONENT a = Arm() AT (0,0,0) ABSOLUTE EXTEND %{{passes++;%}}
    COMPONENT b = Arm() AT (0,0,1) ABSOLUTE EXTEND %{{printf("visited b\\n");%}}
    COMPONENT c = Arm() AT (0,0,2) ABSOLUTE {jump}
    COMPONENT d = Arm() AT (0,0,3) ABSOLUTE EXTEND %{{printf("passes=%d\\n", passes);%}}
    END
    """


@compiled_test
def test_jump_previous_iterate():
    # PREVIOUS from c is b, which is after the counter: b three times, a once
    lines = run_lines(ITERATE_PREVIOUS.format(jump='JUMP PREVIOUS ITERATE iter'), '-n 1 -y iter=3')
    assert lines.count('visited b') == 3
    assert 'passes=1' in lines


@compiled_test
def test_jump_previous_n_iterate():
    # PREVIOUS(2) from c is a: the counter is passed 'iter' times
    lines = run_lines(ITERATE_PREVIOUS.format(jump='JUMP PREVIOUS(2) ITERATE iter'), '-n 1 -y iter=3')
    assert 'passes=3' in lines


# ADR items 2, 3, 5 and the instrument-parameter type message: must fail with a
# diagnostic naming the problem, not an internal Python error
@pytest.mark.parametrize('contents, match', [
    pytest.param("""\
        DEFINE INSTRUMENT bad() TRACE
        COMPONENT a = Arm() AT (0,0,0) ABSOLUTE
        COMPONENT b = Arm() AT (0,0,1) RELATIVE a JUMP nosuch WHEN (0)
        END""", 'nosuch', id='jump-unknown-name'),
    pytest.param("""\
        DEFINE INSTRUMENT bad() TRACE
        COMPONENT a = Arm() AT (0,0,0) ABSOLUTE
        COMPONENT b = Arm() AT (0,0,1) RELATIVE a JUMP NEXT(2) WHEN (0)
        COMPONENT c = Arm() AT (0,0,1) RELATIVE b
        END""", 'NEXT', id='jump-next-out-of-range'),
    pytest.param("""\
        DEFINE INSTRUMENT bad() TRACE
        COMPONENT a = Arm() AT (0,0,0) ABSOLUTE
        COMPONENT b = Arm() AT (0,0,1) RELATIVE a JUMP PREVIOUS(3) WHEN (0)
        END""", 'PREVIOUS', id='jump-previous-out-of-range'),
    pytest.param("""\
        DEFINE INSTRUMENT bad() TRACE
        COMPONENT a = Arm() AT (0,0,0) ABSOLUTE
        COMPONENT b = Slit(xwidth=MYSELF, yheight=0.1) AT (0,0,1) RELATIVE a
        END""", 'MYSELF', id='myself-in-parameters'),
    pytest.param("""\
        DEFINE INSTRUMENT bad(p=MYSELF) TRACE
        COMPONENT a = Arm() AT (0,0,0) ABSOLUTE
        END""", 'MYSELF', id='myself-in-instrument-parameters'),
    pytest.param("""\
        DEFINE INSTRUMENT bad() TRACE
        COMPONENT a = COPY(PREVIOUS) AT (0,0,0) ABSOLUTE
        END""", 'COPY of an undefined component instance PREVIOUS', id='copy-undefined-previous'),
    pytest.param("""\
        DEFINE INSTRUMENT bad() TRACE
        COMPONENT a = Arm() AT (0,0,0) ABSOLUTE
        COMPONENT b = COPY(nosuch) AT (0,0,0) ABSOLUTE
        END""", 'COPY of an undefined component instance nosuch', id='copy-undefined-name'),
    pytest.param("""\
        DEFINE INSTRUMENT bad() TRACE
        COMPONENT a = Arm() AT (0,0,0) ABSOLUTE
        COMPONENT b = Arm() AT (0,0,1) RELATIVE nosuch
        END""", 'undefined component instance nosuch', id='at-relative-undefined'),
    pytest.param("""\
        DEFINE INSTRUMENT bad() TRACE
        COMPONENT a = Arm() AT (0,0,0) ABSOLUTE
        COMPONENT b = Arm() AT (0,0,1) RELATIVE a ROTATED (0,0,0) RELATIVE nosuch
        END""", 'undefined component instance nosuch', id='rotated-relative-undefined'),
    pytest.param("""\
        DEFINE INSTRUMENT bad() TRACE
        COMPONENT a = NoSuchComponent() AT (0,0,0) ABSOLUTE
        END""", 'NoSuchComponent', id='unknown-component'),
    pytest.param("""\
        DEFINE INSTRUMENT bad(int *x) TRACE
        COMPONENT a = Arm() AT (0,0,0) ABSOLUTE
        END""", r"\*", id='illegal-pointer-type'),
])
def test_rejected(contents, match):
    with pytest.raises(Exception, match=match):
        translate(contents)


# ADR item 3: MYSELF stays valid from WHEN onwards
def test_myself_in_when():
    instr = parse_mcstas_instr(dedent("""\
        DEFINE INSTRUMENT m() TRACE
        COMPONENT a = Arm() AT (0,0,0) ABSOLUTE
        COMPONENT b = Arm() WHEN (MYSELF) AT (0,0,1) RELATIVE a
        END"""))
    assert 'b' in str(instr.components[1].when)


# ADR item 1: whole-component INHERIT, Diaphragm is 'DEFINE COMPONENT Diaphragm INHERIT Slit'
DIAPHRAGM = """\
    DEFINE INSTRUMENT diaphragm(dummy=0)
    TRACE
    COMPONENT src = Arm() AT (0,0,0) ABSOLUTE EXTEND %{{x=0.2; y=0; vz=1000;%}}
    {slit}
    COMPONENT d = Diaphragm(xwidth=0.25, yheight=0.25) AT (0,0,0.2) ABSOLUTE
    COMPONENT after = Arm() AT (0,0,0.3) ABSOLUTE EXTEND %{{printf("passed\\n");%}}
    END
    """


@compiled_test
def test_diaphragm_absorbs_like_slit():
    # x=0.2 is outside the 0.25 m wide Diaphragm
    assert 'passed' not in run_lines(DIAPHRAGM.format(slit=''))


@compiled_test
def test_diaphragm_with_slit_compiles():
    # x=0.2 is inside the 0.5 m wide Slit
    slit = 'COMPONENT s = Slit(xwidth=0.5, yheight=0.5) AT (0,0,0.1) ABSOLUTE'
    assert 'passed' not in run_lines(DIAPHRAGM.format(slit=slit))


def test_inherited_share_emitted_once():
    source = translate(DIAPHRAGM.format(slit='COMPONENT s = Slit(xwidth=0.5, yheight=0.5) AT (0,0,0.1) ABSOLUTE'))
    assert source.count('slit_print_if (int condition') == 1


# ADR items 7 and 8: several declarations per line, non-double USERVARS via particle_getvar
@compiled_test
def test_int_uservar_through_getvar():
    lines = run_lines("""\
        DEFINE INSTRUMENT uv(dummy=0)
        USERVARS %{int flag; double wsum;%}
        TRACE
        COMPONENT a = Arm() AT (0,0,0) ABSOLUTE EXTEND %{flag=3; wsum=2.5;%}
        COMPONENT b = Arm() AT (0,0,1) ABSOLUTE EXTEND %{
          int fail_f, fail_w;
          double f = particle_getvar(_particle, "flag", &fail_f);
          double w = particle_getvar(_particle, "wsum", &fail_w);
          printf("flag=%g %d\\n", f, fail_f);
          printf("wsum=%g %d\\n", w, fail_w);
        %}
        END
        """)
    assert 'wsum=2.5 0' in lines
    assert 'flag=3 0' in lines


def test_myself_in_instrument_parameters_only():
    from mccode_antlr.loader.loader import parse_mccode_instr_parameters
    with pytest.raises(RuntimeError, match='MYSELF'):
        parse_mccode_instr_parameters('DEFINE INSTRUMENT bad(p=MYSELF) TRACE END')


@compiled_test
def test_non_numeric_uservars_through_getvar():
    # a struct (whose type name contains 'int') and an array can not be read as a double
    lines = run_lines("""\
        DEFINE INSTRUMENT uv_struct(dummy=0)
        USERVARS %{Coords Point; double arr[2]; unsigned long count; int16_t small;%}
        TRACE
        COMPONENT a = Arm() AT (0,0,0) ABSOLUTE EXTEND %{count=7; small=-2;%}
        COMPONENT b = Arm() AT (0,0,1) ABSOLUTE EXTEND %{
          int fail;
          const char *names[] = {"Point", "arr", "count", "small"};
          for (int i = 0; i < 4; i++) {
            double v = particle_getvar(_particle, (char *) names[i], &fail);
            printf("%s=%g %d\\n", names[i], v, fail);
          }
        %}
        END
        """)
    assert 'Point=0 1' in lines
    assert 'arr=0 1' in lines
    assert 'count=7 0' in lines
    assert 'small=-2 0' in lines


def test_relative_previous_on_first_instance_is_absolute():
    instr = parse_mcstas_instr(dedent("""\
        DEFINE INSTRUMENT first() TRACE
        COMPONENT a = Arm() AT (0,0,1) RELATIVE PREVIOUS
        END"""))
    assert instr.components[0].at_relative[1] is None

"""A parameter a component does not declare is an error however the instance is made.

The C translators read only the parameters a component declares, so a misspelt one --
``double_prec`` for MCPL_output's ``doubleprec`` -- used to be kept on the instance and
dropped without a word when it arrived through make_instance, insert_component or
mcpl_split. The parser and the Assembler already refused it.
"""
import pytest

from mccode_antlr.common import ComponentParameter, Expr
from mccode_antlr.loader.loader import parse_mccode_instr
from mccode_antlr.reader.registry import InMemoryRegistry

KNOB = 'DEFINE COMPONENT Knob\nSETTING PARAMETERS (gain=1)\nTRACE %{\n%}\nEND\n'

SOURCE = """DEFINE INSTRUMENT knobs()
TRACE
COMPONENT origin = Knob() AT (0, 0, 0) ABSOLUTE
COMPONENT last = Knob() AT (0, 0, 1) RELATIVE origin
END
"""


def _instrument():
    registry = InMemoryRegistry('unknown_parameters')
    registry.add_comp('Knob', KNOB)
    return parse_mccode_instr(SOURCE, [registry])


def _comp(instr):
    return next(c for c in instr.components if c.name == 'origin').type


def test_make_instance_refuses_an_unknown_parameter():
    instr = _instrument()
    with pytest.raises(RuntimeError, match='Unknown parameter gian for component type Knob'):
        instr.make_instance('extra', _comp(instr), parameters=(ComponentParameter('gian', Expr.float(2)),))
    instr.make_instance('extra', _comp(instr), parameters=(ComponentParameter('gain', Expr.float(2)),))


def test_insert_component_refuses_an_unknown_parameter():
    instr = _instrument()
    with pytest.raises(RuntimeError, match='Unknown parameter gian for component type Knob'):
        instr.insert_component('extra', _comp(instr), after='origin',
                               parameters=(ComponentParameter('gian', Expr.float(2)),))
    assert [c.name for c in instr.components] == ['origin', 'last']


def test_mcpl_split_refuses_a_misspelt_mcpl_parameter():
    """The case that hid a precision bug: MCPL_output's option is doubleprec."""
    from mccode_antlr.loader import parse_mcstas_instr
    instr = parse_mcstas_instr("""DEFINE INSTRUMENT t()
    TRACE
    COMPONENT origin = Arm() AT (0,0,0) ABSOLUTE
    COMPONENT cut = Arm() AT (0,0,1) RELATIVE origin
    COMPONENT mon = Arm() AT (0,0,1) RELATIVE origin
    END""")
    with pytest.raises(RuntimeError, match='Unknown parameter double_prec for component type MCPL_output'):
        instr.mcpl_split('cut', output_parameters=(ComponentParameter('double_prec', Expr.float(1)),))
    with pytest.raises(RuntimeError, match='Unknown parameter weightmode for component type MCPL_input'):
        instr.mcpl_split('cut', input_parameters=(ComponentParameter('weightmode', Expr.float(0)),))
    first, _ = instr.mcpl_split('cut', output_parameters=(ComponentParameter('doubleprec', Expr.float(1)),))
    cut = next(c for c in first.components if c.name == 'cut')
    assert 'doubleprec' in [p.name for p in cut.parameters]

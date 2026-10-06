"""verify_parameters promotes every instrument parameter in an expression, not just one.

It used to substitute each name into the expression as it was before the loop, so each
substitution discarded the one before it. Only the last name found, in declaration
order, became a McCodeParameter; the others stayed plain symbols, which the C printer
writes as bare identifiers -- `a4 - _instrument_var._parameters.a3` -- and which the
compiler then rejects as undeclared.
"""
from mccode_antlr.common.expression import Expr


def test_every_named_parameter_is_promoted():
    expression = Expr.parse('sin(DEG2RAD*(a4 - a3))')
    expression.verify_parameters(['a3', 'a4'])
    printed = format(expression, 'p')
    assert '_instrument_var._parameters.a3' in printed
    assert '_instrument_var._parameters.a4' in printed


def test_the_order_of_the_names_does_not_matter():
    for names in (['a3', 'a4'], ['a4', 'a3']):
        expression = Expr.parse('a4 - a3 + 59')
        expression.verify_parameters(names)
        printed = format(expression, 'p')
        assert '_instrument_var._parameters.a3' in printed, names
        assert '_instrument_var._parameters.a4' in printed, names


def test_identifiers_that_are_not_parameters_stay_as_they_are():
    expression = Expr.parse('a4 - a3 + offset')
    expression.verify_parameters(['a3', 'a4'])
    printed = format(expression, 'p')
    assert '_instrument_var._parameters.offset' not in printed
    assert 'offset' in printed


def test_a_component_parameter_naming_two_instrument_parameters():
    """The way it was found: an assembled component whose parameter follows two angles."""
    from mccode_antlr import Flavor
    from mccode_antlr.assembler import Assembler

    assembler = Assembler('two_angles', flavor=Flavor.MCSTAS)
    assembler.parameter('double sample_rotation = 0;')
    assembler.parameter('double detector_tank_angle = 0;')
    assembler.component('slit', 'Slit', at=((0, 0, 1), 'ABSOLUTE'), parameters={
        'xmin': 'sin(DEG2RAD * (detector_tank_angle - sample_rotation)) - 1', 'xmax': 0.1,
        'ymin': -0.1, 'ymax': 0.1})
    instrument = assembler.instrument
    # what every translator does before it writes a component's parameters
    instrument.verify_instance_parameters()
    instance = instrument.components[0]
    printed = format(next(p for p in instance.parameters if p.name == 'xmin').value, 'p')
    assert '_instrument_var._parameters.sample_rotation' in printed
    assert '_instrument_var._parameters.detector_tank_angle' in printed

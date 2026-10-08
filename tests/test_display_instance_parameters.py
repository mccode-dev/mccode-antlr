"""InstrumentDisplay uses the parameter values of component instances."""
from textwrap import dedent

import numpy as np
import pytest

from mccode_antlr.display import InstrumentDisplay
from mccode_antlr.loader import parse_mcstas_instr
from mccode_antlr.reader.registry import InMemoryRegistry

PANEL = dedent(r"""DEFINE COMPONENT Panel
    SETTING PARAMETERS (xwidth=0, yheight=0)
    TRACE %{
    %}
    MCDISPLAY %{
    rectangle("xy", 0, 0, 0, xwidth, yheight);
    %}
    END
    """)


def _instr():
    reg = InMemoryRegistry("display_instance_parameters")
    reg.add_comp("Panel", PANEL)
    return parse_mcstas_instr(dedent("""DEFINE INSTRUMENT panels(double w = 0.3)
    TRACE
    COMPONENT literal = Panel(xwidth=0.5, yheight=0.2) AT (0, 0, 1) ABSOLUTE
    COMPONENT symbolic = Panel(xwidth=w, yheight=2*w) AT (0, 0, 2) ABSOLUTE
    END
    """), registries=[reg])


def _extent(polylines):
    pts = np.concatenate(polylines)
    return np.ptp(pts[:, 0]), np.ptp(pts[:, 1])


def test_literal_instance_parameters_are_used():
    polylines = InstrumentDisplay(_instr()).to_polylines({'w': 0.3})
    assert polylines['literal'], 'no geometry drawn'
    assert _extent(polylines['literal']) == pytest.approx((0.5, 0.2))


def test_instance_parameters_from_instrument_parameters_are_used():
    polylines = InstrumentDisplay(_instr()).to_polylines({'w': 0.3})
    assert polylines['symbolic'], 'no geometry drawn'
    assert _extent(polylines['symbolic']) == pytest.approx((0.3, 0.6))

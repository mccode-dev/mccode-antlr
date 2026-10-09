"""InstrumentDisplay evaluates if/else and loops in MCDISPLAY, with component
defaults."""
from textwrap import dedent

import numpy as np
import pytest

from mccode_antlr.display import InstrumentDisplay
from mccode_antlr.loader import parse_mcstas_instr
from mccode_antlr.reader.registry import InMemoryRegistry

SHAPE = dedent(r"""DEFINE COMPONENT Shape
    SETTING PARAMETERS (xwidth=0, yheight=0, zdepth=0, radius=0)
    TRACE %{
    %}
    MCDISPLAY %{
    if (radius > 0 && yheight > 0)
      cylinder(0, 0, 0, radius, yheight, 0, 0, 1, 0);
    else if (radius > 0)
      sphere(0, 0, 0, radius);
    else
      box(0, 0, 0, xwidth, yheight, zdepth, 0, 0, 1, 0);
    %}
    END
    """)

HALFWIDTH = dedent(r"""DEFINE COMPONENT HalfWidth
    SETTING PARAMETERS (xwidth=0, xmax=0.05)
    INITIALIZE %{
    if (xwidth > 0) xmax = xwidth / 2;
    %}
    TRACE %{
    %}
    MCDISPLAY %{
    line(-xmax, 0, 0, xmax, 0, 0);
    %}
    END
    """)


LOOP = dedent(r"""DEFINE COMPONENT Loop
    SETTING PARAMETERS (n=2)
    TRACE %{
    %}
    MCDISPLAY %{
    int i;
    for (i = 0; i < n; i++)
      line(0, 0, i, 1, 0, i);
    %}
    END
    """)


def _polylines():
    reg = InMemoryRegistry("display_conditions")
    reg.add_comp("Shape", SHAPE)
    reg.add_comp("HalfWidth", HALFWIDTH)
    reg.add_comp("Loop", LOOP)
    instr = parse_mcstas_instr(dedent("""DEFINE INSTRUMENT shapes(dummy=0)
    TRACE
    COMPONENT box = Shape(xwidth=0.1, yheight=0.2, zdepth=0.3) AT (0, 0, 1) ABSOLUTE
    COMPONENT cyl = Shape(radius=0.05, yheight=0.4) AT (0, 0, 2) ABSOLUTE
    COMPONENT sph = Shape(radius=0.06) AT (0, 0, 3) ABSOLUTE
    COMPONENT half = HalfWidth(xwidth=0.2) AT (0, 0, 4) ABSOLUTE
    COMPONENT loop = Loop() AT (0, 0, 5) ABSOLUTE
    END
    """), registries=[reg])
    return InstrumentDisplay(instr).to_polylines({})


def _extent(polylines):
    pts = np.concatenate(polylines)
    return tuple(np.ptp(pts, axis=0))


@pytest.mark.parametrize('name, extent', [('box', (0.1, 0.2, 0.3)),
                                          ('cyl', (0.1, 0.4, 0.1)),
                                          ('sph', (0.12, 0.12, 0.12))])
def test_only_the_selected_branch_is_drawn(name, extent):
    assert _extent(_polylines()[name]) == pytest.approx(extent, rel=1e-3)


def test_defaults_changed_in_initialize_are_not_used():
    # xmax is set from xwidth in INITIALIZE, which drawing does not run:
    assert _polylines()['half'] == []


def test_loops_do_not_fail():
    assert 'loop' in _polylines()

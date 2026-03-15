"""McCode display geometry extraction and rendering.

Parse a component's ``MCDISPLAY`` section into symbolic geometry primitives,
evaluate them with concrete parameter values, and render the result in 3-D.

Quick start::

    from mccode_antlr.loader import load_mcstas_instr
    from mccode_antlr.display import InstrumentDisplay
    from mccode_antlr.display.render.matplotlib import plot_geometry

    instr = load_mcstas_instr('my_instrument.instr')
    disp = InstrumentDisplay(instr)
    polylines = disp.to_polylines({'E_i': 5.0})   # dict[name -> list[ndarray]]

    fig, ax = plot_geometry(polylines)

Single-component use::

    from mccode_antlr.display import ComponentDisplay

    cd = ComponentDisplay(comp)                    # from a Comp object
    polylines = cd.to_polylines({'xwidth': 0.05, 'yheight': 0.1})
"""

from .component_display import ComponentDisplay
from .instrument_display import InstrumentDisplay
from .primitives import (
    Primitive, Magnify, Line, DashedLine, Multiline,
    Circle, Rectangle, Box, Sphere, Cylinder, Cone,
    CircleNormal, Disc, Annulus, Polygon, Polyhedron,
    ConditionalBlock, LoopBlock,
)
from .visitor import parse_display_source

__all__ = [
    'ComponentDisplay',
    'InstrumentDisplay',
    'parse_display_source',
    # Primitives
    'Primitive',
    'Magnify',
    'Line',
    'DashedLine',
    'Multiline',
    'Circle',
    'CircleNormal',
    'Rectangle',
    'Box',
    'Sphere',
    'Cylinder',
    'Cone',
    'Disc',
    'Annulus',
    'Polygon',
    'Polyhedron',
    'ConditionalBlock',
    'LoopBlock',
]

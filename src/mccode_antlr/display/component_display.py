"""ComponentDisplay — geometry model for a single McCode component.

Parses the ``MCDISPLAY`` section of a :class:`~mccode_antlr.comp.comp.Comp`
into a list of :class:`~mccode_antlr.display.primitives.Primitive` objects
backed by :class:`~mccode_antlr.common.expression.Expr`.

Example::

    from mccode_antlr.comp import Comp
    from mccode_antlr.display import ComponentDisplay

    comp = ...  # a parsed Comp with a MCDISPLAY section
    cd = ComponentDisplay(comp)

    # Evaluate with specific parameter values
    polylines = cd.to_polylines({'xwidth': 0.05, 'yheight': 0.1, 'zdepth': 0.02})
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Union

import numpy as np

if TYPE_CHECKING:
    from ..comp.comp import Comp

from .primitives import Primitive, ConditionalBlock, LoopBlock
from .visitor import parse_display_source

AnyBlock = Union[Primitive, ConditionalBlock, LoopBlock]


class ComponentDisplay:
    """Parse and evaluate the ``MCDISPLAY`` section of a component.

    Parameters
    ----------
    comp:
        The component whose ``display`` RawC blocks to parse.
    """

    def __init__(self, comp: 'Comp'):
        self._comp = comp
        self._primitives: list[AnyBlock] | None = None

    @property
    def name(self) -> str:
        return self._comp.name or '(unnamed)'

    @property
    def primitives(self) -> list[AnyBlock]:
        """Lazily parse the display source and cache the result."""
        if self._primitives is None:
            self._primitives = self._parse()
        return self._primitives

    def _parse(self) -> list[AnyBlock]:
        if not self._comp.display:
            return []
        # Combine all RawC blocks into a single source string
        source = '\n'.join(block.source for block in self._comp.display)
        if not source.strip():
            return []
        return parse_display_source(source)

    def is_empty(self) -> bool:
        """Return ``True`` if this component has no display geometry."""
        return len(self.primitives) == 0

    def to_polylines(self, params: dict[str, float] | None = None) -> list[np.ndarray]:
        """Return all geometry as a flat list of ``(N, 3)`` numpy arrays.

        Parameters
        ----------
        params:
            Component parameter values (and any instrument parameters
            referenced in the display expressions).  Values that are unknown
            in *params* remain symbolic and may cause evaluation errors;
            they are silently skipped.
        """
        p = params or {}
        result: list[np.ndarray] = []
        for prim in self.primitives:
            try:
                result.extend(prim.to_polylines(p))
            except Exception:
                pass
        return result

    def __repr__(self) -> str:
        n = len(self.primitives)
        return f'ComponentDisplay({self.name!r}, {n} primitive{"s" if n != 1 else ""})'

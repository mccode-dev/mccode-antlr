"""InstrumentDisplay — geometry model for a full McCode instrument.

Collects :class:`ComponentDisplay` objects for every component instance that
has a ``MCDISPLAY`` section, transforms each component's local geometry into
the global instrument coordinate frame using the symbolic
:class:`~mccode_antlr.instr.orientation.Orient` chain already attached to
each :class:`~mccode_antlr.instr.instance.Instance`, and then evaluates
everything with a supplied instrument parameter dict.

Example::

    from mccode_antlr.loader import load_mcstas_instr
    from mccode_antlr.display import InstrumentDisplay

    instr = load_mcstas_instr('my_instrument.instr')
    disp = InstrumentDisplay(instr)

    # Provide instrument parameter values
    polylines = disp.to_polylines({'E_i': 5.0, 'delta_e': 1.0})
    # polylines is a dict: {component_name: list[np.ndarray(N,3)]}
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Union

import numpy as np

if TYPE_CHECKING:
    from ..instr.instr import Instr

from ..instr.orientation import Vector
from ..common.expression import Expr
from .component_display import ComponentDisplay
from .primitives import Primitive, ConditionalBlock, LoopBlock

AnyBlock = Union[Primitive, ConditionalBlock, LoopBlock]


def _eval_expr(e: Expr | float, params: dict) -> float:
    if isinstance(e, Expr):
        return float(e.evaluate(params).simplify())
    return float(e)


def _transform_polyline(pts: np.ndarray, rotation, translation: Vector,
                        params: dict) -> np.ndarray:
    """Apply a symbolic Orient transform to a (N,3) polyline.

    Parameters
    ----------
    pts:
        Component-local coordinates, shape (N, 3).
    rotation:
        A :class:`~mccode_antlr.instr.orientation.Rotation` (3×3 matrix of
        :class:`~mccode_antlr.common.expression.Expr`).
    translation:
        A :class:`~mccode_antlr.instr.orientation.Vector` of Expr.
    params:
        Instrument / component parameter values for evaluation.
    """
    tx = _eval_expr(translation.x, params)
    ty = _eval_expr(translation.y, params)
    tz = _eval_expr(translation.z, params)

    # Materialise the rotation matrix
    try:
        R = np.array([
            [_eval_expr(rotation.xx, params), _eval_expr(rotation.xy, params), _eval_expr(rotation.xz, params)],
            [_eval_expr(rotation.yx, params), _eval_expr(rotation.yy, params), _eval_expr(rotation.yz, params)],
            [_eval_expr(rotation.zx, params), _eval_expr(rotation.zy, params), _eval_expr(rotation.zz, params)],
        ], dtype=float)
    except Exception:
        R = np.eye(3)

    t = np.array([tx, ty, tz], dtype=float)
    return (R @ pts.T).T + t


class InstrumentDisplay:
    """Parse and evaluate the geometry for an entire instrument.

    Parameters
    ----------
    instr:
        The :class:`~mccode_antlr.instr.instr.Instr` to display.
    """

    def __init__(self, instr: 'Instr'):
        self._instr = instr
        self._components: dict[str, ComponentDisplay] = {}
        for instance in instr.components:
            cd = ComponentDisplay(instance.type)
            if not cd.is_empty():
                self._components[instance.name] = cd

    @property
    def component_names(self) -> list[str]:
        """Names of components that have display geometry."""
        return list(self._components.keys())

    def component_display(self, name: str) -> ComponentDisplay:
        """Return the :class:`ComponentDisplay` for the named instance."""
        return self._components[name]

    def to_polylines(
        self,
        params: dict[str, float] | None = None,
        *,
        global_frame: bool = True,
    ) -> dict[str, list[np.ndarray]]:
        """Evaluate all component geometries and return polylines.

        Parameters
        ----------
        params:
            Instrument parameter values.  Component SETTING parameters that
            match instance parameter assignments are also injected automatically.
        global_frame:
            If ``True`` (default) transform all polylines to the global
            instrument frame using each component's :class:`~mccode_antlr.instr.orientation.Orient`.
            If ``False`` return component-local coordinates.

        Returns
        -------
        dict[str, list[np.ndarray]]
            Mapping from component instance name to a list of ``(N, 3)``
            polyline arrays.
        """
        p = dict(params or {})
        result: dict[str, list[np.ndarray]] = {}

        for instance in self._instr.components:
            name = instance.name
            if name not in self._components:
                continue

            # Build merged parameter dict: instr params + instance overrides
            comp_params = dict(p)
            for cp in instance.parameters:
                try:
                    val = cp.value.evaluate(p).simplify()
                    comp_params[cp.name] = float(val)
                except Exception:
                    pass

            cd = self._components[name]
            local_polylines = cd.to_polylines(comp_params)

            if not global_frame or instance.orientation is None:
                result[name] = local_polylines
                continue

            # Transform to global frame
            try:
                orient = instance.orientation
                rotation = orient.rotation()
                translation = orient.position()
            except Exception:
                result[name] = local_polylines
                continue

            global_polylines = []
            for pts in local_polylines:
                try:
                    global_polylines.append(_transform_polyline(pts, rotation, translation, p))
                except Exception:
                    global_polylines.append(pts)
            result[name] = global_polylines

        return result

    def __repr__(self) -> str:
        n = len(self._components)
        return (f'InstrumentDisplay({self._instr.name!r}, '
                f'{n} component{"s" if n != 1 else ""} with display)')

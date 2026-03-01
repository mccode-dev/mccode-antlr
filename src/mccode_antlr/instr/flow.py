"""Particle flow graph representation for McCode instruments.

Builds a :class:`networkx.MultiDiGraph` whose nodes are component instance
names and whose edges carry typed :class:`FlowEdge` payloads describing *how*
a particle moves between components.

Edge payload hierarchy
----------------------
::

    FlowEdge (abstract Struct base, tag_field='type')
    ├── SequentialEdge      – default linear flow (possibly gated by WHEN)
    ├── GroupEdge           – GROUP try-until-SCATTER semantics
    ├── JumpEdge            – JUMP WHEN / JUMP ITERATE
    └── WeightedRandomEdge  – future: weighted random outgoing edge selection

All edge types are :class:`msgspec.Struct` subclasses with a ``type``
discriminator field.  The serialisable ground truth is stored as a
:class:`tuple` of :class:`FlowEdgeRecord` objects on :class:`~mccode_antlr.instr.Instr`
(the ``flow_edges`` field).  The :class:`networkx.MultiDiGraph` is a *derived
view* built on demand from that tuple.

Serialisation
-------------
:class:`FlowEdgeRecord` is a plain msgspec Struct containing ``(src, dst, edge)``.
Round-trip serialisation via the existing IO infrastructure (``to_dict`` /
``from_dict``) works for all edge types.  Direct ``msgspec.json`` decoding of the
:data:`AnyFlowEdge` union also works for ``GroupEdge``; for edges whose fields
include :class:`~mccode_antlr.common.Expr` use :meth:`FlowEdgeRecord.from_dict`.

Node data
---------
Each node stores an ``instance`` attribute holding the original
:class:`~mccode_antlr.instr.Instance` object *by reference* (not copied).
All component properties are therefore accessible via
``G.nodes[name]['instance']``.

Usage
-----
::

    from mccode_antlr.instr import Instr
    from mccode_antlr.instr.flow import build_particle_flow_graph

    instr = ...  # parsed Instr object
    G = build_particle_flow_graph(instr)

    for u, v, data in G.edges(data=True):
        edge: FlowEdge = data['flow']
        print(u, '->', v, type(edge).__name__)

Incremental building (via Visitor / Assembler)
----------------------------------------------
:meth:`~mccode_antlr.instr.Instr.add_flow_edge` inserts a single
:class:`FlowEdgeRecord` into ``Instr.flow_edges``.
:meth:`~mccode_antlr.instr.Instr.finalize_flow_edges` adds deferred JUMP edges
after all components are known.
:meth:`~mccode_antlr.instr.Instr.build_flow_graph` rebuilds the full edge list
from scratch (idempotent, replaces ``flow_edges``).
"""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING, Optional, Union

import msgspec
import networkx as nx

from ..common import Expr

if TYPE_CHECKING:
    from .instr import Instr
    from .instance import Instance


# ---------------------------------------------------------------------------
# Edge payload types
# ---------------------------------------------------------------------------

class FlowEdge(msgspec.Struct, tag_field='type'):
    """Base for all particle flow edge payloads.

    The ``type`` field is a JSON discriminator that enables round-trip
    serialisation of the :data:`AnyFlowEdge` union.  New flow-control
    mechanisms should subclass this and supply a unique ``tag``.
    """


class SequentialEdge(FlowEdge, tag='sequential'):
    """Implicit linear flow: particle visits *v* after *u*.

    Args:
        when: The ``WHEN`` expression on the *destination* component, if any.
              A particle that doesn't satisfy ``when`` skips that component
              but continues along the sequential path.
    """
    when: Optional[Expr] = None


class GroupEdgeKind(Enum):
    """Describes the role of an edge within GROUP semantics."""
    ENTRY = auto()         # preceding component → first group member
    TRY_NEXT = auto()      # member → next member after no-SCATTER (state reset before each)
    SCATTER_EXIT = auto()  # member → component after group, when member issued SCATTER
    PASS_THROUGH = auto()  # last member → component after group, when no member scattered


class GroupEdge(FlowEdge, tag='group'):
    """Edge within or around a GROUP block.

    Args:
        group_name: Name of the GROUP this edge belongs to.
        kind: Semantic role of this edge (see :class:`GroupEdgeKind`).
    """
    group_name: str
    kind: GroupEdgeKind


class JumpEdge(FlowEdge, tag='jump'):
    """JUMP control-flow edge.

    Args:
        condition: The expression controlling the jump.
        iterate: ``True`` for ``JUMP … ITERATE``, ``False`` for ``JUMP … WHEN``.
        absolute_target: Resolved index of the target component in
            ``instr.components`` (mirrors
            :attr:`~mccode_antlr.instr.Jump.absolute_target`).
    """
    condition: Expr
    iterate: bool
    absolute_target: int


class WeightedRandomEdge(FlowEdge, tag='weighted_random'):
    """Future extension: weighted random outgoing edge selection.

    When multiple :class:`WeightedRandomEdge` instances leave the same node,
    a runtime sampler picks one according to their relative weights.

    Args:
        weight: Non-negative weight for this edge.
        condition: Optional guard; treated as zero-weight when ``False``.
    """
    weight: float = 1.0
    condition: Optional[Expr] = None


#: Union of all concrete edge types; use as the ``type`` argument when
#: decoding a serialised :class:`FlowEdge` with :mod:`msgspec` (works for
#: edge types without :class:`~mccode_antlr.common.Expr` fields; use
#: :meth:`FlowEdgeRecord.from_dict` for the full set).
AnyFlowEdge = Union[SequentialEdge, GroupEdge, JumpEdge, WeightedRandomEdge]


# ---------------------------------------------------------------------------
# Serialisable edge record
# ---------------------------------------------------------------------------

class FlowEdgeRecord(msgspec.Struct):
    """Serialisable (src, dst, edge) triplet stored on :class:`~mccode_antlr.instr.Instr`.

    This is the authoritative persisted representation of a flow edge.
    The :class:`networkx.MultiDiGraph` returned by
    :attr:`~mccode_antlr.instr.Instr.flow_graph` is always derived from
    these records.
    """
    src: str
    dst: str
    edge: AnyFlowEdge

    @classmethod
    def from_dict(cls, args: dict) -> FlowEdgeRecord:
        """Reconstruct from a plain dict (as produced by the IO decoder).

        Handles :class:`~mccode_antlr.common.Expr` fields in all edge types
        via the existing :func:`~mccode_antlr.common.expression.Expr.from_dict`
        infrastructure.
        """
        edge_data = dict(args['edge'])
        edge_type = edge_data.pop('type', None)

        if edge_type == 'sequential':
            when_data = edge_data.get('when')
            edge = SequentialEdge(when=Expr.from_dict(when_data) if when_data else None)
        elif edge_type == 'group':
            edge = GroupEdge(
                group_name=edge_data['group_name'],
                kind=GroupEdgeKind(edge_data['kind']),
            )
        elif edge_type == 'jump':
            edge = JumpEdge(
                condition=Expr.from_dict(edge_data['condition']),
                iterate=edge_data['iterate'],
                absolute_target=edge_data['absolute_target'],
            )
        elif edge_type == 'weighted_random':
            cond_data = edge_data.get('condition')
            edge = WeightedRandomEdge(
                weight=edge_data.get('weight', 1.0),
                condition=Expr.from_dict(cond_data) if cond_data else None,
            )
        else:
            raise ValueError(f"Unknown flow edge type tag: {edge_type!r}")

        return cls(src=args['src'], dst=args['dst'], edge=edge)


# ---------------------------------------------------------------------------
# Graph construction helpers
# ---------------------------------------------------------------------------

def flow_graph_from_records(
    components: tuple,
    flow_edges: tuple,
) -> nx.MultiDiGraph:
    """Build a :class:`networkx.MultiDiGraph` from component instances and edge records.

    This is the low-level builder used by :attr:`~mccode_antlr.instr.Instr.flow_graph`.

    Parameters
    ----------
    components:
        ``tuple[Instance, ...]`` — component instances (provide node attributes).
    flow_edges:
        ``tuple[FlowEdgeRecord, ...]`` — the authoritative edge list.
    """
    G: nx.MultiDiGraph = nx.MultiDiGraph()
    for inst in components:
        G.add_node(inst.name, instance=inst)
    for rec in flow_edges:
        G.add_edge(rec.src, rec.dst, flow=rec.edge)
    return G


def build_particle_flow_graph(instr: Instr) -> nx.MultiDiGraph:
    """Build a complete particle flow graph for *instr* from scratch.

    Equivalent to calling :meth:`~mccode_antlr.instr.Instr.build_flow_graph`
    but returns the :class:`networkx.MultiDiGraph` directly without storing it.
    Prefer :meth:`~mccode_antlr.instr.Instr.build_flow_graph` when you want
    the result persisted on the instrument.

    Returns
    -------
    nx.MultiDiGraph
        Nodes are component instance name strings with an ``instance`` attribute
        (reference, not copy).  Edges carry a ``flow`` attribute holding an
        :data:`AnyFlowEdge` instance.
    """
    records = _build_flow_edge_records(instr.components)
    return flow_graph_from_records(instr.components, records)


# ---------------------------------------------------------------------------
# Internal: build the authoritative FlowEdgeRecord tuple from components
# ---------------------------------------------------------------------------

def _build_flow_edge_records(components: tuple) -> tuple:
    """Compute the full ``tuple[FlowEdgeRecord, ...]`` from a component list.

    Called by :func:`build_particle_flow_graph` and
    :meth:`~mccode_antlr.instr.Instr.build_flow_graph`.
    """
    records: list[FlowEdgeRecord] = []
    n = len(components)

    if n == 0:
        return ()

    # Collect groups: name -> ordered [(index, Instance)]
    groups: dict[str, list[tuple[int, object]]] = {}
    for idx, inst in enumerate(components):
        if inst.group is not None:
            groups.setdefault(inst.group, []).append((idx, inst))

    # Sequential and within-group edges
    for idx in range(n - 1):
        src = components[idx]
        dst = components[idx + 1]
        same_group = src.group is not None and src.group == dst.group
        src_exits_group = src.group is not None and src.group != (dst.group or '')

        if same_group:
            records.append(FlowEdgeRecord(
                src=src.name, dst=dst.name,
                edge=GroupEdge(group_name=src.group, kind=GroupEdgeKind.TRY_NEXT),
            ))
        elif src_exits_group:
            # Group exit edges are handled below; skip sequential here to avoid
            # duplicating the PASS_THROUGH edge.
            pass
        else:
            records.append(FlowEdgeRecord(
                src=src.name, dst=dst.name,
                edge=SequentialEdge(when=dst.when),
            ))

    # Group exit edges: scatter-exit from every member, pass-through from last
    for group_name, members in groups.items():
        last_idx, last_inst = members[-1]
        exit_idx = last_idx + 1
        while exit_idx < n and components[exit_idx].group == group_name:
            exit_idx += 1

        if exit_idx < n:
            exit_name = components[exit_idx].name
            for _, member_inst in members:
                records.append(FlowEdgeRecord(
                    src=member_inst.name, dst=exit_name,
                    edge=GroupEdge(group_name=group_name, kind=GroupEdgeKind.SCATTER_EXIT),
                ))
            records.append(FlowEdgeRecord(
                src=last_inst.name, dst=exit_name,
                edge=GroupEdge(group_name=group_name, kind=GroupEdgeKind.PASS_THROUGH),
            ))

    # Jump edges — resolve target by name if absolute_target is unset (-1)
    name_to_idx = {inst.name: idx for idx, inst in enumerate(components)}
    for inst in components:
        for jmp in inst.jump:
            target_idx = jmp.absolute_target
            if target_idx < 0:
                target_idx = name_to_idx.get(jmp.target, -1)
            if 0 <= target_idx < n:
                records.append(FlowEdgeRecord(
                    src=inst.name, dst=components[target_idx].name,
                    edge=JumpEdge(
                        condition=jmp.condition,
                        iterate=jmp.iterate,
                        absolute_target=target_idx,
                    ),
                ))

    return tuple(records)


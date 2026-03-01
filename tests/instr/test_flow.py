from unittest import TestCase

from mccode_antlr.utils import parse_instr_string
from mccode_antlr.instr.flow import (
    build_particle_flow_graph,
    SequentialEdge,
    GroupEdge,
    GroupEdgeKind,
    JumpEdge,
    AnyFlowEdge,
)
import msgspec


def _flow(G, u, v):
    """Return the list of FlowEdge payloads on all edges from u to v."""
    return [data['flow'] for _, _, data in G.edges(data=True) if _ == u and _ != v or True
            if False] or [
        data['flow'] for k, data in G[u][v].items()
    ]


def _flows(G, u, v):
    """Return all FlowEdge payloads on edges from u to v."""
    if v not in G[u]:
        return []
    return [data['flow'] for data in G[u][v].values()]


class TestBuildParticleFlowGraph(TestCase):

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse(trace_body: str):
        src = f"""
        DEFINE INSTRUMENT test()
        TRACE
        {trace_body}
        END
        """
        return parse_instr_string(src)

    # ------------------------------------------------------------------
    # Sequential flow
    # ------------------------------------------------------------------

    def test_sequential_nodes(self):
        instr = self._parse("""
            COMPONENT a = Arm() AT (0,0,0) ABSOLUTE
            COMPONENT b = Arm() AT (0,0,1) RELATIVE a
            COMPONENT c = Arm() AT (0,0,1) RELATIVE b
        """)
        G = build_particle_flow_graph(instr)
        self.assertEqual(set(G.nodes), {'a', 'b', 'c'})

    def test_sequential_edges(self):
        instr = self._parse("""
            COMPONENT a = Arm() AT (0,0,0) ABSOLUTE
            COMPONENT b = Arm() AT (0,0,1) RELATIVE a
            COMPONENT c = Arm() AT (0,0,1) RELATIVE b
        """)
        G = build_particle_flow_graph(instr)
        ab = _flows(G, 'a', 'b')
        bc = _flows(G, 'b', 'c')
        self.assertEqual(len(ab), 1)
        self.assertIsInstance(ab[0], SequentialEdge)
        self.assertEqual(len(bc), 1)
        self.assertIsInstance(bc[0], SequentialEdge)

    def test_node_instance_reference(self):
        """Node 'instance' attribute must be the exact same object as in instr.components."""
        instr = self._parse("""
            COMPONENT a = Arm() AT (0,0,0) ABSOLUTE
            COMPONENT b = Arm() AT (0,0,1) RELATIVE a
        """)
        G = build_particle_flow_graph(instr)
        self.assertIs(G.nodes['a']['instance'], instr.components[0])
        self.assertIs(G.nodes['b']['instance'], instr.components[1])

    def test_empty_instrument(self):
        instr = self._parse("")
        G = build_particle_flow_graph(instr)
        self.assertEqual(len(G.nodes), 0)
        self.assertEqual(len(G.edges), 0)

    # ------------------------------------------------------------------
    # GROUP flow
    # ------------------------------------------------------------------

    def test_group_try_next_edges(self):
        instr = self._parse("""
            COMPONENT before = Arm() AT (0,0,0) ABSOLUTE
            COMPONENT g1 = Arm() AT (0,0,1) RELATIVE before GROUP MyGroup
            COMPONENT g2 = Arm() AT (0,0,2) RELATIVE before GROUP MyGroup
            COMPONENT g3 = Arm() AT (0,0,3) RELATIVE before GROUP MyGroup
            COMPONENT after = Arm() AT (0,0,4) RELATIVE before
        """)
        G = build_particle_flow_graph(instr)

        # within-group edges are TRY_NEXT
        g1g2 = _flows(G, 'g1', 'g2')
        g2g3 = _flows(G, 'g2', 'g3')
        self.assertTrue(any(isinstance(e, GroupEdge) and e.kind == GroupEdgeKind.TRY_NEXT for e in g1g2))
        self.assertTrue(any(isinstance(e, GroupEdge) and e.kind == GroupEdgeKind.TRY_NEXT for e in g2g3))

    def test_group_scatter_exit_edges(self):
        instr = self._parse("""
            COMPONENT before = Arm() AT (0,0,0) ABSOLUTE
            COMPONENT g1 = Arm() AT (0,0,1) RELATIVE before GROUP MyGroup
            COMPONENT g2 = Arm() AT (0,0,2) RELATIVE before GROUP MyGroup
            COMPONENT after = Arm() AT (0,0,4) RELATIVE before
        """)
        G = build_particle_flow_graph(instr)

        # every member has a SCATTER_EXIT edge to after
        for member in ('g1', 'g2'):
            edges = _flows(G, member, 'after')
            self.assertTrue(
                any(isinstance(e, GroupEdge) and e.kind == GroupEdgeKind.SCATTER_EXIT for e in edges),
                f"missing SCATTER_EXIT from {member}",
            )

    def test_group_pass_through_edge(self):
        instr = self._parse("""
            COMPONENT before = Arm() AT (0,0,0) ABSOLUTE
            COMPONENT g1 = Arm() AT (0,0,1) RELATIVE before GROUP MyGroup
            COMPONENT g2 = Arm() AT (0,0,2) RELATIVE before GROUP MyGroup
            COMPONENT after = Arm() AT (0,0,4) RELATIVE before
        """)
        G = build_particle_flow_graph(instr)

        # only the last group member has a PASS_THROUGH edge
        last_edges = _flows(G, 'g2', 'after')
        self.assertTrue(
            any(isinstance(e, GroupEdge) and e.kind == GroupEdgeKind.PASS_THROUGH for e in last_edges)
        )
        first_edges = _flows(G, 'g1', 'after')
        self.assertFalse(
            any(isinstance(e, GroupEdge) and e.kind == GroupEdgeKind.PASS_THROUGH for e in first_edges)
        )

    def test_group_edge_group_name(self):
        instr = self._parse("""
            COMPONENT before = Arm() AT (0,0,0) ABSOLUTE
            COMPONENT g1 = Arm() AT (0,0,1) RELATIVE before GROUP Detectors
            COMPONENT g2 = Arm() AT (0,0,2) RELATIVE before GROUP Detectors
            COMPONENT after = Arm() AT (0,0,4) RELATIVE before
        """)
        G = build_particle_flow_graph(instr)
        for e in _flows(G, 'g1', 'g2') + _flows(G, 'g1', 'after'):
            self.assertEqual(e.group_name, 'Detectors')

    # ------------------------------------------------------------------
    # JUMP flow
    # ------------------------------------------------------------------

    def test_jump_when_edge(self):
        instr = self._parse("""
            COMPONENT a = Arm() AT (0,0,0) ABSOLUTE
            COMPONENT b = Arm() AT (0,0,1) RELATIVE a JUMP a WHEN (1)
            COMPONENT c = Arm() AT (0,0,2) RELATIVE a
        """)
        G = build_particle_flow_graph(instr)
        jump_edges = [e for e in _flows(G, 'b', 'a') if isinstance(e, JumpEdge)]
        self.assertEqual(len(jump_edges), 1)
        self.assertFalse(jump_edges[0].iterate)

    def test_jump_iterate_edge(self):
        instr = self._parse("""
            COMPONENT a = Arm() AT (0,0,0) ABSOLUTE
            COMPONENT b = Arm() AT (0,0,1) RELATIVE a
            COMPONENT c = Arm() AT (0,0,2) RELATIVE a JUMP a ITERATE (jumps)
        """)
        G = build_particle_flow_graph(instr)
        jump_edges = [e for e in _flows(G, 'c', 'a') if isinstance(e, JumpEdge)]
        self.assertEqual(len(jump_edges), 1)
        self.assertTrue(jump_edges[0].iterate)

    # ------------------------------------------------------------------
    # Serialisation round-trip
    # ------------------------------------------------------------------

    def test_sequential_edge_roundtrip(self):
        instr = self._parse("""
            COMPONENT a = Arm() AT (0,0,0) ABSOLUTE
            COMPONENT b = Arm() AT (0,0,1) RELATIVE a
        """)
        G = build_particle_flow_graph(instr)
        edge = _flows(G, 'a', 'b')[0]
        encoded = msgspec.json.encode(edge)
        decoded = msgspec.json.decode(encoded, type=AnyFlowEdge)
        self.assertIsInstance(decoded, SequentialEdge)

    def test_group_edge_roundtrip(self):
        instr = self._parse("""
            COMPONENT before = Arm() AT (0,0,0) ABSOLUTE
            COMPONENT g1 = Arm() AT (0,0,1) RELATIVE before GROUP G
            COMPONENT g2 = Arm() AT (0,0,2) RELATIVE before GROUP G
            COMPONENT after = Arm() AT (0,0,4) RELATIVE before
        """)
        G = build_particle_flow_graph(instr)
        try_next = next(e for e in _flows(G, 'g1', 'g2') if isinstance(e, GroupEdge))
        encoded = msgspec.json.encode(try_next)
        decoded = msgspec.json.decode(encoded, type=AnyFlowEdge)
        self.assertIsInstance(decoded, GroupEdge)
        self.assertEqual(decoded.kind, GroupEdgeKind.TRY_NEXT)
        self.assertEqual(decoded.group_name, 'G')

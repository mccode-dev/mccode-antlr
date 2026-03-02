"""Tests for Instr.insert_component."""
from unittest import TestCase

from mccode_antlr.utils import parse_instr_string
from mccode_antlr.instr.flow import SequentialEdge, GroupEdge, GroupEdgeKind


def _parse(trace_body: str):
    src = f"""
    DEFINE INSTRUMENT test()
    TRACE
    {trace_body}
    END
    """
    return parse_instr_string(src)


def _edge_pairs(instr):
    """Return list of (src, dst, edge_type_name) for all flow edges."""
    return [(r.src, r.dst, type(r.edge).__name__) for r in instr.flow_edges]


def _sequential_pairs(instr):
    """Return (src, dst) for all SequentialEdge records."""
    return [(r.src, r.dst) for r in instr.flow_edges if isinstance(r.edge, SequentialEdge)]


def _group_pairs_by_kind(instr, kind):
    return [(r.src, r.dst) for r in instr.flow_edges
            if isinstance(r.edge, GroupEdge) and r.edge.kind == kind]


class TestInsertComponentSequential(TestCase):

    def _seq_instr(self):
        return _parse("""
            COMPONENT a = Arm() AT (0,0,0) ABSOLUTE
            COMPONENT b = Arm() AT (0,0,1) RELATIVE a
            COMPONENT c = Arm() AT (0,0,2) RELATIVE b
        """)

    # ── insert_before ────────────────────────────────────────────────────────

    def test_insert_before_middle_component_names(self):
        instr = self._seq_instr()
        instr.insert_component('x', instr.get_component('b').type, before='b')
        self.assertEqual([c.name for c in instr.components], ['a', 'x', 'b', 'c'])

    def test_insert_before_splits_sequential_edge(self):
        instr = self._seq_instr()
        instr.insert_component('x', instr.get_component('a').type, before='b')
        seq = _sequential_pairs(instr)
        self.assertIn(('a', 'x'), seq)
        self.assertIn(('x', 'b'), seq)
        self.assertNotIn(('a', 'b'), seq)

    def test_insert_before_first_component(self):
        instr = self._seq_instr()
        instr.insert_component('x', instr.get_component('a').type, before='a')
        self.assertEqual(instr.components[0].name, 'x')
        seq = _sequential_pairs(instr)
        self.assertIn(('x', 'a'), seq)
        # No pred: no edge into 'x' from another component
        self.assertFalse(any(r.dst == 'x' for r in instr.flow_edges))

    # ── insert_after ─────────────────────────────────────────────────────────

    def test_insert_after_middle_component_names(self):
        instr = self._seq_instr()
        instr.insert_component('x', instr.get_component('b').type, after='b')
        self.assertEqual([c.name for c in instr.components], ['a', 'b', 'x', 'c'])

    def test_insert_after_splits_sequential_edge(self):
        instr = self._seq_instr()
        instr.insert_component('x', instr.get_component('a').type, after='b')
        seq = _sequential_pairs(instr)
        self.assertIn(('b', 'x'), seq)
        self.assertIn(('x', 'c'), seq)
        self.assertNotIn(('b', 'c'), seq)

    def test_insert_after_last_component(self):
        instr = self._seq_instr()
        instr.insert_component('x', instr.get_component('a').type, after='c')
        self.assertEqual(instr.components[-1].name, 'x')
        seq = _sequential_pairs(instr)
        self.assertIn(('c', 'x'), seq)
        self.assertFalse(any(r.src == 'x' for r in instr.flow_edges))

    # ── validation ───────────────────────────────────────────────────────────

    def test_insert_requires_exactly_one_of_before_after(self):
        instr = self._seq_instr()
        with self.assertRaises(ValueError):
            instr.insert_component('x', instr.get_component('a').type)  # neither
        with self.assertRaises(ValueError):
            instr.insert_component('x', instr.get_component('a').type, before='a', after='b')

    def test_insert_duplicate_name_raises(self):
        instr = self._seq_instr()
        with self.assertRaises(ValueError):
            instr.insert_component('b', instr.get_component('a').type, before='b')

    def test_insert_unknown_reference_raises(self):
        instr = self._seq_instr()
        with self.assertRaises(ValueError):
            instr.insert_component('x', instr.get_component('a').type, before='z')

    # ── graph consistency ─────────────────────────────────────────────────────

    def test_flow_graph_has_new_node(self):
        instr = self._seq_instr()
        instr.insert_component('x', instr.get_component('a').type, after='a')
        G = instr.flow_graph
        self.assertIn('x', G.nodes)

    def test_flow_graph_instance_reference(self):
        instr = self._seq_instr()
        inst = instr.insert_component('x', instr.get_component('a').type, after='a')
        G = instr.flow_graph
        self.assertIs(G.nodes['x']['instance'], inst)

    def test_sequential_edge_count_increases_by_one(self):
        """After insertion, there is one more sequential edge (split → two, lost one)."""
        instr = self._seq_instr()
        before = len(_sequential_pairs(instr))
        instr.insert_component('x', instr.get_component('a').type, after='a')
        after_count = len(_sequential_pairs(instr))
        self.assertEqual(after_count, before + 1)

    def test_returned_instance_is_in_components(self):
        instr = self._seq_instr()
        inst = instr.insert_component('x', instr.get_component('a').type, before='b')
        self.assertIn(inst, instr.components)
        self.assertIs(instr.get_component('x'), inst)


class TestInsertComponentGroup(TestCase):

    def _group_instr(self):
        return _parse("""
            COMPONENT before = Arm() AT (0,0,0) ABSOLUTE
            COMPONENT g1 = Arm() AT (0,0,1) RELATIVE before GROUP MyGroup
            COMPONENT g2 = Arm() AT (0,0,2) RELATIVE before GROUP MyGroup
            COMPONENT g3 = Arm() AT (0,0,3) RELATIVE before GROUP MyGroup
            COMPONENT after = Arm() AT (0,0,4) RELATIVE before
        """)

    def test_insert_group_member_between_two_members(self):
        """Insert a group member between g1 and g2; TRY_NEXT chain preserved."""
        instr = self._group_instr()
        comp_type = instr.get_component('g1').type
        instr.insert_component('gx', comp_type, after='g1', group='MyGroup')
        names = [c.name for c in instr.components]
        self.assertEqual(names, ['before', 'g1', 'gx', 'g2', 'g3', 'after'])
        try_next = _group_pairs_by_kind(instr, GroupEdgeKind.TRY_NEXT)
        self.assertIn(('g1', 'gx'), try_next)
        self.assertIn(('gx', 'g2'), try_next)
        self.assertNotIn(('g1', 'g2'), try_next)

    def test_insert_non_group_between_group_members_raises(self):
        """Inserting a non-group component between group members raises ValueError."""
        instr = self._group_instr()
        comp_type = instr.get_component('g1').type
        with self.assertRaises(ValueError, msg="Expected ValueError for group contiguity violation"):
            instr.insert_component('gx', comp_type, after='g1')

    def test_insert_wrong_group_between_group_members_raises(self):
        """Inserting a component from a different group between group members raises ValueError."""
        instr = self._group_instr()
        comp_type = instr.get_component('g1').type
        with self.assertRaises(ValueError):
            instr.insert_component('gx', comp_type, after='g1', group='OtherGroup')

    def test_insert_same_group_between_group_members_succeeds(self):
        """Inserting a component that joins the same group between members is allowed."""
        instr = self._group_instr()
        comp_type = instr.get_component('g1').type
        instr.insert_component('gx', comp_type, after='g1', group='MyGroup')
        try_next = _group_pairs_by_kind(instr, GroupEdgeKind.TRY_NEXT)
        self.assertIn(('g1', 'gx'), try_next)
        self.assertIn(('gx', 'g2'), try_next)
        self.assertNotIn(('g1', 'g2'), try_next)

    def test_insert_before_group_does_not_break_group_edges(self):
        """Insert before the group; group-internal TRY_NEXT edges unchanged."""
        instr = self._group_instr()
        comp_type = instr.get_component('before').type
        instr.insert_component('x', comp_type, before='before')
        try_next = _group_pairs_by_kind(instr, GroupEdgeKind.TRY_NEXT)
        self.assertIn(('g1', 'g2'), try_next)
        self.assertIn(('g2', 'g3'), try_next)

    def test_scatter_exit_edges_unchanged_after_insert_within_group(self):
        """SCATTER_EXIT edges still connect to 'after' after inserting within group."""
        instr = self._group_instr()
        comp_type = instr.get_component('g1').type
        instr.insert_component('gx', comp_type, after='g1', group='MyGroup')
        scatter = _group_pairs_by_kind(instr, GroupEdgeKind.SCATTER_EXIT)
        # All original group members should still exit to 'after'
        for member in ('g1', 'g2', 'g3'):
            self.assertIn((member, 'after'), scatter, f"SCATTER_EXIT from {member} missing")


class TestInsertComponentJump(TestCase):

    def _jump_instr(self):
        return _parse("""
            COMPONENT a = Arm() AT (0,0,0) ABSOLUTE
            COMPONENT b = Arm() AT (0,0,1) RELATIVE a
            COMPONENT c = Arm() AT (0,0,2) RELATIVE b
              JUMP b WHEN(1)
            COMPONENT d = Arm() AT (0,0,3) RELATIVE c
        """)

    def test_jump_targets_invalidated_after_insert(self):
        """After insert_component, all Jump.absolute_target values are -1."""
        instr = self._jump_instr()
        comp_type = instr.get_component('a').type
        instr.insert_component('x', comp_type, after='a')
        for inst in instr.components:
            for jmp in inst.jump:
                self.assertEqual(jmp.absolute_target, -1,
                                 f"{inst.name}.jump.absolute_target should be -1 after insertion")

    def test_jump_edge_dst_name_still_correct(self):
        """JumpEdge records in flow_edges still reference 'b' by name after insertion."""
        from mccode_antlr.instr.flow import JumpEdge
        instr = self._jump_instr()
        jump_records = [r for r in instr.flow_edges if isinstance(r.edge, JumpEdge)]
        # There should be exactly one jump edge: c → b
        self.assertEqual(len(jump_records), 1)
        self.assertEqual(jump_records[0].src, 'c')
        self.assertEqual(jump_records[0].dst, 'b')

        comp_type = instr.get_component('a').type
        instr.insert_component('x', comp_type, after='a')  # inserts at index 1

        # Jump edge should still point to 'b' by name
        jump_records_after = [r for r in instr.flow_edges if isinstance(r.edge, JumpEdge)]
        self.assertEqual(len(jump_records_after), 1)
        self.assertEqual(jump_records_after[0].dst, 'b')

    def test_flow_graph_jump_edge_still_connects_to_b(self):
        """flow_graph routes JUMP edge to 'b' even after an insertion before 'b'."""
        from mccode_antlr.instr.flow import JumpEdge
        instr = self._jump_instr()
        comp_type = instr.get_component('a').type
        instr.insert_component('x', comp_type, after='a')
        G = instr.flow_graph
        # Should have an edge from 'c' to 'b'
        jump_edges = [d['flow'] for _, _, d in G.out_edges('c', data=True)
                      if isinstance(d['flow'], JumpEdge)]
        self.assertEqual(len(jump_edges), 1)


class TestInsertComponentPositioning(TestCase):

    def _positioned_instr(self):
        return _parse("""
            COMPONENT a = Arm() AT (0,0,0) ABSOLUTE
            COMPONENT b = Arm() AT (0,0,2) RELATIVE a
        """)

    def test_auto_midpoint_at_relative_is_set(self):
        """When no at_relative is provided, the new instance gets a non-None at_relative."""
        instr = self._positioned_instr()
        inst = instr.insert_component('x', instr.get_component('a').type, before='b')
        self.assertIsNotNone(inst.at_relative)
        at_vec, ref_inst = inst.at_relative
        self.assertIsNotNone(at_vec)

    def test_explicit_at_relative_tuple_is_used(self):
        """When at_relative given as ((x,y,z), ref_name), it is normalised and stored."""
        instr = self._positioned_instr()
        a_inst = instr.get_component('a')
        inst = instr.insert_component(
            'x', instr.get_component('a').type,
            before='b',
            at_relative=((0, 0, 1), 'a'),
        )
        at_vec, ref_inst = inst.at_relative
        self.assertIs(ref_inst, a_inst)

    def test_explicit_at_relative_with_forward_ref_is_fixed(self):
        """When at_relative references 'b' (which comes after the insertion), it is fixed to 'a'."""
        instr = self._positioned_instr()
        a_inst = instr.get_component('a')
        inst = instr.insert_component(
            'x', instr.get_component('a').type,
            before='b',
            at_relative=((0, 0, 0), 'b'),  # 'b' is after the new instance → must be fixed
        )
        _, ref_inst = inst.at_relative
        # Reference must have been re-expressed relative to 'a' (the predecessor)
        self.assertIs(ref_inst, a_inst)

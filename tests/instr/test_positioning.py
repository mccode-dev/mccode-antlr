from unittest import TestCase


class TestInstrPositioning(TestCase):

    def assertRotationsEqual(self, r1, r2):
        from mccode_antlr.instr.orientation import Rotation, Matrix
        self.assertTrue(isinstance(r1, Rotation))
        self.assertTrue(isinstance(r2, Rotation))
        d = r1 - r2
        self.assertTrue(isinstance(d, Matrix))
        self.assertEqual(round(abs(d), 14), Matrix())

    def _positioning_evaluator(self, instr):
        """Common positioning checks for `test_read_positioning` and `test_assemble_positioning`"""
        from mccode_antlr.common import Expr
        from mccode_antlr.instr.orientation import Vector, Rotation
        z, o = Expr.float(0), Expr.float(1)

        orientations = instr.resolve_orientations()

        left_or = orientations['left']
        v3 = Vector(z, z, o)
        self.assertEqual(v3, left_or.position())
        self.assertEqual(Rotation(z, z, -o, z, o, z, o, z, z), left_or.rotation())
        self.assertEqual(left_or.rotation(), left_or.rotation('coordinates').inverse())

        up_or = orientations['up']
        v4 = Vector(o, z, z)
        self.assertEqual(v4, up_or.position() - left_or.position())
        up_orientation = Rotation(z, z, -o, -o, z, z, z, o, z)
        self.assertRotationsEqual(up_orientation, up_or.rotation())
        self.assertEqual(Vector(o, z, o), up_or.position())
        self.assertRotationsEqual(up_orientation, up_or.rotation('coordinates').inverse())

        last_or = orientations['last']
        v5 = Vector(z, o, z)
        self.assertRotationsEqual(up_orientation, last_or.rotation())
        self.assertEqual(v5, last_or.position() - up_or.position())

    def test_assemble_positioning(self):
        from mccode_antlr.utils import make_assembler

        """Equivalent test to `test_read_positioning` but using an assembled instrument"""
        assembler = make_assembler('orientation_test')
        origin = assembler.component("origin", "Progress_bar", at=[0, 0, 0])
        # Use explicit (angles, reference) pairs so rotation is RELATIVE, matching the parsed version.
        left = assembler.component('left', 'Arm', at=([0, 0, 1], origin), rotate=([0, 90, 0], origin))
        up = assembler.component("up", 'Arm', at=([0, 0, 1], left), rotate=([-90, 0, 0], left))
        assembler.component("last", 'Arm', at=([0, 0, 1], up), rotate=([0, 0, 0], up))
        self._positioning_evaluator(assembler.instrument)

    def test_read_positioning(self):
        from mccode_antlr.utils import parse_instr_string

        """Equivalent test to `test_assemble_positioning` but using a parsed instrument"""
        instr_source = """DEFINE INSTRUMENT orientation_test() TRACE
        COMPONENT origin = Arm() AT (0, 0, 0) ABSOLUTE
        COMPONENT left = Arm() AT (0, 0, 1) RELATIVE PREVIOUS ROTATED (0, 90, 0) RELATIVE origin
        COMPONENT up = Arm() AT (0, 0, 1) RELATIVE left ROTATED (-90, 0, 0) RELATIVE left
        COMPONENT last = Arm() AT (0, 0, 1) RELATIVE up
        END """
        self._positioning_evaluator(parse_instr_string(instr_source))

    def test_absolute_rotation(self):
        """AT RELATIVE A ROTATED (a,b,c) ABSOLUTE must use the global frame, not A's frame.

        Also covers the bare-angles form rotate=(a,b,c) in the Assembler API, which
        is treated as ABSOLUTE (no reference) rather than inheriting the AT reference.
        """
        from mccode_antlr.utils import make_assembler, parse_instr_string
        from mccode_antlr.common import Expr
        from mccode_antlr.instr.orientation import Vector

        z, o = Expr.float(0), Expr.float(1)

        # ── Parser path ────────────────────────────────────────────────────────
        # ref is AT (0,0,1) RELATIVE origin ROTATED (0,90,0) RELATIVE origin
        #     → position (0,0,1), rotation R_Y(90°)
        # comp_abs is AT (0,0,1) RELATIVE ref ROTATED (0,0,0) ABSOLUTE
        #     → position (1,0,1), rotation = identity  (global frame)
        # comp_rel is AT (0,0,1) RELATIVE ref ROTATED (0,0,0) RELATIVE ref
        #     → position (1,0,1), rotation = R_Y(90°)  (ref's frame)
        instr = parse_instr_string("""DEFINE INSTRUMENT abs_rot_test() TRACE
        COMPONENT origin   = Arm() AT (0,0,0) ABSOLUTE
        COMPONENT ref      = Arm() AT (0,0,1) RELATIVE origin ROTATED (0,90,0) RELATIVE origin
        COMPONENT comp_abs = Arm() AT (0,0,1) RELATIVE ref    ROTATED (0,0,0) ABSOLUTE
        COMPONENT comp_rel = Arm() AT (0,0,1) RELATIVE ref    ROTATED (0,0,0) RELATIVE ref
        END""")
        orientations = instr.resolve_orientations()

        expected_pos = Vector(o, z, o)  # (1, 0, 1)
        self.assertEqual(expected_pos, orientations['comp_abs'].position())
        self.assertEqual(expected_pos, orientations['comp_rel'].position())
        # comp_abs uses global frame → same rotation as origin (identity)
        self.assertRotationsEqual(orientations['origin'].rotation(), orientations['comp_abs'].rotation())
        # comp_rel uses ref's frame → same rotation as ref (R_Y(90°))
        self.assertRotationsEqual(orientations['ref'].rotation(), orientations['comp_rel'].rotation())

        # ── Assembler path — exercises _handle_rotate ─────────────────────────
        assembler = make_assembler('abs_rot_test')
        a_origin = assembler.component('origin', 'Arm', at=[0, 0, 0])
        a_ref = assembler.component('ref', 'Arm', at=([0, 0, 1], a_origin),
                                    rotate=([0, 90, 0], a_origin))
        # Explicit 'ABSOLUTE' reference: the bug
        a_abs = assembler.component('comp_abs', 'Arm', at=([0, 0, 1], a_ref),
                                    rotate=([0, 0, 0], 'ABSOLUTE'))
        # Bare 3-tuple — also treated as ABSOLUTE (same bug)
        a_bare = assembler.component('comp_bare', 'Arm', at=([0, 0, 1], a_ref),
                                     rotate=[0, 0, 0])
        a_rel = assembler.component('comp_rel', 'Arm', at=([0, 0, 1], a_ref),
                                    rotate=([0, 0, 0], a_ref))

        oa = assembler.instrument.resolve_orientations()
        self.assertEqual(expected_pos, oa['comp_abs'].position())
        self.assertEqual(expected_pos, oa['comp_bare'].position())
        self.assertEqual(expected_pos, oa['comp_rel'].position())
        # Both explicit ABSOLUTE and bare-tuple forms must give global-frame rotation
        self.assertRotationsEqual(oa['origin'].rotation(), oa['comp_abs'].rotation())
        self.assertRotationsEqual(oa['origin'].rotation(), oa['comp_bare'].rotation())
        # RELATIVE ref gives ref's rotation
        self.assertRotationsEqual(oa['ref'].rotation(), oa['comp_rel'].rotation())

    def _simple_position_tests(self, instr, positions: dict):
        from mccode_antlr.common import Expr
        from mccode_antlr.instr.orientation import Vector
        positions = {k: Vector(*[Expr.float(x) for x in v]) for k, v in positions.items()}
        orientations = instr.resolve_orientations()
        for instance in instr.components:
            orient = orientations[instance.name]
            self.assertEqual(positions[instance.name], orient.position())
            self.assertEqual(positions[instance.name], orient.position('axes'))
            self.assertEqual(positions[instance.name], orient.position('coordinates'))

    def test_simple_positioning(self):
        from mccode_antlr.utils import parse_instr_string

        from math import pi, cos, sin
        instr_source = """DEFINE INSTRUMENT simple_test() TRACE
        COMPONENT origin = Arm() AT (0, 0, 0) ABSOLUTE
        COMPONENT slit = Arm() at (0, 0, 10) RELATIVE origin
        COMPONENT sample = Arm() at (0, 0, 10) RELATIVE slit
        END"""
        instr = parse_instr_string(instr_source)
        positions = {'origin': (0, 0, 0), 'slit': (0, 0, 10), 'sample': (0, 0, 20)}
        self._simple_position_tests(instr, positions)

        instr_source = """DEFINE INSTRUMENT slightly_more_complex() TRACE
        COMPONENT origin = Arm() AT (0, 0, 0) ABSOLUTE
        COMPONENT guide_start = Arm() AT (0.01277, 0, 1.930338) RELATIVE origin ROTATED (0, -0.56, 0) RELATIVE origin
        COMPONENT guide = Arm() AT (0, 0, 0) RELATIVE guide_start
        COMPONENT guide_end = Arm() AT (0, 0, 4.33) RELATIVE guide
        END
        """
        instr = parse_instr_string(instr_source)
        positions = {'origin': (0, 0, 0), 'guide_start': (0.01277, 0, 1.930338), 'guide': (0.01277, 0, 1.930338),
                     'guide_end': (0.01277 - 4.33*sin(pi/180*0.56), 0, 1.930338 + 4.33*cos(pi/180*0.56))}
        self._simple_position_tests(instr, positions)

        orientations = instr.resolve_orientations()
        pos = orientations['guide'].position()
        distance = pos.length()
        vector = pos / distance
        pos_hat = (0.006615, 0, 0.999978)
        self.assertAlmostEqual(vector.x, pos_hat[0], 6)
        self.assertAlmostEqual(vector.y, pos_hat[1], 6)
        self.assertAlmostEqual(vector.z, pos_hat[2], 6)
        self.assertAlmostEqual(distance, 1.930380239005777, 6)

        # Combining the position and rotation (reduced) operations should yield the same position
        comb = orientations['guide'].combine().reduce()
        self.assertEqual(pos, comb.position())

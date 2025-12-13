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

        left = instr.get_component('left')
        v3 = Vector(z, z, o)
        self.assertEqual(v3, left.orientation.position())
        self.assertEqual(Rotation(z, z, -o, z, o, z, o, z, z), left.orientation.rotation())
        self.assertEqual(left.orientation.rotation(), left.orientation.rotation('coordinates').inverse())

        up = instr.get_component('up')
        v4 = Vector(o, z, z)
        self.assertEqual(v4, up.orientation.position() - left.orientation.position())
        up_orientation = Rotation(z, z, -o, -o, z, z, z, o, z)
        self.assertRotationsEqual(up_orientation, up.orientation.rotation())
        self.assertEqual(Vector(o, z, o), up.orientation.position())
        self.assertRotationsEqual(up_orientation, up.orientation.rotation('coordinates').inverse())

        last = instr.get_component('last')
        v5 = Vector(z, o, z)
        self.assertRotationsEqual(up_orientation, last.orientation.rotation())
        self.assertEqual(v5, last.orientation.position() - up.orientation.position())

    def test_assemble_positioning(self):
        from mccode_antlr.utils import make_assembler

        """Equivalent test to `test_read_positioning` but using an assembled instrument"""
        assembler = make_assembler('orientation_test')
        origin = assembler.component("origin", "Progress_bar", at=[0, 0, 0])
        left = assembler.component('left', 'Arm', at=([0, 0, 1], origin), rotate=[0, 90, 0])
        up = assembler.component("up", 'Arm', at=([0, 0, 1], left), rotate=[-90, 0, 0])
        assembler.component("last", 'Arm', at=([0, 0, 1], up), rotate=[0, 0, 0])
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

    def _simple_position_tests(self, instr, positions: dict):
        from mccode_antlr.common import Expr
        from mccode_antlr.instr.orientation import Vector
        positions = {k: Vector(*[Expr.float(x) for x in v]) for k, v in positions.items()}
        for instance in instr.components:
            self.assertEqual(positions[instance.name], instance.orientation.position())
            self.assertEqual(positions[instance.name], instance.orientation.position('axes'))
            self.assertEqual(positions[instance.name], instance.orientation.position('coordinates'))

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
        pos_hat = (0.006615, 0, 0.999978)
        pos = instr.components[2].orientation.position()
        distance = pos.length()
        vector = pos / distance
        self.assertAlmostEqual(vector.x, pos_hat[0], 6)
        self.assertAlmostEqual(vector.y, pos_hat[1], 6)
        self.assertAlmostEqual(vector.z, pos_hat[2], 6)
        self.assertAlmostEqual(distance, 1.930380239005777, 6)

        # Combining the position and rotation (reduced) operations should yield the same position
        comb = instr.components[2].orientation.combine().reduce()
        self.assertEqual(pos, comb.position())
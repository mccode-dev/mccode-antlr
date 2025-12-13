from unittest import TestCase

from mccode_antlr.instr import Instr, Instance
from mccode_antlr.common.expression import Expr
from mccode_antlr.instr.orientation import Vector


class TestInstrSplit(TestCase):
    def test_mcpl_split(self):
        from mccode_antlr.utils import parse_instr_string

        instr_source = """
        DEFINE INSTRUMENT test_copy()
        TRACE
        COMPONENT origin = Arm() AT (0, 0, 0) ABSOLUTE
        COMPONENT first = Arm() AT (0, 0, 100) RELATIVE origin ROTATED (0, 90, 0) RELATIVE origin
        COMPONENT second = Arm() AT (0, 0, 1) RELATIVE first ROTATED (-90, 0, 0) RELATIVE first
        COMPONENT split_here = Arm() AT (0, 0, 0) RELATIVE second
        COMPONENT third = Arm() AT (0, 0, 10) RELATIVE second
        END
        """
        instr = parse_instr_string(instr_source)
        before, after = instr.mcpl_split('split_here', filename='test_mcpl_split')
        self.assertTrue(isinstance(before, Instr))
        self.assertTrue(isinstance(after, Instr))
        self.assertEqual(len(before.components), 4)
        self.assertEqual(len(after.components), 2)
        for inst, name in zip(before.components, ('origin', 'first', 'second', 'split_here')):
            self.assertEqual(name, inst.name)

        for inst, name in zip(after.components, ('split_here', 'third')):
            self.assertEqual(name, inst.name)

        self.assertEqual(before.components[-1].type.name, 'MCPL_output')
        self.assertEqual(after.components[0].type.name, 'MCPL_input')

        # It is imperative that the split-point did not move:
        sp = after.components[0]
        at_rel = sp.at_relative
        self.assertTrue(at_rel[1] is None)  # the position is absolute
        pos = Vector(Expr.float(1), Expr.float(0), Expr.float(100))
        self.assertEqual(pos, at_rel[0])

        # The final component had a relative position which spanned the split point, so it should now be absolute
        self.assertTrue(after.components[-1].at_relative[1] is None)
        # rounding makes third.x 1.000...07
        for a, b in zip(Vector(Expr.float(1), Expr.float(10), Expr.float(100)), after.components[-1].at_relative[0]):
            self.assertAlmostEqual(a, b)

        # The relative orientation of components 'first' and 'second' must persist into the 'before' instrument:
        first = before.get_component('first')
        self.assertEqual(first.rotate_relative[1], before.get_component('origin'))
        self.assertEqual(before.get_component('second').rotate_relative[1], first)

    def test_split_broken_reference(self):
        from mccode_antlr.utils import parse_instr_string

        from textwrap import dedent
        instr = dedent("""\
        DEFINE INSTRUMENT test_tof(phase/"degree"=0)
        TRACE
        COMPONENT Origin = Progress_bar() AT (0, 0, 0) ABSOLUTE 
        COMPONENT ESS_source = ESS_butterfly(
            sector="W", beamline=4, yheight=0.03, cold_frac=0.5, dist=1, focus_xw=0.01, focus_yh=0.01, 
            c_performance=1.0, t_performance=1.0, Lmin=1, Lmax=2, tmax_multiplier=1.5, n_pulses=1, acc_power=2.0
        ) AT (0, 0, 0) ABSOLUTE 
        COMPONENT guide = Guide_gravity(w1=0.01, w2=0.05, h1=0.01, h2=0.05, l=8.0, m=3.5, G=-9.82) AT (0, 0, 1) ABSOLUTE 
        COMPONENT guide_end = Arm() AT (0, 0, 8.0) RELATIVE guide
        COMPONENT chopper = DiskChopper(radius=0.35, nu=14, phase=phase, theta_0=115) AT (0, 0, 0.01) RELATIVE guide_end
        COMPONENT split_before = Arm() AT (0, 0, 1e-08) RELATIVE chopper
        COMPONENT split_at = Arm() AT (0, 0, 0) RELATIVE split_before
        COMPONENT split_after = Arm() AT (0, 0, 0) RELATIVE split_before
        COMPONENT sample = Incoherent(
            radius=0.005, yheight=0.02, thickness=0.001, focus_ah=2.0, focus_aw=2.0, target_x=1.0, target_y=0.0, 
            target_z=0.0, Etrans=0.0, deltaE=0.2
        ) AT (0, 0, 1) RELATIVE chopper 
        COMPONENT a4 = Arm() AT (0, 0, 0) RELATIVE sample ROTATED (0, 90, 0) RELATIVE sample
        COMPONENT analyzer = Arm() AT (0, 0, 1) RELATIVE a4
        COMPONENT a6 = Arm() AT (0, 0, 0) RELATIVE analyzer ROTATED (0, -90, 0) RELATIVE analyzer
        COMPONENT detector = Arm() AT (0, 0, 1) RELATIVE a6
        END""")
        instr = parse_instr_string(instr)
        first, second = instr.split('split_at', remove_unused_parameters=True)
        # The last component in the first part of the instrument _is_ split_at
        self.assertEqual('split_at', first.components[-1].name)
        # The position of the split_at component should be absolute and the same as in the main instrument
        split_at = second.components[0]
        self.assertEqual(split_at.name, 'split_at')
        at_ref = split_at.at_relative
        self.assertTrue(isinstance(at_ref[0], Vector))
        self.assertTrue(at_ref[1] is None)
        v = Vector(Expr.float(0), Expr.float(0), Expr.float(1 + 8 + 0.01 + 1E-8))
        self.assertEqual(v, at_ref[0])

        # The sample _should not_ still depend on the chopper, which is only present in the first instrument!
        sample = second.components[2]
        self.assertEqual(sample.name, 'sample')
        at_ref = sample.at_relative
        self.assertTrue(isinstance(at_ref[0], Vector))
        self.assertFalse(isinstance(at_ref[1], Instance))
        self.assertTrue(at_ref[1] is None)
        # the position of the sample depends on the source, guide, guide-end, and chopper
        v = Vector(Expr.float(0), Expr.float(0), Expr.float(1 + 8 + 0.01 + 1))
        self.assertEqual(v, at_ref[0])

        # But everything after _should_ still depend on relative positions
        for i, name in enumerate(('a4', 'analyzer', 'a6', 'detector')):
            # Verify that we positioned the components relative in the initial instrument
            i_inst = instr.components[len(first.components)+2+i]
            self.assertEqual(name, i_inst.name)
            self.assertTrue(i_inst.at_relative[1] is not None)
            self.assertTrue(i_inst.rotate_relative[1] is not None)
            self.assertTrue(instr.has_component_named(i_inst.at_relative[1].name))
            self.assertTrue(second.has_component_named(i_inst.at_relative[1].name))
            # And that, since they're relative to second-instrument components, they're still relative
            s_inst = second.components[3+i]
            self.assertEqual(name, s_inst.name)
            self.assertTrue(s_inst.at_relative[1] is not None)
            self.assertTrue(s_inst.rotate_relative[1] is not None)

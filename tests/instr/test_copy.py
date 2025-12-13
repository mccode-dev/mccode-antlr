from unittest import TestCase


class TestInstrCopy(TestCase):
    def test_copy(self):
        from mccode_antlr.instr import Instr
        from mccode_antlr.common import InstrumentParameter, Expr
        from mccode_antlr.utils import parse_instr_string
        instr_source = """
        DEFINE INSTRUMENT test_copy(par0=3.14159, double par1 = 49, int par2 =     1010110
            , string par3="this is a long string with spaces", 

            string par4, int par5, double par6, par7)
        TRACE
        COMPONENT first = Arm() AT (0, 0, 0) ABSOLUTE
        COMPONENT second = Arm() AT (0, 0, 1) RELATIVE first ROTATED (0, 90, 0) RELATIVE first
        END
        """
        instr = parse_instr_string(instr_source)
        instr_copy = instr.copy()
        self.assertTrue(isinstance(instr_copy, Instr))
        self.assertEqual(instr.name, instr_copy.name)
        self.assertEqual(len(instr.parameters), len(instr_copy.parameters))
        self.assertEqual(len(instr.components), len(instr_copy.components))
        for p, p_copy in zip(instr.parameters, instr_copy.parameters):
            self.assertTrue(isinstance(p_copy, InstrumentParameter))
            self.assertEqual(p.name, p_copy.name)
            self.assertEqual(p.value, p_copy.value)

        instr_copy.add_parameter(InstrumentParameter('par8', '', Expr.float(1.6189)))
        self.assertEqual(len(instr.parameters), len(instr_copy.parameters) - 1)

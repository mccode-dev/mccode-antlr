from unittest import TestCase


class TestInstrParameters(TestCase):

    def test_tas1_c1_parameter(self):
        from mccode_antlr.loader.loader import parse_mccode_instr_parameters
        contents = """ DEFINE INSTRUMENT tas(PHM=-37.077,TTM=-74,C1=30) TRACE END"""
        instr_parameters = parse_mccode_instr_parameters(contents)
        self.assertEqual(len(instr_parameters), 3)
        self.assertEqual(instr_parameters[0].name, 'PHM')
        self.assertEqual(instr_parameters[1].name, 'TTM')
        self.assertEqual(instr_parameters[2].name, 'C1')
        self.assertEqual(instr_parameters[0].value, -37.077)
        self.assertEqual(instr_parameters[1].value, -74)
        self.assertEqual(instr_parameters[2].value, 30)

    def test_used_parameter_check(self):
        from mccode_antlr import Flavor
        from mccode_antlr.assembler import Assembler
        assembler = Assembler('test_used_parameter_check', flavor=Flavor.MCSTAS)
        assembler.parameter('double par0/"pi" = 3.14159')
        assembler.parameter('int par1 = 49')
        assembler.parameter('int par2 = 1010110')
        assembler.parameter('string par3 = "this is a long string with spaces"')
        assembler.parameter('string par4 = "the-fourth_parameter"')
        assembler.parameter('par5 = -9.11')
        assembler.parameter('a4/"degree" = 90')
        assembler.component('origin', 'Progress_bar', at=(0, 0, 0))
        assembler.component('left', 'PSD_monitor', at=(0, 0, 1), parameters=dict(
            xwidth='par0', yheight='2*fmod(par5, 0.1)', nx='par1', ny='par2 >> 4', restore_neutron=1))
        # TODO (maybe) the right shift operator is not implemented, instead the expression is parsed as
        #      BinOp('>', [BinOp('>', ['par2', '']), '4']) {or similar} which passes this test but may not
        #      be sufficient for all cases
        assembler.component('up', 'PSD_monitor', at=(0, 0, 2), parameters=dict(
            xwidth='cos(DEG2RAD * a4)', yheight='sin(DEG2RAD * a4)', nx='-a4 * DEG2RAD', restore_neutron=1))

        inst = assembler.instrument
        self.assertEqual(7, len(inst.parameters))
        self.assertEqual(3, len(inst.components))
        self.assertTrue(inst.parameter_used('par0'))
        self.assertTrue(inst.parameter_used('par1'))
        self.assertTrue(inst.parameter_used('par2'))
        self.assertFalse(inst.parameter_used('par3'))
        self.assertFalse(inst.parameter_used('par4'))
        self.assertTrue(inst.parameter_used('par5'))
        self.assertTrue(inst.parameter_used('a4'))
        self.assertEqual(2, inst.check_instrument_parameters(), )

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

    def test_parameter_types_parse_check(self):
        from mccode_antlr import Flavor
        from mccode_antlr.assembler import Assembler
        from mccode_antlr.reader.registry import InMemoryRegistry
        from mccode_antlr.common import DataType
        from textwrap import dedent
        import warnings
        comps = InMemoryRegistry('components')
        comps.add_comp('Only', dedent("""
        DEFINE COMPONENT Only
        SETTING PARAMETERS (
          a=1.,
          int b=2,
          string c="three",
          vector d = {4, 4, 4, 4},
          int * e = 0,
          double * f = 0
        )
        END
        """))
        assembler = Assembler('singular', flavor=Flavor.MCSTAS, registries=[comps])
        assembler.component('one', 'Only', at=[0, 0, 0])
        params = {p.name: p for p in assembler.instrument.get_component('one').type.setting}

        self.assertIn('a', params)
        self.assertEqual(params['a'].value.data_type, DataType.float)
        self.assertFalse(params['a'].value.is_vector)

        self.assertIn('b', params)
        self.assertEqual(params['b'].value.data_type, DataType.int)
        self.assertFalse(params['b'].value.is_vector)

        self.assertIn('c', params)
        self.assertEqual(params['c'].value.data_type, DataType.str)
        self.assertFalse(params['c'].value.is_vector)

        self.assertIn('d', params)
        self.assertEqual(params['d'].value.data_type, DataType.float)
        self.assertTrue(params['d'].value.is_vector)

        self.assertIn('e', params)
        self.assertEqual(params['e'].value.data_type, DataType.int)
        self.assertTrue(params['e'].value.is_vector)

        self.assertIn('f', params)
        self.assertEqual(params['f'].value.data_type, DataType.float)
        self.assertTrue(params['f'].value.is_vector)

    def test_symbol_parameter_warns_and_parses(self):
        from mccode_antlr import Flavor
        from mccode_antlr.assembler import Assembler
        from mccode_antlr.reader.registry import InMemoryRegistry
        from mccode_antlr.common import DataType
        from textwrap import dedent
        comps = InMemoryRegistry('components')
        comps.add_comp('WithSymbol', dedent("""
        DEFINE COMPONENT WithSymbol
        SETTING PARAMETERS (
          symbol g = FLT_MAX
        )
        END
        """))
        assembler = Assembler('singular', flavor=Flavor.MCSTAS, registries=[comps])
        with self.assertWarns(UserWarning):
            assembler.component('one', 'WithSymbol', at=[0, 0, 0])
        params = {p.name: p for p in assembler.instrument.get_component('one').type.setting}
        self.assertIn('g', params)
        self.assertEqual(params['g'].value.data_type, DataType.str)
        self.assertFalse(params['g'].value.is_vector)

from unittest import TestCase


class TestInstrEmptyTrace(TestCase):
    def test_parse_empty_trace(self):
        from mccode_antlr.instr import Instr
        from mccode_antlr.common import InstrumentParameter, Expr, Value, DataType
        from mccode_antlr.loader import parse_mcstas_instr
        instr_source = """
        DEFINE INSTRUMENT test_parse(par0=3.14159, double par1 = 49, int par2 =     1010110
            , string par3="this is a long string with spaces", 

            string par4, int par5, double par6, par7)
        TRACE
        END
        """
        instr = parse_mcstas_instr(instr_source)
        self.assertTrue(isinstance(instr, Instr))
        self.assertEqual(instr.name, 'test_parse')
        self.assertEqual(len(instr.parameters), 8)
        self.assertEqual(len(instr.components), 0)
        for i, (d_type, val) in enumerate([('double', 3.14159), ('double', 49), ('int', 1010110),
                                           ('string', '"this is a long string with spaces"'),
                                           ('string', None), ('int', None), ('double', None), ('double', None)]):
            p = instr.parameters[i]
            self.assertTrue(isinstance(p, InstrumentParameter))
            self.assertEqual(p.name, f'par{i}')
            self.assertTrue(isinstance(p.value, Expr))
            self.assertEqual(p.value, Value(val, DataType.from_name(d_type)))

    def test_assemble_empty_trace(self):
        from mccode_antlr.instr import Instr
        from mccode_antlr.common import InstrumentParameter, Expr, Value, DataType
        from mccode_antlr.utils import make_assembler

        assembler = make_assembler('test_assemble')

        # There are multiple ways to specify instrument parameters:
        # 1. specify a single parameter object to add:
        assembler.parameter(InstrumentParameter('par0', '', Expr.float(3.14159)))
        # 2. specify a single parameter as a string to be parsed:
        assembler.parameter('double par1 = 49')
        # 3. Using the parameters method, specify any number of parameter objects or strings to be parsed (as above)
        #    and/or specify keyword value pairs, where each value can be
        #      a. a two-element list or tuple of 'value', 'unit'
        #      b. a dict with entries 'unit' and 'value'
        #      c. a plain value
        #    in each of these cases, Expr.best converts the provided value if it is not already an Expr object
        assembler.parameters(InstrumentParameter('par2', '', Expr.int(1010110)),
                             'string par3 = "this is a long string with spaces"',
                             InstrumentParameter('par4', '', Expr.str('"the-fourth_parameter"')),
                             'int par5=-9', par6=[Expr.float(None), ''], par7=191, par8=dict(unit='', value='"whoa!"'))

        instr = assembler.instrument
        self.assertTrue(isinstance(instr, Instr))
        self.assertEqual(instr.name, 'test_assemble')
        self.assertEqual(len(instr.parameters), 9)
        self.assertEqual(len(instr.components), 0)
        d_type_vals = [('double', 3.14159), ('double', 49), ('int', 1010110),
                       ('string', '"this is a long string with spaces"'), ('string', '"the-fourth_parameter"'),
                       ('int', -9), ('float', None), ('int', 191), ('string', '"whoa!"')]
        for i, (par, (d_type, val)) in enumerate(zip(instr.parameters, d_type_vals)):
            self.assertTrue(isinstance(par, InstrumentParameter))
            self.assertEqual(par.name, f'par{i}')
            self.assertTrue(isinstance(par.value, Expr))
            self.assertEqual(par.value, Value(val, DataType.from_name(d_type)))

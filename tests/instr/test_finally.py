from unittest import TestCase
from mccode_antlr.test import compiled_test

class TestInstrFinally(TestCase):
    @compiled_test
    def test_parse_finally(self):
        from mccode_antlr.instr import Instr
        from mccode_antlr.loader import parse_mcstas_instr
        from mccode_antlr.utils import compile_and_run
        instr_source = """
        DEFINE INSTRUMENT test_finally_parse(par0=3.14159)
        TRACE
        FINALLY
        %{
        printf("this finally block is parsed\\n");
        %}
        END
        """
        instr = parse_mcstas_instr(instr_source)
        self.assertTrue(isinstance(instr, Instr))
        self.assertEqual(instr.name, 'test_finally_parse')
        self.assertEqual(len(instr.parameters), 1)
        self.assertEqual(len(instr.components), 0)
        self.assertEqual(len(instr.final), 1)
        self.assertTrue("this finally block is parsed" in str(instr.final[0]))

        std_output, dats = compile_and_run(instr, "-n 1 -y")
        self.assertTrue("this finally block is parsed" in std_output.decode())


    def test_assemble_empty_trace(self):
        from mccode_antlr.instr import Instr
        from mccode_antlr.utils import make_assembler

        assembler = make_assembler('test_finally_assemble')
        assembler.final('printf("this finally block is present\\n");')

        instr = assembler.instrument
        self.assertTrue(isinstance(instr, Instr))
        self.assertEqual(instr.name, 'test_finally_assemble')
        self.assertEqual(len(instr.final), 1)
        self.assertTrue("this finally block is present" in str(instr.final[0]))

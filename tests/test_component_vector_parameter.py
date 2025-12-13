import unittest

from mccode_antlr.test import compiled_test

FAKE_COMPONENTS = dict(component_with_vector_parameter="""
DEFINE COMPONENT component_with_vector_parameter
SETTING PARAMETERS (int n, vector easy_to_spot, vector dont_set_me)
OUTPUT PARAMETERS ()
SHARE 
%{
%}
DECLARE
%{
%}
INITIALIZE
%{
  if (n < 0) {
    fprintf(stderr, "component_with_vector_parameter: n < 0\\n");
  }
  if (easy_to_spot == NULL) {
    fprintf(stderr, "component_with_vector_parameter: parameter easy_to_spot is NULL\\n");
  }
  if (dont_set_me != NULL) {
    fprintf(stderr, "component_with_vector_parameter: parameter dont_set_me is not NULL\\n");
  }
  for (int i= 0; i < n; i++) {
    printf("easy_to_spot[%d] = %g\\n", i, easy_to_spot[i]);
  }
%}
TRACE
%{
%}
FINALLY
%{
%}
MCDISPLAY
%{
%}
END
""")


INSTR_CONTENTS = dict(test_vector_parameter="""
DEFINE INSTRUMENT test_vector_parameter()
DECLARE %{
double declared_array[] = {1, 2, 3};
%}
TRACE
COMPONENT origin = Arm() AT (0, 0, 0) ABSOLUTE
COMPONENT one = component_with_vector_parameter(n=3, easy_to_spot=declared_array) AT (0, 0, 1) RELATIVE origin
END
""")


class ComponentVectorParameterTestCase(unittest.TestCase):
    def setUp(self):
        from mccode_antlr import Flavor
        from mccode_antlr.assembler import Assembler
        self.assembler = Assembler('test', flavor=Flavor.MCSTAS)
        for name, contents in FAKE_COMPONENTS.items():
            self._parse_comp(name, contents)

    def _compile_and_run(self, instr, parameters):
        from mccode_antlr.compiler.c import compile_instrument, CBinaryTarget, run_compiled_instrument
        from mccode_antlr import Flavor
        from mccode_antlr.config import config as module_config
        from tempfile import TemporaryDirectory
        from os import R_OK, access
        from pathlib import Path

        target = CBinaryTarget(mpi=False, acc=False, count=1, nexus=False)
        config = dict(default_main=True, enable_trace=False, portable=False, include_runtime=True,
                      embed_instrument_file=False, verbose=False)

        with TemporaryDirectory() as directory:
            try:
                compile_instrument(instr, target, directory, flavor=Flavor.MCSTAS, config=config, dump_source=True)
            except RuntimeError as e:
                raise e
            binary = Path(directory).joinpath(f'{instr.name}{module_config["ext"].get(str)}')
            self.assertTrue(binary.exists())
            self.assertTrue(binary.is_file())
            self.assertTrue(access(binary, R_OK))
            result = run_compiled_instrument(binary, target, f"--dir {directory}/instr {parameters}", capture=True)
            filtered = filter(lambda x: x.startswith('easy_to_spot'), result.decode('utf8').split('\n'))
            return [float(x.split('=')[-1].strip()) for x in filtered]

    def _parse_comp(self, comp_name: str, contents: str, instance_name: str = 'instance'):
        from antlr4 import InputStream
        from mccode_antlr.grammar import McComp_parse, McComp_ErrorListener
        from mccode_antlr.comp import CompVisitor
        from mccode_antlr.reader.reader import make_reader_error_listener
        error_listener = make_reader_error_listener(
            McComp_ErrorListener, 'Component', comp_name, contents
        )
        tree = McComp_parse(InputStream(contents), 'prog', error_listener)
        # no need to call back to the reader, so we can use a dummy visitor
        visitor = CompVisitor(self.assembler.reader, __file__, instance_name=instance_name)
        res = visitor.visitProg(tree)
        self.assembler.reader.components[comp_name] = res
        return res

    def _parse_instr(self, contents: str):
        from antlr4 import InputStream
        from mccode_antlr.grammar import McInstr_parse
        from mccode_antlr.instr import InstrVisitor
        tree = McInstr_parse(InputStream(contents), 'prog')
        visitor = InstrVisitor(self.assembler.reader, 'no source')
        instr = visitor.visitProg(tree)
        instr.flags = tuple(self.assembler.reader.c_flags)
        instr.registries = tuple(self.assembler.reader.registries)
        return instr

    def _check_instr_0_properties(self, instr):
        from mccode_antlr.common.expression import DataType, ShapeType, Expr, Value
        self.assertEqual(len(instr.components), 2)
        self.assertEqual(instr.components[0].name, 'origin')
        self.assertEqual(instr.components[1].name, 'one')
        self.assertEqual(len(instr.components[1].parameters), 2)
        self.assertEqual(instr.components[1].parameters[1].name, 'easy_to_spot')
        value = instr.components[1].parameters[1].value
        self.assertEqual(value.shape_type, ShapeType.vector)
        self.assertEqual(value.data_type, DataType.float)
        self.assertTrue(value.is_vector)
        # Now weirdness
        self.assertTrue(isinstance(value, Expr))
        self.assertEqual(len(value.expr), 1)
        self.assertTrue(isinstance(value.expr[0], Value))
        #
        self.assertEqual(value.expr[0].value, "declared_array")
        # the _actual_ value is defined in the instrument declare section, we would need to compile the instrument
        # to access it -- this should be done later

    def _parse_instr_0(self):
        return self._parse_instr(INSTR_CONTENTS['test_vector_parameter'])

    def test_instr_0_parsed(self):
        self._check_instr_0_properties(self._parse_instr_0())

    def _assemble_instr_0(self):
        self.assembler.declare_array('double', 'declared_array', [1, 2, 3], source=__file__, line=1)
        self.assembler.component('origin', 'Arm', at=((0, 0, 0), 'absolute'))
        self.assembler.component('one', 'component_with_vector_parameter', at=((0, 0, 1), 'origin'),
                                 parameters=dict(n=3, easy_to_spot='declared_array'))
        return self.assembler.instrument

    def test_instr_0_assembled(self):
        self._check_instr_0_properties(self._assemble_instr_0())

    @compiled_test
    def test_parsed_instr_0_compiled(self):
        easy_to_spot = self._compile_and_run(self._parse_instr_0(), '')
        self.assertEqual(easy_to_spot, [1, 2, 3])

    @compiled_test
    def test_assembled_instr_0_compiled(self):
        easy_to_spot = self._compile_and_run(self._assemble_instr_0(), '')
        self.assertEqual(easy_to_spot, [1, 2, 3])


if __name__ == '__main__':
    unittest.main()

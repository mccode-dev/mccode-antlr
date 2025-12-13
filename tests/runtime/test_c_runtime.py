import unittest
from textwrap import dedent
from mccode_antlr.loader import parse_mcstas_instr
from mccode_antlr.test import compiled_test, gpu_compiled_test


class CRuntimeTestCase(unittest.TestCase):
    def _do_trace_tests(self, with_acc):
        from mccode_antlr.utils import compile_and_run
        instr = parse_mcstas_instr(dedent(
            """\
            DEFINE INSTRUMENT test_component_traces_visited()
            TRACE
            COMPONENT a = Arm() AT (0, 0, 0) ABSOLUTE EXTEND %{printf("visited a\\n");%}
            COMPONENT b = Arm() AT (0, 0, 1) ABSOLUTE EXTEND %{printf("visited b\\n");%}
            END
            """)
        )
        #
        results, data = compile_and_run(instr, "-n 1", target={'acc': with_acc})
        lines = results.decode('utf-8').splitlines()
        self.assertEqual(1, sum(line == 'visited a' for line in lines))
        self.assertEqual(1, sum(line == 'visited b' for line in lines))

    @compiled_test
    def test_raytrace_traces_visited(self):
        self._do_trace_tests(with_acc=False)

    @gpu_compiled_test
    def test_funnel_raytrace_traces_visited(self):
        # The FUNNEL define is only followed if OpenACC is enabled :/
        # And real OpenACC can only be enabled if we have a GPU :(
        # But since we don't actually need ACC, we can force use of the normal compiler instead
        # Unfortunately the runtime still includes openacc.h, so we should not try to run this normally.
        from mccode_antlr.config import config
        config['acc'] = config['cc'].get(str)
        config['flags']['acc'] = config['flags']['cc'].get(str) + ' -DFUNNEL -DOPENACC -DGCCOFFLOAD'
        self._do_trace_tests(with_acc=True)

    def _do_jump_tests(self, contents: str, jumps: int):
        from mccode_antlr.utils import compile_and_run
        instr = parse_mcstas_instr(contents)
        results, data = compile_and_run(instr, f"-n 1 jumps={jumps}")
        lines = results.decode('utf-8').splitlines()
        self.assertEqual(jumps, sum(line.startswith('time=') for line in lines))
        times = [int(x.split('=')[-1]) for x in filter(lambda y: y.startswith('time='), lines)]
        self.assertEqual(((jumps + 1) * jumps) >> 1, sum(times))

    @compiled_test
    def test_jump_iterate(self):
        contents = dedent("""\
                          DEFINE INSTRUMENT test_jump_iterate(int jumps)
                          USERVARS %{int time;%}
                          TRACE
                          COMPONENT o = Arm() AT (0,0,0) ABSOLUTE EXTEND %{time=0;%}
                          COMPONENT a = Arm() AT (0,0,0) ABSOLUTE EXTEND %{time+=1;%}
                          COMPONENT b = Arm() AT (0,0,1) ABSOLUTE EXTEND %{printf("time=%d\\n", time);%}
                          COMPONENT c = Arm() AT (0,0,2) ABSOLUTE JUMP a ITERATE jumps
                          END
                          """)
        self._do_jump_tests(contents, 10)

    @compiled_test
    def test_jump_when(self):
        contents = dedent("""\
                          DEFINE INSTRUMENT test_jump_when(int jumps)
                          USERVARS %{int time; int do_jump;%}
                          TRACE
                          COMPONENT o = Arm() AT (0,0,0) ABSOLUTE EXTEND %{time=0;%}
                          COMPONENT a = Arm() AT (0,0,0) ABSOLUTE EXTEND %{
                             time+=1;
                             do_jump = time < INSTRUMENT_GETPAR(jumps) ? 1 : 0;
                          %}
                          COMPONENT b = Arm() AT (0,0,1) ABSOLUTE EXTEND %{printf("time=%d\\n", time);%}
                          COMPONENT c = Arm() AT (0,0,2) ABSOLUTE JUMP a WHEN (do_jump)
                          END
                          """)
        self._do_jump_tests(contents, 100)

    @compiled_test
    def test_split(self):
        from mccode_antlr.utils import compile_and_run
        contents = dedent("""\
                          define instrument test_split(int splits) trace
                          component a = Arm() AT (0,0,0) ABSOLUTE EXTEND %{printf("a\\n");%}
                          split splits component b = Arm() at (0,0,0) absolute extend %{printf("b\\n");%}
                          split splits component c = Arm() at (0,0,0) absolute extend %{printf("c\\n");%}
                          end 
                          """)
        instr = parse_mcstas_instr(contents)
        splits = 10
        results, data = compile_and_run(instr, f"-n 1 splits={splits}")
        lines = results.decode('utf-8').splitlines()
        self.assertEqual(1, sum(line == 'a' for line in lines))
        self.assertEqual(splits, sum(line == 'b' for line in lines))
        self.assertEqual(splits*splits, sum(line == 'c' for line in lines))
        # The *order* of output is known as well:
        expected = ['a', *(['b', *(['c'] * splits)] * splits)]
        for ex, ln in zip(expected, lines):
            self.assertEqual(ex, ln)

    @compiled_test
    def test_when(self):
        from mccode_antlr.utils import compile_and_run
        instr = parse_mcstas_instr(dedent("""\
            define instrument test_when(dummy) 
            declare %{int count;%}
            initialize %{count = 0;%}
            trace
            component a = Arm() at (0,0,0) absolute extend %{++count;%}
            component b = Arm() when (count%2==1) at (0,0,0) absolute extend %{printf("count=%d\\n", count);%}
            end 
        """))
        n_max = 10
        results, data = compile_and_run(instr, f"-n {n_max} dummy=1")
        lines = results.decode('utf-8').splitlines()
        print(lines)
        expected = [f'count={x}' for x in range(1, n_max, 2)]
        for ex, ln in zip(expected, lines):
            self.assertEqual(ex, ln)

    @compiled_test
    def test_group(self):
        from mccode_antlr.utils import compile_and_run
        instr = parse_mcstas_instr(dedent("""\
            define instrument test_group(dummy)
            declare %{int count;%}
            initialize %{count = -1;%}
            trace
            component o = Arm() at (0,0,0) absolute extend %{++count;%}
            component a = Arm() when (count%4==0) at (0,0,0) absolute group first 
                          extend %{printf("a=%d\\n", count); SCATTER; %}
            component b = Arm() when (count%2==0) at (0,0,0) absolute group first 
                          extend %{printf("b=%d\\n", count);%}
            end 
        """))
        n_max = 10
        results, data = compile_and_run(instr, f"-n {n_max} dummy=1")
        lines = results.decode('utf-8').splitlines()
        print(lines)
        expected = [f'{"a" if x % 4 == 0 else "b"}={x}' for x in range(0, n_max, 2)]
        for ex, ln in zip(expected, lines):
            self.assertEqual(ex, ln)


if __name__ == '__main__':
    unittest.main()

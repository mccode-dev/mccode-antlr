from textwrap import dedent
from mccode_antlr.loader import parse_mcstas_instr
from mccode_antlr.test import gpu_compiled_test
from mccode_antlr.utils import compile_and_run
from mccode_antlr.reader.registry import InMemoryRegistry


# config['flags']['acc'] = "-lm -fast -Minfo=accel -acc=host -DOPENACC -x c -D_POSIX_C_SOURCE=2"


class Capturing(list):
    def __enter__(self):
        from io import StringIO
        import sys
        self._stdout = sys.stdout
        sys.stdout = self._stringio = StringIO()
        return self

    def __exit__(self, *args):
        import sys
        self.extend(self._stringio.getvalue().splitlines())
        del self._stringio  # free up some memory
        sys.stdout = self._stdout


def instrument_translation_prints_funnel(instr):
    import re
    from mccode_antlr.compiler.c import instrument_source
    from mccode_antlr import Flavor
    # Check that the McStas-parsing of the instrument prints '-DFUNNEL' to STDOUT
    with Capturing() as output:
        instrument_source(instr, Flavor.MCSTAS, {}, False)

    flags_line = re.compile('^CFLAGS=.*$')

    return any('-DFUNNEL' in line for line in output if flags_line.match(line))


FAKE_COMPONENTS = dict(
    with_noacc=dedent("""DEFINE COMPONENT with_noacc
    SETTING PARAMETERS (int n)
    NOACC
    TRACE
    %{
      for (int i= 0; i < n; i++) {
        printf("%d\\n", i);
      }
    %}
    END
    """),
    without_noacc=dedent("""DEFINE COMPONENT without_noacc
    SETTING PARAMETERS (int n)
    TRACE
    %{
      double store = 3.14159;
      for (int i = 0; i < n; i++) {
        store /= 2.0;
      }
    %}
    END
    """),
)


in_memory = InMemoryRegistry("test_components")
for comp, repr in FAKE_COMPONENTS.items():
    in_memory.add_comp(comp, repr)


@gpu_compiled_test
def test_simple_acc():
    instr = parse_mcstas_instr(dedent("""
    define instrument test_simple_acc(dummy=0.)
    trace
    component origin = without_noacc() at (0, 0, 0) absolute
    end
    """), registries=[in_memory])
    assert not instrument_translation_prints_funnel(instr)
    compile_and_run(instr, '-n 1 dummy=2', target={'acc': True})


@gpu_compiled_test
def test_cpu_only_instance():
    instr = parse_mcstas_instr(dedent("""
    define instrument test_cpu_only_instance(dummy=0.)
    trace
    component origin = without_noacc() at (0, 0, 0) absolute
    cpu component ordered = without_noacc() at (0, 0, 1) absolute
    component disordered = without_noacc() at (0, 0, 2) absolute
    end
    """), registries=[in_memory])
    assert instrument_translation_prints_funnel(instr)
    compile_and_run(instr, '-n 1 dummy=2', target={'acc': True})



@gpu_compiled_test
def test_noacc_component():
    instr = parse_mcstas_instr(dedent("""
    define instrument test_noacc_instance(dummy=0.)
    trace
    component origin = without_noacc() at (0, 0, 0) absolute
    component ordered = with_noacc() at (0, 0, 1) absolute
    end
    """), registries=[in_memory])
    assert instrument_translation_prints_funnel(instr)
    compile_and_run(instr, '-n 1 dummy=2', target={'acc': True})


@gpu_compiled_test
def test_cpu_and_noacc_component():
    instr = parse_mcstas_instr(dedent("""
    define instrument test_cpu_and_noacc_component(dummy=0.)
    trace
    component origin = without_noacc() at (0, 0, 0) absolute
    cpu component ordered = with_noacc() at (0, 0, 1) absolute
    end
    """), registries=[in_memory])
    assert instrument_translation_prints_funnel(instr)
    compile_and_run(instr, '-n 1 dummy=2', target={'acc': True})



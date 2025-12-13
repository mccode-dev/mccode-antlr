from textwrap import dedent
from mccode_antlr.loader import parse_mcstas_instr
from mccode_antlr.test import compiled_test
from mccode_antlr.utils import compile_and_run
from mccode_antlr.reader.registry import InMemoryRegistry


FAKE_COMPONENTS = dict(
    n_part=dedent("""DEFINE COMPONENT n_part
    SETTING PARAMETERS (int n)
    TRACE
    %{
      for (int i= 0; i < n; i++) {
        printf("n=%d\\n", i);
      }
    %}
    END
    """),
    m_part=dedent("""DEFINE COMPONENT m_part
    SETTING PARAMETERS (int m)
    TRACE
    %{
      for (int i = 0; i < m; i++) {
        printf("m=%d\\n", i);
      }
    %}
    END
    """),
    both_parts=dedent("""DEFINE COMPONENT both_parts
    SETTING PARAMETERS (int n, int m)
    TRACE INHERIT n_part INHERIT m_part
    END
    """),
    crazy=dedent("""DEFINE COMPONENT crazy
    SETTING PARAMETERS (int n, int m, int k)
    TRACE %{
    printf("We can do anything\\n");
    %}
    inherit n_part 
    EXTEND %{
    printf("Why!?\\n"); 
    %}
    inherit m_part
    EXTEND %{
    printf("Because we can!\\n"); 
    %}
    END"""),
)


in_memory = InMemoryRegistry("test_components")
for comp, repr in FAKE_COMPONENTS.items():
    in_memory.add_comp(comp, repr)


@compiled_test
def test_n_part():
    instr = parse_mcstas_instr(dedent("""
    define instrument test_n_part(dummy=0.)
    trace
    component origin = n_part(n=1) at (0, 0, 0) absolute
    end
    """), registries=[in_memory])
    output, files = compile_and_run(instr, '-n 1 dummy=2')
    lines = output.decode('utf-8').splitlines()
    for line, expected in zip(lines, ("n=0",)):
        assert line.strip() == expected.strip()


@compiled_test
def test_m_part():
    instr = parse_mcstas_instr(dedent("""
    define instrument test_m_part(dummy=0.)
    trace
    component origin = m_part(m=2) at (0, 0, 0) absolute
    end
    """), registries=[in_memory])
    output, files = compile_and_run(instr, '-n 1 dummy=2')
    lines = output.decode('utf-8').splitlines()
    for line, expected in zip(lines, ("m=0", "m=1")):
        assert line.strip() == expected.strip()


@compiled_test
def test_both_parts():
    instr = parse_mcstas_instr(dedent("""
    define instrument test_both_parts(dummy=0.)
    trace
    component origin = both_parts(n=3, m=2) at (0, 0, 0) absolute
    end
    """), registries=[in_memory])
    output, files = compile_and_run(instr, '-n 1 dummy=2')
    lines = output.decode('utf-8').splitlines()
    for line, expected in zip(lines, ("n=0", "n=1", "n=2", "m=0", "m=1")):
        assert line.strip() == expected.strip()


@compiled_test
def test_crazy_parts():
    instr = parse_mcstas_instr(dedent("""
    define instrument test_crazy(dummy=0.)
    trace
    component origin = crazy(n=3, m=2, k=0) at (0, 0, 0) absolute
    end
    """), registries=[in_memory])
    output, files = compile_and_run(instr, '-n 1 dummy=2')
    lines = output.decode('utf-8').splitlines()
    for line, expected in zip(lines, ("We can do anything", "n=0", "n=1", "n=2", "Why!?", "m=0", "m=1", "Because we can!")):
        assert line.strip() == expected.strip()
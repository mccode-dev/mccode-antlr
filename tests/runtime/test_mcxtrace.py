from textwrap import dedent
from mccode_antlr.loader import parse_mcstas_instr, parse_mcxtrace_instr
from mccode_antlr.test import compiled_test
from mccode_antlr.utils import compile_and_run, Flavor
from mccode_antlr.reader.registry import InMemoryRegistry

in_memory = InMemoryRegistry(
    "test_components",
    calls_restore_xray=dedent("""DEFINE COMPONENT calls_restore_xray
    SETTING PARAMETERS (int n)
    TRACE %{
    RESTORE_XRAY(INDEX_CURRENT_COMP, x, y, z, kx, ky, kz, phi, t, Ex, Ey, Ez, p);
    %}
    END
    """),
    calls_restore_neutron=dedent("""DEFINE COMPONENT calls_restore_neutron
    SETTING PARAMETERS (int n)
    TRACE %{
    RESTORE_NEUTRON(INDEX_CURRENT_COMP, x, y, z, vx, vy, vz, t, sx, sy, sz, p);
    %}
    END
    """),
    useless=dedent("""DEFINE COMPONENT useless
    SETTING PARAMETERS (int n)
    TRACE 
    %{
    %}
    END
    """),
)


@compiled_test
def test_simplest_mcstas():
    instr = parse_mcstas_instr(dedent("""
    define instrument test_simplest_mcstas(dummy=0.)
    trace component origin = useless() at (0, 0, 0) absolute end
    """), registries=[in_memory])
    compile_and_run(instr, '-n 1 dummy=2', flavor=Flavor.MCSTAS)


@compiled_test
def test_simplest_mcxtrace():
    instr = parse_mcxtrace_instr(dedent("""
    define instrument test_simplest_mcxtrace(dummy=0.)
    trace component origin = useless() at (0, 0, 0) absolute end
    """), registries=[in_memory])
    compile_and_run(instr, '-n 1 dummy=2', flavor=Flavor.MCXTRACE)


@compiled_test
def test_restore_neutron():
    instr = parse_mcstas_instr(dedent("""
    define instrument test_restore_neutron(dummy=0.)
    trace component origin = calls_restore_neutron() at (0, 0, 0) absolute end
    """), registries=[in_memory])
    compile_and_run(instr, '-n 1 dummy=2', flavor=Flavor.MCSTAS)

@compiled_test
def test_restore_xray():
    instr = parse_mcxtrace_instr(dedent("""
    define instrument test_restore_xray(dummy=0.)
    trace component origin = calls_restore_xray() at (0, 0, 0) absolute end
    """), registries=[in_memory])
    compile_and_run(instr, '-n 1 dummy=2', flavor=Flavor.MCXTRACE)
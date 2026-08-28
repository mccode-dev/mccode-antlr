from textwrap import dedent
from mccode_antlr.loader import parse_mcstas_instr
from mccode_antlr.test import compiled_test
from mccode_antlr.utils import compile_and_run
from mccode_antlr.reader.registry import InMemoryRegistry


FAKE_COMPONENTS = dict(
    check_for_define=dedent(r"""DEFINE COMPONENT check_for_define
    SETTING PARAMETERS (int n)
    TRACE
    %{
    #ifdef UNUSUAL_MACRO
    printf("UNUSUAL_MACRO set\n");
    #else
    printf("UNUSUAL_MACRO not set\n");
    #endif
    %}
    END
    """),
    check_for_nexus=dedent(r"""DEFINE COMPONENT check_for_nexus
    SETTING PARAMETERS (int n)
    TRACE
    %{
    %}
    END
    """),
    no_default_string_parameter=dedent(r"""DEFINE COMPONENT no_default_string_parameter
    SETTING PARAMETERS (string filename)
    TRACE
    %{
    %}
    END
    """),
)


def macro_name():
    from platform import system
    return "/DUNUSUAL_MACRO" if system() == "Windows" else "-DUNUSUAL_MACRO"


in_memory = InMemoryRegistry("test_components")
for comp, repr in FAKE_COMPONENTS.items():
    in_memory.add_comp(comp, repr)


@compiled_test
def test_instr_dependency():
    instr = parse_mcstas_instr(dedent(f"""
    define instrument test_instr_dependency(dummy=0.)
    DEPENDENCY "{macro_name()}"
    trace
    component origin = check_for_define() at (0, 0, 0) absolute
    end
    """), registries=[in_memory])
    assert any(macro_name() == x for x in instr.dependency)
    results, data = compile_and_run(instr, '-n 1 dummy=2')
    lines = results.decode('utf-8').splitlines()
    assert sum('UNUSUAL_MACRO set' == x for x in lines) == 1
    assert sum('UNUSUAL_MACRO not set' == x for x in lines) == 0


@compiled_test
def test_instr_no_dependency():
    instr = parse_mcstas_instr(dedent("""
    define instrument test_instr_no_dependency(dummy=0.)
    trace
    component origin = check_for_define() at (0, 0, 0) absolute
    end
    """), registries=[in_memory])
    assert not any(macro_name() == x for x in instr.dependency)
    results, data = compile_and_run(instr, '-n 1 dummy=2')
    lines = results.decode('utf-8').splitlines()
    assert sum('UNUSUAL_MACRO set' == x for x in lines) == 0
    assert sum('UNUSUAL_MACRO not set' == x for x in lines) == 1


def test_nexus_key_is_expanded():
    from mccode_antlr.config import config
    instr = parse_mcstas_instr(dedent("""
       define instrument test_nexus_key_is_expanded(dummy=0.)
       DEPENDENCY "@NEXUSFLAGS@"
       trace
       component origin = check_for_nexus() at (0, 0, 0) absolute
       end
       """), registries=[in_memory])
    assert any('@NEXUSFLAGS@' == x for x in instr.dependency)
    assert not any('@NEXUSFLAGS@' == x for x in instr.decoded_flags())
    nexus_flags = config['flags']['nexus'].get()
    assert any(nexus_flags == x for x in instr.decoded_flags())


def test_no_default_string_parameter_component_is_compilable():
    from mccode_antlr.translators.c import CTargetVisitor
    from mccode_antlr import Flavor
    instr = parse_mcstas_instr(dedent("""define instrument
    uses_no_default_string_parameter (string filename="some_file.txt")
    DEPENDENCY "@NEXUSFLAGS@"
    trace
    component origin = no_default_string_parameter(filename=filename) at (0, 0, 0) absolute
    end
    """), registries=[in_memory])

    config = dict(
        default_main=True,
        enable_trace=True,
        portable=True,
        include_runtime=True,
        embed_instrument_file=False,
        verbose=False,
        output=f'{instr.name if instr.name else "none"}.c')

    # Construct the object which will translate the Python instrument to C
    visitor = CTargetVisitor(instr, flavor=Flavor.MCSTAS, config=config, verbose=False, debug=False)
    # Go through the instrument, finish by collecting the C file contents:
    c_program = visitor.contents()

    bad_output = '"filename", , _instrument_var._parameters.filename'
    good_output = '"filename", "NONE", _instrument_var._parameters.filename'
    assert bad_output not in c_program
    assert good_output in c_program

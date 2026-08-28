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
    boring=dedent("""DEFINE COMPONENT boring
    SETTING PARAMETERS (int n)
    DECLARE %{
    char buffer[10];
    %}
    INITIALIZE %{
    strcpy(buffer, "boring");
    %}
    TRACE %{
    printf("I'm the %s component with n=%d\\n", buffer, n);
    %}
    END
    """),
    exciting=dedent("""DEFINE COMPONENT exciting INHERIT boring
    INITIALIZE %{
    strcpy(buffer, "exciting");
    %}
    END
    """),
)


in_memory = InMemoryRegistry("test_components")
for comp, representation in FAKE_COMPONENTS.items():
    in_memory.add_comp(comp, representation)


# --- issue #321: `DEFINE COMPONENT b INHERIT a` + section-level INHERIT/EXTEND ---
# Mirrors the shape of the upstream StatisticalChopper_Monitor.comp: the whole
# definition is inherited AND several sections are individually inherited,
# inherited-and-extended, or replaced outright. Before the fix each inherited
# section was appended on top of the whole-definition copy, doubling it, and the
# duplicated declarations broke the C compile.
INHERIT_321 = dict(
    ancestor_321=dedent("""DEFINE COMPONENT ancestor_321
    SETTING PARAMETERS (int reps=1)
    DECLARE %{
    int counter_321;
    %}
    INITIALIZE %{
    char tmp_321[32];
    counter_321 = 0;
    strcpy(tmp_321, "a");
    %}
    TRACE %{
    counter_321++;
    %}
    SAVE %{
    printf("ancestor_321 save\\n");
    %}
    END
    """),
    descendant_321=dedent("""DEFINE COMPONENT descendant_321 INHERIT ancestor_321
    DECLARE INHERIT ancestor_321
    INITIALIZE INHERIT ancestor_321 EXTEND %{
    counter_321 = 10;
    %}
    TRACE %{
    counter_321 += 2;
    %}
    END
    """),
)
for comp, representation in INHERIT_321.items():
    in_memory.add_comp(comp, representation)


def _drop_component_json_cache():
    """The component parser has a disk JSON cache keyed only on the .comp mtime;
    a stale entry from a previous (pre-fix) parse would mask the behaviour under
    test. Flush the in-memory level and delete the JSON sidecars in this
    registry's materialised tree."""
    from mccode_antlr.reader.reader import component_cache
    component_cache.clear()
    for name in list(FAKE_COMPONENTS) + list(INHERIT_321):
        in_memory.path(f'{name}.comp').with_suffix('.comp.json').unlink(missing_ok=True)


def test_inherit_definition_plus_section_inherit_does_not_duplicate_blocks():
    _drop_component_json_cache()
    instr = parse_mcstas_instr(dedent("""define instrument test_inherit_321(dummy=0.)
    trace
    component origin = descendant_321(reps=1) at (0, 0, 0) absolute
    end
    """), registries=[in_memory])
    comp = instr.components[0].type
    # DECLARE INHERIT ancestor_321 -> exactly one copy, not the copy + the append
    assert len(comp.declare) == 1
    assert "\n".join(b.source for b in comp.declare).count("int counter_321;") == 1
    # INITIALIZE INHERIT ancestor_321 EXTEND %{...%} -> ancestor block + extension
    assert len(comp.initialize) == 2
    assert "\n".join(b.source for b in comp.initialize).count("char tmp_321[32];") == 1
    # bare TRACE %{...%} replaces the inherited trace
    assert len(comp.trace) == 1
    assert "counter_321++" not in "\n".join(b.source for b in comp.trace)
    # SAVE not mentioned -> inherited copy kept
    assert len(comp.save) == 1


@compiled_test
def test_inherit_duplicated_blocks_instrument_compiles():
    _drop_component_json_cache()
    from mccode_antlr.compiler.check import compiles
    instr = parse_mcstas_instr(dedent("""define instrument test_inherit_321_compiles(dummy=0.)
    trace
    component origin = descendant_321(reps=1) at (0, 0, 0) absolute
    end
    """), registries=[in_memory])
    # pre-fix: C compiler fails with "redeclaration of 'tmp_321'"
    compiles('cc', instr)


@compiled_test
def test_statistical_chopper_monitor_compiles():
    """Issue #321: the upstream StatisticalChopper_Monitor.comp is the only
    component combining `DEFINE COMPONENT ... INHERIT ...` with section-level
    `SECTION INHERIT ...`, `... EXTEND`, and bare replacement. Before the block
    override fix its inherited DECLARE/INITIALIZE/TRACE were doubled and the
    generated C failed to compile."""
    from mccode_antlr.reader.reader import component_cache
    component_cache.clear()
    from mccode_antlr.compiler.check import compiles
    instr = parse_mcstas_instr(dedent("""DEFINE INSTRUMENT test_sc_monitor(lambda=1)
    TRACE
    COMPONENT origin = Progress_bar() AT (0, 0, 0) ABSOLUTE
    COMPONENT src = Source_simple(xwidth=0.026, yheight=0.026, lambda0=lambda,
      dlambda=0.001, focus_xw=0.005, focus_yh=0.05, dist=1.2) AT (0, 0, 0.001) RELATIVE PREVIOUS
    COMPONENT chop1 = StatisticalChopper(nu=350, verbose=0) AT (0, 0, 1) RELATIVE PREVIOUS
    COMPONENT mon = StatisticalChopper_Monitor(
      options="banana time limits=[-0.002 0.004] bins=100, y bins=10",
      radius=2, yheight=0.11, comp="chop1", restore_neutron=1) AT (0, 0, 0.1) RELATIVE PREVIOUS
    END
    """))
    compiles('cc', instr)


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


@compiled_test
def test_inherit_component_definition():
    instr = parse_mcstas_instr(
        dedent("""define instrument test_inherit_component_definition(dummy=0.)
        trace
        component first = boring(n=10) at (0, 0, 0) absolute
        component second = exciting(n=121) at (0, 0, 0) absolute
        end
        """), registries=[in_memory])
    output, files = compile_and_run(instr, '-n 1 dummy=2')
    lines = output.decode('utf-8').splitlines()
    boring_says = "I'm the boring component with n=10"
    exciting_says = "I'm the exciting component with n=121"
    for line, expected in zip(lines, (boring_says, exciting_says)):
        assert line.strip() == expected.strip()

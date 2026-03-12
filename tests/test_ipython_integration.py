from __future__ import annotations

from textwrap import dedent

from IPython.core.completer import CompletionContext, IPCompleter, provisionalcompleter

from mccode_antlr import Flavor
from mccode_antlr.assembler import Assembler
from mccode_antlr.integrations.ipython import (
    McCodeIPythonMatcher,
    load_ipython_extension,
    register_ipython_matcher,
    unload_ipython_extension,
)
from mccode_antlr.loader import parse_mcstas_instr
from mccode_antlr.reader.registry import InMemoryRegistry
from mccode_antlr.run import McStas


COMPONENTS = InMemoryRegistry(
    'ipython-components',
    Source_simple=dedent("""\
    DEFINE COMPONENT Source_simple
    DEFINITION PARAMETERS (double E0 = 5.0)
    SETTING PARAMETERS (double radius = 0.1, string filename = "source.dat")
    TRACE
    %{
    %}
    END
    """),
    Monitor_nD=dedent("""\
    DEFINE COMPONENT Monitor_nD
    DEFINITION PARAMETERS (double xmin = -0.1, double xmax = 0.1)
    SETTING PARAMETERS (string options = "x y", string filename = "det.dat")
    TRACE
    %{
    %}
    END
    """),
)




class _FakeMagicsManager:
    def lsmagic(self):
        return {'line': [], 'cell': []}

class _FakeCompleter:
    def __init__(self):
        self.custom_matchers = []


class _FakeShell:
    def __init__(self, **user_ns):
        self.user_ns = user_ns
        self.user_global_ns = {}
        self.magics_manager = _FakeMagicsManager()
        self.Completer = _FakeCompleter()


def _labels(result) -> list[str]:
    return [completion.text for completion in result['completions']]


def _ctx(text: str) -> CompletionContext:
    cursor = len(text)
    line = text.count('\n')
    token = text.split()[-1] if text.split() else ''
    return CompletionContext(
        token=token,
        full_text=text,
        cursor_position=cursor,
        cursor_line=line,
        limit=None,
    )


def test_component_type_completion_for_positional_argument():
    assembler = Assembler('Test', registries=[COMPONENTS], flavor=Flavor.MCSTAS)
    matcher = McCodeIPythonMatcher(shell=_FakeShell(a=assembler))

    result = matcher(_ctx('a.component("src", "Mon'))

    labels = _labels(result)
    assert 'Monitor_nD' in labels
    assert 'Source_simple' not in labels


def test_component_type_completion_for_keyword_argument():
    assembler = Assembler('Test', registries=[COMPONENTS], flavor=Flavor.MCSTAS)
    matcher = McCodeIPythonMatcher(shell=_FakeShell(a=assembler))

    result = matcher(_ctx('a.component("src", type_name="Sou'))

    assert 'Source_simple' in _labels(result)


def test_component_parameter_completion_inside_parameters_dict():
    assembler = Assembler('Test', registries=[COMPONENTS], flavor=Flavor.MCSTAS)
    matcher = McCodeIPythonMatcher(shell=_FakeShell(a=assembler))

    result = matcher(_ctx('a.component("src", "Source_simple", parameters={"fi'))

    labels = _labels(result)
    assert 'filename' in labels
    assert 'radius' not in labels


def test_simulation_instrument_parameter_completion_inside_run_dict():
    instr = parse_mcstas_instr(dedent("""\
        DEFINE INSTRUMENT test_instr(double value = 1.0, int n = 2)
        TRACE
        COMPONENT origin = Arm() AT (0, 0, 0) ABSOLUTE
        END
    """))
    simulation = McStas(instr)
    matcher = McCodeIPythonMatcher(shell=_FakeShell(sim=simulation))

    result = matcher(_ctx('sim.run({"va'))

    assert 'value' in _labels(result)


def test_simulation_runtime_keyword_completion():
    instr = parse_mcstas_instr(dedent("""\
        DEFINE INSTRUMENT test_instr(double value = 1.0)
        TRACE
        COMPONENT origin = Arm() AT (0, 0, 0) ABSOLUTE
        END
    """))
    simulation = McStas(instr)
    matcher = McCodeIPythonMatcher(shell=_FakeShell(sim=simulation))

    result = matcher(_ctx('sim.run(nc'))

    assert 'ncount=' in _labels(result)


def test_register_ipython_matcher_appends_once():
    shell = _FakeShell()

    first = register_ipython_matcher(shell=shell)
    second = register_ipython_matcher(shell=shell)

    assert first.matcher_identifier == second.matcher_identifier
    assert len(shell.Completer.custom_matchers) == 1
    assert shell.Completer.custom_matchers[0].matcher_identifier == 'mccode_antlr.ipython'


def test_load_and_unload_ipython_extension():
    shell = _FakeShell()

    matcher = load_ipython_extension(shell)
    assert matcher.matcher_identifier == 'mccode_antlr.ipython'
    assert len(shell.Completer.custom_matchers) == 1

    unload_ipython_extension(shell)
    assert shell.Completer.custom_matchers == []


def test_real_ipython_completer_pipeline_for_component_strings():
    assembler = Assembler('Test', registries=[COMPONENTS], flavor=Flavor.MCSTAS)

    class _PipelineShell:
        def __init__(self):
            self.user_ns = {'a': assembler}
            self.user_global_ns = {}
            self.magics_manager = _FakeMagicsManager()
            self.Completer = IPCompleter(shell=self)

    shell = _PipelineShell()
    register_ipython_matcher(shell=shell)

    with provisionalcompleter():
        completions = list(shell.Completer.completions("a.component('blah', '", len("a.component('blah', '")))

    labels = [completion.text for completion in completions]
    assert 'Monitor_nD' in labels
    assert 'Source_simple' in labels



def test_component_reference_completion_inside_at_tuple():
    assembler = Assembler('Test', registries=[COMPONENTS], flavor=Flavor.MCSTAS)
    assembler.component('Origin', 'Source_simple', at=(0, 0, 0))
    assembler.component('Guide', 'Monitor_nD', at=((0, 0, 1), 'Origin'))
    matcher = McCodeIPythonMatcher(shell=_FakeShell(a=assembler))

    result = matcher(_ctx('a.component("New", "Monitor_nD", at=((0, 0, 1), "Or'))

    labels = _labels(result)
    assert 'Origin' in labels
    assert 'Guide' not in labels


def test_component_reference_completion_inside_rotate_tuple():
    assembler = Assembler('Test', registries=[COMPONENTS], flavor=Flavor.MCSTAS)
    assembler.component('Origin', 'Source_simple', at=(0, 0, 0))
    assembler.component('Guide', 'Monitor_nD', at=((0, 0, 1), 'Origin'))
    matcher = McCodeIPythonMatcher(shell=_FakeShell(a=assembler))

    result = matcher(_ctx('a.component("New", "Monitor_nD", rotate=((0, 1, 0), "O'))

    assert 'Origin' in _labels(result)


def test_real_ipython_completer_pipeline_for_component_references():
    assembler = Assembler('Test', registries=[COMPONENTS], flavor=Flavor.MCSTAS)
    assembler.component('Origin', 'Source_simple', at=(0, 0, 0))

    class _PipelineShell:
        def __init__(self):
            self.user_ns = {'a': assembler}
            self.user_global_ns = {}
            self.magics_manager = _FakeMagicsManager()
            self.Completer = IPCompleter(shell=self)

    shell = _PipelineShell()
    register_ipython_matcher(shell=shell)

    text = 'a.component("New", "Monitor_nD", at=((0, 0, 1), "O'
    with provisionalcompleter():
        completions = list(shell.Completer.completions(text, len(text)))

    labels = [completion.text for completion in completions]
    assert 'Origin' in labels

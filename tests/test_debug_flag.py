"""--debug: #line directives, and how source locations are named in SIG_MESSAGE.

Without it the generated C must not depend on the machine that produced it, while
still naming a real file and line -- classic McCode reports neither, only the
component type and line 0.
"""
import pytest


INSTR = """DEFINE INSTRUMENT dbg()
TRACE
COMPONENT o = Progress_bar() AT (0,0,0) ABSOLUTE
END
"""


def _translate(tmp_path, **kwargs):
    from mccode_antlr import Flavor
    from mccode_antlr.loader import parse_mcstas_instr
    from mccode_antlr.translators.c import CTargetVisitor
    output = tmp_path / f'dbg{"-debug" if kwargs.get("debug") else ""}.c'
    instr = parse_mcstas_instr(INSTR)
    # Mirrors the CLI defaults. include_runtime matters here: without it the
    # runtime is referenced by `#include "<absolute path>"` rather than embedded,
    # and those paths are functional -- the C compiler has to resolve them.
    config = dict(default_main=True, enable_trace=True, portable=False,
                  include_runtime=True, embed_instrument_file=False, verbose=False,
                  output=str(output))
    visitor = CTargetVisitor(instr, flavor=Flavor.MCSTAS, config=config, **kwargs)
    visitor.save(filename=str(output))
    return output.read_text()


def _sig_locations(text):
    import re
    return re.findall(r'SIG_MESSAGE\("[^"]*\[([^\]"]*)\]"', text)


class TestDefault:
    def test_source_locations_are_registry_relative(self, tmp_path):
        locations = _sig_locations(_translate(tmp_path))
        comp = [x for x in locations if 'Progress_bar.comp' in x]
        assert comp, f'no Progress_bar location among {locations[:5]}'
        assert all(not x.startswith('/') for x in comp)
        assert any(x.startswith('mcstas-comps/') for x in comp)

    def test_a_real_line_number_is_kept(self, tmp_path):
        """Strictly more useful than classic McCode, which reports line 0."""
        locations = _sig_locations(_translate(tmp_path))
        comp = [x for x in locations if 'Progress_bar.comp' in x]
        assert any(int(x.rsplit(':', 1)[1]) > 0 for x in comp)

    def test_no_line_directives(self, tmp_path):
        assert '\n#line ' not in _translate(tmp_path)

    def test_only_the_data_root_remains_absolute(self, tmp_path):
        """#define MCSTAS is functional -- the binary uses it to find $MCSTAS/data."""
        text = _translate(tmp_path)
        absolute = [line for line in text.splitlines() if '/.cache/mccodeantlr' in line]
        assert all(line.lstrip().startswith('#define MCSTAS') for line in absolute), absolute[:3]


class TestDebug:
    def test_source_locations_are_absolute(self, tmp_path):
        locations = _sig_locations(_translate(tmp_path, debug=True))
        comp = [x for x in locations if 'Progress_bar.comp' in x]
        assert comp and all(x.startswith('/') for x in comp)

    def test_line_directives_are_emitted(self, tmp_path):
        assert '\n#line ' in _translate(tmp_path, debug=True)


class TestDeprecatedAlias:
    def test_line_directives_keyword_still_works_and_warns(self, tmp_path):
        from mccode_antlr.utils import McCodeAntlrDeprecationWarning
        with pytest.warns(McCodeAntlrDeprecationWarning, match='line_directives'):
            text = _translate(tmp_path, line_directives=True)
        assert '\n#line ' in text
        locations = _sig_locations(text)
        assert any(x.startswith('/') for x in locations if 'Progress_bar.comp' in x)

    def test_not_passing_it_does_not_warn(self, tmp_path, recwarn):
        from mccode_antlr.utils import McCodeAntlrDeprecationWarning
        _translate(tmp_path)
        assert not [w for w in recwarn if issubclass(w.category, McCodeAntlrDeprecationWarning)]


class TestShortening:
    def test_falls_back_to_the_bare_name_outside_every_registry(self):
        """Never leak an absolute path just because nothing matched."""
        from mccode_antlr import Flavor
        from mccode_antlr.translators.target import TargetVisitor

        class DummyInstr:
            name = 'dummy'
            registries = []
            components = []

            def verify_instance_parameters(self):
                return None

        visitor = TargetVisitor(DummyInstr(), Flavor.MCSTAS)
        assert visitor.display_source_path('/somewhere/else/Thing.comp') == 'Thing.comp'

    def test_debug_keeps_the_path_untouched(self):
        from mccode_antlr import Flavor
        from mccode_antlr.translators.target import TargetVisitor

        class DummyInstr:
            name = 'dummy'
            registries = []
            components = []

            def verify_instance_parameters(self):
                return None

        visitor = TargetVisitor(DummyInstr(), Flavor.MCSTAS, debug=True)
        assert visitor.display_source_path('/a/b/Thing.comp') == '/a/b/Thing.comp'

    def test_shortening_does_not_build_an_unused_registry_index(self):
        """Reading reg.pooch would fetch an index over the network purely to
        shorten a comment."""
        from mccode_antlr import Flavor
        from mccode_antlr.reader.registry import GitHubRegistry
        from mccode_antlr.translators.target import TargetVisitor

        unused = GitHubRegistry('unused', 'https://attacker.invalid/repo', 'v1',
                                filename='x.txt')

        class DummyInstr:
            name = 'dummy'
            registries = [unused]
            components = []

            def verify_instance_parameters(self):
                return None

        visitor = TargetVisitor(DummyInstr(), Flavor.MCSTAS)
        assert visitor.display_source_path('/a/b/Thing.comp') == 'Thing.comp'
        assert unused._pooch is None

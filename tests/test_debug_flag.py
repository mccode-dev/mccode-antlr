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
    return output.read_text(), visitor


def _sig_locations(text):
    import re
    return re.findall(r'SIG_MESSAGE\("[^"]*\[([^\]"]*)\]"', text)


def _slashes(text):
    r"""Separators as '/', whatever the platform and the C escaping.

    escape_str_for_c puts a path through unicode-escape, so a single backslash
    reaches the generated C doubled: 'C:\\Users\\...'.
    """
    return text.replace('\\\\', '/').replace('\\', '/')


def _is_absolute(location):
    """Whether a SIG_MESSAGE location names an absolute path, on any platform.

    Not `startswith('/')`: a Windows path is 'C:\\...', which that would call
    relative. The trailing ':<line>' is dropped first, and survives the drive
    colon because only the last colon is split on.
    """
    import re
    path = _slashes(location).rsplit(':', 1)[0]
    return path.startswith('/') or re.match(r'^[A-Za-z]:/', path) is not None


class TestPlatformHelpers:
    """The helpers above decide what the other tests mean, so they are checked
    against both platforms' shapes here -- only one of which CI can produce per
    run."""

    def test_posix_absolute(self):
        assert _is_absolute('/home/u/.cache/mccodeantlr/x/Progress_bar.comp:58')

    def test_windows_absolute_as_it_reaches_the_generated_c(self):
        assert _is_absolute(r'C:\\Users\\runneradmin\\AppData\\x\\Progress_bar.comp:58')

    def test_windows_absolute_unescaped(self):
        assert _is_absolute(r'C:\Users\runneradmin\x\Progress_bar.comp:58')

    def test_registry_relative_is_not_absolute(self):
        assert not _is_absolute('mcstas-comps/misc/Progress_bar.comp:58')

    def test_bare_name_is_not_absolute(self):
        assert not _is_absolute('Progress_bar.comp:58')

    def test_a_drive_letter_is_not_mistaken_for_a_line_number(self):
        assert _slashes(r'C:\\a\\b.comp') == 'C:/a/b.comp'


class TestDefault:
    def test_source_locations_are_registry_relative(self, tmp_path):
        text, _ = _translate(tmp_path)
        locations = _sig_locations(text)
        comp = [x for x in locations if 'Progress_bar.comp' in x]
        assert comp, f'no Progress_bar location among {locations[:5]}'
        assert not any(_is_absolute(x) for x in comp)
        # display_source_path uses as_posix(), so the separator is '/' either way
        assert any(_slashes(x).startswith('mcstas-comps/') for x in comp)

    def test_a_real_line_number_is_kept(self, tmp_path):
        """Strictly more useful than classic McCode, which reports line 0."""
        text, _ = _translate(tmp_path)
        comp = [x for x in _sig_locations(text) if 'Progress_bar.comp' in x]
        assert any(int(x.rsplit(':', 1)[1]) > 0 for x in comp)

    def test_no_line_directives(self, tmp_path):
        text, _ = _translate(tmp_path)
        assert '\n#line ' not in text

    def test_only_the_data_root_names_a_registry_directory(self, tmp_path):
        """#define MCSTAS is functional -- the binary uses it to find $MCSTAS/data.

        Compares against the registries' own base directories rather than a
        hardcoded cache path, which would never match on Windows and would let
        this pass without checking anything.
        """
        text, visitor = _translate(tmp_path)
        bases = [_slashes(str(b)) for b in visitor._registry_bases()]
        assert bases, 'no registry bases to compare against'
        naming = [line for line in text.splitlines()
                  if any(b in _slashes(line) for b in bases)]
        assert naming, 'expected at least the #define MCSTAS line to name one'
        assert all(x.lstrip().startswith('#define MCSTAS') for x in naming), naming[:3]


class TestDebug:
    def test_source_locations_are_absolute(self, tmp_path):
        text, _ = _translate(tmp_path, debug=True)
        locations = _sig_locations(text)
        comp = [x for x in locations if 'Progress_bar.comp' in x]
        assert comp and all(_is_absolute(x) for x in comp)

    def test_line_directives_are_emitted(self, tmp_path):
        text, _ = _translate(tmp_path, debug=True)
        assert '\n#line ' in text

    def test_debug_location_extends_the_default_one(self, tmp_path):
        """Ties the two modes together without asserting any path syntax."""
        plain, _ = _translate(tmp_path)
        debug, _ = _translate(tmp_path, debug=True)
        short = [x for x in _sig_locations(plain) if 'Progress_bar.comp' in x][0]
        full = [x for x in _sig_locations(debug) if 'Progress_bar.comp' in x][0]
        assert _slashes(full).endswith(_slashes(short))
        assert len(full) > len(short)


class TestDeprecatedAlias:
    def test_line_directives_keyword_still_works_and_warns(self, tmp_path):
        from mccode_antlr.utils import McCodeAntlrDeprecationWarning
        with pytest.warns(McCodeAntlrDeprecationWarning, match='line_directives'):
            text, _ = _translate(tmp_path, line_directives=True)
        assert '\n#line ' in text
        locations = _sig_locations(text)
        assert any(_is_absolute(x) for x in locations if 'Progress_bar.comp' in x)

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

"""Save-time capture of the local files an instrument needs.

Component definitions already travel in a serialized instrument. The files they
%include, and the data files they name, do not -- those are resolved from a
registry at translation time, so without capture an instrument saved on one
machine fails to translate on another.
"""
import pytest


@pytest.fixture
def local_tree(tmp_path):
    """A component in a search directory, whose SHARE block includes a library."""
    lib = tmp_path / 'lib'
    lib.mkdir()
    (lib / 'mylib.h').write_text('/* MYLIB SENTINEL */\ndouble mylib_helper(double x);\n')
    (lib / 'mylib.c').write_text('double mylib_helper(double x) { return 2.0 * x; }\n')
    (lib / 'UsesLib.comp').write_text(
        'DEFINE COMPONENT UsesLib\nSETTING PARAMETERS (thing=1)\n'
        'SHARE %{ %include "mylib" %}\nTRACE %{ SCATTER; %}\nEND\n'
    )
    instr = tmp_path / 'u.instr'
    instr.write_text(
        'DEFINE INSTRUMENT u()\nTRACE\n'
        'COMPONENT o = Progress_bar() AT (0,0,0) ABSOLUTE\n'
        'COMPONENT m = UsesLib(thing=3) AT (0,0,1) ABSOLUTE\nEND\n'
    )
    return tmp_path, lib, instr


def _read(lib, instr):
    from mccode_antlr import Flavor
    from mccode_antlr.reader import Reader
    from mccode_antlr.reader.registry import collect_local_registries
    reader = Reader(registries=collect_local_registries(Flavor.MCSTAS, [lib]))
    return reader.get_instrument(instr)


class TestCapture:
    def test_library_include_is_captured_as_both_h_and_c(self, local_tree):
        """The translator fetches {lib}.h, and {lib}.c when embedding the runtime."""
        from mccode_antlr.io.portable import embedded_registry
        _, lib, instr = local_tree
        captured = embedded_registry(_read(lib, instr))
        assert captured is not None
        assert set(captured.filenames()) == {'mylib.h', 'mylib.c'}
        assert 'MYLIB SENTINEL' in captured.contents('mylib.h')

    def test_nothing_captured_without_a_local_registry(self, local_tree):
        from mccode_antlr.io.portable import embedded_registry
        _, lib, instr = local_tree
        parsed = _read(lib, instr)
        parsed.registries = tuple(
            r for r in parsed.registries if type(r).__name__ != 'LocalRegistry')
        assert embedded_registry(parsed) is None

    def test_remote_files_are_not_embedded(self, local_tree):
        """Remote registry contents are reachable by name anywhere; copying them
        into every artifact would only bloat it."""
        from mccode_antlr.io.portable import embedded_registry
        _, lib, instr = local_tree
        captured = embedded_registry(_read(lib, instr))
        # Progress_bar and the runtime come from the remote registries
        assert not any('mccode-r' in n or 'Progress_bar' in n for n in captured.filenames())

    def test_transitive_includes_are_followed(self, local_tree):
        """A share library may %include further files."""
        from mccode_antlr.io.portable import embedded_registry
        _, lib, instr = local_tree
        (lib / 'deeper.h').write_text('/* DEEPER */\n')
        (lib / 'mylib.h').write_text('%include "deeper.h"\ndouble mylib_helper(double x);\n')
        captured = embedded_registry(_read(lib, instr))
        assert 'deeper.h' in captured.filenames()

    def test_size_limit_is_honoured(self, local_tree):
        from mccode_antlr.io.portable import embedded_registry
        _, lib, instr = local_tree
        (lib / 'mylib.h').write_text('/* pad */\n' + 'x' * 200000)
        captured = embedded_registry(_read(lib, instr), size_limit_mb=0.0001)
        assert captured is None or 'mylib.h' not in captured.filenames()

    def test_embedded_registry_ranks_below_search_dirs(self, local_tree):
        """A loading user's own -I must still win over what the artifact carries."""
        from mccode_antlr.io.portable import embedded_registry
        from mccode_antlr.reader.registry import REGISTRY_PRIORITY_HIGHEST
        _, lib, instr = local_tree
        captured = embedded_registry(_read(lib, instr))
        assert captured.priority < REGISTRY_PRIORITY_HIGHEST

    def test_captured_files_are_attributed_to_their_local_registry(self, local_tree):
        """Provenance for debugging a user-provided serialized instrument: each
        embedded file records which LocalRegistry supplied it, by name only --
        never the registry's filesystem root, so nothing about the saving
        machine's directory layout leaks into the artifact."""
        from mccode_antlr.io.portable import embedded_registry
        _, lib, instr = local_tree
        captured = embedded_registry(_read(lib, instr))
        assert captured.origins['mylib.h'] == f'local:{lib.stem}'
        assert captured.origins['mylib.c'] == f'local:{lib.stem}'
        assert str(lib) not in captured.origins['mylib.h']


class TestUnresolvableIncludes:
    """An %include that resolves nowhere is a translate-time error, but saving an
    instrument that does not yet translate is legitimate -- the file may appear
    before it is translated, or on the machine that translates it."""

    def _warnings(self, call):
        from loguru import logger
        messages = []
        sink = logger.add(lambda m: messages.append(str(m)), level='WARNING')
        try:
            result = call()
        finally:
            logger.remove(sink)
        return result, messages

    def _deferred(self, tmp_path):
        lib = tmp_path / 'lib'
        lib.mkdir()
        (lib / 'Deferred.comp').write_text(
            'DEFINE COMPONENT Deferred\nSHARE %{ %include "not_here_yet.h" %}\n'
            'TRACE %{ SCATTER; %}\nEND\n'
        )
        instr = tmp_path / 'u.instr'
        instr.write_text(
            'DEFINE INSTRUMENT u()\nTRACE\n'
            'COMPONENT o = Progress_bar() AT (0,0,0) ABSOLUTE\n'
            'COMPONENT d = Deferred() AT (0,0,1) ABSOLUTE\nEND\n'
        )
        return lib, instr

    def test_saving_still_succeeds(self, tmp_path):
        from mccode_antlr.io import to_json
        lib, instr = self._deferred(tmp_path)
        assert len(to_json(_read(lib, instr))) > 0

    def test_the_user_is_told_which_include_is_missing(self, tmp_path):
        from mccode_antlr.io import to_json
        lib, instr = self._deferred(tmp_path)
        _, messages = self._warnings(lambda: to_json(_read(lib, instr)))
        assert any('not_here_yet.h' in m for m in messages)

    def test_a_resolvable_instrument_is_quiet(self, local_tree):
        from mccode_antlr.io import to_json
        _, lib, instr = local_tree
        _, messages = self._warnings(lambda: to_json(_read(lib, instr)))
        assert not any('could not be resolved' in m for m in messages)

    def test_a_header_only_library_does_not_warn(self, tmp_path):
        """A bare %include pulls {name}.h and {name}.c, but only the header is
        required -- many libraries have no .c at all."""
        from mccode_antlr.io.portable import embedded_registry
        lib = tmp_path / 'lib'
        lib.mkdir()
        (lib / 'onlyh.h').write_text('/* HEADER ONLY */\n')
        (lib / 'HdrOnly.comp').write_text(
            'DEFINE COMPONENT HdrOnly\nSHARE %{ %include "onlyh" %}\n'
            'TRACE %{ SCATTER; %}\nEND\n'
        )
        instr = tmp_path / 'u.instr'
        instr.write_text(
            'DEFINE INSTRUMENT u()\nTRACE\n'
            'COMPONENT o = Progress_bar() AT (0,0,0) ABSOLUTE\n'
            'COMPONENT h = HdrOnly() AT (0,0,1) ABSOLUTE\nEND\n'
        )
        captured, messages = self._warnings(lambda: embedded_registry(_read(lib, instr)))
        assert captured.filenames() == ['onlyh.h']
        assert not any('could not be resolved' in m for m in messages)

    def test_output_filenames_are_not_reported_as_missing(self, local_tree):
        """Data-file candidates are heuristic: a string parameter ending in an
        extension is usually an *output* name, so it must never be reported."""
        from mccode_antlr.io.portable import embedded_registry
        _, lib, instr = local_tree
        instr.write_text(
            'DEFINE INSTRUMENT u()\nTRACE\n'
            'COMPONENT o = Progress_bar() AT (0,0,0) ABSOLUTE\n'
            'COMPONENT m = UsesLib(thing=3) AT (0,0,1) ABSOLUTE\n'
            'COMPONENT p = PSD_monitor(filename="never_going_to_exist.psd") '
            'AT (0,0,2) ABSOLUTE\nEND\n'
        )
        _, messages = self._warnings(lambda: embedded_registry(_read(lib, instr)))
        assert not any('never_going_to_exist' in m for m in messages)


class TestSerializedInstrument:
    def test_captured_files_reach_the_json(self, local_tree):
        from mccode_antlr.io import to_json
        from mccode_antlr.reader.registry import InMemoryRegistry
        from mccode_antlr.io.portable import EMBEDDED_REGISTRY_NAME
        from mccode_antlr.io import from_json
        _, lib, instr = local_tree
        back = from_json(to_json(_read(lib, instr)))
        embedded = [r for r in back.registries
                    if isinstance(r, InMemoryRegistry) and r.name == EMBEDDED_REGISTRY_NAME]
        assert len(embedded) == 1
        assert 'MYLIB SENTINEL' in embedded[0].contents('mylib.h')

    def test_captured_origin_survives_the_json_round_trip(self, local_tree):
        from mccode_antlr.io import to_json, from_json
        from mccode_antlr.reader.registry import InMemoryRegistry
        from mccode_antlr.io.portable import EMBEDDED_REGISTRY_NAME
        _, lib, instr = local_tree
        back = from_json(to_json(_read(lib, instr)))
        embedded = next(r for r in back.registries
                         if isinstance(r, InMemoryRegistry) and r.name == EMBEDDED_REGISTRY_NAME)
        assert embedded.origins['mylib.h'] == f'local:{lib.stem}'

    def test_origin_survives_repeated_saves(self, local_tree):
        """Carrying an embedded registry forward across saves (with_embedded_files)
        must not drop the origin recorded on the first save."""
        from mccode_antlr.io import to_json, from_json
        from mccode_antlr.reader.registry import InMemoryRegistry
        from mccode_antlr.io.portable import EMBEDDED_REGISTRY_NAME
        _, lib, instr = local_tree
        once = from_json(to_json(_read(lib, instr)))
        twice = from_json(to_json(once))
        embedded = next(r for r in twice.registries
                         if isinstance(r, InMemoryRegistry) and r.name == EMBEDDED_REGISTRY_NAME)
        assert embedded.origins['mylib.h'] == f'local:{lib.stem}'

    def test_disabled_by_configuration(self, local_tree, monkeypatch):
        from mccode_antlr.config import config
        from mccode_antlr.io import to_json, from_json
        from mccode_antlr.reader.registry import InMemoryRegistry
        _, lib, instr = local_tree
        config['serialization']['embed_local_files'] = False
        try:
            back = from_json(to_json(_read(lib, instr)))
        finally:
            config['serialization']['embed_local_files'] = True
        assert not any(isinstance(r, InMemoryRegistry) for r in back.registries)

    def test_capture_is_not_doubled_on_repeated_saves(self, local_tree):
        from mccode_antlr.io import to_json, from_json
        from mccode_antlr.reader.registry import InMemoryRegistry
        _, lib, instr = local_tree
        once = from_json(to_json(_read(lib, instr)))
        twice = from_json(to_json(once))
        embedded = [r for r in twice.registries if isinstance(r, InMemoryRegistry)]
        assert len(embedded) == 1

    def test_re_saving_a_loaded_instrument_keeps_its_files(self, local_tree, tmp_path):
        """The loaded instrument has no LocalRegistry left to capture from, so a
        fresh capture finds nothing; the carried files must survive anyway."""
        import shutil
        from mccode_antlr import Flavor
        from mccode_antlr.io import to_json, from_json
        from mccode_antlr.translators.c import CTargetVisitor
        _, lib, instr = local_tree
        once = from_json(to_json(_read(lib, instr)))
        blob = to_json(once)          # re-saved with the search directory gone from it
        shutil.rmtree(lib)
        output = tmp_path / 'twice.c'
        CTargetVisitor(from_json(blob), flavor=Flavor.MCSTAS,
                       config=dict(output=str(output))).save(filename=str(output))
        assert 'MYLIB SENTINEL' in output.read_text()

    def test_a_locally_edited_file_wins_over_the_carried_copy(self, local_tree):
        from mccode_antlr.io import to_json, from_json
        from mccode_antlr.io.portable import EMBEDDED_REGISTRY_NAME
        from mccode_antlr.reader.registry import InMemoryRegistry
        _, lib, instr = local_tree
        once = from_json(to_json(_read(lib, instr)))
        (lib / 'mylib.h').write_text('/* EDITED SENTINEL */\n')
        # re-read from the tree so a LocalRegistry is present again
        again = _read(lib, instr)
        again.registries = tuple(again.registries) + tuple(
            r for r in once.registries
            if isinstance(r, InMemoryRegistry) and r.name == EMBEDDED_REGISTRY_NAME)
        back = from_json(to_json(again))
        embedded = [r for r in back.registries if isinstance(r, InMemoryRegistry)][0]
        assert 'EDITED SENTINEL' in embedded.contents('mylib.h')


class TestEndToEnd:
    def test_translates_elsewhere_with_the_source_tree_gone(self, local_tree, tmp_path):
        """The whole point: save here, translate there, without the local files."""
        import shutil
        from mccode_antlr import Flavor
        from mccode_antlr.io import to_json, from_json
        from mccode_antlr.translators.c import CTargetVisitor
        _, lib, instr = local_tree
        blob = to_json(_read(lib, instr))

        shutil.rmtree(lib)  # the search directory no longer exists
        elsewhere = tmp_path / 'elsewhere'
        elsewhere.mkdir()
        output = elsewhere / 'out.c'

        loaded = from_json(blob)
        CTargetVisitor(loaded, flavor=Flavor.MCSTAS,
                       config=dict(output=str(output))).save(filename=str(output))
        generated = output.read_text()
        assert 'MYLIB SENTINEL' in generated
        assert 'mylib_helper(double x)' in generated

    def test_without_capture_the_same_case_fails(self, local_tree, tmp_path):
        """Guards the test above: it must be the capture doing the work."""
        import shutil
        from mccode_antlr import Flavor
        from mccode_antlr.config import config
        from mccode_antlr.io import to_json, from_json
        from mccode_antlr.translators.c import CTargetVisitor
        _, lib, instr = local_tree
        config['serialization']['embed_local_files'] = False
        try:
            blob = to_json(_read(lib, instr))
        finally:
            config['serialization']['embed_local_files'] = True

        shutil.rmtree(lib)
        with pytest.raises(RuntimeError, match='mylib'):
            CTargetVisitor(from_json(blob), flavor=Flavor.MCSTAS,
                           config=dict(output=str(tmp_path / 'no.c')))


class TestRuntimeDataFiles:
    """Embedding makes a data file reachable at *translation* time via reg.path(),
    which materializes into a cache directory. The compiled binary does not search
    there: Open_File tries the name as given, the instrument source directory, the
    executable's directory, $HOME, then $FLAVOR/data and $FLAVOR/contrib. So the
    file has to be deposited somewhere it will actually be found.
    """

    def _with_data(self, tmp_path):
        lib = tmp_path / 'lib'
        lib.mkdir()
        (lib / 'myrefl.dat').write_text('# local table\n0.0 1.0\n1.0 0.5\n')
        instr = tmp_path / 'u.instr'
        instr.write_text(
            'DEFINE INSTRUMENT u()\nTRACE\n'
            'COMPONENT o = Progress_bar() AT (0,0,0) ABSOLUTE\n'
            'COMPONENT g = Guide_gravity(w1=0.06,h1=0.12,l=1,m=4,reflect="myrefl.dat")'
            ' AT (0,0,1) ABSOLUTE\nEND\n'
        )
        return lib, instr

    def test_data_file_is_captured(self, tmp_path):
        from mccode_antlr.io.portable import embedded_registry
        lib, instr = self._with_data(tmp_path)
        captured = embedded_registry(_read(lib, instr))
        assert 'myrefl.dat' in captured.filenames()

    def test_deposited_beside_the_generated_c(self, tmp_path):
        import shutil
        from mccode_antlr import Flavor
        from mccode_antlr.io import to_json, from_json
        from mccode_antlr.translators.c import CTargetVisitor
        lib, instr = self._with_data(tmp_path)
        blob = to_json(_read(lib, instr))
        shutil.rmtree(lib)
        elsewhere = tmp_path / 'elsewhere'
        elsewhere.mkdir()
        output = elsewhere / 'out.c'
        CTargetVisitor(from_json(blob), flavor=Flavor.MCSTAS,
                       config=dict(output=str(output))).save(filename=str(output))
        assert (elsewhere / 'myrefl.dat').read_text().startswith('# local table')

    def test_deposit_targets_a_given_directory(self, tmp_path):
        """The compile path generates its source in memory, so it deposits beside
        the binary rather than beside any .c file."""
        from mccode_antlr.io import to_json, from_json
        from mccode_antlr.io.portable import deposit_embedded_data_files
        lib, instr = self._with_data(tmp_path)
        loaded = from_json(to_json(_read(lib, instr)))
        destination = tmp_path / 'bin'
        destination.mkdir()
        written = deposit_embedded_data_files(loaded, destination)
        assert [p.name for p in written] == ['myrefl.dat']

    def test_headers_are_not_deposited(self, local_tree):
        """Only files a parameter names; headers are compiled in, never opened."""
        from mccode_antlr.io import to_json, from_json
        from mccode_antlr.io.portable import deposit_embedded_data_files
        _, lib, instr = local_tree
        loaded = from_json(to_json(_read(lib, instr)))
        destination = instr.parent / 'bin'
        destination.mkdir()
        assert deposit_embedded_data_files(loaded, destination) == []

    def test_an_existing_different_file_is_not_overwritten(self, tmp_path):
        from mccode_antlr.io import to_json, from_json
        from mccode_antlr.io.portable import deposit_embedded_data_files
        lib, instr = self._with_data(tmp_path)
        loaded = from_json(to_json(_read(lib, instr)))
        destination = tmp_path / 'bin'
        destination.mkdir()
        (destination / 'myrefl.dat').write_text('the user has their own')
        assert deposit_embedded_data_files(loaded, destination) == []
        assert (destination / 'myrefl.dat').read_text() == 'the user has their own'

    def test_no_destination_is_a_no_op(self, tmp_path):
        from mccode_antlr.io import to_json, from_json
        from mccode_antlr.io.portable import deposit_embedded_data_files
        lib, instr = self._with_data(tmp_path)
        loaded = from_json(to_json(_read(lib, instr)))
        assert deposit_embedded_data_files(loaded, None) == []


class TestResolveRegistryAndPathStrictness:
    """A registry must not be credited with a name it only *contains* as a
    substring: 'ESS_butterfly.comp' is a literal substring of a real file,
    'Masked_ESS_butterfly.comp', in an unrelated registry. Trusting that match
    misattributes the genuinely-upstream ESS_butterfly component to whichever
    registry happens to hold a longer, colliding filename."""

    def _fake_remote(self, name, files):
        from types import SimpleNamespace
        from mccode_antlr.reader.registry import RemoteRegistry
        reg = RemoteRegistry(name, url='https://example.invalid/x', version='v1',
                              filename=f'{name}-registry.txt')
        reg._pooch = SimpleNamespace(registry_files=files, fetch=lambda n: n)
        return reg

    def test_a_substring_only_match_is_not_resolved(self):
        from mccode_antlr.io.portable import resolve_registry_and_path
        colliding = self._fake_remote('mcstas-chopper-lib', ['Masked_ESS_butterfly.comp'])
        reg, path = resolve_registry_and_path([colliding], 'ESS_butterfly.comp')
        assert reg is None
        assert path is None

    def test_an_exact_match_elsewhere_is_still_resolved(self):
        from mccode_antlr.io.portable import resolve_registry_and_path
        colliding = self._fake_remote('mcstas-chopper-lib', ['Masked_ESS_butterfly.comp'])
        exact = self._fake_remote('mcstas', ['ESS_butterfly.comp'])
        reg, _ = resolve_registry_and_path([colliding, exact], 'ESS_butterfly.comp')
        assert reg is exact


class TestIncludeResolutionWithoutDisk:
    """%include resolution asks registries for text, not a path.

    Requiring a path forces an in-memory registry to write itself out first, which
    is pointless when the caller only reads the file and discards the location.
    """

    def _materialized_count(self, instr):
        from mccode_antlr.reader.registry import InMemoryRegistry
        return sum(len(r._materialized) for r in instr.registries
                   if isinstance(r, InMemoryRegistry))

    def test_translation_materializes_nothing(self, local_tree, tmp_path):
        import shutil
        from mccode_antlr import Flavor
        from mccode_antlr.io import to_json, from_json
        from mccode_antlr.translators.c import CTargetVisitor
        _, lib, instr = local_tree
        blob = to_json(_read(lib, instr))
        shutil.rmtree(lib)
        elsewhere = tmp_path / 'elsewhere'
        elsewhere.mkdir()
        output = elsewhere / 'out.c'
        loaded = from_json(blob)
        CTargetVisitor(loaded, flavor=Flavor.MCSTAS,
                       config=dict(output=str(output))).save(filename=str(output))
        assert 'MYLIB SENTINEL' in output.read_text()
        assert self._materialized_count(loaded) == 0

    def test_file_text_prefers_contents_over_path(self, local_tree):
        from mccode_antlr import Flavor
        from mccode_antlr.io import to_json, from_json
        from mccode_antlr.translators.c import CTargetVisitor
        _, lib, instr = local_tree
        loaded = from_json(to_json(_read(lib, instr)))
        visitor = CTargetVisitor.__new__(CTargetVisitor)
        visitor.source = loaded
        assert 'MYLIB SENTINEL' in visitor.file_text('mylib.h')
        assert self._materialized_count(loaded) == 0

    def test_missing_name_still_reports_the_registries(self):
        import pytest
        from mccode_antlr import Flavor
        from mccode_antlr.loader import parse_mcstas_instr
        from mccode_antlr.translators.c import CTargetVisitor
        instr = parse_mcstas_instr(
            'DEFINE INSTRUMENT t()\nTRACE\n'
            'COMPONENT o = Progress_bar() AT (0,0,0) ABSOLUTE\nEND\n'
        )
        visitor = CTargetVisitor.__new__(CTargetVisitor)
        visitor.source = instr
        with pytest.raises(RuntimeError, match='not found in registr'):
            visitor.file_text('definitely_absent.h')

    def test_embedded_runtime_files_are_named_not_located(self):
        """embed_file and configure_file used to print the resolved absolute path
        into the generated C, so identical input produced different output on
        different machines. Upstream McCode emits no path either."""
        import re
        from io import StringIO
        from mccode_antlr import Flavor
        from mccode_antlr.translators.target import TargetVisitor

        class DummyInstr:
            name = 'dummy'
            registries = []
            components = []

            def verify_instance_parameters(self):
                return None

        class DummyVisitor(TargetVisitor):
            def file_text(self, name, which=None):
                return 'int body;\n'

        visitor = DummyVisitor(DummyInstr(), Flavor.MCSTAS)
        visitor.output = StringIO()
        visitor.embed_file('mccode-r.c')
        output = visitor.output.getvalue()
        assert '/* embedding file "mccode-r.c" */' in output
        assert '/* end of file "mccode-r.c" */' in output
        assert 'int body;' in output
        named = re.search(r'embedding file "([^"]*)"', output).group(1)
        # Both separators: a Windows path would contain '\', not '/'
        assert '/' not in named and '\\' not in named, named

    def test_falls_through_a_registry_that_cannot_deliver(self):
        """%include resolution was the last lookup still binding to the first
        registry whose known() answered True, even when it then failed."""
        from mccode_antlr import Flavor
        from mccode_antlr.reader.registry import InMemoryRegistry
        from mccode_antlr.translators.c import CTargetVisitor

        class _Broken:
            name = 'broken'
            root = None
            version = '0'
            priority = 20          # must outrank the working one to be tried first

            def known(self, name, ext=None, strict=False):
                return True

            def contents(self, name, ext=None):
                raise RuntimeError('deliberately broken')

        working = InMemoryRegistry('working', priority=0)
        working.add('mylib.h', '/* THE REAL ONE */\n')

        class DummyInstr:
            name = 'dummy'
            registries = [_Broken(), working]
            components = []

            def verify_instance_parameters(self):
                return None

        visitor = CTargetVisitor.__new__(CTargetVisitor)
        visitor.source = DummyInstr()
        assert 'THE REAL ONE' in visitor.file_text('mylib.h')

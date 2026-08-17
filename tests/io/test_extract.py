"""Reconstitute an Instr (with local dependencies) back onto disk, flat."""
import pytest


@pytest.fixture
def local_tree(tmp_path):
    """A local component whose SHARE block %includes a library, plus a remote one."""
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


class TestExtractToDirectory:
    def test_instr_file_is_written(self, local_tree, tmp_path):
        from mccode_antlr.io.extract import extract_to_directory
        _, lib, instr = local_tree
        out = tmp_path / 'out'
        extract_to_directory(_read(lib, instr), out)
        assert (out / 'u.instr').exists()

    def test_local_component_is_extracted_by_default(self, local_tree, tmp_path):
        from mccode_antlr.io.extract import extract_to_directory
        _, lib, instr = local_tree
        out = tmp_path / 'out'
        extract_to_directory(_read(lib, instr), out)
        assert 'DEFINE COMPONENT UsesLib' in (out / 'UsesLib.comp').read_text()

    def test_remote_component_is_excluded_by_default(self, local_tree, tmp_path):
        from mccode_antlr.io.extract import extract_to_directory
        _, lib, instr = local_tree
        out = tmp_path / 'out'
        extract_to_directory(_read(lib, instr), out)
        assert not (out / 'Progress_bar.comp').exists()

    def test_remote_component_is_included_with_flag(self, local_tree, tmp_path):
        from mccode_antlr.io.extract import extract_to_directory
        _, lib, instr = local_tree
        out = tmp_path / 'out'
        extract_to_directory(_read(lib, instr), out, include_remote=True)
        assert (out / 'Progress_bar.comp').exists()

    def test_local_dependency_files_are_extracted_flat(self, local_tree, tmp_path):
        from mccode_antlr.io.extract import extract_to_directory
        _, lib, instr = local_tree
        out = tmp_path / 'out'
        extract_to_directory(_read(lib, instr), out)
        assert 'MYLIB SENTINEL' in (out / 'mylib.h').read_text()
        assert (out / 'mylib.c').exists()

    def test_extraction_works_from_a_reloaded_json(self, local_tree, tmp_path):
        """The primary use case: extract from a portable .json whose LocalRegistry
        was dropped on load -- the embedded files must still make it out."""
        from mccode_antlr.io import to_json, from_json
        from mccode_antlr.io.extract import extract_to_directory
        _, lib, instr = local_tree
        loaded = from_json(to_json(_read(lib, instr)))
        out = tmp_path / 'out'
        extract_to_directory(loaded, out)
        assert 'MYLIB SENTINEL' in (out / 'mylib.h').read_text()
        assert 'DEFINE COMPONENT UsesLib' in (out / 'UsesLib.comp').read_text()

    def test_extracted_directory_is_self_sufficient(self, local_tree, tmp_path):
        """Re-reading the extracted .instr with no -I finds everything it needs
        from within the extracted directory alone -- the point of flattening."""
        import os
        import shutil
        from mccode_antlr import Flavor
        from mccode_antlr.reader import Reader
        from mccode_antlr.reader.registry import collect_local_registries
        from mccode_antlr.io.extract import extract_to_directory
        _, lib, instr = local_tree
        out = tmp_path / 'out'
        extract_to_directory(_read(lib, instr), out)
        shutil.rmtree(lib)
        cwd = os.getcwd()
        os.chdir(out)
        try:
            reader = Reader(registries=collect_local_registries(Flavor.MCSTAS, None))
            reloaded = reader.get_instrument(out / 'u.instr')
        finally:
            os.chdir(cwd)
        assert [c.name for c in reloaded.components] == ['o', 'm']

    def test_no_remote_dependency_files_without_the_flag(self, local_tree, tmp_path):
        from mccode_antlr.io.extract import extract_to_directory
        _, lib, instr = local_tree
        out = tmp_path / 'out'
        extract_to_directory(_read(lib, instr), out)
        assert not any('mccode-r' in p.name for p in out.iterdir())

    def test_select_extracts_only_matching_members(self, local_tree, tmp_path):
        from mccode_antlr.io.extract import extract_to_directory
        _, lib, instr = local_tree
        out = tmp_path / 'out'
        extract_to_directory(_read(lib, instr), out, select=['mylib.h'])
        assert {p.name for p in out.iterdir()} == {'mylib.h'}

    def test_select_bypasses_remote_gate(self, local_tree, tmp_path):
        """An explicitly named remote-sourced member is extracted even without include_remote."""
        from mccode_antlr.io.extract import extract_to_directory
        _, lib, instr = local_tree
        out = tmp_path / 'out'
        extract_to_directory(_read(lib, instr), out, select=['Progress_bar.comp'])
        assert {p.name for p in out.iterdir()} == {'Progress_bar.comp'}

    def test_exclude_omits_matches_from_default_sweep(self, local_tree, tmp_path):
        from mccode_antlr.io.extract import extract_to_directory
        _, lib, instr = local_tree
        out = tmp_path / 'out'
        extract_to_directory(_read(lib, instr), out, exclude=['*.h'])
        names = {p.name for p in out.iterdir()}
        assert 'mylib.h' not in names
        assert 'mylib.c' in names
        assert 'u.instr' in names

    def test_repository_filters_extraction(self, local_tree, tmp_path):
        """Repository filter extracts only that repository's files, remote-gate bypassed."""
        from mccode_antlr.io.extract import extract_to_directory
        _, lib, instr = local_tree
        out = tmp_path / 'out'
        extract_to_directory(_read(lib, instr), out, repository=['*/mccode-dev/*'])
        assert {p.name for p in out.iterdir()} == {'Progress_bar.comp'}


class TestBuildManifest:
    def test_categories_and_sources(self, local_tree):
        from mccode_antlr.io.extract import build_manifest
        _, lib, instr = local_tree
        by_name = {m.name: m for m in build_manifest(_read(lib, instr))}

        assert by_name['u.instr'].category == 'instr'
        assert by_name['u.instr'].source == 'generated'
        assert by_name['u.instr'].default_included is True
        assert by_name['u.instr'].repository == 'generated'
        assert by_name['u.instr'].repository_match == 'generated'

        assert by_name['mylib.h'].category == 'dependency'
        assert by_name['mylib.h'].source == 'local'
        assert by_name['mylib.h'].default_included is True
        assert by_name['mylib.h'].repository == lib.stem
        assert by_name['mylib.h'].repository_match == str(lib.resolve())

        assert by_name['UsesLib.comp'].category == 'component'
        assert by_name['UsesLib.comp'].source == 'local'
        assert by_name['UsesLib.comp'].default_included is True
        assert by_name['UsesLib.comp'].repository == lib.stem
        assert by_name['UsesLib.comp'].repository_match == str(lib.resolve())

        assert by_name['Progress_bar.comp'].category == 'component'
        assert by_name['Progress_bar.comp'].source == 'remote'
        assert by_name['Progress_bar.comp'].default_included is False
        assert by_name['Progress_bar.comp'].repository == 'mcstas'
        assert by_name['Progress_bar.comp'].repository_match.startswith('https://github.com/')

    def test_embedded_files_are_attributed_to_their_recorded_origin(self, local_tree):
        """Debugging payoff of provenance tracking: even when a user submits a
        serialized instrument with no trusted LocalRegistry, `-l`/build_manifest
        can still say which of the user's local directories a file came from --
        by name only, never the filesystem path (see io.portable._origin_label)."""
        from mccode_antlr.io import to_json, from_json
        from mccode_antlr.io.extract import build_manifest
        _, lib, instr = local_tree
        loaded = from_json(to_json(_read(lib, instr)))
        by_name = {m.name: m for m in build_manifest(loaded)}
        assert by_name['mylib.h'].source == 'embedded'
        assert by_name['mylib.h'].repository == f'local:{lib.stem}'
        assert by_name['mylib.h'].repository_match == f'local:{lib.stem}'

    def test_component_falls_back_to_recorded_origin_when_unresolvable(self, local_tree):
        """Without --trust-local-registries, the LocalRegistry that originally
        resolved UsesLib is dropped on reload, so live re-resolution against
        `registries` fails (reg is None). _component_members must still show
        the origin Reader.add_component recorded on the Comp at parse time."""
        from mccode_antlr.io import to_json, from_json
        from mccode_antlr.io.extract import build_manifest
        _, lib, instr = local_tree
        loaded = from_json(to_json(_read(lib, instr)))
        by_name = {m.name: m for m in build_manifest(loaded)}
        assert by_name['UsesLib.comp'].source == 'local'
        assert by_name['UsesLib.comp'].repository == f'local:{lib.stem}'
        assert by_name['UsesLib.comp'].repository_match == f'local:{lib.stem}'

    def test_include_remote_marks_remote_members_default_included(self, local_tree):
        from mccode_antlr.io.extract import build_manifest
        _, lib, instr = local_tree
        by_name = {m.name: m for m in build_manifest(_read(lib, instr), include_remote=True)}
        assert by_name['Progress_bar.comp'].default_included is True

    def test_embedded_duplicate_is_dropped_once_trust_restores_the_registry(self, local_tree):
        """A file embedded at save time (portable without its LocalRegistry) can
        become resolvable again once --trust-local-registries restores that
        registry -- it must appear once, attributed to the live registry, not
        twice (once 'embedded', once 'local')."""
        from mccode_antlr.config import config
        from mccode_antlr.io import to_json, from_json
        from mccode_antlr.io.extract import build_manifest
        _, lib, instr = local_tree
        blob = to_json(_read(lib, instr))

        config['serialization']['trust_local_registries'] = True
        try:
            loaded = from_json(blob)
        finally:
            config['serialization']['trust_local_registries'] = False

        manifest = build_manifest(loaded)
        entries = [m for m in manifest if m.name == 'mylib.h']
        assert len(entries) == 1
        assert entries[0].source == 'local'
        assert entries[0].repository == lib.stem
        assert entries[0].repository_match == str(lib.resolve())


class TestSelectMembers:
    def test_no_select_returns_default_included_only(self, local_tree):
        from mccode_antlr.io.extract import build_manifest, select_members
        _, lib, instr = local_tree
        manifest = build_manifest(_read(lib, instr))
        chosen = {m.name for m in select_members(manifest)}
        assert chosen == {m.name for m in manifest if m.default_included}
        assert 'Progress_bar.comp' not in chosen

    def test_select_bypasses_default_included_gate(self, local_tree):
        from mccode_antlr.io.extract import build_manifest, select_members
        _, lib, instr = local_tree
        manifest = build_manifest(_read(lib, instr))
        chosen = {m.name for m in select_members(manifest, select=['Progress_bar.comp'])}
        assert chosen == {'Progress_bar.comp'}

    def test_exclude_applies_after_select(self, local_tree):
        from mccode_antlr.io.extract import build_manifest, select_members
        _, lib, instr = local_tree
        manifest = build_manifest(_read(lib, instr))
        chosen = {m.name for m in select_members(manifest, select=['*.h', '*.c'], exclude=['*.c'])}
        assert chosen == {'mylib.h'}

    def test_repository_filter_matches_by_url_glob(self, local_tree):
        from mccode_antlr.io.extract import build_manifest, select_members
        _, lib, instr = local_tree
        manifest = build_manifest(_read(lib, instr))
        chosen = {m.name for m in select_members(manifest, repository=['*/mccode-dev/*'])}
        assert chosen == {'Progress_bar.comp'}

    def test_repository_filter_bypasses_default_included_gate(self, local_tree):
        from mccode_antlr.io.extract import build_manifest, select_members
        _, lib, instr = local_tree
        manifest = build_manifest(_read(lib, instr))
        chosen = {m.name for m in select_members(manifest, repository=['*/mccode-dev/*'])}
        assert 'Progress_bar.comp' in chosen

    def test_repository_and_select_combine_as_and(self, local_tree):
        from mccode_antlr.io.extract import build_manifest, select_members
        _, lib, instr = local_tree
        manifest = build_manifest(_read(lib, instr))
        # Progress_bar.comp matches the name glob but not the repository glob
        chosen = {m.name for m in select_members(
            manifest, select=['*.comp'], repository=[str(lib.resolve())],
        )}
        assert chosen == {'UsesLib.comp'}

    def test_repository_filter_no_match_returns_empty(self, local_tree):
        from mccode_antlr.io.extract import build_manifest, select_members
        _, lib, instr = local_tree
        manifest = build_manifest(_read(lib, instr))
        chosen = select_members(manifest, repository=['*/no-such-org/*'])
        assert chosen == []

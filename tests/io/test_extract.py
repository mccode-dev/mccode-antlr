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

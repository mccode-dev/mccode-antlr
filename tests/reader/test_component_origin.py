"""Reader.add_component records which registry resolved each Comp, so a
serialized instrument can still say where a component came from even after
its LocalRegistry is dropped (untrusted) on reload -- see io.extract's
_component_members fallback and reader.registry.origin_label.
"""
import pytest


@pytest.fixture
def local_tree(tmp_path):
    """A local component alongside an instrument that also uses a remote one."""
    lib = tmp_path / 'lib'
    lib.mkdir()
    (lib / 'UsesLib.comp').write_text(
        'DEFINE COMPONENT UsesLib\nSETTING PARAMETERS (thing=1)\nTRACE %{ SCATTER; %}\nEND\n'
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


class TestAddComponentOrigin:
    def test_locally_resolved_component_records_local_origin(self, local_tree):
        _, lib, instr = local_tree
        loaded = _read(lib, instr)
        comp = next(i.type for i in loaded.components if i.type.name == 'UsesLib')
        assert comp.origin == f'local:{lib.stem}'

    def test_remotely_resolved_component_records_remote_origin(self, local_tree):
        _, lib, instr = local_tree
        loaded = _read(lib, instr)
        comp = next(i.type for i in loaded.components if i.type.name == 'Progress_bar')
        assert comp.origin == 'remote:mcstas'

    def test_origin_is_not_written_into_the_comp_text(self, local_tree):
        """Provenance is metadata, not part of the McCode DSL text."""
        _, lib, instr = local_tree
        loaded = _read(lib, instr)
        comp = next(i.type for i in loaded.components if i.type.name == 'UsesLib')
        assert 'local:' not in comp.to_string()

    def test_origin_survives_the_json_round_trip(self, local_tree):
        """Exercises Comp.from_dict's field whitelist, not just generic msgspec
        struct decoding -- Instr.from_dict reconstructs components via
        Comp.from_dict(v), so a field left out of that whitelist is silently
        dropped even though it serialized correctly on the way out."""
        from mccode_antlr.io import to_json, from_json
        _, lib, instr = local_tree
        back = from_json(to_json(_read(lib, instr)))
        comp = next(i.type for i in back.components if i.type.name == 'UsesLib')
        assert comp.origin == f'local:{lib.stem}'

"""InMemoryRegistry: storage, materialization and serialization.

The translator resolves files through reg.path() and then open() -- it never asks
a registry for contents() -- so an in-memory registry is only usable once its
entries exist on disk.
"""


def _registry(**kwargs):
    from mccode_antlr.reader.registry import InMemoryRegistry
    reg = InMemoryRegistry('inmem', **kwargs)
    reg.add_comp('MyComp', 'DEFINE COMPONENT MyComp\nEND\n')
    reg.add('share/helper.h', '/* SENTINEL */\n')
    reg.add('data/blob.dat', bytes(range(256)))
    return reg


class TestStorage:
    def test_add_comp_forces_the_suffix_but_add_does_not(self):
        reg = _registry()
        assert 'MyComp.comp' in reg.filenames()
        assert 'share/helper.h' in reg.filenames()

    def test_components_property_exposes_text_entries_only(self):
        """Kept for callers that predate binary support; binary is not decodable."""
        reg = _registry()
        assert set(reg.components) == {'MyComp.comp', 'share/helper.h'}

    def test_kwargs_construction_still_works(self):
        from mccode_antlr.reader.registry import InMemoryRegistry
        reg = InMemoryRegistry('inmem', MyComp='DEFINE COMPONENT MyComp\nEND\n')
        assert reg.contents('MyComp', '.comp').startswith('DEFINE COMPONENT')

    def test_files_kwarg_is_not_swallowed_as_a_component(self):
        from base64 import b64encode
        from mccode_antlr.reader.registry import InMemoryRegistry
        reg = InMemoryRegistry('inmem', files={'a.h': b64encode(b'x').decode()})
        assert reg.filenames() == ['a.h']

    def test_files_values_must_be_base64(self):
        import pytest
        from mccode_antlr.reader.registry import InMemoryRegistry
        with pytest.raises(ValueError, match='base64'):
            InMemoryRegistry('inmem', files={'a.h': 'not valid base64 !!'})

    def test_binary_via_contents_raises_but_bytes_work(self):
        import pytest
        reg = _registry()
        with pytest.raises(RuntimeError, match='not UTF-8'):
            reg.contents('data/blob.dat')
        assert reg.contents_bytes('data/blob.dat') == bytes(range(256))

    def test_known_unique_and_availability(self):
        reg = _registry()
        assert reg.known('MyComp', '.comp')
        assert not reg.known('Absent', '.comp')
        assert reg.is_available('MyComp', '.comp')
        # Registry.unique is a bare `pass`; without the override configure_file
        # silently skips this registry
        assert reg.unique('helper.h')


class TestMaterialization:
    def test_path_writes_the_entry_and_content_matches(self):
        reg = _registry()
        assert reg.path('share/helper.h').read_text() == '/* SENTINEL */\n'

    def test_nested_names_become_directories(self):
        """A filename containing '/' has to survive as a real subdirectory."""
        reg = _registry()
        path = reg.path('share/helper.h')
        assert path.parent.name == 'share'
        assert path.parent.parent == reg.root

    def test_binary_payload_survives_the_write(self):
        reg = _registry()
        assert reg.path('data/blob.dat').read_bytes() == bytes(range(256))

    def test_all_entries_are_written_together(self):
        """One entry may %include another, so siblings must be present."""
        reg = _registry()
        reg.path('MyComp.comp')
        assert (reg.root / 'share' / 'helper.h').is_file()

    def test_root_is_content_addressed_and_stable(self):
        assert _registry().root == _registry().root

    def test_differing_content_gets_a_different_root(self):
        from mccode_antlr.reader.registry import InMemoryRegistry
        a, b = InMemoryRegistry('inmem'), InMemoryRegistry('inmem')
        a.add('x.h', 'one')
        b.add('x.h', 'two')
        assert a.root != b.root

    def test_repeated_materialization_is_idempotent(self):
        reg = _registry()
        first = reg.path('MyComp.comp')
        stamp = first.stat().st_mtime_ns
        assert reg.path('MyComp.comp') == first
        assert first.stat().st_mtime_ns == stamp

    def test_unknown_name_raises(self):
        import pytest
        with pytest.raises(KeyError):
            _registry().path('Absent.comp')


class TestSerialization:
    def test_json_round_trip(self):
        import msgspec
        from mccode_antlr.reader.registry import SerializableRegistry
        reg = _registry()
        sr = SerializableRegistry.from_registry(reg)
        back = msgspec.json.decode(msgspec.json.encode(sr), type=SerializableRegistry).to_registry()
        assert back == reg
        assert back.contents_bytes('data/blob.dat') == bytes(range(256))

    def test_msgpack_round_trip(self):
        import msgspec
        from mccode_antlr.reader.registry import SerializableRegistry
        reg = _registry()
        sr = SerializableRegistry.from_registry(reg)
        back = msgspec.msgpack.decode(msgspec.msgpack.encode(sr), type=SerializableRegistry).to_registry()
        assert back == reg

    def test_instrument_carrying_one_can_be_saved(self):
        """to_json used to raise AttributeError: no attribute 'file_contents'."""
        from mccode_antlr.assembler import Assembler
        from mccode_antlr.reader.registry import InMemoryRegistry
        from mccode_antlr import Flavor
        from mccode_antlr.io import to_json, from_json
        mem = InMemoryRegistry('inmem')
        mem.add_comp('MyLocal', 'DEFINE COMPONENT MyLocal\nTRACE %{ SCATTER; %}\nEND\n')
        a = Assembler('demo', flavor=Flavor.MCSTAS, registries=[mem])
        a.component('mine', 'MyLocal', at=(0, 0, 1))
        back = from_json(to_json(a.instrument))
        assert any(isinstance(r, InMemoryRegistry) for r in back.registries)

    def test_not_dropped_by_the_trust_gate(self):
        """Only LocalRegistry names a path on the saving machine."""
        import mccode_antlr.reader.registry as rm
        reg = _registry()
        assert rm.screen_deserialized_registries([reg], 'a test') == [reg]

    def test_python_export_round_trips_including_binary(self):
        """The emitted expression previously referenced an undefined `name`."""
        from mccode_antlr.export.python import _handle_registry
        from mccode_antlr.reader.registry import InMemoryRegistry
        reg = _registry()
        rep, _ = _handle_registry(reg)
        back = eval(rep, {'InMemoryRegistry': InMemoryRegistry})
        assert back == reg
        assert back.contents_bytes('data/blob.dat') == bytes(range(256))

    def test_equality_and_hashing(self):
        from mccode_antlr.reader.registry import InMemoryRegistry
        a, b = _registry(), _registry()
        assert a == b and hash(a) == hash(b)
        c = InMemoryRegistry('inmem')
        c.add('x.h', 'different')
        assert a != c

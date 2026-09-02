"""TargetVisitor.prefetch_data_files must find data files nested a level
deeper than data/, e.g. McStas's data/ISIS_tables/ and data/Gas_tables/
families (issue #329)."""
from mccode_antlr import Flavor
from mccode_antlr.translators.target import TargetVisitor


class FakeValue:
    def __init__(self, value):
        self.is_str = True
        self.has_value = True
        self.value = value


class FakeParam:
    def __init__(self, value):
        self.value = FakeValue(value)


class FakeComponent:
    def __init__(self, *values):
        self.parameters = [FakeParam(v) for v in values]


class FakeRegistry:
    """Mimics the bits of RemoteRegistry/LocalRegistry that prefetch_data_files
    relies on: known()/fullname() resolve a bare name against a fixed mapping
    of registered files, and path() records what was actually fetched."""

    def __init__(self, files: dict[str, str]):
        # files: {bare_name: resolved registry path}
        self._files = files
        self.fetched = []

    def known(self, name, ext=None, strict=False):
        return name in self._files

    def fullname(self, name, ext=None, exact=True):
        return self._files.get(name)

    def path(self, name, ext=None, exact=True):
        self.fetched.append(name)
        return f'/cache/{name}'


class DummyInstr:
    name = 'dummy'

    def __init__(self, registries, components):
        self.registries = registries
        self.components = components

    def verify_instance_parameters(self):
        return None


def _prefetch(registry_files, param_value):
    reg = FakeRegistry(registry_files)
    instr = DummyInstr([reg], [FakeComponent(param_value)])
    visitor = TargetVisitor(instr, Flavor.MCSTAS)
    visitor.prefetch_data_files()
    return reg


class TestNestedDataDirectory:
    def test_file_nested_under_a_data_subdirectory_is_fetched(self):
        """TS2.imat lives at mcstas-comps/data/ISIS_tables/TS2.imat -- one
        directory deeper than the plain data/<name> case."""
        reg = _prefetch(
            {'TS2.imat': 'mcstas-comps/data/ISIS_tables/TS2.imat'},
            '"TS2.imat"',
        )
        assert reg.fetched == ['TS2.imat']

    def test_gas_tables_family_is_also_fetched(self):
        reg = _prefetch(
            {'He3.gas': 'mcstas-comps/data/Gas_tables/He3.gas'},
            '"He3.gas"',
        )
        assert reg.fetched == ['He3.gas']

    def test_file_directly_under_data_still_works(self):
        """No regression on the original, simpler data/<name> layout."""
        reg = _prefetch(
            {'some_file.dat': 'mcstas-comps/data/some_file.dat'},
            '"some_file.dat"',
        )
        assert reg.fetched == ['some_file.dat']

    def test_file_outside_any_data_directory_is_not_fetched(self):
        """A same-named non-data asset elsewhere in the registry must not be
        pulled in just because it shares a basename with a string parameter."""
        reg = _prefetch(
            {'Something.comp': 'mcstas-comps/contrib/Something.comp'},
            '"Something.comp"',
        )
        assert reg.fetched == []

    def test_a_file_literally_named_data_does_not_spuriously_match(self):
        """The check excludes the filename itself when looking for a `data`
        ancestor, so a bare top-level file named `data.ext` isn't treated as
        living under a directory called `data`."""
        reg = _prefetch(
            {'data.ext': 'mcstas-comps/data.ext'},
            '"data.ext"',
        )
        assert reg.fetched == []

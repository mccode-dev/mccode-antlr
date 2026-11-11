"""The --verbose NeXus compile hint must warn when the configured flags name
the wrong library for the in-use McCode libc: NeXus before mccode-dev/McCode#2895,
HDF5 after (the change the libc made at v3.10.1), regardless of whether the
flags use gcc/clang '-l' syntax or MSVC '.lib' filenames. See #405.
"""
import pytest

from mccode_antlr.translators.c import CTargetVisitor


class FakeRegistry:
    def __init__(self, name, version):
        self.name = name
        self.version = version


class FakeSource:
    def __init__(self, registries):
        self.registries = registries


def visitor_with_registries(*registries):
    visitor = CTargetVisitor.__new__(CTargetVisitor)
    visitor.source = FakeSource(list(registries))
    return visitor


@pytest.mark.parametrize('version, boundary, expected', [
    ('3.10.0', '3.10.1', True),
    ('3.10.1', '3.10.1', False),
    ('3.11.0', '3.10.1', False),
    ('3.5.19', '3.5.20', True),
    ('3.5.20', '3.5.20', False),
])
def test_libc_before_compares_the_libc_registrys_own_version(version, boundary, expected):
    visitor = visitor_with_registries(FakeRegistry('libc', version), FakeRegistry('mcstas', '9.9.9'))
    assert visitor._libc_before(boundary) is expected


def test_libc_before_is_false_when_no_libc_registry_is_present():
    visitor = visitor_with_registries(FakeRegistry('mcstas', '9.9.9'))
    assert visitor._libc_before('3.10.1') is False


INSTR = """DEFINE INSTRUMENT quiet(dummy=0)
TRACE
COMPONENT origin = Arm() AT (0, 0, 0) ABSOLUTE
END
"""


def build_with_libc_version(libc_version, caplog):
    from mccode_antlr import Flavor
    from mccode_antlr.loader import parse_mcstas_instr

    caplog.set_level('INFO', logger='mccode_antlr')
    instr = parse_mcstas_instr(INSTR)
    for reg in instr.registries:
        if reg.name == 'libc':
            reg.version = libc_version
    config = dict(default_main=True, enable_trace=False, portable=False,
                  include_runtime=True, embed_instrument_file=False)
    CTargetVisitor(instr, flavor=Flavor.MCSTAS, config=config, verbose=True).contents()


def run_with_flags(nexus_flags, libc_version, caplog):
    from mccode_antlr.config import config

    config.set({'flags': {'nexus': nexus_flags}})
    try:
        build_with_libc_version(libc_version, caplog)
    finally:
        config.sources.pop(0)
    # ignore unrelated warnings, e.g. registry.py's "specified more than once" from
    # overwriting the real libc registry's version for this test
    return [r.getMessage() for r in caplog.records
            if r.levelname == 'WARNING' and r.name == 'mccode_antlr.translators.c']


# gcc/clang (Linux, macOS) spell the library as a '-l' linker flag; MSVC (Windows)
# names the .lib file directly -- the hint must not assume either syntax, only that
# the library's name ('NeXus' or 'hdf5') appears somewhere in the configured flags.
@pytest.mark.parametrize('nexus_flags', [
    '-DUSE_NEXUS -lNeXus',       # Linux/macOS, pre-#2895 McCode
    '/DUSE_NEXUS NeXus.lib',     # Windows, pre-#2895 McCode
])
def test_hint_warns_when_post_2895_libc_is_paired_with_nexus_flags(nexus_flags, caplog):
    warnings = run_with_flags(nexus_flags, '3.10.1', caplog)
    assert any('HDF5' in m for m in warnings), warnings


@pytest.mark.parametrize('hdf5_flags', [
    '-DUSE_NEXUS -lhdf5',        # Linux/macOS, post-#2895 McCode
    '/DUSE_NEXUS hdf5.lib',      # Windows, post-#2895 McCode
])
def test_hint_is_quiet_when_post_2895_libc_is_paired_with_hdf5_flags(hdf5_flags, caplog):
    warnings = run_with_flags(hdf5_flags, '3.10.1', caplog)
    assert warnings == []


@pytest.mark.parametrize('nexus_flags', [
    '-DUSE_NEXUS -lNeXus',       # Linux/macOS, pre-#2895 McCode
    '/DUSE_NEXUS NeXus.lib',     # Windows, pre-#2895 McCode
])
def test_hint_is_quiet_when_pre_2895_libc_is_paired_with_nexus_flags(nexus_flags, caplog):
    warnings = run_with_flags(nexus_flags, '3.10.0', caplog)
    assert warnings == []

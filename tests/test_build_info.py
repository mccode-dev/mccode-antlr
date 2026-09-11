"""Build information written into the generated C, and read back out of a binary.

A compiled binary should be able to say what it is without being run, and the
MPI/OpenACC/NeXus part of that statement must be decided by the preprocessor --
otherwise a `.c` translated for one target and compiled for another lies.
"""
import json

import pytest

INSTR = """DEFINE INSTRUMENT dbg(dummy=0)
TRACE
COMPONENT o = Progress_bar() AT (0,0,0) ABSOLUTE
END
"""

WITH_METADATA = """DEFINE INSTRUMENT dbg(dummy=0)
TRACE
COMPONENT o = Progress_bar() AT (0,0,0) ABSOLUTE
METADATA "text/plain" a_key %{
He said "hi"
%}
END
"""

MACROS = ('MCCODE_ANTLR_BUILD_MPI', 'MCCODE_ANTLR_BUILD_ACC', 'MCCODE_ANTLR_BUILD_NEXUS')


def translate(source=INSTR, **config_overrides):
    from mccode_antlr import Flavor
    from mccode_antlr.loader import parse_mcstas_instr
    from mccode_antlr.translators.c import CTargetVisitor
    instr = parse_mcstas_instr(source)
    config = dict(default_main=True, enable_trace=True, portable=False,
                  include_runtime=True, embed_instrument_file=False, verbose=False)
    config.update(config_overrides)
    return instr, CTargetVisitor(instr, flavor=Flavor.MCSTAS, config=config).contents()


def table_of(text):
    """The metadata_table[] initializer, without the preceding declaration."""
    start = text.index('struct metadata_table_struct metadata_table[] = {')
    return text[start:text.index('int num_metadata =', start)]


def payload_of(text, mpi='false', acc='false', nexus='false'):
    """The build-info JSON as the preprocessor would leave it."""
    row = [line for line in table_of(text).splitlines()
           if 'mccode_antlr_build' in line][0]
    value = row[row.index('"application/json", ') + len('"application/json", '):]
    value = value.rsplit('},', 1)[0].strip()
    for macro, chosen in zip(MACROS, (mpi, acc, nexus)):
        value = value.replace(macro, f'"{chosen}"')
    # concatenate the adjacent C string literals, then undo the C escaping
    joined = ''.join(part for part in value.split('" "'))
    return json.loads(joined.strip('"').replace('\\"', '"'))


class TestGeneratedC:
    def test_macros_are_emitted_before_the_table_that_uses_them(self):
        _, text = translate()
        for macro in MACROS:
            assert f'#  define {macro} "true"' in text
            assert f'#  define {macro} "false"' in text
            assert text.index(f'#  define {macro}') < text.index(
                'struct metadata_table_struct metadata_table[] = {')

    def test_the_macros_are_spliced_not_quoted(self):
        """The whole point: these must reach the preprocessor, not sit inside a
        string literal where they would be inert text."""
        _, text = translate()
        row = table_of(text)
        for macro in MACROS:
            assert f' {macro} ' in row
            assert f'\\"{macro}' not in row

    def test_payload_records_the_instrument_and_its_digest(self):
        from mccode_antlr.instr.digest import instrument_digest
        instr, text = translate()
        payload = payload_of(text)
        assert payload['mccode_antlr_build_info'] == 1
        assert payload['generator'] == 'mccode-antlr'
        assert payload['instrument'] == 'dbg'
        assert payload['flavor'] == 'mcstas'
        assert payload['source_hash'] == instrument_digest(instr)

    def test_the_spliced_fields_follow_the_macro(self):
        _, text = translate()
        assert payload_of(text, mpi='false')['mpi'] is False
        assert payload_of(text, mpi='true')['mpi'] is True
        assert payload_of(text, acc='true')['acc'] is True
        assert payload_of(text, nexus='true')['nexus'] is True

    def test_trace_follows_the_config(self):
        _, on = translate(enable_trace=True)
        _, off = translate(enable_trace=False)
        assert payload_of(on)['trace'] is True
        assert payload_of(off)['trace'] is False

    def test_translation_is_reproducible(self):
        """No timestamp in the payload, or the digest could never be compared."""
        assert payload_of(translate()[1]) == payload_of(translate()[1])

    def test_user_metadata_is_still_escaped_as_before(self):
        _, text = translate(WITH_METADATA)
        row = [line for line in table_of(text).splitlines() if 'a_key' in line][0]
        assert '\\"hi\\"' in row
        assert '\\n' in row

    def test_num_metadata_counts_the_build_info_row(self):
        import re
        for source, expected in ((INSTR, 1), (WITH_METADATA, 2)):
            _, text = translate(source)
            assert int(re.search(r'int num_metadata = (\d+);', text).group(1)) == expected

    def test_it_can_be_turned_off(self):
        _, text = translate(build_info=False)
        assert 'mccode_antlr_build' not in text
        assert MACROS[0] not in text

    def test_a_user_entry_with_the_reserved_name_is_ignored(self):
        reserved = INSTR.replace('END', 'METADATA "application/json" mccode_antlr_build %{\n{"spoofed":1}\n%}\nEND')
        _, text = translate(reserved)
        assert 'spoofed' not in text
        assert payload_of(text)['generator'] == 'mccode-antlr'


class TestDigest:
    def test_stable_across_parses(self):
        from mccode_antlr.instr.digest import instrument_digest
        from mccode_antlr.loader import parse_mcstas_instr
        assert (instrument_digest(parse_mcstas_instr(INSTR))
                == instrument_digest(parse_mcstas_instr(INSTR)))

    def test_stable_across_a_translation(self):
        """Translation memoises RawC.translated on shared, cached component
        objects; hashing that would make the digest depend on what ran earlier."""
        from mccode_antlr.instr.digest import instrument_digest
        instr, _ = translate()
        before = instrument_digest(instr)
        translate()  # populates the memo on the cached Progress_bar
        from mccode_antlr.loader import parse_mcstas_instr
        assert instrument_digest(parse_mcstas_instr(INSTR)) == before
        assert instrument_digest(instr) == before

    def test_content_changes_the_digest(self):
        from mccode_antlr.instr.digest import instrument_digest
        from mccode_antlr.loader import parse_mcstas_instr
        other = INSTR.replace('AT (0,0,0)', 'AT (0,0,1)')
        assert (instrument_digest(parse_mcstas_instr(INSTR))
                != instrument_digest(parse_mcstas_instr(other)))

    def test_independent_of_the_build_info_entry(self):
        """Guards the self-reference: the digest lives inside the payload."""
        from mccode_antlr.common.metadata import MetaData
        from mccode_antlr.instr.digest import instrument_digest
        from mccode_antlr.loader import parse_mcstas_instr
        instr = parse_mcstas_instr(INSTR)
        before = instrument_digest(instr)
        instr.add_metadata(MetaData.from_instrument_tokens(
            instr.name, 'application/json', 'mccode_antlr_build', '{"anything": 1}'))
        assert instrument_digest(instr) == before


class TestNaming:
    @pytest.mark.parametrize('mpi,acc,tag', [(False, False, ''), (True, False, 'mpi'),
                                             (False, True, 'acc'), (True, True, 'mpiacc')])
    def test_tag(self, mpi, acc, tag):
        from mccode_antlr.compiler.c import CBinaryTarget
        assert CBinaryTarget(mpi=mpi, acc=acc).tag == tag

    def test_nexus_is_not_tagged(self):
        from mccode_antlr.compiler.c import CBinaryTarget
        assert CBinaryTarget(nexus=True).tag == ''
        assert CBinaryTarget(mpi=True, nexus=True).tag == 'mpi'

    def test_filename(self):
        from mccode_antlr.compiler.c import CBinaryTarget, binary_filename
        from mccode_antlr.config import config
        ext = config['ext'].get(str)
        assert binary_filename('foo', CBinaryTarget()) == f'foo{ext}'
        assert binary_filename('foo', CBinaryTarget(mpi=True)) == f'foo.mpi{ext}'

    def test_a_dotted_instrument_name_is_not_truncated(self):
        """Path.with_suffix would turn 'TAS.v2' into 'TAS.out'."""
        from mccode_antlr.compiler.c import CBinaryTarget, binary_filename
        from mccode_antlr.config import config
        assert binary_filename('TAS.v2', CBinaryTarget()) == f'TAS.v2{config["ext"].get(str)}'

    def test_an_existing_tag_is_replaced_not_appended(self):
        from mccode_antlr.compiler.c import CBinaryTarget, binary_filename, strip_target_tag
        from mccode_antlr.config import config
        ext = config['ext'].get(str)
        assert strip_target_tag('foo.mpi') == 'foo'
        assert strip_target_tag('foo.mpiacc') == 'foo'
        assert strip_target_tag('foo') == 'foo'
        assert binary_filename('foo.mpi', CBinaryTarget(acc=True)) == f'foo.acc{ext}'

    def test_path_rules(self, tmp_path):
        from mccode_antlr.compiler.c import CBinaryTarget, binary_path
        from mccode_antlr.config import config
        ext = config['ext'].get(str)
        mpi = CBinaryTarget(mpi=True)
        assert binary_path(tmp_path, 'foo', mpi) == tmp_path / f'foo.mpi{ext}'
        assert binary_path(tmp_path / 'bar', 'foo', mpi) == tmp_path / f'bar.mpi{ext}'
        # an explicit filename is the user's choice and is left alone
        named = tmp_path / 'bar.bin'
        assert binary_path(named, 'foo', mpi) == named


class TestProbe:
    """Synthetic blobs: no compiler needed, and every rung can be exercised."""

    def payload(self, **overrides):
        base = {'mccode_antlr_build_info': 1, 'generator': 'mccode-antlr',
                'instrument': 'dbg', 'source_hash': 'abc123',
                'mpi': False, 'acc': False, 'nexus': False}
        base.update(overrides)
        return json.dumps(base, separators=(',', ':')).encode()

    def write(self, tmp_path, name, *chunks):
        path = tmp_path / name
        path.write_bytes(b'\x7fELF padding\x00' + b'\x00'.join(chunks) + b'\x00tail')
        return path

    def test_metadata_wins(self, tmp_path):
        from mccode_antlr.build_info import probe_binary
        probe = probe_binary(self.write(tmp_path, 'a', self.payload(mpi=True)),
                             allow_exec=False)
        assert (probe.mpi, probe.acc, probe.origin) == (True, False, 'metadata')
        assert probe.info['instrument'] == 'dbg'

    def test_help_strings_when_there_is_no_metadata(self, tmp_path):
        from mccode_antlr.build_info import HELP_MPI, probe_binary
        probe = probe_binary(self.write(tmp_path, 'b', HELP_MPI), allow_exec=False)
        assert (probe.mpi, probe.acc, probe.origin) == (True, False, 'help-strings')

    def test_symbol_names_alone_prove_nothing(self, tmp_path):
        """The regression: a serial binary built with --source embeds the
        instrument text, and that text may contain MPI_Init inside an
        '#ifdef USE_MPI' block. Scanning for the symbol reported it as MPI."""
        from mccode_antlr.build_info import probe_binary
        blob = b'#ifdef USE_MPI\n  MPI_Init(NULL, NULL);\n#endif\nacc_init\n'
        probe = probe_binary(self.write(tmp_path, 'c', blob), allow_exec=False)
        assert probe.mpi is None and probe.acc is None
        assert probe.origin == 'unknown' and not probe.known

    def test_embedded_source_does_not_shadow_the_real_entry(self, tmp_path):
        """A dumped .c embeds the row C-escaped, so it cannot collide; text that
        merely quotes the magic must still be rejected for want of the shape."""
        from mccode_antlr.build_info import probe_binary
        decoy = b'{"mccode_antlr_build_info":1,"generator":"something else"}'
        probe = probe_binary(self.write(tmp_path, 'd', decoy, self.payload(mpi=True)),
                             allow_exec=False)
        assert (probe.mpi, probe.origin) == (True, 'metadata')

    def test_unreadable_file_is_unknown_not_serial(self, tmp_path):
        from mccode_antlr.build_info import probe_binary
        probe = probe_binary(tmp_path / 'does-not-exist', allow_exec=False)
        assert probe.mpi is None and probe.origin == 'unknown'

    def test_infer_binary_target_keeps_the_supplied_default(self, tmp_path):
        from mccode_antlr.compiler.c import CBinaryTarget, infer_binary_target
        default = CBinaryTarget(mpi=True)
        inferred = infer_binary_target(tmp_path / 'nothing', default=default,
                                       allow_exec=False)
        assert inferred.type & CBinaryTarget.Type.mpi


class TestFlagResolution:
    """An explicit flag is never overridden; an absent one takes the binary's value."""

    def resolve(self, requested, detected):
        from mccode_antlr.run.runner import resolve_target_flag
        return resolve_target_flag('--parallel', 'MPI', requested, detected, 'x.out')

    @pytest.mark.parametrize('detected,expected', [(True, True), (False, False), (None, False)])
    def test_unspecified_follows_the_binary(self, detected, expected):
        assert self.resolve(None, detected) is expected

    def test_agreement_is_silent(self):
        assert self.resolve(True, True) is True
        assert self.resolve(False, False) is False

    def test_requesting_mpi_from_a_serial_binary_is_an_error(self):
        """Otherwise mpirun starts N full-ncount runs which race on --dir."""
        with pytest.raises(RuntimeError, match='not built with MPI support'):
            self.resolve(True, False)

    def test_declining_mpi_on_an_mpi_binary_warns_but_obeys(self):
        assert self.resolve(False, True) is False

    def test_an_unknown_binary_never_overrides_the_user(self):
        assert self.resolve(True, None) is True
        assert self.resolve(False, None) is False


class TestCacheComparison:
    def expected(self, **overrides):
        base = {'mccode_antlr_build_info': 1, 'generator_version': '1.0',
                'flavor': 'mcstas', 'instrument': 'dbg', 'source_hash': 'abc',
                'trace': True, 'mpi': False, 'acc': False, 'nexus': False}
        base.update(overrides)
        return base

    def test_identical_matches(self):
        from mccode_antlr.build_info import build_info_matches
        assert build_info_matches(self.expected(), self.expected())[0]

    def test_missing_information_never_matches(self):
        from mccode_antlr.build_info import build_info_matches
        ok, why = build_info_matches(None, self.expected())
        assert not ok and 'no mccode-antlr build information' in why

    def test_a_changed_source_hash_rebuilds(self):
        from mccode_antlr.build_info import build_info_matches
        ok, why = build_info_matches(self.expected(source_hash='old'), self.expected())
        assert not ok and 'source_hash changed' in why

    def test_requesting_mpi_of_a_serial_binary_rebuilds(self):
        from mccode_antlr.build_info import build_info_matches
        ok, why = build_info_matches(self.expected(mpi=False), self.expected(mpi=True))
        assert not ok and 'mpi support was requested' in why

    def test_an_extra_capability_is_tolerated(self):
        """A DEPENDENCY carrying -DUSE_MPI makes the splice record mpi=true even
        for a nominally serial request; demanding equality would rebuild forever."""
        from mccode_antlr.build_info import build_info_matches
        assert build_info_matches(self.expected(mpi=True), self.expected(mpi=False))[0]

    def test_unknown_expectations_are_not_compared(self):
        """mccode_version is None when the registry version cannot be resolved."""
        from mccode_antlr.build_info import build_info_matches
        assert build_info_matches(self.expected(mccode_version='3.7.22'),
                                  self.expected(mccode_version=None))[0]

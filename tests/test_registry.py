def test_mccode_pooch_tags():
    from mccode_antlr import Flavor
    from mccode_antlr.reader import default_registries
    for flavor in (Flavor.BASE, Flavor.MCSTAS, Flavor.MCXTRACE,):
        for reg in default_registries(flavor):
            assert reg.version != "main"


def test_mccode_pooch_codegen_registry():
    from mccode_antlr.reader import codegen_registries
    registries = codegen_registries()
    assert isinstance(registries, list)
    assert len(registries) == 1
    assert registries[0].name == 'codegen'
    assert registries[0].known('windirent.h')


# ---------------------------------------------------------------------------
# _parse_gitref_spec — pure parsing, no network
# ---------------------------------------------------------------------------

class TestParseGitrefSpec:
    """Unit tests for the compact git-reference spec parser."""

    def _parse(self, spec):
        from mccode_antlr.reader.registry import _parse_gitref_spec
        return _parse_gitref_spec(spec)

    # -- git+ prefix ----------------------------------------------------------

    def test_git_plus_basic(self):
        result = self._parse('git+https://github.com/owner/repo@v1.0')
        assert result == ('repo', 'https://github.com/owner/repo', 'v1.0', 'pooch-registry.txt')

    def test_git_plus_strips_dot_git(self):
        result = self._parse('git+https://github.com/owner/repo.git@v2.3')
        assert result == ('repo', 'https://github.com/owner/repo', 'v2.3', 'pooch-registry.txt')

    def test_git_plus_custom_registry_file(self):
        result = self._parse('git+https://github.com/owner/repo@v1.0#my-registry.txt')
        assert result == ('repo', 'https://github.com/owner/repo', 'v1.0', 'my-registry.txt')

    def test_git_plus_commit_sha(self):
        result = self._parse('git+https://github.com/owner/repo@abc1234')
        assert result is not None
        name, url, version, reg = result
        assert version == 'abc1234'
        assert name == 'repo'

    def test_git_plus_no_at_returns_none(self):
        assert self._parse('git+https://github.com/owner/repo') is None

    def test_git_plus_strips_trailing_slash(self):
        result = self._parse('git+https://github.com/owner/repo/@v1.0')
        assert result is not None
        assert result[1] == 'https://github.com/owner/repo'

    # -- owner/repo@version ---------------------------------------------------

    def test_short_form_basic(self):
        result = self._parse('owner/repo@v3.5')
        assert result == ('repo', 'https://github.com/owner/repo', 'v3.5', 'pooch-registry.txt')

    def test_short_form_custom_registry_file(self):
        result = self._parse('owner/repo@v3.5#mcstas-registry.txt')
        assert result == ('repo', 'https://github.com/owner/repo', 'v3.5', 'mcstas-registry.txt')

    def test_short_form_tag_with_dots(self):
        result = self._parse('mccode-dev/McCode@v3.5.31')
        assert result is not None
        _, _, version, _ = result
        assert version == 'v3.5.31'

    # -- non-matching inputs --------------------------------------------------

    def test_space_separated_returns_none(self):
        assert self._parse('name https://example.com v1 reg.txt') is None

    def test_plain_path_returns_none(self):
        assert self._parse('/some/local/path') is None

    def test_empty_returns_none(self):
        assert self._parse('') is None

    def test_no_at_returns_none(self):
        assert self._parse('owner/repo') is None

    def test_multiple_slashes_before_at_returns_none(self):
        # Looks like a URL path fragment, not owner/repo — should not match
        assert self._parse('owner/repo/extra@v1') is None


# ---------------------------------------------------------------------------
# registry_from_specification — new formats (GitHubRegistry mocked)
# ---------------------------------------------------------------------------

class TestRegistryFromSpecificationNewFormats:
    """Tests that the new compact formats reach GitHubRegistry with correct args."""

    def _call(self, spec, monkeypatch):
        """Call registry_from_specification with GitHubRegistry.__init__ mocked."""
        captured = {}

        import mccode_antlr.reader.registry as reg_mod

        original_init = reg_mod.GitHubRegistry.__init__

        def fake_init(self, name, url, version, filename=None, **kw):
            captured.update(name=name, url=url, version=version, filename=filename)
            # Minimal init to avoid network calls
            self.name = name
            self.url = url
            self.version = version
            self.filename = filename
            self.pooch = None
            self._stashed_registry = None

        monkeypatch.setattr(reg_mod.GitHubRegistry, '__init__', fake_init)
        result = reg_mod.registry_from_specification(spec)
        return result, captured

    def test_git_plus_creates_github_registry(self, monkeypatch):
        reg, cap = self._call('git+https://github.com/owner/repo@v1.0', monkeypatch)
        assert cap['name'] == 'repo'
        assert cap['url'] == 'https://github.com/owner/repo'
        assert cap['version'] == 'v1.0'
        assert cap['filename'] == 'pooch-registry.txt'

    def test_short_form_creates_github_registry(self, monkeypatch):
        reg, cap = self._call('owner/repo@v3.5.31', monkeypatch)
        assert cap['name'] == 'repo'
        assert cap['url'] == 'https://github.com/owner/repo'
        assert cap['version'] == 'v3.5.31'
        assert cap['filename'] == 'pooch-registry.txt'

    def test_custom_registry_file_passed_through(self, monkeypatch):
        reg, cap = self._call('owner/repo@v1.0#custom.txt', monkeypatch)
        assert cap['filename'] == 'custom.txt'

    def test_git_plus_dot_git_stripped(self, monkeypatch):
        reg, cap = self._call('git+https://github.com/owner/repo.git@v2.0', monkeypatch)
        assert cap['url'] == 'https://github.com/owner/repo'
        assert cap['name'] == 'repo'



# ---------------------------------------------------------------------------
# Registry.to_file — serialization format
# ---------------------------------------------------------------------------

class TestRegistryToFile:
    """Tests for the Registry: <spec> comment format written by to_file."""

    def _to_file_str(self, registry):
        from io import StringIO
        from mccode_antlr.common import TextWrapper
        out = StringIO()
        registry.to_file(out, TextWrapper())
        return out.getvalue().strip()

    def test_remote_registry_format(self):
        import mccode_antlr.reader.registry as rm
        reg = rm.RemoteRegistry('mylib', 'https://example.com/repo', 'v1.0', 'mylib-registry.txt')
        line = self._to_file_str(reg)
        assert line == 'Registry: mylib https://example.com/repo v1.0 mylib-registry.txt'

    def test_local_registry_format(self, tmp_path):
        import mccode_antlr.reader.registry as rm
        reg = rm.LocalRegistry('mylib', str(tmp_path))
        line = self._to_file_str(reg)
        assert line == f'Registry: mylib {tmp_path.as_posix()}'

    def test_remote_registry_roundtrips(self):
        import mccode_antlr.reader.registry as rm
        reg = rm.RemoteRegistry('mylib', 'https://example.com/repo', 'v1.0', 'mylib-registry.txt')
        line = self._to_file_str(reg)
        spec = line[len('Registry:'):].strip()
        # format 4 → registry_from_specification would create a GitHubRegistry;
        # check the spec is parseable back to the right name/url/version/filename
        parts = spec.split()
        assert parts == ['mylib', 'https://example.com/repo', 'v1.0', 'mylib-registry.txt']

    def test_github_registry_with_separate_registry_url_includes_fifth_field(self, monkeypatch):
        """GitHubRegistry with a separate registry URL should emit 5 fields."""
        import mccode_antlr.reader.registry as rm
        calls = {}
        def fake_init(self, name, url, version, filename=None, registry=None, priority=0):
            self.name = name
            self.url = url
            self.version = version
            self.filename = filename or f'{name}-registry.txt'
            self._stashed_registry = registry if isinstance(registry, str) else None
            self.pooch = None
            self.priority = priority
            calls['registry'] = registry
        monkeypatch.setattr(rm.GitHubRegistry, '__init__', fake_init)
        reg = rm.GitHubRegistry('files', 'https://github.com/org/files-repo', 'v2.0',
                                registry='https://github.com/org/registry-repo')
        line = self._to_file_str(reg)
        parts = line[len('Registry:'):].strip().split()
        assert parts == [
            'files',
            'https://github.com/org/files-repo',
            'v2.0',
            'files-registry.txt',
            'https://github.com/org/registry-repo',
        ]

    def test_github_registry_separate_registry_url_roundtrips(self, monkeypatch):
        """Round-trip: to_file then registry_from_specification preserves the registry URL."""
        import mccode_antlr.reader.registry as rm
        captured = {}
        def fake_init(self, name, url, version, filename=None, registry=None, priority=0):
            self.name = name
            self.url = url
            self.version = version
            self.filename = filename or f'{name}-registry.txt'
            self._stashed_registry = registry if isinstance(registry, str) else None
            self.pooch = None
            self.priority = priority
            captured.update(name=name, url=url, version=version, filename=filename, registry=registry)
        monkeypatch.setattr(rm.GitHubRegistry, '__init__', fake_init)

        reg = rm.GitHubRegistry('files', 'https://github.com/org/files-repo', 'v2.0',
                                registry='https://github.com/org/registry-repo')
        line = self._to_file_str(reg)
        spec = line[len('Registry:'):].strip()

        # Reset captured so we can record what registry_from_specification passes
        captured.clear()
        recovered = rm.registry_from_specification(spec)
        assert recovered is not None
        assert captured['name'] == 'files'
        assert captured['url'] == 'https://github.com/org/files-repo'
        assert captured['version'] == 'v2.0'
        assert captured['registry'] == 'https://github.com/org/registry-repo'

    def test_local_registry_roundtrips(self, tmp_path):
        import mccode_antlr.reader.registry as rm
        reg = rm.LocalRegistry('mylib', str(tmp_path))
        line = self._to_file_str(reg)
        spec = line[len('Registry:'):].strip()
        recovered = rm.registry_from_specification(spec)
        assert recovered is not None
        assert recovered.name == 'mylib'
        assert recovered.root == tmp_path.resolve()


# ---------------------------------------------------------------------------
# registries_from_instr_header — header comment scanner
# ---------------------------------------------------------------------------

class TestRegistriesFromInstrHeader:

    def test_no_block_comment_returns_empty(self):
        from mccode_antlr.reader.registry import registries_from_instr_header
        assert registries_from_instr_header('DEFINE INSTRUMENT foo() TRACE END') == []

    def test_comment_without_registry_lines_returns_empty(self):
        from mccode_antlr.reader.registry import registries_from_instr_header
        source = '/* Instrument foo\nSource: foo.instr\n*/\nDEFINE INSTRUMENT foo()\n'
        assert registries_from_instr_header(source) == []

    def test_local_registry_dropped_by_default(self, tmp_path):
        """A header names a directory on whoever wrote the .instr -- not trusted."""
        from mccode_antlr.reader.registry import registries_from_instr_header
        source = f'/* Instrument foo\nRegistry: mylib {tmp_path.as_posix()}\n*/\n'
        assert registries_from_instr_header(source) == []

    def test_local_registry_recovered(self, tmp_path, trusted_local_registries):
        from mccode_antlr.reader.registry import registries_from_instr_header
        source = f'/* Instrument foo\nRegistry: mylib {tmp_path.as_posix()}\n*/\n'
        regs = registries_from_instr_header(source)
        assert len(regs) == 1
        assert regs[0].name == 'mylib'
        assert regs[0].root == tmp_path.resolve()

    def test_nonexistent_local_path_skipped(self, trusted_local_registries):
        """Trusting a non-existent path does not yield a LocalRegistry"""
        from mccode_antlr.reader.registry import registries_from_instr_header
        source = '/* Instrument foo\nRegistry: mylib /nonexistent/path/that/does/not/exist\n*/\n'
        regs = registries_from_instr_header(source)
        assert regs == []

    def test_multiple_registries_recovered(self, tmp_path, trusted_local_registries):
        from mccode_antlr.reader.registry import registries_from_instr_header
        dir_a = tmp_path / 'a'
        dir_b = tmp_path / 'b'
        dir_a.mkdir()
        dir_b.mkdir()
        source = (
            f'/* Instrument foo\n'
            f'Registry: libA {dir_a.as_posix()}\n'
            f'Registry: libB {dir_b.as_posix()}\n'
            f'*/\n'
        )
        regs = registries_from_instr_header(source)
        assert len(regs) == 2
        assert {r.name for r in regs} == {'libA', 'libB'}

    def test_duplicate_names_deduplicated(self, tmp_path, trusted_local_registries):
        from mccode_antlr.reader.registry import registries_from_instr_header
        source = (
            f'/* Instrument foo\n'
            f'Registry: mylib {tmp_path.as_posix()}\n'
            f'Registry: mylib {tmp_path.as_posix()}\n'
            f'*/\n'
        )
        regs = registries_from_instr_header(source)
        assert len(regs) == 1

    def test_unclosed_comment_returns_empty(self, trusted_local_registries):
        """A trusted but malformed registry does not return a LocalRegistry"""
        from mccode_antlr.reader.registry import registries_from_instr_header
        source = '/* Instrument foo\nRegistry: mylib /some/path\n'
        assert registries_from_instr_header(source) == []

    def test_leading_whitespace_ignored(self, tmp_path, trusted_local_registries):
        from mccode_antlr.reader.registry import registries_from_instr_header
        source = f'\n\n/* Instrument foo\nRegistry: mylib {tmp_path.as_posix()}\n*/\n'
        regs = registries_from_instr_header(source)
        assert len(regs) == 1


# ---------------------------------------------------------------------------
# ensure_registries — default/file merge behavior
# ---------------------------------------------------------------------------

class TestEnsureRegistries:
    def test_file_registry_overrides_default_and_warns_on_version_change(self, monkeypatch):
        import mccode_antlr.reader.registry as rm

        default = rm.RemoteRegistry(
            'libc',
            'https://example.com/default',
            'v9',
            'libc-registry.txt',
        )
        file_reg = rm.RemoteRegistry(
            'libc',
            'https://example.com/file',
            'v8',
            'libc-registry.txt',
        )

        warnings = []

        class DummyLogger:
            def warning(self, msg):
                warnings.append(msg)

        monkeypatch.setattr(rm, 'default_registries', lambda flavor: [default])
        monkeypatch.setattr(rm, 'logger', DummyLogger())

        merged = rm.ensure_registries(rm.Flavor.BASE, [file_reg])

        assert len(merged) == 1
        assert merged[0] is file_reg
        assert len(warnings) == 1
        assert 'libc' in warnings[0]
        assert 'v9' in warnings[0]
        assert 'v8' in warnings[0]
        assert 'https://example.com/default' in warnings[0]
        assert 'https://example.com/file' in warnings[0]

    def test_file_registry_overrides_default_and_warns_on_root_change(self, monkeypatch, tmp_path):
        import mccode_antlr.reader.registry as rm

        default = rm.LocalRegistry('components', str(tmp_path / 'default'))
        file_reg = rm.LocalRegistry('components', str(tmp_path / 'file'))

        warnings = []

        class DummyLogger:
            def warning(self, msg):
                warnings.append(msg)

        monkeypatch.setattr(rm, 'default_registries', lambda flavor: [default])
        monkeypatch.setattr(rm, 'logger', DummyLogger())

        merged = rm.ensure_registries(rm.Flavor.BASE, [file_reg])

        assert len(merged) == 1
        assert merged[0] is file_reg
        assert len(warnings) == 1
        assert (tmp_path / 'default').as_posix() in warnings[0]
        assert (tmp_path / 'file').as_posix() in warnings[0]


# ---------------------------------------------------------------------------
# screen_deserialized_registries — LocalRegistry entries restored from an
# untrusted artifact are ignored unless explicitly trusted
# ---------------------------------------------------------------------------

class TestScreenDeserializedRegistries:
    def _mixed(self, tmp_path):
        import mccode_antlr.reader.registry as rm
        local = rm.LocalRegistry('mylib', str(tmp_path))
        remote = rm.RemoteRegistry('remote', 'https://example.com', 'v1', 'r.txt')
        return local, remote

    def test_local_dropped_remote_kept(self, tmp_path):
        import mccode_antlr.reader.registry as rm
        local, remote = self._mixed(tmp_path)
        kept = rm.screen_deserialized_registries([local, remote], 'a test')
        assert kept == [remote]

    def test_kept_when_trusted(self, tmp_path, trusted_local_registries):
        import mccode_antlr.reader.registry as rm
        local, remote = self._mixed(tmp_path)
        assert rm.screen_deserialized_registries([local, remote], 'a test') == [local, remote]

    def test_warning_names_the_root_not_only_the_name(self, tmp_path, caplog):
        """`-I .` produces a registry named '', so the root has to be in the text."""
        import mccode_antlr.reader.registry as rm
        from loguru import logger
        messages = []
        sink = logger.add(lambda m: messages.append(str(m)), level='WARNING')
        try:
            rm.screen_deserialized_registries([rm.LocalRegistry('', str(tmp_path))], 'a test')
        finally:
            logger.remove(sink)
        assert any(tmp_path.as_posix() in m for m in messages)
        assert any('--trust-local-registries' in m for m in messages)

    def test_instr_json_round_trip_drops_local_registries(self, tmp_path):
        """The end-to-end path: a serialized instrument cannot carry a search
        directory into the loading environment."""
        import mccode_antlr.reader.registry as rm
        from mccode_antlr.io import to_json, from_json
        from mccode_antlr.loader import parse_mcstas_instr
        instr = parse_mcstas_instr(
            'DEFINE INSTRUMENT t()\nTRACE\n'
            'COMPONENT o = Progress_bar() AT (0,0,0) ABSOLUTE\nEND\n'
        )
        instr.registries = tuple(instr.registries) + (rm.LocalRegistry('sneaky', str(tmp_path)),)
        back = from_json(to_json(instr))
        assert not any(isinstance(r, rm.LocalRegistry) for r in back.registries)
        assert {r.name for r in back.registries} == {
            r.name for r in instr.registries if not isinstance(r, rm.LocalRegistry)}

    def test_with_local_registries_restores_the_loading_environment(self, tmp_path):
        import mccode_antlr.reader.registry as rm
        from mccode_antlr import Flavor
        from mccode_antlr.io import to_json, from_json
        from mccode_antlr.loader import parse_mcstas_instr
        instr = parse_mcstas_instr(
            'DEFINE INSTRUMENT t()\nTRACE\n'
            'COMPONENT o = Progress_bar() AT (0,0,0) ABSOLUTE\nEND\n'
        )
        back = rm.with_local_registries(from_json(to_json(instr)), Flavor.MCSTAS, [tmp_path])
        roots = [r.root for r in back.registries if isinstance(r, rm.LocalRegistry)]
        assert tmp_path in roots


# ---------------------------------------------------------------------------
# LocalRegistry recursion — the working directory is searched top-level only,
# matching `mcstas`, while -I/--search-dir directories are whole trees
# ---------------------------------------------------------------------------

class TestLocalRegistryRecursion:
    def _tree(self, tmp_path):
        tmp_path.joinpath('Top.comp').write_text('top')
        tmp_path.joinpath('sub').mkdir()
        tmp_path.joinpath('sub', 'Deep.comp').write_text('deep')
        return tmp_path

    def test_recursive_is_the_default(self, tmp_path):
        import mccode_antlr.reader.registry as rm
        assert rm.LocalRegistry('mylib', str(tmp_path)).recursive

    def test_non_recursive_finds_top_level(self, tmp_path):
        import mccode_antlr.reader.registry as rm
        root = self._tree(tmp_path)
        reg = rm.LocalRegistry('wd', str(root), recursive=False)
        assert reg.known('Top', '.comp')
        assert reg.path('Top', '.comp') == root / 'Top.comp'

    def test_non_recursive_ignores_subdirectories(self, tmp_path):
        import mccode_antlr.reader.registry as rm
        root = self._tree(tmp_path)
        assert not rm.LocalRegistry('wd', str(root), recursive=False).known('Deep', '.comp')
        assert rm.LocalRegistry('tree', str(root)).known('Deep', '.comp')

    def test_non_recursive_still_resolves_explicit_relative_paths(self, tmp_path):
        """A name that spells out a subdirectory is a path, not a tree search."""
        import mccode_antlr.reader.registry as rm
        root = self._tree(tmp_path)
        reg = rm.LocalRegistry('wd', str(root), recursive=False)
        assert reg.known('sub/Deep.comp')
        assert reg.path('sub/Deep.comp') == root / 'sub' / 'Deep.comp'

    def test_non_recursive_filenames_and_filetypes_stay_top_level(self, tmp_path):
        from pathlib import Path
        import mccode_antlr.reader.registry as rm
        root = self._tree(tmp_path)
        reg = rm.LocalRegistry('wd', str(root), recursive=False)
        assert [p.name for p in reg._filetype_iterator('comp')] == ['Top.comp']
        assert sorted(Path(f).name for f in reg.filenames()) == ['Top.comp', 'sub']

    def test_recursive_spec_is_unchanged(self, tmp_path):
        import mccode_antlr.reader.registry as rm
        reg = rm.LocalRegistry('mylib', str(tmp_path))
        assert reg.specification_string() == f'mylib {tmp_path.as_posix()}'

    def test_non_recursive_spec_roundtrips(self, tmp_path):
        import mccode_antlr.reader.registry as rm
        reg = rm.LocalRegistry('wd', str(tmp_path), recursive=False)
        spec = reg.specification_string()
        assert spec == f'wd {tmp_path.as_posix()} non-recursive'
        recovered = rm.registry_from_specification(spec)
        assert recovered is not None
        assert not recovered.recursive
        assert recovered == reg

    def test_spec_without_token_is_recursive(self, tmp_path):
        """Specs written before the flag existed describe recursive registries."""
        import mccode_antlr.reader.registry as rm
        for spec in (tmp_path.as_posix(), f'mylib {tmp_path.as_posix()}'):
            assert rm.registry_from_specification(spec).recursive

    def test_serializable_registry_roundtrips_recursion(self, tmp_path):
        import mccode_antlr.reader.registry as rm
        for recursive in (True, False):
            reg = rm.LocalRegistry('wd', str(tmp_path), recursive=recursive)
            back = rm.SerializableRegistry.from_registry(reg).to_registry()
            assert back.recursive is recursive
            assert back == reg

    def test_registries_differing_only_in_recursion_are_unequal(self, tmp_path):
        import mccode_antlr.reader.registry as rm
        assert rm.LocalRegistry('wd', str(tmp_path)) != rm.LocalRegistry('wd', str(tmp_path), recursive=False)


class TestCollectLocalRegistries:
    def test_working_directory_is_not_recursive(self):
        from mccode_antlr import Flavor
        from mccode_antlr.reader.registry import collect_local_registries
        wd = [r for r in collect_local_registries(Flavor.MCSTAS) if r.name == 'working_directory']
        assert len(wd) == 1
        assert not wd[0].recursive

    def test_search_dir_registries_are_recursive(self, tmp_path):
        """-I directories are tree roots, including -I . for the working directory."""
        from mccode_antlr import Flavor
        from mccode_antlr.reader.registry import collect_local_registries, LocalRegistry
        registries = collect_local_registries(Flavor.MCSTAS, [tmp_path])
        specified = [r for r in registries
                     if isinstance(r, LocalRegistry) and r.root == tmp_path]
        assert len(specified) == 1
        assert specified[0].recursive


# ---------------------------------------------------------------------------
# Ambiguous lookups: reported as ambiguity, and survivable by falling through
# to the next registry
# ---------------------------------------------------------------------------

class TestAmbiguousLookup:
    def _two_copies(self, tmp_path, first: str, second: str):
        """A tree with the same component name in two subdirectories."""
        for sub, text in (('a', first), ('b', second)):
            tmp_path.joinpath(sub).mkdir()
            tmp_path.joinpath(sub, 'Dupe.comp').write_text(text)
        import mccode_antlr.reader.registry as rm
        return rm.LocalRegistry('tree', str(tmp_path))

    def test_differing_copies_report_ambiguity(self, tmp_path):
        import pytest
        reg = self._two_copies(tmp_path, 'one', 'two')
        with pytest.raises(RuntimeError) as excinfo:
            reg.fullname('Dupe', '.comp')
        message = str(excinfo.value)
        assert 'Ambiguous' in message
        # The old bug: an ambiguity reported as its opposite
        assert 'No match' not in message
        assert str(tmp_path / 'a' / 'Dupe.comp') in message
        assert str(tmp_path / 'b' / 'Dupe.comp') in message

    def test_identical_copies_still_dedupe(self, tmp_path):
        """Guards the content-hash dedupe -- identical copies are not ambiguous."""
        reg = self._two_copies(tmp_path, 'same', 'same')
        assert reg.fullname('Dupe', '.comp').name == 'Dupe.comp'

    def test_absent_name_still_says_no_match(self, tmp_path):
        import pytest
        import mccode_antlr.reader.registry as rm
        reg = rm.LocalRegistry('tree', str(tmp_path))
        with pytest.raises(RuntimeError, match='No match'):
            reg.fullname('Nothing', '.comp')

    def test_remote_registry_zero_candidates_says_no_match(self):
        """RemoteRegistry.fullname had the mirror-image bug: zero matches were
        reported as 'More than one match' with an empty list."""
        import pytest
        import mccode_antlr.reader.registry as rm

        class _Pooch:
            registry_files = ['some/other.comp']

        reg = rm.RemoteRegistry('remote', 'https://example.com', 'v1', 'r.txt')
        reg.pooch = _Pooch()
        with pytest.raises(RuntimeError) as excinfo:
            reg.fullname('Nothing', '.comp', exact=False)
        assert 'No match' in str(excinfo.value)
        assert 'More than one' not in str(excinfo.value)


class _RaisingRegistry:
    """Claims to know everything, fails to provide anything.

    Priority must outrank LocalRegistry's 10, or Reader's priority sort puts the
    working registry first and the fall-through is never exercised.
    """
    name = 'broken'
    root = None
    version = '0'
    priority = 20

    def known(self, name, ext=None, strict=False):
        return True

    def path(self, name, ext=None):
        raise RuntimeError('deliberately broken')

    contents = path
    fullname = path


class TestReaderFallsThrough:
    def _reader(self, tmp_path, *extra):
        import mccode_antlr.reader.registry as rm
        from mccode_antlr.reader import Reader
        tmp_path.joinpath('Good.comp').write_text('DEFINE COMPONENT Good')
        working = rm.LocalRegistry('good', str(tmp_path))
        return Reader(registries=[*extra, working])

    def test_locate_skips_a_registry_that_cannot_deliver(self, tmp_path):
        reader = self._reader(tmp_path, _RaisingRegistry())
        assert reader.locate('Good', ext='.comp') == tmp_path / 'Good.comp'

    def test_contents_and_fullname_also_fall_through(self, tmp_path):
        reader = self._reader(tmp_path, _RaisingRegistry())
        assert reader.contents('Good', ext='.comp') == 'DEFINE COMPONENT Good'
        assert reader.fullname('Good', ext='.comp') == tmp_path / 'Good.comp'

    def test_all_failing_registries_are_named_in_the_error(self, tmp_path):
        import pytest
        from mccode_antlr.reader import Reader
        first, second = _RaisingRegistry(), _RaisingRegistry()
        second.name = 'also_broken'
        reader = Reader(registries=[first, second])
        with pytest.raises(RuntimeError) as excinfo:
            reader.locate('Anything', ext='.comp')
        message = str(excinfo.value)
        assert 'broken' in message and 'also_broken' in message
        assert 'deliberately broken' in message

    def test_ambiguous_registry_falls_through_to_a_usable_one(self, tmp_path):
        """The original symptom: an ambiguous tree must not abort the lookup."""
        import mccode_antlr.reader.registry as rm
        from mccode_antlr.reader import Reader
        ambiguous = tmp_path / 'ambiguous'
        for sub, text in (('a', 'one'), ('b', 'two')):
            ambiguous.joinpath(sub).mkdir(parents=True)
            ambiguous.joinpath(sub, 'Dupe.comp').write_text(text)
        good = tmp_path / 'good'
        good.mkdir()
        good.joinpath('Dupe.comp').write_text('the real one')
        reader = Reader(registries=[rm.LocalRegistry('ambiguous', str(ambiguous)),
                                    rm.LocalRegistry('good', str(good))])
        assert reader.contents('Dupe', ext='.comp') == 'the real one'

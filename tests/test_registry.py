def test_mccode_pooch_tags():
    from mccode_antlr import Flavor
    from mccode_antlr.reader import default_registries
    for flavor in (Flavor.BASE, Flavor.MCSTAS, Flavor.MCXTRACE,):
        for reg in default_registries(flavor):
            assert reg.version != "main"


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


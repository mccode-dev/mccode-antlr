"""Integration tests for cache populate to catch registry API mismatches.

These tests invoke populate_from_clone() and warm_via_pooch() with different flavor
parameters, which will surface bugs like incorrect loop variable usage where the
parameter is passed to _mccode_pooch_registries() instead of the loop variable.
"""
import pytest
from mccode_antlr import Flavor
from mccode_antlr.cli.cache import cache_populate, populate_from_clone, warm_via_pooch
import mccode_antlr.reader.registry as registry_mod


def test_populate_from_clone_with_flavor_mcstas(tmp_path, monkeypatch):
    """populate_from_clone(flavor=Flavor.MCSTAS) should not error on _mccode_pooch_registries call."""
    clone = _make_dummy_mccode_clone(tmp_path)
    
    # Mock _mccode_pooch_registries to verify it's called with list[str], not Flavor
    call_log = []
    
    def fake_registries(names):
        call_log.append(names)
        if not isinstance(names, list):
            raise TypeError(f"Expected list[str], got {type(names).__name__}")
        return []
    
    monkeypatch.setattr(registry_mod, "_mccode_pooch_registries", fake_registries)
    
    # Should not raise TypeError
    total, errors = populate_from_clone(clone, tag="v3.5.31", flavor=Flavor.MCSTAS)
    
    # Verify _mccode_pooch_registries was called with a list
    assert len(call_log) > 0, "Expected _mccode_pooch_registries to be called"
    assert isinstance(call_log[0], list), f"Expected list, got {type(call_log[0])}"
    assert 'mcstas' in call_log[0], f"Expected 'mcstas' in {call_log[0]}"


def test_populate_from_clone_with_flavor_mcxtrace(tmp_path, monkeypatch):
    """populate_from_clone(flavor=Flavor.MCXTRACE) should not error on _mccode_pooch_registries call."""
    clone = _make_dummy_mccode_clone(tmp_path)
    
    call_log = []
    
    def fake_registries(names):
        call_log.append(names)
        if not isinstance(names, list):
            raise TypeError(f"Expected list[str], got {type(names).__name__}")
        return []
    
    monkeypatch.setattr(registry_mod, "_mccode_pooch_registries", fake_registries)
    
    total, errors = populate_from_clone(clone, tag="v3.5.31", flavor=Flavor.MCXTRACE)
    
    assert len(call_log) > 0
    assert isinstance(call_log[0], list)
    assert 'mcxtrace' in call_log[0]


def test_populate_from_clone_with_flavor_none(tmp_path, monkeypatch):
    """populate_from_clone(flavor=None) should not error on _mccode_pooch_registries call."""
    clone = _make_dummy_mccode_clone(tmp_path)
    
    call_log = []
    
    def fake_registries(names):
        call_log.append(names)
        if not isinstance(names, list):
            raise TypeError(f"Expected list[str], got {type(names).__name__}")
        return []
    
    monkeypatch.setattr(registry_mod, "_mccode_pooch_registries", fake_registries)
    
    total, errors = populate_from_clone(clone, tag="v3.5.31", flavor=None)
    
    # Should call registries twice (once for each flavor)
    assert len(call_log) >= 2
    assert all(isinstance(call, list) for call in call_log)


def test_warm_via_pooch_with_flavor_mcstas(monkeypatch):
    """warm_via_pooch(flavor=Flavor.MCSTAS) should not error on _mccode_pooch_registries call."""
    call_log = []
    
    def fake_registries(names):
        call_log.append(names)
        if not isinstance(names, list):
            raise TypeError(f"Expected list[str], got {type(names).__name__}")
        return []
    
    monkeypatch.setattr(registry_mod, "_mccode_pooch_registries", fake_registries)
    
    total, errors = warm_via_pooch(flavor=Flavor.MCSTAS)
    
    assert len(call_log) > 0
    assert isinstance(call_log[0], list)
    assert 'mcstas' in call_log[0]


def test_warm_via_pooch_with_flavor_mcxtrace(monkeypatch):
    """warm_via_pooch(flavor=Flavor.MCXTRACE) should not error on _mccode_pooch_registries call."""
    call_log = []
    
    def fake_registries(names):
        call_log.append(names)
        if not isinstance(names, list):
            raise TypeError(f"Expected list[str], got {type(names).__name__}")
        return []
    
    monkeypatch.setattr(registry_mod, "_mccode_pooch_registries", fake_registries)
    
    total, errors = warm_via_pooch(flavor=Flavor.MCXTRACE)
    
    assert len(call_log) > 0
    assert isinstance(call_log[0], list)
    assert 'mcxtrace' in call_log[0]


def test_warm_via_pooch_with_flavor_none(monkeypatch):
    """warm_via_pooch(flavor=None) should not error on _mccode_pooch_registries call."""
    call_log = []
    
    def fake_registries(names):
        call_log.append(names)
        if not isinstance(names, list):
            raise TypeError(f"Expected list[str], got {type(names).__name__}")
        return []
    
    monkeypatch.setattr(registry_mod, "_mccode_pooch_registries", fake_registries)
    
    total, errors = warm_via_pooch(flavor=None)
    
    # Should call registries twice (once for each flavor)
    assert len(call_log) >= 2
    assert all(isinstance(call, list) for call in call_log)


class _FakePooch:
    def __init__(self, path, registry_files, registry=None):
        self.path = path
        self.registry_files = registry_files
        self.registry = registry or {}


class _FakeRegistry:
    def __init__(self, name, pooch):
        self.name = name
        self.pooch = pooch


def _registries_with_one_missing_file(tmp_path, monkeypatch):
    """Patch _mccode_pooch_registries to return a single registry whose one
    registry file does not exist under the dummy clone, and return the clone."""
    clone = _make_dummy_mccode_clone(tmp_path)
    cache_dir = tmp_path / "pooch-cache"
    fake_pooch = _FakePooch(str(cache_dir), ["missing-file.dat"])
    fake_reg = _FakeRegistry("mcstas", fake_pooch)

    def fake_registries(names):
        return [fake_reg]

    monkeypatch.setattr(registry_mod, "_mccode_pooch_registries", fake_registries)
    return clone


def _registries_with_one_hash_mismatch(tmp_path, monkeypatch):
    """Patch _mccode_pooch_registries to return a single registry whose one
    registry file exists under the dummy clone but has the wrong content
    (and therefore the wrong hash), and return the clone."""
    clone = _make_dummy_mccode_clone(tmp_path)
    (clone / "mismatched-file.dat").write_text("actual content")
    cache_dir = tmp_path / "pooch-cache"
    fake_pooch = _FakePooch(
        str(cache_dir),
        ["mismatched-file.dat"],
        registry={"mismatched-file.dat": "0" * 64},  # deliberately wrong hash
    )
    fake_reg = _FakeRegistry("mcstas", fake_pooch)

    def fake_registries(names):
        return [fake_reg]

    monkeypatch.setattr(registry_mod, "_mccode_pooch_registries", fake_registries)
    return clone


def test_populate_from_clone_strict_default_prints_error(tmp_path, monkeypatch, capsys):
    """Missing files are reported as ERROR (and counted) when strict is left at its default."""
    clone = _registries_with_one_missing_file(tmp_path, monkeypatch)

    total, errors = populate_from_clone(clone, tag="v3.5.31", flavor=Flavor.MCSTAS)

    out = capsys.readouterr().out
    assert errors == 1
    assert "ERROR: " in out
    assert "not in clone" in out
    assert "WARNING: " not in out


def test_populate_from_clone_lenient_prints_warning(tmp_path, monkeypatch, capsys):
    """Missing files are reported as WARNING (but still counted) when strict=False."""
    clone = _registries_with_one_missing_file(tmp_path, monkeypatch)

    total, errors = populate_from_clone(clone, tag="v3.5.31", flavor=Flavor.MCSTAS, strict=False)

    out = capsys.readouterr().out
    assert errors == 1
    assert "WARNING: " in out
    assert "not in clone" in out
    assert "ERROR: " not in out


def test_populate_from_clone_check_hashes_off_by_default_copies_mismatch(tmp_path, monkeypatch, capsys):
    """With check_hashes left at its default (False), a hash mismatch goes undetected and the file is copied."""
    clone = _registries_with_one_hash_mismatch(tmp_path, monkeypatch)

    total, errors = populate_from_clone(clone, tag="v3.5.31", flavor=Flavor.MCSTAS)

    out = capsys.readouterr().out
    assert errors == 0
    assert total == 1
    assert "hash mismatch" not in out
    assert (tmp_path / "pooch-cache" / "mismatched-file.dat").exists()


def test_populate_from_clone_check_hashes_strict_flags_mismatch_as_error(tmp_path, monkeypatch, capsys):
    """With check_hashes=True and strict (default), a hash mismatch is an ERROR and the file is not copied."""
    clone = _registries_with_one_hash_mismatch(tmp_path, monkeypatch)

    total, errors = populate_from_clone(clone, tag="v3.5.31", flavor=Flavor.MCSTAS, check_hashes=True)

    out = capsys.readouterr().out
    assert errors == 1
    assert total == 0
    assert "ERROR: " in out
    assert "hash mismatch" in out
    assert not (tmp_path / "pooch-cache" / "mismatched-file.dat").exists()


def test_populate_from_clone_check_hashes_lenient_flags_mismatch_as_warning(tmp_path, monkeypatch, capsys):
    """With check_hashes=True and strict=False, a hash mismatch is a WARNING (still not copied)."""
    clone = _registries_with_one_hash_mismatch(tmp_path, monkeypatch)

    total, errors = populate_from_clone(
        clone, tag="v3.5.31", flavor=Flavor.MCSTAS, strict=False, check_hashes=True,
    )

    out = capsys.readouterr().out
    assert errors == 1
    assert total == 0
    assert "WARNING: " in out
    assert "hash mismatch" in out
    assert "ERROR: " not in out


def test_cache_populate_check_hashes_defaults_to_strict_value(tmp_path, monkeypatch):
    """cache_populate should resolve check_hashes=None to follow --strict/--no-strict."""
    captured = {}

    def fake_populate_from_clone(clone, tag, flavor=None, strict=True, check_hashes=False):
        captured['strict'] = strict
        captured['check_hashes'] = check_hashes
        return 0, 0

    monkeypatch.setattr("mccode_antlr.cli.cache.populate_from_clone", fake_populate_from_clone)

    cache_populate(tag="v3.5.31", from_path=str(tmp_path), clone_url="unused", flavor="mcstas")
    assert captured['strict'] is True
    assert captured['check_hashes'] is True

    cache_populate(
        tag="v3.5.31", from_path=str(tmp_path), clone_url="unused", flavor="mcstas", strict=False,
    )
    assert captured['strict'] is False
    assert captured['check_hashes'] is False


def test_cache_populate_check_hashes_explicit_overrides_strict(tmp_path, monkeypatch):
    """An explicit check_hashes value should win over the strict-derived default."""
    captured = {}

    def fake_populate_from_clone(clone, tag, flavor=None, strict=True, check_hashes=False):
        captured['check_hashes'] = check_hashes
        return 0, 0

    monkeypatch.setattr("mccode_antlr.cli.cache.populate_from_clone", fake_populate_from_clone)

    # strict=False (check_hashes would default to False) but explicitly requested True.
    cache_populate(
        tag="v3.5.31", from_path=str(tmp_path), clone_url="unused", flavor="mcstas",
        strict=False, check_hashes=True,
    )
    assert captured['check_hashes'] is True

    # strict=True (check_hashes would default to True) but explicitly requested False.
    cache_populate(
        tag="v3.5.31", from_path=str(tmp_path), clone_url="unused", flavor="mcstas",
        strict=True, check_hashes=False,
    )
    assert captured['check_hashes'] is False


def test_cache_populate_strict_default_exits_nonzero(tmp_path, monkeypatch):
    """cache_populate exits with code 1 when errors occurred and strict is left at its default."""
    monkeypatch.setattr(
        "mccode_antlr.cli.cache.populate_from_clone",
        lambda clone, tag, flavor=None, strict=True, check_hashes=False: (0, 1),
    )

    with pytest.raises(SystemExit) as exc_info:
        cache_populate(tag="v3.5.31", from_path=str(tmp_path), clone_url="unused", flavor="mcstas")

    assert exc_info.value.code == 1


def test_cache_populate_lenient_exits_zero(tmp_path, monkeypatch):
    """cache_populate does not exit non-zero when strict=False, even if errors occurred."""
    monkeypatch.setattr(
        "mccode_antlr.cli.cache.populate_from_clone",
        lambda clone, tag, flavor=None, strict=True, check_hashes=False: (0, 1),
    )

    # Should not raise SystemExit.
    cache_populate(
        tag="v3.5.31", from_path=str(tmp_path), clone_url="unused", flavor="mcstas", strict=False,
    )


def _make_dummy_mccode_clone(tmp_path):
    """Create a minimal McCode repository structure for populate_from_clone().
    
    The pooch registry files are expected at predictable paths within the clone.
    This creates enough structure for populate_from_clone to attempt iteration
    over registries without requiring a full clone.
    """
    clone = tmp_path / "mccode"
    clone.mkdir()
    
    # Create the standard directory structure
    (clone / "src" / "support" / "Python").mkdir(parents=True)
    
    # Create minimal pooch registry files
    # These map to the libc, mcstas, and mcxtrace registries
    (clone / "src" / "support" / "Python" / "pooch-registry.txt").write_text("")
    (clone / "src" / "mcstas" / "pooch-registry.txt").parent.mkdir(parents=True, exist_ok=True)
    (clone / "src" / "mcstas" / "pooch-registry.txt").write_text("")
    (clone / "src" / "mcxtrace" / "pooch-registry.txt").parent.mkdir(parents=True, exist_ok=True)
    (clone / "src" / "mcxtrace" / "pooch-registry.txt").write_text("")
    
    return clone

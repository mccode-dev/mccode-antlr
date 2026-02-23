from mccode_antlr import Flavor


def test_git_fallback_with_missing_module(missing_modules):
    """
    Test that the registry system falls back to local cache when git module is missing.

    This test runs twice:
    1. First with git available to populate the local cache
    2. Then with git module 'missing' to verify fallback mechanism works

    The @cache decorator on _source_registry_tag() needs to be cleared between runs.

    This test uses pytest-missing-modules to simulate the git module being unavailable,
    which allows testing the fallback mechanism even on CI machines with network access.
    """
    import mccode_antlr.reader.registry as registry_module

    # First run: ensure remote components are fetched with git available
    # This populates the local cache
    from mccode_antlr.reader import default_registries

    # Get registries to trigger the remote fetch and cache population
    registries_with_git = default_registries(Flavor.MCSTAS)
    assert len(registries_with_git) > 0

    # Verify we got some registries and they have valid versions
    for reg in registries_with_git:
        assert reg.version != "main", f"Registry {reg.name} should have a specific version, not 'main'"

    # Now verify that local cache was populated
    import pooch
    cache_path = pooch.os_cache('mccodeantlr/libc')
    assert cache_path.exists(), "Local cache should exist after first run"

    # Check that we have at least one version directory in the cache
    version_dirs = [d for d in cache_path.glob('v*') if d.is_dir()]
    assert len(version_dirs) > 0, "Local cache should have version directories"

    # Clear the cache on _source_registry_tag to allow re-evaluation
    registry_module._source_registry_tag.cache_clear()

    # Second run: simulate missing git module
    # Use pytest-missing-modules to make git import fail
    with missing_modules('git'):
        # Test that _get_remote_repository_version_tags returns None when git is missing
        result = registry_module._get_remote_repository_version_tags("https://github.com/test/repo")
        assert result is None, "Should return None when git module is not available"

        # Test that _get_local_version_tags returns cached versions
        local_versions = registry_module._get_local_version_tags()
        assert len(local_versions) > 0, "Should find cached versions when git is unavailable"

        # Now test the full flow: clear cache and get registries again
        registry_module._source_registry_tag.cache_clear()

        # This should work by falling back to local cache
        registries_without_git = default_registries(Flavor.MCSTAS)
        assert len(registries_without_git) > 0, "Should get registries even without git"

        # Verify the registries have valid versions from local cache
        for reg in registries_without_git:
            assert reg.version != "main", f"Registry {reg.name} should use cached version, not 'main'"

        # The versions should match what we got in the first run
        # (they're both using the same cache/resolution)
        assert len(registries_without_git) == len(registries_with_git)


def test_git_command_failure_fallback():
    """
    Test that the registry system falls back to local cache when git ls-remote fails.

    This simulates a network failure scenario where git is available but git ls-remote
    fails due to no network connection.
    """
    import mccode_antlr.reader.registry as registry_module
    from unittest.mock import MagicMock
    from types import ModuleType
    import sys

    # First ensure we have a local cache populated
    from mccode_antlr.reader import default_registries
    registries_first = default_registries(Flavor.MCSTAS)
    assert len(registries_first) > 0

    # Clear the cache to force re-evaluation
    registry_module._source_registry_tag.cache_clear()

    # Create a proper mock git module using types.ModuleType
    mock_git = ModuleType('git')

    # Create the cmd submodule
    mock_git.cmd = ModuleType('git.cmd')

    # Create the exc submodule
    mock_git.exc = ModuleType('git.exc')

    # Create a mock Git class
    mock_git_instance = MagicMock()

    # Create a custom exception class for GitCommandError
    class MockGitCommandError(Exception):
        pass

    # Add GitCommandError to the exc submodule
    mock_git.exc.GitCommandError = MockGitCommandError

    # Make Git() raise the exception when ls_remote is called
    mock_git_instance.ls_remote.side_effect = MockGitCommandError("Network error")
    mock_git.cmd.Git = MagicMock(return_value=mock_git_instance)

    # Patch git in sys.modules so when it's imported inside the function, it gets our mock
    original_git = sys.modules.get('git')
    original_git_cmd = sys.modules.get('git.cmd')
    original_git_exc = sys.modules.get('git.exc')
    try:
        sys.modules['git'] = mock_git
        sys.modules['git.cmd'] = mock_git.cmd
        sys.modules['git.exc'] = mock_git.exc

        # Test that _get_remote_repository_version_tags returns None on git command error
        result = registry_module._get_remote_repository_version_tags("https://github.com/test/repo")
        assert result is None, "Should return None when git command fails"

        # Clear cache again to test full flow
        registry_module._source_registry_tag.cache_clear()

        # This should work by falling back to local cache
        registries_after_failure = default_registries(Flavor.MCSTAS)
        assert len(registries_after_failure) > 0, "Should get registries even when git command fails"

        # Verify the registries have valid versions from local cache
        for reg in registries_after_failure:
            assert reg.version != "main", f"Registry {reg.name} should use cached version, not 'main'"
    finally:
        # Restore original git modules
        if original_git is not None:
            sys.modules['git'] = original_git
        elif 'git' in sys.modules:
            del sys.modules['git']

        if original_git_cmd is not None:
            sys.modules['git.cmd'] = original_git_cmd
        elif 'git.cmd' in sys.modules:
            del sys.modules['git.cmd']

        if original_git_exc is not None:
            sys.modules['git.exc'] = original_git_exc
        elif 'git.exc' in sys.modules:
            del sys.modules['git.exc']

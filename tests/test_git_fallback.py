from mccode_antlr import Flavor


def test_git_fallback():
    """
    Test that the registry system falls back to local cache when git is unavailable.

    This test verifies the fallback mechanism in two phases:
    1. First run with git available to populate the local cache
    2. Second run with git unavailable (simulated by mocking) to verify fallback

    By patching _get_remote_repository_version_tags to return None, we simulate
    what happens when git is unavailable (whether due to module import failure
    or git command failure like network issues). This ensures the fallback to
    local cache works correctly in all such scenarios.
    """
    import mccode_antlr.reader.registry as registry_module
    from unittest.mock import patch
    from mccode_antlr.reader import default_registries

    # First run: ensure remote components are fetched with git available
    # This populates the local cache
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

    # Test fallback when git is unavailable (covers both module missing and command failure)
    # Clear the cache on _source_registry_tag to allow re-evaluation
    registry_module._source_registry_tag.cache_clear()

    # Patch _get_remote_repository_version_tags to return None, simulating git being unavailable.
    # This covers both scenarios: git module import failure and git command failure (e.g., network issues)
    with patch.object(registry_module, '_get_remote_repository_version_tags', return_value=None):
        # Test that _get_local_version_tags returns cached versions
        local_versions = registry_module._get_local_version_tags()
        assert len(local_versions) > 0, "Should find cached versions when git is unavailable"

        # Clear cache again to test full flow with patched function
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


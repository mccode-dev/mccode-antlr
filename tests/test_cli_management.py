"""
Pytest tests for CLI management functions.

UPDATE: The deficiencies in config_set and config_unset have been FIXED!

These tests verify the functionality of config and cache management commands in
src/mccode_antlr/cli/management.py.

ORIGINAL ISSUE (NOW RESOLVED):
Previously, config_set and config_unset only modified in-memory configuration
without persisting changes to disk, causing data loss and user confusion.

FIXES IMPLEMENTED:
1. config_set() NOW properly persists:
   - Reads existing config file
   - Merges new value into existing structure
   - Saves complete config back to disk
   - Preserves all other keys

2. config_unset() NOW properly persists:
   - Reads existing config file
   - Removes only the specified key
   - Saves complete config back to disk
   - Preserves all other keys

The functions now match user expectations and prevent data loss!
"""
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
import yaml
import confuse


class TestConfigManagement:
    """Test suite for configuration management functions."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create a temporary directory for config files."""
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def isolated_config(self, monkeypatch, temp_config_dir):
        """Create an isolated config instance for testing."""
        # Create a test config that won't interfere with the real one
        test_config = confuse.Configuration('mccodeantlr_test', read=False)

        # Set up initial test data
        test_data = {
            'test_key': 'test_value',
            'nested': {
                'key1': 'value1',
                'key2': 'value2'
            },
            'compiler': {
                'flags': '-O2'
            }
        }
        test_config.set(test_data)

        # Override config_dir method to use temp directory
        test_config.config_dir = lambda: str(temp_config_dir)

        # We'll manually inject this into functions that need it
        return test_config, temp_config_dir

    def test_config_dump(self):
        """Test that config_dump properly serializes configuration to YAML."""
        from mccode_antlr.cli.management import config_dump
        from collections import OrderedDict

        test_config = OrderedDict([
            ('key1', 'value1'),
            ('key2', {'nested': 'value'})
        ])

        result = config_dump(test_config)

        assert isinstance(result, str)
        assert 'key1: value1' in result
        assert 'key2:' in result
        assert 'nested: value' in result

    def test_config_list_displays_real_config(self, capsys):
        """Test that config_list prints configuration values from the real config."""
        from mccode_antlr.cli.management import config_list

        config_list(regex=None)

        captured = capsys.readouterr()
        # The real config should have some standard keys
        assert len(captured.out) > 0
        # Should be valid YAML output
        assert ':' in captured.out

    def test_config_get_full_real_config(self, capsys):
        """Test config_get without key returns full configuration."""
        from mccode_antlr.cli.management import config_get

        config_get(key=None, verbose=False)

        captured = capsys.readouterr()
        # Should output something
        assert len(captured.out) > 0

    def test_config_get_nonexistent_key_verbose(self, capsys):
        """Test config_get with nonexistent key and verbose mode."""
        from mccode_antlr.cli.management import config_get

        config_get(key='this_key_definitely_does_not_exist_12345', verbose=True)

        captured = capsys.readouterr()
        assert 'not found' in captured.out.lower()

    def test_config_get_nonexistent_key_silent(self, capsys):
        """Test config_get with nonexistent key silently returns."""
        from mccode_antlr.cli.management import config_get

        config_get(key='this_key_definitely_does_not_exist_12345', verbose=False)

        captured = capsys.readouterr()
        assert captured.out == ''

    def test_config_set_now_persists_to_disk(self, temp_config_dir):
        """
        FIXED: Verify that config_set NOW properly persists changes to disk.

        This test verifies that the deficiency has been fixed - config_set
        now reads the existing config file, merges changes, and saves back
        the complete configuration.
        """
        from mccode_antlr.cli.management import config_set

        config_file = temp_config_dir / 'config.yaml'

        # Create an initial config file with multiple keys
        initial_config = {
            'key1': 'value1',
            'nested': {
                'key2': 'value2',
                'key3': 'value3'
            }
        }
        with config_file.open('w') as f:
            yaml.dump(initial_config, f)

        # Use config_set to change a nested value
        config_set('nested.key2', 'modified_value', str(temp_config_dir))

        # Read the file to verify persistence
        with config_file.open('r') as f:
            saved_config = yaml.safe_load(f)

        # FIXED: All keys should be preserved, and the change should be saved
        assert saved_config['key1'] == 'value1', "key1 should be preserved!"
        assert saved_config['nested']['key2'] == 'modified_value', "nested.key2 should be updated!"
        assert saved_config['nested']['key3'] == 'value3', "nested.key3 should be preserved!"

    def test_config_set_creates_nested_structure(self, temp_config_dir):
        """
        Test that config_set properly creates nested structure when setting new keys.
        """
        from mccode_antlr.cli.management import config_set

        config_file = temp_config_dir / 'config.yaml'

        # Start with simple config
        initial_config = {'existing': 'value'}
        with config_file.open('w') as f:
            yaml.dump(initial_config, f)

        # Add a deeply nested key
        config_set('new.nested.deep.key', 'deep_value', str(temp_config_dir))

        # Verify the structure was created and existing keys preserved
        with config_file.open('r') as f:
            saved_config = yaml.safe_load(f)

        assert saved_config['existing'] == 'value', "Existing key should be preserved!"
        assert saved_config['new']['nested']['deep']['key'] == 'deep_value', "Nested structure should be created!"

    def test_config_unset_now_persists_deletion(self, temp_config_dir):
        """
        FIXED: Verify that config_unset NOW properly persists deletions to disk.

        The deficiency has been fixed - config_unset now reads the existing
        config file, removes the specified key, and saves back the complete
        configuration with other keys preserved.
        """
        from mccode_antlr.cli.management import config_unset

        config_file = temp_config_dir / 'config.yaml'

        # Create initial config
        initial_config = {
            'keep_me': 'value',
            'nested': {
                'remove_me': 'gone',
                'keep_me_too': 'preserved'
            }
        }
        with config_file.open('w') as f:
            yaml.dump(initial_config, f)

        # Unset a nested key
        config_unset('nested.remove_me', str(temp_config_dir))

        # Verify the deletion was persisted and other keys preserved
        with config_file.open('r') as f:
            saved_config = yaml.safe_load(f)

        # FIXED: Key should be removed from file, others preserved
        assert saved_config['keep_me'] == 'value', "Top-level key should be preserved!"
        assert 'remove_me' not in saved_config['nested'], "nested.remove_me should be deleted!"
        assert saved_config['nested']['keep_me_too'] == 'preserved', "nested.keep_me_too should be preserved!"

    def test_config_save_creates_file(self, temp_config_dir):
        """Test that config_save creates a config file."""
        from mccode_antlr.cli.management import config_save

        config_file = temp_config_dir / 'config.yaml'
        assert not config_file.exists()

        config_save(path=str(temp_config_dir), verbose=False)

        assert config_file.exists()

    def test_config_save_writes_yaml(self, temp_config_dir):
        """Test that config_save writes valid YAML."""
        from mccode_antlr.cli.management import config_save

        config_save(path=str(temp_config_dir), verbose=False)

        config_file = temp_config_dir / 'config.yaml'
        with config_file.open('r') as f:
            saved_config = yaml.safe_load(f)

        # Should be a dictionary
        assert isinstance(saved_config, dict)
        # Should have some content from the real config
        assert len(saved_config) > 0

    def test_config_save_verbose_output(self, capsys, temp_config_dir):
        """Test that config_save with verbose prints confirmation."""
        from mccode_antlr.cli.management import config_save

        config_save(path=str(temp_config_dir), verbose=True)

        captured = capsys.readouterr()
        assert 'Configuration written to' in captured.out
        assert 'config.yaml' in captured.out


class TestCacheManagement:
    """Test suite for cache management functions."""

    @pytest.fixture
    def temp_cache(self, monkeypatch):
        """Create a temporary cache directory."""
        with TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir)

            # Mock the cache_path function
            from mccode_antlr.cli import management
            monkeypatch.setattr(management, 'cache_path', lambda: cache_path)

            # Create some test cache structure
            (cache_path / 'package1' / 'v1.0').mkdir(parents=True)
            (cache_path / 'package1' / 'v2.0').mkdir(parents=True)
            (cache_path / 'package2' / 'v1.5').mkdir(parents=True)

            # Add some dummy files
            (cache_path / 'package1' / 'v1.0' / 'data.txt').write_text('test')
            (cache_path / 'package2' / 'v1.5' / 'data.txt').write_text('test')

            yield cache_path

    def test_cache_path_returns_path(self):
        """Test that cache_path returns a valid path."""
        from mccode_antlr.cli.management import cache_path

        path = cache_path()

        assert isinstance(path, (str, Path))
        assert 'mccodeantlr' in str(path).lower()

    def test_cache_list_all(self, capsys, temp_cache):
        """Test cache_list without name shows all packages."""
        from mccode_antlr.cli.management import cache_list

        cache_list(name=None, long=False)

        captured = capsys.readouterr()
        assert 'package1' in captured.out
        assert 'package2' in captured.out

    def test_cache_list_specific_package(self, capsys, temp_cache):
        """Test cache_list with package name shows versions."""
        from mccode_antlr.cli.management import cache_list

        cache_list(name='package1', long=False)

        captured = capsys.readouterr()
        assert 'v1.0' in captured.out or 'package1/v1.0' in captured.out
        assert 'v2.0' in captured.out or 'package1/v2.0' in captured.out

    def test_cache_list_long_format(self, capsys, temp_cache):
        """Test cache_list with long format shows full paths."""
        from mccode_antlr.cli.management import cache_list

        cache_list(name='package1', long=True)

        captured = capsys.readouterr()
        # In long format, we expect to see the full path
        assert 'package1' in captured.out

    def test_cache_remove_specific_version_with_force(self, temp_cache):
        """Test removing a specific version with force flag."""
        from mccode_antlr.cli.management import cache_remove

        version_path = temp_cache / 'package1' / 'v1.0'
        assert version_path.exists()

        cache_remove(name='package1', version='v1.0', force=True)

        assert not version_path.exists()
        # Other versions should still exist
        assert (temp_cache / 'package1' / 'v2.0').exists()

    def test_cache_remove_all_versions_with_force(self, temp_cache):
        """Test removing all versions of a package."""
        from mccode_antlr.cli.management import cache_remove

        package_path = temp_cache / 'package1'
        assert package_path.exists()

        cache_remove(name='package1', version=None, force=True)

        assert not package_path.exists()
        # Other packages should still exist
        assert (temp_cache / 'package2').exists()

    def test_cache_remove_all_with_force(self, temp_cache):
        """Test removing entire cache."""
        from mccode_antlr.cli.management import cache_remove

        assert temp_cache.exists()
        assert (temp_cache / 'package1').exists()
        assert (temp_cache / 'package2').exists()

        cache_remove(name=None, version=None, force=True)

        # The entire cache directory should be removed
        assert not temp_cache.exists()

    def test_cache_remove_without_force_requires_confirmation(self, temp_cache, monkeypatch):
        """Test that cache_remove without force asks for confirmation."""
        from mccode_antlr.cli.management import cache_remove

        # Mock input to decline removal
        monkeypatch.setattr('builtins.input', lambda _: 'n')

        version_path = temp_cache / 'package1' / 'v1.0'
        assert version_path.exists()

        cache_remove(name='package1', version='v1.0', force=False)

        # Should still exist because we declined
        assert version_path.exists()

    def test_cache_remove_with_yes_confirmation(self, temp_cache, monkeypatch):
        """Test that cache_remove accepts 'yes' confirmation."""
        from mccode_antlr.cli.management import cache_remove

        # Mock input to confirm removal
        monkeypatch.setattr('builtins.input', lambda _: 'yes')

        version_path = temp_cache / 'package1' / 'v1.0'
        assert version_path.exists()

        cache_remove(name='package1', version='v1.0', force=False)

        # Should be removed because we confirmed
        assert not version_path.exists()

    def test_cache_remove_with_y_confirmation(self, temp_cache, monkeypatch):
        """Test that cache_remove accepts 'y' confirmation."""
        from mccode_antlr.cli.management import cache_remove

        # Mock input to confirm removal with short form
        monkeypatch.setattr('builtins.input', lambda _: 'y')

        version_path = temp_cache / 'package1' / 'v1.0'
        assert version_path.exists()

        cache_remove(name='package1', version='v1.0', force=False)

        assert not version_path.exists()


class TestParserFunctions:
    """Test the argument parser creation functions."""

    def test_config_management_parser_structure(self):
        """Test that the config parser is properly structured."""
        from mccode_antlr.cli.management import add_config_management_parser
        from argparse import ArgumentParser

        parser = ArgumentParser()
        modes = parser.add_subparsers()
        actions = add_config_management_parser(modes)

        # Verify that the actions subparser was returned
        assert actions is not None

    def test_cache_management_parser_structure(self):
        """Test that the cache parser is properly structured."""
        from mccode_antlr.cli.management import add_cache_management_parser
        from argparse import ArgumentParser

        parser = ArgumentParser()
        modes = parser.add_subparsers()
        actions = add_cache_management_parser(modes)

        assert actions is not None

    def test_mccode_management_parser_creation(self):
        """Test that the main management parser can be created."""
        from mccode_antlr.cli.management import mccode_management_parser

        parser = mccode_management_parser()

        assert parser is not None
        assert parser.prog == "mccode-antlr"

    def test_mccode_management_parser_has_subcommands(self):
        """Test that parser has config and cache subcommands."""
        from mccode_antlr.cli.management import mccode_management_parser

        parser = mccode_management_parser()

        # Try parsing config subcommand
        args = parser.parse_args(['config', 'list'])
        assert hasattr(args, 'action')

        # Try parsing cache subcommand
        args = parser.parse_args(['cache', 'list'])
        assert hasattr(args, 'action')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])


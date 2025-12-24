#!/usr/bin/env python3
"""
Test to verify config_unset preserves other keys.
"""
import tempfile
from pathlib import Path
import yaml


def test_config_unset_preserves_keys():
    """Verify that config_unset only removes the target key and preserves others."""
    from mccode_antlr.cli.management import config_unset

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Manually create an initial config with nested structure
        config_file = tmppath / 'config.yaml'
        initial_config = {
            'compiler': {
                'cc': 'gcc',
                'flags': '-O2',
                'debug': False
            },
            'runtime': {
                'threads': 4,
                'verbose': True
            }
        }
        with config_file.open('w') as f:
            yaml.dump(initial_config, f)

        print("Initial config:")
        print(yaml.dump(initial_config))

        # Now use config_unset to remove a nested key
        config_unset('compiler.debug', str(tmppath))

        # Read back the saved config
        with config_file.open('r') as f:
            saved_config = yaml.safe_load(f)

        print("\nSaved config after unsetting compiler.debug:")
        print(yaml.dump(saved_config))

        # Check if other keys are preserved
        print("\nChecking preserved keys:")
        print(f"  compiler.cc: {'✓' if 'cc' in saved_config.get('compiler', {}) else '✗ MISSING'}")
        print(f"  compiler.flags: {'✓' if 'flags' in saved_config.get('compiler', {}) else '✗ MISSING'}")
        print(f"  compiler.debug: {'✗ REMOVED' if 'debug' not in saved_config.get('compiler', {}) else '✓ (should be removed)'}")
        print(f"  runtime.threads: {'✓' if 'threads' in saved_config.get('runtime', {}) else '✗ MISSING'}")
        print(f"  runtime.verbose: {'✓' if 'verbose' in saved_config.get('runtime', {}) else '✗ MISSING'}")

        # Verify the expected behavior
        assert 'compiler' in saved_config, "compiler section missing!"
        assert 'runtime' in saved_config, "runtime section missing!"
        assert 'debug' not in saved_config['compiler'], "debug key should be removed!"
        assert saved_config['compiler']['cc'] == 'gcc', "cc was lost!"
        assert saved_config['compiler']['flags'] == '-O2', "flags was lost!"
        assert saved_config['runtime']['threads'] == 4, "runtime.threads was lost!"
        assert saved_config['runtime']['verbose'] == True, "runtime.verbose was lost!"


def test_config_unset_entire_section():
    """Test removing an entire section."""
    from mccode_antlr.cli.management import config_unset

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        config_file = tmppath / 'config.yaml'
        initial_config = {
            'compiler': {
                'cc': 'gcc',
                'flags': '-O2'
            },
            'runtime': {
                'threads': 4
            }
        }
        with config_file.open('w') as f:
            yaml.dump(initial_config, f)

        print("\n" + "="*60)
        print("Test: Unsetting entire section")
        print("="*60)
        print("\nInitial config:")
        print(yaml.dump(initial_config))

        # Remove entire compiler section
        config_unset('compiler', str(tmppath))

        with config_file.open('r') as f:
            saved_config = yaml.safe_load(f)

        print("\nSaved config after unsetting compiler:")
        print(yaml.dump(saved_config))

        assert 'compiler' not in saved_config, "compiler section should be removed!"
        assert 'runtime' in saved_config, "runtime section was lost!"
        assert saved_config['runtime']['threads'] == 4, "runtime.threads was lost!"


if __name__ == '__main__':
    test_config_unset_preserves_keys()
    print("\n✅ Test 1 passed!")

    test_config_unset_entire_section()
    print("\n✅ Test 2 passed!")

    print("\n" + "="*60)
    print("All tests passed!")
    print("="*60)


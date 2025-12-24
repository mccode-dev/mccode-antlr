#!/usr/bin/env python3
"""
Test to reproduce the nested key save issue.
"""
import tempfile
from pathlib import Path
import yaml


def test_nested_key_save_issue():
    """Reproduce the issue where setting a nested key only saves that key."""
    from mccode_antlr.cli.management import config_set

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
                'threads': 4
            }
        }
        with config_file.open('w') as f:
            yaml.dump(initial_config, f)

        print("Initial config:")
        print(yaml.dump(initial_config))

        # Now use config_set to update a nested key
        config_set('compiler.flags', '-O3', str(tmppath))

        # Read back the saved config
        with config_file.open('r') as f:
            saved_config = yaml.safe_load(f)

        print("\nSaved config after setting compiler.flags to -O3:")
        print(yaml.dump(saved_config))

        # Check if all keys are preserved
        print("\nChecking preserved keys:")
        print(f"  compiler.cc: {'✓' if 'cc' in saved_config.get('compiler', {}) else '✗ MISSING'}")
        print(f"  compiler.flags: {'✓' if 'flags' in saved_config.get('compiler', {}) else '✗ MISSING'}")
        print(f"  compiler.debug: {'✓' if 'debug' in saved_config.get('compiler', {}) else '✗ MISSING'}")
        print(f"  runtime.threads: {'✓' if 'threads' in saved_config.get('runtime', {}) else '✗ MISSING'}")

        # Verify the issue
        assert 'compiler' in saved_config, "compiler section missing!"
        assert 'runtime' in saved_config, "runtime section missing!"
        assert saved_config['compiler']['flags'] == '-O3', "flags not updated!"
        assert saved_config['compiler']['cc'] == 'gcc', "cc was lost!"
        assert saved_config['runtime']['threads'] == 4, "runtime section was lost!"


if __name__ == '__main__':
    test_nested_key_save_issue()
    print("\n✅ Test passed!")


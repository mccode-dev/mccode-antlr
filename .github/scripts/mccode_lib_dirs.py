"""Read a mccode-pooch-registries libc-registry.txt from stdin and print the
unique parent directories of every listed file, space-separated, to stdout.

Usage (from a CI shell step):
    curl -fsSL <libc-registry.txt URL> | python3 .github/scripts/mccode_lib_dirs.py
"""
import sys

dirs: set[str] = set()
for line in sys.stdin:
    line = line.strip()
    if line and not line.startswith('#'):
        parts = line.split()
        if parts:
            parent = '/'.join(parts[0].split('/')[:-1])
            if parent:
                dirs.add(parent)

print(' '.join(sorted(dirs)))

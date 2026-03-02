"""Pre-populate the mccode-antlr pooch cache for all known registries.

On a cache miss in CI this script shallow-clones the McCode repository and
copies files directly into the pooch cache directory, using git's efficient
pack compression rather than thousands of individual HTTP requests.

Usage:
    # Populate from a local McCode clone (fast: one git pack transfer):
    python3 .github/scripts/warm_pooch_cache.py --tag TAG --clone-url URL

    # Fall back to individual pooch downloads (slow but no git needed):
    python3 .github/scripts/warm_pooch_cache.py --tag TAG
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def clone_mccode(url: str, tag: str, dest: Path) -> Path:
    """Shallow-clone the McCode repository at the given tag into dest."""
    print(f"Cloning {url} at {tag} …", flush=True)
    subprocess.run(
        ['git', 'clone', '--depth=1', '--branch', tag, '--', url, str(dest)],
        check=True,
    )
    return dest


def populate_from_clone(clone: Path, tag: str) -> tuple[int, int]:
    """Copy registry files from a McCode clone into the pooch cache."""
    import pooch as _pooch
    from mccode_antlr import Flavor
    from mccode_antlr.reader.registry import _mccode_pooch_registries

    total = errors = 0
    seen: set[Path] = set()  # avoid duplicate work when flavors share a registry

    for flavor in (Flavor.MCSTAS, Flavor.MCXTRACE):
        for reg in _mccode_pooch_registries(flavor):
            p = getattr(reg, 'pooch', None)
            if p is None or p.path in seen:
                continue
            seen.add(p.path)
            files = list(p.registry_files)
            print(f"  [{reg.name}] copying {len(files)} files into {p.path} …", flush=True)
            for fname in files:
                src = clone / fname
                dst = Path(p.path) / fname
                if not src.exists():
                    print(f"    WARNING: {src} not in clone", flush=True)
                    errors += 1
                    continue
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                total += 1

    return total, errors


def warm_via_pooch(tag: str) -> tuple[int, int]:
    """Fall back to individual pooch downloads (slow)."""
    import pooch as _pooch
    from mccode_antlr import Flavor
    from mccode_antlr.reader.registry import _mccode_pooch_registries

    total = errors = 0
    seen: set = set()

    for flavor in (Flavor.MCSTAS, Flavor.MCXTRACE):
        for reg in _mccode_pooch_registries(flavor):
            p = getattr(reg, 'pooch', None)
            if p is None or id(p) in seen:
                continue
            seen.add(id(p))
            files = list(p.registry_files)
            print(f"  [{reg.name}] downloading {len(files)} files …", flush=True)
            for fname in files:
                try:
                    p.fetch(fname)
                    total += 1
                except Exception as exc:
                    print(f"    WARNING: could not fetch {fname}: {exc}", flush=True)
                    errors += 1

    return total, errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--tag', required=True, help='McCode version tag (e.g. v3.5.31)')
    parser.add_argument('--clone-url', default='https://github.com/mccode-dev/McCode.git',
                        help='McCode git URL to clone on cache miss')
    args = parser.parse_args()

    os.environ.setdefault('MCCODEANTLR_MCCODE_POOCH__TAG', args.tag)

    import pooch as _pooch
    cache_root = _pooch.os_cache('mccodeantlr')
    print(f"Pooch cache root: {cache_root}", flush=True)

    with tempfile.TemporaryDirectory() as tmp:
        clone = clone_mccode(args.clone_url, args.tag, Path(tmp) / 'McCode')
        total, errors = populate_from_clone(clone, args.tag)

    print(f"\nDone. {total} files cached, {errors} errors.", flush=True)
    if errors:
        sys.exit(1)


if __name__ == '__main__':
    main()

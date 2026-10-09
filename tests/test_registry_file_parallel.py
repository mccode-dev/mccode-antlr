"""Registries cached by several processes at the same time."""
import multiprocessing
from pathlib import Path

N = 20000


def _registry_size(cache):
    import pooch
    from mccode_antlr.reader.registry import GitHubRegistry
    pooch.os_cache = lambda name: Path(cache, name)
    files = {f'dir{i}/Comp{i}.comp': 'sha256:' + 'ab' * 32 for i in range(N)}
    try:
        return len(GitHubRegistry('test', 'https://example.invalid/x', 'v1.0', registry=files).pooch.registry)
    except Exception as error:
        return repr(error)


def test_parallel_registry_file(tmp_path):
    with multiprocessing.get_context('spawn').Pool(8) as pool:
        for i in range(5):
            assert pool.map(_registry_size, [str(tmp_path / str(i))] * 8) == [N] * 8

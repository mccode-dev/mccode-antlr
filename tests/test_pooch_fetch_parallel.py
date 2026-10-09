"""Parallel downloads into one pooch cache (https://github.com/fatiando/pooch/issues/555)."""
import functools
import http.server
import multiprocessing
import threading

import pooch

from mccode_antlr.reader.registry import pooch_fetch

NAMES = [f'd{i}/e{i}/f.txt' for i in range(100)]


def _fetch_all(args):
    port, cache = args
    p = pooch.create(path=cache, base_url=f'http://127.0.0.1:{port}/',
                     registry={name: None for name in NAMES})
    failed = []
    for name in NAMES:
        try:
            pooch_fetch(p, name)
        except Exception as error:
            failed.append(f'{name}: {error!r}')
    return failed


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def test_parallel_fetch_into_new_directories(tmp_path):
    served = tmp_path / 'served'
    for name in NAMES:
        (served / name).parent.mkdir(parents=True)
        (served / name).write_text(name)
    server = http.server.ThreadingHTTPServer(
        ('127.0.0.1', 0), functools.partial(_QuietHandler, directory=str(served)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    level = pooch.get_logger().level
    pooch.get_logger().setLevel('WARNING')
    try:
        with multiprocessing.Pool(8) as pool:
            results = pool.map(_fetch_all, [(server.server_address[1], str(tmp_path / 'cache'))] * 8)
    finally:
        pooch.get_logger().setLevel(level)
        server.shutdown()
    assert [f for failed in results for f in failed] == []
    for name in NAMES:
        assert (tmp_path / 'cache' / name).read_text() == name


def test_fetch_retried_on_permission_error(tmp_path):
    class FlakyPooch:
        abspath = tmp_path
        calls = 0

        def fetch(self, filename):
            self.calls += 1
            if self.calls < 3:
                raise PermissionError('in use by another process')
            return str(tmp_path / filename)

    flaky = FlakyPooch()
    assert pooch_fetch(flaky, 'd/f.txt') == tmp_path / 'd' / 'f.txt'
    assert flaky.calls == 3

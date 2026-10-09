"""Option to report registry downloads on one updating line."""
import pooch

from mccode_antlr.reader import registry


class FakePooch:
    def __init__(self, directory, registry_files):
        self.abspath = directory
        self.registry_files = registry_files

    def fetch(self, filename):
        path = self.abspath / filename
        if not path.exists():
            pooch.get_logger().info(f"Downloading file '{filename}'")
            path.write_text('content')
        return str(path)


def test_compact_download_messages(tmp_path, capsys):
    from mccode_antlr.config import config  # (other tests reload it)
    fake = FakePooch(tmp_path, ['a.comp', 'b.comp', 'c.comp', 'd.comp'])
    assert registry._fetch(fake, 'a.comp', 'mcstas') == tmp_path / 'a.comp'
    assert capsys.readouterr().err == ''  # off by default
    previous = config['mccode_pooch']['compact_download_messages'].get()
    config['mccode_pooch']['compact_download_messages'] = True
    try:
        registry._fetch(fake, 'b.comp', 'mcstas')
        registry._fetch(fake, 'b.comp', 'mcstas')  # cached: no update
        registry._fetch(fake, 'c.comp', 'mcstas')
    finally:
        config['mccode_pooch']['compact_download_messages'] = previous
    lines = capsys.readouterr().err.split('\r')
    assert [line.rstrip() for line in lines] == ['', 'mccode-antlr: 2 mcstas files in the local cache',
                                                 'mccode-antlr: 3 mcstas files in the local cache']
    assert all(len(line) == 66 for line in lines[1:])

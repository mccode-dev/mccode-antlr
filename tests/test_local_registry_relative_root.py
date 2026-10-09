"""LocalRegistry with a relative root."""
from mccode_antlr.reader.registry import LocalRegistry


def test_path_with_relative_root(tmp_path, monkeypatch):
    (tmp_path / 'comps').mkdir()
    (tmp_path / 'comps' / 'Dummy.comp').write_text('DEFINE COMPONENT Dummy\nEND\n')
    monkeypatch.chdir(tmp_path)
    path = LocalRegistry('local', 'comps').path('Dummy', '.comp')
    assert path.is_file()
    assert path.resolve() == (tmp_path / 'comps' / 'Dummy.comp').resolve()

"""`mccode-antlr datafile fetch/get` resolution.

_fetch_one used to bind to the first registry whose known() answered True, so a
registry that claimed a data file and then failed to produce it aborted the fetch
rather than letting a later registry supply it.
"""
import pytest


class _Broken:
    """Claims everything, delivers nothing."""
    name = 'broken'
    root = None
    version = '0'
    priority = 20          # tried first

    def known(self, name, ext=None, strict=False):
        return True

    def path(self, name, ext=None):
        raise RuntimeError('registry is unreachable')


class _Working:
    name = 'working'
    root = None
    version = '0'
    priority = 0

    def __init__(self, tmp_path):
        self._file = tmp_path / 'table.dat'
        self._file.write_text('# data\n')

    def known(self, name, ext=None, strict=False):
        return name == 'table.dat'

    def path(self, name, ext=None):
        return self._file


def _patch_registries(monkeypatch, registries):
    import mccode_antlr.cli.datafile as datafile
    monkeypatch.setattr(datafile, '_data_registries', lambda flavor: list(registries))
    return datafile


def test_falls_through_a_registry_that_cannot_deliver(tmp_path, monkeypatch):
    working = _Working(tmp_path)
    datafile = _patch_registries(monkeypatch, [_Broken(), working])
    assert datafile._fetch_one('table.dat', 'mcstas') == working._file


def test_absent_file_still_raises_filenotfound_and_points_at_list(tmp_path, monkeypatch):
    datafile = _patch_registries(monkeypatch, [_Working(tmp_path)])
    with pytest.raises(FileNotFoundError) as excinfo:
        datafile._fetch_one('absent.dat', 'mcstas')
    message = str(excinfo.value)
    assert 'absent.dat' in message
    assert 'datafile list --flavor mcstas' in message


def test_a_delivery_failure_is_not_reported_as_absence(tmp_path, monkeypatch):
    """The reason matters: 'not found' would send the user looking for a missing
    file rather than at an unreachable registry."""
    datafile = _patch_registries(monkeypatch, [_Broken()])
    with pytest.raises(FileNotFoundError) as excinfo:
        datafile._fetch_one('table.dat', 'mcstas')
    assert 'registry is unreachable' in str(excinfo.value)
    assert isinstance(excinfo.value.__cause__, RuntimeError)

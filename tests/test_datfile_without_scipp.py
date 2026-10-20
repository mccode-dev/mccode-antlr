"""McCode .dat files are read, combined and written with numpy alone (#374).

scipp is optional: only ``DatFile.dataset`` and a scan's concatenated monitors need it.
These run with scipp made unimportable, whether or not it is installed.
"""
import logging
import sys
from textwrap import dedent

import numpy as np
import pytest

_DAT1D = dedent("""\
    # Format: McCode with text headers
    # URL: http://www.mccode.org
    # Creator: McStas 3.x
    # Instrument: test_instr
    # Ncount: {ncount}
    # Trace: no
    # Gravitation: no
    # Seed: {seed}
    # Directory: {directory}
    # Param: a=1
    # Date: Mon Jan 1 00:00:00 2024
    # type: array_1d(3)
    # Source: test_instr
    # component: mon
    # position: 0 0 1
    # title: Wavelength monitor
    # Ncount: {ncount}
    # filename: mon.dat
    # statistics: X0=2; dX=1;
    # signal: Min=1; Max=3; Mean=2;
    # values: 6 1 60
    # xvar: L
    # yvar: (I,I_err)
    # xlabel: Wavelength [AA]
    # ylabel: Intensity
    # xlimits: 1 3
    # variables: L I I_err N
    1 1 0.3 10
    2 2 0.4 20
    3 3 0.5 30
""")

_DAT0D = dedent("""\
    # Format: McCode with text headers
    # type: array_0d
    # component: det
    # filename: det.dat
    # variables: I I_err N
    12.5 0.5 100
""")


@pytest.fixture
def no_scipp(monkeypatch):
    from mccode_antlr.loader.datfile import _scipp_available
    monkeypatch.setitem(sys.modules, 'scipp', None)
    _scipp_available.cache_clear()
    yield
    _scipp_available.cache_clear()


def _write(path, ncount=1000, seed=1, directory='one'):
    path.write_text(_DAT1D.format(ncount=ncount, seed=seed, directory=directory))
    return path


def test_a_file_is_read_without_scipp(no_scipp, tmp_path):
    from mccode_antlr.loader.datfile import DatFile1D, DatFile0D, read_mccode_dat
    dat = read_mccode_dat(_write(tmp_path / 'mon.dat'))
    assert isinstance(dat, DatFile1D)
    assert dat.values.shape == (4, 3)
    np.testing.assert_allclose(dat['I'], [1, 2, 3])
    np.testing.assert_allclose(dat['L'], [1, 2, 3])
    assert dat['a'] == '1'
    assert dat.data.shape == (3, 3)

    (tmp_path / 'det.dat').write_text(_DAT0D)
    det = read_mccode_dat(tmp_path / 'det.dat')
    assert isinstance(det, DatFile0D)
    assert det['I'] == pytest.approx(12.5)


def test_the_scipp_view_says_what_it_needs(no_scipp, tmp_path):
    from mccode_antlr.loader.datfile import read_mccode_dat
    dat = read_mccode_dat(_write(tmp_path / 'mon.dat'))
    with pytest.raises(ImportError, match=r'mccode-antlr\[scipp\]'):
        dat.dataset


def test_runs_combine_without_scipp(no_scipp, tmp_path):
    """Two runs of the same instrument combine as one run of all their rays.

    McCode normalises each run's intensity to its own ray count, so intensities are
    averaged, weighted by Ncount; errors are the weighted errors in quadrature over the
    total; counts add; the axis column stays.
    """
    from mccode_antlr.loader.datfile import read_mccode_dat, write_combined_mccode_dats
    one = _write(tmp_path / 'one.dat', ncount=1000, seed=1, directory='one')
    two = _write(tmp_path / 'two.dat', ncount=3000, seed=2, directory='two')
    write_combined_mccode_dats([one, two], tmp_path / 'both.dat')
    both = read_mccode_dat(tmp_path / 'both.dat')
    np.testing.assert_allclose(both['L'], [1, 2, 3])
    np.testing.assert_allclose(both['I'], [1, 2, 3])
    np.testing.assert_allclose(both['I_err'], np.sqrt(10) / 4 * np.array([0.3, 0.4, 0.5]))
    np.testing.assert_allclose(both['N'], [20, 40, 60])
    assert both['Ncount'] == '4000'


def test_runs_are_weighted_by_their_ray_counts(no_scipp, tmp_path):
    """A run of three times the rays counts three times as much, and the header's
    totals describe the combined histogram, not the first run's."""
    from mccode_antlr.loader.datfile import read_mccode_dat
    one = read_mccode_dat(_write(tmp_path / 'one.dat', ncount=1000))
    two = read_mccode_dat(_write(tmp_path / 'two.dat', ncount=3000, seed=2, directory='two'))
    two.values[1] = [5.0, 6.0, 7.0]          # a different intensity in each bin
    both = one + two
    np.testing.assert_allclose(both['I'], [(1 + 3 * 5) / 4, (2 + 3 * 6) / 4, (3 + 3 * 7) / 4])
    total, error, events = (float(x) for x in both['values'].split())
    assert total == pytest.approx(both['I'].sum(), rel=1e-5)
    assert error == pytest.approx(np.sqrt((both['I_err'] ** 2).sum()), rel=1e-5)
    assert events == pytest.approx(120)
    mean = (both['L'] * both['I']).sum() / both['I'].sum()
    assert both['statistics'].startswith(f'X0={mean:g};')
    assert both['signal'] == f"Min={both['I'].min():g}; Max={both['I'].max():g}; Mean={both['I'].mean():g};"


def test_a_run_without_a_ray_count_is_not_combined(no_scipp, tmp_path):
    from mccode_antlr.loader.datfile import read_mccode_dat
    one = read_mccode_dat(_write(tmp_path / 'one.dat'))
    two = read_mccode_dat(_write(tmp_path / 'two.dat', seed=2, directory='two'))
    del two.metadata['Ncount']
    with pytest.raises(RuntimeError, match='Ncount'):
        one + two


def test_files_with_different_bins_do_not_combine(no_scipp, tmp_path):
    from mccode_antlr.loader.datfile import read_mccode_dat
    one = read_mccode_dat(_write(tmp_path / 'one.dat'))
    two = read_mccode_dat(_write(tmp_path / 'two.dat', seed=2, directory='two'))
    two.values[0] += 1
    with pytest.raises(RuntimeError, match="'L'"):
        one + two


def test_a_run_s_monitors_are_collected_without_scipp(no_scipp, tmp_path, caplog):
    """The bug in #374: without scipp every monitor landed in `unrecognized`, silently."""
    from mccode_antlr.run.output import _collect_output
    _write(tmp_path / 'mon.dat')
    (tmp_path / 'det.dat').write_text(_DAT0D)
    (tmp_path / 'broken.dat').write_text('# Format: McCode with text headers\n# type: array_9d\n1 2\n')
    (tmp_path / 'notes.txt').write_bytes(b'\x00\x01 not McCode at all')
    with caplog.at_level(logging.WARNING, logger='mccode_antlr.run.output'):
        out = _collect_output(tmp_path)
    assert sorted(out.dats) == ['det', 'mon']
    assert sorted(p.name for p in out.unrecognized) == ['broken.dat', 'notes.txt']
    # a file that says it is McCode output and is not readable is reported; others are not
    assert 'broken.dat' in caplog.text and 'notes.txt' not in caplog.text


def test_a_missing_package_is_not_an_unrecognized_file(tmp_path):
    from mccode_antlr.run.output import _collect_output, _LOAD_FILTERS, register_output_filter

    def needs_h5py(path):
        raise ImportError('h5py is needed for .h5 files')

    (tmp_path / 'data.h5').write_bytes(b'')
    saved = dict(_LOAD_FILTERS)
    register_output_filter('.h5', needs_h5py)
    try:
        with pytest.raises(ImportError, match='h5py'):
            _collect_output(tmp_path)
    finally:
        _LOAD_FILTERS.clear()
        _LOAD_FILTERS.update(saved)

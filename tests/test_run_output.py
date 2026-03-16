"""Tests for RunOutput/ScanOutput coords accessors and Coords class."""
from __future__ import annotations

import pytest

from mccode_antlr.run.range import Coords, MRange, EList, Singular, _make_scanned_parameter


# ---------------------------------------------------------------------------
# _make_scanned_parameter — bracket-string handling
# ---------------------------------------------------------------------------

class TestMakeScannedParameter:
    def test_bracket_elist(self):
        result = _make_scanned_parameter('[100,200,1000]')
        assert isinstance(result, EList)
        assert result.values == [100, 200, 1000]

    def test_bracket_with_spaces(self):
        result = _make_scanned_parameter(' [1,2,3] ')
        assert isinstance(result, EList)
        assert result.values == [1, 2, 3]

    def test_plain_elist(self):
        result = _make_scanned_parameter('100,200,1000')
        assert isinstance(result, EList)
        assert result.values == [100, 200, 1000]

    def test_mrange(self):
        result = _make_scanned_parameter('0:1:5')
        assert isinstance(result, MRange)
        assert result.start == 0
        assert result.step == 1
        assert result.stop == 5

    def test_singular_int(self):
        result = _make_scanned_parameter('42')
        assert isinstance(result, Singular)
        assert result.value == 42

    def test_singular_float(self):
        result = _make_scanned_parameter('3.14')
        assert isinstance(result, Singular)
        assert pytest.approx(result.value) == 3.14

    def test_singular_string(self):
        result = _make_scanned_parameter('"flag"')
        assert isinstance(result, Singular)
        assert result.value == '"flag"'


# ---------------------------------------------------------------------------
# Coords class
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_coords():
    return Coords({
        'a': MRange(0, 5, 1),
        'b': EList([100, 200, 300]),
        'c': Singular('flag', 6),
    })


class TestCoordsMapping:
    def test_getitem(self, sample_coords):
        assert isinstance(sample_coords['a'], MRange)
        assert isinstance(sample_coords['b'], EList)
        assert isinstance(sample_coords['c'], Singular)

    def test_getitem_missing(self, sample_coords):
        with pytest.raises(KeyError):
            _ = sample_coords['nonexistent']

    def test_len(self, sample_coords):
        assert len(sample_coords) == 3

    def test_iter(self, sample_coords):
        assert list(sample_coords) == ['a', 'b', 'c']

    def test_contains(self, sample_coords):
        assert 'a' in sample_coords
        assert 'z' not in sample_coords

    def test_keys(self, sample_coords):
        assert set(sample_coords.keys()) == {'a', 'b', 'c'}

    def test_values(self, sample_coords):
        vals = list(sample_coords.values())
        assert len(vals) == 3

    def test_items(self, sample_coords):
        items = dict(sample_coords.items())
        assert 'a' in items


class TestCoordsAttrAccess:
    def test_attr(self, sample_coords):
        assert sample_coords.a is sample_coords['a']
        assert sample_coords.b is sample_coords['b']
        assert sample_coords.c is sample_coords['c']

    def test_attr_missing(self, sample_coords):
        with pytest.raises(AttributeError):
            _ = sample_coords.nonexistent

    def test_private_attr_falls_through(self, sample_coords):
        # Internal attributes like _axes should not go through __getattr__
        with pytest.raises(AttributeError):
            _ = sample_coords._nonexistent


class TestCoordsRepr:
    def test_repr_contains_names(self, sample_coords):
        r = repr(sample_coords)
        assert 'a' in r
        assert 'b' in r
        assert 'c' in r
        assert '3 axes' in r

    def test_repr_empty(self):
        assert repr(Coords({})) == 'Coords()'


# ---------------------------------------------------------------------------
# RunOutput.coords
# ---------------------------------------------------------------------------

class TestRunOutputCoords:
    def test_coords_is_coords(self):
        from mccode_antlr.run.output import RunOutput, SimulationOutput
        from pathlib import Path
        import tempfile

        d = Path(tempfile.mkdtemp())
        sim_out = SimulationOutput(directory=d, dats={}, other={}, unrecognized=[], binary_files=[], sim_file=None, tmpdir=None)
        run_out = RunOutput(stdout='', parameters={'x': 1.0, 'y': 2}, output=sim_out)
        c = run_out.coords
        assert isinstance(c, Coords)
        assert 'x' in c
        assert 'y' in c
        assert isinstance(c['x'], Singular)
        assert c['x'].value == 1.0
        assert isinstance(c['y'], Singular)
        assert c['y'].value == 2


# ---------------------------------------------------------------------------
# ScanOutput
# ---------------------------------------------------------------------------

def _make_run_output(params: dict):
    """Helper: create a RunOutput with empty SimulationOutput."""
    from mccode_antlr.run.output import RunOutput, SimulationOutput
    from pathlib import Path
    import tempfile
    d = Path(tempfile.mkdtemp())
    sim_out = SimulationOutput(directory=d, dats={}, other={}, unrecognized=[], binary_files=[], sim_file=None, tmpdir=None)
    return RunOutput(stdout='', parameters=params, output=sim_out)


class TestScanOutputCoords:
    def test_coords_reflects_axes(self):
        from mccode_antlr.run.output import ScanOutput
        axes = {
            'a': MRange(0, 4, 1),
            'b': EList([10, 20]),
        }
        pts = tuple(_make_run_output({'a': i, 'b': 10}) for i in range(5))
        scan = ScanOutput(grid=False, points=pts, axes=axes)
        c = scan.coords
        assert isinstance(c, Coords)
        assert isinstance(c['a'], MRange)
        assert isinstance(c['b'], EList)

    def test_shape_zip(self):
        from mccode_antlr.run.output import ScanOutput
        axes = {'a': MRange(0, 4, 1), 'b': Singular(5, 5)}
        pts = tuple(_make_run_output({'a': i, 'b': 5}) for i in range(5))
        scan = ScanOutput(grid=False, points=pts, axes=axes)
        assert scan.shape == (5,)
        assert scan.ndim == 1

    def test_shape_grid(self):
        from mccode_antlr.run.output import ScanOutput
        axes = {'a': MRange(0, 2, 1), 'b': EList([10, 20, 30])}
        pts = tuple(_make_run_output({'a': i % 3, 'b': 10}) for i in range(9))
        scan = ScanOutput(grid=True, points=pts, axes=axes)
        assert scan.shape == (3, 3)
        assert scan.ndim == 2

    def test_len(self):
        from mccode_antlr.run.output import ScanOutput
        pts = tuple(_make_run_output({'a': i}) for i in range(4))
        scan = ScanOutput(grid=False, points=pts, axes={'a': MRange(0, 3, 1)})
        assert len(scan) == 4

    def test_iter(self):
        from mccode_antlr.run.output import RunOutput, ScanOutput
        pts = tuple(_make_run_output({'a': i}) for i in range(3))
        scan = ScanOutput(grid=False, points=pts, axes={'a': MRange(0, 2, 1)})
        for item in scan:
            assert isinstance(item, RunOutput)

    def test_getitem_int(self):
        from mccode_antlr.run.output import ScanOutput
        pts = tuple(_make_run_output({'a': i}) for i in range(3))
        scan = ScanOutput(grid=False, points=pts, axes={'a': MRange(0, 2, 1)})
        assert scan[0] is pts[0]
        assert scan[-1] is pts[-1]

    def test_getitem_slice(self):
        from mccode_antlr.run.output import ScanOutput
        pts = tuple(_make_run_output({'a': i}) for i in range(5))
        scan = ScanOutput(grid=False, points=pts, axes={'a': MRange(0, 4, 1)})
        sliced = scan[1:3]
        assert len(sliced) == 2


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------

class TestPublicExports:
    def test_run_init_exports(self):
        from mccode_antlr import run
        assert hasattr(run, 'Coords')
        assert hasattr(run, 'RunOutput')
        assert hasattr(run, 'ScanOutput')
        assert hasattr(run, 'MRange')
        assert hasattr(run, 'EList')
        assert hasattr(run, 'Singular')

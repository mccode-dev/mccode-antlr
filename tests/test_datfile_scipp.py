"""Tests for the scipp-backed DatFile classes."""
import unittest
from io import StringIO
from pathlib import Path
from textwrap import dedent
import tempfile

import numpy as np

# ---------------------------------------------------------------------------
# Helpers to write minimal McCode .dat content to a temp file
# ---------------------------------------------------------------------------

_DAT0D = dedent("""\
    # Format: McCode with text headers
    # URL: http://www.mccode.org
    # Creator: McStas 3.x
    # Instrument: test_instr
    # Ncount: 1000000
    # Trace: no
    # Gravitation: no
    # Seed: 12345
    # Directory: .
    # Date: Mon Jan  1 00:00:00 2024
    # type: array_0d
    # Source: test_instr
    # component: Monitor_0D
    # position: 0 0 1
    # title: Monitor 0D
    # Ncount: 1000000
    # filename: mon0d.dat
    # statistics: X0=0; dX=0;
    # signal: Min=0; Max=0; Mean=0;
    # values: 1234.5 6.78 9000
    # yvar: I I_err N
    # ylabel: Intensity
    # xlimits: 0 1
    # variables: I I_err N
    1234.5 6.78 9000
""")

_DAT1D = dedent("""\
    # Format: McCode with text headers
    # URL: http://www.mccode.org
    # Creator: McStas 3.x
    # Instrument: test_instr
    # Ncount: 1000000
    # Trace: no
    # Gravitation: no
    # Seed: 12345
    # Directory: .
    # Date: Mon Jan  1 00:00:00 2024
    # type: array_1d(5)
    # Source: test_instr
    # component: Monitor_1D
    # position: 0 0 2
    # title: Monitor 1D
    # Ncount: 1000000
    # filename: mon1d.dat
    # statistics: X0=2.5; dX=1.5;
    # signal: Min=10; Max=100; Mean=50;
    # values: 250.0 5.0 500
    # xvar: x
    # yvar: (I,I_err)
    # xlabel: x-axis [m]
    # ylabel: Intensity
    # xlimits: 0.5 4.5
    # variables: I I_err N
    1 0.1 10
    2 0.2 20
    3 0.3 30
    4 0.4 40
    5 0.5 50
""")

_DAT2D = dedent("""\
    # Format: McCode with text headers
    # URL: http://www.mccode.org
    # Creator: McStas 3.x
    # Instrument: test_instr
    # Ncount: 1000000
    # Trace: no
    # Gravitation: no
    # Seed: 12345
    # Directory: .
    # Date: Mon Jan  1 00:00:00 2024
    # type: array_2d(3, 2)
    # Source: test_instr
    # component: Monitor_2D
    # position: 0 0 3
    # title: Monitor 2D
    # Ncount: 1000000
    # filename: mon2d.dat
    # statistics: X0=0; dX=1; Y0=0; dY=1;
    # signal: Min=0; Max=100; Mean=50;
    # values: 300.0 10.0 600
    # xvar: x
    # yvar: y
    # xlabel: x-axis [m]
    # ylabel: y-axis [AA]
    # zvar: I
    # zlabel: Intensity
    # xylimits: -1.5 1.5 -1.0 1.0
    # variables: I I_err N
    # Data [Monitor_2D/mon2d.dat] I:
    10 20 30
    40 50 60
    # Errors [Monitor_2D/mon2d.dat] I_err:
    1 2 3
    4 5 6
    # Events [Monitor_2D/mon2d.dat] N:
    100 200 300
    400 500 600
""")


def _write_tmp(content: str, suffix: str = '.dat') -> Path:
    f = tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False)
    f.write(content)
    f.close()
    return Path(f.name)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDatFile0D(unittest.TestCase):
    def setUp(self):
        self.path = _write_tmp(_DAT0D)

    def tearDown(self):
        self.path.unlink(missing_ok=True)

    def _load(self):
        from mccode_antlr.loader.datfile import read_mccode_dat
        return read_mccode_dat(self.path)

    def test_type(self):
        from mccode_antlr.loader.datfile import DatFile0D
        dat = self._load()
        self.assertIsInstance(dat, DatFile0D)

    def test_dataset_keys(self):
        import scipp as sc
        dat = self._load()
        self.assertIn('I', dat.dataset)
        self.assertIn('N', dat.dataset)

    def test_I_value(self):
        dat = self._load()
        self.assertAlmostEqual(float(dat.dataset['I'].value), 1234.5, places=3)

    def test_I_variance(self):
        dat = self._load()
        self.assertAlmostEqual(float(dat.dataset['I'].variance), 6.78 ** 2, places=3)

    def test_N_value(self):
        dat = self._load()
        self.assertAlmostEqual(float(dat.dataset['N'].value), 9000, places=1)

    def test_getitem_I_err(self):
        dat = self._load()
        self.assertAlmostEqual(float(dat['I_err']), 6.78, places=3)

    def test_backward_compat_data_property(self):
        dat = self._load()
        arr = dat.data[0]
        self.assertAlmostEqual(float(arr), 1234.5, places=3)

    def test_backward_compat_variables_property(self):
        dat = self._load()
        self.assertIn('I', dat.variables)
        self.assertIn('N', dat.variables)

    def test_metadata_accessible(self):
        dat = self._load()
        self.assertEqual(dat.metadata['component'], 'Monitor_0D')

    def test_add_combines_correctly(self):
        dat1 = self._load()
        dat2 = self._load()  # independent load
        combined = dat1 + dat2
        self.assertAlmostEqual(float(combined.dataset['I'].value), 2 * 1234.5, places=3)
        # Independent measurements: variances add
        expected_var = 2 * (6.78 ** 2)
        self.assertAlmostEqual(float(combined.dataset['I'].variance), expected_var, places=3)


class TestDatFile1D(unittest.TestCase):
    def setUp(self):
        self.path = _write_tmp(_DAT1D)

    def tearDown(self):
        self.path.unlink(missing_ok=True)

    def _load(self):
        from mccode_antlr.loader.datfile import read_mccode_dat
        return read_mccode_dat(self.path)

    def test_type(self):
        from mccode_antlr.loader.datfile import DatFile1D
        dat = self._load()
        self.assertIsInstance(dat, DatFile1D)

    def test_dataset_keys(self):
        dat = self._load()
        self.assertIn('I', dat.dataset)
        self.assertIn('N', dat.dataset)

    def test_I_shape(self):
        dat = self._load()
        self.assertEqual(dat.dataset['I'].shape, (5,))

    def test_I_values(self):
        dat = self._load()
        np.testing.assert_allclose(dat.dataset['I'].values, [1, 2, 3, 4, 5])

    def test_I_variances(self):
        dat = self._load()
        expected = np.array([0.1, 0.2, 0.3, 0.4, 0.5]) ** 2
        np.testing.assert_allclose(dat.dataset['I'].variances, expected, rtol=1e-5)

    def test_x_coord_present(self):
        dat = self._load()
        self.assertTrue(len(dat.dataset['I'].coords) > 0)

    def test_x_coord_values(self):
        dat = self._load()
        # First coordinate (the x axis) should have 5 bin centres 0.5…4.5
        coord = next(iter(dat.dataset['I'].coords.values()))
        np.testing.assert_allclose(coord.values, [0.5, 1.5, 2.5, 3.5, 4.5], rtol=1e-5)

    def test_x_coord_unit(self):
        import scipp as sc
        dat = self._load()
        coord = next(iter(dat.dataset['I'].coords.values()))
        self.assertEqual(coord.unit, sc.Unit('m'))

    def test_backward_compat_data(self):
        dat = self._load()
        arr = dat.data[0]
        np.testing.assert_allclose(arr, [1, 2, 3, 4, 5])

    def test_getitem_I_err(self):
        dat = self._load()
        err = dat['I_err']
        np.testing.assert_allclose(err, [0.1, 0.2, 0.3, 0.4, 0.5], rtol=1e-5)

    def test_add_propagates_variance(self):
        dat1 = self._load()
        dat2 = self._load()  # independent load
        combined = dat1 + dat2
        expected_var = 2 * np.array([0.1, 0.2, 0.3, 0.4, 0.5]) ** 2
        np.testing.assert_allclose(
            combined.dataset['I'].variances, expected_var, rtol=1e-5
        )
        np.testing.assert_allclose(combined.dataset['I'].values, [2, 4, 6, 8, 10])


class TestDatFile2D(unittest.TestCase):
    def setUp(self):
        self.path = _write_tmp(_DAT2D)

    def tearDown(self):
        self.path.unlink(missing_ok=True)

    def _load(self):
        from mccode_antlr.loader.datfile import read_mccode_dat
        return read_mccode_dat(self.path)

    def test_type(self):
        from mccode_antlr.loader.datfile import DatFile2D
        dat = self._load()
        self.assertIsInstance(dat, DatFile2D)

    def test_I_shape(self):
        dat = self._load()
        self.assertEqual(dat.dataset['I'].shape, (2, 3))

    def test_I_values(self):
        dat = self._load()
        expected = np.array([[10, 20, 30], [40, 50, 60]], dtype=float)
        np.testing.assert_allclose(dat.dataset['I'].values, expected)

    def test_y_coord_unit(self):
        import scipp as sc
        dat = self._load()
        # Find the y coord (named after ylabel label, containing 'angstrom')
        y_coord = None
        for coord in dat.dataset['I'].coords.values():
            if coord.unit == sc.Unit('angstrom'):
                y_coord = coord
                break
        self.assertIsNotNone(y_coord, "Expected a coord with angstrom unit for y-axis [AA]")

    def test_add_propagates_variance(self):
        dat1 = self._load()
        dat2 = self._load()  # independent load
        combined = dat1 + dat2
        expected_I = 2 * np.array([[10, 20, 30], [40, 50, 60]], dtype=float)
        np.testing.assert_allclose(combined.dataset['I'].values, expected_I)
        expected_var = 2 * np.array([[1, 2, 3], [4, 5, 6]], dtype=float) ** 2
        np.testing.assert_allclose(combined.dataset['I'].variances, expected_var)


class TestUnitMapping(unittest.TestCase):
    def test_angstrom(self):
        import scipp as sc
        from mccode_antlr.loader._units import parse_mccode_unit
        self.assertEqual(parse_mccode_unit('AA'), sc.Unit('angstrom'))

    def test_inverse_angstrom(self):
        import scipp as sc
        from mccode_antlr.loader._units import parse_mccode_unit
        self.assertEqual(parse_mccode_unit('AA^-1'), sc.Unit('1/angstrom'))

    def test_microseconds(self):
        import scipp as sc
        from mccode_antlr.loader._units import parse_mccode_unit
        self.assertEqual(parse_mccode_unit('microseconds'), sc.Unit('us'))

    def test_mccode_escape(self):
        import scipp as sc
        from mccode_antlr.loader._units import parse_mccode_unit
        self.assertEqual(parse_mccode_unit('\\gms'), sc.Unit('us'))

    def test_meters(self):
        import scipp as sc
        from mccode_antlr.loader._units import parse_mccode_unit
        self.assertEqual(parse_mccode_unit('m'), sc.Unit('m'))

    def test_label_unit_parsing(self):
        import scipp as sc
        from mccode_antlr.loader._units import parse_mccode_label_unit
        label, unit = parse_mccode_label_unit('x-axis [m]')
        self.assertEqual(label, 'x-axis')
        self.assertEqual(unit, sc.Unit('m'))

    def test_label_without_unit(self):
        import scipp as sc
        from mccode_antlr.loader._units import parse_mccode_label_unit
        label, unit = parse_mccode_label_unit('Intensity')
        self.assertEqual(label, 'Intensity')
        self.assertEqual(unit, sc.Unit('dimensionless'))


if __name__ == '__main__':
    unittest.main()

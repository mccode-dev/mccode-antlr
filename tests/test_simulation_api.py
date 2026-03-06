"""Tests for the Simulation / McStas / McXtrace Python API."""
import unittest
from textwrap import dedent

import pytest

from mccode_antlr.loader import parse_mcstas_instr
from mccode_antlr.test import compiled_test


# ---------------------------------------------------------------------------
# Minimal instrument fixtures
# ---------------------------------------------------------------------------

def _simple_instr(name: str = 'sim_api_test') -> object:
    """Single-parameter instrument that writes the parameter value to stdout."""
    return parse_mcstas_instr(dedent(f"""\
        DEFINE INSTRUMENT {name}(double value=1.0)
        TRACE
        COMPONENT origin = Arm() AT (0, 0, 0) ABSOLUTE
        END
        """))


def _counting_instr(name: str = 'scan_api_test') -> object:
    """Two-parameter instrument for scan tests."""
    return parse_mcstas_instr(dedent(f"""\
        DEFINE INSTRUMENT {name}(double x=0.0, double y=0.0)
        TRACE
        COMPONENT origin = Arm() AT (0, 0, 0) ABSOLUTE
        END
        """))


# ---------------------------------------------------------------------------
# Unit tests (no compilation required)
# ---------------------------------------------------------------------------

class SimulationUnitTests(unittest.TestCase):
    """Tests that do not require a working C compiler."""

    def test_run_before_compile_raises(self):
        from mccode_antlr.run import McStas
        sim = McStas(_simple_instr())
        with self.assertRaises(RuntimeError):
            sim.run()  # no parameters — should still raise before compile check

    def test_scan_before_compile_raises(self):
        from mccode_antlr.run import McStas
        sim = McStas(_simple_instr())
        with self.assertRaises(RuntimeError):
            sim.scan()  # no parameters — should still raise before compile check

    def test_run_rejects_multi_point_string(self):
        """run() should raise if a parameter string resolves to >1 point."""
        from mccode_antlr.run import McStas
        from mccode_antlr.run.simulation import Simulation
        from mccode_antlr import Flavor

        sim = Simulation(_simple_instr(), Flavor.MCSTAS)
        # Inject a fake binary so the compile check passes
        sim._binary = object()
        sim._target = object()
        sim._compile_dir = None

        with self.assertRaises(ValueError):
            sim.run({'value': '1:1:5'})  # resolves to 5 points

    def test_normalize_scan_parameters_string_range(self):
        """_normalize_scan_parameters converts range strings to MRange."""
        from mccode_antlr.run.simulation import Simulation
        from mccode_antlr.run.range import MRange
        from mccode_antlr import Flavor

        sim = Simulation(_simple_instr(), Flavor.MCSTAS)
        result = sim._normalize_scan_parameters({'x': '1:0.5:3'})
        self.assertIn('x', result)
        self.assertIsInstance(result['x'], MRange)

    def test_normalize_scan_parameters_list(self):
        """_normalize_scan_parameters converts Python lists to EList."""
        from mccode_antlr.run.simulation import Simulation
        from mccode_antlr.run.range import EList
        from mccode_antlr import Flavor

        sim = Simulation(_simple_instr(), Flavor.MCSTAS)
        result = sim._normalize_scan_parameters({'x': [1, 2, 3]})
        self.assertIsInstance(result['x'], EList)
        self.assertEqual(list(result['x']), [1, 2, 3])

    def test_normalize_scan_parameters_scalar_becomes_singular(self):
        """_normalize_scan_parameters wraps scalars in Singular."""
        from mccode_antlr.run.simulation import Simulation
        from mccode_antlr.run.range import Singular
        from mccode_antlr import Flavor

        sim = Simulation(_simple_instr(), Flavor.MCSTAS)
        result = sim._normalize_scan_parameters({'x': '1:1:3', 'y': 5.0})
        self.assertIsInstance(result['y'], Singular)
        self.assertEqual(result['y'].value, 5.0)

    def test_normalize_scan_parameters_singular_maximum_set(self):
        """Unbounded Singular objects get a maximum equal to the longest range."""
        from mccode_antlr.run.simulation import Simulation
        from mccode_antlr.run.range import Singular
        from mccode_antlr import Flavor

        sim = Simulation(_simple_instr(), Flavor.MCSTAS)
        result = sim._normalize_scan_parameters({'x': '1:1:5', 'y': 2.0})
        # x has 5 points, so y's Singular should repeat 5 times
        self.assertEqual(result['y'].maximum, 5)

    def test_mcstas_subclass_sets_flavor(self):
        from mccode_antlr.run import McStas
        from mccode_antlr import Flavor
        sim = McStas(_simple_instr())
        self.assertEqual(sim.flavor, Flavor.MCSTAS)

    def test_mcxtrace_subclass_sets_flavor(self):
        from mccode_antlr.run import McXtrace
        from mccode_antlr import Flavor
        sim = McXtrace(_simple_instr())
        self.assertEqual(sim.flavor, Flavor.MCXTRACE)


# ---------------------------------------------------------------------------
# Integration tests (require a working C compiler)
# ---------------------------------------------------------------------------

class SimulationCompileRunTests(unittest.TestCase):
    """Tests that compile and run real instruments."""

    @compiled_test
    def test_compile_returns_self(self):
        """compile() returns the Simulation instance for method chaining."""
        from tempfile import TemporaryDirectory
        from mccode_antlr.run import McStas

        with TemporaryDirectory() as tmpdir:
            sim = McStas(_simple_instr())
            result = sim.compile(tmpdir)
            self.assertIs(result, sim)

    @compiled_test
    def test_compile_skip_if_exists(self):
        """compile() with force=False skips recompilation if binary already exists."""
        from tempfile import TemporaryDirectory
        from mccode_antlr.run import McStas

        with TemporaryDirectory() as tmpdir:
            sim = McStas(_simple_instr())
            sim.compile(tmpdir)
            binary_mtime = sim._binary.stat().st_mtime

            # Compile again without force — should reuse existing binary
            sim.compile(tmpdir, force=False)
            self.assertEqual(binary_mtime, sim._binary.stat().st_mtime)

    @compiled_test
    def test_compile_force_recompiles(self):
        """compile(force=True) rebuilds even when the binary already exists."""
        from tempfile import TemporaryDirectory
        import os
        from mccode_antlr.run import McStas

        with TemporaryDirectory() as tmpdir:
            sim = McStas(_simple_instr())
            sim.compile(tmpdir)
            self.assertIsNotNone(sim._binary)
            self.assertTrue(sim._binary.exists())

            # Overwrite the binary so we can detect it was replaced
            sim._binary.write_bytes(b'placeholder')

            # compile(force=True) should rebuild, replacing the placeholder
            sim.compile(tmpdir, force=True)
            self.assertNotEqual(sim._binary.read_bytes(), b'placeholder')

    @compiled_test
    def test_run_single_point(self):
        """run() executes a single simulation and returns (result, dats)."""
        from tempfile import TemporaryDirectory
        from mccode_antlr.run import McStas

        with TemporaryDirectory() as tmpdir:
            sim = McStas(_simple_instr()).compile(tmpdir)
            result, dats = sim.run({'value': 1.5}, ncount=10, seed=1)
            # result is a bytes object (captured stdout) or similar
            self.assertIsNotNone(result)
            self.assertIsInstance(dats, dict)

    @compiled_test
    def test_run_chained(self):
        """McStas(instr).compile(dir).run(params) works as a one-liner."""
        from tempfile import TemporaryDirectory
        from mccode_antlr.run import McStas

        with TemporaryDirectory() as tmpdir:
            result, dats = McStas(_simple_instr()).compile(tmpdir).run({'value': 2.0}, ncount=5, seed=42)
            self.assertIsNotNone(result)

    @compiled_test
    def test_scan_linear_returns_list(self):
        """scan() with a range returns one (result, dats) per scan point."""
        from tempfile import TemporaryDirectory
        from mccode_antlr.run import McStas

        with TemporaryDirectory() as tmpdir:
            sim = McStas(_counting_instr()).compile(tmpdir)
            results = sim.scan({'x': '1:1:3', 'y': 0.0}, ncount=5, seed=1)
            self.assertEqual(len(results), 3)
            for result, dats in results:
                self.assertIsNotNone(result)
                self.assertIsInstance(dats, dict)

    @compiled_test
    def test_scan_explicit_list(self):
        """scan() accepts a Python list as parameter values."""
        from tempfile import TemporaryDirectory
        from mccode_antlr.run import McStas

        with TemporaryDirectory() as tmpdir:
            sim = McStas(_counting_instr()).compile(tmpdir)
            results = sim.scan({'x': [1.0, 2.0, 3.0], 'y': 0.0}, ncount=5, seed=1)
            self.assertEqual(len(results), 3)

    @compiled_test
    def test_scan_grid(self):
        """scan(grid=True) runs the Cartesian product of parameter ranges."""
        from tempfile import TemporaryDirectory
        from mccode_antlr.run import McStas

        with TemporaryDirectory() as tmpdir:
            sim = McStas(_counting_instr()).compile(tmpdir)
            # 2 x values × 3 y values = 6 points
            results = sim.scan({'x': '1:1:2', 'y': '10:1:12'}, grid=True, ncount=5, seed=1)
            self.assertEqual(len(results), 6)

    @compiled_test
    def test_scan_single_constant_parameter(self):
        """scan() with only a scalar parameter runs once."""
        from tempfile import TemporaryDirectory
        from mccode_antlr.run import McStas

        with TemporaryDirectory() as tmpdir:
            sim = McStas(_simple_instr()).compile(tmpdir)
            results = sim.scan({'value': 1.5}, ncount=5, seed=1)
            self.assertEqual(len(results), 1)

    @compiled_test
    def test_run_with_no_parameters_uses_defaults(self):
        """run() with no parameters passes --yes so binary uses compiled-in defaults."""
        from tempfile import TemporaryDirectory
        from mccode_antlr.run import McStas

        with TemporaryDirectory() as tmpdir:
            sim = McStas(_simple_instr()).compile(tmpdir)
            result, dats = sim.run(ncount=5, seed=1)
            self.assertIsNotNone(result)
            self.assertIsInstance(dats, dict)

    @compiled_test
    def test_run_with_empty_dict_uses_defaults(self):
        """run({}) also passes --yes so the binary uses compiled-in defaults."""
        from tempfile import TemporaryDirectory
        from mccode_antlr.run import McStas

        with TemporaryDirectory() as tmpdir:
            sim = McStas(_simple_instr()).compile(tmpdir)
            result, dats = sim.run({}, ncount=5, seed=1)
            self.assertIsNotNone(result)

    @compiled_test
    def test_scan_with_no_parameters_uses_defaults(self):
        """scan() with no parameters runs once using --yes for compiled-in defaults."""
        from tempfile import TemporaryDirectory
        from mccode_antlr.run import McStas

        with TemporaryDirectory() as tmpdir:
            sim = McStas(_simple_instr()).compile(tmpdir)
            results = sim.scan(ncount=5, seed=1)
            self.assertEqual(len(results), 1)
            result, dats = results[0]
            self.assertIsNotNone(result)


if __name__ == '__main__':
    unittest.main()

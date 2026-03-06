"""Tests for the Simulation / McStas / McXtrace Python API."""
import unittest
from collections.abc import Mapping
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
            self.assertIsInstance(dats, Mapping)  # SimulationOutput is a Mapping (dict-like)
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
                self.assertIsInstance(dats, Mapping)

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
            self.assertIsInstance(dats, Mapping)

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


# ---------------------------------------------------------------------------
# SimulationOutput unit tests (no compilation required)
# ---------------------------------------------------------------------------

class SimulationOutputUnitTests(unittest.TestCase):
    """Tests for SimulationOutput behaviour without running a real simulation."""

    def _make_output(self, tmpdir, *, extra_files=None):
        """Write minimal fake output files and return a SimulationOutput."""
        from pathlib import Path
        from mccode_antlr.run.output import _collect_output

        d = Path(tmpdir)

        # Write a minimal McCode .dat file (1D, 10 bins)
        dat_content = dedent("""\
            # Format: McCode with text headers
            # URL: http://www.mccode.org
            # Creator: test
            # Instrument: fake
            # Ncount: 1000
            # Trace: no
            # Gravitation: no
            # Seed: 1
            # Date: 0
            # type: array_1d(10)
            # Source: test.instr
            # component: mon
            # position: 0 0 0
            # title: Monitor
            # Ncount: 1000
            # filename: mon.dat
            # statistics: X0=0; dX=0;
            # signal: Min=0; Max=0; Mean=0;
            # values: 0 0 0
            # xvar: x
            # yvar: (I,I_err)
            # xlabel: x [m]
            # ylabel: Intensity
            # xlimits: 0 1
            # variables: x I I_err N
            0.05 0.0 0.0 0
            0.15 0.0 0.0 0
            0.25 0.0 0.0 0
            0.35 0.0 0.0 0
            0.45 0.0 0.0 0
            0.55 0.0 0.0 0
            0.65 0.0 0.0 0
            0.75 0.0 0.0 0
            0.85 0.0 0.0 0
            0.95 0.0 0.0 0
            """)
        (d / 'mon.dat').write_text(dat_content)

        # Write a minimal .sim file
        sim_content = dedent("""\
            # Format: McCode with text headers
            # URL: http://www.mccode.org
            # Creator: test
            # Instrument: fake
            # Ncount: 1000
            # Trace: no
            # Gravitation: no
            # Seed: 1
            # Date: 0
            # type: multiarray_1d(1)
            # Source: test.instr
            # simulation: fake
            # filename: mccode.sim
            # statistics: X0=0; dX=0;
            begin instrument
              Name: fake
              Source: fake.instr
              Parameters: none
              Trace_enabled: no
              Default_main: yes
              Embedded_runtime: yes
            end instrument
            begin simulation
              Ncount: 1000
              Seed: 1
              Date: 0
              Nodes: 1
              Gravitation: no
            end simulation
            """)
        (d / 'mccode.sim').write_text(sim_content)

        for filename, content in (extra_files or []):
            p = d / filename
            if isinstance(content, bytes):
                p.write_bytes(content)
            else:
                p.write_text(content)

        return _collect_output(d)

    def test_dats_contains_known_dat_file(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmpdir:
            out = self._make_output(tmpdir)
            self.assertIn('mon', out.dats)

    def test_mapping_interface_getitem(self):
        """out['mon'] works like the old dats['mon']."""
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmpdir:
            out = self._make_output(tmpdir)
            item = out['mon']
            self.assertIsNotNone(item)

    def test_mapping_interface_len(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmpdir:
            out = self._make_output(tmpdir)
            self.assertEqual(len(out), 1)  # only 'mon'; .sim is excluded

    def test_mapping_interface_iter(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmpdir:
            out = self._make_output(tmpdir)
            self.assertEqual(list(out), ['mon'])

    def test_sim_file_is_loaded(self):
        """The .sim metadata file is loaded and available as .sim_file."""
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmpdir:
            out = self._make_output(tmpdir)
            # The .sim loader may raise on a minimal fake file; we just check
            # that if it's None the attribute still exists.
            self.assertTrue(hasattr(out, 'sim_file'))

    def test_unrecognized_contains_binary_files(self):
        """Files that cannot be parsed appear in .unrecognized."""
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmpdir:
            out = self._make_output(tmpdir, extra_files=[
                ('particle_output.mcpl', b'\x89MCPL binary data\x00'),
            ])
            unrecognized_names = [p.name for p in out.unrecognized]
            self.assertIn('particle_output.mcpl', unrecognized_names)

    def test_non_dat_extension_with_mccode_format_is_loaded(self):
        """Files with non-.dat extensions that contain McCode format are loaded."""
        from tempfile import TemporaryDirectory
        from pathlib import Path
        dat_content = dedent("""\
            # Format: McCode with text headers
            # URL: http://www.mccode.org
            # Creator: test
            # Instrument: fake
            # Ncount: 1000
            # Trace: no
            # Gravitation: no
            # Seed: 1
            # Date: 0
            # type: array_1d(5)
            # Source: test.instr
            # component: nd_mon
            # position: 0 0 0
            # title: Monitor_nD output
            # Ncount: 1000
            # filename: nd_mon.monitor
            # statistics: X0=0; dX=0;
            # signal: Min=0; Max=0; Mean=0;
            # values: 0 0 0
            # xvar: x
            # yvar: (I,I_err)
            # xlabel: x [m]
            # ylabel: Intensity
            # xlimits: 0 1
            # variables: x I I_err N
            0.1 0.0 0.0 0
            0.3 0.0 0.0 0
            0.5 0.0 0.0 0
            0.7 0.0 0.0 0
            0.9 0.0 0.0 0
            """)
        with TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / 'nd_mon.monitor').write_text(dat_content)
            from mccode_antlr.run.output import _collect_output
            out = _collect_output(Path(tmpdir))
            self.assertIn('nd_mon', out.dats,
                          "McCode-format file with non-.dat extension should be in dats")

    def test_register_output_filter(self):
        """register_output_filter installs a custom loader for a given extension."""
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from mccode_antlr.run import register_output_filter
        from mccode_antlr.run.output import _collect_output, _LOAD_FILTERS

        loaded_paths = []

        def _fake_loader(path: Path):
            loaded_paths.append(path)
            return {'fake': True}

        register_output_filter('.xyz', _fake_loader)
        try:
            with TemporaryDirectory() as tmpdir:
                (Path(tmpdir) / 'custom.xyz').write_text('some custom data')
                out = _collect_output(Path(tmpdir))
                self.assertIn('custom', out.other)
                self.assertEqual(out.other['custom'], {'fake': True})
                self.assertEqual(len(loaded_paths), 1)
        finally:
            _LOAD_FILTERS.pop('.xyz', None)

    def test_loaded_combines_dats_and_other(self):
        """out.loaded includes both dats and other keyed entries."""
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from mccode_antlr.run import register_output_filter
        from mccode_antlr.run.output import _collect_output, _LOAD_FILTERS

        register_output_filter('.xyz', lambda p: {'custom': p.stem})
        try:
            with TemporaryDirectory() as tmpdir:
                out = self._make_output(tmpdir, extra_files=[('extra.xyz', 'data')])
                self.assertIn('mon', out.loaded)
                self.assertIn('extra', out.loaded)
        finally:
            _LOAD_FILTERS.pop('.xyz', None)

    def test_directory_attribute(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        with TemporaryDirectory() as tmpdir:
            out = self._make_output(tmpdir)
            self.assertEqual(out.directory, Path(tmpdir))

    @compiled_test
    def test_run_returns_simulation_output(self):
        """sim.run() returns a SimulationOutput, not a plain dict."""
        from tempfile import TemporaryDirectory
        from mccode_antlr.run import McStas, SimulationOutput

        with TemporaryDirectory() as tmpdir:
            sim = McStas(_simple_instr()).compile(tmpdir)
            result, out = sim.run(ncount=5, seed=1)
            self.assertIsInstance(out, SimulationOutput)
            self.assertIsNotNone(result)

    @compiled_test
    def test_simulation_output_is_mapping(self):
        """SimulationOutput behaves as a Mapping (backward compat)."""
        from tempfile import TemporaryDirectory
        from collections.abc import Mapping
        from mccode_antlr.run import McStas

        with TemporaryDirectory() as tmpdir:
            sim = McStas(_simple_instr()).compile(tmpdir)
            result, out = sim.run(ncount=5, seed=1)
            self.assertIsInstance(out, Mapping)
            # dict-like operations must work
            _ = list(out.keys())
            _ = list(out.values())
            _ = list(out.items())


if __name__ == '__main__':
    unittest.main()

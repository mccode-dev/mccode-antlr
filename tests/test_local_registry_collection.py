from unittest import TestCase
from pathlib import Path
from mccode_antlr import Flavor
import mccode_antlr.config

MCKEY = 'MCCODEANTLR_MCSTAS__PATHS'
MXKEY = 'MCCODEANTLR_MCXTRACE__PATHS'


class TestLocalRegistryCollection(TestCase):
    def setUp(self):
        from tempfile import mkdtemp
        self.temps = [Path(p) for p in [mkdtemp(), mkdtemp()]]

    def tearDown(self):
        from shutil import rmtree
        for tmp in self.temps:
            rmtree(tmp)

    def assertAllEqual(self, a, b):
        self.assertEqual(len(a), len(b))
        for i, j in zip(a, b):
            self.assertEqual(i, j)

    def assertPaths(self, flavor, paths: list[Path]):
        from importlib import reload
        reload(mccode_antlr.config)
        from mccode_antlr.reader import LocalRegistry as LReg
        from mccode_antlr.reader.registry import REGISTRY_PRIORITY_HIGH as HIGH
        from mccode_antlr.reader.registry import default_registries
        def_regs = default_registries(flavor)
        for x in [LReg(path.stem, path.as_posix(), priority=HIGH) for path in paths]:
            self.assertIn(x, def_regs)

    def test_mcstas_environment_variable_single(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {MCKEY: self.temps[0].as_posix()}):
            self.assertPaths(Flavor.MCSTAS, self.temps[0:1])

    def test_mcxtrace_environment_variable_single(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {MXKEY: self.temps[1].as_posix()}):
            self.assertPaths(Flavor.MCXTRACE, self.temps[1:2])

    def test_mcstas_environment_variable_multi(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {MCKEY: ' '.join(p.as_posix() for p in self.temps)}):
            self.assertPaths(Flavor.MCSTAS, self.temps[0:2])

    def test_mcxtrace_environment_variable_multi(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {MXKEY: ' '.join(p.as_posix() for p in self.temps)}):
            self.assertPaths(Flavor.MCXTRACE, self.temps[0:2])
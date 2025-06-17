from unittest import TestCase
from importlib import reload
from pathlib import Path
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

    def assertPathsAndWorkingDirectory(self, regs, paths: list[Path]):
        from mccode_antlr.reader import LocalRegistry
        ex = [LocalRegistry(path.stem, path.as_posix(), priority=5) for path in paths]
        ex.append(LocalRegistry('working_directory', f'{Path().resolve()}'))
        self.assertAllEqual(regs, ex)

    def test_mcstas_environment_variable_single(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {MCKEY: self.temps[0].as_posix()}):
            reload(mccode_antlr.config)
            from mccode_antlr.reader.registry import collect_local_registries
            self.assertPathsAndWorkingDirectory(collect_local_registries('mcstas'), self.temps[0:1])

    def test_mcxtrace_environment_variable_single(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {MXKEY: self.temps[1].as_posix()}):
            reload(mccode_antlr.config)
            from mccode_antlr.reader.registry import collect_local_registries
            self.assertPathsAndWorkingDirectory(collect_local_registries('mcxtrace'), self.temps[1:2])

    def test_mcstas_environment_variable_multi(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {MCKEY: ' '.join(p.as_posix() for p in self.temps)}):
            reload(mccode_antlr.config)
            from mccode_antlr.reader.registry import collect_local_registries
            self.assertPathsAndWorkingDirectory(collect_local_registries('mcstas'), self.temps[0:2])

    def test_mcxtrace_environment_variable_multi(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {MXKEY: ' '.join(p.as_posix() for p in self.temps)}):
            reload(mccode_antlr.config)
            from mccode_antlr.reader.registry import collect_local_registries
            self.assertPathsAndWorkingDirectory(collect_local_registries('mcxtrace'), self.temps[0:2])
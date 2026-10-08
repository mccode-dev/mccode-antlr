"""The compiler check says nothing, unless the compiler does not work."""
import logging
from types import SimpleNamespace

import pytest

from mccode_antlr.compiler import check


@pytest.fixture
def fresh_check():
    check.simple_instr_compiles.cache_clear()
    yield
    check.simple_instr_compiles.cache_clear()


def _fake_compile(returncode, seen):
    def compile_func(compiler, compiler_flags, binary, linker_flags, source):
        seen.append(source)
        if not returncode:
            binary.write_bytes(b'')
        return [compiler], SimpleNamespace(returncode=returncode, stdout=b'', stderr=b'it broke')
    return compile_func


@pytest.mark.usefixtures('fresh_check')
@pytest.mark.parametrize('returncode', [0, 1])
def test_only_a_failing_check_is_reported(returncode, monkeypatch, capsys, caplog):
    import mccode_antlr.compiler.c as c
    seen = []
    for name in ('linux_compile', 'windows_compile'):
        monkeypatch.setattr(c, name, _fake_compile(returncode, seen))
    monkeypatch.setattr(check, 'check_for_mccode_antlr_compiler', lambda which: True)
    caplog.set_level(logging.DEBUG, logger='mccode_antlr')

    assert check.simple_instr_compiles('cc') is (returncode == 0)

    assert seen and 'check' in seen[0]  # the check instrument was translated and handed to the compiler
    assert capsys.readouterr().out == ''
    messages = [(r.levelname, r.getMessage()) for r in caplog.records if r.name.startswith('mccode_antlr')]
    if returncode:
        assert len(messages) == 1 and messages[0][0] == 'WARNING' and 'it broke' in messages[0][1], messages
    else:
        assert messages == []
    assert logging.getLogger('mccode_antlr').level == logging.DEBUG  # the caller's level is restored

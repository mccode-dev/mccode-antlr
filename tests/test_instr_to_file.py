"""Instr.to_file writes to a file object, or to a file given by name."""
from textwrap import dedent

from mccode_antlr.loader import parse_mcstas_instr
from mccode_antlr.reader.registry import InMemoryRegistry


def _instr():
    reg = InMemoryRegistry("to_file")
    reg.add_comp("Thing", "DEFINE COMPONENT Thing\nTRACE %{\n%}\nEND\n")
    return parse_mcstas_instr(dedent("""DEFINE INSTRUMENT to_file_instr()
    TRACE
    COMPONENT origin = Thing() AT (0, 0, 0) ABSOLUTE
    END
    """), registries=[reg])


def test_to_file_with_a_file_name_or_path(tmp_path):
    instr = _instr()
    expected = instr.to_string(None)
    instr.to_file(str(tmp_path / 'a.instr'))
    instr.to_file(tmp_path / 'b.instr')
    assert (tmp_path / 'a.instr').read_text(encoding='utf-8') == expected
    assert (tmp_path / 'b.instr').read_text(encoding='utf-8') == expected

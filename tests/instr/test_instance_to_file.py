"""Round-trip fidelity of the clauses Instance.to_file writes before COMPONENT.

McInstr.g4 fixes their order:

    component_instance:
      Removable? Cpu? split? Component instance_name Assign component_type ...

so REMOVABLE, CPU and SPLIT must be emitted in that order to re-parse. SPLIT and
REMOVABLE were previously parsed, stored, and then silently dropped on the way
back out, which made an .instr -> .instr round trip produce an instrument that
traces differently from the one it was written from.
"""
from mccode_antlr.common.expression import Expr
from mccode_antlr.common.textwrap import HTMLWrapper, TextWrapper
from mccode_antlr.loader.loader import parse_mccode_instr
from mccode_antlr.reader.registry import InMemoryRegistry

THING = 'DEFINE COMPONENT Thing\nTRACE %{\nSCATTER;\n%}\nEND\n'

CLAUSES = """DEFINE INSTRUMENT clauses()
TRACE
COMPONENT plain = Thing() AT (0, 0, 0) ABSOLUTE
SPLIT 17 COMPONENT split_only = Thing() AT (0, 0, 1) RELATIVE plain
REMOVABLE COMPONENT removable_only = Thing() AT (0, 0, 2) RELATIVE plain
REMOVABLE CPU SPLIT 3 COMPONENT all_three = Thing() AT (0, 0, 3) RELATIVE plain
SPLIT COMPONENT bare_split = Thing() AT (0, 0, 4) RELATIVE plain
END
"""


def _registry():
    reg = InMemoryRegistry('to_file_test')
    reg.add_comp('Thing', THING)
    return reg


def _parse(source=CLAUSES):
    return parse_mccode_instr(source, [_registry()])


def _by_name(instr):
    return {c.name: c for c in instr.components}


def test_clauses_survive_parsing():
    """Baseline: the clauses reach the Instance in the first place."""
    c = _by_name(_parse())
    assert c['plain'].split is None and not c['plain'].removable and not c['plain'].cpu
    assert c['split_only'].split == Expr.integer(17)
    assert c['removable_only'].removable
    assert c['all_three'].removable and c['all_three'].cpu
    assert c['all_three'].split == Expr.integer(3)


def test_to_string_emits_split_and_removable():
    text = _parse().to_string(TextWrapper())
    assert 'SPLIT 17 COMPONENT split_only' in text
    assert 'REMOVABLE COMPONENT removable_only' in text
    # and nothing leaks onto the instance that has neither
    plain = next(ln for ln in text.splitlines() if 'COMPONENT plain' in ln)
    assert 'SPLIT' not in plain and 'REMOVABLE' not in plain


def test_emitted_clause_order_matches_the_grammar():
    """Removable? Cpu? split? Component -- any other order will not re-parse."""
    text = _parse().to_string(TextWrapper())
    line = next(ln for ln in text.splitlines() if 'COMPONENT all_three' in ln)
    assert line.index('REMOVABLE') < line.index('CPU') < line.index('SPLIT') \
        < line.index('COMPONENT')


def test_round_trip_preserves_clauses():
    first = _parse()
    again = parse_mccode_instr(first.to_string(TextWrapper()), [_registry()])

    before, after = _by_name(first), _by_name(again)
    assert set(before) == set(after)
    for name in before:
        assert after[name].split == before[name].split, name
        assert after[name].removable == before[name].removable, name
        assert after[name].cpu == before[name].cpu, name


def test_bare_split_round_trips_as_its_parsed_default():
    """`SPLIT` with no count is normalised to 10 by McInstrVisitor.visitSplit,
    so that -- not a bare SPLIT -- is what a round trip has to preserve."""
    first = _parse()
    assert _by_name(first)['bare_split'].split == Expr.integer(10)

    text = first.to_string(TextWrapper())
    assert 'SPLIT 10 COMPONENT bare_split' in text

    again = parse_mccode_instr(text, [_registry()])
    assert _by_name(again)['bare_split'].split == Expr.integer(10)


def test_html_wrapper_renders_the_clauses():
    """The HTML writer marks them up the way it already marks up CPU."""
    text = _parse().to_string(HTMLWrapper())
    assert '<b>REMOVABLE</b>' in text
    assert '<b>CPU</b>' in text
    assert '<b>SPLIT</b> 17' in text

"""Tests for TRACE-level %include provenance: Instr.included, Instance.source,
the shared Instr.include merge, the Assembler context manager, and to_files."""
import pytest
from mccode_antlr.assembler import Assembler
from mccode_antlr.instr import Instr
from mccode_antlr.loader.loader import parse_mccode_instr
from mccode_antlr.reader.registry import InMemoryRegistry

THING = 'DEFINE COMPONENT Thing\nTRACE %{\nSCATTER;\n%}\nEND\n'

CHILD = """DEFINE INSTRUMENT child(dpar=3.0)
DECLARE %{
double dvar;
%}
INITIALIZE %{
dvar = dpar;
%}
TRACE
COMPONENT c_first = Thing() AT (0, 0, 0.1) RELATIVE base
REMOVABLE COMPONENT c_gone = Thing() AT (0, 0, 0.2) RELATIVE c_first
COMPONENT c_second = Thing() AT (0, 0, 0.3) RELATIVE c_first
END
"""

# A child that stands alone (no references to parent components), for Assembler.include
LONE_CHILD = """DEFINE INSTRUMENT lone(dpar=3.0)
DECLARE %{
double dvar;
%}
TRACE
COMPONENT c_first = Thing() AT (0, 0, 0.1) ABSOLUTE
REMOVABLE COMPONENT c_gone = Thing() AT (0, 0, 0.2) ABSOLUTE
COMPONENT c_second = Thing() AT (0, 0, 0.3) ABSOLUTE
END
"""

PARENT = """DEFINE INSTRUMENT parent(ppar=1.0)
DECLARE %{
double pvar;
%}
TRACE
COMPONENT base = Thing() AT (0, 0, 0) ABSOLUTE
%include "child"
COMPONENT after = Thing() AT (0, 0, 1) RELATIVE base
END
"""

# Three-level hierarchy: g_prev exercises PREVIOUS through the chain (the grandchild
# state is empty at that point), g_base a two-level reference, g_cfirst a one-level one.
GRANDCHILD = """DEFINE INSTRUMENT grandchild(gpar=2.0)
DECLARE %{
double gvar;
%}
TRACE
COMPONENT g_prev = Thing() AT (0, 0, 0.01) RELATIVE PREVIOUS
COMPONENT g_base = Thing() AT (0, 0, 0.02) RELATIVE base
COMPONENT g_cfirst = Thing() AT (0, 0, 0.03) RELATIVE c_first
END
"""

NESTED_CHILD = """DEFINE INSTRUMENT nchild(dpar=3.0)
DECLARE %{
double dvar;
%}
TRACE
COMPONENT c_first = Thing() AT (0, 0, 0.1) RELATIVE base
%include "grandchild"
COMPONENT c_second = Thing() AT (0, 0, 0.3) RELATIVE c_first
END
"""

NESTED_PARENT = """DEFINE INSTRUMENT parent(ppar=1.0)
TRACE
COMPONENT base = Thing() AT (0, 0, 0) ABSOLUTE
%include "nchild"
COMPONENT after = Thing() AT (0, 0, 1) RELATIVE base
END
"""

CYC_A = 'DEFINE INSTRUMENT cyc_a()\nTRACE\nCOMPONENT a1 = Thing() AT (0, 0, 0) ABSOLUTE\n%include "cyc_b"\nEND\n'
CYC_B = 'DEFINE INSTRUMENT cyc_b()\nTRACE\nCOMPONENT b1 = Thing() AT (0, 0, 0) ABSOLUTE\n%include "cyc_a"\nEND\n'
CYC_SELF = 'DEFINE INSTRUMENT cyc_self()\nTRACE\nCOMPONENT s1 = Thing() AT (0, 0, 0) ABSOLUTE\n%include "cyc_self"\nEND\n'
DIAMOND_A = 'DEFINE INSTRUMENT d_a()\nTRACE\nCOMPONENT da1 = Thing() AT (0, 0, 0) ABSOLUTE\n%include "grandchild_solo"\nEND\n'
DIAMOND_B = 'DEFINE INSTRUMENT d_b()\nTRACE\nCOMPONENT db1 = Thing() AT (0, 0, 0) ABSOLUTE\n%include "grandchild_solo"\nEND\n'
DIAMOND_PARENT = ('DEFINE INSTRUMENT dparent()\nTRACE\nCOMPONENT base = Thing() AT (0, 0, 0) ABSOLUTE\n'
                  '%include "d_a"\n%include "d_b"\nEND\n')
GRANDCHILD_SOLO = 'DEFINE INSTRUMENT grandchild_solo()\nTRACE\nCOMPONENT gs1 = Thing() AT (0, 0, 0) ABSOLUTE\nEND\n'


def _registry():
    reg = InMemoryRegistry('include_test')
    reg.add_comp('Thing', THING)
    reg.add_instr('child', CHILD)
    reg.add_instr('lone', LONE_CHILD)
    reg.add_instr('grandchild', GRANDCHILD)
    reg.add_instr('nchild', NESTED_CHILD)
    reg.add_instr('cyc_a', CYC_A)
    reg.add_instr('cyc_b', CYC_B)
    reg.add_instr('cyc_self', CYC_SELF)
    reg.add_instr('d_a', DIAMOND_A)
    reg.add_instr('d_b', DIAMOND_B)
    reg.add_instr('grandchild_solo', GRANDCHILD_SOLO)
    return reg


def _parse_parent():
    return parse_mccode_instr(PARENT, [_registry()])


def test_parse_records_hierarchy():
    instr = _parse_parent()
    assert len(instr.included) == 1
    child = instr.included[0]
    assert child.name == 'child'
    assert tuple(x.name for x in instr.components) == ('base', 'c_first', 'c_second', 'after')
    assert instr.get_component('base').source is None
    assert instr.get_component('after').source is None
    assert instr.get_component('c_first').source == 'child'
    assert instr.get_component('c_second').source == 'child'
    # the child shares Instance objects with the parent
    assert tuple(x.name for x in child.components) == ('c_first', 'c_second')
    assert instr.get_component('c_first') is child.components[0]
    assert instr.get_component('c_second') is child.components[1]
    # cross-file reference resolved to the parent's instance
    assert instr.get_component('c_first').at_relative[1] is instr.get_component('base')
    # merged content
    assert instr.has_parameter('dpar') and instr.has_parameter('ppar')
    assert any('double dvar;' in block.source for block in instr.declare)


def test_json_round_trip():
    from mccode_antlr.io import to_json, from_json
    instr = _parse_parent()
    ret = from_json(to_json(instr))
    assert type(ret) is Instr
    assert ret == instr
    assert ret.get_component('c_first') is ret.included[0].components[0]


def test_msgpack_round_trip():
    from mccode_antlr.io import to_msgpack, from_msgpack
    instr = _parse_parent()
    ret = from_msgpack(to_msgpack(instr))
    assert type(ret) is Instr
    assert ret == instr
    assert ret.get_component('c_first') is ret.included[0].components[0]


def test_to_files_reconstructs_hierarchy(tmp_path):
    instr = _parse_parent()
    path = instr.to_files(tmp_path)
    parent_text = path.read_text()
    assert parent_text.count('%include "child.instr"') == 1
    assert 'c_first' not in parent_text
    assert 'c_second' not in parent_text
    assert 'dvar' not in parent_text
    child_path = tmp_path / 'child.instr'
    assert child_path.exists()
    child_text = child_path.read_text()
    assert 'COMPONENT c_first' in child_text and 'COMPONENT c_second' in child_text
    assert 'double dvar;' in child_text
    # the written pair reparses to the same structure
    reg = InMemoryRegistry('reparse_test')
    reg.add_comp('Thing', THING)
    reg.add_instr('child', child_text)
    again = parse_mccode_instr(parent_text, [reg])
    assert tuple(x.name for x in again.components) == tuple(x.name for x in instr.components)
    assert tuple(x.type.name for x in again.components) == tuple(x.type.name for x in instr.components)
    assert tuple(x.source for x in again.components) == tuple(x.source for x in instr.components)
    assert tuple(x.name for x in again.included) == tuple(x.name for x in instr.included)
    assert tuple(p.name for p in again.parameters) == tuple(p.name for p in instr.parameters)
    # write→reparse pads block text with newlines, so compare stripped C text
    assert [b.source.strip() for b in again.declare] == [b.source.strip() for b in instr.declare]


def test_flat_output_unchanged():
    instr = _parse_parent()
    text = str(instr)
    assert 'COMPONENT c_first' in text
    assert 'double dvar;' in text
    assert 'Contains: "%include child"' in text
    # the only %include mention is the header comment
    assert text.count('%include') == 1


def test_assembler_context_manager():
    a = Assembler('demo', registries=[_registry()])
    origin = a.component('origin', 'Thing', at=(0, 0, 0))
    with a.included('sub') as s:
        g1 = s.component('g1', 'Thing', at=((0, 0, 1), 'origin'))
    assert len(a.instrument.included) == 1
    assert a.instrument.included[0].name == 'sub'
    assert g1.source == 'sub'
    assert a.instrument.get_component('g1') is g1
    assert g1.at_relative[1] is origin


def test_assembler_context_manager_no_merge_on_error():
    a = Assembler('demo', registries=[_registry()])
    a.component('origin', 'Thing', at=(0, 0, 0))
    with pytest.raises(RuntimeError, match='deliberate'):
        with a.included('sub') as s:
            s.component('g1', 'Thing', at=(0, 0, 1))
            raise RuntimeError('deliberate')
    assert a.instrument.included == ()
    assert not a.instrument.has_component_named('g1')


def test_assembler_include_method():
    child = parse_mccode_instr(LONE_CHILD, [_registry()])
    assert any(x.removable for x in child.components)  # standalone parse keeps REMOVABLE
    a = Assembler('demo', registries=[_registry()])
    a.component('origin', 'Thing', at=(0, 0, 0))
    a.include(child)
    assert a.instrument.included[0].name == 'lone'
    assert not a.instrument.has_component_named('c_gone')
    assert a.instrument.get_component('c_first').source == 'lone'
    assert a.instrument.has_parameter('dpar')
    assert any('double dvar;' in block.source for block in a.instrument.declare)


def test_assembler_rawc_provenance():
    a = Assembler('demo', registries=[_registry()])
    a.declare('double x;')
    assert a.instrument.declare[-1].filename == 'demo.instr'
    with a.included('sub') as s:
        s.declare('double y;')
    blocks = {block.source: block.filename for block in a.instrument.declare}
    assert blocks['double x;'] == 'demo.instr'
    assert blocks['double y;'] == 'sub.instr'


def test_copy_preserves_hierarchy():
    instr = _parse_parent()
    dup = instr.copy()
    assert tuple(x.name for x in dup.included) == ('child',)
    # the copy's child components are the copy's own instances, not the originals
    assert dup.included[0].components[0] is dup.get_component('c_first')
    assert dup.included[0].components[0] is not instr.get_component('c_first')


def test_split_strips_hierarchy():
    instr = _parse_parent()
    first, second = instr.split('c_first')
    for part in (first, second):
        assert part.included == ()
        assert all(x.source is None for x in part.components)
    # the original is untouched
    assert instr.get_component('c_first').source == 'child'


def _parse_nested():
    return parse_mccode_instr(NESTED_PARENT, [_registry()])


def test_nested_parse_records_tree():
    instr = _parse_nested()
    assert tuple(x.name for x in instr.components) == (
        'base', 'c_first', 'g_prev', 'g_base', 'g_cfirst', 'c_second', 'after')
    tags = {x.name: x.source for x in instr.components}
    assert tags['base'] is None and tags['after'] is None
    assert tags['c_first'] == 'nchild' and tags['c_second'] == 'nchild'
    assert all(tags[g] == 'grandchild' for g in ('g_prev', 'g_base', 'g_cfirst'))
    child = instr.included[0]
    assert child.name == 'nchild'
    grand = child.included[0]
    assert grand.name == 'grandchild'
    # sharing across all three levels: the same object in parent, child, and grandchild
    g_base = instr.get_component('g_base')
    assert g_base is grand.components[1]
    assert any(x is g_base for x in child.components)


def test_nested_cross_file_references():
    instr = _parse_nested()
    c_first = instr.get_component('c_first')
    assert instr.get_component('g_prev').at_relative[1] is c_first  # PREVIOUS through the chain
    assert instr.get_component('g_base').at_relative[1] is instr.get_component('base')  # two levels up
    assert instr.get_component('g_cfirst').at_relative[1] is c_first  # one level up


def test_nested_round_trip():
    from mccode_antlr.io import to_json, from_json, to_msgpack, from_msgpack
    instr = _parse_nested()
    for ret in (from_json(to_json(instr)), from_msgpack(to_msgpack(instr))):
        assert type(ret) is Instr
        assert ret == instr
        assert ret.get_component('g_base') is ret.included[0].included[0].components[1]
        assert any(x is ret.get_component('g_base') for x in ret.included[0].components)


def test_nested_to_files(tmp_path):
    instr = _parse_nested()
    path = instr.to_files(tmp_path)
    parent_text = path.read_text()
    assert parent_text.count('%include "nchild.instr"') == 1
    assert 'grandchild.instr' not in parent_text
    assert 'c_first' not in parent_text and 'g_base' not in parent_text
    child_text = (tmp_path / 'nchild.instr').read_text()
    assert 'COMPONENT c_first' in child_text and 'COMPONENT c_second' in child_text
    assert child_text.count('%include "grandchild.instr"') == 1
    assert 'COMPONENT g_' not in child_text
    grand_text = (tmp_path / 'grandchild.instr').read_text()
    for name in ('g_prev', 'g_base', 'g_cfirst'):
        assert f'COMPONENT {name}' in grand_text
    # the trio reparses to the same structure
    reg = InMemoryRegistry('nested_reparse')
    reg.add_comp('Thing', THING)
    reg.add_instr('nchild', child_text)
    reg.add_instr('grandchild', grand_text)
    again = parse_mccode_instr(parent_text, [reg])
    assert tuple(x.name for x in again.components) == tuple(x.name for x in instr.components)
    assert tuple(x.source for x in again.components) == tuple(x.source for x in instr.components)
    assert tuple(x.name for x in again.included) == ('nchild',)
    assert tuple(x.name for x in again.included[0].included) == ('grandchild',)


def test_include_cycle_raises():
    with pytest.raises(RuntimeError, match='cycle'):
        parse_mccode_instr(CYC_A, [_registry()])
    with pytest.raises(RuntimeError, match='cycle'):
        parse_mccode_instr(CYC_SELF, [_registry()])


def test_repeated_include_raises():
    a = Assembler('demo', registries=[_registry()])
    a.include('lone')
    with pytest.raises(RuntimeError, match='more than once'):
        a.include('lone')


def test_diamond_include_raises():
    with pytest.raises(RuntimeError, match='more than once'):
        parse_mccode_instr(DIAMOND_PARENT, [_registry()])


def test_assembler_nested_context_manager():
    a = Assembler('demo', registries=[_registry()])
    origin = a.component('origin', 'Thing', at=(0, 0, 0))
    with a.included('outer') as o:
        o.component('o1', 'Thing', at=((0, 0, 1), 'origin'))
        with o.included('inner') as i:
            i1 = i.component('i1', 'Thing', at=((0, 0, 2), 'origin'))
    assert tuple(x.name for x in a.instrument.included) == ('outer',)
    assert tuple(x.name for x in a.instrument.included[0].included) == ('inner',)
    assert a.instrument.get_component('o1').source == 'outer'
    assert a.instrument.get_component('i1').source == 'inner'
    assert a.instrument.get_component('i1') is i1
    assert i1.at_relative[1] is origin


def test_reinclude_absorbed_raises():
    reg = _registry()
    child = parse_mccode_instr(LONE_CHILD, [reg])
    a1 = Assembler('demo', registries=[reg])
    a1.include(child)
    a2 = Assembler('other', registries=[reg])
    with pytest.raises(RuntimeError, match='detached'):
        a2.include(child)
    a2.include(child.detached())
    # the two instruments hold independent instances
    mine, theirs = a2.instrument.get_component('c_first'), a1.instrument.get_component('c_first')
    assert mine is not theirs
    assert mine.source == 'lone' and theirs.source == 'lone'
    # mutating one instrument's instance leaves the other untouched
    mine.GROUP('only_mine')
    assert theirs.group is None


def test_merged_assembler_guard():
    a = Assembler('demo', registries=[_registry()])
    a.component('origin', 'Thing', at=(0, 0, 0))
    with a.included('sub') as s:
        s.component('g1', 'Thing', at=(0, 0, 1))
    with pytest.raises(RuntimeError, match='already merged'):
        s.component('late', 'Thing', at=(0, 0, 2))
    with pytest.raises(RuntimeError, match='already merged'):
        s.declare('double z;')
    assert not a.instrument.has_component_named('late')
    # a body that raises leaves the child usable (nothing merged)
    with pytest.raises(RuntimeError, match='deliberate'):
        with a.included('sub2') as s2:
            raise RuntimeError('deliberate')
    s2.component('fine', 'Thing', at=(0, 0, 3))
    assert s2.instrument.has_component_named('fine')
    assert not a.instrument.has_component_named('fine')

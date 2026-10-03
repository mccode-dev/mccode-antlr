"""C array initializers in DECLARE/INITIALIZE blocks, and their use as vector values.

``double edges[4] = {1.0, 2.0, 3.0, 4.0};`` in a DECLARE block used to reach
``Expr.parse``, whose ``expr`` rule has no brace list: ANTLR's error recovery dropped
the ``{`` and kept only ``1.0``. Arrays assigned in INITIALIZE were tracked by the C
evaluator but never returned. And a component parameter referring to a known array
(``slit_edges=edges``) could not be evaluated, because ``Expr.evaluate`` ignored
vector-valued symbols.
"""
from textwrap import dedent

import pytest

from mccode_antlr.common.expression import Expr
from mccode_antlr.translators.c_evaluator import CBlockEvaluator, evaluate_c_block_evaluator
from mccode_antlr.translators.c_listener import (
    extract_c_declared_expressions, evaluate_c_defined_expressions,
)


def declared(block: str) -> dict[str, Expr]:
    return {d.name: e for d, e in extract_c_declared_expressions(block).items()}


def test_expr_parse_brace_list():
    expr = Expr.parse('{1.0, 2.0, 3.0, 4.0}')
    assert expr.is_vector
    assert expr.value == [1.0, 2.0, 3.0, 4.0]


@pytest.mark.parametrize('declaration, values', [
    ('double edges[4] = {1.0, 2.0, 3.0, 4.0};', [1.0, 2.0, 3.0, 4.0]),
    ('double edges[] = {1.0, 2.0};', [1.0, 2.0]),
    # unlisted elements are zero, as in C
    ('double edges[4] = {1.0, 2.0};', [1.0, 2.0, 0, 0]),
    # C99 designators; an undesignated value follows the previous one
    ('double edges[5] = {[3]=7.0, 8.0, [0]=1.0};', [1.0, 0, 0, 7.0, 8.0]),
    # a two-dimensional array flattens row-major, as it is laid out in memory
    ('double grid[2][2] = {{1, 2}, {3, 4}};', [1, 2, 3, 4]),
    ('double grid[2][3] = {{1, 2}, {3, 4, 5}};', [1, 2, 3, 4, 5, 0]),
    ('int n[3] = {1, 2*3, 10 - 6};', [1, 6, 4]),
])
def test_declared_array_initializer(declaration, values):
    (expr,) = declared(declaration).values()
    assert expr.is_vector
    assert expr.value == values


def test_declared_char_array_is_still_a_string():
    (expr,) = declared('char name[16] = "hello";').values()
    assert expr.is_str
    assert expr.value == '"hello"'


def test_initialize_updates_declared_arrays():
    variables = declared('double edges[4] = {1.0, 2.0, 3.0, 4.0}; double later[3]; double x = 2; double s;')
    result = evaluate_c_defined_expressions(variables, dedent("""\
        later[0] = x;
        later[1] = 2 * x;
        later[2] = 3;
        edges[1] = 20.0;
        s = edges[2] + later[1];
        """))
    assert result['edges'].value == [1.0, 20.0, 3.0, 4.0]
    assert result['later'].value == [2, 4, 3]
    assert result['s'].value == 7.0


def test_initialize_fills_an_array_in_a_loop():
    variables = declared('double edges[3] = {1, 2, 3}; double shifted[3];')
    result = evaluate_c_defined_expressions(
        variables, 'for (int i = 0; i < 3; i++) shifted[i] = edges[i] + 5;')
    assert result['shifted'].value == [6, 7, 8]


def test_initialize_declaration_of_an_array():
    """An INITIALIZE-local array with an initializer is tracked like a declared one."""
    evaluator = evaluate_c_block_evaluator('double e[4] = {[1]=2.0, 3.0};')
    assert {i: e.value for i, e in evaluator.array_state['e'].items()} == {0: 0, 1: 2.0, 2: 3.0, 3: 0}


def test_struct_designated_initializer():
    evaluator = evaluate_c_block_evaluator('struct {double x; double y;} p = {.y = 2.0, .x = 1.0};')
    assert {k: v.value for k, v in evaluator.struct_state['p'].items()} == {'x': 1.0, 'y': 2.0}


def test_evaluate_known_array():
    known = declared('double edges[4] = {1.0, 2.0, 3.0, 4.0}; int i = 2;')
    whole = Expr.parse('edges').evaluate(known)
    assert whole.vector_known and whole.value == [1.0, 2.0, 3.0, 4.0]
    assert Expr.parse('edges[2]').evaluate(known).value == 3.0
    assert Expr.parse('2*edges[i] + 1').evaluate(known).value == 7.0
    # out-of-range indexes stay symbolic rather than guessing
    assert not Expr.parse('edges[9]').evaluate(known).is_constant


def test_vector_component_parameter_folds_to_the_declared_array():
    """The niess.scaffold pattern: DECLARE + INITIALIZE, then fold a vector parameter."""
    from mccode_antlr.loader import parse_mcstas_instr
    from mccode_antlr.reader.registry import InMemoryRegistry

    registry = InMemoryRegistry('c_initializers')
    registry.add_comp('chopper', dedent("""\
        DEFINE COMPONENT chopper
        SETTING PARAMETERS (vector slit_edges=NULL, int n_edges=2)
        TRACE
        %{
        %}
        END
        """))
    instr = parse_mcstas_instr(dedent("""\
        DEFINE INSTRUMENT c_initializers(dummy=0)
        DECLARE %{
        double edges[4] = {-10.0, 10.0, 170.0, 190.0};
        double shifted[4];
        %}
        INITIALIZE %{
        for (int i = 0; i < 4; i++) shifted[i] = edges[i] + 5;
        %}
        TRACE
        COMPONENT a = chopper(slit_edges=edges, n_edges=4) AT (0, 0, 0) ABSOLUTE
        COMPONENT b = chopper(slit_edges=shifted, n_edges=4) AT (0, 0, 1) ABSOLUTE
        END
        """), registries=[registry])
    block = '\n'.join(raw.source for raw in instr.declare)
    known = evaluate_c_defined_expressions(
        declared(block), '\n'.join(raw.source for raw in instr.initialize))
    folded = {c.name: c.get_parameter('slit_edges').value.evaluate(known).value for c in instr.components}
    assert folded == {'a': [-10.0, 10.0, 170.0, 190.0], 'b': [-5.0, 15.0, 175.0, 195.0]}

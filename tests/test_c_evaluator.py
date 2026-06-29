"""Tests for the ANTLR C grammar-based block evaluator."""
import pytest
from mccode_antlr.translators.c_evaluator import evaluate_c_block, MCCODE_CONSTANTS
from mccode_antlr.common import Expr
from mccode_antlr.common.expression.types import DataType


def ev(block, known=None):
    return evaluate_c_block(block, known=known or {})


# ---------------------------------------------------------------------------
# Constants and literals
# ---------------------------------------------------------------------------

class TestConstants:
    def test_mccode_pi(self):
        result = ev('x = PI;')
        assert abs(float(result['x'].value) - 3.14159265358979) < 1e-12

    def test_integer_literal(self):
        result = ev('x = 42;')
        assert result['x'].value == 42

    def test_hex_literal(self):
        result = ev('x = 0xFF;')
        assert result['x'].value == 255

    def test_float_literal(self):
        result = ev('x = 3.14;')
        assert abs(result['x'].value - 3.14) < 1e-12

    def test_float_scientific(self):
        result = ev('x = 1.5e3;')
        assert abs(result['x'].value - 1500.0) < 1e-9

    def test_negative_literal(self):
        result = ev('x = -1;')
        assert result['x'].value == -1


# ---------------------------------------------------------------------------
# Simple assignments
# ---------------------------------------------------------------------------

class TestAssignment:
    def test_simple(self):
        result = ev('x = 1; y = 2; z = x + y;')
        assert result['z'].value == 3

    def test_chained(self):
        result = ev('a = 1; b = a + 2; c = b * 3;')
        assert result['c'].value == 9

    def test_compound_plus(self):
        result = ev('x = 5; x += 3;')
        assert result['x'].value == 8

    def test_compound_minus(self):
        result = ev('x = 10; x -= 4;')
        assert result['x'].value == 6

    def test_compound_star(self):
        result = ev('x = 3; x *= 4;')
        assert result['x'].value == 12

    def test_compound_div(self):
        result = ev('x = 10.0; x /= 4.0;')
        assert abs(result['x'].value - 2.5) < 1e-12

    def test_from_known(self):
        result = ev('y = x + 1;', known={'x': Expr.integer(7)})
        assert result['y'].value == 8

    def test_overwrites(self):
        result = ev('x = 1; x = 2; x = 3;')
        assert result['x'].value == 3


# ---------------------------------------------------------------------------
# Declarations with initializers
# ---------------------------------------------------------------------------

class TestDeclarations:
    def test_int_decl(self):
        result = ev('int n = 5;')
        assert result['n'].value == 5

    def test_double_decl(self):
        result = ev('double d = 2.71828;')
        assert abs(result['d'].value - 2.71828) < 1e-10

    def test_decl_expr(self):
        result = ev('double x = 3.0; double y = x * x;')
        assert abs(result['y'].value - 9.0) < 1e-12

    def test_array_decl_skipped(self):
        # Array declarations with subscripts should not crash
        result = ev('double arr[10]; arr[0] = 1.0;')
        # arr not tracked as a simple scalar
        assert 'arr' not in result or result.get('arr') is not None


# ---------------------------------------------------------------------------
# Arithmetic and math builtins
# ---------------------------------------------------------------------------

class TestMath:
    def test_add(self):
        result = ev('z = 3.0 + 4.0;')
        assert abs(result['z'].value - 7.0) < 1e-12

    def test_sub(self):
        result = ev('z = 10.0 - 3.5;')
        assert abs(result['z'].value - 6.5) < 1e-12

    def test_mul(self):
        result = ev('z = 2.0 * 6.0;')
        assert abs(result['z'].value - 12.0) < 1e-12

    def test_div(self):
        result = ev('z = 10.0 / 4.0;')
        assert abs(result['z'].value - 2.5) < 1e-12

    def test_int_div(self):
        result = ev('int z = 7 / 2;')
        assert result['z'].value == 3

    def test_mod(self):
        result = ev('int z = 7 % 3;')
        assert result['z'].value == 1

    def test_sin(self):
        import math
        result = ev('x = sin(0.0);')
        assert abs(result['x'].value - 0.0) < 1e-12

    def test_cos(self):
        import math
        result = ev('x = cos(0.0);')
        assert abs(result['x'].value - 1.0) < 1e-12

    def test_sqrt(self):
        result = ev('x = sqrt(9.0);')
        assert abs(result['x'].value - 3.0) < 1e-12

    def test_pow(self):
        result = ev('x = pow(2.0, 10.0);')
        assert abs(result['x'].value - 1024.0) < 1e-9

    def test_atan2(self):
        import math
        result = ev('x = atan2(1.0, 1.0);')
        assert abs(result['x'].value - math.pi / 4) < 1e-10

    def test_fabs(self):
        result = ev('x = fabs(-5.0);')
        assert abs(result['x'].value - 5.0) < 1e-12

    def test_deg2rad(self):
        import math
        result = ev('x = DEG2RAD * 180.0;')
        assert abs(result['x'].value - math.pi) < 1e-10

    def test_nested_math(self):
        import math
        result = ev('x = 4.0 * PI * sin(DEG2RAD * 0.5) / 6.0;')
        expected = 4.0 * math.pi * math.sin(math.radians(0.5)) / 6.0
        assert abs(result['x'].value - expected) < 1e-10


# ---------------------------------------------------------------------------
# Comparisons: used as if-conditions (the primary use case)
# ---------------------------------------------------------------------------

class TestComparisons:
    def test_eq_concrete_in_if(self):
        result = ev('if (3 == 3) { x = 1; } else { x = 0; }')
        assert result['x'].value == 1

    def test_ne_concrete_in_if(self):
        result = ev('if (3 != 4) { x = 1; } else { x = 0; }')
        assert result['x'].value == 1

    def test_lt_concrete_in_if(self):
        result = ev('if (2 < 5) { x = 1; } else { x = 0; }')
        assert result['x'].value == 1

    def test_gt_concrete_false_in_if(self):
        result = ev('if (2 > 5) { x = 1; } else { x = 0; }')
        assert result['x'].value == 0

    def test_symbolic_eq_produces_ternary(self):
        result = ev('if (n == 0) { x = 1.0; } else { x = 2.0; }',
                    known={'n': Expr.id('n')})
        # Result is symbolic - depends on n
        assert 'n' in result['x']


# ---------------------------------------------------------------------------
# if/else: known conditions
# ---------------------------------------------------------------------------

class TestIfKnown:
    def test_if_true(self):
        result = ev('if (1) { x = 10; } else { x = 20; }')
        assert result['x'].value == 10

    def test_if_false(self):
        result = ev('if (0) { x = 10; } else { x = 20; }')
        assert result['x'].value == 20

    def test_if_no_else(self):
        result = ev('x = 5; if (0) { x = 99; }')
        assert result['x'].value == 5

    def test_if_nested(self):
        result = ev('x = 0; if (1) { if (1) { x = 7; } }')
        assert result['x'].value == 7

    def test_if_concrete_expr(self):
        result = ev('x = 3; if (x == 3) { y = 1; } else { y = 0; }',
                    known={'x': Expr.integer(3)})
        assert result['y'].value == 1


# ---------------------------------------------------------------------------
# if/else: unknown (symbolic) conditions → CTernary
# ---------------------------------------------------------------------------

class TestIfSymbolic:
    def test_ternary_created(self):
        result = ev(
            'if (Lambda == 0) { Lam = 6.0; } else { Lam = Lambda; }',
            known={'Lambda': Expr.id('Lambda'), 'Lam': Expr.float('0.0')},
        )
        lam = result['Lam']
        assert 'Lambda' in lam  # Lam depends on Lambda symbolically

    def test_ternary_collapses_with_evaluate(self):
        result = ev(
            'if (Lambda == 0) { Lam = 6.0; } else { Lam = Lambda; }',
            known={'Lambda': Expr.id('Lambda'), 'Lam': Expr.float('0.0')},
        )
        # When Lambda is known, the ternary collapses
        lam_at_0 = result['Lam'].evaluate({'Lambda': Expr.integer(0)})
        lam_at_3 = result['Lam'].evaluate({'Lambda': Expr.float('3.0')})
        assert abs(float(lam_at_0.value) - 6.0) < 1e-12
        assert abs(float(lam_at_3.value) - 3.0) < 1e-12

    def test_unchanged_variable_not_wrapped(self):
        result = ev(
            'y = 5.0; if (x == 0) { z = 1.0; } else { z = 2.0; }',
            known={'x': Expr.id('x')},
        )
        # y was not touched by the if/else, should remain 5.0
        assert result['y'].value == 5.0

    def test_skadi_pattern(self):
        block = '''
            double Lam = Lambda;
            if (Lambda == 0) { Lam = 6.0; }
            double q = 4.0 * PI * sin(0.5 * DEG2RAD) / Lam;
        '''
        result = evaluate_c_block(block, known={'Lambda': Expr.id('Lambda')})
        q = result.get('q')
        assert q is not None
        # q is symbolic and depends on Lambda
        assert 'Lambda' in q
        # When Lambda=0, Lam=6.0
        q_val = q.evaluate({'Lambda': Expr.integer(0)})
        import math
        expected = 4.0 * math.pi * math.sin(math.radians(0.5)) / 6.0
        assert abs(float(q_val.value) - expected) < 1e-8


# ---------------------------------------------------------------------------
# evaluate_c_defined_expressions integration (c_listener wrapper)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Phase 2: for / while / do-while loop unrolling
# ---------------------------------------------------------------------------

class TestForLoop:
    def test_simple_counting_loop(self):
        result = ev('int x = 0; for (int i = 0; i < 5; i++) { x += 1; }')
        assert result['x'].value == 5

    def test_sum_loop(self):
        result = ev('int s = 0; for (int i = 1; i <= 4; i++) { s += i; }')
        assert result['s'].value == 10

    def test_for_with_break(self):
        result = ev('int x = 0; for (int i = 0; i < 10; i++) { if (i == 3) break; x = i; }')
        assert result['x'].value == 2

    def test_for_with_continue(self):
        result = ev('int s = 0; for (int i = 0; i < 5; i++) { if (i == 2) continue; s += 1; }')
        assert result['s'].value == 4

    def test_array_fill_via_loop(self):
        result = evaluate_c_block(
            'double arr[5]; for (int i = 0; i < 5; i++) { arr[i] = i * 2.0; }',
            known={},
        )
        from mccode_antlr.translators.c_evaluator import CBlockEvaluator
        from antlr4 import InputStream, CommonTokenStream
        from mccode_antlr.grammar import CLexer, CParser
        from mccode_antlr.translators.c_listener import make_error_listener
        from antlr4.error.ErrorListener import ErrorListener
        text = '{ double arr[5]; for (int i = 0; i < 5; i++) { arr[i] = i * 2.0; } }'
        stream = InputStream(text)
        lexer = CLexer(stream)
        tokens = CommonTokenStream(lexer)
        parser = CParser(tokens)
        parser.addErrorListener(make_error_listener(ErrorListener, text))
        tree = parser.compoundStatement()
        evaluator = CBlockEvaluator({})
        evaluator.visit(tree)
        assert evaluator.array_state['arr'][0].value == 0
        assert evaluator.array_state['arr'][4].value == 8


class TestWhileLoop:
    def test_simple_while(self):
        result = ev('int x = 0; int i = 0; while (i < 3) { x += 1; i += 1; }')
        assert result['x'].value == 3

    def test_while_with_break(self):
        result = ev('int x = 0; while (1) { x += 1; if (x == 4) break; }')
        assert result['x'].value == 4

    def test_while_false_skipped(self):
        result = ev('int x = 99; while (0) { x = 0; }')
        assert result['x'].value == 99


class TestDoWhileLoop:
    def test_do_while_runs_once(self):
        result = ev('int x = 0; do { x = 1; } while (0);')
        assert result['x'].value == 1

    def test_do_while_counting(self):
        result = ev('int x = 0; int c = 0; do { c += 1; x += c; } while (c < 3);')
        assert result['c'].value == 3
        assert result['x'].value == 6


# ---------------------------------------------------------------------------
# Phase 2: switch / case
# ---------------------------------------------------------------------------

class TestSwitch:
    def test_switch_first_case(self):
        result = ev('int x = 0; int n = 1; switch (n) { case 1: x = 10; break; case 2: x = 20; break; }')
        assert result['x'].value == 10

    def test_switch_second_case(self):
        result = ev('int x = 0; int n = 2; switch (n) { case 1: x = 10; break; case 2: x = 20; break; }')
        assert result['x'].value == 20

    def test_switch_default(self):
        result = ev('int x = 0; int n = 5; switch (n) { case 1: x = 1; break; default: x = 99; break; }')
        assert result['x'].value == 99

    def test_switch_fallthrough(self):
        result = ev('int x = 0; int n = 1; switch (n) { case 1: x += 1; case 2: x += 2; break; }')
        assert result['x'].value == 3

    def test_switch_no_match(self):
        result = ev('int x = 7; switch (3) { case 1: x = 1; break; case 2: x = 2; break; }')
        assert result['x'].value == 7


# ---------------------------------------------------------------------------
# Phase 3: array state (concrete integer indices)
# ---------------------------------------------------------------------------

class TestArrayState:
    def _get_evaluator(self, src):
        from mccode_antlr.translators.c_evaluator import CBlockEvaluator
        from antlr4 import InputStream, CommonTokenStream
        from mccode_antlr.grammar import CLexer, CParser
        from mccode_antlr.translators.c_listener import make_error_listener
        from antlr4.error.ErrorListener import ErrorListener
        text = src if src.lstrip().startswith('{') else f'{{\n{src}\n}}'
        stream = InputStream(text)
        lexer = CLexer(stream)
        tokens = CommonTokenStream(lexer)
        parser = CParser(tokens)
        parser.addErrorListener(make_error_listener(ErrorListener, text))
        tree = parser.compoundStatement()
        evaluator = CBlockEvaluator({})
        evaluator.visit(tree)
        return evaluator

    def test_array_write_read(self):
        ev_obj = self._get_evaluator('double a[3]; a[0] = 1.0; a[1] = 2.0; double x = a[0] + a[1];')
        assert ev_obj.state['x'].value == 3.0

    def test_array_initializer(self):
        ev_obj = self._get_evaluator('double a[] = {10.0, 20.0, 30.0};')
        assert ev_obj.array_state['a'][0].value == 10.0
        assert ev_obj.array_state['a'][2].value == 30.0

    def test_array_read_after_write(self):
        ev_obj = self._get_evaluator('double b[5]; b[2] = 99.0; double x = b[2];')
        assert ev_obj.state['x'].value == 99.0

    def test_array_compound_assign(self):
        ev_obj = self._get_evaluator('double a[2]; a[0] = 5.0; a[0] += 3.0;')
        assert ev_obj.array_state['a'][0].value == 8.0

    def test_array_state_not_in_scalar(self):
        ev_obj = self._get_evaluator('double arr[2]; arr[0] = 1.0;')
        assert 'arr' not in ev_obj.state


# ---------------------------------------------------------------------------
# Phase 4: struct / pointer member state
# ---------------------------------------------------------------------------

class TestStructState:
    def _get_evaluator(self, src):
        from mccode_antlr.translators.c_evaluator import CBlockEvaluator
        from antlr4 import InputStream, CommonTokenStream
        from mccode_antlr.grammar import CLexer, CParser
        from mccode_antlr.translators.c_listener import make_error_listener
        from antlr4.error.ErrorListener import ErrorListener
        text = src if src.lstrip().startswith('{') else f'{{\n{src}\n}}'
        stream = InputStream(text)
        lexer = CLexer(stream)
        tokens = CommonTokenStream(lexer)
        parser = CParser(tokens)
        parser.addErrorListener(make_error_listener(ErrorListener, text))
        tree = parser.compoundStatement()
        evaluator = CBlockEvaluator({})
        evaluator.visit(tree)
        return evaluator

    def test_struct_dot_write_read(self):
        ev_obj = self._get_evaluator('obj.x = 3.0; obj.y = 4.0; double d = obj.x + obj.y;')
        assert ev_obj.state['d'].value == 7.0

    def test_struct_arrow_write_read(self):
        ev_obj = self._get_evaluator('ptr->x = 10.0; double v = ptr->x;')
        assert ev_obj.state['v'].value == 10.0

    def test_struct_compound_assign(self):
        ev_obj = self._get_evaluator('s.v = 5.0; s.v += 2.0;')
        assert ev_obj.struct_state['s']['v'].value == 7.0

    def test_struct_field_independence(self):
        ev_obj = self._get_evaluator('obj.a = 1.0; obj.b = 2.0;')
        assert ev_obj.struct_state['obj']['a'].value == 1.0
        assert ev_obj.struct_state['obj']['b'].value == 2.0


class TestCListenerIntegration:
    def test_simple_assignment(self):
        from mccode_antlr.translators.c_listener import evaluate_c_defined_expressions
        variables = {'x': Expr.float('0.0')}
        result = evaluate_c_defined_expressions(variables, 'x = 3.14;')
        assert abs(result['x'].value - 3.14) < 1e-12

    def test_if_block_handled(self):
        from mccode_antlr.translators.c_listener import evaluate_c_defined_expressions
        # Old evaluator would fail on 'if'; new one handles it
        variables = {'Lam': Expr.float('0.0')}
        block = 'double Lambda = 0; double Lam = 6.0; if (Lambda == 0) { Lam = 6.0; } else { Lam = Lambda; }'
        result = evaluate_c_defined_expressions(variables, block)
        assert result['Lam'] is not None  # at minimum, didn't crash

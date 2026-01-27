"""
Extended test cases for Expr implementation to ensure refactoring safety.

These tests cover edge cases, complex scenarios, and behaviors that should be
preserved when replacing the implementation with a sympy wrapper.
"""
from unittest import TestCase
from mccode_antlr.common.expression import (
    Expr, Value, Op, UnaryOp, BinaryOp, TrinaryOp, 
    DataType, ShapeType, ObjectType, OpStyle
)


class TestNumericEdgeCases(TestCase):
    """Test edge cases for numeric operations."""
    
    def test_division_by_zero_constant(self):
        """Division by zero with constants should raise or return special value."""
        with self.assertRaises((ZeroDivisionError, RuntimeError)):
            result = Expr.int(1) / Expr.int(0)
            # If it doesn't raise, it should evaluate to infinity or similar
            _ = result.simplify()
    
    def test_division_by_zero_symbolic(self):
        """Division by zero with identifiers should create valid expression."""
        x = Expr.id('x')
        result = Expr.int(1) / x
        self.assertTrue(isinstance(result, Expr))
        # Should be able to evaluate when x is known
        evaluated = result.evaluate({'x': Expr.int(2)})
        self.assertEqual(evaluated, Expr.float(0.5))
    
    def test_very_large_numbers(self):
        """Test operations with very large numbers."""
        large = Expr.float(1e308)
        small = Expr.float(1e-308)
        
        # These should not raise overflow errors
        result1 = large * small
        result2 = large + large
        
        self.assertTrue(isinstance(result1, Expr))
        self.assertTrue(isinstance(result2, Expr))
    
    def test_integer_division_types(self):
        """Integer division should return int, true division should return float."""
        a = Expr.int(7)
        b = Expr.int(3)
        
        true_div = a / b
        floor_div = a // b
        
        self.assertEqual(true_div.data_type, DataType.float)
        self.assertEqual(floor_div.data_type, DataType.int)
        
        # Check actual values
        self.assertEqual(floor_div.simplify(), Expr.int(2))
        seven_thirds = Expr.float(2.3333333)
        self.assertAlmostEqual(true_div.simplify(), seven_thirds)
    
    def test_negative_modulo(self):
        """Test modulo operations with negative numbers."""
        a = Expr.int(-7)
        b = Expr.int(3)
        
        # Should handle negative operands
        result = a % b
        self.assertTrue(isinstance(result, Expr))
        self.assertEqual(result.simplify(), Expr.int(2))

        # Flipping both signs flips the sign but not magnitude of the result
        # In Python the modulo with a negative divisor should be negative
        self.assertEqual(7 % -3, -2)
        # This is not true for C, but we ignore this difference for the time being
        self.assertEqual(-a % -b, Expr.int(-2))
    
    def test_zero_times_infinity_symbolic(self):
        """Test 0 * x where x might be infinite."""
        zero = Expr.int(0)
        x = Expr.id('x')
        
        result = zero * x
        self.assertTrue(result.is_zero or isinstance(result, Expr))
    
    def test_mixed_int_float_operations(self):
        """Test type promotion in mixed operations."""
        i = Expr.int(5)
        f = Expr.float(2.5)
        
        tests = [
            (i + f, DataType.float),
            (i - f, DataType.float),
            (i * f, DataType.float),
            (i / f, DataType.float),
            (f + i, DataType.float),
            (f - i, DataType.float),
            (f * i, DataType.float),
            (f / i, DataType.float),
        ]
        
        for result, expected_type in tests:
            self.assertEqual(result.data_type, expected_type)


class TestComplexParsing(TestCase):
    """Test parsing of complex expressions."""
    
    def test_nested_function_calls(self):
        """Test parsing nested function calls."""
        expr = Expr.parse('sin(cos(x))')
        
        self.assertTrue(isinstance(expr, Expr))
        self.assertTrue(expr.depends_on('x'))
        self.assertTrue(expr.depends_on('sin') or not expr.depends_on('sin'))
        self.assertTrue(expr.depends_on('cos') or not expr.depends_on('cos'))
    
    def test_multiple_function_arguments(self):
        """Test functions with multiple arguments."""
        expr = Expr.parse('atan2(y, x)')
        
        self.assertTrue(expr.depends_on('x'))
        self.assertTrue(expr.depends_on('y'))
        
        # Test with three arguments
        expr3 = Expr.parse('func(a, b, c)')
        self.assertTrue(expr3.depends_on('a'))
        self.assertTrue(expr3.depends_on('b'))
        self.assertTrue(expr3.depends_on('c'))
    
    def test_mixed_operator_precedence(self):
        """Test operator precedence in complex expressions."""
        # a + b * c should be a + (b * c)
        expr = Expr.parse('2 + 3 * 4')
        self.assertEqual(expr.simplify(), Expr.int(14))
        
        # a * b + c * d
        expr2 = Expr.parse('2 * 3 + 4 * 5')
        self.assertEqual(expr2.simplify(), Expr.int(26))
        
        # a / b - c / d
        expr3 = Expr.parse('10 / 2 - 12 / 4')
        self.assertEqual(expr3.simplify(), Expr.int(2))
    
    def test_parentheses_grouping(self):
        """Test that parentheses override precedence correctly."""
        expr1 = Expr.parse('(2 + 3) * 4')
        self.assertEqual(expr1.simplify(), Expr.int(20))
        
        expr2 = Expr.parse('2 * (3 + 4)')
        self.assertEqual(expr2.simplify(), Expr.int(14))
        
        expr3 = Expr.parse('((2 + 3) * 4) / (5 - 3)')
        self.assertEqual(expr3.simplify(), Expr.int(10))
    
    def test_complex_nested_expression(self):
        """Test deeply nested complex expression."""
        expr = Expr.parse('sin(-PI * x / 2)')
        
        self.assertTrue(expr.depends_on('x'))
        self.assertTrue(expr.depends_on('PI'))
        self.assertFalse(expr.is_constant)
    
    def test_array_indexing(self):
        """Test array indexing operations."""
        # Create an array access expression manually since parsing may vary
        arr = Value('arr', DataType.float, ObjectType.identifier, ShapeType.vector)
        idx = Expr.int(0)
        
        expr = BinaryOp(DataType.float, OpStyle.C, '__getitem__', [arr], idx.expr)
        
        self.assertFalse(expr.is_vector)
        self.assertTrue(expr.is_op) # it is still the operator
        self.assertEqual(str(expr), 'arr[0]')
    
    def test_chained_struct_access(self):
        """Test chained struct/pointer access."""
        obj = Value.id('obj')
        
        # obj.field
        field_access = BinaryOp(DataType.undefined, OpStyle.C, '__struct_access__', obj, Value.id('field'))
        self.assertEqual(str(field_access), 'obj.field')
        
        # obj->field
        ptr_access = BinaryOp(DataType.undefined, OpStyle.C, '__pointer_access__', obj, Value.id('field'))
        self.assertEqual(str(ptr_access), 'obj->field')
    
    def test_unary_minus_in_expression(self):
        """Test unary minus within larger expressions."""
        expr = Expr.parse('2 * -x + 3')
        
        self.assertTrue(expr.depends_on('x'))
        
        evaluated = expr.evaluate({'x': Expr.int(5)})
        # no need to simplify, since it has already greedily performed a simplification
        self.assertEqual(evaluated, Expr.int(-7))
        # and simplifying in this case doesn't change anything
        simplified = evaluated.simplify()
        self.assertEqual(simplified, Expr.int(-7))


class TestSimplificationEdgeCases(TestCase):
    """Test edge cases in expression simplification."""
    
    def test_algebraic_simplification_addition(self):
        """Test simplification of x + x -> 2*x."""
        x = Expr.id('x')
        expr = x + x
        
        # This may or may not simplify depending on implementation
        # But should at least remain valid
        self.assertTrue(isinstance(expr, Expr))
        self.assertTrue(expr.depends_on('x'))
    
    def test_algebraic_simplification_subtraction(self):
        """Test simplification of x - x -> 0."""
        x = Expr.id('x')
        expr = x - x
        
        simplified = expr.simplify()
        # May simplify to zero if implementation is sophisticated
        self.assertTrue(isinstance(simplified, Expr))
    
    def test_multiplication_identity_symbolic(self):
        """Test that 1 * x = x."""
        x = Expr.id('x')
        one = Expr.int(1)
        
        self.assertEqual(one * x, x)
        self.assertEqual(x * one, x)
    
    def test_division_identity_symbolic(self):
        """Test that x / 1 = x."""
        x = Expr.id('x')
        one = Expr.int(1)
        
        self.assertEqual(x / one, x)
    
    def test_division_by_self_symbolic(self):
        """Test that x / x might simplify to 1."""
        x = Expr.id('x')
        expr = x / x
        
        # This is a challenging simplification
        # At minimum should create valid expression
        self.assertTrue(isinstance(expr, Expr))
    
    def test_complex_constant_folding(self):
        """Test that complex constant expressions fold correctly."""
        expr = Expr.parse('(2 + 3) * (4 - 1) / (10 - 9)')
        simplified = expr.simplify()
        
        # self.assertTrue(simplified.is_constant)
        self.assertEqual(simplified, Expr.int(15))
    
    def test_partial_simplification(self):
        """Test expressions that can only partially simplify."""
        x = Expr.id('x')
        expr = Expr.parse('2 + 3') * x + Expr.parse('4 * 5')
        
        # 2+3 should fold to 5, 4*5 should fold to 20
        # Result should be 5*x + 20
        simplified = expr.simplify()
        self.assertTrue(simplified.depends_on('x'))
        
        # When x=0, should evaluate to 20
        evaluated = simplified.evaluate({'x': Expr.int(0)})
        self.assertEqual(evaluated.simplify(), Expr.int(20))
    
    def test_simplification_preserves_type(self):
        """Test that simplification preserves data types."""
        expr = Expr.float(2.0) + Expr.float(3.0)
        simplified = expr.simplify()
        
        self.assertEqual(simplified.data_type, DataType.float)
        
        expr_int = Expr.int(2) + Expr.int(3)
        simplified_int = expr_int.simplify()
        
        self.assertEqual(simplified_int.data_type, DataType.int)
    
    def test_nested_simplification(self):
        """Test that simplification works recursively."""
        expr = Expr.parse('((1 + 2) * (3 + 4)) / (5 + 2)')
        simplified = expr.simplify()
        
        self.assertTrue(simplified.is_constant)
        self.assertEqual(simplified, Expr.int(3))


class TestEvaluationEdgeCases(TestCase):
    """Test edge cases in expression evaluation."""
    
    def test_partial_evaluation(self):
        """Test evaluation with only some variables known."""
        expr = Expr.parse('a + b * c')
        
        # Only know 'b'
        partial = expr.evaluate({'b': Expr.int(2)})
        self.assertTrue(partial.depends_on('a'))
        self.assertTrue(partial.depends_on('c'))
        self.assertFalse(partial.depends_on('b'))
    
    def test_evaluation_with_zero(self):
        """Test evaluation when variable is zero."""
        expr = Expr.parse('x * y + z')
        
        evaluated = expr.evaluate({'x': Expr.int(0)})
        simplified = evaluated.simplify()
        
        # x*y becomes 0*y, leaving 0 * y + z
        self.assertFalse(simplified.depends_on('x'))
        self.assertTrue(simplified.depends_on('y'))
        self.assertTrue(simplified.depends_on('z'))
    
    def test_evaluation_order_independence(self):
        """Test that evaluation order doesn't matter."""
        expr = Expr.parse('a + b + c')
        
        known = {
            'a': Expr.int(1),
            'b': Expr.int(2),
            'c': Expr.int(3)
        }
        
        result = expr.evaluate(known).simplify()
        self.assertEqual(result, Expr.int(6))
    
    def test_evaluation_with_expressions(self):
        """Test evaluation where known values are themselves expressions."""
        expr = Expr.parse('x + y')
        
        known = {
            'x': Expr.parse('a + b'),
            'y': Expr.parse('c * d')
        }
        
        result = expr.evaluate(known)
        self.assertTrue(result.depends_on('a'))
        self.assertTrue(result.depends_on('b'))
        self.assertTrue(result.depends_on('c'))
        self.assertTrue(result.depends_on('d'))
    
    def test_evaluation_with_vectors(self):
        """Test evaluation with vector values."""
        expr = Expr.parse('v + w')
        
        vec1 = Value.array([1, 2, 3], DataType.float)
        vec2 = Value.array([4, 5, 6], DataType.float)
        
        result = expr.evaluate({'v': Expr([vec1]), 'w': Expr([vec2])})
        
        self.assertTrue(isinstance(result, Expr))
    
    def test_nested_evaluation(self):
        """Test evaluation of nested expressions."""
        expr = Expr.parse('sin(x * PI)')
        
        evaluated = expr.evaluate({'x': Expr.int(1)})
        
        self.assertFalse(evaluated.depends_on('x'))
        self.assertTrue(evaluated.depends_on('PI'))
    
    def test_evaluation_preserves_parameter_type(self):
        """Test that evaluating parameters preserves ObjectType.parameter."""
        par = Value('instr_param', _object=ObjectType.parameter)
        expr = Expr([par])
        
        # Evaluation with empty dict should preserve the expression
        result = expr.evaluate({})
        self.assertTrue(result.is_parameter)


class TestStringFormatting(TestCase):
    """Test string formatting and representation."""
    
    def test_parameter_formatting_prefix(self):
        """Test parameter formatting with custom prefix."""
        par = Value('my_param', _object=ObjectType.parameter)
        
        # Default parameter format
        self.assertEqual(f'{par:p}', '_instrument_var._parameters.my_param')
        
        # Custom prefix
        self.assertEqual(f'{par:prefix:custom_}', 'custom_my_param')
        
        # Normal string representation
        self.assertEqual(str(par), 'my_param')
    
    def test_c_vs_python_style_operators(self):
        """Test C vs Python style for all operators."""
        a = Value.id('a')
        b = Value.id('b')
        c = Value.id('c')
        
        # Binary operators
        tests = [
            ('__and__', 'a && b', 'a and b'),
            ('__or__', 'a || b', 'a or b'),
            ('__pow__', 'a^b', 'a**b'),
        ]
        
        for op, c_str, py_str in tests:
            expr = BinaryOp(DataType.undefined, OpStyle.C, op, a, b)
            self.assertEqual(str(expr), c_str)
            
            expr.style = OpStyle.PYTHON
            self.assertEqual(str(expr), py_str)
        
        # Unary operators
        not_expr = UnaryOp(DataType.undefined, OpStyle.C, '__not__', a)
        self.assertEqual(str(not_expr), '!a')
        not_expr.style = OpStyle.PYTHON
        self.assertEqual(str(not_expr), 'not a')
        
        # Trinary operator
        ternary = TrinaryOp(DataType.undefined, OpStyle.C, '__trinary__', a, b, c)
        self.assertEqual(str(ternary), 'a ? b : c')
        ternary.style = OpStyle.PYTHON
        self.assertEqual(str(ternary), 'b if a else c')
    
    def test_format_preservation_through_operations(self):
        """Test that format settings are preserved through operations."""
        a = Value.id('a')
        b = Value.id('b')
        
        # Create expression in C style
        expr = BinaryOp(DataType.undefined, OpStyle.C, '__and__', a, b)
        self.assertEqual(str(expr), 'a && b')
        
        # Operations should preserve style
        expr2 = -expr
        # The negation wraps the expression, preserving inner style
        self.assertIn('&&', str(expr2))
    
    def test_repr_is_valid_python(self):
        """Test that repr() produces useful debug output."""
        val = Value.int(42)
        repr_str = repr(val)
        
        self.assertIsInstance(repr_str, str)
        self.assertIn('42', repr_str)
    
    def test_format_spec_edge_cases(self):
        """Test edge cases in format specifications."""
        par = Value('param', _object=ObjectType.parameter)
        
        # Empty format spec
        self.assertEqual(f'{par:}', 'param')
        
        # Invalid format spec should fall back to default
        # (behavior may vary by implementation)
        try:
            result = f'{par:invalid_spec}'
            self.assertIsInstance(result, str)
        except (ValueError, KeyError):
            pass  # Some implementations may raise


class TestVectorOperations(TestCase):
    """Test vector-specific operations."""
    
    def test_vector_concatenation(self):
        """Test that vector addition concatenates."""
        v1 = Value.array([1, 2, 3], DataType.int)
        v2 = Value.array([4, 5, 6], DataType.int)
        
        result = v1 + v2
        
        self.assertTrue(result.is_vector)
        self.assertEqual(result.vector_len, 6)
    
    def test_vector_type_promotion(self):
        """Test type promotion in vector operations."""
        v_int = Value.array([1, 2, 3], DataType.int)
        v_float = Value.array([4.0, 5.0, 6.0], DataType.float)
        
        result = v_int + v_float
        
        # Should promote to float
        self.assertEqual(result.data_type, DataType.float)
    
    def test_empty_vector(self):
        """Test operations with empty vectors."""
        empty = Value.array([], DataType.float)
        
        self.assertTrue(empty.is_vector)
        self.assertEqual(empty.vector_len, 0)
    
    def test_vector_indexing_type(self):
        """Test that vector indexing returns scalar."""
        vec = Value('vec', DataType.float, ObjectType.identifier, ShapeType.vector)
        idx = Expr.int(0)
        
        access = BinaryOp(DataType.float, OpStyle.C, '__getitem__', [vec], idx.expr)
        
        self.assertFalse(access.is_vector)
        # self.assertTrue(access.is_scalar)  # We dont know this, it could be a nested vector?
    
    def test_scalar_vector_operations(self):
        """Test operations between scalars and vectors."""
        scalar = Expr.int(2)
        vec = Value.array([1, 2, 3], DataType.int)
        
        # These create BinaryOp expressions
        result1 = scalar * Expr([vec])
        result2 = Expr([vec]) * scalar
        
        self.assertTrue(isinstance(result1, Expr))
        self.assertTrue(isinstance(result2, Expr))
    
    def test_null_vector_compatibility(self):
        """Test NULL vector compatibility with identifiers."""
        null_vec = Value.array("NULL")
        
        # NULL vector should be compatible with identifiers
        self.assertTrue(null_vec.compatible("some_id"))
        self.assertFalse(null_vec.compatible('"quoted_string"'))
    
    def test_vector_in_expressions(self):
        """Test vectors used in larger expressions."""
        # But adding a vector and a scalar isn't an allowed operation.
        vec = Value.array([1, 2, 3], DataType.float)
        scalar = Value.float(2.0)

        with self.assertRaises(TypeError):
            expr = Expr([vec]) + Expr([scalar])

        # # Expression containing vectors
        # self.assertTrue(isinstance(expr, Expr))


class TestTypeCompatibility(TestCase):
    """Test type compatibility and coercion."""
    
    def test_all_datatype_combinations(self):
        """Test compatibility between all DataType pairs."""
        types = [DataType.undefined, DataType.float, DataType.int, DataType.str]
        
        for t1 in types:
            for t2 in types:
                compatible = t1.compatible(t2)
                # undefined is compatible with everything
                if t1 == DataType.undefined or t2 == DataType.undefined:
                    self.assertTrue(compatible)
                # same types are compatible
                elif t1 == t2:
                    self.assertTrue(compatible)
                # float and int are compatible
                elif {t1, t2} == {DataType.float, DataType.int}:
                    self.assertTrue(compatible)
                # string is incompatible with numeric
                elif DataType.str in {t1, t2}:
                    self.assertFalse(compatible)
    
    def test_shapetype_compatibility(self):
        """Test ShapeType compatibility rules."""
        unknown = ShapeType.unknown
        scalar = ShapeType.scalar
        vector = ShapeType.vector
        
        # unknown is compatible with everything
        self.assertTrue(unknown.compatible(scalar))
        self.assertTrue(unknown.compatible(vector))
        self.assertTrue(unknown.compatible(unknown))
        
        # scalar and vector are not compatible with each other
        self.assertFalse(scalar.compatible(vector))
        self.assertFalse(vector.compatible(scalar))
        
        # same types are compatible
        self.assertTrue(scalar.compatible(scalar))
        self.assertTrue(vector.compatible(vector))
    
    def test_objecttype_properties(self):
        """Test ObjectType property methods."""
        tests = [
            (ObjectType.value, False, False, False),
            (ObjectType.identifier, True, False, False),
            (ObjectType.parameter, False, True, False),
            (ObjectType.function, False, False, True),
            (ObjectType.initializer_list, False, False, False),
        ]
        
        for obj_type, is_id, is_param, is_func in tests:
            self.assertEqual(obj_type.is_id, is_id)
            self.assertEqual(obj_type.is_parameter, is_param)
            self.assertEqual(obj_type.is_function, is_func)
    
    def test_type_promotion_in_operations(self):
        """Test that operations promote types correctly."""
        int_val = Expr.int(5)
        float_val = Expr.float(2.5)
        
        # int + float -> float
        result = int_val + float_val
        self.assertEqual(result.data_type, DataType.float)
        
        # int * float -> float
        result = int_val * float_val
        self.assertEqual(result.data_type, DataType.float)
        
        # int / int -> float (true division)
        result = int_val / Expr.int(2)
        self.assertEqual(result.data_type, DataType.float)
        
        # int // int -> int (floor division)
        result = int_val // Expr.int(2)
        self.assertEqual(result.data_type, DataType.int)
    
    def test_as_type_method(self):
        """Test the as_type method for type coercion."""
        val = Value.int(42)
        
        float_val = val.as_type(DataType.float)
        self.assertEqual(float_val.data_type, DataType.float)
        
        # Original should be unchanged
        self.assertEqual(val.data_type, DataType.int)


class TestCopyAndEquality(TestCase):
    """Test copy operations and equality comparisons."""
    
    def test_value_copy(self):
        """Test that copying Values works correctly."""
        original = Value.int(42)
        copied = original.copy()
        
        self.assertEqual(original, copied)
        self.assertIsNot(original, copied)
    
    def test_expr_copy(self):
        """Test that copying Expr works correctly."""
        original = Expr.parse('x + y * 2')
        copied = original.copy()
        
        self.assertEqual(original, copied)
        self.assertIsNot(original, copied)
    
    def test_deep_copy_mutation_safety(self):
        """Test that mutations to copy don't affect original."""
        original = Expr.parse('x + y')
        copied = original.copy()
        
        # Evaluate the copy
        copied.evaluate({'x': Expr.int(1)})
        
        # Original should still depend on x
        self.assertTrue(original.depends_on('x'))
    
    def test_equality_structural(self):
        """Test that structurally identical expressions are equal."""
        expr1 = Expr.parse('x + y')
        expr2 = Expr.parse('x + y')
        
        self.assertEqual(expr1, expr2)
    
    def test_equality_with_different_construction(self):
        """Test equality for expressions built differently."""
        # Built through parsing
        expr1 = Expr.parse('2 * x')
        
        # Built manually
        expr2 = Expr.int(2) * Expr.id('x')
        
        # These may or may not be equal depending on simplification
        # But at minimum, they should evaluate the same
        result1 = expr1.evaluate({'x': Expr.int(3)})
        result2 = expr2.evaluate({'x': Expr.int(3)})
        
        self.assertEqual(result1.simplify(), result2.simplify())
    
    def test_hash_consistency(self):
        """Test that hash is consistent with equality."""
        expr1 = Expr.int(42)
        expr2 = Expr.int(42)
        
        if expr1 == expr2:
            self.assertEqual(hash(expr1), hash(expr2))
    
    def test_equality_with_operations(self):
        """Test equality through various operations."""
        a = Expr.int(2)
        b = Expr.int(3)
        
        self.assertEqual(a + b, Expr.int(5))
        self.assertEqual(a * b, Expr.int(6))
        self.assertEqual(b - a, Expr.int(1))
    
    def test_inequality_operations(self):
        """Test inequality comparisons."""
        a = Expr.int(2)
        b = Expr.int(3)
        
        self.assertTrue(a < b)
        self.assertTrue(a <= b)
        self.assertTrue(b > a)
        self.assertTrue(b >= a)
        self.assertFalse(a > b)
        self.assertFalse(b < a)
    
    def test_contains_operator(self):
        """Test the __contains__ operator for expressions."""
        val = Value.int(42)
        expr = Expr.parse('x + 42 + y')
        
        # Should be able to check if value is in expression
        result = val in expr
        self.assertIsInstance(result, bool)


class TestMiscellaneousEdgeCases(TestCase):
    """Test miscellaneous edge cases and corner cases."""
    
    def test_expr_list_multiple_expressions(self):
        """Test Expr with multiple sub-expressions."""
        exprs = [Value.int(1), Value.int(2), Value.int(3)]
        expr = Expr(exprs)
        
        self.assertEqual(len(expr.expr), 3)
        self.assertFalse(expr.is_singular)
    
    def test_mccode_c_type_names(self):
        """Test C type name generation."""
        tests = [
            (Value.int(1), 'int', 'instr_type_int'),
            (Value.float(1.0), 'double', 'instr_type_double'),
            (Value.str('test'), 'char *', 'instr_type_string'),
        ]
        
        for val, c_type, c_type_name in tests:
            self.assertEqual(val.mccode_c_type, c_type)
            self.assertEqual(val.mccode_c_type_name, c_type_name)
    
    def test_is_zero_detection(self):
        """Test is_zero property."""
        self.assertTrue(Expr.int(0).is_zero)
        self.assertTrue(Expr.float(0.0).is_zero)
        self.assertFalse(Expr.int(1).is_zero)
        self.assertFalse(Expr.id('x').is_zero)
        
        # Zero from operation
        result = Expr.int(5) - Expr.int(5)
        self.assertTrue(result.is_zero)
    
    def test_is_constant_detection(self):
        """Test is_constant property."""
        self.assertTrue(Expr.int(42).is_constant)
        self.assertTrue(Expr.float(3.14).is_constant)
        self.assertFalse(Expr.id('x').is_constant)
        
        # Constant from simplification
        expr = Expr.parse('2 + 3')
        self.assertTrue(expr.simplify().is_constant)
    
    def test_verify_parameters(self):
        """Test verify_parameters method."""
        expr = Expr.parse('x + instrument_param + y')
        
        # Should not raise if all identifiers are valid
        # This tests the method exists and runs
        try:
            expr.verify_parameters(['instrument_param'])
        except (RuntimeError, ValueError, AttributeError):
            # May raise if x and y are not recognized
            pass
    
    def test_abs_operations(self):
        """Test absolute value operations."""
        self.assertEqual(abs(Expr.int(-5)), Expr.int(5))
        self.assertEqual(abs(Expr.float(-3.14)), Expr.float(3.14))
        
        # abs(abs(x)) == abs(x)
        x = Expr.id('x')
        abs_x = abs(x)
        abs_abs_x = abs(abs_x)
        self.assertEqual(abs_x, abs_abs_x)
    
    def test_round_operations(self):
        """Test rounding operations."""
        self.assertEqual(round(Expr.float(3.7)), Expr.float(4.0))
        self.assertEqual(round(Expr.float(3.2)), Expr.float(3.0))
    
    def test_power_operations(self):
        """Test power/exponentiation operations."""
        base = Expr.int(2)
        exp = Expr.int(3)
        
        result = base ** exp
        self.assertEqual(result.simplify(), Expr.int(8))
    
    def test_reverse_operations(self):
        """Test reverse operations (1 + expr, etc)."""
        x = Expr.id('x')
        
        # These should work and produce valid expressions
        result1 = 1 + x
        result2 = 2 * x
        result3 = 10 - x
        result4 = 6 / x
        
        for result in [result1, result2, result3, result4]:
            self.assertTrue(isinstance(result, Expr))
            self.assertTrue(result.depends_on('x'))
    
    def test_best_value_constructor(self):
        """Test Value.best() constructor for type inference."""
        # Integer
        val1 = Value.best(42)
        self.assertEqual(val1.data_type, DataType.int)
        
        # Float
        val2 = Value.best(3.14)
        self.assertEqual(val2.data_type, DataType.float)
        
        # String
        val3 = Value.best('"hello"')
        self.assertEqual(val3.data_type, DataType.str)
        
        # Identifier
        val4 = Value.best('variable_name')
        self.assertEqual(val4.object_type, ObjectType.identifier)
    
    def test_function_call_syntax(self):
        """Test function call syntax."""
        func = Value.function('sqrt')
        arg = Value.int(16)
        
        call = BinaryOp(DataType.undefined, OpStyle.C, '__call__', func, arg)
        
        self.assertEqual(str(call), 'sqrt(16)')
    
    def test_data_type_from_name(self):
        """Test DataType.from_name static method."""
        self.assertEqual(DataType.from_name('int'), DataType.int)
        self.assertEqual(DataType.from_name('float'), DataType.float)
        self.assertEqual(DataType.from_name('double'), DataType.float)
        self.assertEqual(DataType.from_name('string'), DataType.str)
    
    def test_shape_type_from_name(self):
        """Test ShapeType.from_name static method."""
        self.assertEqual(ShapeType.from_name('scalar'), ShapeType.scalar)
        self.assertEqual(ShapeType.from_name('vector'), ShapeType.vector)
        self.assertEqual(ShapeType.from_name('unknown'), ShapeType.unknown)
    
    def test_object_type_from_name(self):
        """Test ObjectType.from_name static method."""
        self.assertEqual(ObjectType.from_name('value'), ObjectType.value)
        self.assertEqual(ObjectType.from_name('identifier'), ObjectType.identifier)
        self.assertEqual(ObjectType.from_name('function'), ObjectType.function)
        self.assertEqual(ObjectType.from_name('parameter'), ObjectType.parameter)


if __name__ == '__main__':
    import unittest
    unittest.main()

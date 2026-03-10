from unittest import TestCase
from mccode_antlr.common.expression import (
    Expr, DataType, ShapeType, ObjectType, OpStyle
)

class TestExpression(TestCase):
    def test_ObjectType(self):
        from mccode_antlr.common.expression import ObjectType as OT

        for ot in (OT.value, OT.initializer_list):
            self.assertFalse(ot.is_id)
            self.assertFalse(ot.is_parameter)
            self.assertFalse(ot.is_function)

        ot = OT.identifier
        self.assertTrue(ot.is_id)
        self.assertFalse(ot.is_parameter)
        self.assertFalse(ot.is_function)

        ot = OT.function
        self.assertFalse(ot.is_id)
        self.assertFalse(ot.is_parameter)
        self.assertTrue(ot.is_function)

        ot = OT.parameter
        self.assertFalse(ot.is_id)
        self.assertTrue(ot.is_parameter)
        self.assertFalse(ot.is_function)

        types = OT.value, OT.initializer_list, OT.identifier, OT.function, OT.parameter
        for ot in types:
            self.assertEqual(ot, ot)

        for i in range(len(types)):
            for j in range(len(types)):
                if i != j:
                    self.assertNotEqual(types[i], types[j])

    def test_ShapeType(self):
        from mccode_antlr.common.expression import ShapeType as ST
        ut = ST.unknown
        st = ST.scalar
        vt = ST.vector
        self.assertTrue(ut.compatible(st))
        self.assertTrue(ut.compatible(vt))
        self.assertTrue(ut.compatible(ut))
        self.assertTrue(st.compatible(ut))
        self.assertTrue(vt.compatible(ut))
        self.assertFalse(st.compatible(vt))
        self.assertFalse(vt.compatible(st))
        self.assertTrue(st.compatible(st))
        self.assertTrue(vt.compatible(vt))
        self.assertTrue(st.is_scalar)
        self.assertFalse(st.is_vector)
        self.assertTrue(vt.is_vector)
        self.assertFalse(vt.is_scalar)
        self.assertEqual(st.mccode_c_type, '')
        self.assertEqual(vt.mccode_c_type, '*')

    def test_DataType(self):
        from mccode_antlr.common.expression import DataType as DT
        u, f, i, s = DT.undefined, DT.float, DT.int, DT.str
        for x in (u, f, i, s):
            self.assertTrue(x.compatible(x))
            self.assertTrue(u.compatible(x))
            self.assertTrue(x.compatible(u))
        for x in (f, i):
            self.assertFalse(s.compatible(x))
            self.assertFalse(x.compatible(s))
        self.assertTrue(f.compatible(i))
        self.assertTrue(i.compatible(f))

        for x in (u, f, i, s):
            self.assertEqual(x + x, x)
            self.assertEqual(x - x, x)
            self.assertEqual(x * x, x)

        for x in (f, i, s):
            self.assertEqual(x + u, x)
            self.assertEqual(x - u, x)
            self.assertEqual(x * u, x)
            self.assertEqual(u + x, x)
            self.assertEqual(u - x, x)
            self.assertEqual(u * x, x)

        for x in (u, f, i):
            self.assertEqual(x // x, i)
            self.assertEqual(x / x, f)
            self.assertEqual(x / u, f)
            self.assertEqual(u / x, f)

        for x in (u, f, i):
            self.assertEqual(x + s, s)
            self.assertEqual(x - s, s)
            self.assertEqual(x * s, s)
            self.assertEqual(s + x, s)
            self.assertEqual(s - x, s)
            self.assertEqual(s * x, s)
            self.assertRaises(RuntimeError, lambda: x / s)
            self.assertRaises(RuntimeError, lambda: s / x)

        self.assertEqual(i + f, f)
        self.assertEqual(i - f, f)
        self.assertEqual(i * f, f)
        self.assertEqual(i / f, f)

        self.assertEqual(i.mccode_c_type, 'int')
        self.assertEqual(f.mccode_c_type, 'double')
        self.assertEqual(s.mccode_c_type, 'char *')

    def test_Value(self):
        float_value = Expr.float(1)
        int_value = Expr.int(1)
        str_value = Expr.str('1')
        id_value = Expr.id('one')
        array_value = Expr.array([1])
        function_value = Expr.function('ones')

        for x in (float_value, int_value, str_value, id_value, array_value, function_value):
            self.assertFalse(x.is_op)
            self.assertFalse(x.is_zero)

        self.assertEqual(float_value._object_type, ObjectType.value)
        self.assertEqual(int_value._object_type, ObjectType.value)
        self.assertEqual(str_value._object_type, ObjectType.value)
        self.assertEqual(id_value._object_type, ObjectType.identifier)
        self.assertEqual(array_value._object_type, ObjectType.value)
        self.assertEqual(function_value._object_type, ObjectType.function)

        for x, y in ((float_value, ShapeType.scalar), (int_value, ShapeType.scalar), (str_value, ShapeType.scalar),
                     (id_value, ShapeType.scalar), (array_value, ShapeType.vector), (function_value, ShapeType.scalar)):
            self.assertEqual(x.shape_type, y)

        for x in (float_value, int_value, id_value, array_value, function_value):
            self.assertFalse(x.is_str)
        self.assertTrue(str_value.is_str)

        # For float/int, use .value; for str/function use internal _exprs[0]; for array use is_vector
        self.assertTrue(float_value.is_value(float_value.value))
        self.assertTrue(int_value.is_value(int_value.value))
        self.assertTrue(str_value.is_value(str_value._exprs[0]))
        self.assertTrue(array_value.is_vector)
        self.assertTrue(function_value.is_value(function_value._exprs[0]))

        # Identifiers are not values:
        self.assertTrue(id_value.is_id)
        self.assertFalse(id_value.is_value(str(id_value)))

        for x in (float_value, int_value, str_value, id_value, function_value):
            self.assertTrue(x.is_scalar)
            self.assertFalse(x.is_vector)
        self.assertFalse(array_value.is_scalar)
        self.assertTrue(array_value.is_vector)

    def test_null_vector_Value(self):
        array = Expr.array("NULL")
        # an Array is compatible with a raw string (nor a Value.best(str) which produces an identifier)
        self.assertTrue(array.compatible("identifier"))
        # but not a quoted string
        self.assertFalse(array.compatible('"Not an identifier"'))

    def _numeric_Value_checks(self, one, two):
        self.assertEqual(one, one)
        self.assertEqual(one + one, two)
        self.assertEqual(two - one, one)
        self.assertEqual(one * one, one)
        self.assertEqual(two / two, one)
        self.assertEqual(one - two, -one)
        self.assertEqual(abs(one - two), one)
        self.assertTrue(one < two)
        self.assertTrue(one <= two)
        self.assertTrue(two > one)
        self.assertTrue(two >= one)

    def test_float_Value(self):
        one = Expr.float(1)
        two = Expr.float(2)
        self._numeric_Value_checks(one, two)
        self.assertEqual(one.mccode_c_type, 'double')
        self.assertEqual(one.mccode_c_type_name, 'instr_type_double')

    def test_int_Value(self):
        one = Expr.int(1)
        two = Expr.int(2)
        self._numeric_Value_checks(one, two)
        self.assertEqual(one.mccode_c_type, 'int')
        self.assertEqual(one.mccode_c_type_name, 'instr_type_int')

    def test_str_Value(self):
        one = Expr.str('one')
        two = Expr.str('two')
        self.assertEqual(one, one)
        self.assertIsInstance(one + one, Expr)
        self.assertNotEqual(one + one, one)
        self.assertIsInstance(two - one, Expr)
        self.assertIsInstance(one * one, Expr)
        self.assertIsInstance(two / one, Expr)
        self.assertIsInstance(one - two, Expr)
        self.assertEqual(one.mccode_c_type, 'char *')
        self.assertEqual(one.mccode_c_type_name, 'instr_type_string')

    def test_vector_Value(self):
        first = Expr.array([1, 2, 3])
        second = Expr.array([4, 5, 6])

        self.assertTrue(first.is_vector)
        self.assertEqual(first.shape_type, second.shape_type)
        self.assertEqual(first.vector_len, second.vector_len)

    def test_id_Value(self):
        sid = Expr.id('some_parameter')

        self.assertFalse(sid.is_str)
        self.assertTrue(sid.is_id)
        self.assertEqual(str(sid + Expr.int(1)), 'some_parameter + 1')

    def test_parameter_Value(self):
        par = Expr.parameter('instrument_parameter')
        self.assertFalse(par.is_str)
        # self.assertFalse(par.is_id)  # changed as of 2023-10-16 -- a parameter is an identifier
        self.assertTrue(par.is_parameter)
        # Verify that the whole reason for this object type existing works (inserting its name into macros)
        self.assertEqual(f'{par:p}', "_instrument_var._parameters.instrument_parameter")
        # The original implementation broke instrument printing, so str(par) should always be its bare name
        self.assertEqual(str(par), "instrument_parameter")
        self.assertEqual(f'{par}', 'instrument_parameter')
        # And, just in case it's useful, we can specify the prefix:
        self.assertEqual(f'{par:prefix:this_is_cool_}', "this_is_cool_instrument_parameter")

    def test_UnaryOp(self):
        val = Expr.int(1)
        # Negating a numeric int gives a simplified int, NOT an Expr with unary op structure
        self.assertEqual(-val, Expr.int(-1))
        # Double negation cancels out
        self.assertEqual(-(-val), val)
        self.assertEqual(round(val), val)

        val = Expr.int(-1)
        self.assertEqual(-val, Expr.int(1))
        # abs of negative int is simplified directly
        self.assertEqual(abs(val), Expr.int(1))
        # abs(abs(x)) == abs(x) for symbolic (non-numeric) values
        x = Expr.id('x')
        self.assertEqual(abs(abs(x)), abs(x))

        val = Expr.str('string')
        # Negating a string builds a symbolic expression (can't simplify)
        neg_val = -val
        self.assertIsInstance(neg_val, Expr)
        self.assertEqual(-neg_val, val)  # double negation cancels
        # abs of string also builds a symbolic expression
        self.assertIsInstance(abs(val), Expr)

        val = Expr.id('identifier')
        neg_val = -val
        self.assertIsInstance(neg_val, Expr)
        self.assertEqual(str(neg_val), '-identifier')
        abs_val = abs(val)
        self.assertIsInstance(abs_val, Expr)
        self.assertEqual(str(abs_val), 'fabs(identifier)')
        round_val = round(val)
        self.assertIsInstance(round_val, Expr)
        self.assertEqual(str(round_val), 'round(identifier)')

        val = Expr.float(1.)
        # Rounding a numeric float gives the float directly
        self.assertEqual(round(val), val)
        # round(abs(val)) != abs(val) when val is symbolic
        abs_x = abs(Expr.id('x'))
        self.assertNotEqual(round(abs_x), abs_x)
        # round(abs(float(1.))) simplifies to 1.0
        self.assertEqual(round(abs(Expr.float(1.))), Expr.float(1.))

        # C-style logical NOT
        not_val = Expr.parse('!val')
        self.assertEqual(str(not_val), '!(val)')

    def test_UnaryOp_as_type(self):
        import sympy
        from mccode_antlr.common.expression.sympy_classes import CNot
        # CNot creates a logical NOT expression
        uop = Expr([CNot(sympy.Symbol('val'))], DataType.undefined)
        self.assertEqual(str(uop), '!(val)')
        # Changing data type doesn't change the string representation
        iop = Expr(uop._exprs, DataType.int, uop._shape_type, uop._object_type)
        self.assertEqual(str(iop), '!(val)')
        fop = Expr(uop._exprs, DataType.float, uop._shape_type, uop._object_type)
        self.assertEqual(str(fop), '!(val)')


    def test_numeric_BinaryOp(self):
        f = [Expr.float(x) for x in range(3)]
        i = [Expr.float(x) for x in range(3)]
        # Numeric operations produce simplified values (not symbolic Exprs with BinaryOp structure)
        for a, b in ((f[1], f[2]), (i[1], i[2]), (f[1], i[2]), (i[1], f[2])):
            self.assertEqual(a + b, Expr.float(float(a.value + b.value)))
            self.assertEqual(a - b, Expr.float(float(a.value - b.value)))
            self.assertEqual(a * b, Expr.float(float(a.value * b.value)))

        one = Expr.id('one')
        two = Expr.id('two')
        # Symbolic operations produce Expr with the expected string representation
        for a, b in ((one, two), (one, i[2]), (one, f[2])):
            self.assertEqual(str(a + b), f'{str(a)} + {str(b)}')
            self.assertIsInstance(a + b, Expr)
            self.assertIsInstance(a - b, Expr)
            self.assertIsInstance(a * b, Expr)
            self.assertIsInstance(a / b, Expr)
        # except multiplication/division by numeric 1 simplifies
        for a, b in ((f[1], two), (i[1], two)):
            self.assertIsInstance(a + b, Expr)
            self.assertIsInstance(a - b, Expr)
            self.assertEqual(a * b, two)
            self.assertIsInstance(a / b, Expr)
        for a, b in ((one, i[1]), (two, f[1])):
            self.assertIsInstance(a + b, Expr)
            self.assertIsInstance(a - b, Expr)
            self.assertEqual(a * b, a)
            self.assertEqual(a / b, a)
        # Multiplying by zero gives zero
        self.assertTrue((one * f[0]).is_zero)
        self.assertTrue((two * i[0]).is_zero)
        self.assertTrue((i[0] / one).is_zero)
        self.assertTrue((f[0] / two).is_zero)

    def _style_tests(self, expr, c_style, python_style):
        self.assertEqual(str(expr), c_style)
        self.assertEqual(expr.to_python(), python_style)

    def test_identifier_BinaryOp(self):
        import sympy
        from mccode_antlr.common.expression.sympy_classes import (
            CStructAccess, CPointerAccess, CAnd, COr, CFunctionCall
        )
        one_sym = sympy.Symbol('one')
        two_sym = sympy.Symbol('two')
        one = Expr.id('one')
        two = Expr.id('two')

        # Function call: one(two)
        func_call = Expr([CFunctionCall(one_sym, two_sym)])
        self.assertEqual(str(func_call), 'one(two)')

        # Struct access: one.two
        struct_expr = Expr([CStructAccess(one_sym, two_sym)])
        self._style_tests(struct_expr, 'one.two', 'getattr(one, "two")')

        # Pointer access: one->two
        ptr_expr = Expr([CPointerAccess(one_sym, two_sym)])
        self._style_tests(ptr_expr, 'one->two', 'getattr(one, "two")')

        # Power: pow(one, two) in C, one**two in Python
        pow_expr = one ** two
        self._style_tests(pow_expr, 'pow(one, two)', 'one**two')

        # Logical or (C style only - Python printer doesn't support CAnd/COr)
        or_expr = Expr([COr(one_sym, two_sym)])
        self.assertEqual(str(or_expr), 'one || two')

        # Logical and (C style only)
        and_expr = Expr([CAnd(one_sym, two_sym)])
        self.assertEqual(str(and_expr), 'one && two')

        # Any-name function call
        any_func_sym = sympy.Symbol('any_function')
        any_func_expr = Expr([CFunctionCall(any_func_sym, one_sym, two_sym)])
        self.assertEqual(str(any_func_expr), 'any_function(one, two)')

    def test_identifier_TrinaryOp(self):
        test_expr = Expr.parse('test ? one : two')
        self._style_tests(test_expr, '(test ? one : two)', '(one if test else two)')

    def test_simple_Expr(self):
        pass

    def test_parse_Expr(self):

        self.assertEqual(Expr.parse('1'), Expr.int(1))
        self.assertEqual(Expr.parse('1.'), Expr.float(1))
        self.assertEqual(Expr.parse('0'), Expr.int(0))
        self.assertEqual(Expr.parse('0.'), Expr.float(0))
        self.assertEqual(Expr.parse('.0'), Expr.float(0))

        self.assertEqual(Expr.parse('1+1'), Expr.int(2))
        self.assertEqual(Expr.parse('1.+1.'), Expr.float(2))
        self.assertEqual(Expr.parse('1+1.0'), Expr.float(2))
        self.assertEqual(Expr.parse('1.0+1'), Expr.float(2))

        self.assertEqual(Expr.parse('1-1'), Expr.int(0))
        self.assertEqual(Expr.parse('1.-1.'), Expr.float(0))
        self.assertEqual(Expr.parse('1-1.0'), Expr.float(0))
        self.assertEqual(Expr.parse('1.0-1'), Expr.float(0))

        self.assertEqual(Expr.parse('1*1'), Expr.int(1))
        self.assertEqual(Expr.parse('1.*1.'), Expr.float(1))
        self.assertEqual(Expr.parse('1*1.0'), Expr.float(1))
        self.assertEqual(Expr.parse('1.0*1'), Expr.float(1))

        self.assertEqual(Expr.parse('1/1'), Expr.int(1))
        self.assertEqual(Expr.parse('1./1.'), Expr.float(1))
        self.assertEqual(Expr.parse('1/1.0'), Expr.float(1))
        self.assertEqual(Expr.parse('1.0/1'), Expr.float(1))

        self.assertEqual(Expr.parse('"blah"'), Expr.str('"blah"'))
        self.assertEqual(Expr.parse('blah'), Expr.id('blah'))

        sin_minus_pi_x_over_2 = Expr.parse('sin( -PI * x / 2.   )')
        # These two expressions have identical string representations because
        # SymPy canonicalises -PI*x/2 == -(PI*x/2) algebraically.
        wrong_precedence_expr = Expr.parse('sin( -(PI * x / 2.)  )')
        self.assertEqual(str(sin_minus_pi_x_over_2), str(wrong_precedence_expr))
        # SymPy canonically pulls the negative out: sin(-x) → -sin(x)
        self.assertEqual(str(sin_minus_pi_x_over_2), '-sin(0.5*PI*x)')

        # Multi-argument function call: arctan2(y, x)
        atan2_y_x = Expr.parse('arctan2(y, x)')
        self.assertEqual(str(atan2_y_x), 'arctan2(y, x)')

    def test_instrument_parameter(self):
        from antlr4 import InputStream
        from mccode_antlr import Flavor
        from mccode_antlr.grammar import McInstr_parse
        from mccode_antlr.instr import InstrVisitor
        from mccode_antlr.reader import Reader
        from mccode_antlr.common.expression import ObjectType
        instr_source = """
        DEFINE INSTRUMENT blah(int par=0)
        TRACE
        COMPONENT origin = Progress_bar() AT (0, 0, 0) RELATIVE ABSOLUTE
        COMPONENT source = Source_gen(T1=413.5, I1=10.22e12, T2=145.8, I2=3.44e13, T3=40.1, I3=2.78e13, dist=2,
                                      radius=0.06, focus_xw=0.1, focus_yh=0.1, lambda0=1.0, dlambda=0.5)
                           AT (0, 0, 0) RELATIVE PREVIOUS
        COMPONENT monitor = PSD_monitor(nx=par, ny=par, xwidth=0.1, yheight=0.1) AT (0, 0, 10.1) RELATIVE PREVIOUS
        END
        """
        tree = McInstr_parse(InputStream(instr_source), 'prog')
        visitor = InstrVisitor(Reader(flavor=Flavor.MCSTAS), None)
        # Parse the instrument definition and return an Instr object
        instr = visitor.visitProg(tree)
        nx = instr.components[-1].get_parameter('nx')
        self.assertTrue(nx.value.is_parameter)
        self.assertEqual(str(nx.value), 'par')

    def test_simplify(self):
        from mccode_antlr.common.expression import Expr
        is_two = Expr.parse('(2+4)/(1+2)')
        self.assertTrue(isinstance(is_two, Expr))
        is_two = is_two.simplify()
        # Simplifying an expression yields an expression
        self.assertTrue(isinstance(is_two, Expr))
        # Which is equal to the expected result of 2
        self.assertEqual(is_two, Expr.int(2))
        # Finally, the real test -- successfully simplifying an Expr produces a constant Expr
        self.assertTrue(is_two.is_constant)

    def test_evaluate(self):
        from mccode_antlr.common.expression import Expr
        known = {'bw1phase': Expr.float(0)}
        phase = Expr.parse('bw1phase / 2')
        self.assertTrue(isinstance(phase, Expr))
        phase = phase.evaluate(known)
        # Evaluating an expression yields an expression
        self.assertTrue(isinstance(phase, Expr))
        # Which is equal to the expected result of 0
        self.assertEqual(phase, Expr.float(0))
        # Finally, the real test -- successfully evaluating (and simplifying) an Expr produces a constant Expr
        self.assertTrue(phase.is_constant)

    def test_depends_on(self):
        from mccode_antlr.common.expression import Expr
        phase = Expr.parse('bw1phase / 2')
        self.assertTrue(phase.depends_on('bw1phase'))

        expr = Expr.parse('floor(1.4445)/sin(pi * angle / 180.)')
        for name in ('angle', 'pi'):
            self.assertTrue(expr.depends_on(name))
        for func_name in ('floor', 'sin'):
            self.assertFalse(expr.depends_on(func_name))
        for not_name in ('1.4445', '180.', 1.445, 180.0):
            self.assertFalse(expr.depends_on(not_name))

    def test_numeric_operations(self):
        from mccode_antlr.common.expression import Expr, DataType
        x = Expr.float(1.)
        for res in (1 + x, x + 1, 2 * x, x / 0.5, 2 / x):
            self.assertTrue(isinstance(res, Expr))
            self.assertTrue(res.data_type == DataType.float)
            self.assertEqual(res, Expr.float(2))
            self.assertEqual(res, 2)

    def test_numeric_expressions(self):
        for n_slits in (2, Expr.int(2)):
            for theta_0 in (Expr.float(100), Expr.id('variable')):
                delta = theta_0 / 2.0
                edges = [y * 360.0 / n_slits + x for y in range(int(n_slits)) for x in (-delta, delta)]
                self.assertEqual(len(edges), 4)
                for edge in edges:
                    self.assertTrue(isinstance(edge, Expr))

    def test_is_vector(self):
        self.assertTrue(Expr.array([1, 2, 3]).is_vector)
        self.assertFalse(Expr.int(1).is_vector)

        # This is needed for setting, e.g., component parameters from declared _vector_ variables
        expr = Expr.parse('-ex / values[0]')
        self.assertEqual(f'{expr}', '-ex/values[0]')

        self.assertFalse(expr.is_vector) # because values[0] is a scalar


class TestComparisonMethods(TestCase):
    """Tests for the named comparison expression-building methods on Expr and Value."""

    def test_value_parameter_classmethod(self):
        """Expr.parameter() creates ObjectType.parameter directly."""
        v = Expr.parameter('flag')
        self.assertTrue(v.is_id)
        self.assertTrue(v.is_parameter)
        self.assertEqual(v._object_type, ObjectType.parameter)
        self.assertEqual(str(v), 'flag')
        # format spec 'p' must prepend the instrument variable prefix
        self.assertEqual(format(v, 'p'), '_instrument_var._parameters.flag')

    def test_value_parameter_with_data_type(self):
        v = Expr.parameter('n', DataType.int)
        self.assertEqual(v.data_type, DataType.int)
        self.assertTrue(v.is_parameter)

    def test_expr_parameter_classmethod(self):
        """Expr.parameter() wraps Value.parameter."""
        from mccode_antlr.common.expression import Expr, ObjectType
        e = Expr.parameter('flag')
        self.assertTrue(e.is_id)
        self.assertTrue(e.is_parameter)
        self.assertEqual(str(e), 'flag')
        self.assertEqual(format(e, 'p'), '_instrument_var._parameters.flag')

    def test_expr_parameter_is_idempotent(self):
        """Expr.parameter() on an existing Expr returns it unchanged."""
        from mccode_antlr.common.expression import Expr
        e = Expr.parameter('flag')
        self.assertIs(Expr.parameter(e), e)

    def test_value_eq(self):
        """eq() always returns an Expr, never a bool."""
        v = Expr.parameter('flag')
        result = v.eq(Expr.int(1))
        self.assertIsInstance(result, Expr)
        self.assertEqual(str(result), 'flag==1')

    def test_value_ne(self):
        v = Expr.parameter('flag')
        result = v.ne(Expr.int(0))
        self.assertIsInstance(result, Expr)
        self.assertEqual(str(result), 'flag!=0')

    def test_expr_eq(self):
        """Expr.eq() always returns an Expr, never a bool."""
        from mccode_antlr.common.expression import Expr
        e = Expr.parameter('flag')
        result = e.eq(1)
        self.assertIsInstance(result, Expr)
        self.assertEqual(str(result), 'flag==1')

    def test_expr_ne(self):
        from mccode_antlr.common.expression import Expr
        e = Expr.parameter('mode')
        result = e.ne(0)
        self.assertIsInstance(result, Expr)
        self.assertEqual(str(result), 'mode!=0')

    def test_expr_lt(self):
        from mccode_antlr.common.expression import Expr
        result = Expr.parameter('n').lt(10)
        self.assertIsInstance(result, Expr)
        self.assertEqual(str(result), 'n<10')

    def test_expr_gt(self):
        from mccode_antlr.common.expression import Expr
        result = Expr.parameter('n').gt(0)
        self.assertIsInstance(result, Expr)
        self.assertEqual(str(result), 'n>0')

    def test_expr_le(self):
        from mccode_antlr.common.expression import Expr
        result = Expr.parameter('n').le(Expr.int(5))
        self.assertIsInstance(result, Expr)
        self.assertEqual(str(result), 'n<=5')

    def test_expr_ge(self):
        from mccode_antlr.common.expression import Expr
        result = Expr.parameter('n').ge(1)
        self.assertIsInstance(result, Expr)
        self.assertEqual(str(result), 'n>=1')

    def test_expr_eq_between_parameters(self):
        """Comparison between two parameter Expr objects."""
        from mccode_antlr.common.expression import Expr
        a = Expr.parameter('mode')
        b = Expr.parameter('other')
        result = a.eq(b)
        self.assertIsInstance(result, Expr)
        self.assertEqual(str(result), 'mode==other')

    def test_parameter_format_in_comparison(self):
        """format(..., 'p') propagates through comparison expressions."""
        from mccode_antlr.common.expression import Expr
        result = Expr.parameter('flag').eq(1)
        self.assertEqual(format(result, 'p'), '_instrument_var._parameters.flag==1')


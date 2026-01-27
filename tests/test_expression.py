from unittest import TestCase
from mccode_antlr.common.expression import (
    Expr, Value, Op, UnaryOp, BinaryOp, TrinaryOp, DataType, ShapeType, ObjectType, OpStyle
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
        float_value = Value.float(1)
        int_value = Value.int(1)
        str_value = Value.str('1')
        id_value = Value.id('one')
        array_value = Value.array([1])
        function_value = Value.function('ones')

        for x in (float_value, int_value, str_value, id_value, array_value, function_value):
            self.assertFalse(x.is_op)
            self.assertFalse(x.is_zero)

        self.assertEqual(float_value.object_type, ObjectType.value)
        self.assertEqual(int_value.object_type, ObjectType.value)
        self.assertEqual(str_value.object_type, ObjectType.value)
        self.assertEqual(id_value.object_type, ObjectType.identifier)
        self.assertEqual(array_value.object_type, ObjectType.value)
        self.assertEqual(function_value.object_type, ObjectType.function)

        for x, y in ((float_value, ShapeType.scalar), (int_value, ShapeType.scalar), (str_value, ShapeType.scalar),
                     (id_value, ShapeType.scalar), (array_value, ShapeType.vector), (function_value, ShapeType.scalar)):
            self.assertEqual(x.shape_type, y)

        for x in (float_value, int_value, id_value, array_value, function_value):
            self.assertFalse(x.is_str)
        self.assertTrue(str_value.is_str)

        for x in (float_value, int_value, str_value, array_value, function_value):
            self.assertTrue(x.is_value(x._value))

        # Identifiers are not values:
        self.assertTrue(id_value.is_id)
        self.assertFalse(id_value.is_value(id_value._value))

        for x in (float_value, int_value, str_value, id_value, function_value):
            self.assertTrue(x.is_scalar)
            self.assertFalse(x.is_vector)
        self.assertFalse(array_value.is_scalar)
        self.assertTrue(array_value.is_vector)

    def test_null_vector_Value(self):
        array = Value.array("NULL")
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
        one = Value.float(1)
        two = Value.float(2)
        self._numeric_Value_checks(one, two)
        self.assertEqual(one.mccode_c_type, 'double')
        self.assertEqual(one.mccode_c_type_name, 'instr_type_double')

    def test_int_Value(self):
        one = Value.int(1)
        two = Value.int(2)
        self._numeric_Value_checks(one, two)
        self.assertEqual(one.mccode_c_type, 'int')
        self.assertEqual(one.mccode_c_type_name, 'instr_type_int')

    def test_str_Value(self):
        one = Value.str('one')
        two = Value.str('two')
        self.assertEqual(one, one)
        self.assertEqual(one + one, BinaryOp(DataType.undefined, OpStyle.C, '+', one, one))
        self.assertEqual(two - one, BinaryOp(DataType.undefined, OpStyle.C,'-', two, one))
        self.assertEqual(one * one, BinaryOp(DataType.undefined, OpStyle.C,'*', one, one))
        self.assertRaises(RuntimeError, lambda: two / one)
        self.assertEqual(one - two, BinaryOp(DataType.undefined, OpStyle.C,'-', one, two))
        self.assertEqual(one.mccode_c_type, 'char *')
        self.assertEqual(one.mccode_c_type_name, 'instr_type_string')

    def test_vector_Value(self):
        from mccode_antlr.common.expression import Value, DataType
        first = Value.array([1, 2, 3], DataType.float)
        second = Value.array([4, 5, 6], DataType.int)

        self.assertTrue(first.is_vector)
        self.assertEqual(first.shape_type, second.shape_type)
        self.assertEqual(first.vector_len, second.vector_len)
        self.assertNotEqual(first.data_type, second.data_type)
        # Addition concatenates the arrays and promotes the datatype
        self.assertEqual(first + second, Value.array([1, 2, 3, 4, 5, 6], DataType.float))

    def test_id_Value(self):
        sid = Value.id('some_parameter')

        self.assertFalse(sid.is_str)
        self.assertTrue(sid.is_id)
        self.assertEqual(sid + Value.int(1), BinaryOp(DataType.undefined, OpStyle.C, '+', sid, Value.int(1)))

    def test_parameter_Value(self):
        par = Value('instrument_parameter', _object=ObjectType.parameter)
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
        val = Value.int(1)
        # This one is not equal because the unary minus on a numeric value is pushed inside directly
        self.assertNotEqual(-val, UnaryOp(DataType.undefined, OpStyle.C,'-', val))
        # But negating the explicit unary minus operation pops-out its contents
        self.assertEqual(-UnaryOp(DataType.undefined, OpStyle.C,'-', val), val)
        self.assertEqual(round(val), val)

        val = Value.int(-1)
        self.assertNotEqual(-val, UnaryOp(DataType.undefined, OpStyle.C,'-', val))
        self.assertEqual(-UnaryOp(DataType.undefined, OpStyle.C, '-', val), val)
        # again, unary absolute value is pushed onto the contained integer directly
        self.assertNotEqual(abs(val), UnaryOp(DataType.undefined, OpStyle.C, 'abs', val))
        self.assertEqual(abs(val), Value.int(1))
        # abs(abs(x)) == abs(x) [even if we dont know anything about x]
        self.assertEqual(abs(UnaryOp(DataType.undefined, OpStyle.C, 'abs', val)), UnaryOp(DataType.undefined, OpStyle.C, 'abs', val))

        val = Value.str('string')
        # FIXME consider changing this behaviour, since negating a string does not make sense
        self.assertEqual(-val, UnaryOp(DataType.undefined, OpStyle.C, '-', val))
        self.assertEqual(-UnaryOp(DataType.undefined, OpStyle.C, '-', val), val)
        # Nor does the absolute value of a string ... but other (non Python) unary operations make sense
        self.assertEqual(abs(val), UnaryOp(DataType.undefined, OpStyle.C, 'abs', val))

        val = Value.id('identifier')
        self.assertEqual(-val, UnaryOp(DataType.undefined, OpStyle.C, '-', val))
        self.assertEqual(abs(val), UnaryOp(DataType.undefined, OpStyle.C, 'abs', val))
        self.assertEqual(round(val), UnaryOp(DataType.undefined, OpStyle.C, 'round', val))

        val = Value.float(1.)
        # Again, some unary operations get pushed directly onto the underlying value
        self.assertEqual(round(val), val)
        # But if we make an explicit wrapped UnaryOp they do not
        self.assertNotEqual(round(UnaryOp(DataType.undefined, OpStyle.C, 'abs', val)), UnaryOp(DataType.undefined, OpStyle.C, 'abs', val))
        self.assertNotEqual(round(UnaryOp(DataType.undefined, OpStyle.C, 'abs', val)), val)

        not_val = UnaryOp(DataType.undefined, OpStyle.C,'__not__', Value.id('val'))
        self.assertEqual(str(not_val), '!val')
        not_val.style = OpStyle.PYTHON
        self.assertEqual(str(not_val), 'not val')

    def test_UnaryOp_as_type(self):
        uop = UnaryOp(DataType.undefined, OpStyle.C, '__not__', Value.id('val'))
        self.assertEqual(str(uop), '!val')
        iop = uop.as_type(DataType.int)
        self.assertEqual(str(iop), '!val')
        fop = uop.as_type(DataType.float)
        self.assertEqual(str(fop), '!val')


    def test_numeric_BinaryOp(self):
        f = [Value.float(x) for x in range(3)]
        i = [Value.float(x) for x in range(3)]
        # simple operations on numeric values are applied directly, which does not produce a BinaryOp object
        for a, b in ((f[1], f[2]), (i[1], i[2]), (f[1], i[2]), (i[1], f[2])):
            self.assertNotEqual(a + b, BinaryOp(DataType.undefined, OpStyle.C, '+', a, b))
            self.assertNotEqual(a - b, BinaryOp(DataType.undefined, OpStyle.C, '-', a, b))
            self.assertNotEqual(a * b, BinaryOp(DataType.undefined, OpStyle.C, '*', a, b))
            self.assertNotEqual(a / b, BinaryOp(DataType.undefined, OpStyle.C, '/', a, b))

        one = Value.id('one')
        two = Value.id('two')
        # simple operations on non-numeric values are not applied directly, which does produce a BinaryOp object
        for a, b in ((one, two), (one, i[2]), (one, f[2])):
            self.assertEqual(a + b, BinaryOp(DataType.undefined, OpStyle.C, '+', a, b))
            self.assertEqual(a - b, BinaryOp(DataType.undefined, OpStyle.C, '-', a, b))
            self.assertEqual(a * b, BinaryOp(DataType.undefined, OpStyle.C, '*', a, b))
            self.assertEqual(a / b, BinaryOp(DataType.undefined, OpStyle.C, '/', a, b))
        # except in the special case where we multiply or divide by a numeric 1
        for a, b in ((f[1], two), (i[1], two)):
            self.assertEqual(a + b, BinaryOp(DataType.undefined, OpStyle.C, '+', a, b))
            self.assertEqual(a - b, BinaryOp(DataType.undefined, OpStyle.C, '-', a, b))
            self.assertEqual(a * b, b)
            self.assertEqual(a / b, BinaryOp(DataType.undefined, OpStyle.C, '/', a, b))
        for a, b in ((one, i[1]), (two, f[1])):
            self.assertEqual(a + b, BinaryOp(DataType.undefined, OpStyle.C, '+', a, b))
            self.assertEqual(a - b, BinaryOp(DataType.undefined, OpStyle.C, '-', a, b))
            self.assertEqual(a * b, a)
            self.assertEqual(a / b, a)
        # Or multiply by numeric zero
        self.assertTrue((one * f[0]).is_zero)
        self.assertTrue((two * i[0]).is_zero)
        self.assertTrue((i[0] / one).is_zero)
        self.assertTrue((f[0] / two).is_zero)

    def _style_tests(self, op, c_style, python_style):
        self.assertEqual(str(op), c_style)
        op.style = OpStyle.PYTHON
        self.assertEqual(str(op), python_style)

    def test_identifier_BinaryOp(self):
        from mccode_antlr.common.expression import Value, BinaryOp
        one, two = [Value.id(x) for x in ('one', 'two')]
        # BinaryOp allows '__call__' with any value types, but 'left' _should_ have a object_type of ObjectType.function
        self.assertEqual(str(BinaryOp(DataType.undefined, OpStyle.C, '__call__', one, two)), 'one(two)')
        # Other special binary operations have different representations in C vs Python
        for op, c, py in (('struct_access', 'one.two', 'getattr(one, "two")'),
                          ('pointer_access', 'one->two', 'getattr(one, "two")'),
                          ('pow', 'one^two', 'one**two'),
                          ('or', 'one || two', 'one or two'),
                          ('and', 'one && two', 'one and two')):
            self._style_tests(BinaryOp(DataType.undefined, OpStyle.C, f'__{op}__', one, two), c, py)

        self.assertEqual(str(BinaryOp(DataType.undefined, OpStyle.C, 'any_function', one, two)), 'any_function(one, two)')

    def test_identifier_TrinaryOp(self):
        test, one, two = [Value.id(x) for x in ('test', 'one', 'two')]
        self._style_tests(TrinaryOp(DataType.undefined, OpStyle.C, '__trinary__', test, one, two), 'test ? one : two', 'one if test else two')

    def test_simple_Expr(self):
        pass

    def test_parse_Expr(self):

        self.assertEqual(Expr.parse('1'), Value.int(1))
        self.assertEqual(Expr.parse('1.'), Value.float(1))
        self.assertEqual(Expr.parse('0'), Value.int(0))
        self.assertEqual(Expr.parse('0.'), Value.float(0))
        self.assertEqual(Expr.parse('.0'), Value.float(0))

        self.assertEqual(Expr.parse('1+1'), Value.int(2))
        self.assertEqual(Expr.parse('1.+1.'), Value.float(2))
        self.assertEqual(Expr.parse('1+1.0'), Value.float(2))
        self.assertEqual(Expr.parse('1.0+1'), Value.float(2))

        self.assertEqual(Expr.parse('1-1'), Value.int(0))
        self.assertEqual(Expr.parse('1.-1.'), Value.float(0))
        self.assertEqual(Expr.parse('1-1.0'), Value.float(0))
        self.assertEqual(Expr.parse('1.0-1'), Value.float(0))

        self.assertEqual(Expr.parse('1*1'), Value.int(1))
        self.assertEqual(Expr.parse('1.*1.'), Value.float(1))
        self.assertEqual(Expr.parse('1*1.0'), Value.float(1))
        self.assertEqual(Expr.parse('1.0*1'), Value.float(1))

        self.assertEqual(Expr.parse('1/1'), Value.int(1))
        self.assertEqual(Expr.parse('1./1.'), Value.float(1))
        self.assertEqual(Expr.parse('1/1.0'), Value.float(1))
        self.assertEqual(Expr.parse('1.0/1'), Value.float(1))

        self.assertEqual(Expr.parse('"blah"'), Value.str('"blah"'))
        self.assertEqual(Expr.parse('blah'), Value.id('blah'))

        sin_minus_pi_x_over_2 = Expr.parse('sin( -PI * x / 2.   )')
        pi = Expr.id('PI')
        x = Expr.id('x')
        sin = Value('sin', _object=ObjectType.function)
        uop, bop, u, c = UnaryOp, BinaryOp, DataType.undefined, OpStyle.C
        two = Value.float(2)
        # These two expressions have identical string representations,
        # but an error in the grammar caused the Lexer/Parser pick the second.
        # Now that the error is fixed, the Unary operation of negation has higher
        # precedence than either the multiplication or division.
        expr = bop(u, c, '__call__', [sin], [
            bop(u, c, '/', [bop(u, c, '*', [uop(u, c, '-', pi)], [x])], [two])
        ])
        wrong_precedence_expr = bop(u, c, '__call__', [sin], [
            uop(u, c, '-', [bop(u, c, '/', [bop(u, c, '*', [pi], [x])], [two])])
        ])

        self.assertEqual(sin_minus_pi_x_over_2, expr)
        self.assertEqual(str(sin_minus_pi_x_over_2), str(expr))
        self.assertEqual(str(sin_minus_pi_x_over_2), str(wrong_precedence_expr))

        # One reason that Expr has a list of expressions:
        atan2_y_x = Expr.parse('arctan2(y, x)')
        atan2 = Value('arctan2', _object=ObjectType.function)
        y = Expr.id('y')
        expr = BinaryOp(DataType.undefined, OpStyle.C, '__call__', [atan2], [y, x])
        self.assertEqual(atan2_y_x, expr)

    def test_instrument_parameter(self):
        from antlr4 import InputStream
        from mccode_antlr import Flavor
        from mccode_antlr.grammar import McInstr_parse
        from mccode_antlr.instr import InstrVisitor
        from mccode_antlr.reader import Reader
        from mccode_antlr.common.expression import Value, ObjectType
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
        self.assertEqual(nx.value, Value('par', _object=ObjectType.parameter))

    def test_simplify(self):
        from mccode_antlr.common.expression import Expr, Value
        is_two = Expr.parse('(2+4)/(1+2)')
        self.assertTrue(isinstance(is_two, Expr))
        is_two = is_two.simplify()
        # Simplifying an expression yields an expression
        self.assertTrue(isinstance(is_two, Expr))
        # Which is equal to the expected result of 2
        self.assertEqual(is_two, Expr.int(2))
        # For it to be constant it can only have one sub expression part:
        self.assertEqual(len(is_two.expr), 1)
        # Which must be a Value
        self.assertTrue(isinstance(is_two.expr[0], Value))
        # That is not an identifier
        self.assertFalse(is_two.expr[0].is_id)
        # Finally, the real test -- successfully simplifying an Expr produces a constant Expr
        self.assertTrue(is_two.is_constant)

    def test_evaluate(self):
        from mccode_antlr.common.expression import Expr, Value
        known = {'bw1phase': Expr.float(0)}
        phase = Expr.parse('bw1phase / 2')
        self.assertTrue(isinstance(phase, Expr))
        phase = phase.evaluate(known)
        # Evaluating an expression yields an expression
        self.assertTrue(isinstance(phase, Expr))
        # Which is equal to the expected result of 0
        self.assertEqual(phase, Expr.float(0))
        # For it to be constant it can only have one sub expression part:
        self.assertEqual(len(phase.expr), 1)
        # Which must be a Value
        self.assertTrue(isinstance(phase.expr[0], Value))
        # That is not an identifier
        self.assertFalse(phase.expr[0].is_id)
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
        ex = Expr.id('ex')
        values = Value('values', DataType.float, ObjectType.identifier, ShapeType.vector)
        expr = -ex / BinaryOp(DataType.undefined, OpStyle.C, '__getitem__', [values], Expr.int(0).expr)
        self.assertEqual(f'{expr}', '-ex / values[0]')

        self.assertFalse(expr.is_vector) # because values[0] is a scalar

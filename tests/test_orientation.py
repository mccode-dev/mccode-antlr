from unittest import TestCase


def _make_seitz_list(tx, ty, tz, degrees=False):
    from mccode_antlr.common import Expr
    from mccode_antlr.instr.orientation import Seitz, cos_value, sin_value
    o, z = Expr.float(1), Expr.float(0)
    cx, sx = cos_value(tx, degrees), sin_value(tx, degrees)
    cy, sy = cos_value(ty, degrees), sin_value(ty, degrees)
    cz, sz = cos_value(tz, degrees), sin_value(tz, degrees)
    rx = Seitz(o, z, z, z, z, cx, sx, z, z, -sx, cx, z)
    ry = Seitz(cy, z, -sy, z, z, o, z, z, sy, z, cy, z)
    rz = Seitz(cz, sz, z, z, -sz, cz, z, z, z, z, o, z)
    return rx, ry, rz


def _random_angles_radian():
    from numpy import random, pi
    from mccode_antlr.common import Expr
    return [Expr.float(random.rand() * 2 * pi - pi) for _ in range(3)]


def _random_angles_degrees():
    from numpy import random
    from mccode_antlr.common import Expr
    return [Expr.float(random.rand() * 360 - 180) for _ in range(3)]


def _random_vector(minimum: float = 0, maximum: float = 1):
    from numpy import random
    from mccode_antlr.common import Expr
    from mccode_antlr.instr.orientation import Vector

    def _random():
        return Expr.float(random.rand() * (maximum - minimum) + minimum)

    return Vector(_random(), _random(), _random())


def _mcstas_verified_rotations():
    from mccode_antlr.instr.orientation import Rotation
    from mccode_antlr.common import Expr
    o, z = [Expr.float(x) for x in (1, 0)]
    # Verified from McStas compile instrument _*_var.rotation_absolute via --trace output:
    mc = {'zpz': Rotation(z, z, -o, z, o, z, o, z, z),
          'pzz': Rotation(o, z, z, z, z, o, z, -o, z),
          'zzp': Rotation(z, o, z, -o, z, z, z, z, o),
          'pzp': Rotation(z, z, o, -o, z, z, z, -o, z),
          'mzp': Rotation(z, z, -o, -o, z, z, z, o, z),
          'pzm': Rotation(z, z, -o, o, z, z, z, -o, z),
          'mzm': Rotation(z, z, o, o, z, z, z, o, z),
          'zpp': Rotation(z, o, z, z, z, o, o, z, z),
          'zmp': Rotation(z, o, z, z, z, -o, -o, z, z),
          'zmm': Rotation(z, -o, z, z, z, o, -o, z, z),
          'zpm': Rotation(z, -o, z, z, z, -o, o, z, z),
          'ppz': Rotation(z, o, z, z, z, o, o, z, z),
          'ppp': Rotation(z, z, o, z, -o, z, o, z, z),
          'mpp': Rotation(z, z, -o, z, o, z, o, z, z),
          'pmp': Rotation(z, z, o, z, o, z, -o, z, z),
          'ppm': Rotation(z, z, -o, z, o, z, o, z, z),
          'mmp': Rotation(z, z, -o, z, -o, z, -o, z, z),
          'mpm': Rotation(z, z, o, z, -o, z, o, z, z),
          'pmm': Rotation(z, z, -o, z, -o, z, -o, z, z),
          'mmm': Rotation(z, z, o, z, o, z, -o, z, z)}
    return mc


class TestOrientation(TestCase):
    def test_simplifications_in_trig_functions(self):
        from mccode_antlr.instr.orientation import sin_value, cos_value
        from mccode_antlr.common import Expr
        self.assertEqual(sin_value(Expr.float(0)), Expr.float(0))
        self.assertEqual(sin_value(Expr.float(90)), Expr.float(1))
        self.assertEqual(sin_value(Expr.float(-90)), Expr.float(-1))
        self.assertEqual(sin_value(Expr.float(180)), Expr.float(0))

        self.assertEqual(cos_value(Expr.float(0)), Expr.float(1))
        self.assertEqual(cos_value(Expr.float(90)), Expr.float(0))
        self.assertEqual(cos_value(Expr.float(-90)), Expr.float(0))
        self.assertEqual(cos_value(Expr.float(180)), Expr.float(-1))


    def test_matrix_vector_multiply(self):
        from mccode_antlr.instr.orientation import Vector, Matrix
        from mccode_antlr.common import Expr
        from numpy import random
        v = Vector(*[Expr.float(random.rand()) for _ in range(3)])
        m = Matrix(*[Expr.float(random.rand()) for _ in range(9)])
        mv = m * v
        self.assertEqual(mv.x, m.xx * v.x + m.xy * v.y + m.xz * v.z)
        self.assertEqual(mv.y, m.yx * v.x + m.yy * v.y + m.yz * v.z)
        self.assertEqual(mv.z, m.zx * v.x + m.zy * v.y + m.zz * v.z)
        z, o = Expr.float(0), Expr.float(1)
        identity = Matrix(o, z, z, z, o, z, z, z, o)
        self.assertEqual(identity * v, v)
        exchange_xy = Matrix(z, o, z, o, z, z, z, z, o)
        self.assertEqual(exchange_xy * v, Vector(v.y, v.x, v.z))
        exchange_xz = Matrix(z, z, o, z, o, z, o, z, z)
        self.assertEqual(exchange_xz * v, Vector(v.z, v.y, v.x))
        exchange_yz = Matrix(o, z, z, z, z, o, z, o, z)
        self.assertEqual(exchange_yz * v, Vector(v.x, v.z, v.y))

    def test_matrix_matrix_subtract(self):
        from mccode_antlr.instr.orientation import Matrix, Vector
        from mccode_antlr.common import Expr
        from numpy import random
        from itertools import zip_longest
        m1 = Matrix(*[Expr.float(random.rand()) for _ in range(9)])
        m2 = Matrix(*[Expr.float(random.rand()) for _ in range(9)])
        m3 = m1 - m2
        for one, two, three in zip_longest(iter(m1), iter(m2), iter(m3)):
            self.assertEqual(one - two, three)
        m4 = m3 - m3
        v = Vector(*[Expr.float(random.rand()) for _ in range(3)])
        self.assertTrue((m4 * v).is_null)

    def test_vector_length(self):
        from mccode_antlr.instr.orientation import Vector
        from mccode_antlr.common import Expr
        from numpy import random, sqrt
        v = Vector(Expr.float(0), Expr.float(0), Expr.float(0))
        self.assertEqual(v.length(), Expr.float(0))
        self.assertTrue(v.is_null())

        v = Vector(Expr.float(2), Expr.float(0), Expr.float(0))
        self.assertEqual(v.length(), Expr.float(2))
        v = Vector(Expr.float(0), Expr.float(-9), Expr.float(0))
        self.assertEqual(v.length(), Expr.float(9))
        raw_v = [random.rand() for _ in range(3)]
        v = Vector(*[Expr.float(x) for x in raw_v])
        self.assertAlmostEqual(v.length(), Expr.float(sqrt(sum([x * x for x in raw_v]))))

    def test_rotation_matrix(self):
        from mccode_antlr.instr.orientation import Rotation, Angles, _rotation_angles_to_axes_coordinates
        from mccode_antlr.common import Expr
        from numpy import random, pi
        from itertools import zip_longest
        a = Angles(*[Expr.float(random.rand() * 2 * pi - pi) for _ in range(3)])
        while a.is_null():
            a = Angles(*[Expr.float(random.rand() * 2 * pi - pi) for _ in range(3)])
        axes, coordinates = _rotation_angles_to_axes_coordinates(a, degrees=False)
        r = Rotation(*axes)
        inv_r = r.inverse()
        one = r * inv_r
        identity = Rotation()
        for i, j in zip_longest(iter(one), iter(identity)):
            self.assertAlmostEqual(i, j)

        zero = r - r
        for i in zero:
            self.assertEqual(i, Expr.float(0))

    def test_rotation_mccode_style(self):
        from mccode_antlr.instr.orientation import Rotation, Angles, Matrix
        from mccode_antlr.common import Expr
        o, z, p, m = [Expr.float(x) for x in (1, 0, 90, -90)]
        angles = {'zpz': Rotation.from_angles(Angles(z, p, z)),
                  'pzp': Rotation.from_angles(Angles(p, z, p)),
                  'zzp': Rotation.from_angles(Angles(z, z, p)),
                  'ppz': Rotation.from_angles(Angles(p, p, z)),
                  'mzp': Rotation.from_angles(Angles(m, z, p)),
                  'pzm': Rotation.from_angles(Angles(p, z, m)),
                  'mzm': Rotation.from_angles(Angles(m, z, m)),
                  'zpp': Rotation.from_angles(Angles(z, p, p)),
                  'zpm': Rotation.from_angles(Angles(z, p, m)),
                  'zmp': Rotation.from_angles(Angles(z, m, p)),
                  'zmm': Rotation.from_angles(Angles(z, m, m)),
                  'ppp': Rotation.from_angles(Angles(p, p, p)),
                  'ppm': Rotation.from_angles(Angles(p, p, m)),
                  'pmp': Rotation.from_angles(Angles(p, m, p)),
                  'pmm': Rotation.from_angles(Angles(p, m, m)),
                  'mpp': Rotation.from_angles(Angles(m, p, p)),
                  'mpm': Rotation.from_angles(Angles(m, p, m)),
                  'mmp': Rotation.from_angles(Angles(m, m, p)),
                  'mmm': Rotation.from_angles(Angles(m, m, m))}

        # Verified from McStas compile instrument _*_var.rotation_absolute via --trace output:
        mc = _mcstas_verified_rotations()
        # constructing the Rotation matrix may have small numerical errors, so we round to 14 decimal places
        # and compare to the zero Matrix
        for key in angles:
            self.assertEqual(round(abs(angles[key] - mc[key]), 14), Matrix())

    def test_rotation_parts(self):
        from mccode_antlr.instr.orientation import RotationX, RotationY, RotationZ
        from mccode_antlr.common import Expr
        p = Expr.float(90.)
        mc = _mcstas_verified_rotations()
        parts = {
            'pzz': RotationX(v=p, degrees=True),
            'zpz': RotationY(v=p, degrees=True),
            'zzp': RotationZ(v=p, degrees=True),
        }
        for key, part in parts.items():
            self.assertEqual(part.rotation(), mc[key])


    def test_seitz_multiply_identity(self):
        from numpy import random
        from mccode_antlr.common import Expr
        from mccode_antlr.instr.orientation import Seitz
        o, z = Expr.float(1), Expr.float(0)
        a = Seitz(o, z, z, z, z, o, z, z, z, z, o, z)
        b = a * a
        self.assertEqual(a, b)

        c = Seitz(*[Expr.float(random.rand()) for _ in range(12)])
        b = a * c
        self.assertEqual(b, c)

    def test_seitz_inverse(self):
        from numpy import random, pi
        from mccode_antlr.common import Expr
        from mccode_antlr.instr.orientation import Seitz, cos_value, sin_value
        o, z = Expr.float(1), Expr.float(0)
        a = Seitz(o, z, z, z, z, o, z, z, z, z, o, z)
        # Construct a matrix that *has* an inverse (use rotations to make life easier)
        ts = ([Expr.float(30/180*pi) for _ in range(3)], _random_angles_radian(),)
        for tx, ty, tz in ts:
            rx, ry, rz = _make_seitz_list(tx, ty, tz)
            b = rz * (ry * rx)
            c = b.inverse()
            d = c * b

            for i, j in zip(d, a):
                self.assertAlmostEqual(i, j)

            for i, j in zip(b, c.inverse()):
                self.assertAlmostEqual(i, j)

    def test_OrientationPart(self):
        from mccode_antlr.common import Expr
        from mccode_antlr.instr.orientation import Part, Vector
        op = Part()
        self.assertFalse(op.is_translation)
        self.assertFalse(op.is_rotation)
        self.assertTrue(op.is_identity)
        self.assertTrue(op.all_values)
        self.assertTrue(op.is_constant)

        axis, angle, unit = op.rotation_axis_angle
        self.assertEqual(unit, 'degrees')
        self.assertEqual(angle, Expr.float(0))
        # Since the angle is zero, the axis is degenerate and the returned value depends on details of the eigenvalue
        # solver, which we are not testing here.

        tx, ty, tz = _random_angles_degrees()
        while tx.is_zero or ty.is_zero or tz.is_zero:
            print(f'{tx=} {ty=} {tz=} must all be finite')
            tx, ty, tz = _random_angles_degrees()
        rx, ry, rz = _make_seitz_list(tx, ty, tz, degrees=True)

        # for individual rotations, it's easy to prove that axes and coordinates rotate opposite each other:
        opx = Part(rx)
        opy = Part(ry)
        opz = Part(rz)

        for o in (opx, opy, opz):
            if not o.is_rotation:
                print(f'This test fails despite finite {tx}, {ty} and {tz}? Why is {o} not a rotation?')
            self.assertTrue(o.is_rotation)
            self.assertFalse(o.is_translation)
            self.assertFalse(o.is_identity)
            self.assertTrue(o.all_values)
            self.assertTrue(o.is_constant)
            if not (o * o.inverse()).is_identity:
                # This less-robust identity test is needed because of possible numerical errors
                self.assertAlmostEqual((o * o.inverse()).axes.trace(), Expr.float(3),
                                       msg=f'{o} * {o.inverse()} = {o * o.inverse()} is not identity {tx=} {ty=} {tz=}')
            if not (o.inverse() * o).is_identity:
                self.assertAlmostEqual((o.inverse() * o).axes.trace(), Expr.float(3),
                                       msg=f'{o.inverse()} * {o} = {o.inverse() * o} is not identity {tx=} {ty=} {tz=}')

        vx = Vector(Expr.float(1), Expr.float(0), Expr.float(0))
        vy = Vector(Expr.float(0), Expr.float(1), Expr.float(0))
        vz = Vector(Expr.float(0), Expr.float(0), Expr.float(1))

        for o, t, v in [(opx, tx, vx), (opy, ty, vy), (opz, tz, vz)]:
            axis, angle, unit = o.rotation_axis_angle
            if (angle * t) < Expr.float(0):
                # this shouldn't happen since we've selected all vectors to be positive
                angle *= Expr.float(-1)
                axis = Vector(-axis.x, -axis.y, -axis.z)
            self.assertEqual(unit, 'degrees')
            self.assertAlmostEqual(angle, t)
            self.assertEqual(axis, v)

    def test_RotationParts(self):
        from mccode_antlr.common import Expr
        from mccode_antlr.instr.orientation import RotationPart, RotationX, RotationY, RotationZ, Angles, Vector

        rp = RotationPart()
        self.assertTrue(rp.is_constant)
        self.assertFalse(rp.is_translation)
        self.assertFalse(rp.is_rotation)
        self.assertTrue(rp.is_identity)
        self.assertEqual(rp.rotation_axis, Vector(Expr.float(0), Expr.float(0), Expr.float(0)))
        self.assertEqual(rp.position(), Vector(Expr.float(0), Expr.float(0), Expr.float(0)))

        # Since we use random angles, sample more of angle space to increase the chance of finding problems
        for _ in range(500):
            tx, ty, tz = _random_angles_degrees()
            # for individual rotations, it's easy to prove that axes and coordinates rotate opposite each other:
            rpx = RotationX(v=tx, degrees=True)
            self.assertTrue(rpx.is_constant)
            self.assertFalse(rpx.is_translation)
            self.assertTrue(rpx.is_rotation)
            self.assertFalse(rpx.is_identity)
            self.assertEqual(rpx.rotation_axis, Vector(Expr.float(1), Expr.float(0), Expr.float(0)))
            self.assertEqual(rpx.angles(), Angles(tx, Expr.float(0), Expr.float(0)))
            ex = rpx * rpx.inverse()
            if not ex.is_identity:
                # This less-robust identity test is needed because of possible numerical errors
                self.assertAlmostEqual(ex.axes.trace(), Expr.float(3),
                                       msg=f'{rpx} * {rpx.inverse()} = {ex} is not identity for {tx=}')

            rpy = RotationY(v=ty, degrees=True)
            self.assertTrue(rpy.is_constant)
            self.assertFalse(rpy.is_translation)
            self.assertTrue(rpy.is_rotation)
            self.assertFalse(rpy.is_identity)
            self.assertEqual(rpy.rotation_axis, Vector(Expr.float(0), Expr.float(1), Expr.float(0)))
            self.assertEqual(rpy.angles(), Angles(Expr.float(0), ty, Expr.float(0)))
            ey = rpy * rpy.inverse()
            if not ey.is_identity:
                self.assertAlmostEqual(ey.axes.trace(), Expr.float(3),
                                       msg=f'{rpy} * {rpy.inverse()} = {ey} is not identity for {ty=}')

            rpz = RotationZ(v=tz, degrees=True)
            self.assertTrue(rpz.is_constant)
            self.assertFalse(rpz.is_translation)
            self.assertTrue(rpz.is_rotation)
            self.assertFalse(rpz.is_identity)
            self.assertEqual(rpz.rotation_axis, Vector(Expr.float(0), Expr.float(0), Expr.float(1)))
            self.assertEqual(rpz.angles(), Angles(Expr.float(0), Expr.float(0), tz))
            ez = rpz * rpz.inverse()
            if not ez.is_identity:
                self.assertAlmostEqual(ez.axes.trace(), Expr.float(3),
                                       msg=f'{rpz} * {rpz.inverse()} = {ez} is not identity for {tz=}')

    def test_RotationPart_subclass_post_init_is_called(self):
        from mccode_antlr.instr.orientation import Rotation, RotationX, RotationY, RotationZ
        tx, ty, tz = _random_angles_degrees()
        while tx.is_zero or ty.is_zero or tz.is_zero:
            print(f'{tx=} {ty=} {tz=} must all be finite')
            tx, ty, tz = _random_angles_degrees()

        rpx = RotationX(v=tx, degrees=True)
        self.assertFalse(rpx.is_identity)
        self.assertNotEqual(rpx.rotation(), Rotation())
        rpy = RotationY(v=ty, degrees=True)
        self.assertFalse(rpy.is_identity)
        self.assertNotEqual(rpy.rotation(), Rotation())
        rpz = RotationZ(v=tz, degrees=True)
        self.assertFalse(rpz.is_identity)
        self.assertNotEqual(rpz.rotation(), Rotation())

    def test_Vector(self):
        from mccode_antlr.instr.orientation import Vector
        from mccode_antlr.common import Expr
        tx = Vector(Expr.float(1), Expr.float(0), Expr.float(0))
        ty = Vector(Expr.float(0), Expr.float(1), Expr.float(0))
        tz = Vector(Expr.float(0), Expr.float(0), Expr.float(1))

        cxy = tx * ty.cross_matrix()
        self.assertEqual(cxy, tz)
        czx = tz * tx.cross_matrix()
        self.assertEqual(czx, ty)
        cyz = ty * tz.cross_matrix()
        self.assertEqual(cyz, tx)

    def test_TranslationPart(self):
        from mccode_antlr.instr.orientation import TranslationPart, Vector
        t = _random_vector(0.1, 1.0)
        tp = TranslationPart(v=t)
        self.assertTrue(tp.is_translation)
        self.assertFalse(tp.is_rotation)
        self.assertFalse(tp.is_identity)
        self.assertEqual(tp.position(), t)
        self.assertTrue((tp * tp.inverse()).is_identity)

    def test_OrientationParts(self):
        from mccode_antlr.common import Expr
        from mccode_antlr.instr.orientation import TranslationPart, Vector
        from mccode_antlr.instr.orientation import RotationX, RotationY, RotationZ
        from mccode_antlr.instr.orientation import Parts

        tx = TranslationPart(v=Vector(Expr.float(0.1), Expr.float(0), Expr.float(0)))
        ty = TranslationPart(v=Vector(Expr.float(0.), Expr.float(0.2), Expr.float(0)))
        tz = TranslationPart(v=Vector(Expr.float(0.), Expr.float(0), Expr.float(0.3)))

        op = Parts((tx, ty, tz)).reduce()
        self.assertEqual(len(op.stack()), 1)
        t = op.stack()[0]
        self.assertEqual(t, TranslationPart(v=Vector(Expr.float(0.1), Expr.float(0.2), Expr.float(0.3))))

        rx = RotationX(v=Expr.float(30), degrees=True)
        ry = RotationY(v=Expr.float(45), degrees=True)
        rz = RotationZ(v=Expr.float(60), degrees=True)

        rx2 = Parts((rx, rx)).reduce()
        self.assertEqual(len(rx2.stack()), 1)
        rx2 = rx2.stack()[0]
        rx60 = RotationX(v=Expr.float(60), degrees=True)
        for a, b in zip(rx2.seitz(), rx60.seitz()):
            self.assertAlmostEqual(a, b)

        for a, b in zip((Parts((rx,)) + Parts((rx,))).reduce().stack()[0].seitz(), rx2.seitz()):
            self.assertEqual(a, b)

        ry2 = Parts((ry, ry)).reduce()
        self.assertEqual(len(ry2.stack()), 1)
        ry2 = ry2.stack()[0]
        ry90 = RotationY(v=Expr.float(90), degrees=True)
        for a, b in zip(ry2.seitz(), ry90.seitz()):
            self.assertAlmostEqual(a, b)

        rz2 = Parts((rz, rz)).reduce()
        self.assertEqual(len(rz2.stack()), 1)
        rz2 = rz2.stack()[0]
        rz120 = RotationZ(v=Expr.float(120), degrees=True)
        for a, b in zip(rz2.seitz(), rz120.seitz()):
            self.assertAlmostEqual(a, b)

        rxy = Parts((rx, ry)).reduce().stack()[0]
        ryx = Parts((ry, rx)).reduce().stack()[0]
        for j in ('xx', 'yy', 'zz'):
            self.assertAlmostEqual(getattr(rxy.seitz(), j), getattr(ryx.seitz(), j))
        for i, j in [('xy', 'yx')]:
            self.assertAlmostEqual(getattr(rxy.seitz(), i), getattr(ryx.seitz(), j))
        for i, j in [('xz', 'zx'), ('yz', 'zy')]:
            self.assertAlmostEqual(getattr(rxy.seitz(), i), -getattr(ryx.seitz(), j))

        trx = Parts((t, rx)).reduce().stack()[0]
        rxt = Parts((rx, t)).reduce().stack()[0]
        for j in ('xx', 'yy', 'zz', 'xy', 'yx', 'xz', 'zx', 'yz', 'zy', 'xt'):
            self.assertAlmostEqual(getattr(trx.seitz(), j), getattr(rxt.seitz(), j))
        for j in ('yt', 'zt'):
            self.assertNotAlmostEqual(getattr(trx.seitz(), j), getattr(rxt.seitz(), j))

        trz = Parts((t, rz)).reduce().stack()[0]
        rzt = Parts((rz, t)).reduce().stack()[0]
        for j in ('xx', 'yy', 'zz', 'xy', 'yx', 'xz', 'zx', 'yz', 'zy', 'zt'):
            self.assertAlmostEqual(getattr(trz.seitz(), j), getattr(rzt.seitz(), j))
        for j in ('xt', 'yt'):
            self.assertNotAlmostEqual(getattr(trz.seitz(), j), getattr(rzt.seitz(), j))

        trz2 = Parts() + t + rz
        self.assertTrue(isinstance(trz2, Parts))
        self.assertEqual(len(trz2.stack()), 2)
        trz2 = trz2.reduce().stack()[0]
        self.assertEqual(trz2, trz)

    def test_OrientationParts_from_at_rotated(self):
        from mccode_antlr.instr.orientation import Parts, Seitz, RotationX, RotationY, RotationZ, TranslationPart, Angles
        from mccode_antlr.common import Expr
        from itertools import zip_longest
        tx, ty, tz = _random_angles_degrees()
        rx, ry, rz = _make_seitz_list(tx, ty, tz, degrees=True)
        t = _random_vector(0.1, 1.0)
        op = Parts.from_at_rotated(t, Angles(tx, ty, tz), degrees=True)
        self.assertEqual(len(op.stack()), 4)
        self.assertEqual(op.stack()[0], RotationX(v=Expr.float(tx), degrees=True))
        self.assertEqual(op.stack()[1], RotationY(v=Expr.float(ty), degrees=True))
        self.assertEqual(op.stack()[2], RotationZ(v=Expr.float(tz), degrees=True))
        self.assertEqual(op.stack()[3], TranslationPart(v=t))

        inv_op = op.inverse()
        self.assertEqual(len(inv_op.stack()), 4)
        self.assertEqual(inv_op.stack()[1], RotationZ(v=Expr.float(-tz), degrees=True))
        self.assertEqual(inv_op.stack()[2], RotationY(v=Expr.float(-ty), degrees=True))
        self.assertEqual(inv_op.stack()[3], RotationX(v=Expr.float(-tx), degrees=True))

        full = (op + inv_op).reduce()
        resolved = (op + inv_op).resolve()
        self.assertEqual(len(full.stack()), 1)
        full = full.stack()[0]
        self.assertEqual(full, resolved)
        full = full.seitz()
        identity = Seitz()
        for i, j in zip_longest(iter(full), iter(identity)):
            self.assertAlmostEqual(i, j)

    def test_DependentOrientation_no_rotations(self):
        from mccode_antlr.common import Expr
        from mccode_antlr.instr.orientation import TranslationPart, Vector, Angles
        from mccode_antlr.instr.orientation import Parts, Orient

        v123 = Vector(Expr.float(0.1), Expr.float(0.2), Expr.float(0.3))
        v321 = Vector(Expr.float(0.3), Expr.float(0.2), Expr.float(0.1))
        t123 = TranslationPart(v=v123)
        t321 = TranslationPart(v=v321)

        a000 = Angles(Expr.float(0), Expr.float(0), Expr.float(0))

        dop = Orient.from_dependent_orientation(None, v123, a000)
        self.assertEqual(dop.position(), v123)

        d2 = Orient.from_dependent_orientation(dop, v321, a000)
        t444 = Parts((t123, t321)).reduce().stack()[0]
        self.assertEqual(d2.position(), t444.position())
        self.assertEqual(d2.angles(), a000)

    # def test_DependentOrientation_with_rotations(self):
    #     from mccode_antlr.common import Expr
    #     from mccode_antlr.instr.orientation import TranslationPart, Vector, Angles
    #     from mccode_antlr.instr.orientation import RotationX, RotationY, RotationZ
    #     from mccode_antlr.instr.orientation import OrientParts, Orient
    #
    #     tx, ty, tz = _random_angles_degrees()
    #     f = Expr.float
    #
    #     for a in (Angles(tx, f(0), f(0)), Angles(f(0), ty, f(0)), Angles(f(0), f(0), tz)):
    #         v = _random_vector(0.1, 1.0)
    #         dop = Orient.from_dependent_orientation(None, v, a)
    #         self.assertEqual(dop.position(), v)
    #         self.assertEqual(dop.angles(), a)
    #         print(dop)
    #
    #     # Rotate 90 degrees around z axis
    #     z90 = Angles(f(0), f(0), f(90))
    #     # Then rotate 90 degrees around x axis
    #     x90 = Angles(f(90), f(0), f(0))
    #     # This permutes the axes x'=y, y'=z, z'=x
    #     xyz = Orient()
    #     inter = Orient.from_dependent_orientation(xyz, Vector(f(0), f(0), f(0)), z90)
    #     yzx = Orient.from_dependent_orientation(inter, Vector(f(0), f(0), f(0)), x90)
    #
    #     self.assertEqual(yzx._position.resolve().seitz(), yzx._rotation.resolve().seitz())
    #
    #     self.assertNotEqual(yzx.angles(), Angles(f(90), f(0), f(90)))
    #     self.assertEqual(yzx.angles(), Angles(f(180), f(90), f(-90)))
    #
    #
    #     #
    #     # d2 = DependentOrientation.from_dependent_orientation(dop, v321, a000)
    #     # t444 = OrientationParts((t123, t321)).reduce().stack()[0]
    #     # self.assertEqual(d2.position(), t444.position())
    #     # self.assertEqual(d2.angles(), a000)

    def test_DependentOrientation_simple(self):
        from mccode_antlr.common import Expr
        from mccode_antlr.instr.orientation import Vector, Angles, Orient

        v_z1 = Vector(Expr.float(0), Expr.float(0), Expr.float(1))
        v_x1 = Vector(Expr.float(1), Expr.float(0), Expr.float(0))
        v_y1 = Vector(Expr.float(0), Expr.float(1), Expr.float(0))
        v_0 = Vector(Expr.float(0), Expr.float(0), Expr.float(0))
        a_z90 = Angles(Expr.float(0), Expr.float(0), Expr.float(90))
        a_0 = Angles(Expr.float(0), Expr.float(0), Expr.float(0))

        origin = Orient()
        one = Orient.from_dependent_orientation(origin, v_0, a_z90)
        two = Orient.from_dependent_orientation(one, v_z1, a_z90)
        three = Orient.from_dependent_orientation(two, v_z1, a_0)
        four = Orient.from_dependent_orientation(three, v_x1, a_0)

        self.assertEqual(origin.position(), v_0)
        self.assertEqual(origin.angles(), a_0)
        self.assertEqual(one.position(), v_0)
        self.assertEqual(one.angles(), a_z90)
        self.assertEqual(two.position(), v_z1)
        self.assertEqual(two.angles(), a_z90 * Expr.float(2))
        self.assertEqual(three.position(), v_z1 + v_z1)
        self.assertEqual(four.position(), three.position() - v_x1)

    def test_DepedentOrientation_triple_axis(self):
        from math import sin, cos
        from mccode_antlr.common import Expr, unary_expr
        from mccode_antlr.instr.orientation import Vector, Angles, Orient, Rotation, Parts, RotationY

        def ri(i):
            return Angles(Expr.float(0), Expr.id(f'a{i}'), Expr.float(0))

        r1, r2, r3, r4, r5, r6 = [ri(i) for i in range(1, 7)]
        v1 = Vector(Expr.float(0), Expr.float(0), Expr.float(1))
        a0 = Angles(Expr.float(0), Expr.float(0), Expr.float(0))
        v0 = Vector(Expr.float(0), Expr.float(0), Expr.float(0))

        origin = Orient()
        monochromator = Orient.from_dependent_orientation(origin, v1, r1)
        mono_arm = Orient.from_dependent_orientations(monochromator, v0, origin, r2)
        sample = Orient.from_dependent_orientation(mono_arm, v1, r3)
        sample_arm = Orient.from_dependent_orientations(sample, v0, mono_arm, r4)
        analyzer = Orient.from_dependent_orientation(sample_arm, v1, r5)
        ana_arm = Orient.from_dependent_orientations(analyzer, v0, sample_arm, r6)
        detector = Orient.from_dependent_orientation(ana_arm, v1, a0)

        self.assertEqual(origin.position(), v0)
        self.assertEqual(origin.angles(), a0)
        self.assertEqual(monochromator.position(), v1)
        self.assertEqual(monochromator.angles(), r1)
        self.assertEqual(mono_arm.position(), v1)
        self.assertEqual(mono_arm.angles(), r2)
        #self.assertEqual(sample.position(), v1 +v1)

        ai = [Expr.id(f'a{i}') for i in range(7)]
        sa = [unary_expr(sin, 'sin', a) for a in ai]
        ca = [unary_expr(cos, 'cos', a) for a in ai]
        sample_position = Vector(sa[2], Expr.float(0.0), Expr.float(1) + ca[2])
        sample_analyzer_vector = Vector(ca[2] * sa[4] + sa[2] * ca[4], Expr.float(0), - sa[2] * sa[4] + ca[4] * ca[2])

        self.assertEqual(sample.position(), sample_position)
        # Matching up expression trees is hard -- so use this special hand-checked equivalent matrix
        er = Rotation(ca[3] * ca[2] + -sa[3] * sa[2], Expr.float(0), ca[3] * -sa[2] + -sa[3] * ca[2],
                      Expr.float(0), Expr.float(1), Expr.float(0),
                      sa[3] * ca[2] + ca[3] * sa[2], Expr.float(0), sa[3] * -sa[2] + ca[3] * ca[2])
        self.assertEqual(sample.rotation(), er)

        self.assertEqual(sample_arm.position(), sample_position)
        er = Rotation(ca[4] * ca[2] + -sa[4] * sa[2], Expr.float(0), ca[4] * -sa[2] + -sa[4] * ca[2],
                      Expr.float(0), Expr.float(1), Expr.float(0),
                      sa[4] * ca[2] + ca[4] * sa[2], Expr.float(0), sa[4] * -sa[2] + ca[4] * ca[2])
        self.assertEqual(sample_arm.rotation(), er)

        self.assertEqual(analyzer.position(), sample_position + sample_analyzer_vector)

        self.assertEqual(analyzer.rotation_parts(),
                         Parts((RotationY(v=ai[2]), RotationY(v=ai[4]), RotationY(v=ai[5]))))

        self.assertEqual(ana_arm.rotation_parts(),
                         Parts((RotationY(v=ai[2]), RotationY(v=ai[4]), RotationY(v=ai[6]))))

        # testing the detector position is more of the same, but more complicated, than the analyzer position
        # Since it doesn't test much, skip it for the moment
        self.assertEqual(ana_arm.rotation(), detector.rotation())

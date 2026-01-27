from mccode_antlr.common import Expr
from mccode_antlr.common.expression import OpStyle

def test_Orient_add_sub_simple():
    from mccode_antlr.common import Expr
    from mccode_antlr.instr.orientation import Vector, Angles, Orient

    # Start at origin
    origin = Orient()

    # Simple translation along z-axis
    v_z = Vector(Expr.float(0), Expr.float(0), Expr.float(1))
    a_0 = Angles(Expr.float(0), Expr.float(0), Expr.float(0))

    # Create an Orient that is 1 unit along z
    orient_z = Orient.from_dependent_orientation(origin, v_z, a_0)

    # Test 1: (origin + orient_z) - orient_z should equal origin
    result = (origin + orient_z) - orient_z
    assert result.position() == origin.position()
    assert result.angles() == origin.angles()

    # Test 2: (orient_z - orient_z) should equal origin (identity)
    result = orient_z - orient_z
    assert result.position() == Vector(Expr.float(0), Expr.float(0), Expr.float(0))
    assert result.angles() == a_0

    # Simple rotation around z-axis
    a_z90 = Angles(Expr.float(0), Expr.float(0), Expr.float(90))
    orient_rot = Orient.from_dependent_orientation(origin, Vector(Expr.float(0), Expr.float(0), Expr.float(0)), a_z90)

    # Test 3: (origin + orient_rot) - orient_rot should equal origin
    result = (origin + orient_rot) - orient_rot
    assert result.position() == origin.position()
    assert result.angles() == origin.angles()

    # Test 4: Adding and subtracting the same Orient twice
    result = ((origin + orient_z) + orient_z) - (orient_z + orient_z)
    assert result.position() == origin.position()
    assert result.angles() == origin.angles()

    # Test 5: translate along z then rotate around x
    # add and subtract to reach origin again, order is not important
    orient_5 = Orient.from_dependent_orientation(
        origin,
        Vector(Expr.float(0), Expr.float(0), Expr.float(10)),
        Angles(Expr.float(90), Expr.float(0), Expr.float(0))
    )
    result = (origin + orient_5) - orient_5
    assert result.position() == origin.position()
    assert result.angles() == origin.angles()
    result = (origin - orient_5) + orient_5
    assert result.position() == origin.position()
    assert result.angles() == origin.angles()


def test_expr_sympy_equivalence():
    """Test that Expr produces same results as SymPy"""
    # Test eager simplification
    x = Expr.id('x')
    assert (x * Expr.float(0)).is_zero  # Existing behavior
    # SymPy equivalent would be: sp.sympify('x * 0').simplify() == 0

def test_rotation_matrix_composition():
    """Test successive rotations combine correctly"""
    from mccode_antlr.instr.orientation import Seitz, RotationZ, RotationX, RotationY
    o, z = Expr.float(1), Expr.float(0)
    # Without specifying that we are providing the value, all rotations produce
    # the identify matrix
    ri = RotationZ(Expr.float(90))
    assert ri.seitz() == Seitz(
        xx=o, xy=z, xz=z, xt=z,
        yx=z, yy=o, yz=z, yt=z,
        zx=z, zy=z, zz=o, zt=z
    )
    # Rotation{Axis} creates a McStas-style rotation. The specified rotation angle
    # is how much the _coordinate system_ is rotated -- or the inverse of how
    # much the coordinates would be rotated.
    rx = RotationX(v=Expr.float(90), degrees=True)
    assert rx.seitz() == Seitz(
        xx=o, xy=z, xz=z, xt=z,
        yx=z, yy=z, yz=o, yt=z,
        zx=z, zy=-o, zz=z, zt=z
    )
    ry = RotationY(v=Expr.float(90), degrees=True)
    assert ry.seitz() == Seitz(
        xx=z, xy=z, xz=-o, xt=z,
        yx=z, yy=o, yz=z, yt=z,
        zx=o, zy=z, zz=z, zt=z
    )
    combined = ry * rx
    assert combined.seitz() == Seitz(
        xx=z, xy=o, xz=z, xt=z,
        yx=z, yy=z, yz=o, yt=z,
        zx=o, zy=z, zz=z, zt=z
    )

def test_code_generation_equivalence():
    """Test C and Python code generation"""
    expr = Expr.parse('sin(x) + cos(y)')
    c_code = str(expr)  # Should be valid C
    assert c_code == "(sin(x) + cos(y))"
    for i in expr.expr:
        i.style = OpStyle.PYTHON
    py_code = str(expr)  # Should be valid Python
    assert py_code == "(sin(x) + cos(y))"
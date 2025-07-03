from mccode_antlr.io.json import to_json, from_json
from mccode_antlr.common.expression import Value, Expr


def assert_round_trip(obj):
    json = to_json(obj)
    ret = from_json(json)
    assert type(ret) is type(obj)
    assert ret == obj
    return ret


def test_simple_instr_json():
    from mccode_antlr.loader import parse_mcstas_instr
    instr = parse_mcstas_instr(
        "define instrument check() trace component a = Arm() at (0,0,0) absolute end")
    msg = to_json(instr)
    reconstituted = from_json(msg)
    assert type(reconstituted) is type(instr)
    assert instr == reconstituted


def assert_scalar_expr_round_trip(value: Value):
    expr = Expr(value)
    ret = assert_round_trip(expr)
    assert len(ret.expr) == 1
    assert ret.expr[0] == value
    assert str(expr) == str(ret)
    assert str(value) == str(ret.expr[0])


def test_str_expr_json_round_trip():
    assert_scalar_expr_round_trip(Value.str('some string'))


def test_int_expr_json_round_trip():
    assert_scalar_expr_round_trip(Value.int(1))


def test_float_expr_json_round_trip():
    assert_scalar_expr_round_trip(Value.float(1))


def test_instrument_parameter_json_round_trip():
    from mccode_antlr.common.parameters import InstrumentParameter
    ip = InstrumentParameter.parse('int x/"m"=1')
    ret = assert_round_trip(ip)
    assert ip.name == ret.name
    assert ip.value == ret.value
    assert str(ip) == str(ret)
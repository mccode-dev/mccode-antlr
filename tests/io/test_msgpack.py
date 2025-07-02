from mccode_antlr.io.msgpack import to_msgpack, from_msgpack

def test_simple_instr_json():
    from mccode_antlr.loader import parse_mcstas_instr
    instr = parse_mcstas_instr(
        "define instrument check() trace component a = Arm() at (0,0,0) absolute end")
    msg = to_msgpack(instr)
    reconstituted = from_msgpack(msg)
    assert type(reconstituted) is type(instr)
    assert instr == reconstituted


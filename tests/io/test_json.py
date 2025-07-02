from mccode_antlr.io.json import to_json, from_json

def test_simple_instr_json():
    from mccode_antlr.loader import parse_mcstas_instr
    instr = parse_mcstas_instr(
        "define instrument check() trace component a = Arm() at (0,0,0) absolute end")
    msg = to_json(instr)
    reconstituted = from_json(msg)
    assert type(reconstituted) is type(instr)
    assert instr == reconstituted


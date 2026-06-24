from pathlib import Path


def test_convert_parser_is_registered():
    from mccode_antlr.cli.management import mccode_management_parser

    parser = mccode_management_parser()
    args = parser.parse_args(['convert', 'in.instr', '--to', 'json'])

    assert hasattr(args, 'action')
    assert args.to == 'json'
    assert args.filename == 'in.instr'


def test_convert_instr_to_json(tmp_path):
    from mccode_antlr.loader import parse_mcstas_instr
    from mccode_antlr.cli.convert import convert
    from mccode_antlr.io.json import load_json
    from mccode_antlr.instr import Instr

    instr = parse_mcstas_instr(
        "define instrument check() trace component a = Arm() at (0,0,0) absolute end"
    )
    source = tmp_path / 'source.instr'
    with source.open('w') as f:
        instr.to_file(output=f)

    destination = tmp_path / 'converted.json'
    convert(filename=str(source), output=str(destination), to='json')

    converted = load_json(destination)
    assert isinstance(converted, Instr)
    assert converted.name == instr.name
    assert [c.name for c in converted.components] == [c.name for c in instr.components]


def test_convert_json_to_instr(tmp_path):
    from mccode_antlr.loader import parse_mcstas_instr
    from mccode_antlr.cli.convert import convert
    from mccode_antlr.io.json import save_json

    instr = parse_mcstas_instr(
        "define instrument check() trace component a = Arm() at (0,0,0) absolute end"
    )
    source = tmp_path / 'source.json'
    save_json(instr, source)

    destination = tmp_path / 'converted.instr'
    convert(filename=str(source), output=str(destination), to='instr')

    text = destination.read_text()
    assert 'DEFINE INSTRUMENT check' in text
    assert 'COMPONENT a = Arm' in text

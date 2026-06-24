import ast
import pytest


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


def test_convert_instr_to_python(tmp_path):
    from mccode_antlr.loader import parse_mcstas_instr
    from mccode_antlr.cli.convert import convert

    instr = parse_mcstas_instr(
        "define instrument check() trace component a = Arm() at (0,0,0) absolute end"
    )
    source = tmp_path / 'source.instr'
    with source.open('w') as f:
        instr.to_file(output=f)

    destination = tmp_path / 'converted.py'
    convert(filename=str(source), output=str(destination), to='python')

    text = destination.read_text()
    assert 'def build_instrument()' in text
    assert "a.component(name='a', type_name='Arm'" in text
    ast.parse(text)


def test_generated_python_builds_instr_object(tmp_path):
    from mccode_antlr.loader import parse_mcstas_instr
    from mccode_antlr.cli.convert import convert
    from mccode_antlr.instr import Instr

    instr = parse_mcstas_instr(
        "define instrument check() trace component a = Arm() at (0,0,0) absolute end"
    )
    source = tmp_path / 'source.instr'
    with source.open('w') as f:
        instr.to_file(output=f)

    destination = tmp_path / 'converted.py'
    convert(filename=str(source), output=str(destination), to='python')

    namespace = {}
    exec(destination.read_text(), namespace)
    rebuilt = namespace['build_instrument']()

    assert isinstance(rebuilt, Instr)
    assert rebuilt.name == instr.name
    assert [c.name for c in rebuilt.components] == [c.name for c in instr.components]


def test_convert_instr_to_python_optimized_uses_loop(tmp_path):
    from mccode_antlr.loader import parse_mcstas_instr
    from mccode_antlr.cli.convert import convert

    instr = parse_mcstas_instr(
        """
        define instrument check()
        trace
        component origin = Arm() at (0,0,0) absolute
        component guide1 = Arm() at (0,0,1) relative origin
        component guide2 = Arm() at (0,0,2) relative origin
        component guide3 = Arm() at (0,0,3) relative origin
        end
        """
    )
    source = tmp_path / 'source.instr'
    with source.open('w') as f:
        instr.to_file(output=f)

    destination = tmp_path / 'optimized.py'
    convert(filename=str(source), output=str(destination), to='python', optimize=True)

    text = destination.read_text()
    assert 'for i in range(3):' in text
    assert 'name=f"guide{i + 1}"' in text
    ast.parse(text)


def test_generated_optimized_python_preserves_component_names(tmp_path):
    from mccode_antlr.loader import parse_mcstas_instr
    from mccode_antlr.cli.convert import convert

    instr = parse_mcstas_instr(
        """
        define instrument check()
        trace
        component origin = Arm() at (0,0,0) absolute
        component guide1 = Arm() at (0,0,1) relative origin
        component guide2 = Arm() at (0,0,2) relative origin
        component guide3 = Arm() at (0,0,3) relative origin
        end
        """
    )
    source = tmp_path / 'source.instr'
    with source.open('w') as f:
        instr.to_file(output=f)

    destination = tmp_path / 'optimized.py'
    convert(filename=str(source), output=str(destination), to='python', optimize=True)

    namespace = {}
    exec(destination.read_text(), namespace)
    rebuilt = namespace['build_instrument']()
    assert [c.name for c in rebuilt.components] == [c.name for c in instr.components]


def test_optimize_rejected_for_non_python_target(tmp_path):
    from mccode_antlr.loader import parse_mcstas_instr
    from mccode_antlr.cli.convert import convert

    instr = parse_mcstas_instr(
        "define instrument check() trace component a = Arm() at (0,0,0) absolute end"
    )
    source = tmp_path / 'source.instr'
    with source.open('w') as f:
        instr.to_file(output=f)

    with pytest.raises(ValueError, match='--optimize is only supported when --to python'):
        convert(filename=str(source), output=str(tmp_path / 'out.json'), to='json', optimize=True)

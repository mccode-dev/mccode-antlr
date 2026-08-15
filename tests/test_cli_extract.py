def test_extract_parser_is_registered():
    from mccode_antlr.cli.management import mccode_management_parser

    parser = mccode_management_parser()
    args = parser.parse_args(['extract', 'in.json', '--include-remote'])

    assert hasattr(args, 'action')
    assert args.filename == 'in.json'
    assert args.include_remote is True


def test_extract_default_output_directory(tmp_path):
    from mccode_antlr.loader import parse_mcstas_instr
    from mccode_antlr.cli.extract import extract
    from mccode_antlr.io.json import save_json

    instr = parse_mcstas_instr(
        "define instrument check() trace component a = Arm() at (0,0,0) absolute end"
    )
    source = tmp_path / 'source.json'
    save_json(instr, source)

    extract(filename=str(source))

    destination = tmp_path / 'source.extracted'
    assert destination.is_dir()
    assert (destination / 'check.instr').exists()


def test_extract_honours_explicit_output(tmp_path):
    from mccode_antlr.loader import parse_mcstas_instr
    from mccode_antlr.cli.extract import extract
    from mccode_antlr.io.json import save_json

    instr = parse_mcstas_instr(
        "define instrument check() trace component a = Arm() at (0,0,0) absolute end"
    )
    source = tmp_path / 'source.json'
    save_json(instr, source)

    destination = tmp_path / 'bundle'
    extract(filename=str(source), output=str(destination))

    assert (destination / 'check.instr').exists()

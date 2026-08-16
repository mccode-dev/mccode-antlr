def test_extract_parser_is_registered():
    from mccode_antlr.cli.management import mccode_management_parser

    parser = mccode_management_parser()
    args = parser.parse_args(['extract', 'in.json', '--include-remote'])

    assert hasattr(args, 'action')
    assert args.filename == 'in.json'
    assert args.include_remote is True
    assert args.members == []
    assert args.exclude is None
    assert args.list_only is False


def test_extract_parser_members_exclude_list():
    from mccode_antlr.cli.management import mccode_management_parser

    parser = mccode_management_parser()
    args = parser.parse_args(['extract', 'in.json', 'a.comp', 'b.h', '-x', 'c.h', '-l'])

    assert args.filename == 'in.json'
    assert args.members == ['a.comp', 'b.h']
    assert args.exclude == ['c.h']
    assert args.list_only is True


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


def test_extract_list_only_writes_nothing(tmp_path, capsys):
    from mccode_antlr.loader import parse_mcstas_instr
    from mccode_antlr.cli.extract import extract
    from mccode_antlr.io.json import save_json

    instr = parse_mcstas_instr(
        "define instrument check() trace component a = Arm() at (0,0,0) absolute end"
    )
    source = tmp_path / 'source.json'
    save_json(instr, source)

    extract(filename=str(source), list_only=True)

    destination = tmp_path / 'source.extracted'
    assert not destination.exists()
    out = capsys.readouterr().out
    assert 'check.instr' in out


def test_extract_select_writes_only_named_member(tmp_path):
    from mccode_antlr.loader import parse_mcstas_instr
    from mccode_antlr.cli.extract import extract
    from mccode_antlr.io.json import save_json

    instr = parse_mcstas_instr(
        "define instrument check() trace component a = Arm() at (0,0,0) absolute end"
    )
    source = tmp_path / 'source.json'
    save_json(instr, source)

    extract(filename=str(source), members=['check.instr'])

    destination = tmp_path / 'source.extracted'
    assert {p.name for p in destination.iterdir()} == {'check.instr'}


def test_extract_list_only_matches_real_extraction(tmp_path, capsys):
    """--list is a true dry-run: it previews exactly the members a real
    (non-list) invocation with the same selection would write."""
    from mccode_antlr.loader import parse_mcstas_instr
    from mccode_antlr.cli.extract import extract
    from mccode_antlr.io.json import save_json

    instr = parse_mcstas_instr(
        "define instrument check() trace component a = Arm() at (0,0,0) absolute end"
    )
    source = tmp_path / 'source.json'
    save_json(instr, source)

    extract(filename=str(source), list_only=True, members=['Arm.comp'])
    listed_names = {
        line.split()[1] for line in capsys.readouterr().out.splitlines() if line.strip()
    }

    destination = tmp_path / 'bundle'
    extract(filename=str(source), members=['Arm.comp'], output=str(destination))
    written_names = {p.name for p in destination.iterdir()}

    assert listed_names == written_names == {'Arm.comp'}

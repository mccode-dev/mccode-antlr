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
    assert args.repository is None


def test_extract_parser_repository_is_repeatable():
    from mccode_antlr.cli.management import mccode_management_parser

    parser = mccode_management_parser()
    args = parser.parse_args(['extract', 'in.json', '-r', '*/mcdotstar/*', '-r', '*/other-org/*'])

    assert args.repository == ['*/mcdotstar/*', '*/other-org/*']


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
    (non-list) invocation with the same selection would write.

    Dry-run parity is asserted against build_manifest/select_members directly
    (the shared resolution path both extract()'s list and write branches call)
    rather than by parsing the -l/--list console output -- that output is a
    rich Table (with a header row and column-aligned, potentially colorized
    cells), so it's presentation, not a stable line-format contract.
    """
    from mccode_antlr.loader import parse_mcstas_instr
    from mccode_antlr.cli._common import load_instr
    from mccode_antlr.cli.extract import extract
    from mccode_antlr.io.extract import build_manifest, select_members
    from mccode_antlr.io.json import save_json

    instr = parse_mcstas_instr(
        "define instrument check() trace component a = Arm() at (0,0,0) absolute end"
    )
    source = tmp_path / 'source.json'
    save_json(instr, source)

    loaded = load_instr(source, 'mcstas', None)
    manifest = build_manifest(loaded, include_remote=False)
    listed_names = {m.name for m in select_members(manifest, ['Arm.comp'], None)}

    destination = tmp_path / 'bundle'
    extract(filename=str(source), members=['Arm.comp'], output=str(destination))
    written_names = {p.name for p in destination.iterdir()}

    assert listed_names == written_names == {'Arm.comp'}

    extract(filename=str(source), list_only=True, members=['Arm.comp'])
    assert 'Arm.comp' in capsys.readouterr().out


def test_extract_list_output_includes_repository_column(tmp_path, capsys, monkeypatch):
    from mccode_antlr.loader import parse_mcstas_instr
    from mccode_antlr.cli.extract import extract
    from mccode_antlr.io.json import save_json

    monkeypatch.setenv('NO_COLOR', '1')
    instr = parse_mcstas_instr(
        "define instrument check() trace component a = Arm() at (0,0,0) absolute end"
    )
    source = tmp_path / 'source.json'
    save_json(instr, source)

    extract(filename=str(source), list_only=True)

    out = capsys.readouterr().out
    assert 'REPOSITORY' in out
    assert 'LOCATION' in out
    assert 'generated' in out
    assert '\x1b[' not in out


def test_extract_repository_filter_selects_only_matching_files(tmp_path):
    from mccode_antlr.cli.extract import extract

    lib = tmp_path / 'lib'
    lib.mkdir()
    (lib / 'UsesLib.comp').write_text(
        'DEFINE COMPONENT UsesLib\nSETTING PARAMETERS (thing=1)\nTRACE %{ SCATTER; %}\nEND\n'
    )
    instr_path = tmp_path / 'u.instr'
    instr_path.write_text(
        'DEFINE INSTRUMENT u()\nTRACE\n'
        'COMPONENT o = Progress_bar() AT (0,0,0) ABSOLUTE\n'
        'COMPONENT m = UsesLib(thing=3) AT (0,0,1) ABSOLUTE\nEND\n'
    )

    destination = tmp_path / 'bundle'
    extract(
        filename=str(instr_path), output=str(destination), search_dir=[lib],
        repository=['*/mccode-dev/*'],
    )

    assert {p.name for p in destination.iterdir()} == {'Progress_bar.comp'}


def test_trust_local_registries_does_not_duplicate_embedded_listing(tmp_path, capsys, monkeypatch):
    """--trust-local-registries can make a file both embedded (from the JSON)
    and locally resolvable (from the restored registry) -- it must be listed
    once, attributed to the live local registry, not twice."""
    from mccode_antlr import Flavor
    from mccode_antlr.reader import Reader
    from mccode_antlr.reader.registry import collect_local_registries
    from mccode_antlr.config import config
    from mccode_antlr.cli.extract import extract
    from mccode_antlr.io.json import save_json

    monkeypatch.setenv('NO_COLOR', '1')
    lib = tmp_path / 'lib'
    lib.mkdir()
    (lib / 'mylib.h').write_text('/* MYLIB SENTINEL */\ndouble mylib_helper(double x);\n')
    (lib / 'UsesLib.comp').write_text(
        'DEFINE COMPONENT UsesLib\nSETTING PARAMETERS (thing=1)\n'
        'SHARE %{ %include "mylib" %}\nTRACE %{ SCATTER; %}\nEND\n'
    )
    instr_path = tmp_path / 'u.instr'
    instr_path.write_text(
        'DEFINE INSTRUMENT u()\nTRACE\n'
        'COMPONENT o = Progress_bar() AT (0,0,0) ABSOLUTE\n'
        'COMPONENT m = UsesLib(thing=3) AT (0,0,1) ABSOLUTE\nEND\n'
    )
    reader = Reader(registries=collect_local_registries(Flavor.MCSTAS, [lib]))
    loaded = reader.get_instrument(instr_path)
    source = tmp_path / 'source.json'
    save_json(loaded, source)

    try:
        extract(filename=str(source), list_only=True, trust_local_registries=True)
    finally:
        config['serialization']['trust_local_registries'] = False

    lines = [line for line in capsys.readouterr().out.splitlines() if 'mylib.h' in line]
    assert len(lines) == 1
    assert 'local' in lines[0]
    assert 'embedded' not in lines[0]

from textwrap import dedent
from mccode_antlr.loader import parse_mcstas_instr
from mccode_antlr.test import compiled_test
from mccode_antlr.utils import compile_and_run

@compiled_test
def test_when_logical_parses():
    instr = parse_mcstas_instr(dedent("""DEFINE INSTRUMENT when_logical(int should_eye=0)
    DECLARE %{int copied;%}
    INITIALIZE %{copied = should_eye;%}
    TRACE
    COMPONENT only = Arm() WHEN(should_eye) at (0, 0, 0) ABSOLUTE
    EXTEND %{
    printf("should_eye=%d\\n", _instrument_var._parameters.should_eye);
    %}
    COMPONENT acopy = Arm() WHEN(copied) at (0, 0, 1) ABSOLUTE
    EXTEND %{
    printf("copied=%d\\n", copied);
    %} 
    END
    """))
    for should_eye in (0, 1):
        results, data = compile_and_run(instr, f'-n 1 {should_eye=}')
        lines = results.decode('utf-8').splitlines()
        expected = [f'{should_eye=}', f'copied={should_eye}'] if should_eye else []
        assert len(expected) + 1 == len(lines)  # [*expected, '*** TRACE end *** ']
        for ex, ln in zip(expected, lines):
            assert ex == ln


def do_when_op_(checker, op, message):
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from mccode_antlr import Flavor
    from mccode_antlr.run import mccode_compile, mccode_run_compiled
    from itertools import product

    kwargs = dict(target=None, config=None, dump_source=False)

    instr = parse_mcstas_instr(
        dedent(f"""DEFINE INSTRUMENT when_equal(int value=0, int check=-1)
        initialize %{{
        printf("value=%d check=%d\\n", value, check);
        %}}
        TRACE
        COMPONENT only = Arm() WHEN(value {op} check) at (0, 0, 0) ABSOLUTE
        EXTEND %{{
        printf("{message}\\n");
        %}}
        END
        """)
    )
    with TemporaryDirectory() as directory:
        binary, target = mccode_compile(instr, directory, Flavor.MCSTAS, **kwargs)
        for index, (value, check) in enumerate(product((0, 1, 2, 3), (1, 2, 3, 4))):
            path = Path(directory).joinpath(f't{index}')
            result, data = mccode_run_compiled(binary, target, path, f'-n 1 {value=} {check=}')
            lines = result.decode('utf-8').splitlines()
            # print(f'{value=} {check=} {op=} {lines=}')
            expected = [f'{value=} {check=}'] + ([message] if checker(value, check) else [])
            assert len(expected) + 1 == len(lines)  # [*expected, '*** TRACE end *** ']
            for ex, ln in zip(expected, lines):
                assert ex == ln


def test_when_equal_parses():
    do_when_op_(lambda x, y: x == y, '==', 'equal')


def test_when_not_equal_parses():
    do_when_op_(lambda x, y: x != y, '!=', 'unequal')


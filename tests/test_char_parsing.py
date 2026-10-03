"""
mcstas/mcxtrace prior to 2026-10-03 did not parse char literals correctly

no example .instr files use char literals in expressions but, since they are valid C,
they should be supported.

mccode-antlr does not parse char literals in expressions correctly.
"""

def test_char_parsing():
    from mccode_antlr.common.expression import Expr
    for i, c in enumerate((r"'a'", r"'\n'", r"'\''", r"'\\'")):
        orig = f'{c}=={i}'
        # orig = "'a'==1"
        a = Expr.parse(orig)
        res = str(a)
        assert res == orig


def test_char_value_follows_c_promotion():
    """A char literal is an int in C, and arithmetic on chars is int arithmetic."""
    from mccode_antlr.common.expression import Expr, DataType
    a = Expr.parse("'a'")
    assert a.data_type == DataType.chr
    assert a.value == 97
    e = Expr.parse("'x'-'a'+'A'")
    assert e.data_type == DataType.int
    assert e.value == ord('X')
    # evaluating must not fold the stored expression: the C keeps its spelling
    assert str(e) == "'A' - 'a' + 'x'"


def test_declared_char_pointers_and_arrays_are_strings():
    """The C parser hands back dtype='char' for all of these; only the scalar is a char."""
    from mccode_antlr.common.expression import DataType
    from mccode_antlr.translators.c_listener import extract_c_declared_expressions
    found = extract_c_declared_expressions('char a; char *p; char s[16]; char t[] = "hi";')
    types = {d.name: e.data_type for d, e in found.items()}
    assert types == {'a': DataType.chr, 'p': DataType.str, 's': DataType.str, 't': DataType.str}


def test_char_type_names():
    from mccode_antlr.common.expression import DataType
    for name in ('char', 'unsigned char', 'signed char'):
        assert DataType.from_name(name) == DataType.chr
    for name in ('char *', 'char*', 'char[16]', 'string'):
        assert DataType.from_name(name) == DataType.str

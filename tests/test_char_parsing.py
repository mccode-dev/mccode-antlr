"""
mcstas/mcxtrace prior to 2026-10-03 did not parse char literals correctly

no example .instr files use char literals in expressions but, since they are valid C,
they should be supported.

mccode-antlr does not parse char literals in expressions correctly.
"""

def test_char_parsing():
    from mccode_antlr.common.expression import Expr
    for i, c in enumerate(("'a'", "'\n'", "'\''", "'\\'")):
        orig = f'{c}=={i}'
        # orig = "'a'==1"
        a = Expr.parse(orig)
        res = str(a)
        assert res == orig

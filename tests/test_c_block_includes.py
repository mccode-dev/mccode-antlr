"""Issue #320: a `%include` inside a C block may carry a trailing comment.

`%include "conic.h"   // spliced right here`
`%include "read_table-lib"  /* pulled in as a library */`

The file form is spliced in place (the comment ends up on the spliced file's
last line); the library form is lifted out and emitted with the other libraries
(the comment stays where the directive was).
"""
from textwrap import dedent

from mccode_antlr.loader import parse_mcstas_instr
from mccode_antlr.reader.registry import InMemoryRegistry
from mccode_antlr.translators.includes import included_names


CONIC_H = "/* CONIC SENTINEL */\ndouble conic_ex = 1;\n"
MYLIB_H = "/* MYLIB HEADER SENTINEL */\nvoid mylib_fn(void);\n"
MYLIB_C = "/* MYLIB SOURCE SENTINEL */\nvoid mylib_fn(void) {}\n"

THING = dedent(r"""DEFINE COMPONENT Thing
    SHARE %{
    %include "mylib"          // pulled in as a library
    %}
    TRACE %{
    SCATTER;
    %}
    END
    """)


def _registry() -> InMemoryRegistry:
    reg = InMemoryRegistry("issue_320")
    reg.add("conic.h", CONIC_H)
    reg.add("mylib.h", MYLIB_H)
    reg.add("mylib.c", MYLIB_C)
    reg.add_comp("Thing", THING)
    return reg


def _translate(declare_body: str) -> str:
    from mccode_antlr import Flavor
    from mccode_antlr.translators.c import CTargetVisitor

    instr = parse_mcstas_instr(dedent(f"""DEFINE INSTRUMENT issue_320_instr()
    DECLARE %{{
    {declare_body}
    %}}
    TRACE
    COMPONENT origin = Thing() AT (0, 0, 0) ABSOLUTE
    END
    """), registries=[_registry()])
    config = dict(
        default_main=True,
        enable_trace=True,
        portable=True,
        include_runtime=True,
        embed_instrument_file=False,
        verbose=False,
        output="issue_320_instr.c",
    )
    visitor = CTargetVisitor(instr, flavor=Flavor.MCSTAS, config=config, verbose=False, debug=False)
    return visitor.contents()


def test_included_names_tolerates_trailing_comment():
    text = dedent("""\
        %include "read_table-lib"   // a library, with a note
        %include "conic.h"  /* a specific file */
        %include "other-lib"
        %include "plain.h"
    """)
    libraries, files = included_names(text)
    assert libraries == ["read_table-lib", "other-lib"]
    assert files == ["conic.h", "plain.h"]
    # the comment text never leaks into a captured name
    assert not any("note" in name or "/" in name for name in libraries + files)


def test_file_include_splices_and_keeps_comment():
    c_program = _translate('%include "conic.h"   // spliced right here')
    assert "CONIC SENTINEL" in c_program
    assert "// spliced right here" in c_program
    # the raw directive must be gone (it is not valid C)
    assert '%include "conic.h"' not in c_program


def test_block_comment_after_file_include():
    c_program = _translate('%include "conic.h"  /* spliced right here */')
    assert "CONIC SENTINEL" in c_program
    assert "/* spliced right here */" in c_program
    assert '%include "conic.h"' not in c_program


def test_library_include_keeps_comment_at_original_location():
    # the library %include lives in Thing's SHARE block (see THING above)
    c_program = _translate("double instr_declared = 0;")
    assert "MYLIB HEADER SENTINEL" in c_program
    assert '%include "mylib"' not in c_program
    assert "// pulled in as a library" in c_program


def test_bare_include_still_translates():
    c_program = _translate('%include "conic.h"')
    assert "CONIC SENTINEL" in c_program
    assert '%include "conic.h"' not in c_program

"""Each SPLIT branch after the first starts a new trace ray, so mcdisplay draws no return line."""

INSTR = """DEFINE INSTRUMENT split_trace(dummy=0)
TRACE
COMPONENT origin = Arm() AT (0, 0, 0) ABSOLUTE
SPLIT 3 COMPONENT copies = Arm() AT (0, 0, 1) RELATIVE origin
END
"""


def test_split_branches_start_new_trace_rays():
    from mccode_antlr import Flavor
    from mccode_antlr.loader import parse_mcstas_instr
    from mccode_antlr.translators.c import CTargetVisitor

    instr = parse_mcstas_instr(INSTR)
    config = dict(default_main=True, enable_trace=True, portable=False,
                  include_runtime=True, embed_instrument_file=False, verbose=False)
    c_program = CTargetVisitor(instr, flavor=Flavor.MCSTAS, config=config).contents()

    new_ray = 'if (SplitN_copies > 0) { DEBUG_LEAVE(); DEBUG_STATE(); DEBUG_ENTER(); DEBUG_STATE(); }'
    restore = '*_particle=Split_copies_particle;'
    assert new_ray in c_program
    assert c_program.index(new_ray) < c_program.index(restore)

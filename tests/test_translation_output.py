"""Translating an instrument prints nothing: progress is logged at DEBUG, problems as warnings."""

INSTR = """DEFINE INSTRUMENT quiet(dummy=0)
USERVARS %{
double * per_particle;
%}
TRACE
COMPONENT origin = Arm() AT (0, 0, 0) ABSOLUTE
COMPONENT lonely = Arm() AT (0, 0, 1) RELATIVE origin GROUP alone
SPLIT 2 COMPONENT copies = Arm() AT (0, 0, 1) RELATIVE lonely
END
"""


def test_translation_prints_nothing_and_logs_warnings(capsys, caplog):
    from mccode_antlr import Flavor
    from mccode_antlr.loader import parse_mcstas_instr
    from mccode_antlr.translators.c import CTargetVisitor

    caplog.set_level('DEBUG', logger='mccode_antlr')
    instr = parse_mcstas_instr(INSTR)
    config = dict(default_main=True, enable_trace=False, portable=False,
                  include_runtime=True, embed_instrument_file=False, verbose=False)
    CTargetVisitor(instr, flavor=Flavor.MCSTAS, config=config).contents()

    assert capsys.readouterr().out == ''
    warnings = [r.getMessage() for r in caplog.records if r.levelname == 'WARNING']
    assert any('GROUP alone' in m for m in warnings), warnings
    assert any('USERVAR per_particle' in m for m in warnings), warnings
    debug = [r.getMessage() for r in caplog.records if r.levelname == 'DEBUG']
    assert any('-> SPLIT' in m for m in debug), debug

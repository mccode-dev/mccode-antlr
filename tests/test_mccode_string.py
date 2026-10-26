"""MCCODE_STRING must carry the McCode version.

The runtime writes it as the NeXus 'simulation/program' attribute and the
'Creator' line of every output file; readers such as McStasToX take the McCode
version from there, the first X.Y.Z in the string, so the McCode version comes
before the mccode-antlr one.
"""
import re
from mccode_antlr.loader import parse_mcstas_instr
from mccode_antlr import version
from mccode_antlr.reader.registry import InMemoryRegistry, mccode_registry_version


def test_mccode_string_has_version():
    from mccode_antlr import Flavor
    from mccode_antlr.translators.c import CTargetVisitor

    reg = InMemoryRegistry("mccode_string")
    reg.add_comp("Thing", "DEFINE COMPONENT Thing\nTRACE %{\n%}\nEND\n")
    instr = parse_mcstas_instr(
        "DEFINE INSTRUMENT v()\nTRACE\nCOMPONENT o = Thing() AT (0, 0, 0) ABSOLUTE\nEND\n", registries=[reg])
    config = dict(default_main=True, enable_trace=False, portable=False, include_runtime=True,
                  embed_instrument_file=False, verbose=False, output="v.c")
    c = CTargetVisitor(instr, flavor=Flavor.MCSTAS, config=config, verbose=False, debug=False).contents()
    string = re.search(r'#define MCCODE_STRING "(.*)"', c).group(1)
    assert string == f"McStas {mccode_registry_version()} (mccode-antlr {version()})"
    assert re.search(r'\d+\.\d+\.\d+', string).group(0) == str(mccode_registry_version())

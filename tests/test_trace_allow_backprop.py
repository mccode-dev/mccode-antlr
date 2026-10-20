from mccode_antlr import Flavor
from mccode_antlr.translators.c_trace import def_trace_section, undef_trace_section


def test_allow_backprop_defined_in_trace():
    # The runtime macros (PROP_*, DISALLOW_BACKPROP) use `allow_backprop` for both
    # flavors, McXtrace since McCode v3.6.9 -- see mccode-dev/mccode-antlr#118
    for flavor in (Flavor.MCSTAS, Flavor.MCXTRACE):
        assert '#define allow_backprop (_particle->allow_backprop)' in def_trace_section(flavor)
        assert '#undef allow_backprop' in undef_trace_section(flavor)

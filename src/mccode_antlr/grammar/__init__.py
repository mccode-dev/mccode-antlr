def _import_component_language():
    from .sa_mccomp import parse, SA_ErrorListener
    from .McCompVisitor import McCompVisitor, McCompParser
    return parse, SA_ErrorListener, McCompVisitor, McCompParser


def _import_instrument_language():
    from .sa_mcinstr import parse, SA_ErrorListener
    from McInstrVisitor import McInstrVisitor, McInstrParser
    return parse, SA_ErrorListener, McInstrVisitor, McInstrParser


def _import_c_language():
    from .CLexer import CLexer
    from .CParser import CParser
    from .CListener import CListener
    from .CVisitor import CVisitor
    return CLexer, CParser, CListener, CVisitor


# Import the classes defined in the language files
McComp_parse, McComp_ErrorListener, McCompVisitor, McCompParser = _import_component_language()
McInstr_parse, McInstr_ErrorListener, McInstrVisitor, McInstrParser = _import_instrument_language()
CLexer, CParser, CListener, CVisitor = _import_c_language()

# And set only their names to be exported:
__all__ = [
    'McComp_parse',
    'McComp_ErrorListener',
    'McCompParser',
    'McCompVisitor',
    'McInstr_parse',
    'McInstr_ErrorListener',
    'McInstrParser',
    'McInstrVisitor',
    'CLexer',
    'CParser',
    'CListener',
    'CVisitor',
]

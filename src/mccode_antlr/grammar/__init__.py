def _import_mcdoc_language():
    from .mcdoc_parse import parse
    from .McDocVisitor import McDocVisitor
    from .McDocParser import McDocParser
    return parse, McDocVisitor, McDocParser


def _import_component_language():
    # from .sa_mccomp import parse, SA_ErrorListener
    from .mccomp_parse import parse, ErrorListener
    from .McCompVisitor import McCompVisitor
    from .McCompParser import McCompParser
    return parse, ErrorListener, McCompVisitor, McCompParser


def _import_instrument_language():
    # from .sa_mcinstr import parse, SA_ErrorListener
    from .mcinstr_parse import parse, ErrorListener
    from .McInstrVisitor import McInstrVisitor
    from .McInstrParser import McInstrParser
    return parse, ErrorListener, McInstrVisitor, McInstrParser


def _import_c_language():
    from .CLexer import CLexer
    from .CParser import CParser
    from .CListener import CListener
    from .CVisitor import CVisitor
    return CLexer, CParser, CListener, CVisitor


# Import the classes defined in the language files
McDoc_parse, McDocVisitor, McDocParser = _import_mcdoc_language()
McComp_parse, McComp_ErrorListener, McCompVisitor, McCompParser = _import_component_language()
McInstr_parse, McInstr_ErrorListener, McInstrVisitor, McInstrParser = _import_instrument_language()
CLexer, CParser, CListener, CVisitor = _import_c_language()

# And set only their names to be exported:
__all__ = [
    'McDoc_parse',
    'McDocParser',
    'McDocVisitor',
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

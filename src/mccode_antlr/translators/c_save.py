def cogen_save(source, declared_parameters, line_directives: bool = False):
    lines = ["/* *****************************************************************************",
             f"* instrument '{source.name}' and components SAVE",
             "***************************************************************************** */",
             ]

    for comp in source.component_types():
        lines.extend(cogen_comp_save_class(comp, declared_parameters[comp.name], line_directives))

    # write the instrument main code, which calls component ones
    lines.extend([
        f'int save(FILE *handle) {{ /* called by mccode_main for {source.name}:SAVE */',
        "  if (!handle) siminfo_init(NULL);",
    ])

    # insert user code from instrument definition
    if len(source.save):
        f, n = source.save[0].fn
        lines.extend([
            f'  /* Instrument {source.name} SAVE */',
            f'  SIG_MESSAGE("[{source.name} SAVE [{f}:{n}]");'
        ])
        for par in source.parameters:
            # ensure there's no conflict of names
            lines.append(f'  #define {par.name} (instrument->_parameters.{par.name}')
        for block in source.save:
            lines.append(block.to_c(line_directives))
        for par in source.parameters:
            lines.append(f'  #undef {par.name}')

    lines.append('  /* call iteratively all components SAVE */')
    for comp in source.components:
        if len(comp.type.save):
            lines.append(f'  class_{comp.type.name}_save(&_{comp.name}_var);')

    lines.extend([
        '  if (!handle) siminfo_close();'
        '',
        '  return(0);',
        '} /* save */',
        ''
    ])
    return '\n'.join(lines)


def cogen_comp_save_class(comp, declared_parameters, line_directives: bool = False):
    from .c_defines import cogen_parameter_define, cogen_parameter_undef
    if not len(comp.save):
        return []

    lines = [
        # f'_class_{comp.name} *class_{comp.name}_save(_class_{comp.name} *_comp) {{',
        # Changed following https://github.com/McStasMcXtrace/McCode/commit/73a32858af1a5193bbb692da49379816cb0f9e38
        f'void class_{comp.name}_save(_class_{comp.name} *_comp) {{',
        cogen_parameter_define(comp, declared_parameters)
    ]
    f, n = comp.initialize[0].fn if len(comp.initialize) else (comp.name, 0)
    lines.append(f'  SIG_MESSAGE("[_{comp.name}_save] component NULL={comp.name}() [{f}:{n}]");')

    for block in comp.save:
        lines.append(block.to_c(line_directives))

    lines.extend([
        cogen_parameter_undef(comp, declared_parameters),
        # '  return(_comp);',
        '  return;',
        f'}} /* class_{comp.name}_save */',
        ''
    ])
    return lines

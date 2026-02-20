def cogen_finally(source, declared_parameters, line_directives: bool = False):
    lines = ["/* *****************************************************************************",
             f"* instrument {source.name} and components FINALLY",
             "***************************************************************************** */",
             ]

    for comp in source.component_types():
        lines.extend(cogen_comp_finally_class(comp, declared_parameters[comp.name], line_directives))

    # write the instrument main code, which calls component ones
    lines.append(f'int finally(void) {{ /* called by mccode_main for {source.name}:FINALLY */')
    lines.extend([f"#pragma acc update host(_{comp.name}_var)" for comp in source.components])
    lines.extend([
        '#pragma acc update host(_instrument_var)',
        '',
        ' siminfo_init(NULL);',
        ' save(siminfo_file); /* save data when simulation ends */'
    ])

    # insert user code from instrument definition
    if len(source.final):
        f, n = source.final[0].fn
        lines.extend([
            f'  /* Instrument {source.name} FINALLY */',
            f'  SIG_MESSAGE("[{source.name} FINALLY [{f}:{n}]");'
        ])
        for par in source.parameters:
            # ensure there's no conflict of names
            lines.append(f'  #define {par.name} (instrument->_parameters.{par.name})')
        for block in source.final:
            lines.append(block.to_c(line_directives))
        for par in source.parameters:
            lines.append(f'  #undef {par.name}')

    lines.append('  /* call iteratively all components FINALLY */')
    for comp in source.components:
        if len(comp.type.final):
            lines.append(f'  class_{comp.type.name}_finally(&_{comp.name}_var);')

        for p in comp.parameters:
            if p.value.is_vector and p.value.vector_known:
                fullname = f'_{comp.name}_var._parameters.{p.name}'
                lines.append(f'  if({fullname}) free({fullname});')


    lines.extend([
        '  siminfo_close();'
        '',
        '  return(0);',
        '} /* finally */',
        ''
    ])
    return '\n'.join(lines)


def cogen_comp_finally_class(comp, declared_parameters, line_directives: bool = False):
    from .c_defines import cogen_parameter_define, cogen_parameter_undef
    if not len(comp.final):
        return []

    lines = [
        # f'_class_{comp.name} *class_{comp.name}_finally(_class_{comp.name} *_comp) {{',
        # Changed following https://github.com/McStasMcXtrace/McCode/commit/73a32858af1a5193bbb692da49379816cb0f9e38
        f'void class_{comp.name}_finally(_class_{comp.name} *_comp) {{',
        cogen_parameter_define(comp, declared_parameters)
    ]
    f, n = comp.final[0].fn if len(comp.final) else (comp.name, 0)
    lines.append(f'  SIG_MESSAGE("[_{comp.name}_finally] component NULL={comp.name}() [{f}:{n}]");')

    for block in comp.final:
        lines.append(block.to_c(line_directives))

    lines.extend([
        cogen_parameter_undef(comp, declared_parameters),
        # '  return(_comp);',
        '  return;',
        f'}} /* class_{comp.name}_finally */',
        ''
    ])
    return lines


# def cogen_instance_finally(instance):
#     lines = [
#         f'/* component {instance.name} = {instance.type.name}() FINALLY */',
#         f'void _{instance.name}_finally(void) {{',
#     ]
#     if len(instance.type.final):
#         lines.append(f'  class_{instance.type.name}_finally(&_{instance.name}_var);')
#
#     for p in instance.parameters:
#         if p.value.is_vector and p.value.vector_known:
#             fullname = f'_{instance.name}_var._parameters.{p.name}'
#             lines.append(f'  if({fullname}) free({fullname});')
#
#     lines.extend([
#         '} /* _{instance.name}_finally */',
#         ''
#     ])
#
#     return lines

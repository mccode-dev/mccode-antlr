from loguru import logger

_GETDISTANCE_FCT = """
double index_getdistance(long first_index, long second_index)
/* Calculate the distance two components from their indexes*/
{
  return coords_len(coords_sub(POS_A_COMP_INDEX(first_index), POS_A_COMP_INDEX(second_index)));
}

double getdistance(char* first_component, char* second_component)
/* Calculate the distance between two named components */
{
  int first_index = _getcomp_index(first_component);
  int second_index = _getcomp_index(second_component);
  return index_getdistance(first_index, second_index);
}

double checked_setpos_getdistance(long current_index, char* first_component, char* second_component)
/* Calculate the distance between two named components at *_setpos() time, with component index checking */
{
  int first_index = _getcomp_index(first_component);
  int second_index = _getcomp_index(second_component);
  if (first_index >= current_index || second_index >= current_index) {
    printf(\"setpos_getdistance can only be used with the names of components before the current one!\\n\");
    return 0;
  }
  return index_getdistance(first_index, second_index);
}
#define setpos_getdistance(first, second) checked_setpos_getdistance(current_setpos_index, first, second)
"""


def _split_xyz_ref(xyz_ref):
    x, y, z = [f'{v:p}' for v in xyz_ref[0]]
    return x, y, z, xyz_ref[1]


def cogen_comp_init_position(index, comp, last, instr):
    ref = None if index == 0 else instr.components[last]
    var = f'_{comp.name}_var'
    lines = [
        f'  /* component {comp.name}={comp.type.name}() AT ROTATED */',
        f'  // {comp.partial_str()}',
        '  {',
        '    Coords tc1, tc2;',
        '    tc1 = coords_set(0,0,0);',
        '    tc2 = coords_set(0,0,0);',
        '    Rotation tr1;',
        '    rot_set_rotation(tr1,0,0,0);'
    ]
    # Rotation first
    x, y, z, rel = _split_xyz_ref(comp.rotate_relative)
    if rel is None:
        # logger.debug(f'{comp.name} has absolute orientation with rotation ({x}, {y}, {z})')
        lines.append(
            f'    rot_set_rotation({var}._rotation_absolute, ({x})*DEG2RAD, ({y})*DEG2RAD, ({z})*DEG2RAD);'
        )
    else:
        # logger.debug(f'{comp.name} has relative orientation to {rel.name} with rotation ({x}, {y}, {z})')
        lines.extend([
            f'    rot_set_rotation(tr1, ({x})*DEG2RAD, ({y})*DEG2RAD, ({z})*DEG2RAD);',
            f'    rot_mul(tr1, _{rel.name}_var._rotation_absolute, {var}._rotation_absolute);'
        ])
    # Sort out relative orientation
    if index == 0:
        lines.append(f'    rot_copy({var}._rotation_relative, {var}._rotation_absolute);')
    else:
        lines.extend([
            f'    rot_transpose(_{ref.name}_var._rotation_absolute, tr1);',
            f'    rot_mul({var}._rotation_absolute, tr1, {var}._rotation_relative);'
        ])
    lines.append(f'    {var}._rotation_is_identity = rot_test_identity({var}._rotation_relative);')

    # Then translation
    x, y, z, rel = _split_xyz_ref(comp.at_relative)
    if rel is None:
        # logger.debug(f'{comp.name} has absolute positioning with rotation ({x}, {y}, {z})')
        lines.append(f'    {var}._position_absolute = coords_set({x}, {y}, {z});')
    else:
        # logger.debug(f'{comp.name} has relative positioning to {rel.name} with rotation ({x}, {y}, {z})')
        lines.extend([
            f'    tc1 = coords_set({x}, {y}, {z});',
            f'    rot_transpose(_{rel.name}_var._rotation_absolute, tr1);',
            '    tc2 = rot_apply(tr1, tc1);',
            f'    {var}._position_absolute = coords_add(_{rel.name}_var._position_absolute, tc2);'
        ])
    if index == 0:
        lines.append(f'    tc1 = coords_neg({var}._position_absolute);')
    else:
        lines.append(f'    tc1 = coords_sub(_{ref.name}_var._position_absolute, {var}._position_absolute);')
    lines.extend([
        f'    {var}._position_relative = rot_apply({var}._rotation_absolute, tc1);',
        f'  }} /* {comp.name}={comp.type.name}() AT ROTATED */',
        f'  DEBUG_COMPONENT("{comp.name}", {var}._position_absolute, {var}._rotation_absolute);',
        f'  instrument->_position_absolute[{1 + index}] = {var}._position_absolute;',
        f'  instrument->_position_relative[{1 + index}] = {var}._position_relative;',
        f'  {var}._position_relative_is_zero = coords_test_zero({var}._position_relative);'
    ])
    return '\n'.join(lines)


def cogen_comp_setpos(index, comp, last, instr, component_declared_parameters):
    from ..common import Expr

    def parameter_line(default):
        # cogen_comp_init_par skipped any parameters which had "val" which evaluates False
        # For 'out_par' (DECLARE extracted parameters) any non-'->isoptional' values were skipped.
        # For 'set_par' any `exp_tostring(entry->val)` parameters returning NULL (which was none of them?)
        p = comp.get_parameter(default.name)
        if p is None:
            return ''
        pl = []
        fullname = f'_{comp.name}_var._parameters.{p.name}'
        value = f'{p.value:p}'
        if default.value.is_str or p.value.is_str:
            # p might be an identifier, or a string literal, or an operation
            # (function call, struct member access, ...)
            # in any case we need to copy it instead of assigning
            if p.value.is_id or p.value.is_op:
                pl.extend([
                    f'  if ({value} && strlen({value})){{',
                    f'    stracpy({fullname}, {value}, 16384);',
                    '  } else {',
                    f"    {fullname}[0] = '\\0';",
                    '  }',
                ])
            elif p.value.has_value and p.value.value != '0' and p.value.value != 'NULL' and p.value.value != '""':
                # len(value)-1 to remove quotes, but copy null terminator
                pl.append(f'  stracpy({fullname}, {value}, {len(p.value.value)-1});')
            else:
                pl.append(f"  {fullname}[0] = '\\0';")
        elif default.value.is_vector or p.value.is_vector:
            if p.value.vector_known:
                # hack-in an allocator for the fixed-length allocated array
                c_type = par.value.mccode_c_type.translate(str.maketrans('', '', ' *'))  # strip the trailing ' *'
                pl.append(f'  {fullname} = calloc(sizeof({c_type}), {len(p.value.value)});')
                for i, v in enumerate(p.value.value):
                    pl.append(f'  {fullname}[{i}] = {v};')
            elif p.value.is_id:
                pl.append(f'  {fullname} = {value};')
            else:
                # it's a string (if not None), and should be an identifier that is a pointer to the data
                pl.append(f'  {fullname} = {value if p.value.has_value else "NULL"};')
        # elif p.value.is_a(Value.Type.symbol):
        #   symbol is not handled (yet) but should be initialized to zero
        elif p.value.is_id or p.value.is_op:
            pl.append(f"  {fullname} = {value if p.value is not None else 0};")
        else:
            pl.append(f'  {fullname} = {p.value if p.value.has_value else 0};')
        return '\n'.join(pl)

    def nexus_lines():
        # If NeXus output is requested, add a group for this instance,
        # and loop over its parameter values, adding them to the group:
        gstr = f'"{index:04d}_{comp.name}"'
        pos_id = f'_{comp.name}_var._position_absolute'
        rot_id = f'_{comp.name}_var._rotation_absolute'
        lns = [
            '#ifdef USE_NEXUS',
            '  if (nxhandle) {',
            '    if ((!mcdotrace) && mcformat && strcasestr(mcformat, "NeXus")) {',
            '    MPI_MASTER(',
            f'    mccomp_placement_type_nexus(nxhandle, {gstr}, {pos_id}, {rot_id}, "{comp.type.name}");'
        ]
        # loop over component instance parameters and set their values in the NeXus group ...
        for default in comp.type.setting:
            p = comp.get_parameter(default.name)
            dstr = f'{default.value:p}'
            vstr = f'{p.value:p}'
            tstr = f'"{default.value.mccode_c_type}"'
            if not (default.value.is_str or p.value.is_str):
                dstr, vstr = [f'"{x}"' for x in (dstr, vstr)]
            lns.append(f'    mccomp_param_nexus(nxhandle, {gstr}, "{default.name}", {dstr}, {vstr}, {tstr});')

        return '\n'.join(lns + ['    );','    }','  }', '#endif'])

    f, n = comp.type.initialize[0].fn if len(comp.type.initialize) else (comp.name, 0)

    lines = [
        f'/* component {comp.name}={comp.type.name}() SETTING, POSITION/ROTATION */',
        f'int _{comp.name}_setpos(void)',
        "{ /* sets initial component parameters, position and rotation */",
        # init parameters. These can then be used in position/rotation syntax
        # all these parameters have a #define pointing to the real name space in structure
        f'  SIG_MESSAGE("[_{comp.name}_setpos] component {comp.name}={comp.type.name}() SETTING [{f}:{n}]");',
        f'  stracpy(_{comp.name}_var._name, "{comp.name}", {min(len(comp.name)+1, 16384)});',
        f'  stracpy(_{comp.name}_var._type, "{comp.type.name}", {min(len(comp.type.name)+1, 16384)});',
        f'  long current_setpos_index = _{comp.name}_var._index = {1 + index};'  # _index is a long
    ]

    # <<< This is the first call to `cogen_comp_init_par`: `cogen_comp_init_par(comp, instr, "SETTING")
    # With `section == "SETTING"` the first call picks out `comp->def->set_par`
    for par in comp.type.setting:
        # For each component definition SETTING PARAMETER the same-named instance parameter is retrieved
        lines.append(parameter_line(par))
    # >>> End of first call to `cogen_comp_init_par`
    # <<< Start of second call to `cogen_comp_init_par`: `cogen_comp_init_par(comp, instr, "PRIVATE")`
    for c_dec in component_declared_parameters[comp.type.name]:
        # c_dec is a CDeclare named tuple with (name, type, init, is_pointer, is_array, orig)
        initialized_value = 'NULL' if (c_dec.is_pointer and c_dec.init is None) else c_dec.init
        fullname = f'_{comp.name}_var._parameters.{c_dec.name}'
        if c_dec.is_array and initialized_value is not None:
            for i, val in enumerate(initialized_value.strip('{}').split(',')):
                lines.append(f'  {fullname}[{i}] = {val.strip()};')
        # elif c_dec.is_struct and initialized_value is not None:
        #     # deal with a structured initializer ...
        #     # = {.x=#, .y=#, ...}
        #     pass
        elif initialized_value is not None:
            lines.append(f'  {fullname} = {initialized_value};')
    # >>> End of second call to `cogen_comp_init_par`

    # position/rotation
    lines.append(cogen_comp_init_position(index, comp, last, instr))

    i1 = 1 + index
    lines.extend([
        f'  instrument->counter_N[{i1}] = instrument->counter_P[{i1}] = instrument->counter_P2[{i1}] = 0;',
        f'  instrument->counter_AbsorbProp[{i1}] = 0;',
        nexus_lines(),
        f'  return(0);',
        f'}} /* _{comp.name}_setpos */'
    ])
    return lines


def cogen_initialize(source, component_declared_parameters, ok_to_skip):
    from packaging.version import Version
    from mccode_antlr.reader.registry import mccode_registry_version
    version = mccode_registry_version()

    lines = ["/* *****************************************************************************",
             f"* instrument '{source.name}' and components INITIALISE",
             "***************************************************************************** */",
             _GETDISTANCE_FCT, ""]

    last = 0
    for idx, comp in enumerate(source.components):
        lines.extend(cogen_comp_setpos(idx, comp, last, source, component_declared_parameters))
        if ok_to_skip is not None and not ok_to_skip[idx]:
            last = idx

    # generate class functions
    for comp in source.component_types():
        lines.extend(cogen_comp_initialize_class(comp, component_declared_parameters[comp.name]))

    # write the instrument main code, which calls component ones
    lines.extend([
        f'int init(void) {{ /* called by mccode_main for {source.name}:INITIALIZE */',
        '  DEBUG_INSTR();',
    ])
    if version > Version("3.5.40"):
        # McCode https://github.com/mccode-dev/McCode/pull/2227#issuecomment-3613096573
        # changed `mccode_main.c` and the code-generator to move the random number
        # seeding before "INITIALIZE" time.
        # The most-recent release at that time was 3.5.40, so this change is only
        # compatible with releases after that.
        lines.extend([
            '// Initialise rng',
            '  srandom(_hash(mcseed-1));',
        ])
    lines.extend([
        '',
        '  /* code_main/parseoptions/readparams sets instrument parameters value */',
        f'  stracpy(instrument->_name, "{source.name}", {len(source.name)+1});',
    ])

    # insert user code from instrument definition
    if len(source.initialize):
        f, n = source.initialize[0].fn
        lines.extend([
            f'  /* Instrument {source.name} INITIALIZE */',
            f'  SIG_MESSAGE("[{source.name} INITIALIZE [{f}:{n}]");'
        ])
        print(f'The instrument has {len(source.parameters)} parameters')
        for par in source.parameters:
            # ensure there's no conflict of names
            lines.append(f'  #define {par.name} (instrument->_parameters.{par.name})')
        for block in source.initialize:
            lines.append(block.to_c())
        for par in source.parameters:
            lines.append(f'  #undef {par.name}')
    else:
        print("No initialization present?")

    for comp in source.components:
        lines.append(f'  _{comp.name}_setpos(); /* type {comp.type.name} */')

    lines.append('/* call iteratively all components INITIALIZE */')
    for comp in source.components:
        if len(comp.type.initialize):
            lines.append(f'  class_{comp.type.name}_initialize(&_{comp.name}_var);')

    lines.extend([
        '  if (mcdotrace) display();',
        '  DEBUG_INSTR_END();',
        '',
        # call acc_attach for OpenACC (last thing to do in init)
        '#ifdef OPENACC',
        '#include <openacc.h>',
        # update component instances on device (e.g. push managed ata structures)
        *[f'#pragma acc update device(_{comp.name}_var)' for comp in source.components],
        # update instrument
        '#pragma acc update device(_instrument_var)',
        '#endif',
        '',
        '  return(0);',
        '} /* initialize */',
        ''
    ])

    return '\n'.join(lines)


def cogen_comp_initialize_class(comp, declared_parameters):
    from .c_defines import cogen_parameter_define, cogen_parameter_undef
    if not len(comp.initialize):
        return []

    lines = [
        # f'_class_{comp.name} *class_{comp.name}_initialize(_class_{comp.name} *_comp) {{',
        # Changed following https://github.com/McStasMcXtrace/McCode/commit/73a32858af1a5193bbb692da49379816cb0f9e38
        f'void class_{comp.name}_initialize(_class_{comp.name} *_comp) {{',
        cogen_parameter_define(comp, declared_parameters)
    ]
    f, n = comp.initialize[0].fn if len(comp.initialize) else (comp.name, 0)
    lines.append(f'SIG_MESSAGE("[_{comp.name}_initialize] component NULL={comp.name}() [{f}:{n}]");')

    for block in comp.initialize:
        lines.append(block.to_c())

    lines.extend([
        cogen_parameter_undef(comp, declared_parameters),
        # '  return(_comp);',
        '  return;',
        f'}} /* class_{comp.name}_initialize */',
        ''
    ])
    return lines

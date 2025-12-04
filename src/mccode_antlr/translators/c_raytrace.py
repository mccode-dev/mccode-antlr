def cogen_raytrace(source, ok_to_skip):
    lines = [
        "/* *****************************************************************************",
        f"* instrument '{source.name}' TRACE",
        "***************************************************************************** */",
        "",
        "#ifndef FUNNEL",
        "#pragma acc routine",
        "int raytrace(_class_particle* _particle) { "
        f"/* single event propagation, called by mccode_main for {source.name}:TRACE */",
        "",
        "  /* init variables and counters for TRACE */",
        #  // we need this override, since "comp" is not defined in raytrace() - see section-wide define
        "  #undef ABSORB0",
        "  #undef ABSORB",
        "  #define ABSORB0 do { DEBUG_ABSORB(); MAGNET_OFF; ABSORBED++;} while(0)",

        "  #define ABSORB ABSORB0",
        #  /* Debugging (initial state). */
        "  DEBUG_ENTER();",
        "  DEBUG_STATE();",
    ]
    print("\n-----------------------------------------------------------")
    print("\nGenerating single GPU kernel or single CPU section layout:")

    for name, target in [(c.name, j.target) for c in source.components for j in c.jump if j.iterate]:
        lines.append(f'  _particle->_logic.Jump_{name}_{target}=0;')

    lines.extend([
        "  _particle->flag_nocoordschange=0; /* Init */",
        "  _class_particle _particle_save;",
        "  /* the main iteration loop for one incoming event */",
        "  while (!ABSORBED) { /* iterate event until absorbed */",
        "    /* send particle event to component instance, one after the other */",
    ])

    # /* now we produce the list of statements for each component index, with the attached logic */
    for index, comp in enumerate(source.components):
        if comp.split is not None:
            # split is a Value, containing a number or expression indicating *how many* split particles to produce
            print(f'-> SPLIT {comp.split:p} at component {comp.name}')
            lines.extend([
                '#ifndef NOSPLIT',
                f'    /* start SPLIT at {comp.name} */',
                '    if (!ABSORBED) {',
                f'    _class_particle Split_{comp.name}_particle = *_particle;',
                f'    int SplitS_{comp.name} = {comp.split:p};',
                # following https://github.com/McStasMcXtrace/McCode/commit/72cb740d465e2780b228bd937cf62429a96f64d5
                '    #pragma acc loop independent',
                f'    for (int SplitN_{comp.name}=0; SplitN_{comp.name} < SplitS_{comp.name}; SplitN_{comp.name}++) {{',
                '    randstate_t randbackup = *_particle->randstate;',
                f'    *_particle=Split_{comp.name}_particle;',
                '    *_particle->randstate = randbackup;',
                f'    p /= SplitS_{comp.name} > 0 ? SplitS_{comp.name} : 1;',
                '#endif'
            ])
        # Coordinate transforms WRT PREVIOUS
        lines.append(f'    /* begin component {comp.name}={comp.type.name}() [{1+index}] */')
        if not ok_to_skip[index]:
            lines.extend([
                "    if (!_particle->flag_nocoordschange) { // flag activated by JUMP to pass coords change",
                f"      if (_{comp.name}_var._rotation_is_identity) {{",
                f"        if(!_{comp.name}_var._position_relative_is_zero) {{",
                f"          coords_get(coords_add(coords_set(x,y,z), _{comp.name}_var._position_relative),&x, &y, &z);",
                "        }",
                "      } else {",
                f"          mccoordschange(_{comp.name}_var._position_relative, _{comp.name}_var._rotation_relative, _particle);",
                "      }",
                "    }",
            ])
        lines.extend([
            f'    if (!ABSORBED && _particle->_index == {1+index}) {{',
            '      _particle->flag_nocoordschange=0; /* Reset if we came here from a JUMP */',
        ])
        if comp.group is None or source.groups[comp.group].is_leader(index):
            # This allows an empty ('') named group :/
            if not ok_to_skip[index]:
                lines.append('      _particle_save = *_particle;')
        else:
            lines.extend([
                '      // 2nd or higher GROUP member, "reuse" coordinate-changed _particle_Save from 1st GROUP element.',
                f'      mccoordschange(_{comp.name}_var._position_relative, _{comp.name}_var._rotation_relative, &_particle_save);',
            ])
        if not ok_to_skip[index]:
            lines.extend([
                f'      DEBUG_COMP(_{comp.name}_var._name);',
                '      DEBUG_STATE();'
            ])
        if len(comp.type.trace) or len(comp.extend):
            # WHEN
            if comp.when is not None:
                lines.append(f'      if (({comp.when:p}))  // conditional WHEN execution')
            lines.extend([
                f'      class_{comp.type.name}_trace(&_{comp.name}_var, _particle);{" /* contains EXTEND code */" if len(comp.extend) else ""}',
                '      if (_particle->_restore)',
                '        particle_restore(_particle, &_particle_save);'
            ])
        # If we have a JUMP, change the index
        for jump in comp.jump:
            if jump.iterate:
                lines.extend([
                    f'      if (++_particle->_logic.Jump_{comp.name}_{jump.target} < {jump.condition:p}) {{ /* test for iteration */',
                    f'        _particle->_index = {jump.absolute_target};',  # NO -1 despite to ++ below, 0-based target
                    '        _particle->flag_nocoordschange=1; /* pass coordinate transformations when jumping */',
                    '      } else {',
                    f'        _particle->_logic.Jump_{comp.name}_{jump.target} = 0; /* reset Jump top and go forward */',
                    '      }'
                ])
            else:
                lines.extend([
                    f'      if ({jump.condition:p}) {{/* conditional JUMP to {jump.target} */',
                    f'        _particle->_index = {jump.absolute_target};',  # target is 0-based, _index 1; OK
                    '        _particle->flag_nocoordschange=1; /* pass coordinate transformations when jumping */',
                    '      }'
                ])
        # If we are in a group handle SCATTERED
        if comp.group is not None:
            group = source.groups[comp.group]
            fn = group.first.name
            ln = group.last.name
            lid = group.last_id
            lines.extend([
                f'      // GROUP {group.name}: from {fn} [{group.first_id}] to {ln} [{1+lid}]',
                # Skip over when SCATTERED in the group:
                f'      if (SCATTERED) _particle->_index = {1+lid}; '
                f'// when SCATTERED in GROUP: reach exit of GROUP after {ln}',
                #
            ])
            if index == lid:
                lines.append('      else ABSORBED=1; // Not SCATTERED by end of GROUP: particle does not progress')
            else:
                lines.append('      else particle_restore(_particle, &_particle_save); // not SCATTERED in GROUP, restore')

        lines.append('      _particle->_index++;')
        if not ok_to_skip[index]:
            lines.append('      if (!ABSORBED) { DEBUG_STATE(); }')
        lines.append(f'    }} /* end of component {comp.name} [{1+index}] */')

    # /* now we close the SPLIT loops, unrolled from last to 1st */
    for comp in reversed(source.components):
        if comp.split is not None:
            lines.extend([
                '#ifndef NOSPLIT',
                f'    }} /* end SPLIT at {comp.name} */',
                f'    }} /* if (!ABSORBED) relating to SPLIT at {comp.name} */',
                '#endif'
            ])

    # /* handle ABSORB when no more comp, go to next comp, and RESTORE */
    lines.extend([
        # /* propagate to the next component */
        f'    if (_particle->_index > {len(source.components)})',
        # /* if we reach the last component and nothing happened, ABSORB */
        '      ABSORBED++; /* absorbed when passed all components */',
        "  } /* while !ABSORBED */",
        "",
        "  DEBUG_LEAVE()",
        "  particle_restore(_particle, &_particle_save);",
        #  /* Debugging (final state). */
        "  DEBUG_STATE()",
        "",
        "  return(_particle->_index);",
        "} /* raytrace */",
        #  // write the "raytrace_all()" code (for loop previously in mccode_main.c).
        "",
        "/* loop to generate events and call raytrace() propagate them */",
        "void raytrace_all(unsigned long long ncount, unsigned long seed) {",
        "",
        "  /* CPU-loop */",
        "  unsigned long long loops;",
        "  loops = ceil((double)ncount/gpu_innerloop);",
        "  /* if on GPU, printf has been globally nullified, re-enable here */",
        "  #ifdef OPENACC",
        "  #undef strlen",
        "  #undef strcmp",
        "  #undef exit",
        "  #undef printf",
        "  #undef sprintf",
        "  #undef fprintf",
        "  #endif",
        "",
        "  #ifdef OPENACC",
        "  if (ncount>gpu_innerloop) {",
        '    printf("Defining %llu CPU loops around GPU kernel and adjusting ncount\\n",loops);',
        "    mcset_ncount(loops*gpu_innerloop);",
        "  } else {",
        "    #endif",
        "    loops=1;",
        "    gpu_innerloop = ncount;",
        "    #ifdef OPENACC",
        "  }",
        "    #endif",
        "",
        "  for (unsigned long long cloop=0; cloop<loops; cloop++) {",
        "    #ifdef OPENACC",
        '    if (loops>1) fprintf(stdout, "%d..", (int)cloop); fflush(stdout);',
        "    #endif",
        "",
        "    /* if on GPU, re-nullify printf */",
        "    #ifdef OPENACC",
        "    #undef strlen",
        "    #undef strcmp",
        "    #undef exit",
        "    #undef printf",
        "    #undef sprintf",
        "    #undef fprintf",
        "    #endif",
        "",
        "    #pragma acc parallel loop num_gangs(numgangs) vector_length(vecsize)",
        "    for (unsigned long pidx=0 ; pidx < gpu_innerloop ; pidx++) {",
        "      _class_particle particleN = mcgenstate(); // initial particle",
        "      _class_particle* _particle = &particleN;",
        "      particleN._uid = pidx;",
        "      #ifdef USE_MPI",
        "      particleN._uid += mpi_node_rank * ncount;",
        "      #endif",
        "",
        "      srandom(_hash((pidx+1)*(seed+1)));",
        "      particle_uservar_init(_particle);",
        "",
        "      raytrace(_particle);",
        "    } /* inner for */",
        "    seed = seed+gpu_innerloop;",
        "  } /* CPU for */",
        "  /* if on GPU, printf has been globally nullified, re-enable here */",
        "  #ifdef OPENACC",
        "  #undef strlen",
        "  #undef strcmp",
        "  #undef exit",
        "  #undef printf",
        "  #undef sprintf",
        "  #undef fprintf",
        "  #endif",
        "  MPI_MASTER(",
        '  printf("*** TRACE end *** \\n");',
        "  );",
        "} /* raytrace_all */",
        "",
        "#endif //no-FUNNEL",
    ])

    return '\n'.join(lines)


def cogen_funnel(source, ok_to_skip):
    from ..common.utilities import escape_str_for_c
    print('\n-----------------------------------------------------------')
    print('\nGenerating GPU/CPU -DFUNNEL layout:')

    lines = [
        "",
        "#ifdef FUNNEL",
        "// Alternative raytrace algorithm which iterates all particles through",
        "// one component at the time, can remove absorbs from the next loop and",
        "// switch between cpu/gpu.",
        "void raytrace_all_funnel(unsigned long long ncount, unsigned long seed) {",
        "",
        "  // set up outer (CPU) loop / particle batches",
        "  unsigned long long loops;",
        "",
        "  /* if on GPU, printf has been globally nullified, re-enable here */",
        "  #ifdef OPENACC",
        "  #undef strlen",
        "  #undef strcmp",
        "  #undef exit",
        "  #undef printf",
        "  #undef sprintf",
        "  #undef fprintf",
        "  #endif",
        "",
    ]

    for i, c in [(i, c) for i, c in enumerate(source.components) if len(c.jump)]:
        message = [
            f'\nWARNING:\n --> JUMP found at COMPONENT {i}, {c.name}',
            ' --> JUMPS are not supported in FUNNEL mode and are ignored',
            ' --> Your instrument may give different output with FUNNEL'
        ]
        print('\n'.join(message))
        lines.extend(f'printf("{escape_str_for_c(ml)}\\n");' for ml in message)

    lines.extend([
        "  #ifdef OPENACC",
        "  loops = ceil((double)ncount/gpu_innerloop);",
        "  if (ncount>gpu_innerloop) {",
        '    printf("Defining %llu CPU loops around kernel and adjusting ncount\\n",loops);',
        "    mcset_ncount(loops*gpu_innerloop);",
        "  } else {",
        "  #endif",
        "    loops=1;",
        "    gpu_innerloop = ncount;",
        "  #ifdef OPENACC",
        "  }",
        "  #endif",
        "",
        "  // create particles struct and pointer arrays (same memory used by all batches)",
        "  _class_particle* particles = malloc(gpu_innerloop*sizeof(_class_particle));",
        "  _class_particle* pbuffer = malloc(gpu_innerloop*sizeof(_class_particle));",
        "  long livebatchsize = gpu_innerloop;",
        "",
        #  // we need this override, since "comp" is not defined in raytrace() - see section-wide define
        "  #undef ABSORB0",
        "  #undef ABSORB",
        "  #define ABSORB0 do { DEBUG_ABSORB(); MAGNET_OFF; ABSORBED++; } while(0)",
        "  #define ABSORB ABSORB0",
        #  // batches
        "  // outer loop / particle batches",
        "  for (unsigned long long cloop=0; cloop<loops; cloop++) {",
        '    if (loops>1) fprintf(stdout, "%d..", (int)cloop); fflush(stdout);',
        "",
        #  // init batch
        "    // init particles",
        "    #pragma acc parallel loop present(particles[0:livebatchsize])",
        "    for (unsigned long pidx=0 ; pidx < livebatchsize ; pidx++) {",
        "      // generate particle state, set loop index and seed",
        "      particles[pidx] = mcgenstate();",
        "      _class_particle* _particle = particles + pidx;",
        "      _particle->_uid = pidx;",
        "      #ifdef USE_MPI",
        "      _particle->_uid += mpi_node_rank * ncount;",
        "      #endif",
        "      srandom(_hash((pidx+1)*(seed+1))); // _particle->state usage built into srandom macro",
        "      particle_uservar_init(_particle);",
        "    }",
        "",
        '    // iterate components'
    ])
    cpu_last = not source.components[0].cpu if len(source.components) else False
    for index, comp in enumerate(source.components):
        if not comp.type.acc:
            print(f'Component {comp.name} is NOACC, CPUONLY={comp.cpu}')
            print('->FUNNEL mode enabled, SPLIT within buffer.')
            lines.append('        #define JUMP_FUNNEL')
        if index > 0 and (comp.cpu != cpu_last or comp.split is not None):
            lines.append("    }")
            if comp.split is not None:
                lines.extend([
                    '',
                    "    // SPLIT with available livebatchsize ",
                    f"    long mult_{comp.name};",
                    f"    livebatchsize = sort_absorb_last(particles, pbuffer, livebatchsize, gpu_innerloop, 1, &mult_{comp.name});",
                    "    //printf(\"livebatchsize: %ld, split: %ld\\n\",  livebatchsize, mult);",
                ])
                print(f'-> SPLIT within buffer at component {comp.name}')

        elif comp.cpu:
            print(f'-> CPU section from component {comp.name}')
        else:
            print(f'-> GPU kernel from component {comp.name}')

        if index == 0 or comp.cpu != cpu_last or comp.split is not None:
            lines.append("")
            if not comp.cpu:
                lines.extend([
                    "    #pragma acc parallel loop present(particles[0:livebatchsize])"
                ])
            else:
                lines.extend([
                    "    #ifdef MULTICORE",
                    "    #pragma acc parallel loop device_type(host)",
                    "    #endif"
                ])
            lines.extend([
                "    for (unsigned long pidx=0 ; pidx < livebatchsize ; pidx++) {",
                "      _class_particle* _particle = &particles[pidx];",
                "      _class_particle _particle_save;",
            ])

        lines.extend([
            f'      // {comp.name}',
            f'      if (!ABSORBED && _particle->_index == {index+1}) {{',
        ])
        if not ok_to_skip[index]:
            lines.extend([
                "        #ifndef MULTICORE",
                f"        if (_{comp.name}_var._rotation_is_identity) {{",
                f"          coords_get(coords_add(coords_set(x,y,z), _{comp.name}_var._position_relative),&x, &y, &z);",
                "        } else",
                "        #endif",
                "        {",
                f"          mccoordschange(_{comp.name}_var._position_relative, _{comp.name}_var._rotation_relative, _particle);",
                '        }',
                "        _particle_save = *_particle;",
            ])
        if len(comp.type.trace) or len(comp.extend):
            if comp.when is not None:
                lines.append(f'    if (({comp.when:p}))  // conditional WHEN')
            lines.extend([
                f'        class_{comp.type.name}_trace(&_{comp.name}_var, _particle);{" /* contains EXTEND code */" if len(comp.extend) else ""}',
                '         if (_particle->_restore) particle_restore(_particle, &_particle_save);'
            ])
        if comp.group is not None:
            group = source.groups[comp.group]
            if len(group.ids) < 2:
                print(f'\n!!! WARNING: GROUP {group.name} seems to include only one COMPONENT:')
                print(f'!!!   --> {comp.name} <--')
                print('!!! This may lead to unphysical simulation behaviour!')
            ln = group.last.name
            lid = group.last_id
            lines.extend([
                f'    // GROUP {group.name}: from {group.first.name} [{group.first_id}] to {ln} [{lid}]',
                # Skip over when SCATTERED in the group:
                f'    if (SCATTERED) _particle->_index = {lid}; '
                '// when SCATTERED in GROUP: reach exit of GROUP after {ln}',
                #
            ])
            if index == lid:
                lines.append('    else ABSORBED=1; // Not SCATTERED by end of GROUP: removes left events')
            else:
                lines.append("      else ABSORBED=0; // not SCATTERED within GROUP: always tries next")

        lines.append("        _particle->_index++;")
        lines.append("      }")
        cpu_last = comp.cpu

    lines.extend([
        '    }',
        "    // jump to next viable seed",
        "    seed = seed + gpu_innerloop;",
        "  } // outer loop / particle batches",
        "",
        "  free(particles);",
        "  free(pbuffer);",
        "",
        '  printf("\\n");',
        "} /* raytrace_all_funnel */",
        "#endif // FUNNEL",
        "",
    ])

    print("\n-----------------------------------------------------------")

    return '\n'.join(lines)

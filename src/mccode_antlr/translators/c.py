"""Translates a McComp instrument from its intermediate form to a C runtime source file."""
from loguru import logger
from dataclasses import dataclass
from .target import TargetVisitor
from .c_listener import extract_c_declared_variables
from mccode_antlr import Flavor


@dataclass
class CInclude:
    parent: str
    name: str
    order: int
    content: str = ''
    root: str = ''

    def __hash__(self):
        return hash(self.parent + self.name + self.content + self.root)

    def __str__(self):
        return f'{self.root}:{self.parent}({self.order}):{self.name}'

    def __lt__(self, other):
        if self.parent == other.parent:
            return self.order > other.order
        if self.root or other.root:
            if self.parent == self.root or self.parent == other.root:
                return True
            if other.parent == self.root or other.parent == other.root:
                return False
        if self.parent == other.name:
            return False
        if other.parent == self.name:
            return True
        return self.name < other.name


def sort_include_hierarchy(includes: list[CInclude]):
    if len(includes) == 0:
        return []
    logger.debug(f'sort includes {" ".join(str(x) for x in includes)}')
    # find the 'root' of the tree, a parent which is _not_ a named include:
    roots = list(set([x.parent for x in includes]).difference(set([x.name for x in includes])))
    options = {}
    for root in roots:
        for include in includes:
            include.root = root
        # Sort the includes such that if A includes B and C, and C includes B, then we get [C:B, A:C, A:B]
        # Or a more complicated case: G:(Z,A,W), Z:(B,Y), A:X, W(Y) -> [Z:Y, W:Y, A:X, B:W, Z:B, G:A, G:Z, G:W]
        used, output = [], []
        for include in sorted(includes, reverse=True):
            if include.name not in used:
                output.append(include)
                used.append(include.name)
        # Reduce output to [C:B, A:C], or [Z:Y, A:X, B:W, Z:B, G:A, G:Z], which would include the libraries correctly
        # Double check, that the include order does not _directly_ contradict one of the include directives:
        order = [x.name for x in output]
        contradicts = False
        for include in includes:
            if include.parent in order and include.name in order:
                parent_at = [index for index, name in enumerate(order) if name == include.parent][0]
                name_at = [index for index, name in enumerate(order) if name == include.name][0]
                if name_at > parent_at:
                    contradicts = True
        if not contradicts:
            logger.debug(f"sorted to {'  '.join(order)}")
            options[root] = output
    if len(options) == 0:
        raise RuntimeError(f'No valid sorting of {includes=}')
    # Maybe there's a case where the specified root matters?
    return list(options.values())[0]


class CTargetVisitor(TargetVisitor, target_language='c'):
    def _file_contents(self, filename, preserve_escapes=False):
        # First try the McCode C runtime libraries:
        path = self.include_path(filename)
        # Then any registries used in reading the file(s)
        if not path.is_file() and self.known(filename):
            path = self.locate(filename)
        if not path.is_file():
            raise RuntimeError(f"Can not include the file {filename} because it is not locatable")
        with path.open('r') as file:
            lines = [line.strip('\n') for line in file.readlines()]
        if preserve_escapes:
            lines = [line.encode('unicode-escape').decode('utf-8') for line in lines]
        return '\n'.join(lines)

    def _handle_raw_c_include(self, parent: str, raw_c: str):
        import re
        re_lib = re.compile(r'^\s*%include\s*"(?P<libname>[^"\n\.]+)"\s*$', re.MULTILINE)
        re_inc = re.compile(r'^\s*%include\s*"(?P<filename>[^"\n]+)"\s*$', re.MULTILINE)
        # Include statements without an extension are library includes (.h, plus .c if embedding the runtime)
        # McCode3 would insert the library immediately on first-encounter, but we want to collect all libraries
        # and ensure they're included before all components.

        # Get any library names in this block:
        libraries = list(dict.fromkeys([match.group('libname') for match in re_lib.finditer(raw_c)]))
        # *erase* the library includes from the block:
        raw_c = re.sub(re_lib, '', raw_c)

        # We must look through the to-be-included code *now* to see if it *also* includes more libraries.
        includes = [CInclude(parent=parent, name=lib, order=index, content=self._file_contents(f'{lib}.h'))
                    for index, lib in enumerate(libraries)]
        new_includes = []
        for include in includes:
            found_includes, include.content = self._handle_raw_c_include(include.name, include.content)
            if found_includes:
                new_includes.extend(found_includes)
                new_includes = list(dict.fromkeys(new_includes))
        if len(new_includes):
            includes.extend(new_includes)
            includes = list(dict.fromkeys(includes))

        # If there are any non-library includes remaining, we should insert them immediately:
        matches = list(re_inc.finditer(raw_c))
        count = 0
        while len(matches):
            count += 1
            # matches[0] is a re.Match object with (start, stop) = matches[0].span(0) including the full matched string
            # We can use this directly to replace the match without using re.sub, which can cause problems if there are
            # escape characters in the replacement (It seems)
            start, stop = matches[0].span(0)
            raw_c = raw_c[:start] + self._file_contents(matches[0].group('filename')) + raw_c[stop:]

            #filename = matches[0].group('filename')
            #this_re = re.compile(rf'^\s*%include\s*"{filename}"\s*$', re.MULTILINE)
            #logger.info(f'Replacing {this_re} with file contents from {filename}')
            #raw_c = re.sub(this_re, self._file_contents(filename, True), raw_c)

            # re-match since we modified raw_c
            matches = list(re_inc.finditer(raw_c))

        if count:
            found_includes, raw_c = self._handle_raw_c_include(parent, raw_c)
            if len(found_includes):
                includes.extend(found_includes)
                includes = list(dict.fromkeys(includes))

        return includes, raw_c

    def _parse_libraries_for_typedefs(self):
        from .c_listener import extract_c_defined_types as parse
        typedefs = set()
        for include in self.includes:
            # logger.debug(f'library {include.name}')
            # The files '%include'-d can themselves use the '%include' mechanism :/
            defined_types = parse(include.content, user_types=list(typedefs))
            typedefs = typedefs.union(set(defined_types))
            # logger.debug(f'{include.name} done')
        # types can also be defined in component 'SHARE' blocks:
        for block in [share for comp in self.source.component_types() if len(comp.share) for share in comp.share]:
            # TODO decide if this should be block.translated or block.source
            defined_types = parse(block.to_c(), user_types=list(typedefs))
            typedefs = typedefs.union(set(defined_types))
        self.typedefs = list(typedefs)

    def _determine_uservars(self):
        """An instrument can define 'USERVARS' which thus far has been treated as an unparsed block of code.
        We now must extract parameter declarations from this block (there should be *only* declarations, no
        initialization is supported in McCode-3).
        Each declaration *should* of the form
            {type} {name};
            {type} * {name};
            {type} {name}[N];
        Where {type} is a valid C typename _or_ a typename defined in any included libraries or 'SHARE' blocks.
        A possible future extension could allow for valid instantiation in the USERVAR blocks.
        This function extracts the parameter {name}, {type}, (scalar|pointer|array)-ness, and initializer if present
        for the unique set of all variables added to the _particle struct by the user -- it checks for name clashes
        between definitions as well (identical definitions are allowed but not equal named non-matching definitions)

        Extracted values are stored in namedtuple `CDeclaration` objects for easier interaction.
        """
        def extract_declares(name, raw_c_obj):
            # TODO decide if this should be raw_c_obj.translated or raw_c_obj.source
            c_decs = extract_c_declared_variables(raw_c_obj.to_c(), user_types=self.typedefs)
            if any(d.init is not None for d in c_decs):
                logger.critical(f'Warning USERVARS block from {name} contains assignment(s) (= sign).')
                logger.critical('        Move them to an EXTEND section. May fail at compile')
            return c_decs

        declares = []  # runtime-accessing by 'ID' only possible if order is preserved
        for raw_user_vars_c_block in self.source.user:
            # declares = declares.union(extract_declares(self.source.name, raw_user_vars_c_block))
            declares.extend(extract_declares(self.source.name, raw_user_vars_c_block))
            declares = list(dict.fromkeys(declares))

        # Check for differing repeated declarations -- these are set elements with the same name:
        if len(set([d.name for d in declares])) != len(declares):
            raise RuntimeError(f"One or more instrument USERVARS repeated in {self.source.name}")

        # Look for USERVAR section(s) in the set of component definitions too:
        comp_declares = dict()
        for component in self.source.component_types():
            # temp_set = set()
            a_declares = []
            for raw_user_vars_c_block in component.user:
                # temp_set = temp_set.union(extract_declares(component.name, raw_user_vars_c_block))
                a_declares.extend(extract_declares(component.name, raw_user_vars_c_block))
                a_declares = list(dict.fromkeys(a_declares))
            comp_declares[component.name] = a_declares
            # Check for differing repeated declarations in this component:
            if len(set([d.name for d in comp_declares[component.name]])) != len(comp_declares[component.name]):
                raise RuntimeError(f"One or more component USERVARS repeated in {component.name}")

        # Go through all components with uservars, then through the instances of that type
        # and append the instance index to the name of the uservar
        inst_declares = dict()
        for comp_name, a_declares in comp_declares.items():
            i_declares = []
            for index, instance in enumerate(self.source.components):
                if instance.type.name == comp_name:
                    i_declares.extend([d.copy(suffix=str(index+1)) for d in a_declares])
            inst_declares[comp_name] = i_declares
        # Replace the component definition 'base' uservar declares with the 'real' ones:
        comp_declares = inst_declares

        # And between all components and the instrument
        nd = set([x for dec in comp_declares.values() for x in dec]).union(declares)
        if len(set([x.name for x in nd])) != len(nd):
            culprits = [x.name for x in self.source.component_types() if len(comp_declares[x.name])]
            raise RuntimeError(f'Conflicting USERVAR declarations between instrument {self.source.name} and {culprits}')

        self.instrument_uservars = declares
        self.component_uservars = comp_declares

    def __post_init__(self):
        """Before doing *anything* else. We need to search through all raw C code for %include statements.
        This could not be done earlier if the goal is to have a clear separation between the parsing and target
        languages. (A different target language would not include the same libraries in its raw blocks)
        """
        # Make sure the registry list contains the C library registry, so that we can find and include files
        from packaging.version import Version
        from ..reader.registry import ordered_registries, ensure_registries
        # make sure that the libc registry is present before sorting:
        self.source.registries = tuple(ordered_registries(ensure_registries(Flavor.BASE, list(self.source.registries))))

        # Check that the LIBC registry is not too old for current translation
        for reg in self.source.registries:
            # NeXus interface changed in v3.5.20 release of McStas/McXtrace == McCode
            if 'libc' == reg.name and Version(reg.version) < Version("3.5.20"):
                logger.warning(f"Requested McCode libc version {reg.version} may"
                               " cause errors since it is less than v3.5.20")

        includes = []
        inst = self.source
        for grp in (inst.user, inst.declare, inst.initialize, inst.save, inst.final):
            for block in grp:
                incs, block.translated = self._handle_raw_c_include(inst.name, block.source)
                includes.extend(incs)
                includes = list(dict.fromkeys(includes))
        for typ in inst.component_types():
            for grp in (typ.share, typ.user, typ.declare, typ.initialize, typ.trace, typ.save, typ.final, typ.display):
                for block in grp:
                    incs, block.translated = self._handle_raw_c_include(typ.name, block.source)
                    includes.extend(incs)
                    includes = list(dict.fromkeys(includes))
        for instance in inst.components:
            for block in instance.extend:
                incs, block.translated = self._handle_raw_c_include(instance.name, block.source)
                includes.extend(incs)
                includes = list(dict.fromkeys(includes))
        self.includes = sort_include_hierarchy(includes)

        # search the library headers for type definitions:
        self._parse_libraries_for_typedefs()

        # pull together the per-component-type defined parameters into a dictionary... since this is required
        # in multiple places :/  -- now using CDeclarator class objects
        for typ in inst.component_types():
            dp = []
            for block in typ.declare:
                # TODO decide if this should be block.translated or block.source
                dp.extend(extract_c_declared_variables(block.to_c(), user_types=self.typedefs))
                dp = list(dict.fromkeys(dp))
            self.component_declared_parameters[typ.name] = dp
        self._determine_uservars()

    def _instrument_and_component_uservars(self):
        uuv = [x for x in self.instrument_uservars]
        for comp_name, comp_uv in self.component_uservars.items():
            uuv.extend(comp_uv)
            uuv = list(dict.fromkeys(uuv))
        return uuv

    def visit_header(self):
        from .c_header import header_pre_runtime, header_post_runtime
        # Get the unique list of USERVAR declarations:
        # logger.debug(f'Instrument uservars = {self.instrument_uservars}')
        # uuv = set().union(self.instrument_uservars)
        # for x in self.component_uservars:
        #     uuv = uuv.union(x)

        uuv = self._instrument_and_component_uservars()
        self.out(header_pre_runtime(self.source, self.flavor, self.config, uuv))
        # runtime part
        name = str(self.flavor).lower()
        if self.config.get('include_runtime'):
            self.out('#define MC_EMBEDDED_RUNTIME')
            if self.known('mccode-r.h', strict=True):
                self.embed_file('mccode-r.h')
            else:
                self.configure_file('mccode-r.h.in', name)

            self.embed_file(f'{name}-r.h')
            self.embed_file("mccode-r.c")
            self.embed_file(f'{name}-r.c')
            if self.verbose:
                print(f"Compile with flags '-DUSE_NEXUS -lNeXus' to enable NeXus support")
        else:
            # This only works if the module is *not* a compressed archive
            # If it is, we would need to do some trickery to ... write out the
            self.out(f'#include "{self.include_path("mccode-r.h")}"')
            path = self.include_path(f"{name}-r.h")
            self.out(f'#include "{path}"')
            libname = f'{name}-r.o'
            print(f"Dependency: mccode-r.o\nDependency: {libname}")

        # # TODO insert includes here?
        # if len(self.includes):
        #     self.out("/* %include libraries from instrument and component definitions */")
        # for include in self.includes:
        #     self.out(f'/* Contents of {include.name}.h (requested from {include.parent})*/')
        #     self.out(include.content)

        self.out(header_post_runtime(self.source, self.flavor, self.config, self.include_path()))

    def include_header(self, header: CInclude):
        self.info(f'include {header} header')
        self.out(f'/* Contents of {header.name}.h (requested from {header.parent}) */')
        self.out(header.content)

    def include_source(self, source: CInclude):
        self.info(f'include {source} source')
        # c files can %include *more* files! If the specified files have already been included, there's nothing
        # to do. Otherwise, panic.
        lib_names = [lib.name for lib in self.includes]
        c_name = f'{source.name}.c'
        c_libraries, c_content = self._handle_raw_c_include(c_name, self._file_contents(c_name))
        for c_lib in [c_lib for c_lib in c_libraries if c_lib.name not in lib_names]:
            logger.info(f'{c_name} requested {c_lib.name} but is has not been included yet!')
            self.include_header(c_lib)
            self.include_source(c_lib)
            #self.includes.append(c_lib)
        self.out(f'/* Contents of {source.name}.c (requested from {source.parent}) */')
        self.out(c_content)

    def visit_declare(self):
        from .c_decls import declarations_pre_libraries
        self.info("Writing instrument and components DECLARE")

        if len(self.includes):
            self.out("/* %include libraries from instrument and component definitions */")
        for include in self.includes:
            self.include_header(include)

        self.info('Pre library declarations')
        contents, warnings = declarations_pre_libraries(self.source, self.typedefs, self.component_declared_parameters)
        self.out(contents)

        self.info('Include runtime / list dependencies')
        if self.config.get('include_runtime'):
            for include in self.includes:
                self.include_source(include)
        else:
            for include in self.includes:
                print(f'Dependency: {include.name}.o')

        self.out("/* User declarations from instrument definition. Can define functions. */")
        self.out('\n'.join([dec.to_c() for dec in self.source.declare]))
        # FIXME I _think_ these macro undefines are not used (that is, they're never defined in the first place)
        self.out('#undef compcurname\n#undef compcurtype\n#undef compcurindex')
        self.out(f"/* end of instrument '{self.source.name}' and components DECLARE */")

        self.warnings += warnings

    def visit_initialize(self):
        from .c_initialise import cogen_initialize
        self.out(cogen_initialize(self.source, self.component_declared_parameters, self.ok_to_skip))

    def enter_trace(self):
        from .c_trace import def_trace_section, cogen_trace_section
        self.out(def_trace_section(self.flavor))
        self.out(cogen_trace_section(self.flavor, self.source, self.component_declared_parameters,
                                     self.instrument_uservars, self.component_uservars))

    def leave_trace(self):
        from .c_trace import undef_trace_section
        self.out(undef_trace_section(self.flavor))

    def enter_uservars(self):
        # After cogen_trace_section, the USERVAR particle struct members need to be defined for raytrace
        uuv = self._instrument_and_component_uservars()
        self.out('\n'.join([f'#define {x.name} (_particle->{x.name})' for x in uuv]))

    def leave_uservars(self):
        # following TRACE before undef_trace_section, the USERVAR particle struct members need to be undef'd
        uuv = self._instrument_and_component_uservars()
        self.out('\n'.join([f'#undef {x.name}' for x in uuv]))

    def visit_raytrace(self):
        from .c_raytrace import cogen_raytrace
        self.out(cogen_raytrace(self.source, self.ok_to_skip))

    def visit_raytrace_funnel(self):
        from .c_raytrace import cogen_funnel
        self.out(cogen_funnel(self.source, self.ok_to_skip))

    def visit_save(self):
        from .c_save import cogen_save
        self.out(cogen_save(self.source, self.component_declared_parameters))

    def visit_finally(self):
        from .c_finally import cogen_finally
        self.out(cogen_finally(self.source, self.component_declared_parameters))

    def visit_display(self):
        from .c_display import cogen_display
        self.out(cogen_display(self.source, self.component_declared_parameters))

    def visit_macros(self):
        from .c_macros import cogen_getvarpars_fct, cogen_getcompindex_fct, cogen_getparticlevar_fct
        self.out(cogen_getvarpars_fct(self.source))
        self.out(cogen_getparticlevar_fct(self._instrument_and_component_uservars()))
        self.out(cogen_getcompindex_fct(self.source))
        self.embed_file('metadata-r.c')
        self.embed_file('mccode_main.c')
        self.out(f'/* end of generated C code for {self.source.name} */')

    def visit_flags(self):
        """Output compilation flags to STDOUT, so that (e.g.) mcrun can pick them up"""
        flags = self.source.decoded_flags()
        if len(flags):
            print(f'CFLAGS= {" ".join(flags)}')
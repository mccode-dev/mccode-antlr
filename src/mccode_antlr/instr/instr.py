"""Data structures required for representing the contents of a McCode instr file"""
from __future__ import annotations

from io import StringIO
from msgspec import Struct, field
from typing import Optional
from ..common import InstrumentParameter, MetaData, parameter_name_present, RawC, blocks_to_raw_c, Expr, Value
from ..reader import Registry
from .instance import Instance, DepInstance, Comp
from .group import Group, DependentGroup
from loguru import logger


# @dataclass
class Instr(Struct):
    """Intermediate representation of a McCode instrument

    Read from a .instr file -- possibly including more .comp and .instr file sources
    For output to a runtime source file
    """
    name: Optional[str] = None  # Instrument name, e.g. {name}.instr (typically)
    source: Optional[str] = None  # Instrument *file* name
    parameters: tuple[InstrumentParameter, ...] = field(default_factory=tuple)  # runtime-set instrument parameters
    metadata: tuple[MetaData, ...] = field(default_factory=tuple)  # metadata for use by simulation consumers
    components: tuple[Instance, ...] = field(default_factory=tuple)  #
    included: tuple[str, ...] = field(default_factory=tuple)  # names of included instr definition(s)
    user: tuple[RawC, ...] = field(default_factory=tuple)  # struct members for _particle
    declare: tuple[RawC, ...] = field(default_factory=tuple)  # global parameters used in component trace
    initialize: tuple[RawC, ...] = field(default_factory=tuple)  # initialization of global declare parameters
    save: tuple[RawC, ...] = field(default_factory=tuple)  # statements executed after TRACE to save results
    final: tuple[RawC, ...] = field(default_factory=tuple)  # clean-up memory for global declare parameters
    groups: dict[str, Group] = field(default_factory=dict)
    flags: tuple[str, ...] = field(default_factory=tuple)  # (C) flags needed for compilation of the (translated) instrument
    registries: tuple[Registry, ...] = field(default_factory=tuple)  # the registries used by the reader to populate this

    @classmethod
    def from_dict(cls, args: dict):
        from mccode_antlr.reader.registry import SerializableRegistry as SR
        from mccode_antlr.instr.instance import make_independent
        popt = 'name', 'source'
        tpreq = 'included', 'flags',
        tmtype = {'parameters': InstrumentParameter, 'metadata': MetaData,
                 'instances': DepInstance, 'user': RawC, 'declare': RawC,
                  'initialize': RawC, 'save': RawC, 'final': RawC, 'registries': SR
                 }
        dtype = {'components': Comp, 'groups': DependentGroup}

        data = {}
        data.update({k: args[k] for k in popt if k in args})
        data.update({k: tuple(a for a in args[k]) for k in tpreq})
        data.update({k: tuple(t.from_dict(a) for a in args[k]) for k, t in tmtype.items()})
        data.update({k: {n: t.from_dict(v) for n, v in args[k].items()} for k, t in dtype.items()})

        instances = data.pop('instances')
        components = data.pop('components')
        data['components'] = make_independent(instances, components)
        data['groups'] = {k: v.make_independent(data['components']) for k, v in data['groups'].items()}
        return cls(**data)

    def to_dict(self):
        from msgspec.structs import fields
        from mccode_antlr.reader.registry import SerializableRegistry as SR
        data = {k.name: getattr(self, k.name) for k in fields(self)}
        instances = tuple(DepInstance.from_independent(inst) for inst in self.components)
        components = {inst.type.name: inst.type for inst in self.components}

        data['registries'] = [SR.from_registry(r) for r in self.registries]
        data['instances'] = instances
        data['components'] = components
        data['groups'] = {k: DependentGroup.from_independent(v) for k, v in self.groups.items()}
        return data

    def __eq__(self, other):
        if not isinstance(other, Instr):
            return NotImplemented
        from msgspec.structs import fields
        for name in [f.name for f in fields(self)]:
            if getattr(self, name) != getattr(other, name):
                return False
        return True

    def to_file(self, output=None, wrapper=None):
        if output is None:
            output = StringIO()
        if wrapper is None:
            from mccode_antlr.common import TextWrapper
            wrapper = TextWrapper(width=120)
        print(wrapper.start_block_comment(f'Instrument {self.name}'), file=output)
        print(wrapper.line('Instrument:', [self.name or 'None']), file=output)
        print(wrapper.line('Source:', [self.source or 'None']), file=output)
        print(wrapper.line('Contains:', [f'"%include {include}"' for include in self.included]), file=output)
        print(wrapper.line('Registries:', [registry.name for registry in self.registries]), file=output)
        for registry in self.registries:
            registry.to_file(output=output, wrapper=wrapper)
        print(wrapper.end_block_comment(), file=output)

        instr_parameters = wrapper.hide(', '.join(p.to_string(wrapper=wrapper) for p in self.parameters))
        first_line = wrapper.line('DEFINE INSTRUMENT', [f'{self.name}({instr_parameters})'])
        print(first_line, file=output)

        for metadata in self.metadata:
            metadata.to_file(output=output, wrapper=wrapper)
        if self.flags:
            print(wrapper.quoted_line('DEPENDENCY ', list(self.flags)), file=output)

        if self.declare:
            print(wrapper.block('DECLARE', _join_raw_tuple(self.declare)), file=output)
        if self.user:
            print(wrapper.block('USERVARS', _join_raw_tuple(self.user)), file=output)
        if self.initialize:
            print(wrapper.block('INITIALIZE', _join_raw_tuple(self.initialize)), file=output)

        print(wrapper.start_list('TRACE'), file=output)
        for instance in self.components:
            print(wrapper.start_list_item(), file=output)
            instance.to_file(output, wrapper)
            print(wrapper.end_list_item(), file=output)
        if self.save:
            print(wrapper.block('SAVE', _join_raw_tuple(self.save)), file=output)
        if self.final:
            print(wrapper.block('FINALLY', _join_raw_tuple(self.final)), file=output)
        print(wrapper.end_list('END'), file=output)

    def to_string(self, wrapper):
        from io import StringIO
        output = StringIO()
        self.to_file(output, wrapper)
        return output.getvalue()

    def __str__(self):
        from mccode_antlr.common import TextWrapper
        return self.to_string(TextWrapper())

    def _my_repr_html_(self):
        from mccode_antlr.common import HTMLWrapper
        wrapper = HTMLWrapper(hider='hider', hidden='hidden')
        output = StringIO()
        self.to_file(output=output, wrapper=wrapper)
        body = output.getvalue()
        style = """
        <style> 
        .hider {cursor: pointer; user-select: none;}
        .hider::before {content: "...";}
        .hidden-before::before {display: none;}
        .hidden {display: none;}
        .active {display: block;}
        </style>
        """
        script = """
        <script>
        var toggler = document.getElementsByClassName("hider");
        var i;
        for (i = 0; i < toggler.length; i++) {
            toggler[i].addEventListener("click", function() {
                var id = this.getAttribute('data-id');
                this.parentElement.querySelector(`.hidden[id=${id}]`).classList.toggle("active");
                this.classList.toggle("hidden-before");
            });
        }
        </script>
        """
        html = f'<html><head><title>{self.name}</title>{style}</head><body>{body}{script}</body></html>'
        return html

    def add_component(self, a: Instance):
        if any(x.name == a.name for x in self.components):
            raise RuntimeError(f"A component instance named {a.name} is already present in the instrument")
        self.components += (a,)

    def add_parameter(self, a: InstrumentParameter, ignore_repeated=False):
        if not parameter_name_present(self.parameters, a.name):
            self.parameters += (a,)
        elif not ignore_repeated:
            raise RuntimeError(f"An instrument parameter named {a.name} is already present in the instrument")

    def get_parameter(self, name, default=None):
        if parameter_name_present(self.parameters, name):
            for parameter in self.parameters:
                if name == parameter.name:
                    return parameter
        return default

    def has_parameter(self, name):
        return parameter_name_present(self.parameters, name)

    def last_component(self, count: int = 1, removable_ok: bool = True):
        if len(self.components) < count:
            raise RuntimeError(f"Only {len(self.components)} components defined -- can not go back {count}.")
        if removable_ok:
            return self.components[-count]
        fixed = [comp for comp in self.components if not comp.removable]
        if len(fixed) < count:
            for comp in self.components:
                logger.info(f'{comp.name}')
            raise RuntimeError(f"Only {len(fixed)} fixed components defined -- can not go back {count}.")
        return fixed[-count]

    def get_component(self, name: str):
        if name == 'PREVIOUS':
            return self.components[-1]
        for comp in self.components:
            if comp.name == name:
                return comp
        raise RuntimeError(f"No component instance named {name} defined.")

    def has_component_named(self, name: str):
        return any(comp.name == name for comp in self.components)

    def get_component_names_by_category(self, category: str):
        """Find all component instance names for a given category.

        Note:
            The category of an instance is determined by its type, and is either
            - set inside the .comp file by a 'CATEGORY <category>' directive, or
            - *guessed* by the reader based on the path to the .comp file.
            The second behaviour is to match McStasScript/McCode-3, which does not work for user-defined components.
        """
        return [inst.name for inst in self.components if category in inst.type.category]

    def add_included(self, name: str):
        self.included += (name,)

    def DEPENDENCY(self, *strings):
        self.flags += strings

    def USERVARS(self, *blocks):
        self.user += blocks_to_raw_c(*blocks)

    def DECLARE(self, *blocks):
        self.declare += blocks_to_raw_c(*blocks)

    def INITIALIZE(self, *blocks):
        self.initialize += blocks_to_raw_c(*blocks)

    def SAVE(self, *blocks):
        self.save += blocks_to_raw_c(*blocks)

    def FINALLY(self, *blocks):
        self.final += blocks_to_raw_c(*blocks)

    def add_metadata(self, m: MetaData):
        if any([x.name == m.name for x in self.metadata]):
            self.metadata = tuple([x for x in self.metadata if x.name != m.name])
        self.metadata += (m,)

    def determine_groups(self):
        for id, inst in enumerate(self.components):
            if inst.group:
                if inst.group not in self.groups:
                    self.groups[inst.group] = Group(inst.group, len(self.groups))
                self.groups[inst.group].add(id, inst)

    def component_types(self):
        # # If component order is unimportant, we can use a set:
        # return set(inst.type for inst in self.components)
        # For comparison with the C code generator, we must keep the order of component definitions
        return list(dict.fromkeys([inst.type for inst in self.components]))

    def collect_metadata(self):
        """Component definitions and instances can define metadata too, collect it all together here"""
        # Metadata defined in an instance overrides that defined in a component.
        # Metadata defined for an instrument is added to the collected list
        return tuple(m for inst in self.components for m in inst.collect_metadata()) + self.metadata

    def _getpath(self, filename: str):
        from pathlib import Path
        for registry in self.registries:
            if registry.known(filename):
                return registry.path(filename).absolute().resolve()
        return Path()

    def _replace_env_getpath_cmd(self, flags: str):
        """Replace CMD, ENV, and GETPATH directives from a flag string"""

        # Mimics McCode-3/tools/Python/mccodelib/cflags.py:evaluate_dependency_str
        #
        def getpath(chars):
            return self._getpath(chars).as_posix()

        def eval_cmd(chars):
            from mccode_antlr.utils import run_prog_message_output
            from shlex import split
            message, output = run_prog_message_output(split(chars))
            if message:
                raise RuntimeError(f"Calling {chars} resulted in error {message}")
            output = [line.strip() for line in output.splitlines() if line.strip()]
            if len(output) > 1:
                raise RuntimeError(f"Calling {chars} produced more than one line of output")
            return output[0] if output else ''

        def eval_env(chars):
            from os import environ
            return environ.get(chars, '')

        def replace(chars, start, replacer):
            if start not in chars:
                return chars
            before, after = chars.split(start, 1)
            if '(' != after[0]:
                raise ValueError(f'Missing opening parenthesis in dependency string after {start}')
            if ')' not in after:
                raise ValueError(f'Missing closing parenthesis in dependency string after {start}')
            dep, after = after[1:].split(')', 1)
            if start in dep:
                raise ValueError(f'Nested {start} in dependency string')
            return before + replacer(dep) + replace(after, start, replacer)

        for key, worker in zip(['ENV', 'GETPATH', 'CMD'], [eval_env, getpath, eval_cmd]):
            flags = replace(flags, key, worker)

        return flags

    def _replace_keywords(self, flag):
        from mccode_antlr.config import config
        from mccode_antlr.config.fallback import regex_sanitized_config_fallback
        from re import sub, findall
        if '@NEXUSFLAGS@' in flag:
            flag = sub(r'@NEXUSFLAGS@', config['flags']['nexus'].as_str_expanded(), flag)
        if '@MCCODE_LIB@' in flag:
            print(f'The instrument {self.name} uses @MCCODE_LIB@ dependencies which no longer work.')
            print('Expect problems at compilation.')
            flag = sub('@MCCODE_LIB@', '.', flag)
        general_re = r'@(\w+)@'
        for replace in findall(general_re, flag):
            # Is this replacement something like XXXFLAGS?
            if replace.lower().endswith('flags'):
                replacement = regex_sanitized_config_fallback(config['flags'], replace.lower()[:-5])
                flag = sub(f'@{replace}@', replacement, flag)
            else:
                logger.warning(f'Unknown keyword @{replace}@ in dependency string')
        return flag

    @property
    def unique_flags(self) -> set[str]:
        # Each 'flag' in self.flags is from a single instrument component DEPENDENCY,
        # and might contain duplicates: If we accept that white space differences
        # matter, we can deduplicate the strings 'easily'
        uf = set(self.flags)
        if any(inst.cpu for inst in self.components):
            uf.add('-DFUNNEL')
        return uf

    def decoded_flags(self) -> list[str]:
        # The dependency strings are allowed to contain any of
        #       '@NEXUSFLAGS@', @MCCODE_LIB@, CMD(...), ENV(...), GETPATH(...)
        # each of which should be replaced by ... something. Start by replacing the 'static' (old-style) keywords
        replaced_flags = [self._replace_keywords(flag) for flag in self.unique_flags]
        # Then use the above decoder method to replace any instances of CMD, ENV, or GETPATH
        return [self._replace_env_getpath_cmd(flag) for flag in replaced_flags]

    def copy(self, first=0, last=-1):
        """Return a copy of this instrument, optionally with only a subset of components"""
        from copy import deepcopy
        copy = Instr(self.name, self.source)
        copy.parameters = tuple(x for x in self.parameters)
        copy.metadata = tuple(x.copy() for x in self.metadata)
        if last < 0:
            last += 1 + len(self.components)
        copy.components = tuple(x.copy() for x in self.components[first:last])
        copy.included = tuple(x for x in self.included)
        copy.user = tuple(x.copy() for x in self.user)
        copy.declare = tuple(x.copy() for x in self.declare)
        copy.initialize = tuple(x.copy() for x in self.initialize)
        copy.save = tuple(x.copy() for x in self.save)
        copy.final = tuple(x.copy() for x in self.final)
        copy.groups = {k: v.copy() for k, v in self.groups.items()}
        copy.flags = tuple(x for x in self.flags)
        copy.registries = tuple(x for x in self.registries)
        return copy

    def split(self, at, remove_unused_parameters=False):
        """Produces two instruments, both containing the indicated component

        Parameters:
        -----------
        after: Union[Instance, str]
            A component instance or the _name_ of a component instance at which to split the instrument.
            The instance or one with a matching name _must_ be in the instrument, and should probably be an Arm.
        remove_unused_parameters: bool
            If True, any Instrument parameters which do not appear in instance definitions or code blocks is not
            included in the output instruments

        Return:
        -------
        tuple[Instr, Instr]
            The first Instr has components up to and including the split-point.
            The second Instr has components starting from the split-point.
        """
        if isinstance(at, Instance):
            index = self.components.index(at)
        elif isinstance(at, str):
            index = [i for i, x in enumerate(self.components) if x.name == at]
            if len(index) != 1:
                raise RuntimeError(f'Can only split an instrument after a single component, "{at}" matches {index}')
            index = index[0]
        else:
            raise RuntimeError('Can only split an instrument after a component or component name')
        first = self.copy(last=index + 1)
        first.name = self.name + '_first'
        if first.check_instrument_parameters(remove=remove_unused_parameters) and not remove_unused_parameters:
            logger.warning(f'Instrument {first.name} has unused instrument parameters')

        second = self.copy(first=index)
        second.name = self.name + '_second'
        # remove any dangling component references and re-reference into the new instrument's components:
        for instance in second.components:
            at_rel = instance.at_relative[1]
            rot_rel = instance.rotate_relative[1]
            if isinstance(at_rel, Instance):
                if second.has_component_named(at_rel.name):
                    instance.at_relative = instance.at_relative[0], second.get_component(at_rel.name)
                else:
                    instance.at_relative = instance.orientation.position(), None
            if isinstance(rot_rel, Instance):
                if second.has_component_named(rot_rel.name):
                    instance.rotate_relative = instance.rotate_relative[0], second.get_component(rot_rel.name)
                else:
                    instance.rotate_relative = instance.orientation.angles(), None
        if second.check_instrument_parameters(remove=remove_unused_parameters) and not remove_unused_parameters:
            logger.info(f'Instrument {second.name} has unused instrument parameters')

        return first, second

    def make_instance(self, name, component, at_relative=None, rotate_relative=None, orientation=None,
                      parameters=None, group=None, removable=False):
        if parameters is None:
            parameters = tuple()
        if any(x.name == name for x in self.components):
            raise RuntimeError(f"An instance named {name} is already present in the instrument")
        if isinstance(component, str):
            from ..reader import Reader
            reader = Reader(registries=list(self.registries))
            component = reader.get_component(component)
            self.flags += tuple(reader.c_flags)
        self.components += (Instance(name, component, at_relative, rotate_relative, orientation,
                                     parameters, group, removable),)

    def mcpl_split(self,
                   after,
                   filename=None,
                   output_component=None,
                   output_parameters=None,
                   input_component=None,
                   input_parameters=None,
                   remove_unused_parameters=False
                   ):
        from ..common import ComponentParameter
        from ..common import Expr, Value, ObjectType
        from .orientation import Vector, Angles
        if filename is None:
            filename = self.name + '.mcpl'
        if filename[0] != '"' or filename[-1] != '"':
            filename = '"' + filename + '"'

        filename_parameter = ComponentParameter('filename', Expr(Value('mcpl_filename', _object=ObjectType.parameter)))
        first, second = self.split(after, remove_unused_parameters=remove_unused_parameters)
        mcpl_filename = InstrumentParameter.parse(f'string mcpl_filename = {filename}')
        first.add_parameter(mcpl_filename)
        second.add_parameter(mcpl_filename)

        fc = first.components[-1]
        if fc.type.name != 'Arm':
            logger.info(f'Component {after} is a {fc.type.name} instead of an Arm -- using MCPL file may cause problems')

        if output_component is None:
            output_component = 'MCPL_output'
        if output_parameters is None:
            output_parameters = (filename_parameter,)
        elif not any(p.name == 'filename' for p in output_parameters):
            output_parameters = (filename_parameter,) + output_parameters
        # remove the last component, since we're going to re-use its name:
        first.components = first.components[:-1]
        # automatically adds the component at the end of the list:
        first.make_instance(fc.name, output_component, fc.at_relative, fc.rotate_relative, fc.orientation,
                            output_parameters)

        if input_component is None:
            input_component = 'MCPL_input'
        if input_parameters is None:
            input_parameters = (filename_parameter,)
        elif not any(p.name == 'filename' for p in input_parameters):
            input_parameters = (filename_parameter,) + input_parameters
        if not any(p.name == 'verbose' for p in input_parameters):
            input_parameters = (ComponentParameter('verbose', Expr.float(0)),) + input_parameters
        # # the MCPL input component _is_ the origin of its simulation, but must be placed relative to other components.
        # # so we need the *absolute* position and orientation of the removed component:
        # abs_at_rel = fc.orientation.position(), None
        # abs_rot_rel = fc.orientation.angles(), None

        # the split at component in the second instrument should have already been converted to absolute-positioning:
        sc = second.components[0]
        if sc.at_relative[1] is not None or sc.rotate_relative[1] is not None:
            logger.error("The split-at point should be positioned absolutely in the second instrument")
        # remove the first component before adding an-equal named one:
        second.components = second.components[1:]
        second.make_instance(sc.name, input_component, sc.at_relative, sc.rotate_relative, parameters=input_parameters)
        # move the newly added component to the front of the list:
        second.components = (second.components[-1],) + second.components[:-1]

        return first, second

    def parameter_used(self, name: str):
        """Check that an instrument parameter is used in the instrument"""
        for instance in self.components:
            if instance.parameter_used(name):
                return True
        for section in (self.declare, self.initialize, self.save, self.final):
            for block in section:
                # A more complex check would see if the use itself leads to a parameter being used, but
                # that would be language dependent and probably not worth the effort.
                if name in block:
                    return True
        return False

    def check_instrument_parameters(self, remove=False):
        """Check that all instrument parameters are used in the instrument, and optionally remove any that are not

        Returns
        -------
        int
            The number of unused instrument parameters
        """
        names = [p.name for p in self.parameters]
        used = [self.parameter_used(p.name) for p in self.parameters]
        if not all(used):
            logger.info(f'The following instrument parameters are not used in the instrument: '
                     f'{", ".join([n for n, u in zip(names, used) if not u])}')
            if remove:
                self.parameters = tuple(p for i, p in enumerate(self.parameters) if used[i])
                logger.info(f'Removed unused instrument parameters; {len(self.parameters)} remain')
        return len(used) - sum(used)

    def verify_instance_parameters(self):
        """Check that all instance parameters are of the expected type, and that identifiers which match
        instrument parameter names are flagged as such"""
        for instance in self.components:
            instance.verify_parameters(self.parameters)

    def check_expr(self, expr: int | float | str | Expr | Value):
        if not isinstance(expr, Expr):
            expr = Expr.best(expr)
        # check whether the expression contains any identifiers which are actually InstrumentParameters
        expr.verify_parameters([x.name for x in self.parameters])
        # We then verify that no as-of-yet undefined identifiers exist, but can't in case they're defined in
        # an initalize or share block
        return expr


def _join_raw_tuple(raw_tuple: tuple[RawC, ...]):
    return '\n'.join([str(rc) for rc in raw_tuple])

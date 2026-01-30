from __future__ import annotations

from loguru import logger
from typing import Optional
from msgspec import Struct, field
from typing import TypeVar, Union, Optional
from ..comp import Comp
from ..common import Expr, Value, Mode
from ..common import InstrumentParameter, ComponentParameter, MetaData, parameter_name_present, RawC, blocks_to_raw_c
from .orientation import Orient, Vector, Angles
from .jump import Jump

InstanceReference = TypeVar('InstanceReference', bound='Instance')
VectorReference = tuple[Vector, Optional[InstanceReference]]
AnglesReference = tuple[Angles, Optional[InstanceReference]]

# @dataclass
class Instance(Struct):
    """Intermediate representation of a McCode component instance

    Read from a .instr file TRACE section, using one or more .comp sources
    For output to a runtime source file
    """
    name: str
    type: Comp
    at_relative: VectorReference
    rotate_relative: AnglesReference
    orientation: Optional[Orient] = None
    parameters: tuple[ComponentParameter, ...] = field(default_factory=tuple)
    removable: bool = False
    cpu: bool = False
    split: Optional[Expr] = None
    when: Optional[Expr] = None
    group: Optional[str] = None
    extend: tuple[RawC, ...] = field(default_factory=tuple)
    jump: tuple[Jump, ...] = field(default_factory=tuple)
    metadata: tuple[MetaData, ...] = field(default_factory=tuple)
    mode: Mode = Mode.normal

    def __eq__(self, other: Instance) -> bool:
        if not isinstance(other, Instance):
            return NotImplemented
        from msgspec.structs import fields
        for name in [field.name for field in fields(self)]:
            if getattr(self, name) != getattr(other, name):
                return False
        return True

    def __repr__(self):
        return f'Instance({self.name}, {self.type.name})'

    def to_file(self, output, wrapper=None, full=True):
        if self.cpu:
            print(wrapper.line('CPU', []), file=output, end='')

        instance_parameters = wrapper.hide(', '.join(p.to_string(wrapper=wrapper) for p in self.parameters))
        line = wrapper.bold('COMPONENT') + f' {self.name} = {self.type.name}({instance_parameters}) '

        if self.when is not None:
            line += wrapper.bold('WHEN') + ' ' + wrapper.escape(str(self.when)) + ' '

        def rf(which, x, required=False):
            absolute = wrapper.bold('ABSOLUTE')
            relative = wrapper.bold('RELATIVE')
            return _triplet_ref_str(wrapper.bold(which), x, absolute, relative, required)

        # The "AT ..." statement is required even when it is "AT (0, 0, 0) ABSOLUTE"
        line += rf('AT', self.at_relative, required=True) + ' '
        line += rf('ROTATED', self.rotate_relative) + wrapper.br()
        print(line, file=output, end='')

        if not full:
            return  # Skip the rest of the output

        if self.group is not None:
            print(wrapper.line('GROUP', [self.group]), file=output)
        if self.extend:
            extends = '\n'.join(str(ext) for ext in self.extend)
            print(wrapper.block('EXTEND', extends), file=output)
        for jump in self.jump:
            jump.to_file(output, wrapper)
        for metadata in self.metadata:
            metadata.to_file(output, wrapper)

    def to_string(self, wrapper, full=True):
        from io import StringIO
        output = StringIO()
        self.to_file(output, wrapper=wrapper, full=full)
        return output.getvalue()

    def __str__(self):
        from mccode_antlr.common import TextWrapper
        return self.to_string(TextWrapper())

    def partial_str(self):
        from mccode_antlr.common import TextWrapper
        return self.to_string(TextWrapper(), full=False)

    @classmethod
    def from_instance(cls, name: str, ref: InstanceReference, at: VectorReference, rotate: AnglesReference):
        # from copy import deepcopy
        # copy each of: parameters, extend, group, jump, when, metadata
        return cls(name, ref.type, at, rotate,
                   parameters=tuple([par for par in ref.parameters]),
                   when=ref.when, group=ref.group,
                   extend=tuple([ext for ext in ref.extend]),
                   jump=tuple([jmp for jmp in ref.jump]),
                   metadata=tuple([md for md in ref.metadata]),
                   mode=ref.mode)

    def __post_init__(self):
        # TODO: Enhancement idea. Instead of building independent orientation chains
        #       for each instance, as is done in the non-minimal Mode. The Instr
        #       could hold a directed graph defining the chains, with nodes as instances
        #       or instance names, and edges as the the chained operations linking
        #       the dependency. This should make it easier to re-use relative
        #       orientation information in other tools, e.g., moreniius.
        if self.mode != Mode.minimal and self.orientation is None:
            ar, rr = self.at_relative, self.rotate_relative
            if not isinstance(ar[0], Vector) or not isinstance(rr[0], Angles):
                logger.warning(f'Expected {ar=} and {rr=} to be Vector and Angles respectively')
            if rr[1] is None and ar[1] is not None:
                logger.warning(f'Expected rotation reference to be specified when at reference is specified')
            at = ar[0] if isinstance(ar[0], Vector) else Vector(*ar[0])
            an, ar = (ar[1].name, ar[1].orientation) if ar[1] else ("ABSOLUTE", None)
            rt = rr[0] if isinstance(rr[0], Angles) else Angles(*rr[0])
            rn, rr = (rr[1].name, rr[1].orientation) if rr[1] else (an, ar)
            self.orientation = Orient.from_dependent_orientations(ar, at, rr, rt)
        # check if the defining component is marked noacc, in which case this _is_ cpu only
        if not self.type.acc:
            self.cpu = True

    def set_parameter(self, name: str, value, overwrite=False, allow_repeated=True):
        if not parameter_name_present(self.type.define, name) and not parameter_name_present(self.type.setting, name):
            raise RuntimeError(f"Unknown parameter {name} for component type {self.type.name}")
        if parameter_name_present(self.parameters, name):
            if overwrite:
                self.parameters = tuple(x for x in self.parameters if name != x.name)
            elif allow_repeated:
                par = [p for p in self.parameters if name == p.name][0]
                logger.info(f'Multiple definitions of {name} in component instance {self.name}')
                if par.value != value:
                    logger.info(f'  first-encountered value {par.value} retained')
                    logger.info(f'  newly-encountered value {value} dropped')
            else:
                raise RuntimeError(f"Multiple definitions of {name} in component instance {self.name}")
        p = self.type.get_parameter(name)

        if not p.compatible_value(value):
            logger.debug(f'{p=}, {name=}, {value=}')
            raise RuntimeError(f"Provided value for parameter {name} is not compatible with {self.type.name}")

        if p.value.is_vector and isinstance(value, str):
            # FIXME can this be more general? Do we _need_ to treat vectors differently?
            value = Expr(Value(value, p.value.data_type, _shape=p.value.shape_type))
        elif isinstance(value, str):
            value = Expr.parse(value)
        elif not isinstance(value, Expr):
            # Copy the data_type of the component definition parameter
            # -- thus if value is a str but an int or float is expected, we will know it is an identifier
            value = Expr(Value(value, p.value.data_type))

        # 2023-09-14 This did nothing. Why was this here?
        # # is this parameter value *actually* an instrument parameter *name*
        # if value.is_id:
        #     pass
        # # If a parameter is set to an instrument parameter name, we need to keep track of that here:
        # TODO: Either add a reference to the containing instrument (and carry that around always)
        #       Or perform this check when it comes time to translate the whole instrument :/

        self.parameters += (ComponentParameter(p.name, value), )

    def verify_parameters(self, instrument_parameters: tuple[InstrumentParameter, ...]):
        """Check for instance parameters which are identifiers that match instrument parameter names,
        and flag them as parameter objects"""
        instrument_parameter_names = [x.name for x in instrument_parameters]
        for par in self.parameters:
            par.value.verify_parameters(instrument_parameter_names)

    def get_parameter(self, name: str):
        for par in self.parameters:
            if par.name == name:
                return par
        return self.type.get_parameter(name)

    def defines_parameter(self, name: str):
        """Check whether this instance has defined the named parameter"""
        return parameter_name_present(self.parameters, name)

    def set_parameters(self, **kwargs):
        for name, value in kwargs.items():
            self.set_parameter(name, value)

    def REMOVABLE(self):
        self.removable = True

    def CPU(self):
        self.cpu = True

    def SPLIT(self, count):
        if isinstance(count, str):
            count = Expr.parse(count)
        if not isinstance(count, Expr):
            raise ValueError(f'Expected provided SPLIT expression to be an Expr not a {type(count)}')
        self.split = count

    def WHEN(self, expr):
        if isinstance(expr, str):
            expr = Expr.parse(expr)
        if not isinstance(expr, Expr):
            raise ValueError(f'Expected provided WHEN expression to be an Expr not a {type(expr)}')
        if expr.is_constant:
            raise RuntimeError(f'Evaluated WHEN statement {expr} would be constant at runtime!')
        self.when = expr

    def GROUP(self, name: str):
        self.group = name

    def EXTEND(self, *blocks):
        # copy vanilla overwrite-COPY behavior, issue 85
        #
        #self.extend += blocks_to_raw_c(*blocks)
        if len(blocks):
            self.extend = blocks_to_raw_c(*blocks)

    def JUMP(self, *jumps):
        # copy vanilla overwrite-COPY behavior, issue 85
        #
        # self.jump += jumps
        if len(jumps):
            self.jump = jumps

    def add_metadata(self, m: MetaData):
        if any([x.name == m.name for x in self.metadata]):
            self.metadata = tuple([x for x in self.metadata if x.name != m.name])
        self.metadata += (m, )

    def collect_metadata(self):
        # A component declaration and instance can define metadata with the same name
        # When they do, the metadata from *the instance* should take precedence
        md = {m.name: m for m in self.type.collect_metadata()}
        md.update({m.name: m for m in self.metadata})
        return tuple(md.values())

    def copy(self):
        return Instance(self.name, self.type, self.at_relative, self.rotate_relative,
                        orientation=self.orientation, parameters=self.parameters,
                        removable=self.removable, cpu=self.cpu, split=self.split, when=self.when,
                        group=self.group, extend=self.extend, jump=self.jump, metadata=self.metadata)

    def parameter_used(self, name: str):
        if any([name in par.value for par in self.parameters]):
            return True
        if name in self.at_relative[0] or name in self.rotate_relative[0] or name in self.orientation:
            return True
        if name in (self.split or []) or name in (self.when or []):
            return True
        for block in self.extend:
            if name in block:
                return True
        for jump in self.jump:
            if name in jump:
                return True
        return False


def _triplet_ref_str(which, tr: Union[VectorReference, AnglesReference], absolute, relative, required=False):
    pos, ref = tr
    if isinstance(pos, tuple):
        pos = Vector(*pos)
    if pos.is_null() and ref is None and not required:
        return ''
    return f'{which} {pos} {absolute if ref is None else f"{relative} {ref.name}"}'


class DepInstance(Instance):
    at_relative: tuple[Vector, str]
    rotate_relative: tuple[Angles, str]
    type: str

    def __post_init__(self):
        """Only created from exising/partial instances, so don't do post-init"""
        pass

    @classmethod
    def from_independent(cls, independent: Instance):
        from msgspec.structs import fields
        to_copy = {k.name for k in fields(cls) if k.name != 'type'}
        data = {k: getattr(independent, k) for k in to_copy}
        data['type'] = independent.type.name

        def a_b(w):
            a, b = w
            return a, b.name if b is not None else None

        data['at_relative'] = a_b(independent.at_relative)
        data['rotate_relative'] = a_b(independent.rotate_relative)
        return cls(**data)

    @classmethod
    def from_dict(cls, args: dict):
        preq = 'name', 'type', 'removable', 'cpu',
        popt = 'group',
        mreq = {'mode': Mode}
        tmreq = {'parameters': ComponentParameter, 'extend': RawC, 'jump': Jump,
                 'metadata': MetaData}
        mopt = {'split': Expr, 'when': Expr, 'orientation': Orient, }
        data = {k: args[k] for k in preq}
        data.update({k: args[k] for k in popt})
        data.update({k: t(args[k]) for k, t in mreq.items()})
        data.update({k: t.from_dict(args[k]) for k, t in mopt.items() if k in args and args[k]})
        data.update({k: tuple(t.from_dict(a) for a in args[k]) for k, t in tmreq.items()})

        vector, ar_name = args['at_relative']
        angles, rr_name = args['rotate_relative']
        vectors = Vector.from_dict(vector)
        angles = Angles.from_dict(angles)
        data['at_relative'] = (vectors, ar_name)
        data['rotate_relative'] = angles, rr_name
        return cls(**data)

    def make_independent(self, components: dict[str, Comp]):
        from msgspec.structs import fields
        data = {k.name: getattr(self, k.name) for k in fields(self)}
        data['type'] = components[self.type]
        return Instance(**data)

def make_independent(dependents: tuple[DepInstance, ...], components: dict[str, Comp]):
    independents = [d.make_independent(components) for d in dependents]
    # hopefully 'orientation' was set so no check was made against the relative instances
    names = tuple(i.name for i in independents)
    for d, t in zip(dependents, independents):
        if d.at_relative[1] in names:
            t.at_relative = t.at_relative[0], next(i for i in independents if i.name == d.at_relative[1])
        if d.rotate_relative[1] in names:
            t.rotate_relative = t.rotate_relative[0], next(i for i in independents if i.name == d.rotate_relative[1])
    return tuple(independents)
"""Data structures required for representing the contents of a McCode comp file"""
from __future__ import annotations

from typing import Optional
from msgspec import Struct, field
from ..common import ComponentParameter, MetaData, parameter_name_present, RawC, blocks_to_raw_c


# Could this be replaced by a subclassed 'name' class? E.g., Slit.comp <=> class McCompSlit(McComp)?
# @dataclass
class Comp(Struct):
    """Intermediate representation of a McCode component definition

    Read from a .comp file
    For output to a runtime source file
    """
    name: Optional[str] = None           # Component *type* name, e.g. {name}.comp
    category: Optional[str] = None       # Component type catagory -- nearly free-form
    define: tuple[ComponentParameter, ...] = field(default_factory=tuple)   # C #define'ed parameters
    setting: tuple[ComponentParameter, ...] = field(default_factory=tuple)  # Formal 'setting' parameters
    output: tuple[ComponentParameter, ...] = field(default_factory=tuple)   # 'output' parameters
    metadata: tuple[MetaData, ...] = field(default_factory=tuple)           # metadata for use by simulation consumers
    dependency: Optional[str] = None     # compile-time dependency
    acc: bool = True           # False if this component *can not* work under OpenACC
    # literal strings writen into C source files
    share: tuple[RawC, ...] = field(default_factory=tuple)       # function(s) for all instances of this class
    user: tuple[RawC, ...] = field(default_factory=tuple)        # struct members for _particle
    declare: tuple[RawC, ...] = field(default_factory=tuple)     # global parameters used in component trace
    initialize: tuple[RawC, ...] = field(default_factory=tuple)  # initialization of global declare parameters
    trace: tuple[RawC, ...] = field(default_factory=tuple)       # per-particle interaction executed at TRACE time
    save: tuple[RawC, ...] = field(default_factory=tuple)        # statements executed after TRACE to save results
    final: tuple[RawC, ...] = field(default_factory=tuple)       # clean-up memory for global declare parameters
    display: tuple[RawC, ...] = field(default_factory=tuple)     # draw this component

    @classmethod
    def from_dict(cls, args: dict):
        preq = 'acc',
        popt = 'name', 'category', 'dependency'
        tmreq = {'define': ComponentParameter, 'setting': ComponentParameter,
                  'output': ComponentParameter, 'metadata': MetaData,
                  'share': RawC, 'user': RawC, 'declare': RawC, 'initialize': RawC,
                  'trace': RawC, 'save': RawC, 'final': RawC, 'display': RawC
                  }
        data = {}
        data.update({k: args[k] for k in preq})
        data.update({k: args[k] for k in popt if k in args})
        data.update(
            {k: tuple(t.from_dict(a) for a in args[k]) for k, t in tmreq.items()})
        return cls(**data)

    def __hash__(self):
        return hash(repr(self))

    # @property
    # def parameters(self):
    #     return self.define + self.setting

    def has_parameter(self, name: str):
        return parameter_name_present(self.define, name) or parameter_name_present(self.setting, name)

    def get_parameter(self, name: str, default=None):
        if parameter_name_present(self.define, name):
            return [par for par in self.define if par.name == name][0]
        if parameter_name_present(self.setting, name):
            return [par for par in self.setting if par.name == name][0]
        return default

    def compatible_parameter_value(self, name: str, value):
        return self.get_parameter(name).compatible_value(value)

    def parameter_name_used(self, parameter_type: str, name: str):
        """Verify that a new parameter name is not already in use."""
        if parameter_name_present(self.define, name):
            raise RuntimeError(f"{parameter_type} parameter {name} is already an instance parameter!")
        if parameter_name_present(self.setting, name):
            raise RuntimeError(f"{parameter_type} parameter {name} is already a setting parameter!")
        if parameter_name_present(self.output, name):
            raise RuntimeError(f"{parameter_type} parameter {name} is already an output parameter!")

    def add_define(self, a: ComponentParameter):
        self.parameter_name_used('DEFINE', a.name)
        self.define += (a, )

    def add_setting(self, a: ComponentParameter):
        self.parameter_name_used('SETTING', a.name)
        self.setting += (a, )

    def add_output(self, a: ComponentParameter):
        # TODO in McCode-3 OUTPUT PARAMETERS are parsed but unused in the code-generator.
        #      And they can apparently anyway specify the same name as SETTING (and possibly DEFINE) PARAMETERS
        #      So only ensure that the same name isn't specified twice in OUTPUT, and consider dropping entirely.
        #self.parameter_name_used('OUTPUT', a.name)
        if parameter_name_present(self.output, a.name):
            raise RuntimeError(f"OUTPUT parameter {a.name} is already an output parameter!")
        self.output += (a, )

    def no_acc(self):
        self.acc = False

    # Meta programming these block setting methods is more pain than its worth:
    def SHARE(self, *blocks):
        self.share += blocks_to_raw_c(*blocks)

    def USERVARS(self, *blocks):
        self.user += blocks_to_raw_c(*blocks)

    def DECLARE(self, *blocks):
        self.declare += blocks_to_raw_c(*blocks)

    def INITIALIZE(self, *blocks):
        self.initialize += blocks_to_raw_c(*blocks)

    def TRACE(self, *blocks):
        self.trace += blocks_to_raw_c(*blocks)

    def SAVE(self, *blocks):
        self.save += blocks_to_raw_c(*blocks)

    def FINALLY(self, *blocks):
        self.final += blocks_to_raw_c(*blocks)

    def DISPLAY(self, *blocks):
        self.display += blocks_to_raw_c(*blocks)

    def add_metadata(self, m: MetaData):
        if any([x.name == m.name for x in self.metadata]):
            self.metadata = tuple([x for x in self.metadata if x.name != m.name])
        self.metadata += (m, )

    def collect_metadata(self):
        return self.metadata

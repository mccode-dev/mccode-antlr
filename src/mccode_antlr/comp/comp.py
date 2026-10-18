"""Data structures required for representing the contents of a McCode comp file"""
from __future__ import annotations
from pathlib import Path
from typing import Optional
from msgspec import Struct, field
from ..common import ComponentParameter, MetaData, parameter_name_present, RawC, blocks_to_raw_c


# Could this be replaced by a subclassed 'name' class? E.g., Slit.comp <=> class McCompSlit(McComp)?
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
    origin: Optional[str] = None         # which registry resolved this .comp, e.g. 'local:mylib' or
                                          # 'remote:mcstas' -- provenance only, never written into .comp text
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
        popt = 'name', 'category', 'dependency', 'origin'
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

    @classmethod
    def from_source(cls,
                    reader,
                    error_listener,
                    source: str,
                    filename: str | None = None,
                    fullname: str | Path | None = None,
                    ):
        from antlr4 import InputStream
        from mccode_antlr.grammar import McComp_ErrorListener, McComp_parse
        from mccode_antlr.comp.visitor import CompVisitor
        from mccode_antlr.reader.reader import make_reader_error_listener
        stream = InputStream(source)
        tree = McComp_parse(stream, 'prog', error_listener)
        # ANTLR recovers and returns a tree even for input it could not parse, so
        # the tree is only trustworthy once the listener reports no errors.
        if hasattr(error_listener, 'raise_for_errors'):
            error_listener.raise_for_errors()
        visitor = CompVisitor(reader, filename or '<source>')
        comp = visitor.visitProg(tree)
        if comp.category is None and (filename is not None or fullname is not None):
            fullname = fullname or Path(filename)
            fullname = fullname if isinstance(fullname, Path) else Path(fullname)
            comp.category = 'UNKNOWN' if fullname.is_absolute() else fullname.parts[0]
        enrich_comp_from_mcdoc(comp, source)
        return comp

    def __hash__(self):
        return hash(self.name)

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

    def to_file(self, output=None, wrapper=None):
        from io import StringIO
        if output is None:
            output = StringIO()
        if wrapper is None:
            from mccode_antlr.common import TextWrapper
            wrapper = TextWrapper(width=120)

        def _join(raw_tuple):
            return '\n'.join(str(rc) for rc in raw_tuple)

        def _param_str(p):
            # The type and default exactly as a parameter list spells them, so that
            # reading the text back gives the same parameter
            from mccode_antlr.common.expression import DataType, ObjectType
            from mccode_antlr.common.expression.sympy_classes import UNSET_SYMPY
            v = p.value
            if v.is_str:
                # an archaic `symbol` is read as a string with an identifier default
                default = str(v)
                s = 'string ' if default in ('None', 'NULL') or default.startswith('"') else 'symbol '
            elif v.is_vector:
                s = 'int *' if v.data_type == DataType.int else 'vector '
            elif v.data_type == DataType.int:
                s = 'int '
            else:
                s = ''
            s += p.name
            if not (v.is_singular and v._exprs[0] is UNSET_SYMPY):
                value = str(v)
                if v.object_type == ObjectType.initializer_list:
                    value = '{' + value + '}'
                s += '=' + value
            return s

        def _params_str(params):
            return ', '.join(_param_str(p) for p in params)

        print(f'DEFINE COMPONENT {self.name}', file=output)
        if self.define:
            print(f'DEFINITION PARAMETERS ({_params_str(self.define)})', file=output)
        if self.setting:
            print(f'SETTING PARAMETERS ({_params_str(self.setting)})', file=output)
        if self.output:
            print(f'OUTPUT PARAMETERS ({_params_str(self.output)})', file=output)

        # The grammar fixes the order: metadata, then dependency, then NOACC
        for metadata in self.metadata:
            metadata.to_file(output=output, wrapper=wrapper)
        if self.dependency:
            print(f'DEPENDENCY "{self.dependency}"', file=output)
        if not self.acc:
            print('NOACC', file=output)

        for name, raw in (('SHARE', self.share), ('USERVARS', self.user),
                          ('DECLARE', self.declare), ('INITIALIZE', self.initialize),
                          ('TRACE', self.trace), ('SAVE', self.save),
                          ('FINALLY', self.final), ('MCDISPLAY', self.display)):
            if raw:
                print(wrapper.block(name, _join(raw)), file=output)

        print('END', file=output)

    def to_string(self, wrapper=None):
        from io import StringIO
        output = StringIO()
        self.to_file(output, wrapper)
        return output.getvalue()

    def __str__(self):
        return self.to_string()


# ---------------------------------------------------------------------------
# McDoc enrichment helpers
# ---------------------------------------------------------------------------

def enrich_comp_from_mcdoc(comp: Comp, source: str) -> None:
    """Enrich *comp*'s parameters in-place with McDoc unit/description metadata."""
    from msgspec.structs import replace
    try:
        from mccode_antlr.mcdoc import parse_mcdoc
        mcdoc = parse_mcdoc(source)
    except Exception:
        return
    if not mcdoc:
        return

    def handle_one_param(param):
        if (unit_desc := mcdoc.get(param.name)) is not None:
            return replace(param, unit=unit_desc[0], description=unit_desc[1])
        return param

    def handle_param_type(params):
        return tuple(handle_one_param(param) for param in params)

    if comp.define:
        comp.define = handle_param_type(comp.define)
    if comp.setting:
        comp.setting = handle_param_type(comp.setting)
    if comp.output:
        comp.output = handle_param_type(comp.output)
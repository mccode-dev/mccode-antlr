from __future__ import annotations
from pathlib import Path
from loguru import logger
# from dataclasses import dataclass, field
from msgspec import Struct, field

from .registry import Registry, registries_match, registry_from_specification
from ..comp import Comp
from ..common import Mode

from mccode_antlr import Flavor

def make_reader_error_listener(super_class, filetype, name, source, pre=5, post=2):
    class ReaderErrorListener(super_class):
        def __init__(self):
            self.filetype = filetype
            self.name = name
            self.source = source
            self.pre = pre
            self.post = post

        def syntaxError(self, recognizer, offendingSymbol, *args, **kwargs):
            if len(args) == 4 and isinstance(args[3], str):
                # The 'speedy-antlr' syntax
                char_index, line, column, msg = args
            else:
                # the antlr4 (4.13.0) syntax
                line, column, msg, e = args
            logger.error(f'Syntax error in parsing {self.filetype} {self.name} at {line},{column}')
            lines = self.source.split('\n')
            pre_lines = lines[line-self.pre:line]
            post_lines = lines[line:line+self.post]
            for line in pre_lines:
                logger.info(line)
            logger.error('~'*column + '^ ' + msg)
            for line in post_lines:
                logger.info(line)

    return ReaderErrorListener()


# @dataclass
class Reader(Struct):
    registries: list[Registry] = field(default_factory=list)
    components: dict[str, Comp] = field(default_factory=dict)
    c_flags: list[str] = field(default_factory=list)
    flavor: Flavor | None = None

    def __post_init__(self):
        from .registry import ordered_registries, default_registries
        if self.flavor is None:
            self.flavor = Flavor.MCSTAS
        if len(self.registries) == 0:
            self.registries = default_registries(self.flavor)
        self.registries = list(ordered_registries(self.registries))

    def prepend_registry(self, reg: Registry):
        self.registries[:0] = [reg, ]

    def append_registry(self, reg: Registry):
        self.registries.append(reg)

    def handle_search_keyword(self, spec: str):
        if not any(registries_match(reg, spec) for reg in self.registries):
            reg = registry_from_specification(spec)
            if reg is not None:
                self.prepend_registry(reg)
            else:
                raise RuntimeError(f"Registry specification {spec} did not specify a valid registry!")

    def add_c_flags(self, flags):
        self.c_flags.append(flags)

    def locate(self, name: str, which: str = None, ext: str = None, strict: bool = False):
        registries = self.registries if which is None else [x for x in self.registries if x.name in which]
        for reg in registries:
            if reg.known(name, ext, strict=strict):
                return reg.path(name, ext)
        names = [reg.name for reg in registries]
        msg = "registry " + names[0] if len(names) == 1 else 'registries: ' + ','.join(names)
        raise RuntimeError(f'{name} not found in {msg}')

    def contents(self, name: str, which: str = None, ext: str = None, strict: bool = False):
        registries = self.registries if which is None else [x for x in self.registries
                                                            if x.name in which]
        for reg in registries:
            if reg.known(name, ext, strict=strict):
                return reg.contents(name, ext)
        names = [reg.name for reg in registries]
        msg = "registry " + names[0] if len(names) == 1 else 'registries: ' + ','.join(
            names)
        raise RuntimeError(f'{name} not found in {msg}')

    def fullname(self, name: str, which: str = None, ext: str=None, strict: bool = False):
        registries = self.registries if which is None else [x for x in self.registries if x.name in which]
        for reg in registries:
            if reg.known(name, ext, strict=strict):
                return reg.fullname(name, ext)
        names = [reg.name for reg in registries]
        msg = "registry " + names[0] if len(names) == 1 else 'registries: ' + ','.join(names)
        raise RuntimeError(f'{name} not found in {msg}')

    def known(self, name: str, which: str = None, strict: bool = False):
        registries = self.registries if which is None else [x for x in self.registries if x.name in which]
        return any([reg.known(name, strict=strict) for reg in registries])

    def unique(self, name: str, which: str = None):
        registries = self.registries if which is None else [x for x in self.registries if x.name in which]
        return sum([1 for reg in registries if reg.unique(name)]) == 1

    def contain(self, name: str, which: str = None, strict: bool = False):
        registries = self.registries if which is None else [x for x in self.registries if x.name in which]
        return [reg.name for reg in registries if reg.known(name, strict=strict)]

    def stream(self, name: str, which: str = None, strict: bool = False):
        from antlr4 import InputStream
        return InputStream(self.contents(name, which=which, strict=strict))

    def add_component(self, name: str, current_instance_name=None):
        if name in self.components:
            raise RuntimeError("The named component is already known.")
        from antlr4 import InputStream
        from ..grammar import McComp_ErrorListener, McComp_parse
        from ..comp import CompVisitor
        source = self.contents(name, ext='.comp', strict=True)
        filename = str(self.locate(name, ext='.comp', strict=True))

        stream = InputStream(source)
        error_listener = make_reader_error_listener(McComp_ErrorListener, 'Component', name, source)
        tree = McComp_parse(stream, 'prog', error_listener)

        visitor = CompVisitor(self, filename, instance_name=current_instance_name)  # The visitor needs to be able to call *this* method
        res = visitor.visitProg(tree)
        if not isinstance(res, Comp):
            raise RuntimeError(f'Parsing component file {filename} did not produce a component object!')
        if res.category is None:
            # guess the component category from the registered filename (not fully resolved path)
            fullname = self.fullname(name, ext='.comp', strict=True)
            fullname = fullname if isinstance(fullname, Path) else Path(fullname)
            # if fullname is an absolute path, it comes from a local repository -- so we don't know what to do
            res.category = 'UNKNOWN' if fullname.is_absolute() else fullname.parts[0]
        self.components[name] = res

    def get_component(self, name: str, current_instance_name=None):
        if name not in self.components:
            self.add_component(name, current_instance_name=current_instance_name)
        return self.components[name]

    def get_instrument(self, name: str | None | Path, destination=None, mode: Mode | None = None):
        """Load and parse an instr Instrument definition file

        In McCode3 fashion, the instrument file *should* be in the current working directory.
        In new-fashion, the registry/registries will be checked if it is not.
        """
        from antlr4 import InputStream
        from ..grammar import McInstr_parse, McInstr_ErrorListener
        from ..instr import InstrVisitor, Instr
        path = name if isinstance(name, Path) else Path(name)
        if path.suffix != '.instr':
            path = path.with_suffix(f'{path.suffix}.instr')
        if path.exists() and path.is_file():
            source = path.read_text()
        else:
            path = self.locate(path.name)  # include the .instr for the search
            source = self.contents(path.name)

        if not path.resolve().exists():
            filename = name
        else:
            filename = path.resolve().as_posix()

        stream = InputStream(source)
        error_listener = make_reader_error_listener(
            McInstr_ErrorListener, 'Instrument', name, source
        )
        tree = McInstr_parse(stream, 'prog', error_listener)

        visitor = InstrVisitor(self, filename, destination=destination, mode=mode)
        res = visitor.visitProg(tree)
        if not isinstance(res, Instr):
            raise RuntimeError(f'Parsing instrument file {filename} did not produce an Instr object')
        res.source = filename
        res.flags = tuple(self.c_flags)
        res.registries = tuple(self.registries)
        return res

from __future__ import annotations

from pathlib import Path
from typing import Union
from mccode_antlr import Flavor
from mccode_antlr.instr import Instr
from mccode_antlr.reader import Registry
from mccode_antlr.reader.registry import ensure_registries


def parse_mccode_instr_parameters(contents: str):
    from antlr4 import InputStream
    from mccode_antlr.grammar import McInstr_parse
    from mccode_antlr.instr import InstrParametersVisitor
    visitor = InstrParametersVisitor()
    return visitor.visitProg(McInstr_parse(InputStream(contents), 'prog'))


def parse_mccode_instr(contents: str, registries: list[Registry], source: str | None = None) -> Instr:
    from antlr4 import InputStream
    from mccode_antlr.grammar import McInstr_parse
    from mccode_antlr.instr import InstrVisitor
    from mccode_antlr.reader import Reader
    reader = Reader(registries=registries)
    visitor = InstrVisitor(reader, source or '<string>')
    instr = visitor.visitProg(McInstr_parse(InputStream(contents), 'prog'))
    instr.flags += tuple(reader.c_flags)
    instr.registries += tuple(registries)
    return instr


def parse_mcstas_instr(contents: str, registries: list[Registry] | None = None) -> Instr:
    return parse_mccode_instr(contents, ensure_registries(Flavor.MCSTAS, registries))


def parse_mcxtrace_instr(contents: str, registries: list[Registry] | None = None) -> Instr:
    return parse_mccode_instr(contents, ensure_registries(Flavor.MCXTRACE, registries))


def load_mccode_instr(filename: Union[str, Path], registries: list[Registry]) -> Instr:
    return parse_mccode_instr(Path(filename).read_text(), registries, source=str(filename))


def load_mcstas_instr(filename: Union[str, Path], registries: list[Registry] | None = None) -> Instr:
    return load_mccode_instr(filename, ensure_registries(Flavor.MCSTAS, registries))


def load_mcxtrace_instr(filename: Union[str, Path], registries: list[Registry] | None = None) -> Instr:
    return load_mccode_instr(filename, ensure_registries(Flavor.MCXTRACE, registries))

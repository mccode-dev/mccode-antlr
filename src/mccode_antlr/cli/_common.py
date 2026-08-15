"""Shared input-loading logic for CLI subcommands that accept .instr or .json."""
from __future__ import annotations

from pathlib import Path

from mccode_antlr import Flavor
from mccode_antlr.instr import Instr


def load_instr(path: Path, flavor: str, search_dir: list[Path] | None):
    if path.suffix.lower() == '.json':
        from mccode_antlr.io.json import load_json
        from mccode_antlr.reader.registry import with_local_registries
        instr = with_local_registries(load_json(path), Flavor[flavor.upper()], search_dir)
    elif path.suffix.lower() == '.instr':
        from mccode_antlr.reader import Reader, collect_local_registries
        registries = collect_local_registries(Flavor[flavor.upper()], search_dir)
        instr = Reader(registries=registries).get_instrument(path)
    else:
        raise ValueError(f"Unsupported input file type {path.suffix!r}; expected .instr or .json")
    if not isinstance(instr, Instr):
        raise RuntimeError(f'Input {path} did not resolve to an Instr object')
    return instr

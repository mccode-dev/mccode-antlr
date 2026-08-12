"""The `%include` directive: its two forms, and where in an instrument they appear.

Shared by the C translator, which resolves and splices includes at translation
time, and by :mod:`mccode_antlr.io.portable`, which has to find the same files at
*save* time without translating. Keeping one definition here is what stops the
two from drifting apart.
"""
from __future__ import annotations

import re

# %include "read_table-lib" -- no extension, so a *library*: the translator pulls
# in both {name}.h and, when embedding the runtime, {name}.c
LIBRARY_INCLUDE_RE = re.compile(r'^\s*%include\s*"(?P<libname>[^"\n\.]+)"\s*$', re.MULTILINE)
# %include "conic.h" -- a specific file, spliced in place
FILE_INCLUDE_RE = re.compile(r'^\s*%include\s*"(?P<filename>[^"\n]+)"\s*$', re.MULTILINE)


def included_names(text: str) -> tuple[list[str], list[str]]:
    """Return the (library, file) names one block of C requests, without resolving.

    Libraries are returned without an extension, exactly as written.
    """
    if not text:
        return [], []
    libraries = list(dict.fromkeys(m.group('libname') for m in LIBRARY_INCLUDE_RE.finditer(text)))
    # The library form is a strict subset of the file form, so strip it before
    # looking for specific files or every library would match twice.
    remainder = LIBRARY_INCLUDE_RE.sub('', text)
    files = list(dict.fromkeys(m.group('filename') for m in FILE_INCLUDE_RE.finditer(remainder)))
    return libraries, files


def source_blocks(instr):
    """Every block of C an instrument carries, as (owner name, source text).

    Mirrors what CTargetVisitor walks when it resolves includes: instrument-level
    blocks, then each component type's blocks, then per-instance EXTEND blocks.
    """
    for group in (instr.user, instr.declare, instr.initialize, instr.save, instr.final):
        for block in group:
            yield instr.name, block.source
    for comp in instr.component_types():
        for group in (comp.share, comp.user, comp.declare, comp.initialize,
                      comp.trace, comp.save, comp.final, comp.display):
            for block in group:
                yield comp.name, block.source
    for instance in instr.components:
        for block in instance.extend:
            yield instance.name, block.source

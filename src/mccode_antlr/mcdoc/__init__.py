"""McDoc header comment parser.

Extracts parameter metadata (unit, description) from the McDoc-formatted block
comment that appears at the top of McCode .comp and .instr source files.
"""
from __future__ import annotations

import re
from typing import Optional


# Matches a parameter entry line of the form:
#   name: [unit]  description
#   name:         description       (no unit)
#   name: description               (no unit, no brackets)
# The name must start with a letter or underscore (parameter identifiers).
_PARAM_RE = re.compile(
    r'^\s*'
    r'(?P<name>[a-zA-Z_][a-zA-Z0-9_]*)'   # parameter name
    r'\s*:\s*'                              # colon separator
    r'(?:\[(?P<unit>[^\]]*)\])?\s*'        # optional [unit]
    r'(?P<desc>.*?)\s*$'                   # description (remainder)
)

# Lines in the %P section that look like ALL-CAPS subsection headings, e.g.
#   INPUT PARAMETERS:
#   OUTPUT PARAMETERS
# are not parameter entries and should be skipped.
_HEADING_RE = re.compile(r'^[A-Z][A-Z0-9 _]*:?\s*$')


def _preprocess(source: str) -> str:
    """Extract and clean the first C block comment from *source*.

    Strips the ``/* ... */`` delimiters and the leading ``' * '`` (or bare ``'*'``)
    from each interior line.  Returns the cleaned text, or an empty string when no
    block comment is found.
    """
    m = re.search(r'/\*(.*?)\*/', source, re.DOTALL)
    if not m:
        return ''
    raw = m.group(1)
    lines: list[str] = []
    for line in raw.split('\n'):
        stripped = line.strip()
        if stripped.startswith('*'):
            stripped = stripped[1:]
            if stripped.startswith(' '):
                stripped = stripped[1:]
        lines.append(stripped)
    return '\n'.join(lines)


def parse_mcdoc(source: str) -> dict[str, tuple[Optional[str], Optional[str]]]:
    """Parse a McDoc header from *source* and return parameter metadata.

    Parameters
    ----------
    source:
        The full text of a ``.comp`` or ``.instr`` file.

    Returns
    -------
    dict mapping ``parameter_name`` → ``(unit, description)``.
    Both ``unit`` and ``description`` may be ``None`` when not present.
    """
    cleaned = _preprocess(source)
    if not cleaned:
        return {}

    from antlr4 import InputStream
    from mccode_antlr.grammar import McDoc_parse
    from .visitor import McDocExtractVisitor

    stream = InputStream(cleaned)
    tree = McDoc_parse(stream, 'mcdoc')
    visitor = McDocExtractVisitor()
    visitor.visit(tree)
    return visitor.parameters

"""Canonical McDoc header generation and validation for the mcfmt formatter.

This module is used exclusively by the `_McCompFormatter` in format.py.  It is
responsible for:

  1. Extracting existing McDoc content from a C block comment token.
  2. Validating that the %P section matches the actual parameter list.
  3. Emitting a consistently styled replacement header.

Canonical style
---------------
* 80-character ``/*...*/`` separator lines.
* ``%I`` section with ``Written by:``, ``Date:``, ``Origin:`` fields and a
  one-line short description.
* ``%D`` section for the full description.
* ``%P`` section with an ``INPUT PARAMETERS:`` (and optionally
  ``OUTPUT PARAMETERS:``) sub-heading; parameter lines aligned to a common
  column as ``name: [unit]  description``.
* ``%E`` end marker.
* Existing free text, field values, and parameter descriptions are preserved;
  parameters absent from the comp definition are dropped; newly added
  parameters are included with empty unit/description.
"""
from __future__ import annotations

from typing import Optional

_SEP_OPEN  = '/*' + '*' * 78       # /***...  (opens the block comment, 80 chars)
_SEP_CLOSE = '*' * 79 + '/'       # ***.../ (closes the block comment, 80 chars)
_TODO = 'TODO'


# ---------------------------------------------------------------------------
# Public API used by format.py
# ---------------------------------------------------------------------------

def extract_mcdoc_from_token(token_text: str) -> '_McDocData':
    """Parse the McDoc content from a raw ``/* ... */`` token string."""
    from mccode_antlr.mcdoc import parse_mcdoc_full
    data = parse_mcdoc_full(token_text)
    return _McDocData(
        info_fields=data.info_fields,
        short_desc=data.short_desc,
        desc_lines=data.desc_lines,
        parameters=data.parameters,
        link_lines=data.link_lines,
    )


def build_canonical_mcdoc(
    comp_name: str,
    existing: '_McDocData | None',
    input_params: list[str],
    output_params: list[str],
) -> str:
    """Return a canonical McDoc header comment string.

    Parameters
    ----------
    comp_name:
        The component name (from ``DEFINE COMPONENT {name}``).
    existing:
        Parsed data from the existing McDoc comment, or ``None`` if absent.
    input_params:
        Parameter names in the DEFINITION + SETTING parameter sets (in order).
    output_params:
        Parameter names in the OUTPUT parameter set.
    """
    ex = existing or _McDocData()

    lines: list[str] = [_SEP_OPEN]
    lines.append(f'*')
    lines.append(f'* Component: {comp_name}')
    lines.append(f'*')

    # %I section
    lines.append('* %I')
    lines.append('* Written by: ' + ex.info_fields.get('Written by', _TODO))
    lines.append('* Date: ' + ex.info_fields.get('Date', _TODO))
    lines.append('* Origin: ' + ex.info_fields.get('Origin', _TODO))
    # Preserve any other %I fields (e.g. "Modified by:"), but skip known keys
    # and placeholder TODO entries that may have been parsed as fields
    _KNOWN_KEYS = frozenset({'Written by', 'Date', 'Origin'})
    for key, val in ex.info_fields.items():
        if key not in _KNOWN_KEYS:
            lines.append(f'* {key}: {val}')
    lines.append('*')
    # Short description (one-liner) — first non-empty short_desc line
    short = next((s for s in ex.short_desc if s.strip()), None)
    lines.append('* ' + (short if short else '(' + _TODO + ' - add a one-line description)'))
    lines.append('*')

    # %D section
    lines.append('* %D')
    desc = [l for l in ex.desc_lines if l.strip()]
    if desc:
        for dl in desc:
            lines.append('* ' + dl)
    else:
        lines.append('* ' + _TODO + ': Add a detailed description.')
    lines.append('*')

    # %P section
    lines.append('* %P')
    if input_params:
        lines.append('* INPUT PARAMETERS:')
        lines.append('*')
        _append_param_lines(lines, input_params, ex.parameters)
        lines.append('*')
    if output_params:
        lines.append('* OUTPUT PARAMETERS:')
        lines.append('*')
        _append_param_lines(lines, output_params, ex.parameters)
        lines.append('*')

    # %L section — preserve existing links
    if ex.link_lines:
        lines.append('* %L')
        for ll in ex.link_lines:
            lines.append('* ' + ll)
        lines.append('*')

    lines.append('* %E')
    lines.append(_SEP_CLOSE)

    return '\n'.join(lines) + '\n'


def check_mcdoc_params(
    existing: '_McDocData | None',
    input_params: list[str],
    output_params: list[str],
) -> list[str]:
    """Return a list of warning strings describing mismatches.

    Returned warnings are informational only; the formatter always regenerates
    the header so they are surfaced here for potential diagnostic use.
    """
    if existing is None:
        return ['McDoc header is missing']
    warnings: list[str] = []
    all_comp = set(input_params) | set(output_params)
    all_doc = set(existing.parameters)
    for name in sorted(all_comp - all_doc):
        warnings.append(f'parameter {name!r} is not documented in the McDoc header')
    for name in sorted(all_doc - all_comp):
        warnings.append(f'McDoc documents {name!r} which is not a known parameter')
    return warnings


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

class _McDocData:
    """Holds parsed McDoc section data."""
    def __init__(self, *,
                 info_fields: dict[str, str] | None = None,
                 short_desc: list[str] | None = None,
                 desc_lines: list[str] | None = None,
                 parameters: dict | None = None,
                 link_lines: list[str] | None = None):
        self.info_fields: dict[str, str] = info_fields or {}
        self.short_desc: list[str] = short_desc or []
        self.desc_lines: list[str] = desc_lines or []
        self.parameters: dict[str, tuple[Optional[str], Optional[str]]] = parameters or {}
        self.link_lines: list[str] = link_lines or []


def _append_param_lines(
    lines: list[str],
    param_names: list[str],
    existing: dict[str, tuple[Optional[str], Optional[str]]],
) -> None:
    """Append formatted parameter lines to *lines*, aligning the unit column."""
    entries: list[tuple[str, str, str]] = []  # (name, unit_str, desc)
    for name in param_names:
        unit, desc = existing.get(name, (None, None))
        unit_str = f'[{unit}]' if unit else '[]'
        entries.append((name, unit_str, desc or ''))

    if not entries:
        return

    # Column widths for alignment
    name_w = max(len(e[0]) for e in entries)
    unit_w = max(len(e[1]) for e in entries)

    for name, unit_str, desc in entries:
        col = f'{name:<{name_w}}: {unit_str:<{unit_w}}'
        line = f'* {col}  {desc}' if desc else f'* {col}'
        lines.append(line.rstrip())

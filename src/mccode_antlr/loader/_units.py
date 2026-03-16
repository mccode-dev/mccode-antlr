"""McCode → scipp unit string conversion utilities."""
from __future__ import annotations

# Strings that appear in McCode .dat file axis labels but are not directly
# parseable by scipp.Unit().
_MCCODE_UNIT_MAP: dict[str, str] = {
    'AA': 'angstrom',
    'Å': 'angstrom',
    'AA^-1': '1/angstrom',
    'Å^-1': '1/angstrom',
    'Ang': 'angstrom',
    'Ang^-1': '1/angstrom',
    'microseconds': 'us',
    '\\gms': 'us',       # McCode internal escape sequence for µs
    'mus': 'us',
    '1': 'dimensionless',
    '': 'dimensionless',
    'a.u.': 'dimensionless',
    'arb.': 'dimensionless',
}


def parse_mccode_unit(raw: str) -> 'sc.Unit':
    """Convert a raw McCode unit string to a :class:`scipp.Unit`.

    Falls back to constructing ``sc.Unit(raw)`` directly after applying the
    :data:`_MCCODE_UNIT_MAP` translation table.  Raises ``sc.UnitError`` (a
    ``ValueError``) if the resulting string is still not a valid scipp unit.
    """
    import scipp as sc
    mapped = _MCCODE_UNIT_MAP.get(raw, raw)
    return sc.Unit(mapped)


def parse_mccode_label_unit(label_unit: str) -> tuple[str, 'sc.Unit']:
    """Parse a McCode axis label of the form ``'label [unit]'``.

    Returns ``(label_str, sc.Unit)``; if no brackets are found the whole string
    is used as the label and ``sc.Unit('dimensionless')`` is returned.
    """
    import scipp as sc
    label_unit = label_unit.strip()
    if '[' in label_unit and label_unit.endswith(']'):
        label, rest = label_unit.split('[', 1)
        raw_unit = rest.rstrip(']').strip()
        label = label.strip()
    else:
        label = label_unit
        raw_unit = ''
    try:
        unit = parse_mccode_unit(raw_unit)
    except Exception:
        unit = sc.Unit('dimensionless')
    return label, unit

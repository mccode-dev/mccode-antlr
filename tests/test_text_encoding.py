"""Text files are read and written as UTF-8, independent of the locale (issue #364).

Before Python 3.15 (PEP 686) `open()` and `Path.read_text()` default to the
locale encoding -- cp1252 on most Western-European Windows installs. McCode
sources are UTF-8, so relying on the default garbles non-ASCII text on such
systems and fails outright for some byte sequences.

The locale cannot be changed for the running interpreter, so the end-to-end
check runs a child interpreter with a non-UTF-8 locale encoding: ASCII on POSIX
systems, where any reliance on the default encoding then raises, and the ANSI
code page (cp1252 on the GitHub runners) on Windows, where it garbles the text.
"""
import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

from mccode_antlr.common.encoding import decode_source, read_source_text

COMP = """\
/* Component: Probe
* %I
* Written by: Jürgen Ångström
* %D
* Δλ ≥ 0.1 Å -- not representable in cp1252, which lacks Δ, λ and ≥.
* %P
* x: [Å] a length
*/
DEFINE COMPONENT Probe
SETTING PARAMETERS (x=1.0)
TRACE
%{
  /* Δ = 0.5 µm */
  double probe_x = x;
%}
END
"""

INSTR = """\
/* Ørsted, 20 °C */
DEFINE INSTRUMENT probe(dummy=1)
INITIALIZE
%{
  /* Ørsted, 20 °C */
%}
TRACE
COMPONENT origin = Probe(x=2) AT (0, 0, 0) ABSOLUTE
END
"""


def test_decode_source_accepts_utf8():
    assert decode_source(COMP.encode('utf-8')) == COMP


def test_decode_source_drops_byte_order_mark():
    """The McCode grammar has no token for U+FEFF, which some Windows editors prepend."""
    assert decode_source(b'\xef\xbb\xbf' + INSTR.encode('utf-8')) == INSTR


def test_decode_source_tolerates_legacy_encodings():
    """A cp1252-encoded user file is not valid UTF-8, but must still be readable."""
    text = decode_source('/* Café */'.encode('cp1252'), 'legacy.comp')
    # Windows decodes with its ANSI code page; a UTF-8 locale replaces the byte.
    assert text in ('/* Café */', '/* Caf� */')


def test_read_source_text(tmp_path):
    path = tmp_path / 'Probe.comp'
    path.write_bytes(b'\xef\xbb\xbf' + COMP.encode('utf-8'))
    assert read_source_text(path) == COMP


def test_byte_order_mark_does_not_break_parsing(tmp_path):
    from mccode_antlr.loader.loader import load_mccode_instr
    from mccode_antlr.reader.registry import LocalRegistry
    (tmp_path / 'Probe.comp').write_text(COMP, encoding='utf-8')
    (tmp_path / 'probe.instr').write_bytes(b'\xef\xbb\xbf' + INSTR.encode('utf-8'))
    instr = load_mccode_instr(tmp_path / 'probe.instr', [LocalRegistry('local', str(tmp_path))])
    assert [c.type.name for c in instr.components] == ['Probe']


CHILD = dedent("""\
    import locale, sys
    from pathlib import Path
    assert 'utf' not in locale.getpreferredencoding(False).lower(), locale.getpreferredencoding(False)
    from mccode_antlr.loader.loader import load_mccode_instr
    from mccode_antlr.reader.registry import LocalRegistry
    here = Path(sys.argv[1])
    instr = load_mccode_instr(here / 'probe.instr', [LocalRegistry('local', str(here))])
    assert 'Δ = 0.5 µm' in instr.components[0].type.trace[0].source
    instr.to_files(here / 'out')
""")


def test_non_ascii_sources_round_trip_under_a_legacy_locale(tmp_path):
    (tmp_path / 'Probe.comp').write_text(COMP, encoding='utf-8')
    (tmp_path / 'probe.instr').write_text(INSTR, encoding='utf-8')
    env = dict(os.environ, PYTHONUTF8='0')
    if sys.platform == 'win32':
        from mccode_antlr.common.encoding import _legacy_encoding
        if 'utf' in _legacy_encoding().lower():
            pytest.skip('the Windows "Use Unicode UTF-8 for worldwide language support" option is enabled')
    else:
        # PEP 538 coercion would otherwise turn the C locale into UTF-8
        env.update(LC_ALL='C', LANG='C', PYTHONCOERCECLOCALE='0')
    # Python source files are UTF-8 whatever the locale, but command-line arguments are not
    (tmp_path / 'child.py').write_text(CHILD, encoding='utf-8')
    result = subprocess.run([sys.executable, str(tmp_path / 'child.py'), str(tmp_path)],
                            env=env, capture_output=True, encoding='utf-8', errors='replace')
    assert result.returncode == 0, result.stderr
    assert 'Ørsted' in (tmp_path / 'out' / 'probe.instr').read_text(encoding='utf-8')

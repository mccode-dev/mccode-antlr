"""Text encoding policy for files read and written by mccode-antlr.

McCode sources (``.instr``, ``.comp``, ``.c``, ``.h``) in the upstream McCode
repository are UTF-8, and the pooch caches hold byte-for-byte copies of them.
Every text file mccode-antlr reads or writes should therefore use UTF-8
explicitly, rather than the locale-dependent default of :func:`open`, which is
e.g. cp1252 on most Western-European Windows installations (before Python 3.15,
see PEP 686).

User-provided sources are less predictable, so :func:`decode_source` accepts a
UTF-8 byte-order mark and falls back to the platform's ANSI code page (with a
warning) for files which are not valid UTF-8.
"""
from __future__ import annotations

from pathlib import Path

ENCODING = 'utf-8'


def _legacy_encoding() -> str:
    """The locale encoding that ``open()`` used before UTF-8 became the default."""
    import locale
    getencoding = getattr(locale, 'getencoding', None)  # Python >= 3.11, ignores UTF-8 mode
    return getencoding() if getencoding else locale.getpreferredencoding(False)


def decode_source(data: bytes, origin: str | Path | None = None) -> str:
    """Decode the bytes of a McCode source file.

    Tries UTF-8 (dropping a leading byte-order mark, which the McCode grammar
    does not accept), then the legacy locale encoding, and finally UTF-8 with
    undecodable bytes replaced. The fallbacks log a warning naming *origin*.
    """
    try:
        return data.decode('utf-8-sig')
    except UnicodeDecodeError as error:
        from codecs import lookup
        from loguru import logger
        name = origin or '<source>'
        legacy = _legacy_encoding()
        if lookup(legacy).name != 'utf-8':
            try:
                text = data.decode(legacy)
                logger.warning(f'{name} is not valid UTF-8 ({error}); decoded it as {legacy} instead. '
                               f'Please re-save the file with UTF-8 encoding.')
                return text
            except UnicodeDecodeError:
                pass
        logger.warning(f'{name} is not valid UTF-8 ({error}); undecodable bytes were replaced. '
                       f'Please re-save the file with UTF-8 encoding.')
        return data.decode('utf-8', errors='replace')


def read_source_text(path: str | Path) -> str:
    """Read a McCode source file, see :func:`decode_source`."""
    path = Path(path)
    return decode_source(path.read_bytes(), path)

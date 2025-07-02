from __future__ import annotations

from typing import Optional
from msgspec import Struct
from .utilities import escape_str_for_c

# @dataclass
class RawC(Struct):
    filename: Optional[str]
    line: int
    source: str
    translated: Optional[str] = None

    @classmethod
    def from_dict(cls, args: dict):
        return cls(**args)

    def __str__(self):
        return self.source

    @property
    def is_empty(self):
        # this could also check for and exclude comments
        return len(self.source.translate(str.maketrans('', '', ' \t\n'))) == 0

    @staticmethod
    def from_tuple(p: tuple):
        if isinstance(p, tuple) and len(p) == 3 and \
                isinstance(p[0], str) and isinstance(p[1], int) and isinstance(p[2], str):
            return RawC(*p)
        if isinstance(p, tuple) and len(p) == 2 and isinstance(p[0], int) and isinstance(p[1], str):
            return RawC(None, *p)
        if isinstance(p, str):
            return RawC(None, -1, p)
        raise RuntimeError(f"No conversion to RawC from\n{p}")

    def to_c(self):
        """Use the preprocessor #line directive to aid in debugging produced C source code."""
        # return f'#line {self.line} "{self.filename}"\n{self.source}'
        if self.translated is None:
            from loguru import logger
            logger.error('RawC.to_c() called before translation')
        return self.translated

    @property
    def fn(self):
        return escape_str_for_c(self.filename), self.line

    def copy(self):
        return RawC(self.filename, self.line, self.source)

    def __contains__(self, value):
        return value in self.source


def blocks_to_raw_c(*args):
    raw_c = [x if isinstance(x, RawC) else RawC.from_tuple(x) for x in args]
    # Filter out empty blocks
    output = tuple(x for x in raw_c if not x.is_empty)
    return output if len(output) else ()

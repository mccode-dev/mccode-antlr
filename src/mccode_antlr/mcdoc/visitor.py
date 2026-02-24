"""McDoc extraction visitor."""
from __future__ import annotations

import re
from typing import Optional

from antlr4 import ParseTreeVisitor

from mccode_antlr.grammar.McDocVisitor import McDocVisitor
from mccode_antlr.grammar.McDocParser import McDocParser

# See __init__.py for the regex patterns used to classify parameter lines.
from . import _PARAM_RE, _HEADING_RE


class McDocExtractVisitor(McDocVisitor):
    """Visitor that collects parameter (name, unit, description) from a McDoc tree."""

    def __init__(self):
        self.parameters: dict[str, tuple[Optional[str], Optional[str]]] = {}

    # ── Only the parameter section contains structured data we need ──────────

    def visitParamSection(self, ctx: McDocParser.ParamSectionContext):
        """Iterate the content lines of a %P section and extract parameter entries."""
        for child in ctx.getChildren():
            # Each child is either a `line` rule context or a NEWLINE token.
            if isinstance(child, McDocParser.LineContext):
                self._process_param_line(child.LINE().getText())
        return None

    # ── All other sections are ignored for parameter extraction ──────────────

    def visitInfoSection(self, ctx: McDocParser.InfoSectionContext):
        return None

    def visitDescSection(self, ctx: McDocParser.DescSectionContext):
        return None

    def visitLinkSection(self, ctx: McDocParser.LinkSectionContext):
        return None

    def visitOtherSection(self, ctx: McDocParser.OtherSectionContext):
        return None

    # ── Helper ────────────────────────────────────────────────────────────────

    def _process_param_line(self, text: str) -> None:
        """Try to extract a parameter entry from a single LINE token's text."""
        stripped = text.strip()
        if not stripped or _HEADING_RE.match(stripped):
            return
        m = _PARAM_RE.match(stripped)
        if m is None:
            return
        name = m.group('name')
        unit = m.group('unit')
        desc = m.group('desc')
        self.parameters[name] = (
            unit.strip() if unit else None,
            desc.strip() if desc else None,
        )

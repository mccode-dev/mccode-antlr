"""McDoc extraction visitor."""
from __future__ import annotations

import re
from typing import Optional

from antlr4 import ParseTreeVisitor

from mccode_antlr.grammar.McDocVisitor import McDocVisitor
from mccode_antlr.grammar.McDocParser import McDocParser

# See __init__.py for the regex patterns used to classify parameter lines.
from . import _PARAM_RE, _HEADING_RE

# Info field pattern: "Key: value" lines in the %I section
_INFO_FIELD_RE = re.compile(r'^(?P<key>[A-Za-z][A-Za-z0-9 _]*):\s*(?P<value>.*)$')


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


class McDocFullExtractor(McDocVisitor):
    """Visitor that extracts all McDoc sections for header reformatting.

    Attributes
    ----------
    info_fields : dict[str, str]
        Key-value pairs from the ``%I`` section (e.g. ``'Written by'``, ``'Date'``).
    short_desc : list[str]
        Non-field lines in the ``%I`` section (the one-liner component description).
    desc_lines : list[str]
        Lines from the ``%D`` section.
    parameters : dict[str, tuple[str|None, str|None]]
        Parameter entries from the ``%P`` section: name → (unit, description).
    link_lines : list[str]
        Lines from the ``%L`` section.
    """

    def __init__(self):
        self.info_fields: dict[str, str] = {}
        self.short_desc: list[str] = []
        self.desc_lines: list[str] = []
        self.parameters: dict[str, tuple[Optional[str], Optional[str]]] = {}
        self.link_lines: list[str] = []

    def visitInfoSection(self, ctx: McDocParser.InfoSectionContext):
        for child in ctx.getChildren():
            if isinstance(child, McDocParser.LineContext):
                text = child.LINE().getText().strip()
                m = _INFO_FIELD_RE.match(text)
                if m:
                    self.info_fields[m.group('key')] = m.group('value').strip()
                elif text:
                    self.short_desc.append(text)
        return None

    def visitDescSection(self, ctx: McDocParser.DescSectionContext):
        for child in ctx.getChildren():
            if isinstance(child, McDocParser.LineContext):
                self.desc_lines.append(child.LINE().getText())
        return None

    def visitParamSection(self, ctx: McDocParser.ParamSectionContext):
        for child in ctx.getChildren():
            if isinstance(child, McDocParser.LineContext):
                text = child.LINE().getText()
                stripped = text.strip()
                if not stripped or _HEADING_RE.match(stripped):
                    continue
                m = _PARAM_RE.match(stripped)
                if m:
                    name = m.group('name')
                    unit = m.group('unit')
                    desc = m.group('desc')
                    self.parameters[name] = (
                        unit.strip() if unit else None,
                        desc.strip() if desc else None,
                    )
        return None

    def visitLinkSection(self, ctx: McDocParser.LinkSectionContext):
        for child in ctx.getChildren():
            if isinstance(child, McDocParser.LineContext):
                self.link_lines.append(child.LINE().getText().strip())
        return None

    def visitOtherSection(self, ctx: McDocParser.OtherSectionContext):
        return None

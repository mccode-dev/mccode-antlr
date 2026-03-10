"""DisplayVisitor — walks a CParser parse tree of a MCDISPLAY body and
extracts geometry :class:`~mccode_antlr.display.primitives.Primitive` objects.

The visitor is driven by the full ANTLR C99 grammar (``CParser``/``CLexer``)
so it correctly handles:

- Plain primitive calls:  ``circle("xy", 0, 0, 0, r);``
- Math in arguments:      ``multiline(5, -xw/2, -yh/2, 0, xw/2, yh/2, 0, ...);``
- ``if``/``else`` guards: ``if (show_guide) { rectangle(...); }``
  → wrapped in :class:`~mccode_antlr.display.primitives.ConditionalBlock`
- ``for``/``while`` loops (body extracted, loop not yet unrolled)
  → wrapped in :class:`~mccode_antlr.display.primitives.LoopBlock`
- Local variable declarations resolved via the McInstr expression grammar
  (same pattern as :class:`~mccode_antlr.translators.c_listener.EvalCVisitor`).

Public entry point::

    from mccode_antlr.display.visitor import parse_display_source
    primitives = parse_display_source(raw_c_source, local_vars={})
"""
from __future__ import annotations

import re
from typing import Union

from loguru import logger

from ..grammar import CParser, CVisitor
from ..common.expression import Expr

from .primitives import (
    Primitive, Magnify, Line, DashedLine, Multiline, Circle, Rectangle,
    Box, Sphere, Cylinder, Cone, ConditionalBlock, LoopBlock,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

AnyBlock = Union[Primitive, ConditionalBlock, LoopBlock]

_DISPLAY_PRIMITIVES = frozenset({
    'magnify', 'line', 'dashed_line', 'multiline',
    'rectangle', 'box', 'circle', 'sphere',
    'cylinder', 'cone', 'polygon', 'polyhedron',
})


def _literal(ctx) -> str:
    """Return the source text spanned by this parse tree context."""
    stream = ctx.start.getInputStream()
    return stream.getText(ctx.start.start, ctx.stop.stop)


def _split_args(text: str) -> list[str]:
    """Split a comma-separated argument string, respecting nested parentheses
    and quoted strings.

    ``text`` must NOT include the outer ``(`` and ``)``.
    """
    args = []
    depth = 0
    in_string = False
    buf = []
    i = 0
    while i < len(text):
        c = text[i]
        if c == '"' and not in_string:
            in_string = True
            buf.append(c)
        elif c == '"' and in_string:
            in_string = False
            buf.append(c)
        elif not in_string:
            if c == '(':
                depth += 1
                buf.append(c)
            elif c == ')':
                depth -= 1
                buf.append(c)
            elif c == ',' and depth == 0:
                args.append(''.join(buf).strip())
                buf = []
                i += 1
                continue
            else:
                buf.append(c)
        else:
            buf.append(c)
        i += 1
    if buf:
        args.append(''.join(buf).strip())
    return [a for a in args if a]


_QUOTED_STR = re.compile(r'^["\'](.+?)["\']$')


def _parse_arg(s: str, local_vars: dict[str, Expr]) -> Expr | str:
    """Parse a single argument string into an Expr or a plain string."""
    s = s.strip()
    m = _QUOTED_STR.match(s)
    if m:
        return m.group(1)  # string literal like "xy"
    # Substitute known local variables into the expression text so that
    # Expr.parse can handle them as identifiers
    try:
        expr = Expr.parse(s)
        return expr.evaluate(local_vars) if local_vars else expr
    except Exception:
        logger.debug(f'DisplayVisitor: could not parse argument {s!r}; using Expr.id()')
        return Expr.id(s)


def _build_primitive(name: str, args: list, local_vars: dict[str, Expr]) -> Primitive | None:
    """Construct the appropriate Primitive from a parsed call."""
    # Always parse each arg through _parse_arg so quoted strings are unquoted
    # and expression strings are converted to Expr objects.
    parsed = [_parse_arg(str(a), local_vars) for a in args]

    def _e(i, default=None):
        if i < len(parsed):
            v = parsed[i]
            return Expr.best(v) if not isinstance(v, Expr) else v
        return Expr._null() if default is None else Expr.best(default)

    def _s(i, default='xy'):
        if i < len(parsed) and isinstance(parsed[i], str):
            return parsed[i]
        return default

    try:
        if name == 'magnify':
            return Magnify(what=_s(0, ''))
        if name == 'line':
            return Line(_e(0), _e(1), _e(2), _e(3), _e(4), _e(5))
        if name == 'dashed_line':
            return DashedLine(_e(0), _e(1), _e(2), _e(3), _e(4), _e(5), _e(6, 4))
        if name == 'multiline':
            count_expr = _e(0)
            try:
                count = int(float(count_expr.simplify()))
            except Exception:
                count = (len(parsed) - 1) // 3
            points = []
            for i in range(count):
                base = 1 + 3 * i
                points.append((_e(base), _e(base + 1), _e(base + 2)))
            return Multiline(points)
        if name == 'circle':
            return Circle(_s(0), _e(1), _e(2), _e(3), _e(4))
        if name == 'rectangle':
            return Rectangle(_s(0), _e(1), _e(2), _e(3), _e(4), _e(5))
        if name == 'box':
            return Box(_e(0), _e(1), _e(2), _e(3), _e(4), _e(5))
        if name == 'sphere':
            return Sphere(_e(0), _e(1), _e(2), _e(3))
        if name == 'cylinder':
            nx = _e(5, 0) if len(parsed) > 5 else Expr.float(0)
            ny = _e(6, 1) if len(parsed) > 6 else Expr.float(1)
            nz = _e(7, 0) if len(parsed) > 7 else Expr.float(0)
            return Cylinder(_e(0), _e(1), _e(2), _e(3), _e(4), nx, ny, nz)
        if name == 'cone':
            nx = _e(5, 0) if len(parsed) > 5 else Expr.float(0)
            ny = _e(6, 1) if len(parsed) > 6 else Expr.float(1)
            nz = _e(7, 0) if len(parsed) > 7 else Expr.float(0)
            return Cone(_e(0), _e(1), _e(2), _e(3), _e(4), nx, ny, nz)
    except Exception as exc:
        logger.debug(f'DisplayVisitor: error building {name}: {exc}')
    return None


# ---------------------------------------------------------------------------
# Visitor
# ---------------------------------------------------------------------------

class DisplayVisitor(CVisitor):
    """CVisitor subclass that extracts display primitives from a MCDISPLAY body."""

    def __init__(self, local_vars: dict[str, Expr] | None = None):
        self._local_vars: dict[str, Expr] = dict(local_vars or {})
        self._result: list[AnyBlock] = []

    # ------------------------------------------------------------------
    # Public result collection
    # ------------------------------------------------------------------

    @property
    def primitives(self) -> list[AnyBlock]:
        return self._result

    # ------------------------------------------------------------------
    # Top-level traversal
    # ------------------------------------------------------------------

    def visitCompilationUnit(self, ctx: CParser.CompilationUnitContext):
        self.visitChildren(ctx)
        return self._result

    def visitBlockItemList(self, ctx: CParser.BlockItemListContext):
        for item in ctx.blockItem():
            self.visit(item)
        return self._result

    def visitBlockItem(self, ctx: CParser.BlockItemContext):
        self.visitChildren(ctx)

    # ------------------------------------------------------------------
    # Statements
    # ------------------------------------------------------------------

    def visitExpressionStatement(self, ctx: CParser.ExpressionStatementContext):
        if ctx.expression() is None:
            return
        text = _literal(ctx.expression()).strip()
        self._try_extract_call(text)

    def visitSelectionStatement(self, ctx: CParser.SelectionStatementContext):
        """Handle ``if (cond) { ... }`` → ConditionalBlock."""
        if ctx.If() is None:
            # switch — ignore
            self.visitChildren(ctx)
            return

        cond_text = _literal(ctx.expression()).strip()
        try:
            cond_expr = Expr.parse(cond_text).evaluate(self._local_vars)
        except Exception:
            cond_expr = Expr.id(cond_text)

        # Collect primitives from the true branch
        body_visitor = DisplayVisitor(self._local_vars)
        body_visitor.visit(ctx.statement(0))
        body = body_visitor.primitives

        if body:
            self._result.append(ConditionalBlock(cond_expr, body))

        # Ignore else branches for geometry purposes

    def visitIterationStatement(self, ctx: CParser.IterationStatementContext):
        """Handle ``for``/``while`` loops → LoopBlock (body extracted)."""
        loop_text = _literal(ctx).strip()
        # Collect primitives from the loop body (last statement child)
        stmts = ctx.statement()
        body_visitor = DisplayVisitor(self._local_vars)
        if stmts:
            body_visitor.visit(stmts[-1])
        body = body_visitor.primitives
        if body:
            self._result.append(LoopBlock(loop_text, body))

    def visitDeclaration(self, ctx: CParser.DeclarationContext):
        """Track local variable declarations to substitute in expression args."""
        try:
            text = _literal(ctx).strip().rstrip(';')
            # Simple pattern: "type name = expr" or "type name"
            m = re.match(
                r'(?:double|float|int|long|short|char|unsigned)\s+'
                r'(\w+)\s*=\s*(.+)$',
                text,
            )
            if m:
                name, expr_text = m.group(1), m.group(2).strip()
                try:
                    val = Expr.parse(expr_text).evaluate(self._local_vars)
                    self._local_vars[name] = val
                except Exception:
                    pass
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _try_extract_call(self, text: str):
        """Check whether *text* is a display primitive call and, if so, build it."""
        m = re.match(r'^(\w+)\s*\((.*)\)\s*;?\s*$', text, re.DOTALL)
        if m is None:
            return
        name, args_text = m.group(1), m.group(2)
        if name not in _DISPLAY_PRIMITIVES:
            return
        raw_args = _split_args(args_text)
        prim = _build_primitive(name, raw_args, self._local_vars)
        if prim is not None:
            self._result.append(prim)

    # Fall-through: visit children for nodes not explicitly handled
    def visitStatement(self, ctx: CParser.StatementContext):
        self.visitChildren(ctx)

    def visitCompoundStatement(self, ctx: CParser.CompoundStatementContext):
        if ctx.blockItemList():
            self.visitBlockItemList(ctx.blockItemList())


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse_display_source(
    source: str,
    local_vars: dict[str, Expr] | None = None,
) -> list[AnyBlock]:
    """Parse the raw C source of a MCDISPLAY body into geometry primitives.

    Parameters
    ----------
    source:
        The raw C text found between ``%{`` and ``%}`` in a component
        MCDISPLAY section.
    local_vars:
        Optional pre-defined variable bindings (e.g. from the component's
        SETTING PARAMETERS made available to the display function).

    Returns
    -------
    list[Primitive | ConditionalBlock | LoopBlock]
        The extracted geometry primitives in source order.
    """
    from antlr4 import InputStream, CommonTokenStream
    from ..grammar import CLexer

    wrapped = f'void __display__(void) {{\n{source}\n}}'
    stream = InputStream(wrapped)
    lexer = CLexer(stream)
    lexer.removeErrorListeners()
    tokens = CommonTokenStream(lexer)
    parser = CParser(tokens)
    parser.removeErrorListeners()
    tree = parser.compilationUnit()
    visitor = DisplayVisitor(local_vars)
    visitor.visitCompilationUnit(tree)
    return visitor.primitives

"""
McCode DSL formatter (mcfmt) – parse-tree formatter with hidden-channel comment
preservation.

Design
------
Both BlockComment and LineComment tokens in the McCode grammar are placed on
ANTLR4's HIDDEN channel (not discarded).  After parsing, we walk the parse tree
directly (bypassing the IR path used by InstrVisitor/CompVisitor) and reconstruct
a normalised output string.

Before emitting each structural element we call ``_flush_comments_before(token)``
which drains any HIDDEN-channel tokens that precede *token* and have not yet been
written.  This gives every comment a natural resting place immediately before the
next parse-tree node that follows it in the source.

What is normalised
------------------
- All McCode DSL keywords → UPPERCASE.
- Consistent section separators (one blank line between top-level sections).
- Component ``AT``/``ROTATED`` placement on one line.
- Parameter lists formatted as ``name=value`` pairs separated by ``', '``.
- Single trailing newline; no trailing whitespace on any line.

What is intentionally NOT changed
----------------------------------
- ``%{ … %}`` C-code blocks (verbatim; leave those to ``clang-format``).
- Expression text (coordinates, parameter defaults) is reproduced verbatim from
  the token stream so no semantic information is lost.
- Comments on the HIDDEN channel are re-emitted at the position of the next
  following structural token.
"""
from __future__ import annotations

from io import StringIO
from pathlib import Path
from antlr4 import CommonTokenStream, InputStream, Token, TerminalNode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _literal_text(ctx) -> str:
    """Return the original source text that spans *ctx*."""
    start, stop = ctx.start, ctx.stop
    if start is None:
        return ''
    s = start.getInputStream()
    return s.getText(start.start, stop.stop if stop is not None else start.stop)


def _param_name(ctx) -> str:
    """Return the parameter name identifier text from a component_parameter context.

    Some alternatives (Vector, DoubleArray, IntegerArray) can contain a second
    Identifier as the default value, so ``ctx.Identifier()`` returns a list in
    those cases.  This helper always returns just the first (parameter name).
    """
    ident = ctx.Identifier()
    if isinstance(ident, list):
        return ident[0].getText()
    return ident.getText()


def _first_token(ctx):
    """Return the first Token in the subtree rooted at *ctx*."""
    if isinstance(ctx, TerminalNode):
        return ctx.symbol
    for child in (ctx.children or []):
        t = _first_token(child)
        if t is not None:
            return t
    return None


# ---------------------------------------------------------------------------
# Base formatter
# ---------------------------------------------------------------------------

class _Formatter:
    """Shared output buffer and HIDDEN-channel comment flusher."""

    def __init__(self, token_stream: CommonTokenStream,
                 clang_fmt=None):
        self._ts = token_stream
        self._ts.fill()                    # load all tokens incl. hidden channel
        self._out = StringIO()
        self._last_comment_idx = -1        # highest hidden-token index already written
        self._clang_fmt = clang_fmt        # optional callable(str)->str for C blocks

    # -- comment handling --

    def _flush_comments_before(self, token) -> None:
        """Write any HIDDEN-channel tokens that precede *token*.

        For each hidden token we check whether the lexer consumed a newline
        between that comment and whatever follows it (the next hidden token or
        *token* itself).  If so, the newline is restored so that the next
        structural element starts on a fresh line.

        ``//`` line-comments always get their newline restored (the Newline
        rule always skips it).  For ``/* … */`` block comments the decision is
        made by comparing the comment's end line against the start line of what
        follows – if those differ, a consumed newline is inferred and restored.
        Single-line inline block comments (e.g. ``f(x /* note */ + y)``) that
        sit on the same line as the next token are therefore left unchanged.
        """
        if token is None:
            return
        hidden = self._ts.getHiddenTokensToLeft(token.tokenIndex,
                                                Token.HIDDEN_CHANNEL)
        if not hidden:
            return
        eligible = [h for h in hidden if h.tokenIndex > self._last_comment_idx]
        for i, h in enumerate(eligible):
            text = h.text
            # next_line: the line the next token (hidden or visible) starts on
            next_line = eligible[i + 1].line if i + 1 < len(eligible) else token.line
            comment_end_line = h.line + text.count('\n')
            if text.startswith('//') and not text.endswith('\n'):
                # line comment: Newline rule always consumed the trailing newline
                text += '\n'
            elif (text.startswith('/*') and not text.endswith('\n')
                  and next_line > comment_end_line):
                # block comment: a newline was consumed after it
                text += '\n'
            self._out.write(text)
            self._last_comment_idx = h.tokenIndex

    def _flush_trailing_comments(self) -> None:
        """Write HIDDEN tokens that come after the last visible token."""
        for t in self._ts.tokens:
            if (t.channel == Token.HIDDEN_CHANNEL
                    and t.tokenIndex > self._last_comment_idx):
                text = t.text
                if text.startswith('//') and not text.endswith('\n'):
                    text += '\n'
                elif text.startswith('/*') and '\n' in text and not text.endswith('\n'):
                    text += '\n'
                self._out.write(text)
                self._last_comment_idx = t.tokenIndex

    # -- output helpers --

    def _w(self, text: str) -> None:
        self._out.write(text)

    def _format_unparsed_block(self, ub_text: str) -> str:
        """Format a ``%{ … %}`` token, optionally running clang-format on the
        C content between the delimiters.

        When no *clang_fmt* callable was provided at construction time the block
        is returned verbatim.  Otherwise the content (excluding ``%{``/``%}``)
        is passed to the callable and the delimiters are reconstructed around
        the result.
        """
        if self._clang_fmt is None or not (ub_text.startswith('%{')
                                           and ub_text.endswith('%}')):
            return ub_text
        content = ub_text[2:-2]
        formatted = self._clang_fmt(content)
        return '%{' + formatted + '%}'

    def _section(self, keyword: str, ctx_keyword_token, multi_block_ctx) -> None:
        """Emit a named block section, e.g. ``DECLARE %{ … %}``, with a leading
        blank line and any comments that precede the keyword."""
        self._flush_comments_before(ctx_keyword_token)
        self._w(f'\n{keyword}\n')
        self._format_multi_block(multi_block_ctx)

    # -- multi_block --

    def _format_multi_block(self, ctx) -> None:
        """Format ``multi_block: unparsed_block? ((Inherit Identifier)|(Extend unparsed_block))*``."""
        if ctx is None or ctx.children is None:
            return
        last_was_keyword = None   # 'INHERIT' or 'EXTEND' if we just saw the kw
        for child in ctx.children:
            if isinstance(child, TerminalNode):
                token = child.symbol
                self._flush_comments_before(token)
                kw = token.text.upper()
                if kw == 'INHERIT':
                    self._w('INHERIT ')
                    last_was_keyword = 'INHERIT'
                elif kw == 'EXTEND':
                    self._w('\nEXTEND\n')
                    last_was_keyword = 'EXTEND'
                else:
                    # identifier following INHERIT
                    self._w(token.text + '\n')
                    last_was_keyword = None
            else:
                # unparsed_block context
                ub_token = child.UnparsedBlock().symbol
                self._flush_comments_before(ub_token)
                self._w(self._format_unparsed_block(ub_token.text) + '\n')
                last_was_keyword = None

    # -- expressions / coordinates --

    def _expr(self, ctx) -> str:
        """Return the verbatim source text of an expression sub-tree."""
        return _literal_text(ctx)

    def _coords(self, ctx) -> str:
        """Format a ``coords`` context as ``(x, y, z)``."""
        x, y, z = [self._expr(e) for e in ctx.expr()]
        return f'({x}, {y}, {z})'

    def _reference(self, ctx) -> str:
        """Format a ``reference`` context as ``ABSOLUTE`` or ``RELATIVE ref``."""
        if ctx.Absolute() is not None and ctx.Relative() is None:
            return 'ABSOLUTE'
        ref = ctx.component_ref()
        if ref is None:
            return 'ABSOLUTE'
        if ctx.Absolute() is not None:
            return 'RELATIVE ABSOLUTE'
        return 'RELATIVE ' + _literal_text(ref)

    def result(self) -> str:
        text = self._out.getvalue()
        # Normalise: no trailing whitespace on any line, single trailing newline
        lines = [line.rstrip() for line in text.splitlines()]
        return '\n'.join(lines).rstrip('\n') + '\n'


# ---------------------------------------------------------------------------
# McInstr formatter
# ---------------------------------------------------------------------------

class _McInstrFormatter(_Formatter):

    def format(self, prog_ctx) -> str:
        self._format_instrument_definition(prog_ctx.instrument_definition())
        self._flush_trailing_comments()
        return self.result()

    def _format_instrument_definition(self, ctx) -> None:
        self._flush_comments_before(ctx.Define().symbol)

        name = ctx.Identifier().getText()
        params_str = self._format_instrument_parameters(ctx.instrument_parameters())
        self._w(f'DEFINE INSTRUMENT {name}({params_str})\n')

        if ctx.shell() is not None:
            self._format_shell(ctx.shell())
        for s in (ctx.search() or []):
            self._format_search(s)
        if ctx.instrument_metadata() is not None:
            self._format_instrument_metadata(ctx.instrument_metadata())
        if ctx.dependency() is not None:
            self._format_dependency(ctx.dependency())
        if ctx.declare() is not None:
            self._section('DECLARE', ctx.declare().Declare().symbol,
                          ctx.declare().multi_block())
        if ctx.uservars() is not None:
            self._section('USERVARS', ctx.uservars().UserVars().symbol,
                          ctx.uservars().multi_block())
        if ctx.initialise() is not None:
            self._section('INITIALIZE', ctx.initialise().Initialize().symbol,
                          ctx.initialise().multi_block())

        self._format_instrument_trace(ctx.instrument_trace())

        if ctx.save() is not None:
            self._section('SAVE', ctx.save().Save().symbol,
                          ctx.save().multi_block())
        if ctx.finally_() is not None:
            self._section('FINALLY', ctx.finally_().Finally().symbol,
                          ctx.finally_().multi_block())

        self._flush_comments_before(ctx.End().symbol)
        self._w('\nEND\n')

    # -- instrument parameters --

    def _format_instrument_parameters(self, ctx) -> str:
        params = [self._format_instrument_parameter(p)
                  for p in ctx.instrument_parameter()]
        return ', '.join(params)

    def _format_instrument_parameter(self, ctx) -> str:
        name = ctx.Identifier().getText()
        unit = ''
        if ctx.instrument_parameter_unit() is not None:
            unit = '/' + ctx.instrument_parameter_unit().StringLiteral().getText()
        cname = type(ctx).__name__
        default = ''
        if ctx.Assign() is not None:
            if cname == 'InstrumentParameterStringContext':
                if ctx.StringLiteral() is not None:
                    default = '=' + ctx.StringLiteral().getText()
                elif ctx.Null() is not None:
                    default = '=NULL'
                else:
                    default = '=0'
            else:
                expr_ctx = ctx.expr()
                if expr_ctx is not None:
                    default = '=' + self._expr(expr_ctx)
        type_prefix = ''
        if cname == 'InstrumentParameterIntegerContext':
            type_prefix = 'int '
        elif cname == 'InstrumentParameterStringContext':
            type_prefix = 'string '
        return f'{type_prefix}{name}{unit}{default}'

    # -- instrument trace --

    def _format_instrument_trace(self, ctx) -> None:
        self._flush_comments_before(ctx.Trace().symbol)
        self._w('\nTRACE\n')
        if ctx.children is None:
            return
        for child in ctx.children:
            if isinstance(child, TerminalNode):
                continue   # TRACE token already handled
            cname = type(child).__name__
            if cname == 'Component_instanceContext':
                self._format_component_instance(child)
            elif cname in ('SearchPathContext', 'SearchShellContext'):
                self._format_search(child)
            elif cname == 'Instrument_trace_includeContext':
                self._format_trace_include(child)

    def _format_component_instance(self, ctx) -> None:
        self._flush_comments_before(_first_token(ctx))
        self._w('\n')

        prefix = ''
        if ctx.Removable() is not None:
            prefix += 'REMOVABLE '
        if ctx.Cpu() is not None:
            prefix += 'CPU '
        if ctx.split() is not None:
            split_ctx = ctx.split()
            if split_ctx.expr() is not None:
                prefix += f'SPLIT {self._expr(split_ctx.expr())} '
            else:
                prefix += 'SPLIT '

        inst_name = _literal_text(ctx.instance_name())
        comp_type = _literal_text(ctx.component_type())

        params_str = ''
        if ctx.instance_parameters() is not None:
            parts = []
            for p in ctx.instance_parameters().instance_parameter():
                parts.append(self._format_instance_parameter(p))
            params_str = ', '.join(parts)

        when_str = ''
        if ctx.when() is not None:
            when_str = f' WHEN {self._expr(ctx.when().expr())}'

        self._w(f'{prefix}COMPONENT {inst_name} = {comp_type}({params_str}){when_str}\n')

        # AT … RELATIVE/ABSOLUTE
        place = ctx.place()
        coords = self._coords(place.coords())
        ref = self._reference(place.reference())
        self._w(f'AT {coords} {ref}\n')

        # ROTATED … (optional)
        if ctx.orientation() is not None:
            orient = ctx.orientation()
            acoords = self._coords(orient.coords())
            aref = self._reference(orient.reference())
            self._w(f'ROTATED {acoords} {aref}\n')

        if ctx.groupref() is not None:
            self._flush_comments_before(ctx.groupref().Group().symbol)
            self._w(f'GROUP {ctx.groupref().Identifier().getText()}\n')

        if ctx.extend() is not None:
            ext = ctx.extend()
            self._flush_comments_before(ext.Extend().symbol)
            self._w('EXTEND\n')
            ub = ext.unparsed_block().UnparsedBlock().symbol
            self._flush_comments_before(ub)
            self._w(self._format_unparsed_block(ub.text) + '\n')

        if ctx.jumps() is not None:
            for jump in ctx.jumps().jump():
                self._format_jump(jump)

        for meta in (ctx.metadata() or []):
            self._format_metadata(meta)

    def _format_instance_parameter(self, ctx) -> str:
        name = ctx.Identifier().getText()
        cname = type(ctx).__name__
        if cname == 'InstanceParameterNullContext':
            return f'{name}=NULL'
        if cname == 'InstanceParameterVectorContext':
            return f'{name}={_literal_text(ctx.initializerlist())}'
        # InstanceParameterExpr
        return f'{name}={self._expr(ctx.expr())}'

    def _format_jump(self, ctx) -> None:
        self._flush_comments_before(_first_token(ctx))
        jname_ctx = ctx.jumpname()
        jname = _literal_text(jname_ctx)
        kw = 'ITERATE' if ctx.Iterate() is not None else 'WHEN'
        cond = self._expr(ctx.expr())
        self._w(f'JUMP {jname} {kw} {cond}\n')

    def _format_trace_include(self, ctx) -> None:
        self._flush_comments_before(ctx.Include().symbol)
        self._w(f'%include {ctx.StringLiteral().getText()}\n')

    # -- shared helpers --

    def _format_shell(self, ctx) -> None:
        self._flush_comments_before(ctx.Shell().symbol)
        self._w(f'SHELL {ctx.StringLiteral().getText()}\n')

    def _format_search(self, ctx) -> None:
        self._flush_comments_before(_first_token(ctx))
        cname = type(ctx).__name__
        if cname == 'SearchShellContext':
            self._w(f'SEARCH SHELL {ctx.StringLiteral().getText()}\n')
        else:
            self._w(f'SEARCH {ctx.StringLiteral().getText()}\n')

    def _format_dependency(self, ctx) -> None:
        self._flush_comments_before(ctx.Dependency().symbol)
        self._w(f'DEPENDENCY {ctx.StringLiteral().getText()}\n')

    def _format_instrument_metadata(self, ctx) -> None:
        for meta in ctx.metadata():
            self._format_metadata(meta)

    def _format_metadata(self, ctx) -> None:
        self._flush_comments_before(ctx.MetaData().symbol)
        mime = ctx.mime.text
        name = ctx.name.text
        ub = ctx.unparsed_block().UnparsedBlock().symbol
        self._flush_comments_before(ub)
        self._w(f'METADATA {mime} {name}\n{ub.text}\n')


# ---------------------------------------------------------------------------
# McComp formatter
# ---------------------------------------------------------------------------

class _McCompFormatter(_Formatter):

    def format(self, prog_ctx) -> str:
        self._format_component_definition(prog_ctx.component_definition())
        self._flush_trailing_comments()
        return self.result()

    def _format_component_definition(self, ctx) -> None:
        cname = type(ctx).__name__
        name = ctx.Identifier().getText()

        # Collect parameter names for McDoc header generation
        ps = ctx.component_parameter_set()
        input_params: list[str] = []
        output_params: list[str] = []
        if ps.component_define_parameters() is not None:
            input_params += [
                _param_name(p)
                for p in ps.component_define_parameters().component_parameters().component_parameter()
            ]
        if ps.component_set_parameters() is not None:
            input_params += [
                _param_name(p)
                for p in ps.component_set_parameters().component_parameters().component_parameter()
            ]
        if ps.component_out_parameters() is not None:
            output_params += [
                _param_name(p)
                for p in ps.component_out_parameters().component_parameters().component_parameter()
            ]

        # Rewrite the McDoc header before flushing other hidden comments.
        self._format_mcdoc_header(ctx.Define().symbol, name, input_params, output_params)

        self._flush_comments_before(ctx.Define().symbol)

        name = ctx.Identifier().getText()
        if cname == 'ComponentDefineCopyContext':
            copy_from = ctx.Identifier(1).getText()
            self._w(f'DEFINE COMPONENT {name} COPY {copy_from}\n')
        else:
            self._w(f'DEFINE COMPONENT {name}\n')

        # parameter sets
        ps = ctx.component_parameter_set()
        if ps.component_define_parameters() is not None:
            dp = ps.component_define_parameters()
            self._flush_comments_before(dp.Definition().symbol)
            params = self._format_component_parameters(dp.component_parameters())
            self._w(f'DEFINITION PARAMETERS ({params})\n')
        if ps.component_set_parameters() is not None:
            sp = ps.component_set_parameters()
            self._flush_comments_before(sp.Setting().symbol)
            params = self._format_component_parameters(sp.component_parameters())
            self._w(f'SETTING PARAMETERS ({params})\n')
        if ps.component_out_parameters() is not None:
            op = ps.component_out_parameters()
            self._flush_comments_before(_first_token(op))
            params = self._format_component_parameters(op.component_parameters())
            self._w(f'OUTPUT PARAMETERS ({params})\n')

        if ctx.category() is not None:
            cat = ctx.category()
            self._flush_comments_before(_first_token(cat))
            cat_val = (cat.StringLiteral().getText()[1:-1]
                       if cat.Identifier() is None
                       else cat.Identifier().getText())
            self._w(f'CATEGORY {cat_val}\n')

        if ctx.dependency() is not None:
            dep = ctx.dependency()
            self._flush_comments_before(dep.Dependency().symbol)
            self._w(f'DEPENDENCY {dep.StringLiteral().getText()}\n')

        for meta in (ctx.metadata() or []):
            self._format_metadata(meta)

        if ctx.NoAcc() is not None:
            self._flush_comments_before(ctx.NoAcc().symbol)
            self._w('NOACC\n')

        if ctx.shell() is not None:
            sh = ctx.shell()
            self._flush_comments_before(sh.Shell().symbol)
            self._w(f'SHELL {sh.StringLiteral().getText()}\n')

        if ctx.share() is not None:
            self._section('SHARE', ctx.share().Share().symbol,
                          ctx.share().multi_block())
        if ctx.uservars() is not None:
            self._section('USERVARS', ctx.uservars().UserVars().symbol,
                          ctx.uservars().multi_block())
        if ctx.declare() is not None:
            self._section('DECLARE', ctx.declare().Declare().symbol,
                          ctx.declare().multi_block())
        if ctx.initialise() is not None:
            self._section('INITIALIZE', ctx.initialise().Initialize().symbol,
                          ctx.initialise().multi_block())
        if ctx.component_trace() is not None:
            self._section('TRACE', ctx.component_trace().Trace().symbol,
                          ctx.component_trace().multi_block())
        if ctx.save() is not None:
            self._section('SAVE', ctx.save().Save().symbol,
                          ctx.save().multi_block())
        if ctx.finally_() is not None:
            self._section('FINALLY', ctx.finally_().Finally().symbol,
                          ctx.finally_().multi_block())
        if ctx.display() is not None:
            self._section('MCDISPLAY', ctx.display().McDisplay().symbol,
                          ctx.display().multi_block())

        self._flush_comments_before(ctx.End().symbol)
        self._w('\nEND\n')

    def _format_component_parameters(self, ctx) -> str:
        parts = [self._format_component_parameter(p)
                 for p in ctx.component_parameter()]
        return ', '.join(parts)

    def _format_component_parameter(self, ctx) -> str:
        cname = type(ctx).__name__
        name = _param_name(ctx)
        default = ''
        if ctx.Assign() is not None:
            if hasattr(ctx, 'expr') and ctx.expr() is not None:
                default = '=' + self._expr(ctx.expr())
            elif hasattr(ctx, 'StringLiteral') and ctx.StringLiteral() is not None:
                default = '=' + ctx.StringLiteral().getText()
            elif hasattr(ctx, 'Null') and ctx.Null() is not None:
                default = '=NULL'
            elif hasattr(ctx, 'initializerlist') and ctx.initializerlist() is not None:
                default = '=' + _literal_text(ctx.initializerlist())
            else:
                # Vector/DoubleArray/IntegerArray with an Identifier default, or literal '0'
                idents = ctx.Identifier()
                if isinstance(idents, list) and len(idents) > 1:
                    default = '=' + idents[1].getText()
                else:
                    default = '=0'
        if cname == 'ComponentParameterIntegerContext':
            return f'int {name}{default}'
        if cname == 'ComponentParameterStringContext':
            return f'string {name}{default}'
        if cname == 'ComponentParameterVectorContext':
            return f'vector {name}{default}'
        if cname == 'ComponentParameterDoubleArrayContext':
            return f'double* {name}{default}'
        if cname == 'ComponentParameterIntegerArrayContext':
            return f'int* {name}{default}'
        # ComponentParameterDouble (default, no type prefix needed)
        return f'{name}{default}'

    def _format_metadata(self, ctx) -> None:
        self._flush_comments_before(ctx.MetaData().symbol)
        mime = ctx.mime.text
        name = ctx.name.text
        ub = ctx.unparsed_block().UnparsedBlock().symbol
        self._flush_comments_before(ub)
        self._w(f'METADATA {mime} {name}\n{ub.text}\n')

    def _format_mcdoc_header(
        self,
        define_token,
        comp_name: str,
        input_params: list[str],
        output_params: list[str],
    ) -> None:
        """Find, consume, and rewrite the McDoc block comment before *define_token*.

        Any block comment in the HIDDEN channel that contains McDoc section tags
        (``%I``, ``%D``, ``%P``, or ``%E``) is treated as the component's McDoc
        header.  It is consumed from the hidden token stream (so the normal
        ``_flush_comments_before`` does not re-emit it) and replaced with a
        canonically formatted version.

        Other hidden tokens before ``define_token`` (e.g. a copyright block without
        McDoc tags) are left for ``_flush_comments_before`` to handle normally.
        """
        from antlr4 import Token
        from ._mcdoc import build_canonical_mcdoc, extract_mcdoc_from_token

        _MCDOC_TAGS = ('%I', '%D', '%P', '%E')

        hidden = self._ts.getHiddenTokensToLeft(
            define_token.tokenIndex, Token.HIDDEN_CHANNEL
        ) or []

        # Find the first block comment that looks like a McDoc header.
        mcdoc_token = None
        for h in hidden:
            if h.tokenIndex <= self._last_comment_idx:
                continue
            text = h.text
            if text.startswith('/*') and any(tag in text for tag in _MCDOC_TAGS):
                mcdoc_token = h
                break

        # Parse existing McDoc data (if any).
        existing = extract_mcdoc_from_token(mcdoc_token.text) if mcdoc_token else None

        # Consume the McDoc token so _flush_comments_before skips it.
        if mcdoc_token is not None:
            self._last_comment_idx = max(self._last_comment_idx, mcdoc_token.tokenIndex)

        # Emit the canonical header.
        canonical = build_canonical_mcdoc(comp_name, existing, input_params, output_params)
        self._w(canonical)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def format_instr_source(source: str, filename: str = '<stdin>',
                        clang_format=None) -> str:
    """Parse *source* as a McCode ``.instr`` file and return formatted text.

    Parameters
    ----------
    source:
        Raw instrument source text.
    filename:
        Used only for error messages.
    clang_format:
        Optional callable ``(str) -> str`` that formats C code inside
        ``%{ … %}`` blocks.  Build one with :func:`make_clang_formatter`.
        When *None* (the default) C blocks are reproduced verbatim.
    """
    from mccode_antlr.grammar.McInstrLexer import McInstrLexer
    from mccode_antlr.grammar.McInstrParser import McInstrParser

    stream = InputStream(source)
    lexer = McInstrLexer(stream)
    token_stream = CommonTokenStream(lexer)
    parser = McInstrParser(token_stream)
    tree = parser.prog()

    return _McInstrFormatter(token_stream, clang_fmt=clang_format).format(tree)


def format_comp_source(source: str, filename: str = '<stdin>',
                       clang_format=None) -> str:
    """Parse *source* as a McCode ``.comp`` file and return formatted text.

    Parameters
    ----------
    source:
        Raw component source text.
    filename:
        Used only for error messages.
    clang_format:
        Optional callable ``(str) -> str`` for C blocks.  See
        :func:`make_clang_formatter`.
    """
    from mccode_antlr.grammar.McCompLexer import McCompLexer
    from mccode_antlr.grammar.McCompParser import McCompParser

    stream = InputStream(source)
    lexer = McCompLexer(stream)
    token_stream = CommonTokenStream(lexer)
    parser = McCompParser(token_stream)
    tree = parser.prog()

    return _McCompFormatter(token_stream, clang_fmt=clang_format).format(tree)


def format_source(source: str, ext: str, filename: str = '<stdin>',
                  clang_format=None) -> str:
    """Format *source* for the given file extension (``.instr`` or ``.comp``).

    Parameters
    ----------
    source:
        Raw McCode source text.
    ext:
        File extension, e.g. ``'.instr'`` or ``'.comp'``.  Case-insensitive.
    filename:
        Used only for error messages.
    clang_format:
        Optional callable ``(str) -> str`` for C blocks.  See
        :func:`make_clang_formatter`.
    """
    ext = ext.lower()
    if ext == '.instr':
        return format_instr_source(source, filename, clang_format=clang_format)
    if ext == '.comp':
        return format_comp_source(source, filename, clang_format=clang_format)
    raise ValueError(
        f"Unsupported file extension '{ext}'; expected '.instr' or '.comp'"
    )


def format_file(path: str | Path, clang_format=None) -> str:
    """Read *path*, format it, and return the formatted text.

    Parameters
    ----------
    path:
        Path to a ``.instr`` or ``.comp`` file.
    clang_format:
        Optional callable ``(str) -> str`` for C blocks.  See
        :func:`make_clang_formatter`.
    """
    path = Path(path)
    source = path.read_text(encoding='utf-8')
    return format_source(source, path.suffix, filename=str(path),
                         clang_format=clang_format)


# ---------------------------------------------------------------------------
# clang-format integration for C blocks
# ---------------------------------------------------------------------------

def fetch_mccode_clang_format_config() -> Path | None:
    """Fetch (and locally cache) the official McCode ``.clang-format`` file.

    The file is retrieved from the ``mccode-dev/McCode`` GitHub repository at
    the version tag that mccode-antlr is currently configured to use – the same
    tag used for component and library files.  The result is cached under
    ``pooch.os_cache('mccodeantlr/clang-format/{tag}/')`` so subsequent calls
    are free.

    Returns *None* (with a debug-level log message) if:

    - the network is unavailable,
    - the McCode repository does not yet contain a ``.clang-format`` file at
      the resolved tag (the config is still being debated), or
    - any other error occurs.

    The caller should treat a *None* return as "not available yet" and skip
    C-block formatting rather than raising an error.
    """
    try:
        import pooch as _pooch
        from mccode_antlr.reader.registry import (
            mccode_registry_url_tag, _fetch_registry_with_retry,
        )

        source_url, tag = mccode_registry_url_tag()
        url = f'{source_url}/raw/{tag}/.clang-format'
        cache_dir = _pooch.os_cache('mccodeantlr/clang-format') / tag
        cached = cache_dir / '.clang-format'

        if cached.exists():
            return cached

        response = _fetch_registry_with_retry(url)
        if response is None or not response.ok:
            from loguru import logger
            logger.debug(
                f'McCode .clang-format not available at {url} '
                f'(status {getattr(response, "status_code", "?")})'
            )
            return None

        cache_dir.mkdir(parents=True, exist_ok=True)
        cached.write_text(response.text, encoding='utf-8')
        return cached

    except Exception as exc:
        from loguru import logger
        logger.debug(f'Could not fetch McCode .clang-format config: {exc}')
        return None


def make_clang_formatter(
    config: 'str | Path | None' = None,
    style: str | None = None,
    fetch_mccode_config: bool = True,
) -> 'Callable[[str], str] | None':
    """Build a C-code formatter callable for use with :func:`format_source` /
    :func:`format_file`.

    Parameters
    ----------
    config:
        Path to a ``.clang-format`` configuration file.  Passed to
        ``clang-format`` as ``--style=file:<config>``.  When *None* and
        *fetch_mccode_config* is True the official McCode config is fetched
        automatically via :func:`fetch_mccode_clang_format_config`.
    style:
        A clang-format style string (e.g. ``'LLVM'``, ``'Google'``, or an
        inline ``{BasedOnStyle: LLVM, IndentWidth: 4}`` map).  Passed as
        ``--style=<style>``.  Takes precedence over *config* when both are
        given.
    fetch_mccode_config:
        When *True* (the default) and neither *config* nor *style* is given,
        attempt to fetch the official McCode ``.clang-format`` config from
        the McCode GitHub repository.  If the fetch fails the function logs a
        warning and returns *None*.

    Returns
    -------
    callable or None
        A ``(str) -> str`` function that formats C code using clang-format,
        or *None* if clang-format is not installed or no configuration could
        be resolved.  Callers should check for *None* and treat it as
        "C-block formatting unavailable".

    Notes
    -----
    The returned callable passes C content to ``clang-format`` via stdin
    with ``--assume-filename=block.c`` so that the formatter recognises the
    input as C code regardless of which ``.clang-format`` style is used.
    On any clang-format error the original content is returned unchanged so
    that a broken config never corrupts a file.
    """
    import shutil

    if shutil.which('clang-format') is None:
        from loguru import logger
        logger.warning(
            'clang-format not found on PATH; C blocks will not be formatted'
        )
        return None

    # Resolve configuration
    resolved_config: Path | None = None
    if style is None:
        if config is not None:
            resolved_config = Path(config)
        elif fetch_mccode_config:
            resolved_config = fetch_mccode_clang_format_config()
            if resolved_config is None:
                from loguru import logger
                logger.warning(
                    'McCode .clang-format config not yet available; '
                    'C blocks will not be formatted.  '
                    'Supply --clang-format-config or --clang-format-style '
                    'to format C blocks with a local or named style.'
                )
                return None

    def _fmt(content: str) -> str:
        import subprocess
        cmd = ['clang-format', '--assume-filename=block.c']
        if style:
            cmd.append(f'--style={style}')
        elif resolved_config:
            cmd.append(f'--style=file:{resolved_config}')
        # else: no --style flag → clang-format searches for .clang-format upward
        try:
            result = subprocess.run(
                cmd, input=content, capture_output=True, text=True, check=True,
            )
            return result.stdout
        except subprocess.CalledProcessError as exc:
            from loguru import logger
            logger.warning(f'clang-format exited with code {exc.returncode}; '
                           'C block left unchanged')
            return content
        except FileNotFoundError:
            return content

    return _fmt

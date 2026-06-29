"""ANTLR C grammar-based evaluator for McCode INITIALIZE/DECLARE blocks.

Public API:
    evaluate_c_block(block, known, instrument_parameters, user_types, verbose)
        -> dict[str, Expr]
"""
from __future__ import annotations

import sympy
from loguru import logger

from ..grammar import CParser, CVisitor
from ..common import Expr
from ..common.expression.sympy_classes import (
    CTernary, CArrayIndex, CStructAccess, CPointerAccess,
    CFunctionCall, CAnd, COr, CNot, CLeftShift, CRightShift,
)
from ..common.expression.types import DataType


# ---------------------------------------------------------------------------
# Module-level constant tables
# ---------------------------------------------------------------------------

MCCODE_CONSTANTS: dict[str, Expr] = {
    'PI':       Expr.float('3.14159265358979323846'),
    'K2V':      Expr.float('629.622368'),
    'V2K':      Expr.float('1.58825361e-3'),
    'DEG2RAD':  Expr.float('0.017453292519943295'),
    'RAD2DEG':  Expr.float('57.29577951308232'),
    'HBAR':     Expr.float('1.054571817e-34'),
    'MNEUTRON': Expr.float('1.67492749804e-27'),
    'E2V':      Expr.float('437.393377'),
    'V2E':      Expr.float('5.22699392e-6'),
    'SE2V':     Expr.float('437.393377'),
    'VS2E':     Expr.float('5.22699392e-6'),
    'FWHM2SIG': Expr.float('0.4246609001'),
    'SIG2FWHM': Expr.float('2.3548200450'),
    'TRUE':     Expr.integer(1),
    'FALSE':    Expr.integer(0),
}

MATH_BUILTINS: dict[str, object] = {
    'sin':   sympy.sin,
    'cos':   sympy.cos,
    'tan':   sympy.tan,
    'asin':  sympy.asin,
    'acos':  sympy.acos,
    'atan':  sympy.atan,
    'atan2': sympy.atan2,
    'sinh':  sympy.sinh,
    'cosh':  sympy.cosh,
    'tanh':  sympy.tanh,
    'exp':   sympy.exp,
    'log':   sympy.log,
    'log10': lambda x: sympy.log(x, 10),
    'sqrt':  sympy.sqrt,
    'floor': sympy.floor,
    'ceil':  sympy.ceiling,
    'abs':   sympy.Abs,
    'fabs':  sympy.Abs,
    'pow':   sympy.Pow,
    'fmod':  sympy.Mod,
}

VOID_BUILTINS: frozenset[str] = frozenset({
    'printf', 'fprintf', 'sprintf', 'snprintf',
    'scanf', 'fscanf', 'sscanf',
    'exit', 'abort',
    'MPI_MASTER', 'MPI_Send', 'MPI_Recv',
})

_COMPOUND_OPS: dict[str, str] = {
    '+=': '+', '-=': '-', '*=': '*', '/=': '/', '%=': '%',
    '<<=': '<<', '>>=': '>>', '&=': '&', '^=': '^', '|=': '|',
}

_MAX_UNROLL = 1024


# ---------------------------------------------------------------------------
# Flow-control sentinels (raised by jump statements, caught by loop handlers)
# ---------------------------------------------------------------------------

class _Break(Exception):
    pass


class _Continue(Exception):
    pass


# ---------------------------------------------------------------------------
# Helper: parse a C constant literal to Expr
# ---------------------------------------------------------------------------

def _parse_constant(text: str) -> Expr:
    """Convert a C literal token (integer, float, character) to an Expr."""
    if text.startswith("'"):
        inner = text[1:-1]
        try:
            escape_map = {'\\n': '\n', '\\t': '\t', '\\r': '\r',
                          '\\\\': '\\', "\\'": "'", '\\0': '\x00'}
            ch = escape_map.get(inner, inner[1] if inner.startswith('\\') else inner[0])
            return Expr.integer(ord(ch))
        except Exception:
            return Expr.id(text)

    low = text.lower()

    # Hex: 'f' is a valid digit so only strip u/l suffixes
    if low.startswith('0x'):
        raw = text.rstrip('uUlL')
        try:
            return Expr.integer(int(raw, 16))
        except Exception:
            return Expr.id(text)

    raw = text.rstrip('uUlLfF')
    is_float = 'e' in low or '.' in low or low.endswith('f') or low.endswith('l')

    if is_float:
        try:
            return Expr.float(raw)
        except Exception:
            return Expr.id(text)

    try:
        if low.startswith('0b'):
            return Expr.integer(int(raw, 2))
        if raw.startswith('0') and len(raw) > 1:
            return Expr.integer(int(raw, 8))
        return Expr.integer(int(raw))
    except Exception:
        return Expr.id(text)


# ---------------------------------------------------------------------------
# CBlockEvaluator
# ---------------------------------------------------------------------------

class CBlockEvaluator(CVisitor):
    """Evaluate a C compound statement, updating a symbolic variable state.

    Tracks three state dictionaries:
      state        — scalar variable bindings  (name -> Expr)
      array_state  — array element bindings    (name -> {int_index -> Expr})
      struct_state — struct/union field values (name -> {field_str -> Expr})
    """

    def __init__(self, known: dict[str, Expr], instrument_parameters=(),
                 verbose: bool = False):
        self.state: dict[str, Expr] = dict(known)
        self.array_state: dict[str, dict[int, Expr]] = {}
        self.struct_state: dict[str, dict[str, Expr]] = {}
        self.instrument_params: dict[str, Expr] = {}
        for p in instrument_parameters:
            name = p.name if hasattr(p, 'name') else str(p)
            self.instrument_params[name] = Expr.parameter(name)
        self.verbose = verbose

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _read(self, name: str) -> Expr:
        if name in self.state:
            return self.state[name]
        if name in self.instrument_params:
            return self.instrument_params[name]
        if name in MCCODE_CONSTANTS:
            return MCCODE_CONSTANTS[name]
        return Expr.id(name)

    def _write(self, name: str, value: Expr) -> None:
        self.state[name] = value

    def _try_bool(self, expr: Expr) -> bool | None:
        """Return True/False if concretely known, else None."""
        if not expr.is_singular:
            return None
        sym = expr._exprs[0]
        if sym is sympy.true:
            return True
        if sym is sympy.false:
            return False
        if sym.is_number:
            try:
                return bool(float(sym))
            except Exception:
                return None
        return None

    def _to_int(self, expr: Expr | None) -> int | None:
        """Return a concrete Python int from an Expr, or None."""
        if expr is None or not expr.is_singular:
            return None
        sym = expr._exprs[0]
        if sym.is_integer is True and sym.is_number:
            return int(sym)
        return None

    def _fork(self) -> 'CBlockEvaluator':
        """Return a shallow-copied evaluator for branch forking."""
        fork = CBlockEvaluator.__new__(CBlockEvaluator)
        fork.state = dict(self.state)
        fork.array_state = {k: dict(v) for k, v in self.array_state.items()}
        fork.struct_state = {k: dict(v) for k, v in self.struct_state.items()}
        fork.instrument_params = self.instrument_params
        fork.verbose = self.verbose
        return fork

    def _dispatch_function(self, name: str, args: list[Expr]) -> Expr:
        """Evaluate a function call symbolically."""
        if name in VOID_BUILTINS:
            return Expr.integer(0)

        if name in MATH_BUILTINS:
            fn = MATH_BUILTINS[name]
            sym_args = [a._exprs[0] for a in args if a.is_singular]
            if len(sym_args) == len(args):
                try:
                    result = fn(*sym_args)
                    return Expr(result, DataType.float)
                except Exception:
                    pass

        fn_sym = sympy.Symbol(name)
        sym_args = [a._exprs[0] for a in args if a.is_singular]
        if len(sym_args) == len(args):
            return Expr(CFunctionCall(fn_sym, *sym_args), DataType.undefined)
        return Expr.id(f'{name}(...)')

    def _merge_ternary(self, cond_sym, then_val: Expr, else_val: Expr) -> Expr:
        if then_val == else_val:
            return then_val
        if then_val.is_singular and else_val.is_singular:
            return Expr(CTernary(cond_sym, then_val._exprs[0], else_val._exprs[0]),
                        DataType.undefined)
        return then_val  # fallback

    # ------------------------------------------------------------------
    # Statement visitors
    # ------------------------------------------------------------------

    def visitCompoundStatement(self, ctx: CParser.CompoundStatementContext):
        if ctx.blockItemList() is not None:
            self.visit(ctx.blockItemList())

    def visitBlockItemList(self, ctx: CParser.BlockItemListContext):
        for item in ctx.blockItem():
            self.visit(item)

    def visitBlockItem(self, ctx: CParser.BlockItemContext):
        if ctx.statement() is not None:
            self.visit(ctx.statement())
        elif ctx.declaration() is not None:
            self._visit_declaration(ctx.declaration())

    def visitStatement(self, ctx: CParser.StatementContext):
        if ctx.expressionStatement() is not None:
            self.visit(ctx.expressionStatement())
        elif ctx.compoundStatement() is not None:
            self.visit(ctx.compoundStatement())
        elif ctx.selectionStatement() is not None:
            self.visit(ctx.selectionStatement())
        elif ctx.iterationStatement() is not None:
            self.visit(ctx.iterationStatement())
        elif ctx.jumpStatement() is not None:
            self.visit(ctx.jumpStatement())
        elif ctx.labeledStatement() is not None:
            ls = ctx.labeledStatement()
            if ls.statement() is not None:
                self.visit(ls.statement())

    # ------------------------------------------------------------------
    # Jump statements (Phase 2)
    # ------------------------------------------------------------------

    def visitJumpStatement(self, ctx: CParser.JumpStatementContext):
        if ctx.Break() is not None:
            raise _Break()
        if ctx.Continue() is not None:
            raise _Continue()
        # return / goto: skip

    # ------------------------------------------------------------------
    # Iteration statements (Phase 2)
    # ------------------------------------------------------------------

    def visitIterationStatement(self, ctx: CParser.IterationStatementContext):
        if ctx.For() is not None:
            self._visit_for(ctx)
        elif ctx.Do() is not None:
            # Check Do before While: do-while loops also contain a While token
            self._visit_do_while(ctx)
        elif ctx.While() is not None:
            self._visit_while(ctx)

    def _visit_for(self, ctx: CParser.IterationStatementContext):
        fc = ctx.forCondition()
        # Init
        if fc.forDeclaration() is not None:
            self.visit(fc.forDeclaration())
        elif fc.expression() is not None:
            self.visit(fc.expression())

        for _ in range(_MAX_UNROLL):
            # Condition (forExpression(0))
            cond_ctx = fc.forExpression(0)
            if cond_ctx is not None:
                cond = self.visit(cond_ctx)
                known = self._try_bool(cond)
                if known is False:
                    return
                if known is None:
                    logger.debug('CBlockEvaluator: for condition not concrete, skipping loop')
                    return
            # Body
            try:
                self.visit(ctx.statement())
            except _Break:
                return
            except _Continue:
                pass
            # Update (forExpression(1))
            upd_ctx = fc.forExpression(1)
            if upd_ctx is not None:
                self.visit(upd_ctx)
        else:
            logger.debug(f'CBlockEvaluator: for loop hit MAX_UNROLL={_MAX_UNROLL}')

    def _visit_while(self, ctx: CParser.IterationStatementContext):
        for _ in range(_MAX_UNROLL):
            cond_ctx = ctx.expression()
            if cond_ctx is not None:
                cond = self.visit(cond_ctx)
                known = self._try_bool(cond)
                if known is False:
                    return
                if known is None:
                    logger.debug('CBlockEvaluator: while condition not concrete, skipping')
                    return
            try:
                self.visit(ctx.statement())
            except _Break:
                return
            except _Continue:
                pass
        else:
            logger.debug(f'CBlockEvaluator: while loop hit MAX_UNROLL={_MAX_UNROLL}')

    def _visit_do_while(self, ctx: CParser.IterationStatementContext):
        for _ in range(_MAX_UNROLL):
            try:
                self.visit(ctx.statement())
            except _Break:
                return
            except _Continue:
                pass
            cond_ctx = ctx.expression()
            if cond_ctx is not None:
                cond = self.visit(cond_ctx)
                known = self._try_bool(cond)
                if known is False:
                    return
                if known is None:
                    logger.debug('CBlockEvaluator: do-while condition not concrete')
                    return
        else:
            logger.debug(f'CBlockEvaluator: do-while hit MAX_UNROLL={_MAX_UNROLL}')

    def visitForDeclaration(self, ctx: CParser.ForDeclarationContext):
        if ctx.initDeclaratorList() is None:
            return
        for init_decl in ctx.initDeclaratorList().initDeclarator():
            decl = init_decl.declarator()
            dd = decl.directDeclarator() if decl else None
            name = self._get_dd_name(dd) if dd else None
            if name is None:
                continue
            if init_decl.initializer() is not None:
                try:
                    value = self.visit(init_decl.initializer())
                    if value is not None and not isinstance(value, list):
                        self._write(name, value)
                except Exception as e:
                    logger.debug(f'CBlockEvaluator: skip for-init for {name}: {e}')
            else:
                self.state.setdefault(name, Expr.id(name))

    def visitForExpression(self, ctx: CParser.ForExpressionContext):
        result = None
        for a in ctx.assignmentExpression():
            result = self.visit(a)
        return result

    # ------------------------------------------------------------------
    # Selection statements
    # ------------------------------------------------------------------

    def visitSelectionStatement(self, ctx: CParser.SelectionStatementContext):
        if ctx.If() is not None:
            self._visit_if(ctx)
        elif ctx.Switch() is not None:
            self._visit_switch(ctx)

    def _visit_if(self, ctx: CParser.SelectionStatementContext):
        cond = self.visit(ctx.expression())
        if cond is None:
            return
        known = self._try_bool(cond)

        if known is True:
            self.visit(ctx.statement(0))
            return
        if known is False:
            if ctx.statement(1) is not None:
                self.visit(ctx.statement(1))
            return

        # Unknown: fork both branches, merge with CTernary
        cond_sym = cond._exprs[0] if cond.is_singular else sympy.Symbol('_cond_')
        pre_state = dict(self.state)
        pre_array = {k: dict(v) for k, v in self.array_state.items()}
        pre_struct = {k: dict(v) for k, v in self.struct_state.items()}

        then_fork = self._fork()
        then_fork.visit(ctx.statement(0))

        else_fork = self._fork()  # starts from pre-state
        if ctx.statement(1) is not None:
            else_fork.visit(ctx.statement(1))

        # Merge scalar state
        all_keys = set(then_fork.state) | set(else_fork.state)
        for k in all_keys:
            tv = then_fork.state.get(k, pre_state.get(k, Expr.id(k)))
            ev = else_fork.state.get(k, pre_state.get(k, Expr.id(k)))
            self.state[k] = self._merge_ternary(cond_sym, tv, ev)

        # Merge array state
        all_arrs = set(then_fork.array_state) | set(else_fork.array_state)
        for arr in all_arrs:
            ta = then_fork.array_state.get(arr, pre_array.get(arr, {}))
            ea = else_fork.array_state.get(arr, pre_array.get(arr, {}))
            merged: dict[int, Expr] = {}
            for idx in set(ta) | set(ea):
                tv = ta.get(idx, Expr.id(f'{arr}[{idx}]'))
                ev = ea.get(idx, Expr.id(f'{arr}[{idx}]'))
                merged[idx] = self._merge_ternary(cond_sym, tv, ev)
            self.array_state[arr] = merged

        # Merge struct state
        all_structs = set(then_fork.struct_state) | set(else_fork.struct_state)
        for obj in all_structs:
            ts = then_fork.struct_state.get(obj, pre_struct.get(obj, {}))
            es = else_fork.struct_state.get(obj, pre_struct.get(obj, {}))
            merged_s: dict[str, Expr] = {}
            for field in set(ts) | set(es):
                tv = ts.get(field, Expr.id(f'{obj}.{field}'))
                ev = es.get(field, Expr.id(f'{obj}.{field}'))
                merged_s[field] = self._merge_ternary(cond_sym, tv, ev)
            self.struct_state[obj] = merged_s

    def _visit_switch(self, ctx: CParser.SelectionStatementContext):
        sw_val = self.visit(ctx.expression())
        sw_int = self._to_int(sw_val)

        body_stmt = ctx.statement(0)
        if body_stmt is None or body_stmt.compoundStatement() is None:
            return
        compound = body_stmt.compoundStatement()
        if compound.blockItemList() is None:
            return
        items = compound.blockItemList().blockItem()

        if sw_int is None:
            logger.debug('CBlockEvaluator: skip symbolic switch')
            return

        # Find matching case or default
        start_idx = None
        default_idx = None
        for i, item in enumerate(items):
            ls = self._get_labeled_statement(item)
            if ls is None:
                continue
            if ls.Case() is not None and ls.constantExpression() is not None:
                case_val = self.visit(ls.constantExpression())
                if self._to_int(case_val) == sw_int:
                    start_idx = i
                    break
            elif ls.Default() is not None:
                default_idx = i

        if start_idx is None:
            start_idx = default_idx
        if start_idx is None:
            return

        try:
            for item in items[start_idx:]:
                ls = self._get_labeled_statement(item)
                if ls is not None:
                    if ls.statement() is not None:
                        self.visit(ls.statement())
                elif item.statement() is not None:
                    self.visit(item.statement())
                elif item.declaration() is not None:
                    self._visit_declaration(item.declaration())
        except _Break:
            pass

    def _get_labeled_statement(self, item: CParser.BlockItemContext):
        """Return LabeledStatementContext if this blockItem is a labeled statement."""
        if item.statement() is not None:
            stmt = item.statement()
            if stmt.labeledStatement() is not None:
                return stmt.labeledStatement()
        return None

    # ------------------------------------------------------------------
    # Declaration helpers
    # ------------------------------------------------------------------

    def _get_dd_name(self, ctx: CParser.DirectDeclaratorContext) -> str | None:
        """Recursively find the base identifier in a directDeclarator."""
        if ctx.Identifier() is not None:
            return ctx.Identifier().getText()
        if ctx.directDeclarator() is not None:
            return self._get_dd_name(ctx.directDeclarator())
        return None

    def _visit_declaration(self, ctx: CParser.DeclarationContext):
        """Process local variable declarations; array initializers go to array_state."""
        if ctx.staticAssertDeclaration() is not None:
            return
        if ctx.initDeclaratorList() is None:
            return
        for init_decl in ctx.initDeclaratorList().initDeclarator():
            decl = init_decl.declarator()
            dd = decl.directDeclarator() if decl else None
            name = self._get_dd_name(dd) if dd else None
            if name is None:
                continue
            is_array = dd is not None and dd.LeftBracket() is not None
            if init_decl.initializer() is not None:
                try:
                    value = self.visit(init_decl.initializer())
                    if isinstance(value, list):
                        arr: dict[int, Expr] = {}
                        for i, v in enumerate(value):
                            if v is not None and not isinstance(v, list):
                                arr[i] = v
                        self.array_state[name] = arr
                    elif value is not None:
                        self._write(name, value)
                except Exception as e:
                    logger.debug(f'CBlockEvaluator: skip initializer for {name}: {e}')
            elif not is_array:
                self.state.setdefault(name, Expr.id(name))

    # ------------------------------------------------------------------
    # Initializer (Phase 3: list → Python list of Expr)
    # ------------------------------------------------------------------

    def visitInitializer(self, ctx: CParser.InitializerContext):
        if ctx.assignmentExpression() is not None:
            return self.visit(ctx.assignmentExpression())
        if ctx.initializerList() is not None:
            return self.visit(ctx.initializerList())
        return None

    def visitInitializerList(self, ctx: CParser.InitializerListContext):
        values = []
        for init in ctx.initializer():
            val = self.visit(init)
            if isinstance(val, list):
                values.extend(val)
            else:
                values.append(val)
        return values

    # ------------------------------------------------------------------
    # LabeledStatement constant expression (for switch case values)
    # ------------------------------------------------------------------

    def visitConstantExpression(self, ctx: CParser.ConstantExpressionContext):
        return self.visit(ctx.conditionalExpression())

    # ------------------------------------------------------------------
    # Expression statements
    # ------------------------------------------------------------------

    def visitExpressionStatement(self, ctx: CParser.ExpressionStatementContext):
        if ctx.expression() is not None:
            self.visit(ctx.expression())

    # ------------------------------------------------------------------
    # LHS extraction helpers
    # ------------------------------------------------------------------

    def _extract_lhs(self, ctx: CParser.UnaryExpressionContext) -> tuple[str | None, bool]:
        """(name, is_simple_scalar). is_simple=False when subscript/member suffix present."""
        if ctx.postfixExpression() is None:
            return None, False
        pfe = ctx.postfixExpression()
        if pfe.primaryExpression() is None:
            return None, False
        pe = pfe.primaryExpression()
        if pe.Identifier() is None:
            return None, False
        name = pe.Identifier().getText()
        has_suffix = bool(pfe.LeftBracket() or pfe.Dot() or pfe.Arrow() or pfe.LeftParen())
        return name, not has_suffix

    def _extract_array_lhs(self, ctx: CParser.UnaryExpressionContext):
        """Returns (arr_name, idx_expr) for a simple arr[idx] LHS, else None."""
        if ctx.postfixExpression() is None:
            return None
        pfe = ctx.postfixExpression()
        if pfe.primaryExpression() is None or pfe.primaryExpression().Identifier() is None:
            return None
        arr_name = pfe.primaryExpression().Identifier().getText()
        brackets = pfe.LeftBracket() or []
        if len(brackets) != 1 or pfe.Dot() or pfe.Arrow() or pfe.LeftParen():
            return None
        children = pfe.children or []
        for i, child in enumerate(children):
            if hasattr(child, 'symbol') and child.symbol.type == CParser.LeftBracket:
                if i + 1 < len(children):
                    idx = self.visit(children[i + 1])
                    return arr_name, idx
        return None

    def _extract_struct_lhs(self, ctx: CParser.UnaryExpressionContext):
        """Returns (obj_name, field_name, is_arrow) for simple obj.field or ptr->field LHS."""
        if ctx.postfixExpression() is None:
            return None
        pfe = ctx.postfixExpression()
        if pfe.primaryExpression() is None or pfe.primaryExpression().Identifier() is None:
            return None
        obj_name = pfe.primaryExpression().Identifier().getText()
        dots   = pfe.Dot()   or []
        arrows = pfe.Arrow() or []
        if pfe.LeftBracket() or pfe.LeftParen():
            return None
        if len(dots) + len(arrows) != 1:
            return None
        # pfe.Identifier() gives field-name tokens (base ident is in primaryExpression)
        idents = pfe.Identifier() or []
        if not idents:
            return None
        return obj_name, idents[0].getText(), len(arrows) > 0

    # ------------------------------------------------------------------
    # Expression visitors
    # ------------------------------------------------------------------

    def visitExpression(self, ctx: CParser.ExpressionContext):
        result = None
        for child in ctx.assignmentExpression():
            result = self.visit(child)
        return result

    def visitAssignmentExpression(self, ctx: CParser.AssignmentExpressionContext):
        if ctx.conditionalExpression() is not None:
            return self.visit(ctx.conditionalExpression())
        if ctx.unaryExpression() is None:
            return Expr.id(ctx.getText())

        rhs = self.visit(ctx.assignmentExpression())
        if rhs is None:
            return None
        op_text = ctx.assignmentOperator().getText()

        # Simple scalar assignment
        name, is_simple = self._extract_lhs(ctx.unaryExpression())
        if name is not None and is_simple:
            if op_text == '=':
                self._write(name, rhs)
            elif op_text in _COMPOUND_OPS:
                old = self._read(name)
                self._write(name, self._apply_op(_COMPOUND_OPS[op_text], old, rhs))
            return rhs

        # Array element assignment: arr[idx] = rhs  (Phase 3)
        arr_info = self._extract_array_lhs(ctx.unaryExpression())
        if arr_info is not None:
            arr_name, idx = arr_info
            idx_int = self._to_int(idx)
            if idx_int is not None:
                if arr_name not in self.array_state:
                    self.array_state[arr_name] = {}
                if op_text == '=':
                    self.array_state[arr_name][idx_int] = rhs
                elif op_text in _COMPOUND_OPS:
                    old = self.array_state[arr_name].get(
                        idx_int, Expr.id(f'{arr_name}[{idx_int}]'))
                    self.array_state[arr_name][idx_int] = self._apply_op(
                        _COMPOUND_OPS[op_text], old, rhs)
            else:
                logger.debug(f'CBlockEvaluator: skip symbolic array write {arr_name}[{idx}]')
            return rhs

        # Struct/pointer member assignment: obj.field = rhs  (Phase 4)
        struct_info = self._extract_struct_lhs(ctx.unaryExpression())
        if struct_info is not None:
            obj_name, field_name, _ = struct_info
            if obj_name not in self.struct_state:
                self.struct_state[obj_name] = {}
            if op_text == '=':
                self.struct_state[obj_name][field_name] = rhs
            elif op_text in _COMPOUND_OPS:
                old = self.struct_state[obj_name].get(
                    field_name, Expr.id(f'{obj_name}.{field_name}'))
                self.struct_state[obj_name][field_name] = self._apply_op(
                    _COMPOUND_OPS[op_text], old, rhs)
            return rhs

        if name is not None:
            logger.debug(f'CBlockEvaluator: skip complex LHS: {ctx.unaryExpression().getText()}')
        return rhs

    def _apply_op(self, op: str, lhs: Expr, rhs: Expr) -> Expr:
        if op == '+': return lhs + rhs
        if op == '-': return lhs - rhs
        if op == '*': return lhs * rhs
        if op == '/':
            if lhs.data_type == DataType.int and rhs.data_type == DataType.int:
                return lhs // rhs
            return lhs / rhs
        if op == '%': return lhs % rhs
        if op == '<<' and lhs.is_singular and rhs.is_singular:
            return Expr(CLeftShift(lhs._exprs[0], rhs._exprs[0]), DataType.int)
        if op == '>>' and lhs.is_singular and rhs.is_singular:
            return Expr(CRightShift(lhs._exprs[0], rhs._exprs[0]), DataType.int)
        if op == '&': return lhs & rhs
        if op == '^': return lhs ^ rhs
        if op == '|': return lhs | rhs
        return rhs

    def visitConditionalExpression(self, ctx: CParser.ConditionalExpressionContext):
        cond = self.visit(ctx.logicalOrExpression())
        if ctx.Question() is None:
            return cond
        true_val = self.visit(ctx.expression())
        false_val = self.visit(ctx.conditionalExpression())
        known = self._try_bool(cond)
        if known is True:
            return true_val
        if known is False:
            return false_val
        if cond is None or true_val is None or false_val is None:
            return cond
        if cond.is_singular and true_val.is_singular and false_val.is_singular:
            return Expr(CTernary(cond._exprs[0], true_val._exprs[0], false_val._exprs[0]),
                        DataType.undefined)
        return cond

    def visitLogicalOrExpression(self, ctx: CParser.LogicalOrExpressionContext):
        return self._fold_binary(
            ctx, ctx.logicalAndExpression(),
            {CParser.OrOr: lambda l, r: Expr(
                COr(l._exprs[0], r._exprs[0]), DataType.int
            ) if l.is_singular and r.is_singular else l},
        )

    def visitLogicalAndExpression(self, ctx: CParser.LogicalAndExpressionContext):
        return self._fold_binary(
            ctx, ctx.inclusiveOrExpression(),
            {CParser.AndAnd: lambda l, r: Expr(
                CAnd(l._exprs[0], r._exprs[0]), DataType.int
            ) if l.is_singular and r.is_singular else l},
        )

    def visitInclusiveOrExpression(self, ctx: CParser.InclusiveOrExpressionContext):
        return self._fold_binary(ctx, ctx.exclusiveOrExpression(),
                                 {CParser.Or: lambda l, r: l | r})

    def visitExclusiveOrExpression(self, ctx: CParser.ExclusiveOrExpressionContext):
        return self._fold_binary(ctx, ctx.andExpression(),
                                 {CParser.Caret: lambda l, r: l ^ r})

    def visitAndExpression(self, ctx: CParser.AndExpressionContext):
        return self._fold_binary(ctx, ctx.equalityExpression(),
                                 {CParser.And: lambda l, r: l & r})

    def visitEqualityExpression(self, ctx: CParser.EqualityExpressionContext):
        return self._fold_binary(
            ctx, ctx.relationalExpression(),
            {CParser.Equal:    lambda l, r: l.eq(r),
             CParser.NotEqual: lambda l, r: l.ne(r)},
        )

    def visitRelationalExpression(self, ctx: CParser.RelationalExpressionContext):
        return self._fold_binary(
            ctx, ctx.shiftExpression(),
            {CParser.Less:         lambda l, r: l.lt(r),
             CParser.Greater:      lambda l, r: l.gt(r),
             CParser.LessEqual:    lambda l, r: l.le(r),
             CParser.GreaterEqual: lambda l, r: l.ge(r)},
        )

    def visitShiftExpression(self, ctx: CParser.ShiftExpressionContext):
        def _shl(l, r):
            if l.is_singular and r.is_singular:
                return Expr(CLeftShift(l._exprs[0], r._exprs[0]), DataType.int)
            return l
        def _shr(l, r):
            if l.is_singular and r.is_singular:
                return Expr(CRightShift(l._exprs[0], r._exprs[0]), DataType.int)
            return l
        return self._fold_binary(ctx, ctx.additiveExpression(),
                                 {CParser.LeftShift: _shl, CParser.RightShift: _shr})

    def visitAdditiveExpression(self, ctx: CParser.AdditiveExpressionContext):
        return self._fold_binary(
            ctx, ctx.multiplicativeExpression(),
            {CParser.Plus:  lambda l, r: l + r,
             CParser.Minus: lambda l, r: l - r},
        )

    def visitMultiplicativeExpression(self, ctx: CParser.MultiplicativeExpressionContext):
        def _div(l, r):
            if l.data_type == DataType.int and r.data_type == DataType.int:
                return l // r
            return l / r
        return self._fold_binary(
            ctx, ctx.castExpression(),
            {CParser.Star: lambda l, r: l * r,
             CParser.Div:  _div,
             CParser.Mod:  lambda l, r: l % r},
        )

    def _fold_binary(self, ctx, operand_ctxs, op_table: dict) -> Expr:
        """Left-fold binary expression over alternating operands and operators."""
        operands = [self.visit(c) for c in operand_ctxs]
        if not operands:
            return Expr.id(ctx.getText())
        result = operands[0] or Expr.id(ctx.getText())
        op_idx = 0
        for child in (ctx.children or []):
            if not hasattr(child, 'symbol'):
                continue
            ttype = child.symbol.type
            if ttype in op_table and op_idx + 1 < len(operands):
                rhs = operands[op_idx + 1]
                if rhs is not None:
                    try:
                        result = op_table[ttype](result, rhs)
                    except Exception as e:
                        logger.debug(f'CBlockEvaluator: binary op failed: {e}')
                op_idx += 1
        return result

    def visitCastExpression(self, ctx: CParser.CastExpressionContext):
        if ctx.unaryExpression() is not None:
            return self.visit(ctx.unaryExpression())
        if ctx.castExpression() is not None:
            inner = self.visit(ctx.castExpression())
            if inner is None:
                return None
            type_text = ctx.typeName().getText() if ctx.typeName() else ''
            if 'int' in type_text and inner.is_singular:
                return Expr(inner._exprs[0], DataType.int)
            return inner
        return Expr.id(ctx.getText())

    def visitUnaryExpression(self, ctx: CParser.UnaryExpressionContext):
        n_pp = len(ctx.PlusPlus() or [])
        n_mm = len(ctx.MinusMinus() or [])

        if ctx.postfixExpression() is not None:
            base = self.visit(ctx.postfixExpression())
            if (n_pp or n_mm) and base is not None:
                pfe = ctx.postfixExpression()
                if (pfe.primaryExpression() is not None
                        and not pfe.LeftBracket() and not pfe.Dot()
                        and not pfe.Arrow() and not pfe.LeftParen()):
                    pe = pfe.primaryExpression()
                    if pe.Identifier() is not None:
                        name = pe.Identifier().getText()
                        val = self._read(name)
                        if n_pp:
                            val = val + Expr.integer(n_pp)
                        if n_mm:
                            val = val - Expr.integer(n_mm)
                        self._write(name, val)
                        return val
            return base

        if ctx.unaryOperator() is not None:
            operand = self.visit(ctx.castExpression())
            if operand is None:
                return Expr.id(ctx.getText())
            op = ctx.unaryOperator()
            if op.Minus() is not None:
                return -operand
            if op.Plus() is not None:
                return operand
            if op.Not() is not None:
                if operand.is_singular:
                    return Expr(CNot(operand._exprs[0]), DataType.int)
                return operand
            if op.Tilde() is not None:
                return ~operand
            return Expr.id(ctx.getText())

        return Expr.id(ctx.getText())

    def visitPostfixExpression(self, ctx: CParser.PostfixExpressionContext):
        if ctx.primaryExpression() is None:
            return Expr.id('_compound_literal_')

        pe = ctx.primaryExpression()
        base = self.visit(pe)
        if base is None:
            return Expr.id(pe.getText())

        # Track the base identifier name for postfix ++/-- side effects.
        # Cleared as soon as any suffix ([], (), ->, .) is consumed.
        base_name: str | None = pe.Identifier().getText() if pe.Identifier() is not None else None

        children = ctx.children or []
        i = 1  # skip primaryExpression

        while i < len(children):
            child = children[i]
            if not hasattr(child, 'symbol'):
                i += 1
                continue
            ttype = child.symbol.type

            if ttype == CParser.LeftBracket:
                # arr[idx]  — Phase 3: look up in array_state if concrete
                base_name = None
                if i + 1 < len(children):
                    idx = self.visit(children[i + 1])
                    if idx is not None and base.is_singular:
                        idx_int = self._to_int(idx)
                        base_sym = base._exprs[0]
                        if (idx_int is not None
                                and isinstance(base_sym, sympy.Symbol)
                                and base_sym.name in self.array_state
                                and idx_int in self.array_state[base_sym.name]):
                            base = self.array_state[base_sym.name][idx_int]
                        elif idx.is_singular:
                            base = Expr(CArrayIndex(base_sym, idx._exprs[0]),
                                        DataType.undefined)
                i += 3

            elif ttype == CParser.LeftParen:
                # func(args...)
                base_name = None
                args: list[Expr] = []
                j = i + 1
                while j < len(children):
                    c = children[j]
                    if hasattr(c, 'symbol') and c.symbol.type == CParser.RightParen:
                        break
                    if isinstance(c, CParser.ArgumentExpressionListContext):
                        args = [self.visit(a) for a in c.assignmentExpression()]
                        args = [a for a in args if a is not None]
                    j += 1
                fn_name = None
                if base.is_singular and isinstance(base._exprs[0], sympy.Symbol):
                    fn_name = base._exprs[0].name
                if fn_name:
                    base = self._dispatch_function(fn_name, args)
                i = j + 1

            elif ttype == CParser.Arrow:
                # ptr->field  — Phase 4: look up in struct_state
                base_name = None
                if i + 1 < len(children):
                    field = children[i + 1].getText()
                    if base.is_singular and isinstance(base._exprs[0], sympy.Symbol):
                        obj = base._exprs[0].name
                        if obj in self.struct_state and field in self.struct_state[obj]:
                            base = self.struct_state[obj][field]
                        else:
                            base = Expr(CPointerAccess(base._exprs[0], sympy.Symbol(field)),
                                        DataType.undefined)
                    elif base.is_singular:
                        base = Expr(CPointerAccess(base._exprs[0], sympy.Symbol(field)),
                                    DataType.undefined)
                i += 2

            elif ttype == CParser.Dot:
                # obj.field  — Phase 4: look up in struct_state
                base_name = None
                if i + 1 < len(children):
                    field = children[i + 1].getText()
                    if base.is_singular and isinstance(base._exprs[0], sympy.Symbol):
                        obj = base._exprs[0].name
                        if obj in self.struct_state and field in self.struct_state[obj]:
                            base = self.struct_state[obj][field]
                        else:
                            base = Expr(CStructAccess(base._exprs[0], sympy.Symbol(field)),
                                        DataType.undefined)
                    elif base.is_singular:
                        base = Expr(CStructAccess(base._exprs[0], sympy.Symbol(field)),
                                    DataType.undefined)
                i += 2

            elif ttype in (CParser.PlusPlus, CParser.MinusMinus):
                # post-increment/decrement: side effect, return old value
                saved = base
                if base_name is not None:
                    old = self._read(base_name)
                    if ttype == CParser.PlusPlus:
                        self._write(base_name, old + Expr.integer(1))
                    else:
                        self._write(base_name, old - Expr.integer(1))
                base = saved
                i += 1

            else:
                i += 1

        return base

    def visitPrimaryExpression(self, ctx: CParser.PrimaryExpressionContext):
        if ctx.Identifier() is not None:
            return self._read(ctx.Identifier().getText())
        if ctx.Constant() is not None:
            return _parse_constant(ctx.Constant().getText())
        if ctx.StringLiteral():
            return Expr.string(''.join(s.getText() for s in ctx.StringLiteral()))
        if ctx.expression() is not None:
            return self.visit(ctx.expression())
        return Expr.id(ctx.getText())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate_c_block(
    block: str,
    known: dict[str, Expr] | None = None,
    instrument_parameters=(),
    user_types: list[str] | None = None,
    verbose: bool = False,
) -> dict[str, Expr]:
    """Parse and evaluate a C compound statement, returning updated scalar state.

    Args:
        block: C source (bare block body or full ``{ ... }`` compound statement).
        known: initial variable bindings.
        instrument_parameters: objects with ``.name`` → become McCodeParameter symbols.
        user_types: typedef names already in scope.
        verbose: enable debug logging.

    Returns:
        dict mapping scalar variable names to their final symbolic ``Expr`` values.
        Array and struct state are tracked internally and visible through
        ``evaluator.array_state`` / ``evaluator.struct_state`` if you need them
        (use ``CBlockEvaluator`` directly in that case).
    """
    from antlr4 import InputStream, CommonTokenStream
    from antlr4.error.ErrorListener import ErrorListener
    from ..grammar import CLexer
    from .c_listener import make_error_listener

    if known is None:
        known = {}

    text = block if block.lstrip().startswith('{') else f'{{\n{block}\n}}'

    stream = InputStream(text)
    lexer = CLexer(stream)
    tokens = CommonTokenStream(lexer)
    parser = CParser(tokens)
    parser.addErrorListener(make_error_listener(ErrorListener, text))
    tree = parser.compoundStatement()

    evaluator = CBlockEvaluator(known, instrument_parameters, verbose=verbose)
    evaluator.visit(tree)
    return evaluator.state

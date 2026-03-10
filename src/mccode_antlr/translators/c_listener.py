from __future__ import annotations
from dataclasses import dataclass, field
from typing import TypeVar

from loguru import logger
from ..grammar import CParser, McInstrParser, CVisitor
from ..instr import InstrVisitor
from ..common import Expr

def string_between_tokens(start_token, stop_token):
    stream = start_token.getInputStream()
    return stream.getText(start_token.start, stop_token.stop)


def literal_string(ctx, until=None):
    if until is None:
        until = ctx
    return string_between_tokens(ctx.start, until.stop)


def make_error_listener(super_class, source: str, pre=5, post=2):
    class ErrorListener(super_class):
        def __init__(self):
            self.source = source
            self.pre = pre
            self.post = post

        def syntaxError(self, recognizer, offendingSymbol, *args, **kwargs):
            if len(args) == 4 and isinstance(args[3], str):
                # The 'speedy-antlr' syntax
                char_index, line, column, msg = args
            else:
                # the antlr4 (4.13.0) syntax
                line, column, msg, e = args
            logger.error(f'Syntax error in parsing {line},{column}')
            lines = self.source.split('\n')
            pre_lines = lines[line-self.pre:line]
            post_lines = lines[line:line+self.post]
            for line in pre_lines:
                logger.info(line)
            logger.error('~'*column + '^ ' + str(msg))
            for line in post_lines:
                logger.info(line)

    return ErrorListener()

TCDeclarator = TypeVar('TCDeclarator', bound='CDeclarator')
TCFuncPointer = TypeVar('TCFuncPointer', bound='CFuncPointer')

def not_both_None_or_not_equal(a, b):
    if (a is None and b is not None) or (a is not None and b is None):
        return False
    return a is not None and b is not None and a != b

def same_type(a, b):
    return type(a) == type(b)

@dataclass
class CFuncPointer:
    declare: TCDeclarator
    modifiers: str | None = None
    args: str | None = None

    @property
    def name(self) -> str:
        return self.declare.name

    def copy(self, suffix: str | None = None) -> TCFuncPointer:
        return CFuncPointer(
            declare=self.declare.copy(suffix=suffix),
            modifiers=self.modifiers,
            args=self.args,
        )

    def __eq__(self, other: TCFuncPointer) -> bool:
        if not isinstance(other, CFuncPointer):
            raise ValueError('Type mismatch')
        if not_both_None_or_not_equal(self.args, other.args):
            return False
        if not_both_None_or_not_equal(self.modifiers, other.modifiers):
            return False
        return self.declare == other.declare

    def string(self, dec_str):
        f = f'({self.modifiers} {dec_str})' if self.modifiers else f'({dec_str})'
        return f'{f}({self.args})' if self.args else f'{f}()'

    def __str__(self):
        return self.string(str(self.declare))

    def __hash__(self):
        return hash(str(self))

    def as_struct_member(self, dims: int, max_array_length):
        dec = self.declare.as_struct_member(dims=dims, max_array_length=max_array_length)
        return self.string(dec)


@dataclass
class CDeclarator:
    declare: str | CFuncPointer
    pointer: str | None = None
    extensions: list[str] = field(default_factory=list)
    elements: tuple[int,...] | tuple[str,...] | None = None
    dtype: str | None = None
    init: str | None = None

    def __post_init__(self):
        if self.elements is not None and not isinstance(self.elements, tuple):
            self.elements = tuple(self.elements)

    @property
    def is_pointer(self) -> bool:
        return self.pointer is not None and len(self.pointer.strip(' ')) > 0

    @property
    def is_array(self) -> bool:
        if self.elements is not None:
            return True
        # jump through the CFuncPointer to its CDeclarator
        return isinstance(self.declare, CFuncPointer) and self.declare.declare.is_array

    @property
    def name(self) -> str:
        return self.declare if isinstance(self.declare, str) else self.declare.name

    def copy(self, suffix: str | None = None) -> TCDeclarator:
        dec = self.declare
        if suffix is not None and isinstance(self.declare, str):
            dec = f'{self.declare}_{suffix}'
        elif suffix is not None:
            dec = self.declare.copy(suffix=suffix)
        return CDeclarator(
            pointer=self.pointer,
            declare=dec,
            extensions=[x for x in self.extensions],
            elements=self.elements,
            dtype=self.dtype,
            init=self.init,
        )

    def __eq__(self, other: TCDeclarator):
        if not isinstance(other, CDeclarator):
            raise ValueError('Type mismatch')
        if len(self.extensions) != len(other.extensions):
            return False
        for a, b in zip(self.extensions, other.extensions):
            if a != b:
                return False
        for a, b in zip((self.pointer, self.elements, self.dtype, self.init),
                        (other.pointer, other.elements, other.dtype, other.init)):
            if not_both_None_or_not_equal(a, b):
                return False
        return same_type(self.declare, other.declare) and self.declare == other.declare

    def string(self, dec_str):
        ext = " ".join(f'{x}' for x in self.extensions)
        dec = f'{dec_str} {ext}' if len(ext) else f'{dec_str}'
        if self.pointer:
            dec = f'{self.pointer} {dec}'
        if self.dtype:
            dec = f'{self.dtype} {dec}'
        return dec

    def __str__(self):
        return self.string(str(self.declare))

    def __hash__(self):
        return hash(str(self))

    def as_struct_member(self, dims: int = 0, max_array_length: int = 16384):
        if self.init:
            max_array_length = extract_initializer_size(self.init)
        dims = len(self.elements) if self.elements else 0
        mal = max_array_length if isinstance(max_array_length, tuple) else (max_array_length,)
        if len(mal) < dims:
            mal *= dims // len(mal)
        no = self.elements if self.elements else mal
        if not isinstance(no, tuple):
            raise RuntimeError(f'{no} should be a tuple but is a {type(no)}')
        if isinstance(self.declare, CFuncPointer):
            return self.string(self.declare.as_struct_member(dims=dims, max_array_length=no))
        elif self.elements is not None:
            if 0 in no:
                # Is this a bad idea?
                no = tuple(m if x == 0 else x for x, m in zip(no, mal))
            return f"{self}{''.join(f'[{n}]' for n in no)}"
        return str(self)


def extract_initializer_size(init: str) -> tuple[int,...]:
    """Assuming that the provided initializer string is for an array, possibly
    of more statically sized arrays, and that it has been written correctly,
    extract the size of each nested dimension

    >>> extract_initializer_size("{{0, 1, 2}, {3, 4, 5}}")
    (2, 3)

    >>> extract_initializer_size('{{{0}, {1}}, {{2}, {3}}, {{4}, {5}}, {{6}, {7}}}')
    (4, 2, 1)
    """
    import re
    size = []
    inner = re.compile('{([^{}]*)}')
    x = init
    while len(y:=inner.findall(x)):
        size.append(len(y[0].split(',')))
        x = inner.sub('_', x)
    return tuple(reversed(size))


class DeclaresCVisitor(CVisitor):
    def __init__(self, typedefs: list | None = None, verbose: bool = False):
        self.verbose = verbose
        self.typedefs = [x for x in typedefs] if typedefs else []
        self.declares = []

    def debug(self, message):
        if self.verbose:
            logger.debug(message)

    def info(self, message):
        if self.verbose:
            logger.info(message)

    def visitDeclaration(self, ctx:CParser.DeclarationContext):
        if ctx.staticAssertDeclaration() is not None:
            return
        #
        specs = [self.visit(x) for x in ctx.declarationSpecifiers().declarationSpecifier()]
        if ctx.initDeclaratorList() is not None:
            inits = [self.visit(x) for x in ctx.initDeclaratorList().initDeclarator()]
        else:
            inits = []

        if 'typedef' in specs:
            # this _is_ a typedef statement.
            # It (probably) is of the form
            #   typedef typeInformation aliasIdentifier;
            if specs[0] != 'typedef':
                self.debug(f"Expected typedef ... identifier; not\n{literal_string(ctx)}")
            if len(inits):
                self.debug(f'Expected no initializer with typedef, but found {inits}')
            alias = specs[-1]
            if alias in self.typedefs:
                self.info(f'Re-definition of typedef alias {alias}?')
            self.typedefs.append(alias)
        elif len(inits):
            for decl, init in inits:
                decl.dtype = ' '.join(specs)
                decl.init = init
                self.declares.append(decl)
        elif len(specs) > 1:
            decl = CDeclarator(pointer=None, declare=specs[-1], extensions=[])
            decl.dtype = ' '.join(specs[:-1])
            self.declares.append(decl)

    # Five declaration specifiers
    def visitStorageClassSpecifier(self, ctx:CParser.StorageClassSpecifierContext):
        self.debug(f'StorageClassSpecifier {literal_string(ctx)}')
        return literal_string(ctx)

    def visitTypeSpecifier(self, ctx:CParser.TypeSpecifierContext):
        if (c := ctx.atomicTypeSpecifier()) is not None:
            return self.visit(c)
        if (c := ctx.structOrUnionSpecifier()) is not None:
            return self.visit(c)
        if (c := ctx.enumSpecifier()) is not None:
            return self.visit(c)
        if (c := ctx.typedefName()) is not None:
            return self.visit(c)
        if (c := ctx.constantExpression()) is not None:
            return f'__typeof__({self.visit(c)}'
        return literal_string(ctx)

    # Keep going from here
    def visitTypeQualifier(self, ctx:CParser.TypeQualifierContext):
        self.debug(f'typeQualifier {literal_string(ctx)}')
        return literal_string(ctx)

    def visitFunctionSpecifier(self, ctx:CParser.FunctionSpecifierContext):
        self.debug(f'functionSpecifier {literal_string(ctx)}')
        return literal_string(ctx)

    def visitAlignmentSpecifier(self, ctx:CParser.AlignmentSpecifierContext):
        self.debug(f'alignmentSpecifier {literal_string(ctx)}')
        return literal_string(ctx)

    # initDeclarator
    def visitInitDeclarator(self, ctx:CParser.InitDeclaratorContext):
        # declarator ( '=' initializer )?
        decl = self.visit(ctx.declarator())
        init = self.visit(ctx.initializer()) if ctx.initializer() else None
        return decl, init

    def visitAtomicTypeSpecifier(self, ctx:CParser.AtomicTypeSpecifierContext):
        self.debug(f'AtomicTypeSpecifier {literal_string(ctx)}')
        return literal_string(ctx)

    def visitStructOrUnionSpecifier(self, ctx:CParser.StructOrUnionContext):
        self.debug(f'StructOrUnion {literal_string(ctx)}')
        return literal_string(ctx)

    def visitEnumSpecifier(self, ctx:CParser.EnumSpecifierContext):
        self.debug(f'EnumSpecifier {literal_string(ctx)}')
        return literal_string(ctx)

    def visitTypedefName(self, ctx:CParser.TypedefNameContext):
        self.debug(f'TypedefName {literal_string(ctx)}')
        return literal_string(ctx)

    def visitConstantExpression(self, ctx:CParser.ConstantExpressionContext):
        a = ctx.conditionalExpression()
        self.debug(f'ConstantExpression {literal_string(ctx)}')
        return literal_string(a)

    def visitInitializer(self, ctx:CParser.InitializerContext):
        self.debug(f'Initializer {literal_string(ctx)}')
        return literal_string(ctx)

    def visitDeclarator(self, ctx:CParser.DeclaratorContext):
        ptr = self.visit(ctx.pointer()) if ctx.pointer() else None
        dec = self.visit(ctx.directDeclarator())
        extensions = [self.visit(x) for x in ctx.gccDeclaratorExtension()]
        elements = None
        if isinstance(dec, CFuncPointer):
            # elements = dec.declare.elements
            # dec.declare.elements = None
            pass
        elif all(x in dec for x in ('[', ']')):
            dec, post = dec.split('[', 1)
            nums = tuple()
            while ']' in post:
                num, post = post.split(']', 1)
                nums += (num,)
                if '[' in post:
                    _, post = post.split('[', 1)
            try:
                elements = tuple(int(n) if len(n) else 0 for n in nums)
            except ValueError as er:
                logger.info(f"Could not convert an integer from {nums} due to {er}")
                elements = nums
        return CDeclarator(pointer=ptr, declare=dec, extensions=extensions, elements=elements)

    def visitPointer(self, ctx:CParser.PointerContext):
        self.debug(f'pointer {literal_string(ctx)}')
        return literal_string(ctx)

    def visitDirectDeclarator(self, ctx:CParser.DirectDeclaratorContext):
        if ctx.declarator():
            # this _is_ a function pointer declarator, right?
            modifiers = literal_string(ctx.vcSpecificModifer()) if ctx.vcSpecificModifer() else None
            return CFuncPointer(self.visit(ctx.declarator()), modifiers=modifiers)
        if ctx.Identifier():
            return literal_string(ctx)

        dd = ctx.directDeclarator()
        after_dd_str = literal_string(ctx).replace(literal_string(dd), '')
        dec = self.visit(dd)
        if isinstance(dec, CFuncPointer):
            dec.args = after_dd_str.strip('()')
            return dec
        return dec + after_dd_str


def extract_c_declared_variables_and_defined_types(
        block: str, user_types: list = None, verbose=False
) -> tuple[list[CDeclarator], list[str]]:
    from antlr4 import InputStream, CommonTokenStream
    from antlr4.error.ErrorListener import ErrorListener
    from ..grammar import CLexer
    stream = InputStream(block)
    lexer = CLexer(stream)
    tokens = CommonTokenStream(lexer)
    parser = CParser(tokens)
    parser.addErrorListener(make_error_listener(ErrorListener, block))
    tree = parser.compilationUnit()
    visitor = DeclaresCVisitor(user_types, verbose=verbose)
    visitor.visitCompilationUnit(tree)
    return visitor.declares, visitor.typedefs


def extract_c_declared_variables(
        block: str, user_types: list = None, verbose=False
) -> list[CDeclarator]:
    variables, _ = extract_c_declared_variables_and_defined_types(block, user_types, verbose=verbose)
    return variables

def extract_c_defined_types(
        block: str, user_types: list = None, verbose=False
) -> list[str]:
    _, types = extract_c_declared_variables_and_defined_types(block, user_types, verbose=verbose)
    return types


def extract_c_defined_then_declared_variables(
        defined_in_block: str, declared_in_block
) -> list[CDeclarator]:
    _, defined_in_types = extract_c_declared_variables_and_defined_types(defined_in_block)
    return extract_c_declared_variables(declared_in_block, user_types=defined_in_types)


class EvalCVisitor(InstrVisitor):
    def __init__(self, found: dict = None, verbose=False):
        super().__init__(None, None)
        self.verbose = verbose
        self.assigned = {} if found is None else found
        self.prog = []

    def debug(self, message):
        if self.verbose:
            logger.debug(message)

    def visitAssignment(self, ctx: McInstrParser.AssignmentContext):
        name = str(ctx.Identifier())
        value = self.visit(ctx.expr())
        self.prog.append((name, value))
        self.assigned[name] = value
        self.debug(f'{literal_string(ctx)} -> {name} = {value}')

    def visitExpressionIdentifier(self, ctx: McInstrParser.ExpressionIdentifierContext):
        from ..common import Expr
        # check if we already have a value for this identifier and insert it if we do:
        name = str(ctx.Identifier())
        if name in self.assigned:
            return self.assigned[name]
        return Expr.id(name)


def evaluate_c_defined_variables(
        variables: dict[str, str],
        initialized_in: str,
        known: dict[str, Expr] = None,
        verbose=False
):
    """Evaluate individual statements from C-like source in an attempt to find values for the provided variables"""
    from antlr4 import InputStream
    from ..grammar import McInstr_parse, McInstr_ErrorListener
    from ..common import Expr, DataType
    lines = [f'{line};' for line in initialized_in.split(';') if len(line.strip())]
    found = {} if known is None else known
    for line in lines:
        tree = McInstr_parse(InputStream(line), 'assignment', make_error_listener(McInstr_ErrorListener, line))
        visitor = EvalCVisitor(found=found, verbose=verbose)
        visitor.visitAssignment(tree)
        found = visitor.assigned

    def get_found(name, data_type):
        expr = found.get(name, Expr.id(name)).simplify()
        if expr.is_singular:
            expr.data_type = DataType.from_name(data_type)
        return expr

    return {v: get_found(v, data_type) for v, data_type in variables.items()}


def _get_expr(type_name: str, initial_value: str) -> Expr:
    from ..common import DataType
    expr = Expr._null() if initial_value is None else Expr.parse(initial_value)
    expr.data_type = DataType.from_name(type_name)
    return expr


def extract_c_declared_expressions(
        block: str, user_types: list = None, verbose=False
) -> dict[CDeclarator, Expr]:
    variables = extract_c_declared_variables(block, user_types, verbose=verbose)
    return {d: _get_expr(d.dtype, d.init) for d in variables}


def evaluate_c_defined_expressions(
        variables: dict[str, Expr], initialized_in: str, verbose=False
) -> dict[str, Expr]:
    """For defined identifiers, evaluate a (simple) block of C code to determine the end values of the identifiers"""
    names_types = {name: expr.data_type.name for name, expr in variables.items()}
    return evaluate_c_defined_variables(names_types, initialized_in, known=variables, verbose=verbose)

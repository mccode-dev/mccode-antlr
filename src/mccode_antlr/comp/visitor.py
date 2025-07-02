from http.client import UnimplementedFileMode

from loguru import logger

from ..grammar import McCompParser as Parser, McCompVisitor
from .comp import Comp
from ..common import ComponentParameter, Expr, MetaData
from ..common.visitor import add_common_visitors
from ..grammar.McCompParser import McCompParser


class CompVisitor(McCompVisitor):
    def __init__(self, parent, filename, instance_name=None):
        self.parent = parent  # the instrument (handler?) that wanted to read this component
        self.filename = filename
        self.state = Comp()
        self.instance_name = instance_name

    def visitProg(self, ctx: Parser.ProgContext):
        self.state = Comp()
        self.visit(ctx.component_definition())
        return self.state

    def visitComponentDefineNew(self, ctx: Parser.ComponentDefineNewContext):
        self.state.name = str(ctx.Identifier())
        if ctx.NoAcc() is not None:
            self.state.no_acc()
        self.visitChildren(ctx)  # Use the visitor methods to fill in details of the state

    def visitComponentDefineCopy(self, ctx: Parser.ComponentDefineCopyContext):
        from copy import deepcopy
        new_name, copy_from = [str(x) for x in ctx.Identifier()]
        if self.parent is None:
            raise RuntimeError("Can not copy a component definition without a parent instrument")
        copy_from_comp = self.parent.get_component(copy_from)
        # pull from that component ... deepcopy _just_ in case
        self.state = deepcopy(copy_from_comp)
        # update the name to match what we're going to call this component
        self.state.name = new_name
        # add parameters, overwrite all provided details
        if ctx.NoAcc() is not None:
            self.state.no_acc()
        self.visitChildren(ctx)  # Use the visitor methods to overwrite details of the state

    def visitCategory(self, ctx: Parser.CategoryContext):
        # Return the provided identifier or string literal, minus quotes
        self.state.category = str(ctx.StringLiteral())[1:-1] if ctx.Identifier() is None else str(ctx.Identifer())

    def visitComponent_define_parameters(self, ctx: Parser.Component_define_parametersContext):
        for parameter in self.visit(ctx.component_parameters()):
            self.state.add_define(parameter)

    def visitComponent_set_parameters(self, ctx: Parser.Component_set_parametersContext):
        for parameter in self.visit(ctx.component_parameters()):
            self.state.add_setting(parameter)

    def visitComponent_out_parameters(self, ctx: Parser.Component_out_parametersContext):
        for parameter in self.visit(ctx.component_parameters()):
            self.state.add_output(parameter)

    def visitComponent_parameters(self, ctx: Parser.Component_parametersContext):
        return [self.visit(x) for x in ctx.component_parameter()]

    def visitComponentParameterDouble(self, ctx: Parser.ComponentParameterDoubleContext):
        name = str(ctx.Identifier())
        value = None
        if ctx.Assign() is not None:
            # protect against a literal '0' provided ... which doesn't match IntegerLiteral for some reason
            value = 0 if ctx.expr() is None else self.visit(ctx.expr())
        return ComponentParameter(name=name, value=Expr.float(value))

    def visitComponentParameterInteger(self, ctx: Parser.ComponentParameterIntegerContext):
        name = str(ctx.Identifier())
        value = None
        if ctx.Assign() is not None:
            # protect against a literal '0' provided ... which doesn't match IntegerLiteral for some reason
            value = 0 if ctx.expr() is None else self.visit(ctx.expr())
        return ComponentParameter(name=name, value=Expr.int(value))

    def visitComponentParameterString(self, ctx: Parser.ComponentParameterStringContext):
        name = str(ctx.Identifier())
        default = None
        if ctx.Assign() is not None:
            default = 'NULL' if ctx.StringLiteral() is None else str(ctx.StringLiteral())
        return ComponentParameter(name=name, value=Expr.str(default))

    def visitComponentParameterVector(self, ctx: Parser.ComponentParameterVectorContext):
        from ..common import Value, DataType, ShapeType
        name = str(ctx.Identifier(0))
        if ctx.Assign() is not None and ctx.initializerlist() is not None:
            value = self.visit(ctx.initializerlist())
            value.data_type = DataType.float
        else:
            default = None
            if ctx.Assign() is not None:
                default = "NULL"
                if ctx.Identifier(1) is not None:
                    default = str(ctx.Identifier(1))
            value = Expr(Value(default, DataType.float, _shape=ShapeType.vector))
        return ComponentParameter(name=name, value=value)

    def visitComponentParameterSymbol(self, ctx: Parser.ComponentParameterSymbolContext):
        raise RuntimeError("McCode symbol parameter type not supported yet")

    def visitComponentParameterDoubleArray(self, ctx: Parser.ComponentParameterDoubleArrayContext):
        # 'vector' is really just an alias for 'double *', right?
        return self.visitComponentParameterVector(ctx)

    def visitComponentParameterIntegerArray(self, ctx: Parser.ComponentParameterIntegerArrayContext):
        from ..common import Value, DataType, ShapeType
        name = str(ctx.Identifier(0))
        if ctx.assign() is not None and ctx.initializerlist() is not None:
            value = self.visit(ctx.initializerlist())
            value.data_type = DataType.int
        else:
            default = None
            if ctx.assign() is not None:
                default = "NULL"
                if ctx.Identifier(1) is not None:
                    default = str(ctx.Identifier(1))
            value = Expr(Value(default, DataType.int, _shape=ShapeType.vector))
        return ComponentParameter(name=name, value=value)

    def visitDependency(self, ctx: Parser.DependencyContext):
        if ctx.StringLiteral() is not None:
            # the flags are the literal string without its quotes:
            self.parent.add_c_flags(str(ctx.StringLiteral()).strip('"'))

    def visitComponent_trace(self, ctx: McCompParser.Component_traceContext):
        self.state.TRACE(*self.multi_block("trace", ctx.multi_block()))

    def visitDeclare(self, ctx:McCompParser.DeclareContext):
        self.state.DECLARE(*self.multi_block("declare", ctx.multi_block()))

    def visitShare(self, ctx:McCompParser.ShareContext):
        self.state.SHARE(*self.multi_block("share", ctx.multi_block()))

    def visitInitialise(self, ctx:McCompParser.InitialiseContext):
        self.state.INITIALIZE(*self.multi_block("initialize", ctx.multi_block()))

    def visitUservars(self, ctx: Parser.UservarsContext):
        self.state.USERVARS(*self.multi_block("user", ctx.multi_block()))

    def visitSave(self, ctx:McCompParser.SaveContext):
        self.state.SAVE(*self.multi_block("save", ctx.multi_block()))

    def visitFinally(self, ctx:McCompParser.FinallyContext):
        self.state.FINALLY(*self.multi_block("final", ctx.multi_block()))

    def visitDisplay(self, ctx:McCompParser.DisplayContext):
        self.state.DISPLAY(*self.multi_block("display", ctx.multi_block()))

    def visitMetadata(self, ctx: Parser.MetadataContext):
        filename, line_number, metadata = self.visit(ctx.unparsed_block())
        mime = ctx.mime.text if ctx.mime.type == Parser.Identifier else ctx.mime.text[1:-1]
        name = ctx.name.text if ctx.name.type == Parser.Identifier else ctx.name.text[1:-1]
        metadata = MetaData.from_component_tokens(source=self.state.name, mimetype=mime, name=name, value=metadata)
        self.state.add_metadata(metadata)

    def visitUnparsed_block(self, ctx: Parser.Unparsed_blockContext):
        # We want to extract the source-file line number (and filename) for use in the C-preprocessor
        # via `#line {number} "{filename}"` directives, for more expressive error handling
        line_number = None if ctx.start is None else ctx.start.line
        content = str(ctx.UnparsedBlock())[2:-2]
        return self.filename, line_number, content

    # FIXME There *are* no statements in McCode, so all identifiers always produce un-parsable values.
    def visitAssignment(self, ctx: Parser.AssignmentContext):
        line_number = None if ctx.start is None else ctx.start.line
        raise RuntimeError(f"{self.filename}: {line_number} -- assignment statements are not (yet) supported")

    def visitExpressionPrevious(self, ctx: Parser.ExpressionPreviousContext):
        # The very-special no-good expression use of PREVIOUS where it is replaced by the last component's name
        raise RuntimeError('PREVIOUS is not a valid expression in Comp definitions')

    def visitExpressionMyself(self, ctx: Parser.ExpressionMyselfContext):
        # The even-worse expression use of MYSELF to refer to the current being-constructed component's name
        return Expr.str(self.instance.name)

    def multi_block(self, part: str, ctx: Parser.Multi_blockContext):
        """Common visitor for {part} unparsed_block? ((INHERIT identifier)|(EXTEND unparsed_block))*

        Ensures that the correct 'part' is pulled from named component definition(s)
        and that the definitions and new unparsed blocks are inserted in their given
        order.
        """
        blocks = dict()
        for ident in ctx.Identifier():
            comp = self.parent.get_component(str(ident))
            blocks[ident.getSourceInterval()[0]] = getattr(comp, part)
        for unparsed in ctx.unparsed_block():
            blocks[unparsed.getSourceInterval()[0]] = (self.visit(unparsed),)
        return [b for n in sorted(blocks.keys()) for b in blocks[n]]



add_common_visitors(CompVisitor)
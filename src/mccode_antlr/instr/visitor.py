from __future__ import annotations
from ..grammar import McInstrParser, McInstrVisitor
from ..common import InstrumentParameter, MetaData, Expr, Mode
from ..common.visitor import add_common_visitors
from .instr import Instr
from .instance import Instance
from .jump import Jump
from loguru import logger


def literal_string(ctx):
    start_token, stop_token = ctx.start, ctx.stop
    stream = start_token.getInputStream()
    return stream.getText(start_token.start, stop_token.stop)


class InstrVisitor(McInstrVisitor):
    def __init__(self, parent, filename, destination=None, allow_assignment=False, mode: Mode | None = None):
        self.parent = parent
        self.filename = filename
        self.state = Instr()
        self.current_comp = None
        self.current_instance_name = None
        self.destination = destination
        self.mode = mode or Mode.normal

    def visitProg(self, ctx: McInstrParser.ProgContext):
        self.state = Instr()
        self.visit(ctx.instrument_definition())
        return self.state

    def visitInstrument_definition(self, ctx: McInstrParser.Instrument_definitionContext):
        self.state.name = str(ctx.Identifier())
        self.visitChildren(ctx)
        self.state.determine_groups()

    def visitInstrument_parameters(self, ctx: McInstrParser.Instrument_parametersContext):
        # The speedy-antlr-tool exposed Python parse tree doesn't know about/expose
        # the `ctx.params` property
        # -- but we can get the same information from a function call:
        params = ctx.instrument_parameter()
        for param in params:
            self.state.add_parameter(self.visit(param))

    def getInstrument_parameter(self, ctx: McInstrParser.Instrument_parameterContext):
        return self.visit(ctx)

    def visitInstrument_metadata(self, ctx: McInstrParser.Instrument_metadataContext):
        for metadata_context in ctx.metadata():
            mime, name, metadata = self.visit(metadata_context)
            metadata = MetaData.from_instrument_tokens(source=self.state.name, mimetype=mime, name=name, value=metadata)
            self.state.add_metadata(metadata)

    def visitInstrumentParameterDouble(self, ctx: McInstrParser.InstrumentParameterDoubleContext):
        name = str(ctx.Identifier())
        unit = None if ctx.instrument_parameter_unit() is None else self.visit(ctx.instrument_parameter_unit())
        value = None if ctx.Assign() is None else self.visit(ctx.expr())
        return InstrumentParameter(name, unit, Expr.float(value))

    def visitInstrumentParameterInteger(self, ctx: McInstrParser.InstrumentParameterIntegerContext):
        name = str(ctx.Identifier())
        unit = None if ctx.instrument_parameter_unit() is None else self.visit(ctx.instrument_parameter_unit())
        value = None if ctx.Assign() is None else self.visit(ctx.expr())
        return InstrumentParameter(name, unit, Expr.int(value))

    def visitInstrumentParameterString(self, ctx: McInstrParser.InstrumentParameterStringContext):
        name = str(ctx.Identifier())
        unit = None if ctx.instrument_parameter_unit() is None else self.visit(ctx.instrument_parameter_unit())
        value = None
        if ctx.Assign() is not None:
            value = 'NULL' if ctx.StringLiteral() is None else str(ctx.StringLiteral())
        return InstrumentParameter(name, unit, Expr.str(value))

    def visitInstrument_parameter_unit(self, ctx: McInstrParser.Instrument_parameter_unitContext):
        return str(ctx.StringLiteral())

    def visitInstrument_trace(self, ctx: McInstrParser.Instrument_traceContext):
        return self.visitChildren(ctx)

    def visitInstrument_trace_include(self, ctx: McInstrParser.Instrument_trace_includeContext):
        quoted_filename = str(ctx.StringLiteral())
        if self.destination is not None:
            logger.critical(f'including {quoted_filename} from {self.filename}, which is itself included from {self.destination.name}')
            logger.critical('Expect component referencing errors, as the implementation does not cover this use case.')
        instr = self.parent.get_instrument(quoted_filename.strip('"'), destination=self.state)
        # TODO work out how/what to copy from the other instrument into this one
        self.state.add_included(instr.name)
        for par in instr.parameters:
            self.state.add_parameter(par, ignore_repeated=True)
        for meta in instr.metadata:
            self.state.add_metadata(meta)
        if len(instr.declare):
            self.state.declare += instr.declare
        if len(instr.user):
            self.state.user += instr.user
        if len(instr.initialize):
            self.state.initialize += instr.initialize
        if len(instr.save):
            self.state.save += instr.save
        if len(instr.final):
            self.state.final += instr.final
        # McCode3 parsed everything in one memory space, so used some trickery to include
        # component instances from one instrument into another. Here we can be a bit more straightforward
        for instance in instr.components:
            if not instance.removable:
                self.state.add_component(instance)
        # Group membership is determined after all parsing, so nothing to do here

    def visitComponent_instance(self, ctx: McInstrParser.Component_instanceContext):
        from ..comp import Comp
        from ..instr.orientation import Angles
        name = self.visit(ctx.instance_name())
        self.current_instance_name = name
        comp = self.visit(ctx.component_type())
        if not isinstance(comp, (Comp, Instance)):
            raise RuntimeError(f'Undefined component type {type(comp)}')
        is_ref = isinstance(comp, Instance)
        self.current_comp = comp.type if is_ref else comp
        at = self.visit(ctx.place())
        if ctx.orientation() is not None:
            rotate = self.visit(ctx.orientation())
        else:
            # In the case of "AT (x, y, z) ABSOLUTE" or "AT (x, y, z) RELATIVE identifier"
            # We must use *the same* relative information for the rotation -- at[1] is None or a valid instance:
            rotate = (Angles(Expr.int(0), Expr.int(0), Expr.int(0)), at[1])
        # Construct a new instance, possibly copying values from an existing instance:
        instance = Instance.from_instance(name, comp, at, rotate) if is_ref else Instance(name, comp, at, rotate, mode=self.mode)
        if ctx.instance_parameters() is not None:
            for param_name, param_value in self.visit(ctx.instance_parameters()):
                instance.set_parameter(param_name, param_value, overwrite=is_ref)
        if ctx.Removable() is not None:
            instance.REMOVABLE()
        if ctx.Cpu() is not None:
            instance.CPU()
        if ctx.split() is not None:
            instance.SPLIT(self.visit(ctx.split()))
        if ctx.when() is not None:
            instance.WHEN(self.visit(ctx.when()))
        if ctx.groupref() is not None:
            instance.GROUP(self.visit(ctx.groupref()))
        if ctx.extend() is not None:
            instance.EXTEND(self.visit(ctx.extend()))
        if ctx.jumps() is not None:
            instance.JUMP(*self.visit(ctx.jumps()))
        if ctx.metadata() is not None:
            # deal with definition vs instance metadata here?
            for metadata_context in ctx.metadata():
                mime, name, metadata = self.visit(metadata_context)
                metadata = MetaData.from_instance_tokens(source=instance.name, mimetype=mime, name=name, value=metadata)
                instance.add_metadata(metadata)
        # Include this instantiated component instance in the instrument components list
        if self.destination is None or not instance.removable:
            # if this _is_ an included instrument, any REMOVABLE component instances should not be added
            # TODO we don't need to populate the whole Instance object if this branch is not selected
            self.state.add_component(instance)
        self.current_comp = None
        self.current_instance_name = None

    def visitInstanceNameCopyIdentifier(self, ctx: McInstrParser.InstanceNameCopyIdentifierContext):
        return f'{ctx.Identifier()}_{len(self.state.components)+1}'

    def visitInstanceNameCopy(self, ctx: McInstrParser.InstanceNameCopyContext):
        return f'Comp_{len(self.state.components) + 1}'

    def visitInstanceNameIdentifier(self, ctx: McInstrParser.InstanceNameIdentifierContext):
        return str(ctx.Identifier())

    def visitComponentTypeCopy(self, ctx: McInstrParser.ComponentTypeCopyContext):
        return self.visit(ctx.component_ref())

    def visitComponentTypeIdentifier(self, ctx: McInstrParser.ComponentTypeIdentifierContext):
        return self.parent.get_component(str(ctx.Identifier()), current_instance_name=self.current_instance_name)

    def visitInstance_parameters(self, ctx: McInstrParser.Instance_parametersContext):
        # `ctx.params` isn't exposed by speedy-antlr-tool
        # we muse use a function call instead
        return [self.visit(p) for p in ctx.instance_parameter()]

    def visitInstanceParameterExpr(self, ctx: McInstrParser.InstanceParameterExprContext):
        from ..common import DataType
        name = str(ctx.Identifier())
        value = self.visit(ctx.expr())
        default = self.current_comp.get_parameter(name)
        if default is None:
            raise RuntimeError(f'{name} is not a known DEFINITION or SETTING parameter for {self.current_comp.name}')
        if not value.is_op and DataType.undefined == value.data_type:
            value.data_type = default.value.data_type
            value.shape_type = default.value.shape_type
        return name, value

    def visitInstanceParameterNull(self, ctx: McInstrParser.InstanceParameterNullContext):
        from ..common import DataType
        name = str(ctx.Identifier())
        value = Expr.str('NULL')
        default = self.current_comp.get_parameter(name)
        if default is None:
            raise RuntimeError(f'{name} is not a known DEFINITION or SETTING parameter for {self.current_comp.name}')
        if DataType.undefined == value.data_type:
            value.data_type = default.value.data_type
        return name, value

    def visitInstanceParameterVector(self, ctx: McInstrParser.InstanceParameterVectorContext):
        from ..common import DataType
        name = str(ctx.Identifier())
        value = self.visit(ctx.initializerlist())
        value.data_type = DataType.float
        return name, value

    def visitSplit(self, ctx: McInstrParser.SplitContext):
        return Expr.int(10) if ctx.expr() is None else self.visit(ctx.expr())

    def visitWhen(self, ctx: McInstrParser.WhenContext):
        return self.visit(ctx.expr())

    def visitPlace(self, ctx: McInstrParser.PlaceContext):
        from mccode_antlr.instr.orientation import Vector
        vector = self.visit(ctx.coords())
        relative = self.visit(ctx.reference())
        return Vector(*vector), relative

    def visitOrientation(self, ctx: McInstrParser.OrientationContext):
        from mccode_antlr.instr.orientation import Angles
        angles = self.visit(ctx.coords())
        relative = self.visit(ctx.reference())
        return Angles(*angles), relative

    def visitGroupref(self, ctx: McInstrParser.GrouprefContext):
        return str(ctx.Identifier())

    def visitJumps(self, ctx: McInstrParser.JumpsContext):
        return [self.visit(j) for j in ctx.jump()]

    def visitJump(self, ctx: McInstrParser.JumpContext):
        name, index = self.visit(ctx.jumpname())
        iterate = ctx.Iterate() is not None  # and ctx.When() is None
        condition = self.visit(ctx.expr())
        return Jump(name, index, iterate, condition)

    def visitJumpPrevious(self, ctx: McInstrParser.JumpPreviousContext):
        i = ctx.IntegerLiteral()
        return ("PREVIOUS", -1) if i is None else (f"PREVIOUS_{i}", -int(i))

    def visitJumpMyself(self, ctx: McInstrParser.JumpMyselfContext):
        return "MYSELF", 0

    def visitJumpNext(self, ctx: McInstrParser.JumpNextContext):
        i = ctx.IntegerLiteral()
        return ("NEXT", 1) if i is None else (f"NEXT_{i}", int(i))

    def visitJumpIdentifier(self, ctx: McInstrParser.JumpIdentifierContext):
        return str(ctx.Identifier()), 0

    def visitComponent_ref(self, ctx: McInstrParser.Component_refContext):
        if ctx.Previous() is not None:
            count = 1 if ctx.IntegerLiteral() is None else int(str(ctx.IntegerLiteral()))
            # Any included component can be referred to -- REMOVABLE components in an included instrument
            # were _not_ included into the state. Include REMOVABLE components _are_ in the state.
            instances = len(self.state.components)
            if count <= instances:
                return self.state.last_component(count, removable_ok=True)
            elif self.destination is not None:
                return self.destination.last_component(count - instances, removable_ok=True)
            else:
                logger.error(f'Too large PREVIOUS count {count} for instrument with {instances} component instances')
        name = str(ctx.Identifier())
        if any(inst.name == name for inst in self.state.components):
            return self.state.get_component(name)
        elif self.destination is not None:
            return self.destination.get_component(name)
        else:
            logger.error(f'Unknown component reference for instance named {name}')

    def visitCoords(self, ctx: McInstrParser.CoordsContext):
        # FIXME 2023-10-16 previously Coordinate parsing forced all returned Expression objects to be floats
        #   while this is 'correct', it broke the ability to use instrument parameters in component placement
        #   and orientation expressions. I think expression parsing is now implemented correctly for all variants
        #   So _hopefully_ the explicit cast-to-float is not required any longer.
        # A coordinate is _always_ a float, even when represented by an expression or identifier
        # Actually implement the visitExpr variants correctly?
        # return tuple([Expr.float(self.visit(x)) for x in ctx.expr()])
        return tuple([self.visit(x) for x in ctx.expr()])

    def visitReference(self, ctx: McInstrParser.ReferenceContext):
        # ABSOLUTE or RELATIVE ABSOLUTE -> None
        return self.visit(ctx.component_ref()) if ctx.Absolute() is None else None

    def visitDependency(self, ctx: McInstrParser.DependencyContext):
        # store the flag without its surrounding quotes
        self.state.DEPENDENCY(str(ctx.StringLiteral())[1:-1])

    def visitDeclare(self, ctx:McInstrParser.DeclareContext):
        self.state.DECLARE(*self.multi_block("declare", ctx.multi_block()))

    def visitUservars(self, ctx: McInstrParser.UservarsContext):
        self.state.USERVARS(*self.multi_block("user", ctx.multi_block()))

    def visitInitialise(self, ctx:McInstrParser.InitialiseContext):
        self.state.INITIALIZE(*self.multi_block("initialize", ctx.multi_block()))

    def visitSave(self, ctx:McInstrParser.SaveContext):
        self.state.SAVE(*self.multi_block("save", ctx.multi_block()))

    def visitFinalize(self, ctx:McInstrParser.FinalizeContext):
        self.state.FINALLY(*self.multi_block("final", ctx.multi_block()))

    def visitExtend(self, ctx: McInstrParser.ExtendContext):
        return self.visit(ctx.unparsed_block())

    def visitMetadata(self, ctx: McInstrParser.MetadataContext):
        filename, line_number, metadata = self.visit(ctx.unparsed_block())
        # ctx.mime and ctx.name are _either_ identifiers (no double quotes) or string literals (double quotes)
        # so we need to strip the quotes from the string literals, but not the identifiers
        mime = ctx.mime.text if ctx.mime.type == McInstrParser.Identifier else ctx.mime.text[1:-1]
        name = ctx.name.text if ctx.name.type == McInstrParser.Identifier else ctx.name.text[1:-1]
        return mime, name, metadata

    def visitUnparsed_block(self, ctx: McInstrParser.Unparsed_blockContext):
        # We want to extract the source-file line number (and filename) for use in the C-preprocessor
        # via `#line {number} "{filename}"` directives, for more expressive error handling
        line_number = None if ctx.start is None else ctx.start.line
        if line_number is None:
            print(f'Why is line none for {self.filename} {ctx.UnparsedBlock()}')
        return self.filename, line_number,  str(ctx.UnparsedBlock())[2:-2]

    def visitShell(self, ctx: McInstrParser.ShellContext):
        from subprocess import run
        args = str(ctx.StringLiteral()).split(' ')
        run(args, shell=True, check=True)

    def visitSearchPath(self, ctx: McInstrParser.SearchPathContext):
        self.parent.handle_search_keyword(str(ctx.StringLiteral()))

    def visitSearchShell(self, ctx: McInstrParser.SearchShellContext):
        from subprocess import run
        args = str(ctx.StringLiteral()).split()
        res = run(args, shell=True, capture_output=True, check=True)
        for specs in res.stdout.decode().split('\n'):
            self.parent.handle_search_keyword(specs)

    # TODO Make this and the identical list of visitors in comp/visitor.py a single definition ... somehow
    # FIXME There *are* no statements in McCode, so all identifiers always produce un-parsable values.
    def visitAssignment(self, ctx: McInstrParser.AssignmentContext):
        line_number = None if ctx.start is None else ctx.start.line
        raise RuntimeError(
            f"{self.filename}: {line_number} -- assignment statements are not (yet) supported")

    def visitExpressionPrevious(self, ctx: McInstrParser.ExpressionPreviousContext):
        # The very-special no-good expression use of PREVIOUS where it is replaced by the last component's name
        if len(self.state.components):
            return Expr.str(self.state.components[-1].name)
        elif self.destination is not None and len(self.destination.components):
            return Expr.str(self.destination.components[-1].name)
        raise RuntimeError('PREVIOUS keyword used in expression before any components defined')

    def visitExpressionMyself(self, ctx: McInstrParser.ExpressionMyselfContext):
        # The even-worse expression use of MYSELF to refer to the current being-constructed component's name
        return Expr.str(self.current_instance.name)

    def multi_block(self, part: str, ctx: McInstrParser.Multi_blockContext):
        """Common visitor for {part} unparsed_block? ((INHERIT identifier)|(EXTEND unparsed_block))*

        Ensures that the correct 'part' is pulled from named component definition(s)
        and that the definitions and new unparsed blocks are inserted in their given
        order.
        """
        blocks = dict()
        for ident in ctx.Identifier():
            logger.info(f'Copy from component definition {ident} in Instr is ill defined')
            comp = self.state.get_component(str(ident))
            blocks[ident.getSourceInterval()[0]] = getattr(comp, part)
        for unparsed in ctx.unparsed_block():
            blocks[unparsed.getSourceInterval()[0]] = (self.visit(unparsed),)
        return [b for n in sorted(blocks.keys()) for b in blocks[n]]


class InstrParametersVisitor(McInstrVisitor):
    """A visitor which takes a full parse tree and extracts only the instrument parameters"""
    def __init__(self):
        self.state = Instr()

    def visitProg(self, ctx: McInstrParser.ProgContext):
        self.state = Instr()
        self.visit(ctx.instrument_definition())
        return self.state.parameters

    def visitInstrument_definition(self, ctx: McInstrParser.Instrument_definitionContext):
        self.state.name = str(ctx.Identifier())
        self.visitChildren(ctx)

    def visitInstrument_parameters(self, ctx: McInstrParser.Instrument_parametersContext):
        for param in ctx.instrument_parameter():
            self.state.add_parameter(self.visit(param))

    def visitInstrumentParameterDouble(self, ctx: McInstrParser.InstrumentParameterDoubleContext):
        name = str(ctx.Identifier())
        unit = None if ctx.instrument_parameter_unit() is None else self.visit(ctx.instrument_parameter_unit())
        value = None if ctx.Assign() is None else self.visit(ctx.expr())
        return InstrumentParameter(name, unit, Expr.float(value))

    def visitInstrumentParameterInteger(self, ctx: McInstrParser.InstrumentParameterIntegerContext):
        name = str(ctx.Identifier())
        unit = None if ctx.instrument_parameter_unit() is None else self.visit(ctx.instrument_parameter_unit())
        value = None if ctx.Assign() is None else self.visit(ctx.expr())
        return InstrumentParameter(name, unit, Expr.int(value))

    def visitInstrumentParameterString(self, ctx: McInstrParser.InstrumentParameterStringContext):
        name = str(ctx.Identifier())
        unit = None if ctx.instrument_parameter_unit() is None else self.visit(ctx.instrument_parameter_unit())
        value = None
        if ctx.Assign() is not None:
            value = 'NULL' if ctx.StringLiteral() is None else str(ctx.StringLiteral())
        return InstrumentParameter(name, unit, Expr.str(value))

    def visitInstrument_parameter_unit(self, ctx: McInstrParser.Instrument_parameter_unitContext):
        return str(ctx.StringLiteral())

    def visitExpressionPrevious(self, ctx: McInstrParser.ExpressionPreviousContext):
        # The very-special no-good expression use of PREVIOUS where it is replaced by the last component's name
        if len(self.state.components):
            return Expr.str(self.state.components[-1].name)
        elif self.destination is not None and len(self.destination.components):
            return Expr.str(self.destination.components[-1].name)
        raise RuntimeError('PREVIOUS keyword used in expression before any components defined')

    def visitExpressionMyself(self, ctx: McInstrParser.ExpressionMyselfContext):
        # The even-worse expression use of MYSELF to refer to the current being-constructed component's name
        return Expr.str(self.current_instance.name)



add_common_visitors(InstrVisitor)
add_common_visitors(InstrParametersVisitor)
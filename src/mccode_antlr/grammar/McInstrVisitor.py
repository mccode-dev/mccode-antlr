# Generated from McInstr.g4 by ANTLR 4.13.2
from antlr4 import *
if "." in __name__:
    from .McInstrParser import McInstrParser
else:
    from McInstrParser import McInstrParser

# This class defines a complete generic visitor for a parse tree produced by McInstrParser.

class McInstrVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by McInstrParser#prog.
    def visitProg(self, ctx:McInstrParser.ProgContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#instrument_definition.
    def visitInstrument_definition(self, ctx:McInstrParser.Instrument_definitionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#instrument_parameters.
    def visitInstrument_parameters(self, ctx:McInstrParser.Instrument_parametersContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#InstrumentParameterDouble.
    def visitInstrumentParameterDouble(self, ctx:McInstrParser.InstrumentParameterDoubleContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#InstrumentParameterInteger.
    def visitInstrumentParameterInteger(self, ctx:McInstrParser.InstrumentParameterIntegerContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#InstrumentParameterString.
    def visitInstrumentParameterString(self, ctx:McInstrParser.InstrumentParameterStringContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#instrument_parameter_unit.
    def visitInstrument_parameter_unit(self, ctx:McInstrParser.Instrument_parameter_unitContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#instrument_trace.
    def visitInstrument_trace(self, ctx:McInstrParser.Instrument_traceContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#instrument_metadata.
    def visitInstrument_metadata(self, ctx:McInstrParser.Instrument_metadataContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#instrument_trace_include.
    def visitInstrument_trace_include(self, ctx:McInstrParser.Instrument_trace_includeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#component_instance.
    def visitComponent_instance(self, ctx:McInstrParser.Component_instanceContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#InstanceNameCopyIdentifier.
    def visitInstanceNameCopyIdentifier(self, ctx:McInstrParser.InstanceNameCopyIdentifierContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#InstanceNameCopy.
    def visitInstanceNameCopy(self, ctx:McInstrParser.InstanceNameCopyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#InstanceNameIdentifier.
    def visitInstanceNameIdentifier(self, ctx:McInstrParser.InstanceNameIdentifierContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#ComponentTypeCopy.
    def visitComponentTypeCopy(self, ctx:McInstrParser.ComponentTypeCopyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#ComponentTypeIdentifier.
    def visitComponentTypeIdentifier(self, ctx:McInstrParser.ComponentTypeIdentifierContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#instance_parameters.
    def visitInstance_parameters(self, ctx:McInstrParser.Instance_parametersContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#InstanceParameterExpr.
    def visitInstanceParameterExpr(self, ctx:McInstrParser.InstanceParameterExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#InstanceParameterNull.
    def visitInstanceParameterNull(self, ctx:McInstrParser.InstanceParameterNullContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#InstanceParameterVector.
    def visitInstanceParameterVector(self, ctx:McInstrParser.InstanceParameterVectorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#split.
    def visitSplit(self, ctx:McInstrParser.SplitContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#when.
    def visitWhen(self, ctx:McInstrParser.WhenContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#place.
    def visitPlace(self, ctx:McInstrParser.PlaceContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#orientation.
    def visitOrientation(self, ctx:McInstrParser.OrientationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#groupref.
    def visitGroupref(self, ctx:McInstrParser.GrouprefContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#jumps.
    def visitJumps(self, ctx:McInstrParser.JumpsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#jump.
    def visitJump(self, ctx:McInstrParser.JumpContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#JumpPrevious.
    def visitJumpPrevious(self, ctx:McInstrParser.JumpPreviousContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#JumpMyself.
    def visitJumpMyself(self, ctx:McInstrParser.JumpMyselfContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#JumpNext.
    def visitJumpNext(self, ctx:McInstrParser.JumpNextContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#JumpIdentifier.
    def visitJumpIdentifier(self, ctx:McInstrParser.JumpIdentifierContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#extend.
    def visitExtend(self, ctx:McInstrParser.ExtendContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#component_ref.
    def visitComponent_ref(self, ctx:McInstrParser.Component_refContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#coords.
    def visitCoords(self, ctx:McInstrParser.CoordsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#reference.
    def visitReference(self, ctx:McInstrParser.ReferenceContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#dependency.
    def visitDependency(self, ctx:McInstrParser.DependencyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#declare.
    def visitDeclare(self, ctx:McInstrParser.DeclareContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#uservars.
    def visitUservars(self, ctx:McInstrParser.UservarsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#initialise.
    def visitInitialise(self, ctx:McInstrParser.InitialiseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#save.
    def visitSave(self, ctx:McInstrParser.SaveContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#Finally.
    def visitFinally(self, ctx:McInstrParser.FinallyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#multi_block.
    def visitMulti_block(self, ctx:McInstrParser.Multi_blockContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#metadata.
    def visitMetadata(self, ctx:McInstrParser.MetadataContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#category.
    def visitCategory(self, ctx:McInstrParser.CategoryContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#initializerlist.
    def visitInitializerlist(self, ctx:McInstrParser.InitializerlistContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#assignment.
    def visitAssignment(self, ctx:McInstrParser.AssignmentContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#ExpressionBinaryMod.
    def visitExpressionBinaryMod(self, ctx:McInstrParser.ExpressionBinaryModContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#ExpressionBinaryLess.
    def visitExpressionBinaryLess(self, ctx:McInstrParser.ExpressionBinaryLessContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#ExpressionBinaryGreater.
    def visitExpressionBinaryGreater(self, ctx:McInstrParser.ExpressionBinaryGreaterContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#ExpressionBinaryLessEqual.
    def visitExpressionBinaryLessEqual(self, ctx:McInstrParser.ExpressionBinaryLessEqualContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#ExpressionArrayAccess.
    def visitExpressionArrayAccess(self, ctx:McInstrParser.ExpressionArrayAccessContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#ExpressionBinaryLogic.
    def visitExpressionBinaryLogic(self, ctx:McInstrParser.ExpressionBinaryLogicContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#ExpressionInteger.
    def visitExpressionInteger(self, ctx:McInstrParser.ExpressionIntegerContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#ExpressionBinaryRightShift.
    def visitExpressionBinaryRightShift(self, ctx:McInstrParser.ExpressionBinaryRightShiftContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#ExpressionMyself.
    def visitExpressionMyself(self, ctx:McInstrParser.ExpressionMyselfContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#ExpressionPrevious.
    def visitExpressionPrevious(self, ctx:McInstrParser.ExpressionPreviousContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#ExpressionIdentifier.
    def visitExpressionIdentifier(self, ctx:McInstrParser.ExpressionIdentifierContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#ExpressionBinaryNotEqual.
    def visitExpressionBinaryNotEqual(self, ctx:McInstrParser.ExpressionBinaryNotEqualContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#ExpressionStructAccess.
    def visitExpressionStructAccess(self, ctx:McInstrParser.ExpressionStructAccessContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#ExpressionFunctionCall.
    def visitExpressionFunctionCall(self, ctx:McInstrParser.ExpressionFunctionCallContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#ExpressionBinaryMD.
    def visitExpressionBinaryMD(self, ctx:McInstrParser.ExpressionBinaryMDContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#ExpressionString.
    def visitExpressionString(self, ctx:McInstrParser.ExpressionStringContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#ExpressionGrouping.
    def visitExpressionGrouping(self, ctx:McInstrParser.ExpressionGroupingContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#ExpressionExponentiation.
    def visitExpressionExponentiation(self, ctx:McInstrParser.ExpressionExponentiationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#ExpressionBinaryLeftShift.
    def visitExpressionBinaryLeftShift(self, ctx:McInstrParser.ExpressionBinaryLeftShiftContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#ExpressionBinaryGreaterEqual.
    def visitExpressionBinaryGreaterEqual(self, ctx:McInstrParser.ExpressionBinaryGreaterEqualContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#ExpressionZero.
    def visitExpressionZero(self, ctx:McInstrParser.ExpressionZeroContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#ExpressionUnaryPM.
    def visitExpressionUnaryPM(self, ctx:McInstrParser.ExpressionUnaryPMContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#ExpressionTrinaryLogic.
    def visitExpressionTrinaryLogic(self, ctx:McInstrParser.ExpressionTrinaryLogicContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#ExpressionFloat.
    def visitExpressionFloat(self, ctx:McInstrParser.ExpressionFloatContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#ExpressionPointerAccess.
    def visitExpressionPointerAccess(self, ctx:McInstrParser.ExpressionPointerAccessContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#ExpressionBinaryEqual.
    def visitExpressionBinaryEqual(self, ctx:McInstrParser.ExpressionBinaryEqualContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#ExpressionBinaryPM.
    def visitExpressionBinaryPM(self, ctx:McInstrParser.ExpressionBinaryPMContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#ExpressionUnaryLogic.
    def visitExpressionUnaryLogic(self, ctx:McInstrParser.ExpressionUnaryLogicContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#shell.
    def visitShell(self, ctx:McInstrParser.ShellContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#SearchPath.
    def visitSearchPath(self, ctx:McInstrParser.SearchPathContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#SearchShell.
    def visitSearchShell(self, ctx:McInstrParser.SearchShellContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McInstrParser#unparsed_block.
    def visitUnparsed_block(self, ctx:McInstrParser.Unparsed_blockContext):
        return self.visitChildren(ctx)



del McInstrParser
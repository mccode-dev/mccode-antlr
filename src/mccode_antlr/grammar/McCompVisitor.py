# Generated from McComp.g4 by ANTLR 4.13.2
from antlr4 import *
if "." in __name__:
    from .McCompParser import McCompParser
else:
    from McCompParser import McCompParser

# This class defines a complete generic visitor for a parse tree produced by McCompParser.

class McCompVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by McCompParser#prog.
    def visitProg(self, ctx:McCompParser.ProgContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ComponentDefineNew.
    def visitComponentDefineNew(self, ctx:McCompParser.ComponentDefineNewContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ComponentDefineCopy.
    def visitComponentDefineCopy(self, ctx:McCompParser.ComponentDefineCopyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#component_trace.
    def visitComponent_trace(self, ctx:McCompParser.Component_traceContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#component_parameter_set.
    def visitComponent_parameter_set(self, ctx:McCompParser.Component_parameter_setContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#component_define_parameters.
    def visitComponent_define_parameters(self, ctx:McCompParser.Component_define_parametersContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#component_set_parameters.
    def visitComponent_set_parameters(self, ctx:McCompParser.Component_set_parametersContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#component_out_parameters.
    def visitComponent_out_parameters(self, ctx:McCompParser.Component_out_parametersContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#component_parameters.
    def visitComponent_parameters(self, ctx:McCompParser.Component_parametersContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ComponentParameterDouble.
    def visitComponentParameterDouble(self, ctx:McCompParser.ComponentParameterDoubleContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ComponentParameterInteger.
    def visitComponentParameterInteger(self, ctx:McCompParser.ComponentParameterIntegerContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ComponentParameterString.
    def visitComponentParameterString(self, ctx:McCompParser.ComponentParameterStringContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ComponentParameterVector.
    def visitComponentParameterVector(self, ctx:McCompParser.ComponentParameterVectorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ComponentParameterSymbol.
    def visitComponentParameterSymbol(self, ctx:McCompParser.ComponentParameterSymbolContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ComponentParameterDoubleArray.
    def visitComponentParameterDoubleArray(self, ctx:McCompParser.ComponentParameterDoubleArrayContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ComponentParameterIntegerArray.
    def visitComponentParameterIntegerArray(self, ctx:McCompParser.ComponentParameterIntegerArrayContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#share.
    def visitShare(self, ctx:McCompParser.ShareContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#display.
    def visitDisplay(self, ctx:McCompParser.DisplayContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#component_ref.
    def visitComponent_ref(self, ctx:McCompParser.Component_refContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#coords.
    def visitCoords(self, ctx:McCompParser.CoordsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#reference.
    def visitReference(self, ctx:McCompParser.ReferenceContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#dependency.
    def visitDependency(self, ctx:McCompParser.DependencyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#declare.
    def visitDeclare(self, ctx:McCompParser.DeclareContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#uservars.
    def visitUservars(self, ctx:McCompParser.UservarsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#initialise.
    def visitInitialise(self, ctx:McCompParser.InitialiseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#save.
    def visitSave(self, ctx:McCompParser.SaveContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#Finally.
    def visitFinally(self, ctx:McCompParser.FinallyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#multi_block.
    def visitMulti_block(self, ctx:McCompParser.Multi_blockContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#metadata.
    def visitMetadata(self, ctx:McCompParser.MetadataContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#category.
    def visitCategory(self, ctx:McCompParser.CategoryContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#initializerlist.
    def visitInitializerlist(self, ctx:McCompParser.InitializerlistContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#assignment.
    def visitAssignment(self, ctx:McCompParser.AssignmentContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ExpressionBinaryMod.
    def visitExpressionBinaryMod(self, ctx:McCompParser.ExpressionBinaryModContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ExpressionBinaryLess.
    def visitExpressionBinaryLess(self, ctx:McCompParser.ExpressionBinaryLessContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ExpressionBinaryGreater.
    def visitExpressionBinaryGreater(self, ctx:McCompParser.ExpressionBinaryGreaterContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ExpressionBinaryLessEqual.
    def visitExpressionBinaryLessEqual(self, ctx:McCompParser.ExpressionBinaryLessEqualContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ExpressionArrayAccess.
    def visitExpressionArrayAccess(self, ctx:McCompParser.ExpressionArrayAccessContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ExpressionBinaryLogic.
    def visitExpressionBinaryLogic(self, ctx:McCompParser.ExpressionBinaryLogicContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ExpressionInteger.
    def visitExpressionInteger(self, ctx:McCompParser.ExpressionIntegerContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ExpressionBinaryRightShift.
    def visitExpressionBinaryRightShift(self, ctx:McCompParser.ExpressionBinaryRightShiftContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ExpressionMyself.
    def visitExpressionMyself(self, ctx:McCompParser.ExpressionMyselfContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ExpressionPrevious.
    def visitExpressionPrevious(self, ctx:McCompParser.ExpressionPreviousContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ExpressionIdentifier.
    def visitExpressionIdentifier(self, ctx:McCompParser.ExpressionIdentifierContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ExpressionBinaryNotEqual.
    def visitExpressionBinaryNotEqual(self, ctx:McCompParser.ExpressionBinaryNotEqualContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ExpressionStructAccess.
    def visitExpressionStructAccess(self, ctx:McCompParser.ExpressionStructAccessContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ExpressionFunctionCall.
    def visitExpressionFunctionCall(self, ctx:McCompParser.ExpressionFunctionCallContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ExpressionBinaryMD.
    def visitExpressionBinaryMD(self, ctx:McCompParser.ExpressionBinaryMDContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ExpressionString.
    def visitExpressionString(self, ctx:McCompParser.ExpressionStringContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ExpressionGrouping.
    def visitExpressionGrouping(self, ctx:McCompParser.ExpressionGroupingContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ExpressionExponentiation.
    def visitExpressionExponentiation(self, ctx:McCompParser.ExpressionExponentiationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ExpressionBinaryLeftShift.
    def visitExpressionBinaryLeftShift(self, ctx:McCompParser.ExpressionBinaryLeftShiftContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ExpressionBinaryGreaterEqual.
    def visitExpressionBinaryGreaterEqual(self, ctx:McCompParser.ExpressionBinaryGreaterEqualContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ExpressionZero.
    def visitExpressionZero(self, ctx:McCompParser.ExpressionZeroContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ExpressionUnaryPM.
    def visitExpressionUnaryPM(self, ctx:McCompParser.ExpressionUnaryPMContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ExpressionTrinaryLogic.
    def visitExpressionTrinaryLogic(self, ctx:McCompParser.ExpressionTrinaryLogicContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ExpressionFloat.
    def visitExpressionFloat(self, ctx:McCompParser.ExpressionFloatContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ExpressionPointerAccess.
    def visitExpressionPointerAccess(self, ctx:McCompParser.ExpressionPointerAccessContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ExpressionBinaryEqual.
    def visitExpressionBinaryEqual(self, ctx:McCompParser.ExpressionBinaryEqualContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ExpressionBinaryPM.
    def visitExpressionBinaryPM(self, ctx:McCompParser.ExpressionBinaryPMContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#ExpressionUnaryLogic.
    def visitExpressionUnaryLogic(self, ctx:McCompParser.ExpressionUnaryLogicContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#shell.
    def visitShell(self, ctx:McCompParser.ShellContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#SearchPath.
    def visitSearchPath(self, ctx:McCompParser.SearchPathContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#SearchShell.
    def visitSearchShell(self, ctx:McCompParser.SearchShellContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McCompParser#unparsed_block.
    def visitUnparsed_block(self, ctx:McCompParser.Unparsed_blockContext):
        return self.visitChildren(ctx)



del McCompParser
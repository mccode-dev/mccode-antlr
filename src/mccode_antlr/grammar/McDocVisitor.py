# Generated from /home/g/Code/mccode-tidy/src/grammar/McDoc.g4 by ANTLR 4.13.2
from antlr4 import *
if "." in __name__:
    from .McDocParser import McDocParser
else:
    from McDocParser import McDocParser

# This class defines a complete generic visitor for a parse tree produced by McDocParser.

class McDocVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by McDocParser#mcdoc.
    def visitMcdoc(self, ctx:McDocParser.McdocContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McDocParser#InfoSection.
    def visitInfoSection(self, ctx:McDocParser.InfoSectionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McDocParser#DescSection.
    def visitDescSection(self, ctx:McDocParser.DescSectionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McDocParser#ParamSection.
    def visitParamSection(self, ctx:McDocParser.ParamSectionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McDocParser#LinkSection.
    def visitLinkSection(self, ctx:McDocParser.LinkSectionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McDocParser#EndSection.
    def visitEndSection(self, ctx:McDocParser.EndSectionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McDocParser#OtherSection.
    def visitOtherSection(self, ctx:McDocParser.OtherSectionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McDocParser#OrphanLine.
    def visitOrphanLine(self, ctx:McDocParser.OrphanLineContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McDocParser#BlankLine.
    def visitBlankLine(self, ctx:McDocParser.BlankLineContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by McDocParser#line.
    def visitLine(self, ctx:McDocParser.LineContext):
        return self.visitChildren(ctx)



del McDocParser
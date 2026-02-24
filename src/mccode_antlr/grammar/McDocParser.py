# Generated from /home/g/Code/mccode-tidy/src/grammar/McDoc.g4 by ANTLR 4.13.2
# encoding: utf-8
from antlr4 import *
from io import StringIO
import sys
if sys.version_info[1] > 5:
	from typing import TextIO
else:
	from typing.io import TextIO

def serializedATN():
    return [
        4,1,9,64,2,0,7,0,2,1,7,1,2,2,7,2,1,0,5,0,8,8,0,10,0,12,0,11,9,0,
        1,0,1,0,1,1,1,1,1,1,5,1,18,8,1,10,1,12,1,21,9,1,1,1,1,1,1,1,5,1,
        26,8,1,10,1,12,1,29,9,1,1,1,1,1,1,1,5,1,34,8,1,10,1,12,1,37,9,1,
        1,1,1,1,1,1,5,1,42,8,1,10,1,12,1,45,9,1,1,1,1,1,1,1,1,1,5,1,51,8,
        1,10,1,12,1,54,9,1,1,1,1,1,3,1,58,8,1,1,2,1,2,3,2,62,8,2,1,2,0,0,
        3,0,2,4,0,0,79,0,9,1,0,0,0,2,57,1,0,0,0,4,59,1,0,0,0,6,8,3,2,1,0,
        7,6,1,0,0,0,8,11,1,0,0,0,9,7,1,0,0,0,9,10,1,0,0,0,10,12,1,0,0,0,
        11,9,1,0,0,0,12,13,5,0,0,1,13,1,1,0,0,0,14,19,5,1,0,0,15,18,3,4,
        2,0,16,18,5,7,0,0,17,15,1,0,0,0,17,16,1,0,0,0,18,21,1,0,0,0,19,17,
        1,0,0,0,19,20,1,0,0,0,20,58,1,0,0,0,21,19,1,0,0,0,22,27,5,2,0,0,
        23,26,3,4,2,0,24,26,5,7,0,0,25,23,1,0,0,0,25,24,1,0,0,0,26,29,1,
        0,0,0,27,25,1,0,0,0,27,28,1,0,0,0,28,58,1,0,0,0,29,27,1,0,0,0,30,
        35,5,3,0,0,31,34,3,4,2,0,32,34,5,7,0,0,33,31,1,0,0,0,33,32,1,0,0,
        0,34,37,1,0,0,0,35,33,1,0,0,0,35,36,1,0,0,0,36,58,1,0,0,0,37,35,
        1,0,0,0,38,43,5,4,0,0,39,42,3,4,2,0,40,42,5,7,0,0,41,39,1,0,0,0,
        41,40,1,0,0,0,42,45,1,0,0,0,43,41,1,0,0,0,43,44,1,0,0,0,44,58,1,
        0,0,0,45,43,1,0,0,0,46,58,5,5,0,0,47,52,5,6,0,0,48,51,3,4,2,0,49,
        51,5,7,0,0,50,48,1,0,0,0,50,49,1,0,0,0,51,54,1,0,0,0,52,50,1,0,0,
        0,52,53,1,0,0,0,53,58,1,0,0,0,54,52,1,0,0,0,55,58,3,4,2,0,56,58,
        5,7,0,0,57,14,1,0,0,0,57,22,1,0,0,0,57,30,1,0,0,0,57,38,1,0,0,0,
        57,46,1,0,0,0,57,47,1,0,0,0,57,55,1,0,0,0,57,56,1,0,0,0,58,3,1,0,
        0,0,59,61,5,8,0,0,60,62,5,7,0,0,61,60,1,0,0,0,61,62,1,0,0,0,62,5,
        1,0,0,0,13,9,17,19,25,27,33,35,41,43,50,52,57,61
    ]

class McDocParser ( Parser ):

    grammarFileName = "McDoc.g4"

    atn = ATNDeserializer().deserialize(serializedATN())

    decisionsToDFA = [ DFA(ds, i) for i, ds in enumerate(atn.decisionToState) ]

    sharedContextCache = PredictionContextCache()

    literalNames = [  ]

    symbolicNames = [ "<INVALID>", "INFO_TAG", "DESC_TAG", "PARAM_TAG", 
                      "LINK_TAG", "END_TAG", "OTHER_TAG", "NEWLINE", "LINE", 
                      "WS" ]

    RULE_mcdoc = 0
    RULE_section = 1
    RULE_line = 2

    ruleNames =  [ "mcdoc", "section", "line" ]

    EOF = Token.EOF
    INFO_TAG=1
    DESC_TAG=2
    PARAM_TAG=3
    LINK_TAG=4
    END_TAG=5
    OTHER_TAG=6
    NEWLINE=7
    LINE=8
    WS=9

    def __init__(self, input:TokenStream, output:TextIO = sys.stdout):
        super().__init__(input, output)
        self.checkVersion("4.13.2")
        self._interp = ParserATNSimulator(self, self.atn, self.decisionsToDFA, self.sharedContextCache)
        self._predicates = None




    class McdocContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def EOF(self):
            return self.getToken(McDocParser.EOF, 0)

        def section(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(McDocParser.SectionContext)
            else:
                return self.getTypedRuleContext(McDocParser.SectionContext,i)


        def getRuleIndex(self):
            return McDocParser.RULE_mcdoc

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitMcdoc" ):
                return visitor.visitMcdoc(self)
            else:
                return visitor.visitChildren(self)




    def mcdoc(self):

        localctx = McDocParser.McdocContext(self, self._ctx, self.state)
        self.enterRule(localctx, 0, self.RULE_mcdoc)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 9
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while (((_la) & ~0x3f) == 0 and ((1 << _la) & 510) != 0):
                self.state = 6
                self.section()
                self.state = 11
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 12
            self.match(McDocParser.EOF)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class SectionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser


        def getRuleIndex(self):
            return McDocParser.RULE_section

     
        def copyFrom(self, ctx:ParserRuleContext):
            super().copyFrom(ctx)



    class InfoSectionContext(SectionContext):

        def __init__(self, parser, ctx:ParserRuleContext): # actually a McDocParser.SectionContext
            super().__init__(parser)
            self.copyFrom(ctx)

        def INFO_TAG(self):
            return self.getToken(McDocParser.INFO_TAG, 0)
        def line(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(McDocParser.LineContext)
            else:
                return self.getTypedRuleContext(McDocParser.LineContext,i)

        def NEWLINE(self, i:int=None):
            if i is None:
                return self.getTokens(McDocParser.NEWLINE)
            else:
                return self.getToken(McDocParser.NEWLINE, i)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitInfoSection" ):
                return visitor.visitInfoSection(self)
            else:
                return visitor.visitChildren(self)


    class OtherSectionContext(SectionContext):

        def __init__(self, parser, ctx:ParserRuleContext): # actually a McDocParser.SectionContext
            super().__init__(parser)
            self.copyFrom(ctx)

        def OTHER_TAG(self):
            return self.getToken(McDocParser.OTHER_TAG, 0)
        def line(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(McDocParser.LineContext)
            else:
                return self.getTypedRuleContext(McDocParser.LineContext,i)

        def NEWLINE(self, i:int=None):
            if i is None:
                return self.getTokens(McDocParser.NEWLINE)
            else:
                return self.getToken(McDocParser.NEWLINE, i)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitOtherSection" ):
                return visitor.visitOtherSection(self)
            else:
                return visitor.visitChildren(self)


    class BlankLineContext(SectionContext):

        def __init__(self, parser, ctx:ParserRuleContext): # actually a McDocParser.SectionContext
            super().__init__(parser)
            self.copyFrom(ctx)

        def NEWLINE(self):
            return self.getToken(McDocParser.NEWLINE, 0)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitBlankLine" ):
                return visitor.visitBlankLine(self)
            else:
                return visitor.visitChildren(self)


    class DescSectionContext(SectionContext):

        def __init__(self, parser, ctx:ParserRuleContext): # actually a McDocParser.SectionContext
            super().__init__(parser)
            self.copyFrom(ctx)

        def DESC_TAG(self):
            return self.getToken(McDocParser.DESC_TAG, 0)
        def line(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(McDocParser.LineContext)
            else:
                return self.getTypedRuleContext(McDocParser.LineContext,i)

        def NEWLINE(self, i:int=None):
            if i is None:
                return self.getTokens(McDocParser.NEWLINE)
            else:
                return self.getToken(McDocParser.NEWLINE, i)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitDescSection" ):
                return visitor.visitDescSection(self)
            else:
                return visitor.visitChildren(self)


    class LinkSectionContext(SectionContext):

        def __init__(self, parser, ctx:ParserRuleContext): # actually a McDocParser.SectionContext
            super().__init__(parser)
            self.copyFrom(ctx)

        def LINK_TAG(self):
            return self.getToken(McDocParser.LINK_TAG, 0)
        def line(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(McDocParser.LineContext)
            else:
                return self.getTypedRuleContext(McDocParser.LineContext,i)

        def NEWLINE(self, i:int=None):
            if i is None:
                return self.getTokens(McDocParser.NEWLINE)
            else:
                return self.getToken(McDocParser.NEWLINE, i)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitLinkSection" ):
                return visitor.visitLinkSection(self)
            else:
                return visitor.visitChildren(self)


    class EndSectionContext(SectionContext):

        def __init__(self, parser, ctx:ParserRuleContext): # actually a McDocParser.SectionContext
            super().__init__(parser)
            self.copyFrom(ctx)

        def END_TAG(self):
            return self.getToken(McDocParser.END_TAG, 0)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitEndSection" ):
                return visitor.visitEndSection(self)
            else:
                return visitor.visitChildren(self)


    class OrphanLineContext(SectionContext):

        def __init__(self, parser, ctx:ParserRuleContext): # actually a McDocParser.SectionContext
            super().__init__(parser)
            self.copyFrom(ctx)

        def line(self):
            return self.getTypedRuleContext(McDocParser.LineContext,0)


        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitOrphanLine" ):
                return visitor.visitOrphanLine(self)
            else:
                return visitor.visitChildren(self)


    class ParamSectionContext(SectionContext):

        def __init__(self, parser, ctx:ParserRuleContext): # actually a McDocParser.SectionContext
            super().__init__(parser)
            self.copyFrom(ctx)

        def PARAM_TAG(self):
            return self.getToken(McDocParser.PARAM_TAG, 0)
        def line(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(McDocParser.LineContext)
            else:
                return self.getTypedRuleContext(McDocParser.LineContext,i)

        def NEWLINE(self, i:int=None):
            if i is None:
                return self.getTokens(McDocParser.NEWLINE)
            else:
                return self.getToken(McDocParser.NEWLINE, i)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitParamSection" ):
                return visitor.visitParamSection(self)
            else:
                return visitor.visitChildren(self)



    def section(self):

        localctx = McDocParser.SectionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 2, self.RULE_section)
        try:
            self.state = 57
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [1]:
                localctx = McDocParser.InfoSectionContext(self, localctx)
                self.enterOuterAlt(localctx, 1)
                self.state = 14
                self.match(McDocParser.INFO_TAG)
                self.state = 19
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,2,self._ctx)
                while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                    if _alt==1:
                        self.state = 17
                        self._errHandler.sync(self)
                        token = self._input.LA(1)
                        if token in [8]:
                            self.state = 15
                            self.line()
                            pass
                        elif token in [7]:
                            self.state = 16
                            self.match(McDocParser.NEWLINE)
                            pass
                        else:
                            raise NoViableAltException(self)
                 
                    self.state = 21
                    self._errHandler.sync(self)
                    _alt = self._interp.adaptivePredict(self._input,2,self._ctx)

                pass
            elif token in [2]:
                localctx = McDocParser.DescSectionContext(self, localctx)
                self.enterOuterAlt(localctx, 2)
                self.state = 22
                self.match(McDocParser.DESC_TAG)
                self.state = 27
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,4,self._ctx)
                while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                    if _alt==1:
                        self.state = 25
                        self._errHandler.sync(self)
                        token = self._input.LA(1)
                        if token in [8]:
                            self.state = 23
                            self.line()
                            pass
                        elif token in [7]:
                            self.state = 24
                            self.match(McDocParser.NEWLINE)
                            pass
                        else:
                            raise NoViableAltException(self)
                 
                    self.state = 29
                    self._errHandler.sync(self)
                    _alt = self._interp.adaptivePredict(self._input,4,self._ctx)

                pass
            elif token in [3]:
                localctx = McDocParser.ParamSectionContext(self, localctx)
                self.enterOuterAlt(localctx, 3)
                self.state = 30
                self.match(McDocParser.PARAM_TAG)
                self.state = 35
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,6,self._ctx)
                while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                    if _alt==1:
                        self.state = 33
                        self._errHandler.sync(self)
                        token = self._input.LA(1)
                        if token in [8]:
                            self.state = 31
                            self.line()
                            pass
                        elif token in [7]:
                            self.state = 32
                            self.match(McDocParser.NEWLINE)
                            pass
                        else:
                            raise NoViableAltException(self)
                 
                    self.state = 37
                    self._errHandler.sync(self)
                    _alt = self._interp.adaptivePredict(self._input,6,self._ctx)

                pass
            elif token in [4]:
                localctx = McDocParser.LinkSectionContext(self, localctx)
                self.enterOuterAlt(localctx, 4)
                self.state = 38
                self.match(McDocParser.LINK_TAG)
                self.state = 43
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,8,self._ctx)
                while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                    if _alt==1:
                        self.state = 41
                        self._errHandler.sync(self)
                        token = self._input.LA(1)
                        if token in [8]:
                            self.state = 39
                            self.line()
                            pass
                        elif token in [7]:
                            self.state = 40
                            self.match(McDocParser.NEWLINE)
                            pass
                        else:
                            raise NoViableAltException(self)
                 
                    self.state = 45
                    self._errHandler.sync(self)
                    _alt = self._interp.adaptivePredict(self._input,8,self._ctx)

                pass
            elif token in [5]:
                localctx = McDocParser.EndSectionContext(self, localctx)
                self.enterOuterAlt(localctx, 5)
                self.state = 46
                self.match(McDocParser.END_TAG)
                pass
            elif token in [6]:
                localctx = McDocParser.OtherSectionContext(self, localctx)
                self.enterOuterAlt(localctx, 6)
                self.state = 47
                self.match(McDocParser.OTHER_TAG)
                self.state = 52
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,10,self._ctx)
                while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                    if _alt==1:
                        self.state = 50
                        self._errHandler.sync(self)
                        token = self._input.LA(1)
                        if token in [8]:
                            self.state = 48
                            self.line()
                            pass
                        elif token in [7]:
                            self.state = 49
                            self.match(McDocParser.NEWLINE)
                            pass
                        else:
                            raise NoViableAltException(self)
                 
                    self.state = 54
                    self._errHandler.sync(self)
                    _alt = self._interp.adaptivePredict(self._input,10,self._ctx)

                pass
            elif token in [8]:
                localctx = McDocParser.OrphanLineContext(self, localctx)
                self.enterOuterAlt(localctx, 7)
                self.state = 55
                self.line()
                pass
            elif token in [7]:
                localctx = McDocParser.BlankLineContext(self, localctx)
                self.enterOuterAlt(localctx, 8)
                self.state = 56
                self.match(McDocParser.NEWLINE)
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class LineContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LINE(self):
            return self.getToken(McDocParser.LINE, 0)

        def NEWLINE(self):
            return self.getToken(McDocParser.NEWLINE, 0)

        def getRuleIndex(self):
            return McDocParser.RULE_line

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitLine" ):
                return visitor.visitLine(self)
            else:
                return visitor.visitChildren(self)




    def line(self):

        localctx = McDocParser.LineContext(self, self._ctx, self.state)
        self.enterRule(localctx, 4, self.RULE_line)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 59
            self.match(McDocParser.LINE)
            self.state = 61
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,12,self._ctx)
            if la_ == 1:
                self.state = 60
                self.match(McDocParser.NEWLINE)


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx






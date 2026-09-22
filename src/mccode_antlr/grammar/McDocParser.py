# Generated from McDoc.g4 by ANTLR 4.13.2
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
        4,1,9,74,2,0,7,0,2,1,7,1,2,2,7,2,1,0,1,0,5,0,9,8,0,10,0,12,0,12,
        9,0,1,0,5,0,15,8,0,10,0,12,0,18,9,0,1,0,1,0,1,1,1,1,1,1,5,1,25,8,
        1,10,1,12,1,28,9,1,1,1,1,1,1,1,5,1,33,8,1,10,1,12,1,36,9,1,1,1,1,
        1,1,1,5,1,41,8,1,10,1,12,1,44,9,1,1,1,1,1,1,1,5,1,49,8,1,10,1,12,
        1,52,9,1,1,1,1,1,1,1,5,1,57,8,1,10,1,12,1,60,9,1,1,1,1,1,1,1,5,1,
        65,8,1,10,1,12,1,68,9,1,3,1,70,8,1,1,2,1,2,1,2,0,0,3,0,2,4,0,0,90,
        0,10,1,0,0,0,2,69,1,0,0,0,4,71,1,0,0,0,6,9,3,4,2,0,7,9,5,7,0,0,8,
        6,1,0,0,0,8,7,1,0,0,0,9,12,1,0,0,0,10,8,1,0,0,0,10,11,1,0,0,0,11,
        16,1,0,0,0,12,10,1,0,0,0,13,15,3,2,1,0,14,13,1,0,0,0,15,18,1,0,0,
        0,16,14,1,0,0,0,16,17,1,0,0,0,17,19,1,0,0,0,18,16,1,0,0,0,19,20,
        5,0,0,1,20,1,1,0,0,0,21,26,5,1,0,0,22,25,3,4,2,0,23,25,5,7,0,0,24,
        22,1,0,0,0,24,23,1,0,0,0,25,28,1,0,0,0,26,24,1,0,0,0,26,27,1,0,0,
        0,27,70,1,0,0,0,28,26,1,0,0,0,29,34,5,2,0,0,30,33,3,4,2,0,31,33,
        5,7,0,0,32,30,1,0,0,0,32,31,1,0,0,0,33,36,1,0,0,0,34,32,1,0,0,0,
        34,35,1,0,0,0,35,70,1,0,0,0,36,34,1,0,0,0,37,42,5,3,0,0,38,41,3,
        4,2,0,39,41,5,7,0,0,40,38,1,0,0,0,40,39,1,0,0,0,41,44,1,0,0,0,42,
        40,1,0,0,0,42,43,1,0,0,0,43,70,1,0,0,0,44,42,1,0,0,0,45,50,5,4,0,
        0,46,49,3,4,2,0,47,49,5,7,0,0,48,46,1,0,0,0,48,47,1,0,0,0,49,52,
        1,0,0,0,50,48,1,0,0,0,50,51,1,0,0,0,51,70,1,0,0,0,52,50,1,0,0,0,
        53,58,5,5,0,0,54,57,3,4,2,0,55,57,5,7,0,0,56,54,1,0,0,0,56,55,1,
        0,0,0,57,60,1,0,0,0,58,56,1,0,0,0,58,59,1,0,0,0,59,70,1,0,0,0,60,
        58,1,0,0,0,61,66,5,6,0,0,62,65,3,4,2,0,63,65,5,7,0,0,64,62,1,0,0,
        0,64,63,1,0,0,0,65,68,1,0,0,0,66,64,1,0,0,0,66,67,1,0,0,0,67,70,
        1,0,0,0,68,66,1,0,0,0,69,21,1,0,0,0,69,29,1,0,0,0,69,37,1,0,0,0,
        69,45,1,0,0,0,69,53,1,0,0,0,69,61,1,0,0,0,70,3,1,0,0,0,71,72,5,8,
        0,0,72,5,1,0,0,0,16,8,10,16,24,26,32,34,40,42,48,50,56,58,64,66,
        69
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
            self.state = 10
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==7 or _la==8:
                self.state = 8
                self._errHandler.sync(self)
                token = self._input.LA(1)
                if token in [8]:
                    self.state = 6
                    self.line()
                    pass
                elif token in [7]:
                    self.state = 7
                    self.match(McDocParser.NEWLINE)
                    pass
                else:
                    raise NoViableAltException(self)

                self.state = 12
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 16
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while (((_la) & ~0x3f) == 0 and ((1 << _la) & 126) != 0):
                self.state = 13
                self.section()
                self.state = 18
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 19
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
            if hasattr( visitor, "visitEndSection" ):
                return visitor.visitEndSection(self)
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
        self._la = 0 # Token type
        try:
            self.state = 69
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [1]:
                localctx = McDocParser.InfoSectionContext(self, localctx)
                self.enterOuterAlt(localctx, 1)
                self.state = 21
                self.match(McDocParser.INFO_TAG)
                self.state = 26
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                while _la==7 or _la==8:
                    self.state = 24
                    self._errHandler.sync(self)
                    token = self._input.LA(1)
                    if token in [8]:
                        self.state = 22
                        self.line()
                        pass
                    elif token in [7]:
                        self.state = 23
                        self.match(McDocParser.NEWLINE)
                        pass
                    else:
                        raise NoViableAltException(self)

                    self.state = 28
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)

                pass
            elif token in [2]:
                localctx = McDocParser.DescSectionContext(self, localctx)
                self.enterOuterAlt(localctx, 2)
                self.state = 29
                self.match(McDocParser.DESC_TAG)
                self.state = 34
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                while _la==7 or _la==8:
                    self.state = 32
                    self._errHandler.sync(self)
                    token = self._input.LA(1)
                    if token in [8]:
                        self.state = 30
                        self.line()
                        pass
                    elif token in [7]:
                        self.state = 31
                        self.match(McDocParser.NEWLINE)
                        pass
                    else:
                        raise NoViableAltException(self)

                    self.state = 36
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)

                pass
            elif token in [3]:
                localctx = McDocParser.ParamSectionContext(self, localctx)
                self.enterOuterAlt(localctx, 3)
                self.state = 37
                self.match(McDocParser.PARAM_TAG)
                self.state = 42
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                while _la==7 or _la==8:
                    self.state = 40
                    self._errHandler.sync(self)
                    token = self._input.LA(1)
                    if token in [8]:
                        self.state = 38
                        self.line()
                        pass
                    elif token in [7]:
                        self.state = 39
                        self.match(McDocParser.NEWLINE)
                        pass
                    else:
                        raise NoViableAltException(self)

                    self.state = 44
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)

                pass
            elif token in [4]:
                localctx = McDocParser.LinkSectionContext(self, localctx)
                self.enterOuterAlt(localctx, 4)
                self.state = 45
                self.match(McDocParser.LINK_TAG)
                self.state = 50
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                while _la==7 or _la==8:
                    self.state = 48
                    self._errHandler.sync(self)
                    token = self._input.LA(1)
                    if token in [8]:
                        self.state = 46
                        self.line()
                        pass
                    elif token in [7]:
                        self.state = 47
                        self.match(McDocParser.NEWLINE)
                        pass
                    else:
                        raise NoViableAltException(self)

                    self.state = 52
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)

                pass
            elif token in [5]:
                localctx = McDocParser.EndSectionContext(self, localctx)
                self.enterOuterAlt(localctx, 5)
                self.state = 53
                self.match(McDocParser.END_TAG)
                self.state = 58
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                while _la==7 or _la==8:
                    self.state = 56
                    self._errHandler.sync(self)
                    token = self._input.LA(1)
                    if token in [8]:
                        self.state = 54
                        self.line()
                        pass
                    elif token in [7]:
                        self.state = 55
                        self.match(McDocParser.NEWLINE)
                        pass
                    else:
                        raise NoViableAltException(self)

                    self.state = 60
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)

                pass
            elif token in [6]:
                localctx = McDocParser.OtherSectionContext(self, localctx)
                self.enterOuterAlt(localctx, 6)
                self.state = 61
                self.match(McDocParser.OTHER_TAG)
                self.state = 66
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                while _la==7 or _la==8:
                    self.state = 64
                    self._errHandler.sync(self)
                    token = self._input.LA(1)
                    if token in [8]:
                        self.state = 62
                        self.line()
                        pass
                    elif token in [7]:
                        self.state = 63
                        self.match(McDocParser.NEWLINE)
                        pass
                    else:
                        raise NoViableAltException(self)

                    self.state = 68
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)

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
            self.state = 71
            self.match(McDocParser.LINE)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx






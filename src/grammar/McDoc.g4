grammar McDoc;

// Grammar for McDoc component/instrument header comments.
// Input: the pre-processed content of the first C block comment in a .comp or .instr file,
// with the /* and */ delimiters removed and the leading ' * ' stripped from each line.
//
// Section tags recognised:
//   %I / %ID / %Identification / %IDENTIFICATION  -> identification / info section
//   %D / %Description / %DESCRIPTION              -> description section
//   %P / %PAR / %Parameters / %PARAMETERS         -> parameter section
//   %L / %Link / %Links / %LINKS                  -> literature links section
//   %E / %End / %END                              -> end of McDoc block
//   %BUGS / %VALIDATION / other %WORD             -> other sections (treated as free text)
//
// Each content line inside a section is captured as a LINE token.  The visitor
// applies a regular expression to LINE tokens inside ParamSection to extract
// the (name, unit, description) structure of each parameter entry.
//
// A note on why the rules are shaped the way they are.  ANTLR is an LL parser:
// it reads input Left-to-right and builds a Leftmost derivation, deciding which
// alternative of a rule to take *before* consuming the tokens that alternative
// matches.  A grammar is LL(1) when one token of lookahead is always enough to
// make that choice -- the alternatives start with disjoint token sets.  When it
// is not, ANTLR falls back to adaptive LL(*) prediction, simulating the grammar
// over as many tokens as it takes to tell the alternatives apart.
//
// Every decision below is LL(1): content lines (LINE, NEWLINE) and section tags
// are disjoint token sets, so a section body ends exactly where the next tag --
// or EOF -- begins.  Keep it that way.  Letting a content line both continue a
// section and start a new one, or letting `line` optionally absorb the NEWLINE
// the enclosing loop also matches, would make two derivations consume identical
// token streams.  Nothing downstream ever tells them apart, so prediction runs
// to EOF on every line, and -- because that ambiguous full-context lookahead is
// not cached in the DFA -- costs O(n) per line, O(n^2) per comment.  Before
// these rules were made LL(1), a 2157-line header took ten minutes to parse.

mcdoc
    :   (line | NEWLINE)* section* EOF
    ;

section
    :   INFO_TAG  (line | NEWLINE)*   # InfoSection
    |   DESC_TAG  (line | NEWLINE)*   # DescSection
    |   PARAM_TAG (line | NEWLINE)*   # ParamSection
    |   LINK_TAG  (line | NEWLINE)*   # LinkSection
    |   END_TAG   (line | NEWLINE)*   # EndSection
    |   OTHER_TAG (line | NEWLINE)*   # OtherSection
    ;

line
    :   LINE
    ;

// ─── LEXER ───────────────────────────────────────────────────────────────────

// Section tags: each tag consumes optional trailing whitespace and the newline so
// the parser never sees a stray NEWLINE immediately after a tag.

INFO_TAG
    :   '%' ( 'I' | 'ID' | 'Identification' | 'IDENTIFICATION' ) HWS* NL
    ;

DESC_TAG
    :   '%' ( 'D' | 'Description' | 'DESCRIPTION' ) HWS* NL
    ;

PARAM_TAG
    :   '%' ( 'P' | 'PAR' | 'Parameters' | 'PARAMETERS' ) HWS* NL
    ;

LINK_TAG
    :   '%' ( 'L' | 'Link' | 'Links' | 'LINKS' ) HWS* NL
    ;

END_TAG
    :   '%' ( 'E' | 'End' | 'END' ) HWS* NL?
    ;

// Catch-all for other section tags (%BUGS, %VALIDATION, %DESCRIPTION variant, etc.)
OTHER_TAG
    :   '%' [A-Za-z]+ HWS* NL
    ;

NEWLINE
    :   NL
    ;

// A content line: any sequence of characters that does not start with '%' or a
// newline.  The trailing newline is NOT consumed here; it is matched separately
// by the NEWLINE token so that the parser rule `line` can treat it as optional.
LINE
    :   ~[\r\n%] ~[\r\n]*
    ;

// Horizontal whitespace is skipped between tokens.
WS
    :   HWS+ -> skip
    ;

fragment HWS : [ \t] ;
fragment NL  : '\r'? '\n' ;

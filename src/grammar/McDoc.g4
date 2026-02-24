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

mcdoc
    :   section* EOF
    ;

section
    :   INFO_TAG  (line | NEWLINE)*   # InfoSection
    |   DESC_TAG  (line | NEWLINE)*   # DescSection
    |   PARAM_TAG (line | NEWLINE)*   # ParamSection
    |   LINK_TAG  (line | NEWLINE)*   # LinkSection
    |   END_TAG                       # EndSection
    |   OTHER_TAG (line | NEWLINE)*   # OtherSection
    |   line                          # OrphanLine
    |   NEWLINE                       # BlankLine
    ;

line
    :   LINE NEWLINE?
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

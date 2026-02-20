// Keyword list checked against https://en.cppreference.com/w/c/keyword
lexer grammar c99;

IntegerLiteral
    : DecimalLiteral IntegerSuffix?
    | OctalLiteral IntegerSuffix?
    | HexadecimalLiteral IntegerSuffix?
    | BinaryLiteral IntegerSuffix?
    ;
CharacterLiteral: ( 'u' | 'U' | 'L' )? '\'' Cchar+ '\'';
FloatingLiteral
    : FractionalConstant ExponentPart ? FloatingSuffix?
    | DigitSequence ExponentPart FloatingSuffix?
    ;
StringLiteral: EncodingPrefix? (Rawstring | '"' Schar* '"' );
BooleanLitteral: False_ | True_;
//PointerLiteral: Nullptr;
UserDefinedLiteral
    : UserDefinedIntegerLiteral
    | UserDefinedFloatingLiteral
    | UserDefinedStringLiteral
    | UserDefinedCharacterLiteral
    ;
MultiLineMacro: '#' (~[\n]*? '\\' '\r'? '\n')+ ~ [\n]+ -> channel (HIDDEN);
Directive: '#' ~ [\n]* -> channel (HIDDEN);
/*Keywords*/
//Alignas: 'alignas';  // C23; _Alignas in C11, not present in C99
//Alignof: 'alignof';  // C23; _Alignof in C11, not present in C99
Asm: 'asm'; // may be gnu99 specific
Auto: 'auto';
//Bool: 'bool'; // C23, C99 defined n stdbool.h but not part of the language
Bool: '_Bool'; // C99
Break: 'break';
Case: 'case';
//Catch: 'catch';  // C++
Char: 'char';
//Char16: 'char16_t'; // C++
//Char32: 'char32_t'; // C++
//Class: 'class';  // C++
Complex: '_Complex'; // C99
Const: 'const';
//Constexpr: 'constexpr'; // C23, C++
//Const_cast: 'const_cast'; // C++
Continue: 'continue';
//Decltype: 'decltype'; // C++
Default: 'default';
//Delete: 'delete'; // C++
Do: 'do';
Double: 'double';
//Dynamic_cast: 'dynamic_cast'; // C++
Else: 'else';
Enum: 'enum';
//Explicit: 'explicit';
//Export: 'export';  // C++
Extern: 'extern';
//DO NOT RENAME - PYTHON NEEDS True and False
False_: 'false';  // C23
//Final: 'final';  // C++
Float: 'float';
For: 'for';
//Friend: 'friend'; // C++
Goto: 'goto';
If: 'if';
Imaginary: '_Imaginary'; // C99
Inline: 'inline';
Int: 'int';
Long: 'long';
//Mutable: 'mutable'; // C++
//Namespace: 'namespace'; // C++
//New: 'new';
//Noexcept: 'noexcept'; // C++
//Nullptr: 'nullptr'; // C23, C++11
//Operator: 'operator'; // C++
//Override: 'override'; // C++11
//Private: 'private';  // C++
//Protected: 'protected';  // C++
//Public: 'public';  // C++, and possibly a macro in C
Register: 'register';
//Reinterpret_cast: 'reinterpret_cast'; // C++
Return: 'return';
Short: 'short';
Signed: 'signed';
Sizeof: 'sizeof';
Static: 'static';
//Static_assert: 'static_assert'; // C23, GCC extension for C99, maybe as _Static_assert
//Static_cast: 'static_cast'; // C++
Struct: 'struct';
Switch: 'switch';
//Template: 'template'; // C++
//This: 'this'; // C++
//Thread_local: 'thread_local'; // C23
//Throw: 'throw'; // C++
//DO NOT RENAME - PYTHON NEEDS True and False
True_: 'true'; // C23
//Try: 'try';  // C++
Typedef: 'typedef';
//Typeid_: 'typeid';  // C++
//Typename_: 'typename';  // C++
Union: 'union';
Unsigned: 'unsigned';
//Using: 'using';
//Virtual: 'virtual';
Void: 'void';
Volatile: 'volatile';
//Wchar: 'wchar_t';
While: 'while';
/*Operators*/
LeftParen: '(';
RightParen: ')';
LeftBracket: '[';
RightBracket: ']';
LeftBrace: '{';
RightBrace: '}';
Plus: '+';
Minus: '-';
Star: '*';
Div: '/';
Mod: '%';
Caret: '^';
And: '&';
Or: '|';
Tilde: '~';
Not: '!' | 'not';
Assign: '=';
Less: '<';
Greater: '>';
PlusAssign: '+=';
MinusAssign: '-=';
StarAssign: '*=';
DivAssign: '/=';
ModAssign: '%=';
XorAssign: '^=';
AndAssign: '&=';
OrAssign: '|=';
LeftShiftAssign: '<<=';
RightShiftAssign: '>>=';
Equal: '==';
NotEqual: '!=';
LessEqual: '<=';
GreaterEqual: '>=';
AndAnd: '&&' | 'and';
OrOr: '||' | 'or';
PlusPlus: '++';
MinusMinus: '--';
Comma: ',';
ArrowStar: '->*';
Arrow: '->';
Question: '?';
Colon: ':';
Doublecolon: '::';
Semi: ';';
Dot: '.';
DotStar: '.*';
Ellipsis: '...';
fragment Hexquad: HEXADECIMALDIGIT HEXADECIMALDIGIT HEXADECIMALDIGIT HEXADECIMALDIGIT;
fragment Universalcharactername: '\\u' Hexquad | '\\U' Hexquad Hexquad;
Identifier:
	/*
	 Identifiernondigit | Identifier Identifiernondigit | Identifier DIGIT
	 */
	Identifiernondigit (Identifiernondigit | DIGIT)*;
fragment Identifiernondigit: NONDIGIT | Universalcharactername;
fragment NONDIGIT: [a-zA-Z_];
fragment DIGIT: [0-9];
DecimalLiteral: NONZERODIGIT ('\''? DIGIT)*;
OctalLiteral: '0' ('\''? OCTALDIGIT)*;
HexadecimalLiteral: ('0x' | '0X') HEXADECIMALDIGIT ( '\''? HEXADECIMALDIGIT )*;
BinaryLiteral: ('0b' | '0B') BINARYDIGIT ('\''? BINARYDIGIT)*;
fragment NONZERODIGIT: [1-9];
fragment OCTALDIGIT: [0-7];
fragment HEXADECIMALDIGIT: [0-9a-fA-F];
fragment BINARYDIGIT: [01];
IntegerSuffix:
	Unsignedsuffix Longsuffix?
	| Unsignedsuffix Longlongsuffix?
	| Longsuffix Unsignedsuffix?
	| Longlongsuffix Unsignedsuffix?;
fragment Unsignedsuffix: [uU];
fragment Longsuffix: [lL];
fragment Longlongsuffix: 'll' | 'LL';
fragment Cchar:
	~ ['\\\r\n]
	| Escapesequence
	| Universalcharactername;
fragment Escapesequence:
	Simpleescapesequence
	| Octalescapesequence
	| Hexadecimalescapesequence;
fragment Simpleescapesequence
    : '\\\''
	| '\\"'
	| '\\?'
	| '\\\\'
	| '\\a'
	| '\\b'
	| '\\f'
	| '\\n'
	| '\\r'
	| ('\\' ('\r' '\n'? | '\n'))
	| '\\t'
	| '\\v'
	;
fragment Octalescapesequence
    : '\\' OCTALDIGIT
	| '\\' OCTALDIGIT OCTALDIGIT
	| '\\' OCTALDIGIT OCTALDIGIT OCTALDIGIT
	;
fragment Hexadecimalescapesequence: '\\x' HEXADECIMALDIGIT+;
fragment FractionalConstant
    : DigitSequence? '.' DigitSequence
	| DigitSequence '.'
	;
fragment ExponentPart
    : 'e' SIGN? DigitSequence
	| 'E' SIGN? DigitSequence
	;
fragment SIGN: [+-];
fragment DigitSequence: DIGIT ('\''? DIGIT)*;
fragment FloatingSuffix: [flFL];
fragment EncodingPrefix: 'u8' | 'u' | 'U' | 'L';
fragment Schar:
	~ ["\\\r\n]
	| Escapesequence
	| Universalcharactername;
fragment Rawstring: 'R"' (( '\\' ["()] )|~[\r\n (])*? '(' ~[)]*? ')'  (( '\\' ["()]) | ~[\r\n "])*? '"';
UserDefinedIntegerLiteral:
	DecimalLiteral Udsuffix
	| OctalLiteral Udsuffix
	| HexadecimalLiteral Udsuffix
	| BinaryLiteral Udsuffix;
UserDefinedFloatingLiteral:
	FractionalConstant ExponentPart? Udsuffix
	| DigitSequence ExponentPart Udsuffix;
UserDefinedStringLiteral: StringLiteral Udsuffix;
UserDefinedCharacterLiteral: CharacterLiteral Udsuffix;
fragment Udsuffix: Identifier;
Whitespace: [ \t]+ -> skip;
Newline: ('\r' '\n'? | '\n') -> skip;
BlockComment: '/*' .*? '*/' -> channel(HIDDEN);
LineComment: '//' ~ [\r\n]* -> channel(HIDDEN);

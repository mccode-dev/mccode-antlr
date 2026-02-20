"""
mcfmt – McCode DSL formatter CLI.

Usage examples::

    # Print formatted output to stdout
    mcfmt instrument.instr

    # Format one or more files in place
    mcfmt -i component.comp instrument.instr

    # Check whether files are already formatted (useful in CI)
    mcfmt --check *.instr *.comp

    # Show a unified diff of what would change
    mcfmt --diff instrument.instr

    # Also format C-code blocks using the official McCode clang-format config
    mcfmt --clang-format instrument.instr

    # Use a local clang-format config file for C blocks
    mcfmt --clang-format-config /path/to/.clang-format instrument.instr

    # Use a named clang-format style for C blocks
    mcfmt --clang-format-style LLVM instrument.instr
"""
from __future__ import annotations

import sys
from pathlib import Path


def _build_parser():
    from argparse import ArgumentParser

    parser = ArgumentParser(
        prog='mcfmt',
        description='Format McCode DSL source files (.instr and .comp).',
        epilog=(
            'C-code blocks can optionally be formatted by clang-format '
            'using one of the --clang-format* options.'
        ),
    )
    parser.add_argument(
        'files',
        nargs='+',
        type=Path,
        metavar='FILE',
        help='.instr or .comp files to format',
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        '-i', '--inplace',
        action='store_true',
        default=False,
        help='Modify files in place instead of printing to stdout',
    )
    mode.add_argument(
        '--check',
        action='store_true',
        default=False,
        help=(
            'Do not write files; exit with a non-zero status if any file '
            'would be reformatted (useful as a CI gate)'
        ),
    )
    mode.add_argument(
        '--diff',
        action='store_true',
        default=False,
        help='Show a unified diff of proposed changes instead of formatted output',
    )

    cfmt = parser.add_mutually_exclusive_group()
    cfmt.add_argument(
        '--clang-format',
        action='store_true',
        default=False,
        dest='clang_format',
        help=(
            'Format C-code blocks (%%{ … %%}) using clang-format with the '
            'official McCode .clang-format configuration (fetched via pooch).'
        ),
    )
    cfmt.add_argument(
        '--clang-format-config',
        metavar='PATH',
        default=None,
        dest='clang_format_config',
        help=(
            'Format C-code blocks using clang-format with the given '
            '.clang-format configuration file.'
        ),
    )
    cfmt.add_argument(
        '--clang-format-style',
        metavar='STYLE',
        default=None,
        dest='clang_format_style',
        help=(
            'Format C-code blocks using clang-format with the given style '
            '(e.g. "LLVM", "Google", or an inline "{BasedOnStyle: …}" map).'
        ),
    )
    return parser


def _unified_diff(original: str, formatted: str, filename: str) -> str:
    import difflib
    return ''.join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            formatted.splitlines(keepends=True),
            fromfile=f'a/{filename}',
            tofile=f'b/{filename}',
        )
    )


def mcfmt():
    """Entry point for the ``mcfmt`` command-line tool."""
    from mccode_antlr.format import format_file, make_clang_formatter

    parser = _build_parser()
    args = parser.parse_args()

    # Build the clang-format callable (may be None if not requested / unavailable)
    clang_format = None
    if args.clang_format:
        clang_format = make_clang_formatter(fetch_mccode_config=True)
    elif args.clang_format_config:
        clang_format = make_clang_formatter(
            config=args.clang_format_config, fetch_mccode_config=False,
        )
    elif args.clang_format_style:
        clang_format = make_clang_formatter(
            style=args.clang_format_style, fetch_mccode_config=False,
        )

    any_changed = False
    exit_code = 0

    for path in args.files:
        if not path.exists():
            print(f'mcfmt: {path}: No such file', file=sys.stderr)
            exit_code = 1
            continue

        ext = path.suffix.lower()
        if ext not in ('.instr', '.comp'):
            print(
                f'mcfmt: {path}: skipping (unsupported extension "{ext}"; '
                'expected .instr or .comp)',
                file=sys.stderr,
            )
            continue

        original = path.read_text(encoding='utf-8')
        try:
            formatted = format_file(path, clang_format=clang_format)
        except Exception as exc:
            print(f'mcfmt: {path}: error during formatting: {exc}', file=sys.stderr)
            exit_code = 1
            continue

        changed = original != formatted

        if args.check:
            if changed:
                print(f'mcfmt: {path}: would reformat', file=sys.stderr)
                any_changed = True
        elif args.diff:
            diff = _unified_diff(original, formatted, str(path))
            if diff:
                sys.stdout.write(diff)
                any_changed = True
        elif args.inplace:
            if changed:
                path.write_text(formatted, encoding='utf-8')
                print(f'Reformatted {path}', file=sys.stderr)
                any_changed = True
        else:
            # Default: print to stdout (only useful for single-file usage;
            # for multiple files each formatted output is printed in order)
            sys.stdout.write(formatted)

    if args.check and any_changed:
        sys.exit(1)
    sys.exit(exit_code)


if __name__ == '__main__':
    mcfmt()

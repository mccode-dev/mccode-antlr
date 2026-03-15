"""CLI command ``mcdisplay-antlr-step``: convert a McCode instrument to a STEP file.

Usage::

    mcdisplay-antlr-step instrument.instr -o output.step
    mcdisplay-antlr-step instrument.instr -o output.step -p xw=0.05 yh=0.1
    mcdisplay-antlr-step instrument.instr -o output.step --flavor mcxtrace

Requires the ``brep`` optional extra::

    pip install mccode-antlr[brep]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='mcdisplay-antlr-step',
        description='Convert a McCode instrument to a STEP B-rep file.',
    )
    p.add_argument('instr', metavar='INSTRUMENT',
                   help='Path to the .instr file.')
    p.add_argument('-o', '--output', metavar='OUTPUT',
                   help='Output STEP file path (default: <instr_stem>.step).')
    p.add_argument('-p', '--param', metavar='KEY=VAL', nargs='*', default=[],
                   help='Instrument parameter overrides, e.g. -p xw=0.05 yh=0.1')
    p.add_argument('--flavor', choices=['mcstas', 'mcxtrace'], default='mcstas',
                   help='Instrument flavour (default: mcstas).')
    return p


def _parse_params(param_list: list[str]) -> dict[str, float]:
    params: dict[str, float] = {}
    for item in param_list:
        if '=' not in item:
            print(f"Warning: ignoring malformed parameter {item!r} (expected KEY=VAL)",
                  file=sys.stderr)
            continue
        key, _, val = item.partition('=')
        try:
            params[key.strip()] = float(val.strip())
        except ValueError:
            print(f"Warning: cannot convert {val!r} to float for parameter {key!r}",
                  file=sys.stderr)
    return params


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # --- require build123d ---
    try:
        import build123d  # noqa: F401
    except ImportError:
        print("Error: build123d is not installed.\n"
              "Install it with:  pip install mccode-antlr[brep]",
              file=sys.stderr)
        return 1

    instr_path = Path(args.instr)
    if not instr_path.exists():
        print(f"Error: instrument file not found: {instr_path}", file=sys.stderr)
        return 1

    output_path = Path(args.output) if args.output else instr_path.with_suffix('.step')

    params = _parse_params(args.param or [])

    # --- load instrument ---
    try:
        if args.flavor == 'mcstas':
            from mccode_antlr.loader import load_mcstas_instr as loader
        else:
            from mccode_antlr.loader import load_mcxtrace_instr as loader
        instr = loader(str(instr_path))
    except Exception as exc:
        print(f"Error loading instrument: {exc}", file=sys.stderr)
        return 1

    # --- build display + B-rep assembly ---
    try:
        from mccode_antlr.display import InstrumentDisplay
        from mccode_antlr.display.render.brep import instrument_to_assembly, save_step
        disp = InstrumentDisplay(instr)
        assembly = instrument_to_assembly(disp, params)
        save_step(assembly, output_path)
    except Exception as exc:
        print(f"Error building STEP: {exc}", file=sys.stderr)
        return 1

    print(f"Written: {output_path}  ({output_path.stat().st_size:,} bytes)")
    return 0


if __name__ == '__main__':
    sys.exit(main())

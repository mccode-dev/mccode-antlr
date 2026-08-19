"""Render the example notebooks to Markdown for the documentation build.

The notebooks are the source; their Markdown is a build artefact, regenerated here
rather than committed, so it cannot drift from the notebook it came from.

    python docs/examples/build.py

Outputs are taken from the notebooks as stored -- nothing is executed -- which is what
the previous mkdocs-jupyter configuration did (`execute: false`).
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent


def main() -> int:
    notebooks = sorted(HERE.glob('*.ipynb'))
    if not notebooks:
        print(f'no notebooks found in {HERE}', file=sys.stderr)
        return 1

    for notebook in notebooks:
        print(f'rendering {notebook.name}')
        subprocess.run(
            [sys.executable, '-m', 'nbconvert', '--to', 'markdown',
             '--output-dir', str(HERE), str(notebook)],
            check=True,
        )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

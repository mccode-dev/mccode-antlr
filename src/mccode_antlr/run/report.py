"""A live overview of a running scan.

`--capture=tui` keeps a small status display pinned to the terminal while the
simulation runs and erases it afterwards, so a finished scan leaves the user
looking at their own last command rather than at thousands of lines of output.
Nothing is lost: every line still goes to `<output directory>/mccode.out`, the
same as `--capture=tee`.

What can be shown is whatever the McCode runtime happens to print. The useful
markers are:

* ``NN %`` from ``Progress_bar``, which is ``MPI_MASTER``-guarded and flushed, so
  it arrives promptly and is not repeated once per rank
* ``[name] Initialize`` when a point starts
* ``Detector: name_I=... name_ERR=... name_N=...`` as results are written
* ``Finally [name: dir]. Time: ...`` when a point ends

An instrument without a ``Progress_bar`` prints no percentages at all, so the
per-point bar stays indeterminate rather than pretending to know.
"""
from __future__ import annotations

import re
from collections import deque
from pathlib import Path

#: Progress_bar.comp: MPI_MASTER(fprintf(stdout, "%llu %%\n", ...); fflush(stdout););
_PERCENT = re.compile(rb'^\s*(\d{1,3})\s*%\s*$')
_DETECTOR = re.compile(rb'^Detector:\s*(\S+?)_I=(\S+)')
_ERROR = re.compile(rb'(?i)\b(error|warning|abort|failed)\b')

#: Error and warning lines worth surfacing while the display is up.
_KEPT_MESSAGES = 3


def tui_is_usable() -> bool:
    """Whether a live display would work here.

    Under a pipe, a CI log or a dumb terminal it would emit control sequences
    nobody can act on, so the caller falls back to plain streaming.
    """
    try:
        from rich.console import Console
    except ImportError:  # pragma: no cover - rich is a hard dependency
        return False
    return Console().is_terminal


class ScanReporter:
    """Drives the live display for one scan, across all of its points."""

    def __init__(self, name: str, total_points: int):
        from rich.console import Console
        from rich.progress import (BarColumn, MofNCompleteColumn, Progress,
                                   SpinnerColumn, TextColumn, TimeElapsedColumn)
        self.name = name
        self.total_points = total_points
        self.console = Console()
        self._messages: deque[str] = deque(maxlen=_KEPT_MESSAGES)
        self._detector: str | None = None
        self._values: str = ''
        self._live = None

        self._points = Progress(
            TextColumn('[bold]{task.description}'), BarColumn(),
            MofNCompleteColumn(), TimeElapsedColumn(), console=self.console,
        )
        self._point_task = self._points.add_task('scan', total=total_points)
        self._within = Progress(
            SpinnerColumn(), TextColumn('{task.description}'), BarColumn(),
            TextColumn('{task.percentage:>3.0f}%'), console=self.console,
        )
        # total=None renders as an indeterminate bar: honest for an instrument
        # that prints no percentages at all
        self._within_task = self._within.add_task('starting', total=None)

    # -- display ----------------------------------------------------------- #

    def _renderable(self):
        from rich.console import Group
        from rich.text import Text
        parts = [self._points]
        if self.total_points > 1:
            parts.append(self._within)
        else:
            parts = [self._within]
        if self._values:
            parts.append(Text(f'  {self._values}', style='cyan'))
        if self._detector:
            parts.append(Text(f'  {self._detector}', style='green'))
        parts.extend(Text(f'  {m}', style='yellow') for m in self._messages)
        return Group(*parts)

    def _refresh(self):
        if self._live is not None:
            self._live.update(self._renderable())

    def __enter__(self):
        from rich.live import Live
        # transient: the display is erased when the scan ends. A failure tears it
        # down the same way, and the error then prints normally underneath.
        self._live = Live(self._renderable(), console=self.console, transient=True,
                          refresh_per_second=8)
        self._live.__enter__()
        return self

    def __exit__(self, *exc):
        live, self._live = self._live, None
        if live is not None:
            live.__exit__(*exc)
        return False

    # -- per point --------------------------------------------------------- #

    def start_point(self, number: int, values: dict | None = None):
        self._detector = None
        self._messages.clear()
        self._values = ', '.join(f'{k}={v}' for k, v in (values or {}).items())
        label = f'point {number + 1}' if self.total_points > 1 else self.name
        self._points.update(self._point_task, completed=number,
                            description=f'{self.name} scan')
        self._within.reset(self._within_task, total=None, description=label)
        self._refresh()

    def finish_point(self, number: int):
        self._points.update(self._point_task, completed=number + 1)
        self._within.update(self._within_task, total=100, completed=100)
        self._refresh()

    def consume(self, raw: bytes):
        """Called for every line the simulation writes. Never echoes it."""
        line = raw.rstrip(b'\r\n')
        if not line:
            return
        if (found := _PERCENT.match(line)) is not None:
            percent = min(100, int(found.group(1)))
            self._within.update(self._within_task, total=100, completed=percent)
        elif (found := _DETECTOR.match(line)) is not None:
            name = found.group(1).decode('utf-8', errors='replace')
            value = found.group(2).decode('utf-8', errors='replace')
            self._detector = f'{name} = {value}'
        elif _ERROR.search(line) is not None:
            self._messages.append(line.decode('utf-8', errors='replace')[:120])
        else:
            return  # ordinary output; it is in the log, not on the screen
        self._refresh()

    def note(self, message: str):
        self._messages.append(message)
        self._refresh()

    def done(self, directory: Path | None = None):
        """Print the one line worth keeping once the display is gone."""
        where = f' -> {directory}' if directory is not None else ''
        points = f'{self.total_points} point{"s" if self.total_points != 1 else ""}'
        self.console.print(f'{self.name}: {points} finished{where}')

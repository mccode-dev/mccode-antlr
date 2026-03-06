"""Output file collection and loading for a single simulation run."""
from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, Callable

# Registry: extension (lowercase, with dot) → loader callable
# Loaders receive a Path and return a loaded object; they may raise on failure.
_LOAD_FILTERS: dict[str, Callable[[Path], Any]] = {}


def register_output_filter(extension: str, loader: Callable[[Path], Any]) -> None:
    """Register a custom output-file loader for files with the given *extension*.

    The *extension* must include the leading dot (e.g. ``'.h5'``).  The *loader*
    receives the :class:`~pathlib.Path` of the file and must return the loaded
    object, raising any exception if loading fails (the file will then appear in
    :attr:`SimulationOutput.unrecognized`).

    Registering a loader for an extension that already has one replaces the
    existing entry.  This allows user code to override the built-in ``'.dat'``
    loader if needed.

    Example::

        import h5py
        from mccode_antlr.run import register_output_filter
        register_output_filter('.h5', h5py.File)
    """
    _LOAD_FILTERS[extension.lower()] = loader


def _load_one(path: Path) -> Any:
    """Try to load *path* using a registered filter or by attempting McCode dat format."""
    from mccode_antlr.loader import read_mccode_dat

    ext = path.suffix.lower()

    # Use a registered extension-specific filter when available.
    if ext in _LOAD_FILTERS:
        return _LOAD_FILTERS[ext](path)

    # For everything else, try the McCode .dat format reader (which works for
    # any extension that happens to contain McCode-format data, e.g. Monitor_nD
    # output files that use non-standard suffixes).
    return read_mccode_dat(path)


def _collect_output(directory: Path) -> 'SimulationOutput':
    """Scan *directory* recursively and return a :class:`SimulationOutput`.

    Every file found is attempted with :func:`_load_one`.  Files that cannot
    be loaded (because no filter matches and the McCode dat reader fails) are
    stored in :attr:`SimulationOutput.unrecognized`.
    """
    from mccode_antlr.loader import read_mccode_sim
    from mccode_antlr.loader.datfile import DatFileCommon

    loaded: dict[str, Any] = {}
    unrecognized: list[Path] = []
    sim_file = None

    for path in Path(directory).rglob('*'):
        if not path.is_file():
            continue

        ext = path.suffix.lower()

        # .sim files are simulation metadata; load separately and do not mix
        # them into the general keyed dict.
        if ext == '.sim':
            if sim_file is None:
                try:
                    sim_file = read_mccode_sim(path)
                except Exception:
                    pass
            continue

        try:
            obj = _load_one(path)
        except Exception:
            unrecognized.append(path)
            continue

        loaded[path.stem] = obj

    dats: dict[str, DatFileCommon] = {
        stem: obj for stem, obj in loaded.items() if isinstance(obj, DatFileCommon)
    }
    other: dict[str, Any] = {
        stem: obj for stem, obj in loaded.items() if not isinstance(obj, DatFileCommon)
    }

    return SimulationOutput(
        directory=Path(directory),
        dats=dats,
        other=other,
        unrecognized=unrecognized,
        sim_file=sim_file,
    )


class SimulationOutput(Mapping):
    """All files written to disk by a single simulation run.

    :class:`SimulationOutput` implements :class:`~collections.abc.Mapping` so
    that existing code written against the old ``dict[str, DatFile]`` return
    value continues to work without modification::

        result, out = sim.run({'x': 1.5}, ncount=1000)
        # Old-style access still works:
        print(out['m0']['I'])
        print(len(out))

    Additional properties expose the full picture of what was written:

    * :attr:`dats`         — McCode-format files (any extension)
    * :attr:`other`        — Files loaded by registered custom filters
    * :attr:`loaded`       — Union of *dats* and *other* keyed by stem
    * :attr:`unrecognized` — Files that could not be loaded
    * :attr:`sim_file`     — Parsed ``mccode.sim`` metadata (or ``None``)
    * :attr:`directory`    — Output directory :class:`~pathlib.Path`
    """

    def __init__(
        self,
        directory: Path,
        dats: dict[str, Any],
        other: dict[str, Any],
        unrecognized: list[Path],
        sim_file: Any | None,
    ):
        self._dats = dats
        self._other = other
        self._unrecognized = list(unrecognized)
        self._sim_file = sim_file
        self.directory = directory

    # ------------------------------------------------------------------
    # Mapping interface (proxies to dats for backward compatibility)
    # ------------------------------------------------------------------

    def __getitem__(self, key: str) -> Any:
        return self._dats[key]

    def __len__(self) -> int:
        return len(self._dats)

    def __iter__(self) -> Iterator[str]:
        return iter(self._dats)

    # ------------------------------------------------------------------
    # Additional properties
    # ------------------------------------------------------------------

    @property
    def dats(self) -> dict[str, Any]:
        """Files loaded as McCode dat format, keyed by file stem."""
        return dict(self._dats)

    @property
    def other(self) -> dict[str, Any]:
        """Files loaded by registered custom filters, keyed by file stem."""
        return dict(self._other)

    @property
    def loaded(self) -> dict[str, Any]:
        """All successfully loaded files (dats + other), keyed by stem."""
        return {**self._dats, **self._other}

    @property
    def unrecognized(self) -> list[Path]:
        """Paths of files that could not be loaded by any filter."""
        return list(self._unrecognized)

    @property
    def sim_file(self) -> Any | None:
        """Parsed McCode ``.sim`` metadata file, or ``None`` if not found."""
        return self._sim_file

    def __repr__(self) -> str:
        parts = [f"directory={self.directory!r}", f"dats={list(self._dats)!r}"]
        if self._other:
            parts.append(f"other={list(self._other)!r}")
        if self._unrecognized:
            parts.append(f"unrecognized={[p.name for p in self._unrecognized]!r}")
        return f"SimulationOutput({', '.join(parts)})"

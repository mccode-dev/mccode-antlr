"""Output file collection and loading for a single simulation run."""
from __future__ import annotations

from msgspec import Struct
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, Callable


def _is_singular(v) -> bool:
    """Return True if *v* is a :class:`~mccode_antlr.run.range.Singular`."""
    from .range import Singular
    return isinstance(v, Singular)

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


def _collect_output(directory: Path, tmpdir:Path | None=None) -> 'SimulationOutput':
    """Scan *directory* recursively and return a :class:`SimulationOutput`.

    Every file found is attempted with :func:`_load_one`.  Files that cannot
    be loaded (because no filter matches and the McCode dat reader fails) are
    stored in :attr:`SimulationOutput.unrecognized`.
    """
    from mccode_antlr.loader import read_mccode_sim
    from mccode_antlr.loader.datfile import DatFileCommon

    loaded: dict[str, Any] = {}
    unrecognized: list[Path] = []
    binary_files: list[Path] = []
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
        if ext in ('.mcpl', '.gz', '.mcpl.gz'):
            # Skip even attempting to load these filetypes
            binary_files.append(path)
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
        binary_files=binary_files,
        sim_file=sim_file,
        tmpdir=tmpdir,
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
    * :attr: binary_files  — MCPL/GZip files which an instrument might produce
    * :attr:`sim_file`     — Parsed ``mccode.sim`` metadata (or ``None``)
    * :attr:`directory`    — Output directory :class:`~pathlib.Path`
    """

    def __init__(
        self,
        directory: Path,
        dats: dict[str, Any],
        other: dict[str, Any],
        unrecognized: list[Path],
        binary_files: list[Path],
        sim_file: Any | None,
        tmpdir: Path | None,
    ):
        self._dats = dats
        self._other = other
        self._unrecognized = list(unrecognized)
        self._binaries = list(binary_files)
        self._sim_file = sim_file
        self.directory = directory
        self._tmpdir = tmpdir  # Optionally hold a reference to a temporary directory to keep it alive

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
    def binary_files(self) -> list[Path]:
        """Paths of binary files that were skipped."""
        return list(self._binaries)

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


class RunOutput(Struct):
    stdout: str
    parameters: dict[str, Any]
    output: SimulationOutput

    @property
    def coords(self) -> 'Coords':
        """Single-run parameter values as a :class:`Coords` mapping.

        Each parameter is wrapped in a :class:`~mccode_antlr.run.range.Singular`
        so the interface is consistent with :attr:`ScanOutput.coords`.
        """
        from .range import Coords, Singular
        return Coords({k: Singular(v, 1) for k, v in self.parameters.items()})

    @property
    def dats(self) -> dict[str, Any]:
        """McCode monitor files from this run, keyed by file stem."""
        return self.output.dats

    def __getitem__(self, key: str) -> Any:
        """Access a monitor output by file stem (delegates to :attr:`output`)."""
        if not isinstance(key, str):
            raise TypeError(f"RunOutput keys must be strings, not {type(key).__name__!r}")
        return self.output[key]


class ScanOutput(Struct):
    grid: bool
    points: tuple[RunOutput, ...]
    axes: dict[str, Any]

    @property
    def coords(self) -> 'Coords':
        """Axis coordinate access, similar to :mod:`xarray` coords.

        Returns a :class:`~mccode_antlr.run.range.Coords` mapping whose values
        are :class:`~mccode_antlr.run.range.MRange`,
        :class:`~mccode_antlr.run.range.EList`, or
        :class:`~mccode_antlr.run.range.Singular` objects describing each
        parameter axis.

        Example::

            result = sim.scan(parameters={'a': '0:1:5', 'b': '100,200,300'})
            result.coords['a']   # MRange(0, 5, 1)
            result.coords.b      # EList([100, 200, 300])
        """
        from .range import Coords
        return Coords(self.axes)

    @property
    def shape(self) -> tuple[int, ...]:
        """Shape of the scan result array.

        For grid scans: ``(len(axis_0), len(axis_1), ...)`` matching :attr:`axes` order.
        For zip scans: ``(n_points,)``.
        """
        from .range import has_len
        if self.grid:
            return tuple(len(v) for v in self.axes.values() if has_len(v))
        return (len(self.points),)

    @property
    def ndim(self) -> int:
        """Number of scan dimensions.

        For grid scans equals ``len(axes)``; for zip scans always 1.
        """
        return len(self.axes) if self.grid else 1

    def __len__(self) -> int:
        return len(self.points)

    def __iter__(self) -> Iterator[RunOutput]:
        return iter(self.points)

    def __getitem__(self, key):
        if isinstance(key, str):
            return self._concat_monitor(key)
        if isinstance(key, int):
            return self.points[key]
        if isinstance(key, slice):
            return self.points[key]
        raise TypeError(f"'{key}' is not a valid scan key")

    def _concat_monitor(self, monitor: str):
        """Concatenate a named monitor's scipp Dataset across all scan points.

        For zip scans the result has a single extra dimension named after the
        (sole) varied parameter.  For grid scans the flat concat is folded to
        match the declared grid shape and each axis coord is attached.

        Returns a ``scipp.Dataset`` (requires ``scipp`` to be installed).
        """
        import scipp as sc
        per_point = []
        for pt in self.points:
            dat = pt[monitor]
            ds = dat.dataset
            # attach scalar scan-parameter coords so they survive the concat
            coords = {k: sc.scalar(float(v)) for k, v in pt.parameters.items()}
            ds_with_coords = sc.Dataset(
                {key: da.assign_coords(coords) for key, da in ds.items()}
            )
            per_point.append(ds_with_coords)

        flat_ds = sc.concat(per_point, 'scan_idx')

        if not self.grid:
            # zip scan: rename the flat dim to the single varied parameter name
            varied = [k for k, v in self.axes.items() if not _is_singular(v)]
            if len(varied) == 1:
                dim_name = varied[0]
                folded = sc.Dataset(
                    {k: da.rename_dims({'scan_idx': dim_name})
                     for k, da in flat_ds.items()}
                )
                axis_values = list(self.axes[dim_name])
                folded = sc.Dataset({
                    k: da.assign_coords(
                        {dim_name: sc.array(dims=[dim_name], values=[float(x) for x in axis_values])}
                    )
                    for k, da in folded.items()
                })
                return folded
            return flat_ds

        # grid scan: fold per DataArray then rebuild Dataset
        from .range import has_len
        varied_axes = {k: v for k, v in self.axes.items() if has_len(v)}
        dims = list(varied_axes.keys())
        shape = [len(v) for v in varied_axes.values()]
        folded_dict = {}
        for key, da in flat_ds.items():
            folded_da = sc.fold(da, 'scan_idx', dims=dims, sizes=dict(zip(dims, shape)))
            # attach axis coords
            coords = {
                dim: sc.array(dims=[dim], values=[float(x) for x in axis_vals])
                for dim, axis_vals in varied_axes.items()
            }
            folded_dict[key] = folded_da.assign_coords(coords)
        return sc.Dataset(folded_dict)
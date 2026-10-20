from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache, cached_property
from typing import Any, Union
from pathlib import Path

from mccode_antlr.utils import deprecated


@cache
def _scipp_available() -> bool:
    try:
        import scipp  # noqa: F401
    except ImportError:
        return False
    return True


def _require_scipp():
    """Import and return the scipp module, raising a helpful ImportError if absent."""
    try:
        import scipp as sc
        return sc
    except ImportError:
        raise ImportError(
            "scipp is required for McCode data file loading.\n"
            "Install it with:  pip install mccode-antlr[scipp]"
        ) from None


def _parse_file(filename: str | Path) -> tuple:
    """Parse a McCode .dat text file and return raw components.

    Returns ``(source, metadata, parameters, variables, data)`` where *data*
    is a 2-D :class:`numpy.ndarray` (rows = data lines, columns = values).
    """
    from numpy import array
    source = Path(filename).resolve()
    if not source.exists():
        raise RuntimeError('Source filename does not exist')
    if not source.is_file():
        raise RuntimeError(f'{filename} does not name a valid file')
    # The McCode runtime copies UTF-8 instrument text into the header, but paths may be in the locale encoding
    with source.open('r', encoding='utf-8', errors='replace') as file:
        lines = file.readlines()
    header = [x.strip(' #\n') for x in filter(lambda x: x[0] == '#', lines)]
    meta = {k.strip(): v.strip() for k, v in
            [x.split(':', 1) for x in filter(lambda x: not x.startswith('Param'), header)]}
    parm = {k.strip(): v.strip() for k, v in
            [x.split(':', 1)[1].split('=', 1) for x in filter(lambda x: x.startswith('Param'), header)]}
    var = meta.get('variables', '').split()
    data = array([[float(x) for x in line.strip().split()] for line in filter(lambda x: x[0] != '#', lines)])
    return source, meta, parm, var, data


def _extract_var_arrays(var: list[str], data_2d, shape: tuple) -> tuple:
    """Extract (I_values, I_err_values, N_values, extra) from a (nv, ...) numpy array.

    *shape* is the per-variable shape, e.g. ``(nx,)`` for 1-D or ``(ny, nx)`` for 2-D.
    Returns ``(I, I_err, N, extras)`` where each is a numpy array or *None*.
    ``extras`` is a list of ``(name, array)`` for any variables beyond the standard three.
    """
    import numpy as np
    nv = len(var)
    # Rebuild (nv, *shape) array from whatever shape was passed
    arr = np.reshape(data_2d, (nv,) + shape)

    def _get(name, idx):
        if name in var:
            return arr[var.index(name)]
        if 0 <= idx < nv:
            return arr[idx]
        return None

    I_arr = _get('I', 0)
    I_err_arr = _get('I_err', 1)
    N_arr = _get('N', 2)
    standard = {'I', 'I_err', 'N'}
    extras = [(v, arr[i]) for i, v in enumerate(var) if v not in standard]
    return I_arr, I_err_arr, N_arr, extras


def _standard_indices(var: list[str]) -> tuple:
    """Where ``I``, ``I_err`` and ``N`` are among a file's variables, or None."""
    def index(name, fallback):
        if name in var:
            return var.index(name)
        return fallback if fallback < len(var) else None
    return index('I', 0), index('I_err', 1), index('N', 2)


def _combine_values(var: list[str], a, b, rays_a: float, rays_b: float):
    """Two runs' values, (nv, ...) each, as the values of one run of both runs' rays.

    McCode normalises each run's intensity to its own ray count, so the combined
    intensity is the ray-count-weighted mean of the two, and its error is the weighted
    errors added in quadrature, over the total. Counts add. Every other variable -- the
    axis column a 1-D file starts with, say ``Mean`` -- must agree, since it describes
    the bins rather than what landed in them.
    """
    import numpy as np
    i, e, n = _standard_indices(var)
    total = rays_a + rays_b
    out = a.copy()
    if i is not None:
        out[i] = (rays_a * a[i] + rays_b * b[i]) / total
    if e is not None:
        out[e] = np.sqrt((rays_a * a[e]) ** 2 + (rays_b * b[e]) ** 2) / total
    if n is not None:
        out[n] = a[n] + b[n]
    for k, name in enumerate(var):
        if k not in (i, e, n) and not np.array_equal(a[k], b[k]):
            raise RuntimeError(f'Cannot combine files whose {name!r} values differ')
    return out


def _g(x) -> str:
    """A number as McCode prints one in a header."""
    return f'{float(x):g}'


def _moments(axis, weight) -> tuple:
    """The weighted mean and spread of ``axis``, as McCode's ``statistics`` gives them."""
    import numpy as np
    total = weight.sum()
    if not total:
        return 0.0, 0.0
    mean = (axis * weight).sum() / total
    return mean, np.sqrt(max((axis ** 2 * weight).sum() / total - mean ** 2, 0.0))


@dataclass(eq=False)
class DatFileCommon:
    """Base class for McCode output data files.

    ``values`` holds the file's numbers as a numpy array of shape ``(nv, ...)``, one row
    per entry of :attr:`variables` in the file's order -- conventionally ``I``,
    ``I_err`` and ``N``, after any axis column. Reading, writing and combining files
    use only these, so they work without scipp.

    :attr:`dataset` presents the same numbers as a :class:`scipp.Dataset`, with the
    error as the intensity's variance and the axes as coordinates. It needs scipp,
    and is built the first time it is used. The ``metadata`` and ``parameters`` dicts
    hold the text-format header information exactly as read from the file.
    """

    source: Path
    metadata: dict = field(default_factory=dict)
    parameters: dict = field(default_factory=dict)
    values: Any = field(default=None)  # numpy.ndarray, (nv, ...)

    @property
    def variables(self) -> list[str]:
        """Variable names from the file header."""
        return self.metadata.get('variables', '').split()

    @cached_property
    def dataset(self):
        """The values as a :class:`scipp.Dataset`; requires scipp."""
        if self.values is None:
            return None
        return self._build_dataset(self.metadata, self.variables, self.values)

    def _row(self, name: str):
        var = self.variables
        return self.values[var.index(name)] if name in var else None

    @property
    @deprecated(since="0.20.1", replacement="Use {object}['I'] (with variance) or {object}['N'] in place of {object}.data", remove_in=None)
    def data(self):
        """Datafile values as a numpy array (backward compat).

        Returns the ``('I', 'I_err', 'N')`` data variable values; shape is ``(3,nx)``
        for 1-D files and ``(3, ny, nx)`` for 2-D files.
        """
        from numpy import stack, zeros_like
        if self.values is None:
            return None
        intensity, error, counts, _ = _extract_var_arrays(
            self.variables, self.values, self.values.shape[1:])
        if intensity is None or counts is None:
            raise ValueError('I and/or N are missing')
        return stack((intensity, zeros_like(intensity) if error is None else error, counts))

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_filename(cls, filename: str | Path) -> 'DatFileCommon':
        """Load a McCode ``.dat`` file, returning the appropriate subclass instance.

        This is a convenience wrapper around :func:`read_mccode_dat`; the concrete
        type (``DatFile0D``, ``DatFile1D``, ``DatFile2D``) is chosen based on the
        ``type`` metadata key in the file header.
        """
        return read_mccode_dat(filename)

    @classmethod
    def _shape_values(cls, meta: dict, var: list[str], data):
        """The parsed rows of a file as ``(nv, ...)``.  Override in subclasses."""
        raise NotImplementedError

    @classmethod
    def _build_dataset(cls, meta: dict, var: list[str], values) -> Any:
        """Build a ``sc.Dataset`` from ``(nv, ...)`` values.  Override in subclasses."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    @staticmethod
    def parts():
        return [], []

    def print_data(self, file):
        pass

    def to_filename(self, filename: str):
        sink = Path(filename).resolve()
        if sink.exists():
            raise RuntimeError(f'{filename} already exists')
        first, second = self.parts()
        with sink.open('w', encoding='utf-8') as file:
            for item in first:
                print(f'# {item}: {self.metadata[item]}', file=file)
            for param in self.parameters:
                print(f'# Param: {param}={self.parameters[param]}', file=file)
            for item in second:
                print(f'# {item}: {self.metadata[item]}', file=file)
            self.print_data(file)

    # ------------------------------------------------------------------
    # Item access
    # ------------------------------------------------------------------

    def __getitem__(self, item: str):
        """A variable, parameter or header entry, in that order of precedence.

        With scipp a variable the dataset holds -- ``I``, ``N`` -- is its
        ``scipp.DataArray``; without scipp, and for ``I_err``, it is the numpy row.
        """
        if self.values is not None and item in self.variables:
            if _scipp_available() and item in self.dataset:
                return self.dataset[item]
            return self._row(item)
        if item in self.parameters:
            return self.parameters[item]
        if item in self.metadata:
            return self.metadata[item]
        raise KeyError(f'Unknown key {item!r}')

    # ------------------------------------------------------------------
    # Combining / arithmetic
    # ------------------------------------------------------------------

    #: the header entry whose bins two files must share to be combined
    _limits: str | None = None

    def dim_metadata(self) -> list[dict]:
        return []

    def safe_to_combine(self, other) -> bool:
        if type(other) is not type(self) or self.variables != other.variables:
            return False
        if self.values.shape != other.values.shape:
            return False
        return self._limits is None or self.metadata.get(self._limits) == other.metadata.get(self._limits)

    def rays(self) -> int:
        """The run's ray count, ``Ncount``, which its intensities are normalised to."""
        if 'Ncount' not in self.metadata:
            raise RuntimeError(f'{self.source} has no Ncount, so how much it should count '
                               f'for in a combination is unknown')
        return int(self.metadata['Ncount'])

    def __add__(self, other):
        """The two runs as one run of both runs' rays.

        Each run's intensities are normalised to its own ray count, so they are averaged,
        weighted by those counts, not added; see `_combine_values`. The header totals --
        ``values``, ``signal`` and ``statistics`` -- are recomputed from the result.
        """
        if not self.safe_to_combine(other):
            raise RuntimeError(f'Cannot combine these two {type(self).__name__} instances')
        combined = type(self)(self.source,
                              combine_scan_dicts(self.metadata, other.metadata),
                              combine_scan_dicts(self.parameters, other.parameters),
                              _combine_values(self.variables, self.values, other.values,
                                              self.rays(), other.rays()))
        combined.metadata.update({k: v for k, v in combined.header_totals().items()
                                  if k in combined.metadata})
        return combined

    def header_totals(self) -> dict:
        """The header's ``values`` line -- total intensity, its error and total counts --
        and, where the file has bins, ``signal``, from these values."""
        import numpy as np
        i, e, n = _standard_indices(self.variables)
        intensity = self.values[i] if i is not None else np.zeros(self.values.shape[1:])
        error = self.values[e] if e is not None else np.zeros_like(intensity)
        counts = self.values[n] if n is not None else np.zeros_like(intensity)
        totals = {'values': f'{_g(intensity.sum())} {_g(np.sqrt((error ** 2).sum()))} '
                            f'{_g(counts.sum())}'}
        if intensity.ndim:
            totals['signal'] = (f'Min={_g(intensity.min())}; Max={_g(intensity.max())}; '
                                f'Mean={_g(intensity.mean())};')
        return totals

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------

    @property
    def structured(self):
        """Return intensity as a numpy structured array (backward compat)."""
        import numpy as np
        d = self.data
        if d is None:
            return np.array([])
        d_types = [('I', d.dtype)]
        return np.frombuffer(d.tobytes(), dtype=d_types).reshape(d.shape)


# ---------------------------------------------------------------------------
# Module-level helper kept for external backward compat
# ---------------------------------------------------------------------------

def dim_metadata(length, label_unit, lower_limit, upper_limit) -> dict:
    """Build a dimension metadata dict in the old format (backward compat)."""
    from numpy import linspace
    label = label_unit.split(' ', 1)[0]
    unit_str = label_unit.split(' ', 1)[1].strip('[] ') if ' ' in label_unit else ''
    if unit_str == '\\gms':
        unit_str = 'microseconds'
    bin_width = (upper_limit - lower_limit) / max(length - 1, 1)
    boundaries = linspace(lower_limit - bin_width / 2, upper_limit + bin_width / 2, length + 1)
    return dict(lenght=length, label=label, unit=unit_str, bin_boundaries=boundaries)


# ---------------------------------------------------------------------------
# Concrete subclasses
# ---------------------------------------------------------------------------

@dataclass(eq=False)
class DatFile0D(DatFileCommon):
    """0-dimensional McCode monitor output (single scalar result)."""

    @classmethod
    def _shape_values(cls, meta: dict, var: list[str], data):
        flat = data.ravel()
        if flat.size != len(var):
            raise RuntimeError(f'Unexpected data size {flat.size} for {len(var)} variables')
        return flat

    @classmethod
    def _build_dataset(cls, meta: dict, var: list[str], values) -> Any:
        sc = _require_scipp()
        I_arr, I_err_arr, N_arr, extras = _extract_var_arrays(var, values, ())
        I_val = float(I_arr) if I_arr is not None else 0.0
        I_err_val = float(I_err_arr) if I_err_arr is not None else 0.0
        N_val = float(N_arr) if N_arr is not None else 0.0
        ds = sc.Dataset({
            'I': sc.DataArray(sc.scalar(I_val, variance=I_err_val ** 2, unit='counts/second')),
            'N': sc.DataArray(sc.scalar(N_val, unit='dimensionless')),
        })
        for name, arr in extras:
            ds[name] = sc.DataArray(sc.scalar(float(arr)))
        return ds

    def print_data(self, file):
        print(' '.join(str(x) for x in self.values.ravel()), file=file)

    @staticmethod
    def parts():
        first = ('Format', 'URL', 'Creator', 'Instrument', 'Ncount', 'Trace', 'Gravitation', 'Seed', 'Directory')
        second = ('Date', 'type', 'Source', 'component', 'position', 'title', 'Ncount', 'filename', 'statistics',
                  'signal', 'values', 'yvar', 'ylabel', 'xlimits', 'variables')
        return first, second


@dataclass(eq=False)
class DatFile1D(DatFileCommon):
    """1-dimensional McCode monitor output (histogram)."""

    _limits = 'xlimits'

    @classmethod
    def _shape_values(cls, meta: dict, var: list[str], data):
        nx = int(meta['type'].split('(', 1)[1].strip(')'))
        nv = len(var)
        # the file has one line per bin, (nx, nv)
        if data.shape == (nx, nv):
            return data.T
        if data.shape == (nv, nx):
            return data
        raise RuntimeError(f'Unexpected data shape {data.shape} for nx={nx}, nv={nv}')

    @classmethod
    def _build_dataset(cls, meta: dict, var: list[str], values) -> Any:
        sc = _require_scipp()
        from ._units import parse_mccode_label_unit
        import numpy as np
        nx = values.shape[1]
        lower, upper = [float(x) for x in meta['xlimits'].split()]
        bin_centers = np.linspace(lower, upper, nx)
        xlabel = meta.get('xlabel', 'x [1]')
        label, x_unit = parse_mccode_label_unit(xlabel)
        x_coord = sc.array(dims=[label], values=bin_centers, unit=x_unit)
        I_arr, I_err_arr, N_arr, extras = _extract_var_arrays(var, values, (nx,))
        I_vals = I_arr if I_arr is not None else np.zeros(nx)
        I_err_vals = I_err_arr if I_err_arr is not None else np.zeros(nx)
        da_I = sc.DataArray(
            data=sc.Variable(dims=[label], values=I_vals, variances=I_err_vals ** 2, unit='counts/second'),
            coords={label: x_coord},
        )
        ds = sc.Dataset({'I': da_I})
        if N_arr is not None:
            ds['N'] = sc.DataArray(
                sc.Variable(dims=[label], values=N_arr, unit='dimensionless'),
                coords={label: x_coord},
            )
        for name, extra_arr in extras:
            ds[name] = sc.DataArray(
                sc.Variable(dims=[label], values=extra_arr, unit='dimensionless'),
                coords={label: x_coord},
            )
        return ds

    def dim_metadata(self) -> list[dict]:
        lower_limit, upper_limit = [float(x) for x in self['xlimits'].split()]
        return [dim_metadata(self.values.shape[1], self['xlabel'], lower_limit, upper_limit)]

    def header_totals(self) -> dict:
        """As for every file, plus ``statistics``: the intensity-weighted mean and spread of
        the axis column, ``X0`` and ``dX``."""
        totals = super().header_totals()
        i, e, n = _standard_indices(self.variables)
        axes = [k for k in range(len(self.variables)) if k not in (i, e, n)]
        if axes and i is not None:
            mean, spread = _moments(self.values[axes[0]], self.values[i])
            totals['statistics'] = f'X0={_g(mean)}; dX={_g(spread)};'
        return totals

    def print_data(self, file):
        # one line per bin
        for row in self.values.T:
            print(' '.join(str(x) for x in row), file=file)

    @staticmethod
    def parts():
        first = ('Format', 'URL', 'Creator', 'Instrument', 'Ncount', 'Trace', 'Gravitation', 'Seed', 'Directory')
        second = ('Date', 'type', 'Source', 'component', 'position', 'title', 'Ncount', 'filename', 'statistics',
                  'signal', 'values', 'xvar', 'yvar', 'xlabel', 'ylabel', 'xlimits', 'variables')
        return first, second


@dataclass(eq=False)
class DatFile2D(DatFileCommon):
    """2-dimensional McCode monitor output (image / matrix)."""

    _limits = 'xylimits'

    @classmethod
    def _shape_values(cls, meta: dict, var: list[str], data):
        nx, ny = [int(x) for x in meta['type'].split('(', 1)[1].strip(')').split(',')]
        nv = len(var)
        # the file has one ny-line block per variable, (ny * nv, nx)
        if data.shape == (nv, ny, nx):
            return data
        if data.shape == (ny * nv, nx):
            return data.reshape((nv, ny, nx))
        raise RuntimeError(f'Unexpected data shape {data.shape} for nx={nx}, ny={ny}, nv={nv}')

    @classmethod
    def _build_dataset(cls, meta: dict, var: list[str], values) -> Any:
        sc = _require_scipp()
        from ._units import parse_mccode_label_unit
        import numpy as np
        ny, nx = values.shape[1:]
        lower_x, upper_x, lower_y, upper_y = [float(x) for x in meta['xylimits'].split()]
        x_centers = np.linspace(lower_x, upper_x, nx)
        y_centers = np.linspace(lower_y, upper_y, ny)
        xlabel = meta.get('xlabel', 'x [1]')
        ylabel = meta.get('ylabel', 'y [1]')
        x_label, x_unit = parse_mccode_label_unit(xlabel)
        y_label, y_unit = parse_mccode_label_unit(ylabel)
        x_coord = sc.array(dims=[x_label], values=x_centers, unit=x_unit)
        y_coord = sc.array(dims=[y_label], values=y_centers, unit=y_unit)
        I_arr, I_err_arr, N_arr, extras = _extract_var_arrays(var, values, (ny, nx))
        I_vals = I_arr if I_arr is not None else np.zeros((ny, nx))
        I_err_vals = I_err_arr if I_err_arr is not None else np.zeros((ny, nx))
        da_I = sc.DataArray(
            data=sc.Variable(dims=[y_label, x_label], values=I_vals, variances=I_err_vals ** 2, unit='counts/second'),
            coords={x_label: x_coord, y_label: y_coord},
        )
        ds = sc.Dataset({'I': da_I})
        if N_arr is not None:
            ds['N'] = sc.DataArray(
                sc.Variable(dims=[y_label, x_label], values=N_arr, unit='dimensionless'),
                coords={x_label: x_coord, y_label: y_coord},
            )
        for name, extra_arr in extras:
            ds[name] = sc.DataArray(
                sc.Variable(dims=[y_label, x_label], values=extra_arr, unit='dimensionless'),
                coords={x_label: x_coord, y_label: y_coord},
            )
        return ds

    def dim_metadata(self) -> list[dict]:
        lower_x, upper_x, lower_y, upper_y = [float(x) for x in self['xylimits'].split()]
        ny, nx = self.values.shape[1:]
        return [dim_metadata(nx, self['xlabel'], lower_x, upper_x),
                dim_metadata(ny, self['ylabel'], lower_y, upper_y)]

    def header_totals(self) -> dict:
        """As for every file, plus ``statistics``: the intensity-weighted mean and spread of
        each axis, ``X0``, ``dX``, ``Y0`` and ``dY``, at the bin centres McCode uses."""
        import numpy as np
        totals = super().header_totals()
        i, _, _ = _standard_indices(self.variables)
        if i is None or 'xylimits' not in self.metadata:
            return totals
        lower_x, upper_x, lower_y, upper_y = [float(x) for x in self['xylimits'].split()]
        intensity = self.values[i]
        ny, nx = intensity.shape
        x = lower_x + (np.arange(nx) + 0.5) * (upper_x - lower_x) / nx
        y = lower_y + (np.arange(ny) + 0.5) * (upper_y - lower_y) / ny
        x0, dx = _moments(x, intensity.sum(axis=0))
        y0, dy = _moments(y, intensity.sum(axis=1))
        totals['statistics'] = f'X0={_g(x0)}; dX={_g(dx)}; Y0={_g(y0)}; dY={_g(dy)};'
        return totals

    def print_data(self, file):
        labels = 'Data', 'Errors', 'Events'
        for i, name in enumerate(self.variables):
            label = labels[i] if i < len(labels) else f'Extra{i}'
            print(f'# {label} [{self.metadata["component"]}/{self.metadata["filename"]}] {name}:', file=file)
            for row in self.values[i]:
                print(' '.join(str(x) for x in row), file=file)

    @staticmethod
    def parts():
        first = ('Format', 'URL', 'Creator', 'Instrument', 'Ncount', 'Trace', 'Gravitation', 'Seed', 'Directory')
        second = ('Date', 'type', 'Source', 'component', 'position', 'title', 'Ncount', 'filename', 'statistics',
                  'signal', 'values', 'xvar', 'yvar', 'xlabel', 'ylabel', 'zvar', 'zlabel', 'xylimits', 'variables')
        return first, second


# ---------------------------------------------------------------------------
# File loading
# ---------------------------------------------------------------------------

def read_mccode_dat(filename: str | Path) -> DatFileCommon:
    """Load a McCode ``.dat`` output file, returning the appropriate subclass.

    Dispatches to :class:`DatFile0D`, :class:`DatFile1D`, or :class:`DatFile2D`
    based on the ``type`` metadata key. Needs only numpy; scipp is needed for the
    returned object's ``dataset``.
    """
    source, meta, parm, var, data = _parse_file(filename)
    array_type = meta.get('type', '')
    if array_type.startswith('array_0d'):
        cls = DatFile0D
    elif array_type.startswith('array_1d'):
        cls = DatFile1D
    elif array_type.startswith('array_2d'):
        cls = DatFile2D
    else:
        raise RuntimeError(f'Unrecognised array type {array_type!r} in {filename}')
    return cls(source, meta, parm, cls._shape_values(meta, var, data))


# ---------------------------------------------------------------------------
# Combining helpers (kept for backward compat / internal use)
# ---------------------------------------------------------------------------

def combine_scan_dicts(a: dict, b: dict):
    from copy import deepcopy
    c = deepcopy(a)
    special_add = ('Ncount',)
    special_concatenate = ('Directory', 'filename', 'Date', 'Seed')
    special_ignore = ('signal', 'statistics', 'values')
    for k, v in b.items():
        if any(s in k for s in special_add):
            c[k] = int(c[k]) + int(v)
        elif any(s in k for s in special_concatenate):
            if v not in c[k]:
                c[k] = f'{c[k]} {v}'
        elif any(s in k for s in special_ignore):
            pass
        elif k in c:
            if c[k] != v:
                raise RuntimeError(f'Incompatible values for "{k}": {c[k]} and {v}')
        else:
            raise RuntimeError(f'Unexpected key {k} in {b}')
    return c


def combine_scan_lists(a: list, b: list):
    if a != b:
        raise RuntimeError(f'Incompatible lists {a} and {b}')
    return a


def combine_mccode_dats(dats: list):
    one = dats[0]
    for other in dats[1:]:
        one = one + other
    return one


def write_combined_mccode_dats(files: list[Union[Path, str]], output: Union[Path, str]):
    dats = combine_mccode_dats([read_mccode_dat(f) for f in files])
    dats.to_filename(output)


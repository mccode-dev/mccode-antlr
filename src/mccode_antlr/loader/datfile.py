from __future__ import annotations

from typing_extensions import deprecated

from dataclasses import dataclass, field
from typing import Any, Union
from pathlib import Path


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
    with source.open('r') as file:
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


@dataclass
class DatFileCommon:
    """Base class for McCode output data files.

    The *dataset* field is a :class:`scipp.Dataset` whose keys are the signal
    variable names from the file (conventionally ``'I'`` and ``'N'``; the error
    ``'I_err'`` is encoded as ``sqrt(dataset['I'].variances)``).  The ``metadata``
    and ``parameters`` dicts hold the text-format header information exactly as
    read from the file.
    """

    source: Path
    metadata: dict = field(default_factory=dict)
    parameters: dict = field(default_factory=dict)
    dataset: Any = field(default=None)  # sc.Dataset; typed as Any to avoid hard import

    # ------------------------------------------------------------------
    # Backward-compatible properties (replicate the old fields)
    # ------------------------------------------------------------------

    @property
    def variables(self) -> list[str]:
        """Variable names from the file header (backward compat)."""
        return self.metadata.get('variables', '').split()

    @property
    @deprecated("Access 'I' (with variance) or 'N' via getitem method")
    def data(self):
        """Datafile values as a numpy array (backward compat).

        Returns the ``('I', 'I_err', 'N')`` data variable values; shape is ``(3,nx)``
        for 1-D files and ``(3, ny, nx)`` for 2-D files.
        """
        from numpy import sqrt, stack
        if self.dataset is None:
            return None
        keys = list(self.dataset.keys())
        if not keys:
            return None
        if 'I' not in keys or 'N' not in keys:
            raise ValueError('I and/or N are missing')
        i_arr = self.dataset['I'].values
        i_var = self.dataset['I'].variances
        n_arr = self.dataset['N'].values
        return stack((i_arr, sqrt(i_var), n_arr))

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
    def _build_dataset(cls, meta: dict, var: list[str], data) -> Any:
        """Build a ``sc.Dataset`` from parsed file components.  Override in subclasses."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    @staticmethod
    def parts():
        return [], []

    def print_data(self, file):
        pass

    def _extract_numpy_rows(self) -> list:
        """Return a list of 1-D numpy arrays, one per variable, in original order."""
        import numpy as np
        rows = []
        for v in self.variables:
            if v in self.dataset:
                rows.append(self.dataset[v].values.ravel())
            elif v == 'I_err' and 'I' in self.dataset:
                rows.append(np.sqrt(self.dataset['I'].variances).ravel())
            else:
                keys = list(self.dataset.keys())
                rows.append(np.zeros_like(self.dataset[keys[0]].values).ravel() if keys else np.array([0.0]))
        return rows

    def to_filename(self, filename: str):
        sink = Path(filename).resolve()
        if sink.exists():
            raise RuntimeError(f'{filename} already exists')
        first, second = self.parts()
        with sink.open('w') as file:
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
        if self.dataset is not None and item in self.dataset:
            return self.dataset[item]
        # Backward compat: second variable is the standard deviation of the first
        var_list = self.variables
        if (var_list and len(var_list) > 1 and item == var_list[1]
                and self.dataset is not None and var_list[0] in self.dataset):
            import numpy as np
            return np.sqrt(self.dataset[var_list[0]].variances)
        if item in self.parameters:
            return self.parameters[item]
        if item in self.metadata:
            return self.metadata[item]
        raise KeyError(f'Unknown key {item!r}')

    # ------------------------------------------------------------------
    # Combining / arithmetic
    # ------------------------------------------------------------------

    def dim_metadata(self) -> list[dict]:
        """Return dimension metadata derived from scipp coordinates."""
        if self.dataset is None:
            return []
        result = []
        for dim in self.dataset.dims:
            coord = self.dataset.coords.get(dim)
            if coord is not None:
                result.append({'label': dim, 'values': coord.values, 'unit': str(coord.unit)})
        return result

    def safe_to_combine(self, other) -> bool:
        return False

    def __add__(self, other):
        if not self.safe_to_combine(other):
            raise RuntimeError('Cannot combine these two dat files')
        combined = self.dataset + other.dataset
        combined_meta = combine_scan_dicts(self.metadata, other.metadata)
        combined_parm = combine_scan_dicts(self.parameters, other.parameters)
        return type(self)(self.source, combined_meta, combined_parm, combined)

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

@dataclass
class DatFile0D(DatFileCommon):
    """0-dimensional McCode monitor output (single scalar result)."""

    @classmethod
    def _build_dataset(cls, meta: dict, var: list[str], data) -> Any:
        sc = _require_scipp()
        import numpy as np
        # data is shape (1, nv) or (nv,) after parsing
        flat = data.ravel()
        nv = len(var)
        if flat.size != nv:
            raise RuntimeError(f'Unexpected data size {flat.size} for {nv} variables')
        I_arr, I_err_arr, N_arr, extras = _extract_var_arrays(var, flat, ())
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

    def dim_metadata(self) -> list[dict]:
        return []

    def print_data(self, file):
        import numpy as np
        vals = []
        for v in self.variables:
            if v in self.dataset:
                vals.append(float(self.dataset[v].value))
            elif v == 'I_err' and 'I' in self.dataset:
                vals.append(float(np.sqrt(self.dataset['I'].variance)))
            else:
                vals.append(0.0)
        print(' '.join(str(x) for x in vals), file=file)

    @staticmethod
    def parts():
        first = ('Format', 'URL', 'Creator', 'Instrument', 'Ncount', 'Trace', 'Gravitation', 'Seed', 'Directory')
        second = ('Date', 'type', 'Source', 'component', 'position', 'title', 'Ncount', 'filename', 'statistics',
                  'signal', 'values', 'yvar', 'ylabel', 'xlimits', 'variables')
        return first, second

    def safe_to_combine(self, other) -> bool:
        if not isinstance(other, DatFile0D):
            return False
        if self.variables != other.variables:
            return False
        return True

    def __add__(self, other):
        if not self.safe_to_combine(other):
            raise RuntimeError('Cannot combine these two DatFile0D instances')
        combined = self.dataset + other.dataset
        combined_meta = combine_scan_dicts(self.metadata, other.metadata)
        combined_parm = combine_scan_dicts(self.parameters, other.parameters)
        return DatFile0D(self.source, combined_meta, combined_parm, combined)


@dataclass
class DatFile1D(DatFileCommon):
    """1-dimensional McCode monitor output (histogram)."""

    @classmethod
    def _build_dataset(cls, meta: dict, var: list[str], data) -> Any:
        sc = _require_scipp()
        from ._units import parse_mccode_label_unit
        import numpy as np
        nx = int(meta['type'].split('(', 1)[1].strip(')'))
        nv = len(var)
        # raw data shape is (nx, nv); reshape to (nv, nx)
        if data.shape == (nx, nv):
            arr = data.T  # → (nv, nx)
        elif data.shape == (nv, nx):
            arr = data
        else:
            raise RuntimeError(f'Unexpected data shape {data.shape} for nx={nx}, nv={nv}')
        lower, upper = [float(x) for x in meta['xlimits'].split()]
        bin_centers = np.linspace(lower, upper, nx)
        xlabel = meta.get('xlabel', 'x [1]')
        label, x_unit = parse_mccode_label_unit(xlabel)
        x_coord = sc.array(dims=[label], values=bin_centers, unit=x_unit)
        I_arr, I_err_arr, N_arr, extras = _extract_var_arrays(var, arr, (nx,))
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
        return [dim_metadata(self.dataset['I'].shape[0], self['xlabel'], lower_limit, upper_limit)]

    def print_data(self, file):
        import numpy as np
        rows = self._extract_numpy_rows()
        # each row is (nx,); transpose so we write (nx, nv) — one line per bin
        data_2d = np.array(rows)  # (nv, nx)
        for row in data_2d.T:
            print(' '.join(str(x) for x in row), file=file)

    @staticmethod
    def parts():
        first = ('Format', 'URL', 'Creator', 'Instrument', 'Ncount', 'Trace', 'Gravitation', 'Seed', 'Directory')
        second = ('Date', 'type', 'Source', 'component', 'position', 'title', 'Ncount', 'filename', 'statistics',
                  'signal', 'values', 'xvar', 'yvar', 'xlabel', 'ylabel', 'xlimits', 'variables')
        return first, second

    def safe_to_combine(self, other) -> bool:
        if not isinstance(other, DatFile1D):
            return False
        if list(self.dataset.keys()) != list(other.dataset.keys()):
            return False
        if self.dataset.dims != other.dataset.dims:
            return False
        if self.metadata.get('xlimits') != other.metadata.get('xlimits'):
            return False
        if self.dataset['I'].shape != other.dataset['I'].shape:
            return False
        return True

    def __add__(self, other):
        if not self.safe_to_combine(other):
            raise RuntimeError('Cannot combine these two DatFile1D instances')
        combined = self.dataset + other.dataset
        combined_meta = combine_scan_dicts(self.metadata, other.metadata)
        combined_parm = combine_scan_dicts(self.parameters, other.parameters)
        return DatFile1D(self.source, combined_meta, combined_parm, combined)


@dataclass
class DatFile2D(DatFileCommon):
    """2-dimensional McCode monitor output (image / matrix)."""

    @classmethod
    def _build_dataset(cls, meta: dict, var: list[str], data) -> Any:
        sc = _require_scipp()
        from ._units import parse_mccode_label_unit
        import numpy as np
        nx, ny = [int(x) for x in meta['type'].split('(', 1)[1].strip(')').split(',')]
        nv = len(var)
        # raw data shape is (ny*nv, nx); reshape to (nv, ny, nx)
        if data.shape == (nv, ny, nx):
            arr = data
        elif data.shape == (ny * nv, nx):
            arr = data.reshape((nv, ny, nx))
        else:
            raise RuntimeError(f'Unexpected data shape {data.shape} for nx={nx}, ny={ny}, nv={nv}')
        lower_x, upper_x, lower_y, upper_y = [float(x) for x in meta['xylimits'].split()]
        x_centers = np.linspace(lower_x, upper_x, nx)
        y_centers = np.linspace(lower_y, upper_y, ny)
        xlabel = meta.get('xlabel', 'x [1]')
        ylabel = meta.get('ylabel', 'y [1]')
        x_label, x_unit = parse_mccode_label_unit(xlabel)
        y_label, y_unit = parse_mccode_label_unit(ylabel)
        x_coord = sc.array(dims=[x_label], values=x_centers, unit=x_unit)
        y_coord = sc.array(dims=[y_label], values=y_centers, unit=y_unit)
        I_arr, I_err_arr, N_arr, extras = _extract_var_arrays(var, arr, (ny, nx))
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
        nx = self.dataset['I'].shape[1]
        ny = self.dataset['I'].shape[0]
        return [dim_metadata(nx, self['xlabel'], lower_x, upper_x),
                dim_metadata(ny, self['ylabel'], lower_y, upper_y)]

    def print_data(self, file):
        import numpy as np
        labels = 'Data', 'Errors', 'Events'
        rows = self._extract_numpy_rows()
        nv = len(rows)
        var_list = self.variables
        for i, name in enumerate(var_list):
            label = labels[i] if i < len(labels) else f'Extra{i}'
            print(f'# {label} [{self.metadata["component"]}/{self.metadata["filename"]}] {name}:', file=file)
            mat = rows[i].reshape(self.dataset['I'].shape) if i < len(rows) else np.zeros(self.dataset['I'].shape)
            for row in mat:
                print(' '.join(str(x) for x in row), file=file)

    @staticmethod
    def parts():
        first = ('Format', 'URL', 'Creator', 'Instrument', 'Ncount', 'Trace', 'Gravitation', 'Seed', 'Directory')
        second = ('Date', 'type', 'Source', 'component', 'position', 'title', 'Ncount', 'filename', 'statistics',
                  'signal', 'values', 'xvar', 'yvar', 'xlabel', 'ylabel', 'zvar', 'zlabel', 'xylimits', 'variables')
        return first, second

    def safe_to_combine(self, other) -> bool:
        if not isinstance(other, DatFile2D):
            return False
        if list(self.dataset.keys()) != list(other.dataset.keys()):
            return False
        if self.dataset.dims != other.dataset.dims:
            return False
        if self.metadata.get('xylimits') != other.metadata.get('xylimits'):
            return False
        if self.dataset['I'].shape != other.dataset['I'].shape:
            return False
        return True

    def __add__(self, other):
        if not self.safe_to_combine(other):
            raise RuntimeError('Cannot combine these two DatFile2D instances')
        combined = self.dataset + other.dataset
        combined_meta = combine_scan_dicts(self.metadata, other.metadata)
        combined_parm = combine_scan_dicts(self.parameters, other.parameters)
        return DatFile2D(self.source, combined_meta, combined_parm, combined)


# ---------------------------------------------------------------------------
# File loading
# ---------------------------------------------------------------------------

def read_mccode_dat(filename: str | Path) -> DatFileCommon:
    """Load a McCode ``.dat`` output file, returning the appropriate subclass.

    Dispatches to :class:`DatFile0D`, :class:`DatFile1D`, or :class:`DatFile2D`
    based on the ``type`` metadata key.  Requires **scipp** to be installed.
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
    dataset = cls._build_dataset(meta, var, data)
    return cls(source, meta, parm, dataset)


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


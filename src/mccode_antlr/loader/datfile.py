from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union
from pathlib import Path
from numpy import ndarray

# TODO: Find a way to remove this ndarray dependency on numpy?
#       As is, DatFile* is not serialized, so left as a dataclass for now.

@dataclass
class DatFileCommon:
    source: Path
    metadata: dict = field(default_factory=dict)
    parameters: dict = field(default_factory=dict)
    variables: list[str] = field(default_factory=list)
    data: ndarray = field(default_factory=ndarray)

    @classmethod
    def from_filename(cls, filename: str | Path):
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
        var = meta.get('variables', '').split(' ')
        data = array([[float(x) for x in line.strip().split()] for line in filter(lambda x: x[0] != '#', lines)])
        return cls(source, meta, parm, var, data)

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
        with sink.open('w') as file:
            for item in first:
                print(f'# {item}: {self.metadata[item]}', file=file)
            for param in self.parameters:
                print(f'# Param: {param}={self.parameters[param]}', file=file)
            for item in second:
                print(f'# {item}: {self.metadata[item]}', file=file)
            self.print_data(file)

    def __getitem__(self, item):
        if item in self.variables:
            index = [i for i, x in enumerate(self.variables) if x == item]
            if len(index) != 1:
                raise RuntimeError(f'Expected one index for {item} but found {index}')
            return self.data[index[0], ...]
        elif item in self.parameters:
            return self.parameters[item]
        elif item in self.metadata:
            return self.metadata[item]
        else:
            raise KeyError(f'Unknown key {item}')

    def dim_metadata(self) -> list[dict]:
        pass

    @staticmethod
    def safe_to_combine(other):
        return False

    def __add__(self, other):
        if not self.safe_to_combine(other):
            raise RuntimeError('Cannot combine these two dat files')
        metadata = combine_scan_dicts(self.metadata, other.metadata)
        parameters = combine_scan_dicts(self.parameters, other.parameters)
        variables = combine_scan_lists(self.variables, other.variables)
        data = combine_scan_data(self.data, other.data)
        return DatFileCommon(Path(), metadata, parameters, variables, data)

    @property
    def structured(self):
        from numpy import frombuffer
        d_types = [(v, self.data.dtype) for v in self.variables]
        order = list(range(1, self.data.ndim)) + [0]
        s = frombuffer(self.data.transpose(*order).tobytes(), dtype=d_types)
        if len(order) > 1:
            s = s.reshape([self.data.shape[x] for x in order[:-1]])
        return s

def dim_metadata(length, label_unit, lower_limit, upper_limit) -> dict:
    from numpy import linspace
    label = label_unit.split(' ', 1)[0]
    unit = label_unit.split(' ', 1)[1].strip('[] ')
    if '\\gms' == unit:
        unit = 'microseconds'
    bin_width = (upper_limit - lower_limit) / (length - 1)
    boundaries = linspace(lower_limit - bin_width / 2, upper_limit + bin_width / 2, length + 1)
    return dict(lenght=length, label=label, unit=unit, bin_boundaries=boundaries)


@dataclass
class DatFile0D(DatFileCommon):
    def __post_init__(self):
        nv = len(self.variables)
        if self.data.shape == (nv, ):
            # shortcut in case we're already in the right shape (e.g., from __add__)
            return
        if self.data.size != nv:
            raise RuntimeError(f'Unexpected data shape {self.data.shape} for metadata specifying {nv=}')
        self.data = self.data.reshape((nv, ))

    def dim_metadata(self) -> list[dict]:
        return []

    def print_data(self, file):
        print(' '.join(str(x) for x in self.data), file=file)

    @staticmethod
    def parts():
        # Yes, Ncount shows up twice ...
        first = ('Format', 'URL', 'Creator', 'Instrument', 'Ncount', 'Trace', 'Gravitation', 'Seed', 'Directory')
        second = ('Date', 'type', 'Source', 'component', 'position', 'title', 'Ncount', 'filename', 'statistics',
                  'signal', 'values', 'yvar', 'ylabel', 'xlimits', 'variables')
        return first, second

    def safe_to_combine(self, other):
        if not isinstance(other, DatFile1D):
            return False
        if self.variables != other.variables:
            return False
        if self.data.shape != other.data.shape:
            return False
        return True

    def __add__(self, other):
        both = super().__add__(other)
        return DatFile1D(both.source, both.metadata, both.parameters, both.variables, both.data)


@dataclass
class DatFile1D(DatFileCommon):
    def __post_init__(self):
        nx = int(self.metadata['type'].split('(', 1)[1].strip(')'))
        nv = len(self.variables)
        if self.data.shape == (nv, nx):
            # shortcut in case we're already in the right shape (e.g., from __add__)
            return
        if self.data.shape[0] != nx or self.data.shape[1] != nv:
            raise RuntimeError(f'Unexpected data shape {self.data.shape} for metadata specifying {nx=} and {nv=}')
        # we always want the variables along the first dimension:
        self.data = self.data.transpose((1, 0))

    def dim_metadata(self) -> list[dict]:
        lower_limit, upper_limit = [float(x) for x in self['xlimits'].split()]
        return [dim_metadata(self.data.shape[1], self['xlabel'], lower_limit, upper_limit), ]

    def print_data(self, file):
        for row in self.data.transpose((1, 0)):
            print(' '.join(str(x) for x in row), file=file)

    @staticmethod
    def parts():
        # Yes, Ncount shows up twice ...
        first = ('Format', 'URL', 'Creator', 'Instrument', 'Ncount', 'Trace', 'Gravitation', 'Seed', 'Directory')
        second = ('Date', 'type', 'Source', 'component', 'position', 'title', 'Ncount', 'filename', 'statistics',
                  'signal', 'values', 'xvar', 'yvar', 'xlabel', 'ylabel', 'xlimits', 'variables')
        return first, second

    def safe_to_combine(self, other):
        if not isinstance(other, DatFile1D):
            return False
        if self.variables != other.variables:
            return False
        if self.metadata['xlabel'] != other.metadata['xlabel']:
            return False
        if self.metadata['xlimits'] != other.metadata['xlimits']:
            return False
        if self.data.shape != other.data.shape:
            return False
        return True

    def __add__(self, other):
        both = super().__add__(other)
        return DatFile1D(both.source, both.metadata, both.parameters, both.variables, both.data)


@dataclass
class DatFile2D(DatFileCommon):
    def __post_init__(self):
        nx, ny = [int(x) for x in self.metadata['type'].split('(', 1)[1].strip(')').split(',')]
        nv = len(self.variables)
        if self.data.shape == (nv, ny, nx):
            # shortcut in case we're already in the right shape (e.g., from __add__)
            return
        if self.data.shape[0] != ny * nv or self.data.shape[1] != nx:
            raise RuntimeError(f'Expected {ny*nv =} by {nx =} but have {self.data.shape}')
        self.data = self.data.reshape((nv, ny, nx))

    def dim_metadata(self) -> list[dict]:
        lower_x, upper_x, lower_y, upper_y = [float(x) for x in self['xylimits'].split()]
        return [dim_metadata(self.data.shape[2], self['xlabel'], lower_x, upper_x),
                dim_metadata(self.data.shape[1], self['ylabel'], lower_y, upper_y)]

    @staticmethod
    def parts():
        first = ('Format', 'URL', 'Creator', 'Instrument', 'Ncount', 'Trace', 'Gravitation', 'Seed', 'Directory')
        second = ('Date', 'type', 'Source', 'component', 'position', 'title', 'Ncount', 'filename', 'statistics',
                  'signal', 'values', 'xvar', 'yvar', 'xlabel', 'ylabel', 'zvar', 'zlabel', 'xylimits', 'variables')
        return first, second

    def print_data(self, file):
        labels = 'Data', 'Errors', 'Events'  # McPlot looks at only these labels to determine what is the data
        for i, n in enumerate(self.variables):
            print(f'# {labels[i]} [{self.metadata["component"]}/{self.metadata["filename"]}] {n}:', file=file)
            for row in self.data[i, ...]:
                print(' '.join(str(x) for x in row), file=file)

    def safe_to_combine(self, other):
        if not isinstance(other, DatFile2D):
            return False
        if self.variables != other.variables:
            return False
        if self.metadata['xlabel'] != other.metadata['xlabel']:
            return False
        if self.metadata['ylabel'] != other.metadata['ylabel']:
            return False
        if self.metadata['xylimits'] != other.metadata['xylimits']:
            return False
        if self.data.shape != other.data.shape:
            return False
        return True

    def __add__(self, other):
        both = super().__add__(other)
        return DatFile2D(both.source, both.metadata, both.parameters, both.variables, both.data)


def read_mccode_dat(filename: str | Path):
    common = DatFileCommon.from_filename(filename)
    array_type = common.metadata['type']
    ndim, data_type = -1, None
    if array_type.startswith('array_0d'):
        ndim, data_type = 0, DatFile0D
    elif array_type.startswith('array_1d'):
        ndim, data_type = 1, DatFile1D
    elif array_type.startswith('array_2d'):
        ndim, data_type = 2, DatFile2D
    if ndim < 0 or ndim > 2:
        raise RuntimeError(f'Unexpected number of dimensions: {ndim}')
    return data_type(common.source, common.metadata, common.parameters, common.variables, common.data)


def combine_scan_dicts(a: dict, b: dict):
    from copy import deepcopy
    c = deepcopy(a)
    special_add = 'Ncount',
    special_concatenate = 'Directory', 'filename', 'Date', 'Seed'
    special_ignore = 'signal', 'statistics', 'values'
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


def combine_scan_data(a: ndarray, b: ndarray):
    if a.shape != b.shape:
        raise RuntimeError(f'Incompatible shapes {a.shape} and {b.shape}')
    if a.ndim == 2:
        from copy import deepcopy
        # variables are _always_ (?) (..., I, I_err, N)
        c = deepcopy(a)
        c[-3:, :] = a[-3:, :] + b[-3:, :]
        return c
    elif a.ndim == 3:
        # but 3-D _only_ contains (I, I_err, N)
        return a + b
    else:
        raise RuntimeError(f'Unexpected number of dimensions: {a.ndim}')


def combine_mccode_dats(dats: list):
    one = dats[0]
    for other in dats[1:]:
        one = one + other
    return one


def write_combined_mccode_dats(files: list[Union[Path, str]], output: Union[Path, str]):
    dats = combine_mccode_dats([read_mccode_dat(f) for f in files])
    dats.to_filename(output)



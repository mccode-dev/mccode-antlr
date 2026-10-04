from dataclasses import dataclass, field
from typing import Union
from pathlib import Path


def read_keywords(lines: list[str], keywords: list[str], delim: str = None):
    if delim is None:
        delim = ':'
    if len(lines) < len(keywords):
        raise RuntimeError(f"Expected {len(keywords)} lines, got {len(lines)}")
    for line, keyword in zip(lines, keywords):
        key, _, value = line.partition(delim)
        if key.strip() != keyword:
            raise RuntimeError(f"Expected keyword {keyword}, got {key}")
        yield value.strip()


@dataclass
class SimFileHeader:
    description: str
    Date: str
    Program: str

    @staticmethod
    def parse(contents: str):
        contents = contents.strip()
        lines = contents.split('\n')
        if len(lines) != 3:
            raise RuntimeError(f"Expected 3 lines in header, got {len(lines)}")
        description = lines[0].strip()
        date, program = read_keywords(lines[1:], ['Date', 'Program'])
        return SimFileHeader(description=description, Date=date, Program=program)

    def to_file(self, file):
        print(self.description, file=file)
        print(f"Date: {self.Date}", file=file)
        print(f"Program: {self.Program}", file=file)

    def __contains__(self, other):
        if not isinstance(other, SimFileHeader):
            raise RuntimeError(f"Cannot compare header with {other}")
        return other.description in self.description and other.Date in self.Date and other.Program in self.Program

    def combine(self, other):
        if other in self:
            return self
        if self in other:
            return other
        # combine from the right, so self.description might already have other.description in it
        desc = self.description if other.description in self.description else f'{self.description} + {other.description}'
        date = self.Date if other.Date in self.Date else f"{self.Date} + {other.Date}"
        program = self.Program if other.Program in self.Program else f"{self.Program} + {other.Program}"
        return SimFileHeader(description=desc, Date=date, Program=program)


@dataclass
class SimFileInstrument:
    name: str
    File: str
    Source: str
    Parameters: str
    Trace_enabled: bool
    Default_main: bool
    Embedded_runtime: bool

    @staticmethod
    def parse(contents: str):
        contents = contents.strip()
        lines = contents.split('\n')
        if len(lines) != 7:
            raise RuntimeError(f"Expected 7 lines in instrument, got {len(lines)}")
        name = lines[0].strip()
        keywords = ['File', 'Source', 'Parameters', 'Trace_enabled', 'Default_main', 'Embedded_runtime']
        file, source, parameters, trace, default, embed = read_keywords(lines[1:], keywords)
        trace = trace == 'yes'
        default = default == 'yes'
        embed = embed == 'yes'
        return SimFileInstrument(name=name, File=file, Source=source, Parameters=parameters, Trace_enabled=trace,
                                 Default_main=default, Embedded_runtime=embed)

    def to_file(self, file):
        print(f'begin instrument: {self.name}', file=file)
        print(f"  File: {self.File}", file=file)
        print(f"  Source: {self.Source}", file=file)
        print(f"  Parameters: {self.Parameters}", file=file)
        print(f"  Trace_enabled: {'yes' if self.Trace_enabled else 'no'}", file=file)
        print(f"  Default_main: {'yes' if self.Default_main else 'no'}", file=file)
        print(f"  Embedded_runtime: {'yes' if self.Embedded_runtime else 'no'}", file=file)
        print(f'end instrument', file=file)

    def __contains__(self, other):
        if not isinstance(other, SimFileInstrument):
            raise RuntimeError(f"Cannot compare instrument with {other}")
        return other.name in self.name and other.File in self.File and other.Source in self.Source and \
            other.Parameters in self.Parameters and other.Trace_enabled == self.Trace_enabled and \
            other.Default_main == self.Default_main and other.Embedded_runtime == self.Embedded_runtime

    def combine(self, other):
        if other in self:
            return self
        if self in other:
            return other
        # combine from the right, so self.name might already have other.name in it
        name = self.name if other.name in self.name else f'{self.name} + {other.name}'
        file = self.File if other.File in self.File else f"{self.File} + {other.File}"
        source = self.Source if other.Source in self.Source else f"{self.Source} + {other.Source}"
        # parameters are a bit different in that we want their ordered union:
        pars = dict.fromkeys([p.strip() for p in self.Parameters.split(' ')])
        pars.update(dict.fromkeys([p.strip() for p in other.Parameters.split(' ')]))
        parameters = ' '.join(list(pars.keys()))
        trace = self.Trace_enabled and other.Trace_enabled
        default = self.Default_main and other.Default_main
        embed = self.Embedded_runtime and other.Embedded_runtime
        return SimFileInstrument(name=name, File=file, Source=source, Parameters=parameters, Trace_enabled=trace,
                                 Default_main=default, Embedded_runtime=embed)


@dataclass
class SimFileSimulation:
    name: str
    Format: str
    URL: str
    Creator: str
    Instrument: str
    Ncount: int
    Trace: bool
    Gravitation: bool
    Seed: int
    Directory: str
    Params: list[str] = field(default_factory=list)

    @staticmethod
    def parse(contents: str):
        contents = contents.strip()
        lines = contents.split('\n')
        if len(lines) < 10:
            raise RuntimeError(f"Expected at least 10 lines in simulation, got {len(lines)}")
        name = lines[0].strip()
        keywords = ['Format', 'URL', 'Creator', 'Instrument', 'Ncount', 'Trace', 'Gravitation', 'Seed', 'Directory']
        format, url, creator, instrument, ncount, trace, gravitation, seed, directory = read_keywords(lines[1:10],
                                                                                                      keywords)
        params = []
        for line in lines[10:]:
            _, _, param = line.partition(':')
            params.append(param.strip())
        ncount = int(ncount)
        trace = trace == 'yes'
        gravitation = gravitation == 'yes'
        seed = int(seed)
        return SimFileSimulation(name=name, Format=format, URL=url, Creator=creator, Instrument=instrument,
                                 Ncount=ncount, Trace=trace, Gravitation=gravitation, Seed=seed, Directory=directory,
                                 Params=params)

    def to_file(self, file):
        print(f'begin simulation: {self.name}', file=file)
        print(f"  Format: {self.Format}", file=file)
        print(f"  URL: {self.URL}", file=file)
        print(f"  Creator: {self.Creator}", file=file)
        print(f"  Instrument: {self.Instrument}", file=file)
        print(f"  Ncount: {self.Ncount}", file=file)
        print(f"  Trace: {'yes' if self.Trace else 'no'}", file=file)
        print(f"  Gravitation: {'yes' if self.Gravitation else 'no'}", file=file)
        print(f"  Seed: {self.Seed}", file=file)
        print(f"  Directory: {self.Directory}", file=file)
        for param in self.Params:
            print(f"  Param: {param}", file=file)
        print(f'end simulation', file=file)

    def __contains__(self, other):
        if not isinstance(other, SimFileSimulation):
            raise RuntimeError(f"Cannot compare simulation with {other}")
        return other.name in self.name and other.Format in self.Format and other.URL in self.URL and \
            other.Creator in self.Creator and other.Instrument in self.Instrument and \
            other.Trace == self.Trace and other.Gravitation == self.Gravitation and \
            other.Directory in self.Directory and all(p in self.Params for p in other.Params)

    def __eq__(self, other):
        if not isinstance(other, SimFileSimulation):
            raise RuntimeError(f"Cannot compare simulation with {other}")
        return other.name == self.name and other.Format == self.Format and other.URL == self.URL and \
            other.Creator == self.Creator and other.Instrument == self.Instrument and \
            other.Trace == self.Trace and other.Gravitation == self.Gravitation and \
            other.Directory == self.Directory and all(p in self.Params for p in other.Params)

    def combine(self, other):
        from copy import deepcopy
        if other == self:
            # combining a repeat which was done to improve statistics
            out = deepcopy(self)
            out.Ncount += other.Ncount
            if other.Seed == self.Seed:
                from loguru import logger
                logger.warning('combining two simulations with the same seed is not statistically valid')
            return out
        if other in self:
            return self
        elif self in other:
            return other
        # combine from the right, so self.name might already have other.name in it
        name = self.name if other.name in self.name else f'{self.name} + {other.name}'
        format = self.Format if other.Format in self.Format else f"{self.Format} + {other.Format}"
        url = self.URL if other.URL in self.URL else f"{self.URL} + {other.URL}"
        creator = self.Creator if other.Creator in self.Creator else f"{self.Creator} + {other.Creator}"
        instrument = self.Instrument if other.Instrument in self.Instrument else f"{self.Instrument} + {other.Instrument}"
        # TODO this is *not* a repeat. What do we do with the number of particles?
        ncount = min(self.Ncount, other.Ncount)
        trace = self.Trace and other.Trace
        gravitation = self.Gravitation and other.Gravitation
        seed = self.Seed if self.Seed == other.Seed else -1
        directory = self.Directory if other.Directory in self.Directory else f"{self.Directory} + {other.Directory}"
        params = dict.fromkeys(self.Params)
        params.update(dict.fromkeys(other.Params))
        params = list(params.keys())
        return SimFileSimulation(name=name, Format=format, URL=url, Creator=creator, Instrument=instrument,
                                 Ncount=ncount, Trace=trace, Gravitation=gravitation, Seed=seed, Directory=directory,
                                 Params=params)


@dataclass
class SimFileData:
    keywords: list[str]
    Date: str
    type: str
    Source: str
    component: str
    position: str
    title: str
    Ncount: int
    statistics: str
    signal: str
    values: str
    filename: str = None  # Not defined for 0-D data entries
    xvar: str = None  # Not defined for 0-D data entries
    yvar: str = None  # Not defined for 0-D data entries
    xlabel: str = None  # Not defined for 0-D data entries
    ylabel: str = None  # Not defined for 0-D data entries
    variables: str = None  # Not defined for 0-D data entries
    xlimits: str = None  # only defined for 1-D data entries
    zvar: str = None  # only defined for 2-D data entries
    zlabel: str = None  # only defined for 2-D data entries
    xylimits: str = None  # only defined for 2-D data entries

    @staticmethod
    def parse(contents: str):
        contents = contents.strip()
        lines = contents.split('\n')
        first_keywords = ['Date', 'type', 'Source', 'component', 'position', 'title', 'Ncount']
        second_keywords = ['statistics', 'signal', 'values']
        file_keyword = []
        if len(lines) == 12:
            # 0-D -- old style
            last_keywords = ['xylimits', 'variables']
        elif len(lines) == 13:
            # 0-D -- new style (as of when?)
            file_keyword = ['filename']
            last_keywords = ['xylimits', 'variables']
        elif len(lines) == 17:
            # 1-D
            file_keyword = ['filename']
            last_keywords = ['xvar', 'yvar', 'xlabel', 'ylabel', 'xlimits', 'variables']
        elif len(lines) == 19:
            # 2-D
            file_keyword = ['filename']
            last_keywords = ['xvar', 'yvar', 'xlabel', 'ylabel', 'zvar', 'zlabel', 'xylimits', 'variables']
        else:
            raise RuntimeError(f"Expected 12, 13, 17 or 19 lines in data, got {len(lines)}")
        keywords = first_keywords + file_keyword + second_keywords + last_keywords
        values = list(read_keywords(lines, keywords))
        collected = {k: v for k, v in zip(keywords, values)}
        collected['Ncount'] = int(collected['Ncount'])
        return SimFileData(keywords=keywords, **collected)

    def to_file(self, file):
        print(f'begin data', file=file)
        for key in self.keywords:
            if getattr(self, key) is not None:
                print(f'  {key}: {getattr(self, key)}', file=file)
        print(f'end data', file=file)

    def __eq__(self, other):
        if not isinstance(other, SimFileData):
            raise RuntimeError(f"Cannot compare data with {other}")
        return all(getattr(self, k) == getattr(other, k) for k in self.keywords)

    def is_repeat(self, other):
        # Everything must match except Date, Ncount, statistics, signal, values.
        # The Date is the date the simulation was run, so it will be different.
        # The Ncount is the number of particles used in the simulation, so it can be different.
        # The statistics, signal, and values are the results of the simulation, so they will be different.
        if not isinstance(other, SimFileData):
            raise RuntimeError(f"Cannot compare data with {other}")
        skip = ['Date', 'Ncount', 'statistics', 'signal', 'values']
        return all(getattr(self, k) == getattr(other, k) for k in self.keywords if k not in skip)

    def combine(self, other):
        from math import sqrt
        # this should only happen if the simulations are repeats of each other
        if not self.is_repeat(other):
            raise RuntimeError(f"Cannot combine non-repeated {self} with {other}")
        from copy import deepcopy
        out = deepcopy(self)
        out.Ncount += other.Ncount

        def split_statistics(s: str):
            return {k: float(v) for k, v in [z.strip(';').split('=', 1) for z in s.split()]}

        def split_signal(s: str):
            return [float(x.split('=')[1].split(';')[0]) for x in s.split(' ')]

        def split_values(v: str):
            return [int(x) if x.is_integer() else x for x in [float(x) for x in v.split(' ')]]

        # The values line is always "{float} {float} {int}" which _I think_ is <intensity>, <error>, and event count
        s_intensity, s_error, s_counts = split_values(self.values)
        o_intensity, o_error, o_counts = split_values(other.values)
        out.values = f"{s_intensity + o_intensity} {sqrt(s_error * s_error + o_error + o_error)} {s_counts + o_counts}"

        # The signal line is always? "None" or "Min={float}; Max={float}; Mean={float};"
        # we can combine min and max, but not mean (without knowing the number of points)
        if 'None' in self.signal or 'None' in other.signal:
            out.signal = 'None'
        else:
            s_min, s_max, s_mean = split_signal(self.signal)
            o_min, o_max, o_mean = split_signal(other.signal)
            mean_estimate = (s_mean * s_counts + o_mean * o_counts)/(s_counts + o_counts)
            out.signal = f"Min={min(s_min, o_min)}; Max={max(s_max, o_max)}; Mean={mean_estimate};"

        # Statistics: one of "None", "X0={float}; dX={float};" or "X0={float}; dX={float}; Y0={float}; dY={float};"
        # we can combine the values under the assumption that the distribution is Gaussian, but only if we know
        # the overall intensity as well.
        if 'None' in self.statistics or 'None' in other.statistics:
            out.statistics = 'None'
        else:
            s_stats = split_statistics(self.statistics)
            o_stats = split_statistics(other.statistics)
            stats = {}
            for d in ('X', 'Y'):
                d0, dd = f'{d}0', f'd{d}'
                if d0 in s_stats and d0 in o_stats:
                    stats[d0] = (s_stats[d0] * s_counts + o_stats[d0] * o_counts)/(s_counts + o_counts)
                if dd in s_stats and dd in o_stats:
                    sd = s_stats[dd] * s_counts
                    od = o_stats[dd] * o_counts
                    stats[dd] = sqrt(sd * sd + od * od) / (s_counts + o_counts)
            out.statistics = ' '.join([f"{k}={stats[k]};" for k in ['X0', 'dX', 'Y0', 'dY'] if k in stats])
        return out


@dataclass
class SimFile:
    header: SimFileHeader = field(default_factory=SimFileHeader)
    instrument: SimFileInstrument = field(default_factory=SimFileInstrument)
    simulation: SimFileSimulation = field(default_factory=SimFileSimulation)
    data: list[SimFileData] = field(default_factory=list)

    @staticmethod
    def load(source: Union[str, Path]):
        if not isinstance(source, Path):
            source = Path(source)
        if not source.is_file():
            raise FileNotFoundError(f"Could not find file {source}")
        with source.open('r', encoding='utf-8', errors='replace') as f:
            contents = f.read()
        return SimFile.parse(contents)

    def save(self, filename: Union[str, Path]):
        if not isinstance(filename, Path):
            filename = Path(filename)
        with filename.open('w', encoding='utf-8') as f:
            self.to_file(f)

    @staticmethod
    def parse(contents: str):
        # split into sub-string parts:
        header, _, rest = contents.partition('begin instrument: ')
        instrument, _, rest = rest.partition('begin simulation: ')
        instrument, _, _ = instrument.partition('end instrument')
        simulation, _, rest = rest.partition('end simulation')
        data = []
        while rest:
            datum, _, rest = rest.partition('end data')
            _, _, datum = datum.partition('begin data')
            if len(datum.strip()):
                data.append(datum.strip())

        # convert sub-strings into objects:
        header = SimFileHeader.parse(header)
        instrument = SimFileInstrument.parse(instrument)
        simulation = SimFileSimulation.parse(simulation)
        data = [SimFileData.parse(datum.strip()) for datum in data]
        return SimFile(header=header, instrument=instrument, simulation=simulation, data=data)

    def to_file(self, file):
        self.header.to_file(file)
        print(file=file)
        self.instrument.to_file(file)
        print(file=file)
        self.simulation.to_file(file)
        print(file=file)
        for datum in self.data:
            datum.to_file(file)
            print(file=file)


def read_mccode_sim(filename: Union[str, Path]):
    return SimFile.load(filename)


def combine_mccode_sims(sims: list[SimFile]):
    """Combine multiple McCode simulation files together into a single file.

    Each file could be a repeat of the same simulation (to improve statistics)
    or an extension of an earlier simulation to add flightpath, components, detectors, etc."""
    if len(sims) == 0:
        raise RuntimeError("No simulations to combine")

    for sim in sims:
        if not isinstance(sim.header, SimFileHeader):
            raise RuntimeError(f"Header not a SimFileHeader")
        if not isinstance(sim.instrument, SimFileInstrument):
            raise RuntimeError(f"Instrument not a SimFileInstrument")
        if not isinstance(sim.simulation, SimFileSimulation):
            raise RuntimeError(f"Simulation is not a SimFileSimulation")
        for datum in sim.data:
            if not isinstance(datum, SimFileData):
                raise RuntimeError(f"Datum not a SimFileData")

    header = sims[0].header
    instrument = sims[0].instrument
    simulation = sims[0].simulation
    data = {(d.component, d.filename): d for d in sims[0].data}
    for sim in sims[1:]:
        header = header.combine(sim.header)
        instrument = instrument.combine(sim.instrument)
        simulation = simulation.combine(sim.simulation)
        for datum in sim.data:
            key = (datum.component, datum.filename)
            if key not in data:
                data[key] = datum
            else:
                data[key] = data[key].combine(datum)
    return SimFile(header=header, instrument=instrument, simulation=simulation, data=list(data.values()))


def write_combined_mccode_sims(files: list[Union[Path, str]], output: Union[Path, str]):
    sims = [SimFile.load(f) for f in files]
    combined = combine_mccode_sims(sims)
    combined.save(output)

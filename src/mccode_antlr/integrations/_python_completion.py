from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from inspect import signature
from typing import Literal

from mccode_antlr import Flavor
from mccode_antlr.assembler import Assembler
from mccode_antlr.run import Simulation


@dataclass(frozen=True)
class CompletionCandidate:
    label: str
    kind: Literal['component', 'component_parameter', 'instrument_parameter', 'runtime_parameter']
    insert_text: str | None = None
    detail: str = ''
    documentation: str | None = None


def _flavor_enum(flavor: Flavor | str | None) -> Flavor:
    if flavor is None:
        return Flavor.MCSTAS
    if isinstance(flavor, Flavor):
        return flavor
    name = str(flavor).upper().replace('-', '_')
    return Flavor[name] if name in Flavor.__members__ else Flavor.MCSTAS


@lru_cache(maxsize=4)
def _cached_reader(flavor: Flavor):
    from mccode_antlr.reader import Reader

    return Reader(flavor=flavor)


def _reader_for(assembler: Assembler | None, flavor: Flavor | str | None):
    if assembler is not None:
        return assembler.reader
    return _cached_reader(_flavor_enum(flavor))


def _component_name_from_path(filepath):
    """Take a string or Path and return 'name' out of /some/path/to/name.ext"""
    from pathlib import Path
    return filepath.stem if isinstance(filepath, Path) else Path(filepath).stem


def _component_names_from_reader(reader) -> list[str]:
    names: set[str] = set()
    for registry in reader.registries:
        try:
            for fname in registry.filenames():
                if fname.lower().endswith('.comp'):
                    # Strip any leading directory information and insert into the set:
                    names.add(_component_name_from_path(fname))
        except Exception:
            continue
    return sorted(names)


def get_component_names(*, assembler: Assembler | None = None, flavor: Flavor | str | None = None) -> list[CompletionCandidate]:
    reader = _reader_for(assembler, flavor)
    return [
        CompletionCandidate(label=name, kind='component')
        for name in _component_names_from_reader(reader)
    ]


def _param_detail(parameter) -> str:
    try:
        value = parameter.value
        data_type = value.data_type.name.lower()
        if value.is_vector:
            data_type = f'vector {data_type}'
        detail = f'{data_type} = {value}' if value.has_value else data_type
    except Exception:
        detail = str(getattr(parameter, 'value', ''))
    unit = getattr(parameter, 'unit', None)
    if unit:
        detail = f'{detail} [{unit}]' if detail else f'[{unit}]'
    return detail


def get_component_parameters(component_name: str, *, assembler: Assembler | None = None, flavor: Flavor | str | None = None) -> list[CompletionCandidate]:
    reader = _reader_for(assembler, flavor)
    if not reader.known(component_name):
        return []
    component = reader.get_component(component_name)
    items: list[CompletionCandidate] = []
    for parameter in list(component.define) + list(component.setting):
        items.append(
            CompletionCandidate(
                label=parameter.name,
                kind='component_parameter',
                detail=_param_detail(parameter),
                documentation=getattr(parameter, 'description', None),
            )
        )
    return items


def get_instrument_parameters(simulation: Simulation) -> list[CompletionCandidate]:
    return [
        CompletionCandidate(
            label=parameter.name,
            kind='instrument_parameter',
            detail=_param_detail(parameter),
        )
        for parameter in simulation.instr.parameters
    ]


def get_component_instance_names(assembler: Assembler) -> list[CompletionCandidate]:
    return [
        CompletionCandidate(label=instance.name, kind='component')
        for instance in assembler.instrument.components
    ]


def get_runtime_keywords(method_name: str) -> list[CompletionCandidate]:
    method = getattr(Simulation, method_name)
    items: list[CompletionCandidate] = []
    for name, parameter in signature(method).parameters.items():
        if name in {'self', 'parameters'}:
            continue
        if parameter.kind not in (parameter.KEYWORD_ONLY, parameter.POSITIONAL_OR_KEYWORD):
            continue
        items.append(
            CompletionCandidate(
                label=name,
                kind='runtime_parameter',
                insert_text=f'{name}=',
            )
        )
    return items

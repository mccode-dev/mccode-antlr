from __future__ import annotations

from pathlib import Path
from typing import Union
from loguru import logger

VERSION_NAME_KEY = 'mccode-antlr_version_data-type-name'


def _split_version_name(version_name):
    return version_name.split('/', 1)


def _write_header(group, data_type):
    from mccode_antlr.version import version
    group.attrs[VERSION_NAME_KEY] = f'{version()}/{data_type.__name__}'


def _check_header(group, data_type):
    from mccode_antlr.version import version as module_version
    if VERSION_NAME_KEY not in group.attrs:
        raise RuntimeError(f"File does not have type information")
    version, name = _split_version_name(group.attrs[VERSION_NAME_KEY])
    if version != module_version():
        raise RuntimeError(f"File was created with mccode_antlr {version}, but asked to read {module_version()}")
    if name != data_type.__name__:
        raise RuntimeError(f"Group contains mccode_antlr type {name}, but asked to read type {data_type}")


def _standard_read(typename, group, attrs, optional, required, **kwargs):
    _check_header(group, typename)
    values = {name: group.attrs.get(name) for name in attrs}
    for name in optional:
        if name in group:
            values[name] = HDF5IO.load(group[name], **kwargs)
    for name in required:
        if name in group:
            values[name] = HDF5IO.load(group[name], **kwargs)
        else:
            logger.warning('Missing required value!')
            values[name] = None
    if any(values[r] is None for r in required):
        raise ValueError(f"Could not load required values for {typename}")
    return values


def _standard_save(typename, group, data, attrs, fields, **kwargs):
    _write_header(group, typename)
    for name in attrs:
        if getattr(data, name) is not None:
            group.attrs[name] = getattr(data, name)
    for name in fields:
        if getattr(data, name) is not None:
            HDF5IO.save(group=group.create_group(name), data=getattr(data, name), **kwargs)


def _dataclass_io(real_type, attrs: tuple = None, optional: tuple = None, required: tuple = None):
    attrs, optional, required = (attrs or (), optional or (), required or ())

    class _DataclassIO:
        @staticmethod
        def load(group, **kwargs) -> real_type:
            return real_type(**_standard_read(real_type, group, attrs, optional, required, **kwargs))

        @staticmethod
        def save(group, data, **kwargs):
            _standard_save(real_type, group, data, attrs, optional+required, **kwargs)

    return _DataclassIO


class DataSourceIO:
    from mccode_antlr.common.metadata import DataSource

    @staticmethod
    def load(group, **kwargs) -> DataSource:
        values = _standard_read(DataSourceIO.DataSource, group, ('name', 'type_name'), (), (), **kwargs)
        return DataSourceIO.DataSource.from_type_name_and_name(values['type_name'], values['name'])

    @staticmethod
    def save(group, data, **kwargs):
        _standard_save(DataSourceIO.DataSource, group, data, ('name', 'type_name'), (), **kwargs)


class InstanceIO:
    from mccode_antlr.comp import Comp
    from mccode_antlr.instr import Instance
    attrs = ('name', 'removable', 'cpu', 'group')
    names = ('orientation', 'parameters', 'split', 'when', 'extend', 'jump', 'metadata')

    @staticmethod
    def load(group, instances: dict[str, Instance], components: dict[str, Comp], **kwargs) -> Instance:
        values = _standard_read(InstanceIO.Instance, group, InstanceIO.attrs, InstanceIO.names, required=(), **kwargs)
        # handle the special cases: type, at_relative, rotate_relative
        # type:
        type_name = group.attrs.get('type')
        if type_name not in components:
            raise ValueError(f"Unknown component type {type_name}")
        values['type'] = components[type_name]
        # at_relative tuple:
        vec = HDF5IO.load(group['at_vector'])
        ref = group.attrs.get('at_reference')
        if ref is not None and ref not in instances:
            raise ValueError(f"Unknown instance reference {ref}")
        values['at_relative'] = (vec, instances.get(ref) if ref is not None else None)
        # rotate_relative tuple:
        ang = HDF5IO.load(group['rotate_angles'])
        ref = group.attrs.get('rotate_reference')
        if ref is not None and ref not in instances:
            raise ValueError(f"Unknown instance reference {ref}")
        values['rotate_relative'] = (ang, instances.get(ref) if ref is not None else None)
        return InstanceIO.Instance(**values)

    @staticmethod
    def save(group, data: Instance, **kwargs):
        _standard_save(InstanceIO.Instance, group, data, InstanceIO.attrs, InstanceIO.names, **kwargs)
        # type, at_relative, rotate_relative should be _references_ to other HDF5 objects?
        # Maybe we can get away with only keeping their names, since those are unique in the instrument
        # component _type_ name:
        group.attrs['type'] = data.type.name
        # at_relative tuple:
        HDF5IO.save(group=group.create_group('at_vector'), data=data.at_relative[0])
        if data.at_relative[1] is not None:
            group.attrs['at_reference'] = data.at_relative[1].name
        # rotate_relative tuple:
        HDF5IO.save(group=group.create_group('rotate_angles'), data=data.rotate_relative[0])
        if data.rotate_relative[1] is not None:
            group.attrs['rotate_reference'] = data.rotate_relative[1].name


class InstrIO:
    from mccode_antlr.instr import Instr
    attrs = ('name', 'source')
    names = ('parameters', 'metadata', 'included', 'user', 'declare', 'initialize', 'save', 'final',
             'flags', 'registries')

    @staticmethod
    def load(group, **kwargs) -> Instr:
        values = _standard_read(InstrIO.Instr, group, InstrIO.attrs, InstrIO.names, required=(), **kwargs)
        # We had to write the component type definitions, so that they could be loaded before the instances:
        component_types = {component.name: component for component in HDF5IO.load(group['components'])}
        # And the instances need to know which component types and instances have already been loaded:
        known_instances = {}
        # Maybe we could modify the tuple loader to avoid this complexity, but this works for now
        _check_header(group['instances'], tuple)
        instance_count = group['instances'].attrs['length']
        pad = len(str(instance_count))
        instances = []
        for idx in range(instance_count):
            instance_group = group['instances'][TupleIO.entry_name(idx, pad)]
            instances.append(HDF5IO.load(instance_group, instances=known_instances, components=component_types))
            known_instances[instances[-1].name] = instances[-1]
        values['components'] = tuple(instances)
        # With all instances known, it is possible to construct the groups dictionary
        values['groups'] = HDF5IO.load(group['groups'], instances=known_instances)
        return InstrIO.Instr(**values)

    @staticmethod
    def save(group, data: Instr, **kwargs):
        _standard_save(InstrIO.Instr, group, data, InstrIO.attrs, InstrIO.names, **kwargs)
        # The groups field does not need special treatment for saving, but does for loading
        HDF5IO.save(group=group.create_group('groups'), data=data.groups)
        # the instances _must_ be recorded in order (we can recover their names later):
        HDF5IO.save(group=group.create_group('instances'), data=data.components)
        # The order of the component types in the instrument are not important.
        HDF5IO.save(group=group.create_group('components'), data=data.component_types())


class GroupIO:
    from mccode_antlr.instr import Instance, Group

    @staticmethod
    def load(group, instances: dict[str, Instance], **kwargs) -> Group:
        values = _standard_read(GroupIO.Group, group, ('name', 'index'), (), ('ids', 'member_names'), **kwargs)
        values['members'] = [instances[name] for name in values['member_names']]
        del values['member_names']
        return GroupIO.Group(**values)

    @staticmethod
    def save(group, data, **kwargs):
        _standard_save(GroupIO.Group, group, data, ('name', 'index'), ('ids', ), **kwargs)
        HDF5IO.save(group=group.create_group('member_names'), data=[member.name for member in data.members])


def RemoteRegistryIO(actual_type):
    from mccode_antlr.reader.registry import RemoteRegistry

    class _RemoteRegistryIO:
        @staticmethod
        def load(group, **kwargs) -> RemoteRegistry:
            _check_header(group, actual_type)
            values = _standard_read(actual_type, group, actual_type.file_keys(), (), (), **kwargs)
            try:
                return actual_type(**values)
            except RuntimeError:
                logger.warning(f'Unable to reconstruct {actual_type.__name__} registry from {values}')
            return RemoteRegistry('loading error', None, None, None)

        @staticmethod
        def save(group, data, **kwargs):
            _standard_save(actual_type, group, data, actual_type.file_keys(), (), **kwargs)

    return _RemoteRegistryIO


class LocalRegistryIO:
    from mccode_antlr.reader.registry import Registry, LocalRegistry

    @staticmethod
    def load(group, **kwargs) -> Registry:
        values = _standard_read(LocalRegistryIO.LocalRegistry, group, ('name', 'root'), (), (), **kwargs)
        try:
            return LocalRegistryIO.LocalRegistry(**values)
        except RuntimeError:
            logger.warning(f'Unable to reconstruct local registry from {values}')
        return LocalRegistryIO.Registry()

    @staticmethod
    def save(group, data, **kwargs):
        _standard_save(LocalRegistryIO.LocalRegistry, group, data, ('name',), (), **kwargs)
        if data.root is not None:
            group.attrs['root'] = data.root.as_posix()


def _seitz_part_io(actual_type):
    class _RotationPartIO:
        @staticmethod
        def load(group, **kwargs):
            _check_header(group, actual_type)
            v = HDF5IO.load(group['v'], **kwargs)
            if v is None:
                raise ValueError(f"Could not load v for {actual_type}")
            return actual_type(v=v)

        @staticmethod
        def save(group, data, **kwargs):
            _write_header(group, actual_type)
            if data.v is not None:
                HDF5IO.save(group=group.create_group('v'), data=data.v, **kwargs)

    return _RotationPartIO


def _named_tuple_io(typename, names):
    class _NamedTupleIO:
        @staticmethod
        def load(group, **kwargs):
            _check_header(group, typename)
            values = {name: HDF5IO.load(group[name], **kwargs) for name in names}
            if any(v is None for v in values.values()):
                raise ValueError(f"Could not load values for {typename}")
            return typename(**values)

        @staticmethod
        def save(group, data, **kwargs):
            _write_header(group, typename)
            for name in names:
                if getattr(data, name) is not None:
                    HDF5IO.save(group=group.create_group(name), data=getattr(data, name), **kwargs)

    return _NamedTupleIO


def _op_io(typename, fields: list[str]):
    class _OpIO:
        @staticmethod
        def load(group, **kwargs) -> typename:
            from mccode_antlr.common.expression import DataType, OpStyle
            _check_header(group, typename)
            attrs = {name: group.attrs.get(name) for name in ('op', 'style_number', 'data_type_name')}
            values = {name: HDF5IO.load(group[name], **kwargs) for name in fields}
            if any(v is None for v in values.values()):
                raise ValueError(f"Could not load values for {typename}")
            data_type = DataType.from_name(attrs['data_type_name'])
            style = OpStyle(attrs['style_number'])
            op = typename(data_type, style, attrs['op'], **values)
            if op.data_type != data_type:
                raise ValueError(
                    f"Loaded {typename} with data type {op.data_type}, but expected {attrs['data_type_name']}")
            return op

        @staticmethod
        def save(group, data: typename, **kwargs):
            _write_header(group, typename)
            for name in ('op',):
                if getattr(data, name) is not None:
                    group.attrs[name] = getattr(data, name)
            group.attrs['data_type_name'] = data.data_type.name
            group.attrs['style_number'] = int(data.style)
            for name in fields:
                if getattr(data, name) is not None:
                    HDF5IO.save(group=group.create_group(name), data=getattr(data, name), **kwargs)

    return _OpIO


class ValueIO:
    from mccode_antlr.common.expression import Value

    @staticmethod
    def load(group, **kwargs) -> Value:
        from mccode_antlr.common.expression import ObjectType, DataType, ShapeType
        # Since Value takes kwargs different from the calculated property names
        names = {'_object': 'object_type_name', '_shape': 'shape_type_name',
                 '_data': 'data_type_name'}
        _check_header(group, ValueIO.Value)
        types = {f: t.from_name(group.attrs.get(names[f]))
                 for t, f in ((ObjectType, '_object'), (DataType, '_data'), (ShapeType, '_shape'))}
        # A missing value is valid:
        value = HDF5IO.load(group['value'], **kwargs) if 'value' in group else None
        return ValueIO.Value(value, **types)

    @staticmethod
    def save(group, data: Value, **kwargs):
        _write_header(group, ValueIO.Value)
        for name in ('object_type', 'data_type', 'shape_type'):
            if getattr(data, name) is not None:
                group.attrs[f'{name}_name'] = getattr(data, name).name
        if data.value is not None:
            HDF5IO.save(group=group.create_group('value'), data=data.value, **kwargs)


def _iterable_read_setup(typename, group):
    _check_header(group, typename)
    count = group.attrs['length']
    pad = len(str(count))
    return count, pad


def _iterable_save_setup(typename, group, data):
    _write_header(group, typename)
    group.attrs['length'] = len(data)
    pad = len(str(len(data)))
    return pad


class ListIO:
    @staticmethod
    def entry_name(idx, pad=2):
        return f'l{idx:0{pad}d}'

    @staticmethod
    def load(group, **kwargs) -> list:
        count, pad = _iterable_read_setup(list, group)
        return [HDF5IO.load(group=group[TupleIO.entry_name(idx, pad)], **kwargs) for idx in range(count)]

    @staticmethod
    def save(group, data: tuple, **kwargs):
        pad = _iterable_save_setup(list, group, data)
        for idx, d in enumerate(data):
            HDF5IO.save(group=group.create_group(TupleIO.entry_name(idx, pad)), data=d, **kwargs)


class TupleIO:
    @staticmethod
    def entry_name(idx, pad=2):
        return f't{idx:0{pad}d}'

    @staticmethod
    def load(group, **kwargs) -> tuple:
        count, pad = _iterable_read_setup(tuple, group)
        return tuple(HDF5IO.load(group=group[TupleIO.entry_name(idx, pad)], **kwargs) for idx in range(count))

    @staticmethod
    def save(group, data: tuple, **kwargs):
        pad = _iterable_save_setup(tuple, group, data)
        for idx, d in enumerate(data):
            HDF5IO.save(group=group.create_group(TupleIO.entry_name(idx, pad), **kwargs), data=d)


class DictIO:
    @staticmethod
    def load(group, **kwargs) -> dict:
        _check_header(group, dict)
        return {k: HDF5IO.load(group=group[k], **kwargs) for k in group}

    @staticmethod
    def save(group, data: dict, **kwargs):
        _write_header(group, dict)
        for k, v in data.items():
            HDF5IO.save(group=group.create_group(k), data=v, **kwargs)


def _direct_io(cls, convert=None):
    convert = convert or cls

    class _DirectIO:
        @staticmethod
        def load(group):
            _check_header(group, cls)
            return convert(group['entry'][()])

        @staticmethod
        def save(group, data):
            _write_header(group, cls)
            group['entry'] = data

    return _DirectIO


class HDF5IO:
    import numpy as np
    from mccode_antlr.comp import Comp
    from mccode_antlr.common import InstrumentParameter, MetaData, ComponentParameter, RawC
    from mccode_antlr.common.expression import Expr, TrinaryOp, BinaryOp, UnaryOp
    from mccode_antlr.instr.jump import Jump
    from mccode_antlr.instr.orientation import (Matrix, Vector, Angles, Rotation, Seitz, RotationX, RotationY,
                                                RotationZ, TranslationPart, Orient, Parts, Part)
    from mccode_antlr.reader.registry import ModuleRemoteRegistry, GitHubRegistry

    _handlers = {
        'Instr': InstrIO,
        'InstrumentParameter': _dataclass_io(InstrumentParameter, attrs=('name', 'unit'), required=('value',)),
        'MetaData': _dataclass_io(MetaData, attrs=('name', 'mimetype', 'value'), required=('source',)),
        'DataSource': DataSourceIO,
        'Instance': InstanceIO,
        'RawC': _dataclass_io(RawC, attrs=('filename', 'line'), required=('source',), optional=('translated',)),
        'Group': GroupIO,
        'ModuleRemoteRegistry': RemoteRegistryIO(ModuleRemoteRegistry),
        'GitHubRegistry': RemoteRegistryIO(GitHubRegistry),
        'LocalRegistry': LocalRegistryIO,
        'ComponentParameter': _dataclass_io(ComponentParameter, attrs=('name',), required=('value',)),
        'Comp': _dataclass_io(Comp, attrs=('name', 'category', 'dependency', 'acc'),
                              optional=('define', 'setting', 'output', 'metadata', 'share', 'user',
                                        'declare', 'initialize', 'trace', 'save', 'final', 'display')),
        'Orient': _dataclass_io(Orient, attrs=('_degrees',), optional=('_position', '_rotation')),
        'Parts': _dataclass_io(Parts, optional=('_stack',)),
        'Part': _dataclass_io(Part, optional=('_axes',)),
        'RotationX': _seitz_part_io(RotationX),
        'RotationY': _seitz_part_io(RotationY),
        'RotationZ': _seitz_part_io(RotationZ),
        'TranslationPart': _seitz_part_io(TranslationPart),
        'Seitz': _named_tuple_io(Seitz, ('xx', 'xy', 'xz', 'xt', 'yx', 'yy', 'yz', 'yt', 'zx', 'zy', 'zz', 'zt')),
        'Rotation': _named_tuple_io(Rotation,('xx', 'xy', 'xz', 'yx', 'yy', 'yz', 'zx', 'zy', 'zz')),
        'Matrix': _named_tuple_io(Matrix, ('xx', 'xy', 'xz', 'yx', 'yy', 'yz', 'zx', 'zy', 'zz')),
        'Vector': _named_tuple_io(Vector, ('x', 'y', 'z')),
        'Angles': _named_tuple_io(Angles, ('x', 'y', 'z')),
        'Jump': _dataclass_io(Jump, attrs=('target', 'relative_target', 'iterate', 'absolute_target'),
                              required=('condition',)),
        'Value': ValueIO,
        'Expr': _dataclass_io(Expr, optional=('expr',)),  # Not a dataclass, but sufficiently similar
        'TrinaryOp': _op_io(TrinaryOp, ['first', 'second', 'third']),
        'BinaryOp': _op_io(BinaryOp, ['left', 'right']),
        'UnaryOp': _op_io(UnaryOp, ['value']),
        'list': ListIO,
        'tuple': TupleIO,
        'dict': DictIO,
        'str': _direct_io(str, convert=lambda b: b.decode('utf-8')),
        **{t.__name__: _direct_io(t) for t in (
            int,
            np.int64,
            np.int32,
            np.uint64,
            np.uint32,
            float,
            np.float32,
            np.float64,
            bool,
            np.bool_,
            bytes,
        )}
    }

    @classmethod
    def save(cls, group, data, **kwargs):
        name = data.__class__.__name__
        if name not in cls._handlers:
            logger.warning(f'No handler for {type(data)}, skipping')
            return None
        return cls._handlers[name].save(group, data, **kwargs)

    @classmethod
    def load(cls, group, **kwargs):
        version, name = _split_version_name(group.attrs[VERSION_NAME_KEY])
        if name not in cls._handlers:
            logger.warning(f'No handler for {name}, skipping')
            return None
        return cls._handlers[name].load(group, **kwargs)


def save_hdf5(obj, filename: Union[str, Path]) -> None:
    import h5py
    with h5py.File(filename, 'w', driver='core', backing_store=True) as file:
        HDF5IO.save(file, obj)


def load_hdf5(filename: Union[str, Path], path: str | None = None):
    """Load all or part of a serialized Instr from a HDF5 file.

    Parameters
    ----------
    filename : Union[str, Path]
        Path to the HDF5 file.
    path: str or None
        Location within the file to load, or None to load all.

    Warning
    -------
    HDF5 can not natively represent Python infinite precision integers, and as a result
    H5PY silently converts to fixed-bit-width integers at saving and therefore returns
    numpy.int64 integers at loading. Similarly, Bool values become numpy.bool and floats
    become something (numpy.float64?)

    Example
    -------
    >>> from mccode_antlr.io.hdf5 import load_hdf5
    >>> instrument_parameters = load_hdf5('instr.h5', 'parameters')
    """
    import h5py
    with h5py.File(filename, 'r', driver='core', backing_store=False) as file:
        return HDF5IO.load(file[path] if path else file)

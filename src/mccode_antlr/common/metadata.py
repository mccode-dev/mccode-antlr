from dataclasses import dataclass
from msgspec import Struct
from enum import Enum

# @dataclass
class DataSource(Struct):
    class Type(Enum):
        Component = 1
        Instance = 2
        Instrument = 3

    _type : Type
    _name : str

    @classmethod
    def from_dict(cls, args: dict):
        args['_type'] = DataSource.Type(args['_type'])
        return cls(**args)

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, new_name: str):
        self._name = new_name

    def is_a(self, source_type: Type):
        return self._type == source_type

    @property
    def type_name(self):
        return self._type.name

    @staticmethod
    def from_type_name_and_name(type_name: str, name: str):
        return DataSource(DataSource.Type[type_name], name)


# @dataclass
class MetaData(Struct):
    source: DataSource
    name: str
    mimetype: str
    value: str

    @classmethod
    def from_dict(cls, args: dict):
        args['source'] = DataSource.from_dict(args['source'])
        return cls(**args)

    def to_file(self, output, wrapper):
        print(wrapper.metadata_group('METADATA', self.mimetype, self.name, self.value), file=output)

    @staticmethod
    def partial_from_tokens(source: DataSource, mimetype: str, name: str, value: str):
        if ' ' in name and (name[0] != '"' or name[-1] != '"'):
            # need to differentiate names with spaces from multiple names,
            # C runtime needs escaped quote characters for printing:
            name = '"' + name + '"'
        # remove the %{ and %} sentinels, if they're present
        if '%{' == value[:2] and '%}' == value[-2:]:
            value = value[2:-2]
        return MetaData(source, name, mimetype, value)

    @staticmethod
    def from_component_tokens(source: str, mimetype: str, name: str, value: str):
        return MetaData.partial_from_tokens(source=DataSource(DataSource.Type.Component, source),
                                            mimetype=mimetype, name=name, value=value)

    @staticmethod
    def from_instance_tokens(source: str, mimetype: str, name: str, value: str):
        return MetaData.partial_from_tokens(source=DataSource(DataSource.Type.Instance, source),
                                            mimetype=mimetype, name=name, value=value)

    @staticmethod
    def from_instrument_tokens(source: str, mimetype: str, name: str, value: str):
        return MetaData.partial_from_tokens(source=DataSource(DataSource.Type.Instrument, source),
                                            mimetype=mimetype, name=name, value=value)

    # output to metadata_table_struct initializer list
    def to_table_row(self):
        from .utilities import escape_str_for_c as c
        return ','.join(c(x) for x in (self.source.name, self.name, self.mimetype, self.value))

    def copy(self):
        return MetaData(self.source, self.name, self.mimetype, self.value)
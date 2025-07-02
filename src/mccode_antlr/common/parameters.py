from dataclasses import dataclass
from msgspec import Struct
from typing import Union
from .expression import Expr


# @dataclass
class InstrumentParameter(Struct):
    name: str
    unit: str
    value: Expr

    @classmethod
    def from_dict(cls, args: dict):
        args['value'] = Expr.from_dict(args['value'])
        return cls(**args)

    def to_file(self, output, wrapper):
        from .expression import DataType
        line = ''
        if self.value.is_str:
            line = 'string '
        elif self.value.is_vector and self.value.data_type == DataType.float:
            line = 'vector '
        elif self.value.data_type == DataType.int:
            line = 'int '
        line = wrapper.datatype(line) + wrapper.parameter(self.name)
        if self.unit is not None:
            line += wrapper.unit(self.unit)
        if self.value.has_value:
            line += "=" + wrapper.value(self.value)
        print(line, file=output)

    def to_string(self, wrapper):
        from io import StringIO
        output = StringIO()
        self.to_file(output, wrapper)
        return output.getvalue().strip()

    def __str__(self):
        from mccode_antlr.common import TextWrapper
        return self.to_string(TextWrapper())

    @staticmethod
    def parse(s: str):
        from antlr4 import InputStream
        from ..grammar import McInstr_parse
        from ..instr import InstrVisitor
        visitor = InstrVisitor(None, None)
        tree = McInstr_parse(InputStream(s), 'instrument_parameter')
        return visitor.getInstrument_parameter(tree)

    def copy(self):
        return InstrumentParameter(self.name, self.unit, self.value.copy())


# @dataclass
class ComponentParameter(Struct):
    name: str
    value: Expr

    @classmethod
    def from_dict(cls, args: dict):
        args['value'] = Expr.from_dict(args['value'])
        return cls(**args)

    def to_string(self, wrapper):
        from io import StringIO
        output = StringIO()
        self.to_file(output, wrapper)
        return output.getvalue().strip()

    def __str__(self):
        from mccode_antlr.common import TextWrapper
        return self.to_string(TextWrapper())

    def to_file(self, output, wrapper):
        print(wrapper.parameter(self.name) + '=' + wrapper.value(self.value), file=output)

    def compatible_value(self, value):
        return self.value.compatible(value, id_ok=True)

    def __eq__(self, other):
        if isinstance(other, ComponentParameter):
            return self.name == other.name and self.value == other.value
        return self.value == other


def parameter_name_present(parameters: tuple[Union[InstrumentParameter, ComponentParameter], ...],
                           name: str) -> bool:
    return any(name == x.name for x in parameters)

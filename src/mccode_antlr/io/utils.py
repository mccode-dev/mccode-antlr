from pathlib import Path
from typing import Any, Type
import msgspec
import numpy as np

from mccode_antlr.reader.registry import (
    Registry, RemoteRegistry, ModuleRemoteRegistry, GitHubRegistry, LocalRegistry
)
from mccode_antlr.comp import Comp
from mccode_antlr.instr import Instance, Instr, Group
from mccode_antlr.common import InstrumentParameter, MetaData, ComponentParameter, RawC
from mccode_antlr.common.expression import Value, Expr, TrinaryOp, BinaryOp, UnaryOp
from mccode_antlr.instr.jump import Jump
from mccode_antlr.instr.orientation import (Matrix, Vector, Angles, Rotation, Seitz,
                                            RotationX, RotationY, RotationZ,
                                            TranslationPart, Orient, Parts, Part)
from mccode_antlr.common.metadata import DataSource

MODEL_ENC = {
    Instr: 'Instr',
    Instance: 'Instance',
    Comp: 'Comp',
    Group: 'Group',
    InstrumentParameter: 'InstrumentParameter',
    MetaData: 'MetaData',
    ComponentParameter: 'ComponentParameter',
    RawC: 'RawC',
    Value: 'Value',
    Expr: 'Expr',
    TrinaryOp: 'TrinaryOp',
    BinaryOp: 'BinaryOp',
    UnaryOp: 'UnaryOp',
    Jump: 'Jump',
    Matrix: 'Matrix',
    Vector: 'Vector',
    Angles: 'Angles',
    Rotation: 'Rotation',
    Seitz: 'Seitz',
    RotationX: 'RotationX',
    RotationY: 'RotationY',
    RotationZ: 'RotationZ',
    TranslationPart: 'TranslationPart',
    Orient: 'Orient',
    Parts: 'Parts',
    Part: 'Part',
    DataSource: 'DataSource',
}
MODEL_DEC = {v: k for k, v in MODEL_ENC.items()}

REGISTRY_TYPES = (
    Registry, RemoteRegistry, ModuleRemoteRegistry, GitHubRegistry, LocalRegistry
)


class Model(msgspec.Struct):
    name: str
    obj: msgspec.Raw

    @classmethod
    def from_value(cls, obj: Any, encoder=None):
        if encoder is None:
            raise ValueError("An encoder must be provided")
        model_type = MODEL_ENC[type(obj)]
        if hasattr(obj, 'to_dict'):
            obj = obj.to_dict()
        return cls(model_type, msgspec.Raw(encoder.encode(obj)))


def to_model(model_encoder, obj):
    return Model(model_encoder, obj)


def from_model(model_decoder, model):
    if model.name in MODEL_DEC:
        data = model_decoder.decode(model.obj)
        return MODEL_DEC[model.name].from_dict(data)
    else:
        raise ValueError(f'Model {model.name} is not supported')


def enc_hook(obj):
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, Path):
        return str(obj)
    elif type(obj) in REGISTRY_TYPES:
        return obj.file_contents()
    raise NotImplementedError(f"{type(obj)} not supported")


def dec_hook(typ: Type, obj: Any) -> Any:
    if typ is Path:
        return Path(obj)
    elif typ in REGISTRY_TYPES:
        return typ(**obj)
    raise NotImplementedError(f"{typ} not supported")
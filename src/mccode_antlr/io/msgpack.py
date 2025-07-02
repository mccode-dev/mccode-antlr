from __future__ import annotations
from pathlib import Path
import msgspec
from mccode_antlr.io.utils import enc_hook, dec_hook, Model, from_model


def to_msgpack(obj) -> bytes:
    encoder = msgspec.msgpack.Encoder(enc_hook=enc_hook)
    return encoder.encode(Model.from_value(obj, encoder=encoder))


def from_msgpack(msg: bytes):
    decoder = msgspec.msgpack.Decoder(dec_hook=dec_hook)
    return from_model(decoder, msgspec.msgpack.decode(msg, type=Model))


def save_msgpack(obj, filename: str | Path) -> None:
    with open(filename, "wb") as f:
        f.write(to_msgpack(obj))


def load_msgpack(filename: str | Path):
    with open(filename, "rb") as f:
        return from_msgpack(f.read())

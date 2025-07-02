from __future__ import annotations
from pathlib import Path
import msgspec
from mccode_antlr.io.utils import enc_hook, dec_hook, Model, from_model


def to_json(obj) -> bytes:
    encoder = msgspec.json.Encoder(enc_hook=enc_hook)
    return encoder.encode(Model.from_value(obj, encoder=encoder))


def from_json(msg: bytes):
    decoder = msgspec.json.Decoder(dec_hook=dec_hook)
    return from_model(decoder, msgspec.json.decode(msg, type=Model))


def save_json(obj, filename: str | Path) -> None:
    with open(filename, "wb") as f:
        f.write(to_json(obj))


def load_json(filename: str | Path):
    with open(filename, "rb") as f:
        return from_json(f.read())

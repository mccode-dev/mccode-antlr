"""A stable content digest for an Instr.

`Instr.__hash__` folds Python string hashes, so it varies with PYTHONHASHSEED and
cannot be written into a file and compared later. This module provides a digest
that is stable across processes and machines, for use as a cache key deciding
whether a compiled binary still matches the instrument it was built from.
"""
from __future__ import annotations

_DIGEST_FORMAT = 1
_DEFAULT_LENGTH = 16

#: Fields which are lazily populated caches of derived data rather than content.
#: `RawC.translated` memoises the C translation of `RawC.source`, is None until a
#: translation has run, and is shared between instruments through the component
#: cache -- so hashing it would make the digest depend on what happened to run
#: earlier in the process. `source` is hashed instead, and fully determines it.
_VOLATILE_KEYS = frozenset({'translated'})


def _strip_volatile(value):
    if isinstance(value, dict):
        return {k: _strip_volatile(v) for k, v in value.items() if k not in _VOLATILE_KEYS}
    if isinstance(value, list):
        return [_strip_volatile(v) for v in value]
    return value


def instrument_digest(instr, length: int = _DEFAULT_LENGTH) -> str:
    """Return a hex digest of the content of *instr*.

    The digest covers everything the C translation depends on: parameters,
    component instances (including their full component definitions), included
    instruments, the raw C blocks, and the DEPENDENCY flags. It also folds in the
    mccode-antlr version, so upgrading the package invalidates cached binaries.

    Registries are deliberately excluded. `Instr.to_dict` runs
    `with_embedded_files` over them, which walks the filesystem on every call and
    bakes machine-absolute paths into the result -- neither of which belongs on a
    cache-check path. The cost is that editing a file which lives *only* in a
    registry does not invalidate a binary built from it.
    """
    import json
    from hashlib import sha256
    from msgspec.structs import replace
    from mccode_antlr.io.json import to_json
    from mccode_antlr.build_info import BUILD_INFO_NAME
    from mccode_antlr.version import version

    reduced = replace(
        instr,
        registries=(),
        # Defence in depth: the build-info entry is never added to Instr.metadata,
        # but a hand-added one must not make the digest depend on itself.
        metadata=tuple(m for m in instr.metadata if m.name != BUILD_INFO_NAME),
    )
    # Round-tripping through plain JSON to drop the volatile fields also sorts the
    # keys, so the digest does not depend on struct field declaration order either.
    content = json.dumps(_strip_volatile(json.loads(to_json(reduced))),
                         sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    digest = sha256(f'{_DIGEST_FORMAT}:{version()}:'.encode('utf-8'))
    digest.update(content.encode('utf-8'))
    return digest.hexdigest()[:length]

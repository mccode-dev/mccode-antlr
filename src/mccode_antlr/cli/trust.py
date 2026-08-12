"""Shared handling of the --trust-local-registries CLI flag.

The flag is an override for the ``serialization.trust_local_registries`` setting,
so it has to reach the in-memory config before anything deserializes an
instrument. Every entry point that accepts a serialized instrument applies it.
"""
from __future__ import annotations


def apply_registry_trust(args) -> None:
    """Push --trust-local-registries / --no-trust-local-registries into the config.

    A `None` value means the flag was not given, in which case the configured
    value (default false) stands.
    """
    value = getattr(args, 'trust_local_registries', None)
    if value is None:
        return
    from mccode_antlr.config import config
    config['serialization']['trust_local_registries'] = bool(value)
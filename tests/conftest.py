import pytest


@pytest.fixture
def trusted_local_registries():
    """Opt in to trusting LocalRegistry entries restored from serialized artifacts.

    The confuse config is a process-wide singleton, so the previous value is put
    back afterwards to keep tests independent of execution order.
    """
    from mccode_antlr.config import config
    section = config['serialization']['trust_local_registries']
    had = section.exists()
    previous = section.get() if had else None
    config['serialization']['trust_local_registries'] = True
    try:
        yield
    finally:
        if had:
            config['serialization']['trust_local_registries'] = previous
        else:
            config['serialization']['trust_local_registries'] = False

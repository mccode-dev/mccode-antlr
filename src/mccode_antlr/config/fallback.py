from __future__ import annotations
from collections.abc import Callable
from confuse import LazyConfig, Subview
from loguru import logger

def config_fallback(
        cfg: LazyConfig | Subview,
        key: str,
        method: str | None = None,
        prog: str | None = None,
        failsafe: Callable[[str], str] | None = None,
        store: bool = True,
):
    import platform
    from subprocess import getstatusoutput, run
    method = method or 'get'
    prog = prog or f'{key}-config --show buildflags'
    if failsafe is None:
        failsafe = lambda x: f'-l{x}'
    if key in cfg:
        return getattr(cfg[key], method)()

    # If the specified program exists
    checker = {'Windows': 'where'}.get(platform.system(), 'which')
    status, output = getstatusoutput(f'{checker} {prog.split()[0]}')
    if 0 == status:
        # Try running it
        status, output = getstatusoutput(prog)
    # If it failed, fallback again to the failsafe result
    if status:
        output = failsafe(key)
        logger.warning(f'Unable to find {key} or use {prog}, defaulting to {output}')

    # No matter what, if we got this far store the result in the working config cache
    # to avoid needing to re-run any possibly-expensive function.
    # This is predicated on the idea that only one possible function would be called
    if store:
        cfg[key] = output
    return output

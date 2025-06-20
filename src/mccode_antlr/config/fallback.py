from __future__ import annotations
from collections.abc import Callable
from confuse import LazyConfig, Subview
from loguru import logger

def config_fallback(
        cfg: LazyConfig | Subview,
        key: str,
        method: str | None = None,
        prog: list[str] | None = None,
        failsafe: Callable[[str], str] | None = None,
        store: bool = True,
):
    """Retrieve a key from a configuration object or try other methods to find it

    Parameters
    ----------
    cfg : LazyConfig | Subview
        The configuration object or the subview in which we expect to find the key.
    key : str
        The key to retrieve from the configuration object.
    method: str | None
        The method to use to retrieve the key from the configuration object, likely
        one of `'get', `'as_str', or `'as_str_expanded'.
    prog: list[str] | None
        The arguments for a system call which would provide the value for this
        configuration entry. If not provided, the default behavior is to treat
        the key as the project name of a MCPL or NCrystal like project, for which
        we want the build flags -- e.g. by running, `'mcpl-config --show buildflags'`.
    failsafe: Callable[[str] | str] | None
        In case the key is not present and the system call fails, a backup callable
        is used to provide _some_ value for the key. If not provided the default is
        to use, effectively, `f'-l{key}'`.
    store: bool
        Whether to store the returned value in the configuration object, default `True`.
        In case the system call or failsafe function are slow we likely do not want to
        evaluate them more than once.
    """
    from shutil import which
    from subprocess import run
    if key in cfg:
        return getattr(cfg[key], method or 'get')()

    prog = prog or [f'{key}-config', '--show', 'buildflags']

    message, output = None, None
    if which(prog[0]):
        res = run(prog, capture_output=True, text=True)
        output = res.stdout
        if res.returncode or len(res.stderr):
            message = f'Evaluating "{" ".join(prog)}" produced error: {res.stderr}'
    else:
        message = f'{prog[0]} not found'

    if message:
        if failsafe is None:
            failsafe = lambda x: f'-l{x}'
        output = failsafe(key)
        logger.warning(f'{message}, defaulting to {output}')

    if store:
        cfg[key] = output
    return output

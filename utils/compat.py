"""
utils/compat.py
Surviving a half-updated deployment.

THE FAILURE THIS EXISTS FOR
---------------------------
Streamlit re-executes the entry script on every run, but `from frontend import
landing` returns whatever is already in ``sys.modules``. On a hosted container
that pulled a new commit without restarting the process, the entry script is
the new one and the imported modules are the old ones. A keyword argument
added in the same commit to both caller and callee then blows up:

    TypeError: render() got an unexpected keyword argument 'world_uri'

The repository is perfectly consistent; only the running process is not. It
has happened twice on Streamlit Community Cloud, and the visible result is a
traceback on the home page, which for a page whose whole job is to be opened
by someone else is the worst possible outcome.

WHAT THIS DOES ABOUT IT
-----------------------
:func:`call_supported` drops keyword arguments the target does not accept and
reports which ones it dropped. The page then renders in its older form -
missing whatever the new argument added, and nothing else - and the caller can
say plainly that the server is running stale code and needs a reboot.

This is deliberately narrow. It is used at the three component boundaries
where a new argument has actually been added mid-deployment, not as a general
calling convention: silently swallowing a genuine typo in a keyword name would
be far worse than the crash it prevents.
"""

from __future__ import annotations

import inspect
from typing import Any, Callable, List, Tuple


def unsupported_kwargs(func: Callable, kwargs: dict) -> List[str]:
    """
    Names in ``kwargs`` that ``func`` cannot accept.

    A function taking ``**kwargs`` accepts everything, so nothing is
    unsupported. If the signature cannot be read at all - a builtin, or
    something wrapped past recognition - assume every argument is fine and
    let the call fail honestly rather than dropping arguments on a guess.
    """
    try:
        parameters = inspect.signature(func).parameters
    except (TypeError, ValueError):
        return []

    if any(p.kind is inspect.Parameter.VAR_KEYWORD
           for p in parameters.values()):
        return []

    return [name for name in kwargs if name not in parameters]


def call_supported(func: Callable, *args: Any,
                   **kwargs: Any) -> Tuple[Any, List[str]]:
    """
    Call ``func``, omitting any keyword argument it does not accept.

    Returns ``(result, dropped)``. ``dropped`` is empty on a healthy
    deployment, and its contents are the evidence that the process is running
    an older copy of the target module than the one that called it.
    """
    dropped = unsupported_kwargs(func, kwargs)

    if dropped:
        kwargs = {k: v for k, v in kwargs.items() if k not in dropped}

    return func(*args, **kwargs), dropped


def stale_module_warning(dropped: List[str], target: str) -> str:
    """The sentence to show a viewer when arguments had to be dropped."""
    names = ", ".join(sorted(dropped))
    return (
        f"This server is running an older copy of `{target}` than the page "
        f"that called it, so {names} had nothing to apply to. The deployment "
        f"picked up new code without restarting its Python process. "
        f"Reboot the app to clear it — nothing is wrong with the repository."
    )

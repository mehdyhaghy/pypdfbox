"""PEP 562 helper for lazy package re-exports.

A package ``__init__`` that only re-exports names from its submodules can
hand this helper a ``{name: submodule}`` map instead of importing every
submodule eagerly. Each name is imported on first attribute access and then
cached in the package namespace, so ``from pkg import Name`` returns the same
object the eager import used to.
"""

from collections.abc import Callable
from importlib import import_module
from typing import Any


def attach(
    package: str, exports: dict[str, str]
) -> tuple[Callable[[str], Any], Callable[[], list[str]]]:
    """Return ``(__getattr__, __dir__)`` for ``package``.

    ``exports`` maps each public name to the submodule defining it, either
    relative (``".pd_page"``) or absolute.
    """
    namespace = import_module(package).__dict__

    def _getattr(name: str) -> Any:
        module_name = exports.get(name)
        if module_name is None:
            raise AttributeError(f"module {package!r} has no attribute {name!r}")
        value = getattr(import_module(module_name, package), name)
        namespace[name] = value
        return value

    def _dir() -> list[str]:
        return sorted(set(namespace) | set(exports))

    return _getattr, _dir


def lazy_modules(module: str, modules: dict[str, str]) -> Callable[[str], Any]:
    """Return a module ``__getattr__`` that imports third-party modules on use.

    Keeps ``some_module.Image`` / ``some_module.np``-style attributes
    reachable for callers (and tests) after the module moved its own heavy
    imports into the functions that need them. ``modules`` maps the
    attribute name to an absolute module path (``{"Image": "PIL.Image"}``)
    or to ``"module:attribute"`` for a name imported from a module
    (``{"cffStandardStrings": "fontTools.cffLib:cffStandardStrings"}``).
    """
    namespace = import_module(module).__dict__

    def _getattr(name: str) -> Any:
        target = modules.get(name)
        if target is None:
            raise AttributeError(f"module {module!r} has no attribute {name!r}")
        module_name, _, attribute = target.partition(":")
        value = import_module(module_name)
        if attribute:
            value = getattr(value, attribute)
        namespace[name] = value
        return value

    return _getattr
